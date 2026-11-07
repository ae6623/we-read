#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EPUB 上传服务：接收上传 → 落盘 git 目录 → 维护 uploads.json → 入队补笔记 → 本地 commit。

为什么需要它：GitHub Pages 是纯静态托管，浏览器不能写文件、不能 commit、不能起后台任务。
本进程跑在本机，同时静态托管仓库根目录，使上传、清单读取、epub.js 加载全部同源。

接口：
  GET  /api/health                 -> 服务状态 / 上传目录 / registry revision
  GET  /api/uploads                -> uploads.json 清单
  POST /api/upload?name=书名.epub  -> 原始二进制 body（application/octet-stream）
                                     文件名也可用 X-File-Name 请求头（URL 编码）
  GET  /reading-notes/epub/...     -> 静态托管（与 API 同源）

启动（仓库根目录）：
  python tools/epub-upload-server/app.py
  # 然后打开 http://127.0.0.1:8788/reading-notes/epub/index.html

环境变量：
  PORT=8788                  监听端口（默认只绑 127.0.0.1）
  HOST=127.0.0.1             监听地址
  REPO_ROOT=<path>           仓库根（默认按本文件位置上溯）
  MAX_BYTES=15728640         单文件上限，默认 15 MB
  AUTO_PUSH=0                设 1 才 pull --rebase + push；默认只本地 commit
  PIPELINE_HOOK=<cmd>        可选异步钩子，支持 {book_id} {title} {file} 占位符，不等待
  NO_GIT=1                   完全跳过 git 操作（只落盘 + 入队）

真实性边界：入队只表示写进 book-registry.json 的 queued 队列并追加交接事件，
由读书 Agent 按 reading-state-protocol.md 认领跑书补笔记；本服务不启动别的 Agent，
不宣称笔记已生成、不宣称用户亲读或完读，不改 roster / 活动锁 / completion / 完读计数。
"""
import datetime as _dt
import functools
import hashlib
import io
import json
import os
import posixpath
import re
import subprocess
import sys
import threading
import urllib.parse
import zipfile
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from xml.etree import ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.environ.get("REPO_ROOT") or os.path.abspath(os.path.join(HERE, "..", ".."))
PORT = int(os.environ.get("PORT", "8788"))
HOST = os.environ.get("HOST", "127.0.0.1")
MAX_BYTES = int(os.environ.get("MAX_BYTES", str(15 * 1024 * 1024)))
AUTO_PUSH = os.environ.get("AUTO_PUSH", "0") == "1"
NO_GIT = os.environ.get("NO_GIT", "0") == "1"
PIPELINE_HOOK = os.environ.get("PIPELINE_HOOK", "").strip()
TZ = _dt.timezone(_dt.timedelta(hours=8))

EPUB_DIR = os.path.join(REPO_ROOT, "reading-notes", "epub")
UPLOAD_DIR = os.path.join(EPUB_DIR, "uploads")
CATALOG = os.path.join(EPUB_DIR, "uploads.json")
REGISTRY = os.path.join(REPO_ROOT, "skills", "luoyu-reading", "references", "book-registry.json")
COMM_ROOT = os.path.join(REPO_ROOT, "skills", "luoyu-reading", "references", "agent-communication")
WRITE_LOCK = threading.Lock()

os.makedirs(UPLOAD_DIR, exist_ok=True)
if not os.path.exists(CATALOG):
    with open(CATALOG, "w", encoding="utf-8") as f:
        json.dump({"generated": _dt.date.today().isoformat(), "source": "upload",
                   "count": 0, "books": []}, f, ensure_ascii=False, indent=2)


def now():
    return _dt.datetime.now(TZ)


def atomic_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def read_json(path, fallback):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return fallback


def rel(path):
    return os.path.relpath(path, REPO_ROOT).replace(os.sep, "/")


# ---------------------------------------------------------------- EPUB 校验
class InvalidEpub(Exception):
    pass


def parse_epub(data):
    """校验 EPUB 容器，返回 (title, author, chapters)。"""
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except Exception as exc:
        raise InvalidEpub("不是有效的 EPUB/ZIP 文件：%s" % exc)
    with zf:
        names = zf.namelist()
        if not names or names[0] != "mimetype":
            raise InvalidEpub("mimetype 必须是 ZIP 第一个条目")
        info = zf.infolist()[0]
        if info.compress_type != zipfile.ZIP_STORED:
            raise InvalidEpub("mimetype 必须不压缩（STORED）")
        if (zf.read("mimetype") or b"").strip() != b"application/epub+zip":
            raise InvalidEpub("mimetype 内容不是 application/epub+zip")
        if "META-INF/container.xml" not in names:
            raise InvalidEpub("缺少 META-INF/container.xml")

        opf_path, title, author = None, "", ""
        try:
            root = ET.fromstring(zf.read("META-INF/container.xml"))
            for el in root.iter():
                if el.tag.endswith("rootfile") and el.get("full-path"):
                    opf_path = el.get("full-path")
                    break
        except ET.ParseError:
            opf_path = None
        if opf_path and opf_path in names:
            try:
                opf = ET.fromstring(zf.read(opf_path))
                for el in opf.iter():
                    tag = el.tag.split("}")[-1].lower()
                    if tag == "title" and not title and (el.text or "").strip():
                        title = el.text.strip()
                    elif tag == "creator" and not author and (el.text or "").strip():
                        author = el.text.strip()
            except ET.ParseError:
                pass
        chapters = len([n for n in names
                        if n.lower().endswith((".xhtml", ".html")) and not n.startswith("META-INF/")])
    return title, author, max(chapters, 1)


def norm_title(s):
    return re.sub(r"\s+", "", re.sub(r"[（(【\[].*?[）)】\]]", "", s or "")).strip().lower()


# ---------------------------------------------------------------- 入队 / 事件
def enqueue(bid, title, author, file_rel, sha, byte_len, chapters, opf_note):
    """按 reading-state-protocol.md 以 queued 入队；返回 (queued, revision, event_rel)。"""
    reg = read_json(REGISTRY, None)
    if not isinstance(reg, dict) or not isinstance(reg.get("books"), list):
        raise RuntimeError("book-registry.json 不可读或结构异常，已跳过入队")

    exists = any(b.get("book_id") == bid for b in reg["books"])
    old_rev = int(reg.get("revision", 0))
    queued = False
    if not exists:
        stamp = now().strftime("%Y-%m-%dT%H:%M:%S+08:00")
        reg["books"].append({
            "book_id": bid,
            "title": title,
            "author": author or "未署名",
            "platform": "local_pdf",
            "platform_book_id": None,
            "priority": "user_requested",
            "status": "queued",
            "owner_agent_id": None,
            "claim": {
                "state": "unclaimed",
                "source": "用户于 %s 通过本机上传服务上传本地 EPUB，要求新增并生成笔记；排在已有持有任务之后。" % stamp,
                "claimed_at": None
            },
            "last_confirmed_progress": None,
            "resume_point": {
                "status": "needs-confirmation",
                "chapter": None,
                "page": None,
                "position": "尚未开始；无已确认用户亲读位置。",
                "source": "用户上传的本地 EPUB；尚未开始阅读。",
                "confirmed_at": None
            },
            "next_question_status": "needs-confirmation",
            "completion": None,
            "source_format": "epub",
            "upload_path": file_rel,
            "upload_sha256": sha,
            "upload_size": byte_len,
            "upload_chapters": chapters,
            "note_status": "pending",
            "bibliographic_note": opf_note
        })
        reg["revision"] = old_rev + 1
        reg["updated_at"] = stamp
        atomic_json(REGISTRY, reg)
        queued = True

    event_lines = [
        "",
        "### [%s] 用户（本机上传服务代写） / %s" % (now().strftime("%Y-%m-%d %H:%M"), bid),
        "- 类型：用户上传本地 EPUB → 入队补笔记；**不是阅读场次，不代表亲读或完读**。",
        "- 书名：《%s》；作者：%s；稳定 ID `%s`。" % (title, author or "未署名", bid),
        "- 源文件：`%s`（%d 字节，sha256 %s，%d 个 XHTML 分片）。" % (file_rel, byte_len, sha, chapters),
        "- 登记：registry revision %d → %d，status `queued`、owner 空、claim `unclaimed`、"
        "priority `user_requested`、`source_format: epub`；排在已有持有任务之后。" %
        (old_rev, int(reg.get("revision", old_rev))),
        "- 要求：按 `reading-state-protocol.md` 由管理员分发，阅读 Agent 认领后跑书并补笔记；"
        "不自行抢占活动锁，不改 roster / resume_point / completion / 完读计数。",
        "- 重复上传：%s。" % ("本次为同名覆盖，未重复入队" if not queued else "新书，已入队"),
        "- 边界：文件进入公开仓库，`noindex` 不等于私有；Git 记录不等于消息已送达。",
        ""
    ]
    d = now().strftime("%Y/%m").split("/")
    comm_dir = os.path.join(COMM_ROOT, d[0], d[1])
    os.makedirs(comm_dir, exist_ok=True)
    comm_file = os.path.join(comm_dir, "%s.md" % now().strftime("%Y-%m-%d"))
    with open(comm_file, "a", encoding="utf-8") as f:
        f.write("\n".join(event_lines))
    return queued, int(reg.get("revision", old_rev)), rel(comm_file)


# ---------------------------------------------------------------- git / 钩子
def run_git(args):
    if NO_GIT:
        return True, "NO_GIT=1 已跳过"
    try:
        p = subprocess.run(["git", "-C", REPO_ROOT] + args, capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=90)
        if p.returncode != 0:
            return False, (p.stderr or p.stdout or "").strip()[:300]
        return True, (p.stdout or "").strip()[:200]
    except Exception as exc:
        return False, str(exc)[:300]


def commit_all(bid, title, paths):
    notes = []
    ok, msg = run_git(["add", "--"] + paths)
    if not ok:
        return ["git add 失败：%s" % msg]
    ok, msg = run_git(["commit", "-m", "upload: %s（%s）本地 EPUB 入队补笔记" % (title[:40], bid)])
    if not ok:
        notes.append("本地 commit 未成功：%s" % msg)
    else:
        notes.append("已本地 commit")
    if AUTO_PUSH:
        ok, msg = run_git(["pull", "--rebase", "origin", "main"])
        if not ok:
            notes.append("pull --rebase 失败，未 push：%s" % msg)
            return notes
        ok, msg = run_git(["push", "origin", "HEAD:main"])
        notes.append("已 push 到 main" if ok else "push 失败：%s" % msg)
    return notes


def fire_hook(bid, title, file_rel):
    if not PIPELINE_HOOK:
        return
    cmd = (PIPELINE_HOOK.replace("{book_id}", bid)
           .replace("{title}", title)
           .replace("{file}", file_rel))
    try:
        subprocess.Popen(cmd, shell=True, cwd=REPO_ROOT,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as exc:
        sys.stderr.write("PIPELINE_HOOK 启动失败：%s\n" % exc)


# ---------------------------------------------------------------- 业务逻辑
def handle_upload(raw, raw_name):
    if not raw:
        raise InvalidEpub("请求体为空")
    if len(raw) > MAX_BYTES:
        raise InvalidEpub("文件 %.1f MB 超过 %.1f MB 上限" % (len(raw) / 1048576.0, MAX_BYTES / 1048576.0))
    name = urllib.parse.unquote(raw_name or "").replace("\\", "/").split("/")[-1]
    if not name.lower().endswith(".epub"):
        raise InvalidEpub("只允许 .epub 文件")
    safe_name = re.sub(r"[^\w\u4e00-\u9fff.\-()（）\[\]【】 ]+", "_", name)
    fallback = safe_name[:-5].strip() or "未命名"
    title, author, chapters = parse_epub(raw)
    title = re.sub(r"\s+", " ", (title or "").strip())[:120] or fallback
    author = re.sub(r"\s+", " ", (author or "").strip())[:80] or "未署名"
    bid = "upload-" + hashlib.sha256(norm_title(title).encode("utf-8")).hexdigest()[:12]
    sha = hashlib.sha256(raw).hexdigest()
    file_rel = "reading-notes/epub/uploads/%s.epub" % bid
    dest = os.path.join(REPO_ROOT, *file_rel.split("/"))

    with WRITE_LOCK:
        tmp = dest + ".part"
        with open(tmp, "wb") as f:
            f.write(raw)
        os.replace(tmp, dest)

        catalog = read_json(CATALOG, {"books": []})
        books = [b for b in catalog.get("books", []) if b.get("id") != bid]
        books.append({
            "id": bid,
            "title": title,
            "author": author,
            "pages": 0,
            "chars": 0,
            "chapters": chapters,
            "bytes": len(raw),
            "file": "uploads/%s.epub" % bid,
            "source": "upload",
            "source_name": name,
            "sha256": sha,
            "uploaded_at": now().strftime("%Y-%m-%dT%H:%M:%S+08:00"),
            "note_status": "待补笔记"
        })
        books.sort(key=lambda b: b.get("title", ""))
        atomic_json(CATALOG, {"generated": now().date().isoformat(),
                              "source": "upload", "count": len(books), "books": books})

        opf_note = "EPUB 元数据：标题《%s》，作者 %s，%d 个 XHTML 分片；本机上传服务读取。" % (
            title, author, chapters)
        queued, revision, event_rel = enqueue(bid, title, author, file_rel, sha,
                                              len(raw), chapters, opf_note)

        changed = [file_rel, rel(CATALOG)]
        if queued:
            changed += [rel(REGISTRY), event_rel]
        git_notes = commit_all(bid, title, changed)

    fire_hook(bid, title, file_rel)
    return {
        "ok": True,
        "book_id": bid,
        "title": title,
        "author": author,
        "file": "uploads/%s.epub" % bid,
        "bytes": len(raw),
        "chapters": chapters,
        "queued": queued,
        "duplicate": not queued,
        "registry_revision": revision,
        "event": event_rel,
        "git": git_notes,
        "note": "已入队 queued，等待读书 Agent 认领补笔记；不代表笔记已生成"
    }


# ---------------------------------------------------------------- HTTP
class Handler(SimpleHTTPRequestHandler):
    extensions_map = dict(SimpleHTTPRequestHandler.extensions_map)
    extensions_map.update({".epub": "application/epub+zip", ".json": "application/json"})

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-File-Name")
        super().end_headers()

    def log_message(self, *args):
        pass  # 不刷屏；错误通过响应体回报

    def _json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if "/.git/" in path or path.startswith("/.workbuddy/") or "/.env" in path:
            self.send_error(403, "forbidden")
            return
        if path == "/api/health":
            reg = read_json(REGISTRY, {})
            self._json(200, {
                "ok": True,
                "repo_root": REPO_ROOT,
                "upload_dir": rel(UPLOAD_DIR),
                "max_bytes": MAX_BYTES,
                "auto_push": AUTO_PUSH,
                "pipeline_hook": bool(PIPELINE_HOOK),
                "registry_revision": reg.get("revision") if isinstance(reg, dict) else None,
                "time": now().strftime("%Y-%m-%d %H:%M:%S+08:00")
            })
            return
        if path == "/api/uploads":
            self._json(200, read_json(CATALOG, {"books": []}))
            return
        return super().do_GET()

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        if u.path != "/api/upload":
            self._json(404, {"ok": False, "error": "未知接口"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0:
            self._json(400, {"ok": False, "error": "缺少请求体"})
            return
        if length > MAX_BYTES:
            self._json(413, {"ok": False, "error": "超过 %.1f MB 上限" % (MAX_BYTES / 1048576.0)})
            return
        q = urllib.parse.parse_qs(u.query)
        name = (q.get("name") or [""])[0] or self.headers.get("X-File-Name", "")
        try:
            raw = self.rfile.read(length)
            result = handle_upload(raw, name)
            self._json(200, result)
        except InvalidEpub as exc:
            self._json(400, {"ok": False, "error": str(exc)})
        except Exception as exc:
            sys.stderr.write("upload failed: %r\n" % (exc,))
            self._json(500, {"ok": False, "error": "服务端失败：%s" % exc})


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main():
    handler = functools.partial(Handler, directory=REPO_ROOT)
    srv = Server((HOST, PORT), handler)
    print("EPUB 上传服务已启动")
    print("  仓库根   : %s" % REPO_ROOT)
    print("  上传目录 : %s" % rel(UPLOAD_DIR))
    print("  上限     : %.1f MB / 本" % (MAX_BYTES / 1048576.0))
    print("  自动推送 : %s" % ("开启（AUTO_PUSH=1）" if AUTO_PUSH else "关闭，只本地 commit"))
    print("  异步钩子 : %s" % (PIPELINE_HOOK or "未配置，仅入队"))
    print("  书架入口 : http://%s:%d/reading-notes/epub/index.html" % (HOST, PORT))
    print("  阅读器   : http://%s:%d/reading-notes/epub/reader.html" % (HOST, PORT))
    print("  说明     : 入队只写 registry queued + 交接事件，由读书 Agent 认领补笔记")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()
