#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EPUB 上传服务（双模式，同一份代码）

形态一 · 本机仓库模式
    在 we-read 仓库根目录运行：上传的 EPUB 落到 reading-notes/epub/uploads/，
    写 uploads.json；按 reading-state-protocol.md 往 book-registry.json 追加
    queued 记录、追加交接事件；本地 git commit（AUTO_PUSH=1 才 push）。

形态二 · 在线沙箱模式
    部署成单端口 HTTP 应用（平台注入 PORT，绑定 0.0.0.0）。沙箱里没有 git 仓库，
    文件保存到应用数据目录 data/uploads/，维护 uploads.json、queue.json（registry
    兼容字段）、events/YYYY-MM-DD.md；提供队列与同步导出 API，并可选 POST
    PIPELINE_WEBHOOK 异步启动补书流程。sync_to_git.py 可把沙箱数据拉回仓库，
    完成「保存进 git」的闭环。

接口：
  GET  /api/health                  服务状态 / 模式 / 上传目录 / revision
  GET  /api/uploads                 上传书目清单（file 为可直接阅读的绝对 URL）
  GET  /api/queue                  补书任务队列（registry 兼容 queued 条目）
  GET  /api/events?date=YYYY-MM-DD 当日交接事件文本
  GET  /api/sync                   清单 + 队列 + 事件 + 下载链接（供同步脚本）
  GET  /uploads/<book_id>.epub     EPUB 二进制（带 CORS）
  POST /api/upload?name=书名.epub  原始二进制 body（application/octet-stream）；
                                   文件名也可放 X-File-Name 请求头（URL 编码）

环境变量：
  MODE=repo|sandbox        强制模式；默认按目录里是否存在 book-registry.json 自动判定
  PORT=8788                监听端口（托管平台注入）
  HOST=127.0.0.1           监听地址；沙箱/托管时自动改 0.0.0.0
  REPO_ROOT=<path>         仓库根（本机模式）
  DATA_ROOT=<path>         数据目录（沙箱模式，默认 ./data）
  MAX_BYTES=15728640       单文件上限，默认 15 MB
  AUTO_PUSH=0              设 1 才 pull --rebase + push；默认只本地 commit
  NO_GIT=1                 跳过 git 操作（只落盘 + 入队）
  PIPELINE_HOOK=<cmd>      可选本机异步命令，支持 {book_id} {title} {file}
  PIPELINE_WEBHOOK=<url>   可选在线异步回调，POST JSON 任务，不等待结果

真实性边界：入队只表示写进队列（本机是 book-registry.json），由读书 Agent 按
reading-state-protocol.md 认领跑书补笔记；本服务不启动别的 Agent、不宣称笔记已生成、
不宣称用户亲读或完读，不改 roster / 活动锁 / completion / 完读计数。
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
import tempfile
import threading
import urllib.parse
import urllib.request
import zipfile
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from xml.etree import ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.environ.get("REPO_ROOT") or os.path.abspath(os.path.join(HERE, "..", ".."))
PORT = int(os.environ.get("PORT", "8788"))
MAX_BYTES = int(os.environ.get("MAX_BYTES", str(15 * 1024 * 1024)))
AUTO_PUSH = os.environ.get("AUTO_PUSH", "0") == "1"
NO_GIT = os.environ.get("NO_GIT", "0") == "1"
PIPELINE_HOOK = os.environ.get("PIPELINE_HOOK", "").strip()
PIPELINE_WEBHOOK = os.environ.get("PIPELINE_WEBHOOK", "").strip()
TZ = _dt.timezone(_dt.timedelta(hours=8))

_registry_guess = os.path.join(REPO_ROOT, "skills", "luoyu-reading", "references", "book-registry.json")
_auto_sandbox = not (os.path.isfile(_registry_guess) and
                     os.path.isdir(os.path.join(REPO_ROOT, "reading-notes", "epub")))
SANDBOX = (os.environ.get("MODE", "auto").lower() == "sandbox" or
           (os.environ.get("MODE", "auto").lower() != "repo" and _auto_sandbox))
HOST = os.environ.get("HOST") or ("0.0.0.0" if (SANDBOX or "PORT" in os.environ) else "127.0.0.1")

if SANDBOX:
    DATA_ROOT = os.environ.get("DATA_ROOT") or os.path.join(HERE, "data")
    STATIC_ROOT = DATA_ROOT
    UPLOAD_DIR = os.path.join(DATA_ROOT, "uploads")
    CATALOG = os.path.join(DATA_ROOT, "uploads.json")
    QUEUE = os.path.join(DATA_ROOT, "queue.json")
    EVENTS_DIR = os.path.join(DATA_ROOT, "events")
    REGISTRY = QUEUE
    COMM_ROOT = EVENTS_DIR
else:
    STATIC_ROOT = REPO_ROOT
    EPUB_DIR = os.path.join(REPO_ROOT, "reading-notes", "epub")
    UPLOAD_DIR = os.path.join(EPUB_DIR, "uploads")
    CATALOG = os.path.join(EPUB_DIR, "uploads.json")
    QUEUE = None
    EVENTS_DIR = None
    REGISTRY = _registry_guess
    COMM_ROOT = os.path.join(REPO_ROOT, "skills", "luoyu-reading", "references", "agent-communication")

WRITE_LOCK = threading.Lock()

try:
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    if EVENTS_DIR:
        os.makedirs(EVENTS_DIR, exist_ok=True)
except OSError:
    # 某些只读沙箱：退到临时目录，至少保证服务可用（重启后不持久）
    DATA_ROOT = os.path.join(tempfile.gettempdir(), "weread-epub-uploads")
    STATIC_ROOT = DATA_ROOT
    UPLOAD_DIR = os.path.join(DATA_ROOT, "uploads")
    CATALOG = os.path.join(DATA_ROOT, "uploads.json")
    QUEUE = os.path.join(DATA_ROOT, "queue.json")
    EVENTS_DIR = os.path.join(DATA_ROOT, "events")
    REGISTRY = QUEUE
    COMM_ROOT = EVENTS_DIR
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    os.makedirs(EVENTS_DIR, exist_ok=True)

if not os.path.exists(CATALOG):
    with open(CATALOG, "w", encoding="utf-8") as f:
        json.dump({"generated": _dt.date.today().isoformat(), "source": "upload",
                   "count": 0, "books": []}, f, ensure_ascii=False, indent=2)
if SANDBOX and not os.path.exists(QUEUE):
    with open(QUEUE, "w", encoding="utf-8") as f:
        json.dump({"source": "sandbox-upload", "revision": 0, "books": []},
                  f, ensure_ascii=False, indent=2)


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
    return os.path.relpath(path, STATIC_ROOT).replace(os.sep, "/")


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
def registry_entry(bid, title, author, file_rel, sha, byte_len, chapters, opf_note, stamp):
    """与 reading-state-protocol.md 一致的 queued 条目，本机与沙箱共用。"""
    source = ("用户于 %s 通过在线上传服务上传本地 EPUB，要求新增并生成笔记；"
              "排在已有持有任务之后。" % stamp)
    return {
        "book_id": bid,
        "title": title,
        "author": author or "未署名",
        "platform": "local_pdf",
        "platform_book_id": None,
        "priority": "user_requested",
        "status": "queued",
        "owner_agent_id": None,
        "claim": {"state": "unclaimed", "source": source, "claimed_at": None},
        "last_confirmed_progress": None,
        "resume_point": {
            "status": "needs-confirmation", "chapter": None, "page": None,
            "position": "尚未开始；无已确认用户亲读位置。",
            "source": "用户上传的本地 EPUB；尚未开始阅读。", "confirmed_at": None
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
    }


def event_text(bid, title, author, file_rel, sha, byte_len, chapters, old_rev, new_rev, queued):
    by = "在线沙箱上传服务" if SANDBOX else "本机上传服务"
    lines = [
        "",
        "### [%s] 用户（%s代写） / %s" % (now().strftime("%Y-%m-%d %H:%M"), by, bid),
        "- 类型：用户上传本地 EPUB → 入队补笔记；**不是阅读场次，不代表亲读或完读**。",
        "- 书名：《%s》；作者：%s；稳定 ID `%s`。" % (title, author or "未署名", bid),
        "- 源文件：`%s`（%d 字节，sha256 %s，%d 个 XHTML 分片）。" %
        (file_rel, byte_len, sha, chapters),
        "- 登记：%s revision %d → %d，status `queued`、owner 空、claim `unclaimed`、"
        "priority `user_requested`、`source_format: epub`；排在已有持有任务之后。" %
        ("沙箱队列" if SANDBOX else "registry", old_rev, new_rev),
        "- 要求：按 `reading-state-protocol.md` 由管理员分发，阅读 Agent 认领后跑书并补笔记；"
        "不自行抢占活动锁，不改 roster / resume_point / completion / 完读计数。",
        "- 重复上传：%s。" % ("本次为同名覆盖，未重复入队" if not queued else "新书，已入队"),
        "- 边界：文件进入公开仓库，`noindex` 不等于私有；Git 记录不等于消息已送达。",
        ""
    ]
    return "\n".join(lines)


def enqueue(bid, title, author, file_rel, sha, byte_len, chapters, opf_note):
    """返回 dict(queued, revision, event, event_rel)。"""
    stamp = now().strftime("%Y-%m-%dT%H:%M:%S+08:00")
    reg = read_json(REGISTRY, None)
    if SANDBOX:
        if not isinstance(reg, dict):
            reg = {"source": "sandbox-upload", "revision": 0, "books": []}
        if not isinstance(reg.get("books"), list):
            reg["books"] = []
    elif not isinstance(reg, dict) or not isinstance(reg.get("books"), list):
        raise RuntimeError("book-registry.json 不可读或结构异常，已跳过入队")

    exists = any(b.get("book_id") == bid for b in reg["books"])
    old_rev = int(reg.get("revision", 0))
    queued = False
    if not exists:
        reg["books"].append(registry_entry(bid, title, author, file_rel, sha,
                                           byte_len, chapters, opf_note, stamp))
        reg["revision"] = old_rev + 1
        reg["updated_at"] = stamp
        atomic_json(REGISTRY, reg)
        queued = True

    new_rev = int(reg.get("revision", old_rev))
    text = event_text(bid, title, author, file_rel, sha, byte_len,
                      chapters, old_rev, new_rev, queued)
    if SANDBOX:
        comm_file = os.path.join(EVENTS_DIR, "%s.md" % now().strftime("%Y-%m-%d"))
    else:
        d = now().strftime("%Y/%m").split("/")
        comm_dir = os.path.join(COMM_ROOT, d[0], d[1])
        os.makedirs(comm_dir, exist_ok=True)
        comm_file = os.path.join(comm_dir, "%s.md" % now().strftime("%Y-%m-%d"))
    with open(comm_file, "a", encoding="utf-8") as f:
        f.write(text)
    return {"queued": queued, "revision": new_rev, "event": text,
            "event_rel": rel(comm_file)}


# ---------------------------------------------------------------- git / 钩子
def run_git(args):
    if NO_GIT or SANDBOX:
        return True, "沙箱/NO_GIT 已跳过"
    try:
        p = subprocess.run(["git", "-C", REPO_ROOT] + args, capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=90)
        if p.returncode != 0:
            return False, (p.stderr or p.stdout or "").strip()[:300]
        return True, (p.stdout or "").strip()[:200]
    except Exception as exc:
        return False, str(exc)[:300]


def commit_all(bid, title, paths):
    if SANDBOX:
        return ["沙箱模式：文件保存在应用数据目录，等待 sync_to_git.py 同步回仓库"]
    notes = []
    ok, msg = run_git(["add", "--"] + paths)
    if not ok:
        return ["git add 失败：%s" % msg]
    ok, msg = run_git(["commit", "-m", "upload: %s（%s）本地 EPUB 入队补笔记" % (title[:40], bid)])
    notes.append("已本地 commit" if ok else "本地 commit 未成功：%s" % msg)
    if AUTO_PUSH:
        ok, msg = run_git(["pull", "--rebase", "origin", "main"])
        if not ok:
            notes.append("pull --rebase 失败，未 push：%s" % msg)
            return notes
        ok, msg = run_git(["push", "origin", "HEAD:main"])
        notes.append("已 push 到 main" if ok else "push 失败：%s" % msg)
    return notes


def fire_hook(bid, title, file_rel, result):
    if PIPELINE_HOOK:
        cmd = (PIPELINE_HOOK.replace("{book_id}", bid)
               .replace("{title}", title)
               .replace("{file}", file_rel))
        try:
            subprocess.Popen(cmd, shell=True, cwd=(HERE if SANDBOX else REPO_ROOT),
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as exc:
            sys.stderr.write("PIPELINE_HOOK 启动失败：%s\n" % (exc,))
    if PIPELINE_WEBHOOK:
        payload = {
            "type": "epub-upload-queued", "book_id": bid, "title": title,
            "file": file_rel, "file_url": result["file_url"],
            "queue_revision": result["registry_revision"],
            "queued": result["queued"], "mode": "sandbox" if SANDBOX else "repo",
            "note": "仅入队，等待读书 Agent 认领；不代表笔记已生成"
        }
        def send():
            try:
                req = urllib.request.Request(
                    PIPELINE_WEBHOOK, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                    headers={"Content-Type": "application/json"}, method="POST")
                urllib.request.urlopen(req, timeout=6).read()
            except Exception as exc:
                sys.stderr.write("PIPELINE_WEBHOOK 回调失败：%s\n" % (exc,))
        threading.Thread(target=send, daemon=True).start()


# ---------------------------------------------------------------- 业务逻辑
def handle_upload(raw, raw_name, public_base=""):
    if not raw:
        raise InvalidEpub("请求体为空")
    if len(raw) > MAX_BYTES:
        raise InvalidEpub("文件 %.1f MB 超过 %.1f MB 上限" %
                          (len(raw) / 1048576.0, MAX_BYTES / 1048576.0))
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
    file_rel = ("uploads/%s.epub" % bid) if SANDBOX else \
               ("reading-notes/epub/uploads/%s.epub" % bid)
    dest = os.path.join(UPLOAD_DIR, "%s.epub" % bid)

    with WRITE_LOCK:
        tmp = dest + ".part"
        with open(tmp, "wb") as f:
            f.write(raw)
        os.replace(tmp, dest)

        catalog = read_json(CATALOG, {"books": []})
        books = [b for b in catalog.get("books", []) if b.get("id") != bid]
        books.append({
            "id": bid, "title": title, "author": author,
            "pages": 0, "chars": 0, "chapters": chapters,
            "bytes": len(raw), "file": "uploads/%s.epub" % bid,
            "source": "upload", "source_name": name, "sha256": sha,
            "uploaded_at": now().strftime("%Y-%m-%dT%H:%M:%S+08:00"),
            "note_status": "待补笔记"
        })
        books.sort(key=lambda b: b.get("title", ""))
        atomic_json(CATALOG, {"generated": now().date().isoformat(),
                              "source": "upload", "count": len(books), "books": books})

        opf_note = "EPUB 元数据：标题《%s》，作者 %s，%d 个 XHTML 分片；上传服务读取。" % (
            title, author, chapters)
        q = enqueue(bid, title, author, file_rel, sha, len(raw), chapters, opf_note)

        changed = [rel(CATALOG), file_rel]
        if SANDBOX:
            changed += [rel(REGISTRY), q["event_rel"], "events/" + os.path.basename(q["event_rel"])]
        elif q["queued"]:
            changed += [os.path.relpath(REGISTRY, REPO_ROOT).replace(os.sep, "/"),
                        os.path.relpath(os.path.join(COMM_ROOT, q["event_rel"].split("/")[-1]), REPO_ROOT)
                        if False else q["event_rel"]]
        git_notes = commit_all(bid, title, changed)

    file_url = (public_base.rstrip("/") + "/uploads/" + bid + ".epub") if public_base \
        else "uploads/%s.epub" % bid
    result = {
        "ok": True, "mode": "sandbox" if SANDBOX else "repo",
        "book_id": bid, "title": title, "author": author,
        "file": "uploads/%s.epub" % bid, "file_url": file_url,
        "bytes": len(raw), "chapters": chapters,
        "queued": q["queued"], "duplicate": not q["queued"],
        "registry_revision": q["revision"], "event": q["event_rel"],
        "git": git_notes,
        "pipeline": ("webhook" if PIPELINE_WEBHOOK else
                     "local-hook" if PIPELINE_HOOK else "poll-only"),
        "note": "已入队 queued，等待读书 Agent 认领补笔记；不代表笔记已生成"
    }
    fire_hook(bid, title, file_rel, result)
    return result


# ---------------------------------------------------------------- HTTP
class Handler(SimpleHTTPRequestHandler):
    extensions_map = dict(SimpleHTTPRequestHandler.extensions_map)
    extensions_map.update({".epub": "application/epub+zip", ".json": "application/json",
                           ".md": "text/markdown; charset=utf-8"})

    def translate_path(self, path):
        u = urllib.parse.urlparse(path).path
        if u.startswith("/uploads/"):
            return os.path.join(UPLOAD_DIR, posixpath.basename(urllib.parse.unquote(u)))
        return super().translate_path(path)

    def public_base(self):
        fixed = os.environ.get("PUBLIC_BASE", "").strip()
        if fixed:
            return fixed.rstrip("/")
        host = self.headers.get("Host") or "localhost"
        proto = self.headers.get("X-Forwarded-Proto") or \
                ("http" if host.startswith(("127.", "localhost")) else "https")
        return "%s://%s" % (proto, host)

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

    def _catalog_with_urls(self):
        d = read_json(CATALOG, {"books": []})
        base = self.public_base()
        out = dict(d)
        out["books"] = []
        for b in d.get("books", []):
            c = dict(b)
            c["file"] = base + "/uploads/" + str(b.get("id", "")) + ".epub"
            c["file_url"] = c["file"]
            out["books"].append(c)
        out["service_base"] = base
        out["mode"] = "sandbox" if SANDBOX else "repo"
        return out

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        path = u.path
        if "/.git/" in path or path.startswith("/.workbuddy/") or "/.env" in path:
            self.send_error(403, "forbidden")
            return
        if path == "/api/health":
            q = read_json(QUEUE if SANDBOX else REGISTRY, {})
            self._json(200, {
                "ok": True,
                "mode": "sandbox" if SANDBOX else "repo",
                "service_base": self.public_base(),
                "repo_root": (None if SANDBOX else REPO_ROOT),
                "upload_dir": rel(UPLOAD_DIR),
                "max_bytes": MAX_BYTES,
                "auto_push": AUTO_PUSH,
                "pipeline_webhook": bool(PIPELINE_WEBHOOK),
                "pipeline_hook": bool(PIPELINE_HOOK),
                "registry_revision": q.get("revision") if isinstance(q, dict) else None,
                "time": now().strftime("%Y-%m-%d %H:%M:%S+08:00")
            })
            return
        if path == "/api/uploads":
            self._json(200, self._catalog_with_urls())
            return
        if path == "/api/queue":
            self._json(200, read_json(QUEUE if SANDBOX else REGISTRY,
                                      {"revision": 0, "books": []}))
            return
        if path == "/api/events":
            date = (urllib.parse.parse_qs(u.query).get("date") or
                    [now().strftime("%Y-%m-%d")])[0]
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", date or ""):
                self._json(400, {"ok": False, "error": "date 格式应为 YYYY-MM-DD"})
                return
            if SANDBOX:
                p = os.path.join(EVENTS_DIR, date + ".md")
            else:
                d = date.split("-")
                p = os.path.join(COMM_ROOT, d[0], d[1], date + ".md")
            try:
                with open(p, "r", encoding="utf-8") as f:
                    self._json(200, {"date": date, "text": f.read()})
            except OSError:
                self._json(200, {"date": date, "text": ""})
            return
        if path == "/api/sync":
            cat = self._catalog_with_urls()
            events = {}
            if SANDBOX and os.path.isdir(EVENTS_DIR):
                for fn in sorted(os.listdir(EVENTS_DIR)):
                    if re.match(r"^\d{4}-\d{2}-\d{2}\.md$", fn):
                        with open(os.path.join(EVENTS_DIR, fn), "r", encoding="utf-8") as f:
                            events[fn[:-3]] = f.read()
            self._json(200, {
                "ok": True, "mode": "sandbox" if SANDBOX else "repo",
                "generated": now().strftime("%Y-%m-%dT%H:%M:%S+08:00"),
                "service_base": self.public_base(),
                "uploads": cat,
                "queue": read_json(QUEUE if SANDBOX else REGISTRY,
                                   {"revision": 0, "books": []}),
                "events": events,
                "files": [{"id": b["id"], "url": b["file"], "sha256": b.get("sha256"),
                           "bytes": b.get("bytes")} for b in cat["books"]]
            })
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
            self._json(413, {"ok": False, "error": "超过 %.1f MB 上限" %
                             (MAX_BYTES / 1048576.0)})
            return
        q = urllib.parse.parse_qs(u.query)
        name = (q.get("name") or [""])[0] or self.headers.get("X-File-Name", "")
        try:
            raw = self.rfile.read(length)
            result = handle_upload(raw, name, self.public_base())
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
    handler = functools.partial(Handler, directory=STATIC_ROOT)
    srv = Server((HOST, PORT), handler)
    print("EPUB 上传服务已启动（%s 模式）" % ("在线沙箱" if SANDBOX else "本机仓库"))
    print("  监听     : %s:%d" % (HOST, PORT))
    print("  数据根   : %s" % STATIC_ROOT)
    print("  上传目录 : %s" % rel(UPLOAD_DIR))
    print("  上限     : %.1f MB / 本" % (MAX_BYTES / 1048576.0))
    print("  异步流程 : %s" % (PIPELINE_WEBHOOK or PIPELINE_HOOK or "未配置，仅入队待认领"))
    if SANDBOX:
        print("  API      : /api/health /api/uploads /api/queue /api/events /api/sync /api/upload")
        print("  说明     : 沙箱文件需 sync_to_git.py 同步回仓库才是永久保存")
    else:
        print("  自动推送 : %s" % ("开启（AUTO_PUSH=1）" if AUTO_PUSH else "关闭，只本地 commit"))
        print("  书架入口 : http://%s:%d/reading-notes/epub/index.html" % (HOST, PORT))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()
