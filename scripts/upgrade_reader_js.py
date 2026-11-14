#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全站 combined.html 的 reader-*.js 版本批量切换（幂等 / 断点恢复）。

背景
----
站点仓是稀疏检出（本地工作区只有约 48 本），但 git tree 里有 543 本壳页。
本脚本直接读写 git 对象库，不依赖工作区检出，也不需要拉几百 MB 内容：

    git ls-tree -r -z HEAD     列出全部 combined.html 的 blob sha
    git cat-file --batch       一次进程读回全部内容
    Python 直写 loose object   生成新 blob（sha 与 git hash-object 完全一致）
    临时 index + commit-tree   构造单个提交

断点恢复
--------
checkpoint 落在 ``.git/reader_js_upgrade.json``，每 ``--flush-every`` 本落盘一次，
记录每个 path 的 old/new blob sha、以及 commit / push 状态。任何一步掉线后重跑：

  * 已处理的 path 直接跳过（幂等，不会重复造 blob）
  * 已生成但未推送的 commit 直接复用（不会重复造 commit）
  * push 失败只补推，不重做前面的工作

用法
----
    # 只统计，不改任何东西
    python3 scripts/upgrade_reader_js.py --to reader-20261115.js --dry-run

    # 小批验证（只处理前 5 本，不构造提交）
    python3 scripts/upgrade_reader_js.py --to reader-20261115.js --limit 5

    # 全量切换 + 造提交 + 推送（一条命令走完）
    python3 scripts/upgrade_reader_js.py --to reader-20261115.js --push

    # 掉线后从断点续跑
    python3 scripts/upgrade_reader_js.py --resume --push

    # 验收：全站壳页引用是否与 assets/js 下最新版本一致
    python3 scripts/upgrade_reader_js.py --verify

约定
----
只替换壳页里 ``<script src=".../assets/js/reader-<ver>.js">`` 这一处引用，
不改其它内容；已是目标版本的书直接跳过。目标版本必须已存在于 assets/js/。
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import zlib
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GITDIR = subprocess.check_output(['git', 'rev-parse', '--git-dir'], cwd=ROOT).decode().strip()
if not os.path.isabs(GITDIR):
    GITDIR = str(ROOT / GITDIR)
CKPT = os.path.join(GITDIR, 'reader_js_upgrade.json')
BOOKS_PREFIX = 'reading-notes/books'
JS_RE = re.compile(rb'(assets/js/)reader-\d+\.js')


def git(*args, **kw):
    """跑 git 命令，返回 stdout bytes。"""
    inp = kw.pop('input', None)
    env = kw.pop('env', None)
    return subprocess.check_output(['git'] + list(args), input=inp, env=env,
                                   cwd=ROOT, **kw)


def git_text(*args, **kw):
    return git(*args, **kw).decode('utf-8', 'replace').strip()


def list_shells():
    """从 HEAD tree 列出所有 combined.html 的 (blobsha, path)。不受稀疏检出影响。"""
    out = git('ls-tree', '-r', '-z', 'HEAD', '--', BOOKS_PREFIX)
    items = []
    for rec in out.split(b'\0'):
        if not rec:
            continue
        meta, path = rec.split(b'\t', 1)
        _mode, _typ, sha = meta.split()
        p = path.decode('utf-8')
        if p.endswith('/combined.html'):
            items.append((sha.decode(), p))
    return items


def read_blobs(items):
    """一次 cat-file --batch 读回全部 blob 内容 -> {path: bytes}。"""
    proc = subprocess.Popen(['git', 'cat-file', '--batch'],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, cwd=ROOT)
    payload = b''.join(s.encode() + b'\n' for s, _ in items)
    stdout, _ = proc.communicate(payload)
    if proc.returncode != 0:
        raise RuntimeError('git cat-file --batch 失败 rc=%s' % proc.returncode)
    blobs = {}
    pos = 0
    for sha, path in items:
        nl = stdout.index(b'\n', pos)
        hdr = stdout[pos:nl].split()
        pos = nl + 1
        size = int(hdr[2])
        blobs[path] = stdout[pos:pos + size]
        pos += size + 1
    return blobs


def write_blob(data):
    """Python 直写 loose object，返回 sha。与 git hash-object 完全等价。"""
    raw = b'blob ' + str(len(data)).encode() + b'\0' + data
    sha = hashlib.sha1(raw).hexdigest()
    d = os.path.join(GITDIR, 'objects', sha[:2])
    os.makedirs(d, exist_ok=True)
    f = os.path.join(d, sha[2:])
    if not os.path.exists(f):
        tmp = f + '.tmp%d' % os.getpid()
        with open(tmp, 'wb') as fh:
            fh.write(zlib.compress(raw, 1))
        os.replace(tmp, f)
    return sha


def blob_exists(sha):
    if not sha:
        return False
    try:
        git('cat-file', '-e', sha)
        return True
    except subprocess.CalledProcessError:
        return False


def load_ckpt():
    if os.path.exists(CKPT):
        try:
            return json.load(open(CKPT, encoding='utf-8'))
        except Exception:
            pass
    return {'to': None, 'done': {}, 'commit': None, 'pushed': False,
            'started': None, 'updated': None}


def save_ckpt(ck):
    ck['updated'] = datetime.now().isoformat(timespec='seconds')
    tmp = CKPT + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(ck, f, ensure_ascii=False, indent=1)
    os.replace(tmp, CKPT)


def find_target_in_tree():
    """期望版本 = assets/data/reader-js.json 的 current（单一真相源）。"""
    cfg = ROOT / 'assets' / 'data' / 'reader-js.json'
    if cfg.exists():
        try:
            v = json.loads(cfg.read_text(encoding='utf-8')).get('current')
            if v and re.match(r'^reader-\d+\.js$', v):
                return v
        except Exception:
            pass
    # 兜底：真相源缺失时取 assets/js 下最新版本
    out = git_text('ls-tree', '-r', '--name-only', 'HEAD', '--', 'assets/js')
    names = [os.path.basename(x) for x in out.splitlines()
             if re.match(r'^reader-\d+\.js$', os.path.basename(x))]
    return max(names) if names else None


def verify():
    """验收：全站 combined.html 的 reader 引用是否统一指向最新版本。"""
    target = find_target_in_tree()
    if not target:
        print('✗ assets/js 下找不到 reader-<date>.js')
        return 1
    items = list_shells()
    blobs = read_blobs(items)
    bad = []
    dist = {}
    for sha, path in items:
        m = JS_RE.search(blobs[path])
        ver = (m.group(0).split(b'/')[-1].decode() if m else '<无引用>')
        dist[ver] = dist.get(ver, 0) + 1
        if ver != target:
            bad.append((path, ver))
    print('期望版本: %s' % target)
    print('全站壳页: %d 本' % len(items))
    for k, v in sorted(dist.items(), key=lambda x: -x[1]):
        print('  %-28s %d 本' % (k, v))
    if bad:
        print('✗ 不一致 %d 本，示例:' % len(bad))
        for p, v in bad[:12]:
            print('    %s -> %s' % (p, v))
        return 1
    print('✓ 全部一致')
    return 0


def write_obj(typ, data):
    """Python 直写任意 git loose object，返回 sha。"""
    raw = typ.encode() + b' ' + str(len(data)).encode() + b'\0' + data
    sha = hashlib.sha1(raw).hexdigest()
    d = os.path.join(GITDIR, 'objects', sha[:2])
    os.makedirs(d, exist_ok=True)
    f = os.path.join(d, sha[2:])
    if not os.path.exists(f):
        tmp = f + '.tmp%d' % os.getpid()
        with open(tmp, 'wb') as fh:
            fh.write(zlib.compress(raw, 1))
        os.replace(tmp, f)
    return sha


def build_tree(changed):
    """在对象层重建 tree，返回新的根 tree sha。

    为什么不用 ``git write-tree``：本机 .git/objects 有 218 个 pack，
    临时 index 一旦改动就会 cache-tree 全失效，write-tree 要为 6361 个
    条目重建上千个 tree 并逐个查重，实测 >30s 超时。这里改用
    ``git ls-tree -r -t -z`` 一次拿回全部条目（含 tree 节点，且保持
    tree 内原有顺序），只替换目标 blob 的 sha，自底向上直写 tree 对象，
    全程零 git 子进程瓶颈，且顺序天然正确（无需自己实现 git 排序规则）。
    """
    out = git('ls-tree', '-r', '-t', '-z', 'HEAD')
    # children[dir] = [(mode_bytes, name_bytes, sha_bytes20, is_tree)]，顺序 = tree 内顺序
    children = {}
    for rec in out.split(b'\0'):
        if not rec:
            continue
        meta, path = rec.split(b'\t', 1)
        mode, typ, sha = meta.split()
        parent = path.rsplit(b'/', 1)[0] if b'/' in path else b''
        name = path.rsplit(b'/', 1)[-1]
        children.setdefault(parent, []).append(
            [mode.lstrip(b'0') or b'0', name, bytes.fromhex(sha.decode()),
             typ == b'tree', path.decode()])
        if typ == b'tree':
            children.setdefault(path, [])
    # 需要重算的目录：目标文件所在目录及其所有祖先
    dirty = set()
    for p in changed:
        parts = p.split('/')
        for i in range(len(parts)):
            dirty.add('/'.join(parts[:i]).encode())
    # 自底向上（深目录优先）。根目录 b'' 深度记为 -1，确保最后计算；
    # 否则它与 'reading-notes'（同为 0 个斜杠）同级，会先算而拿到旧子树 sha。
    newtree = {}
    for d in sorted(children, key=lambda x: x.count(b'/') if x else -1, reverse=True):
        if d not in dirty and d != b'':
            continue
        buf = bytearray()
        for e in children[d]:
            mode, name, sha20, is_tree, full = e
            if is_tree and full.encode() in newtree:
                sha20 = bytes.fromhex(newtree[full.encode()])
            elif full in changed:
                sha20 = bytes.fromhex(changed[full])
            buf += mode + b' ' + name + b'\0' + sha20
        newtree[d] = write_obj('tree', bytes(buf))
    return newtree[b'']


def build_commit(done, target, msg):
    """构造单个提交；同步主 index 与已检出的工作区文件。"""
    changed = {p: d['new'] for p, d in done.items() if d['changed']}
    if not changed:
        print('无改动需要提交')
        return None
    tree = build_tree(changed)
    # 强校验：新 tree 相对 HEAD 的差异必须恰好等于 changed 集合
    diffout = git('diff-tree', '-r', '--no-commit-id', '--name-only', '-z',
                  'HEAD^{tree}', tree)
    got = set(x.decode() for x in diffout.split(b'\0') if x)
    if got != set(changed):
        raise RuntimeError('tree 差异不符: 期望 %d 实际 %d，差集样例 %s' %
                           (len(changed), len(got), list(got ^ set(changed))[:5]))
    print('tree 校验通过：仅 %d 个 combined.html 变化' % len(got))
    head = git_text('rev-parse', 'HEAD')
    commit = git_text('commit-tree', tree, '-p', head, '-m', msg)
    git('update-ref', 'refs/heads/main', commit)
    # 主 index 跟上新 HEAD（reset --mixed 会重新应用 sparse-checkout 规则）
    git('reset', '--mixed', '-q', 'HEAD')
    return commit


def sync_worktree(done):
    """对本地已检出的文件，从新 blob 重读内容写回，保证 git status 干净。

    checkpoint 不存原始字节（太大且不可序列化），一律按 new sha 取回。
    """
    n = 0
    for p, d in done.items():
        if not d['changed']:
            continue
        f = ROOT / p
        if f.exists():
            f.write_bytes(git('cat-file', 'blob', d['new']))
            n += 1
    return n


def push_with_retry(tries=3):
    for i in range(1, tries + 1):
        try:
            r = subprocess.run(['git', 'push', 'origin', 'main'], cwd=ROOT,
                               capture_output=True, text=True, timeout=300)
            if r.returncode == 0:
                print('  push 成功')
                return True
            print('  push 第 %d 次失败: %s' % (i, (r.stderr or '').strip()[-300:]))
            if 'non-fast-forward' in (r.stderr or '') or 'fetch first' in (r.stderr or ''):
                subprocess.run(['git', 'pull', '--rebase', 'origin', 'main'], cwd=ROOT,
                               capture_output=True, text=True, timeout=300)
        except subprocess.TimeoutExpired:
            print('  push 第 %d 次超时' % i)
        time.sleep(3)
    return False


def main():
    ap = argparse.ArgumentParser(description='全站壳页 reader-*.js 版本批量切换')
    ap.add_argument('--to', help='目标 JS 文件名，如 reader-20261115.js')
    ap.add_argument('--dry-run', action='store_true', help='只统计，不写对象、不提交')
    ap.add_argument('--limit', type=int, default=0, help='只处理前 N 本（小批验证）')
    ap.add_argument('--resume', action='store_true', help='从 checkpoint 续跑')
    ap.add_argument('--verify', action='store_true', help='只做一致性验收')
    ap.add_argument('--push', action='store_true', help='完成后推送到 origin main')
    ap.add_argument('--no-commit', action='store_true', help='只处理不构造提交')
    ap.add_argument('--flush-every', type=int, default=50, help='checkpoint 落盘间隔')
    ap.add_argument('--reset', action='store_true', help='清空 checkpoint 重新开始')
    args = ap.parse_args()

    if args.verify:
        sys.exit(verify())

    ck = load_ckpt()
    if args.reset:
        ck = {'to': None, 'done': {}, 'commit': None, 'pushed': False,
              'started': None, 'updated': None}
        if os.path.exists(CKPT):
            os.unlink(CKPT)
        print('checkpoint 已清空')

    target = args.to or ck.get('to')
    if not target:
        ap.error('需要 --to 指定目标版本（或用 --resume 读 checkpoint）')
    if not re.match(r'^reader-\d+\.js$', target):
        ap.error('目标版本格式应为 reader-<日期>.js')

    # 目标 JS 必须已在仓库里
    try:
        git('cat-file', '-e', 'HEAD:assets/js/' + target)
    except subprocess.CalledProcessError:
        ap.error('assets/js/%s 不在 HEAD 中，请先提交新版 JS' % target)

    if ck.get('to') and ck['to'] != target:
        print('! checkpoint 目标 %s 与当前 %s 不同，重置进度' % (ck['to'], target))
        ck['done'] = {}
        ck['commit'] = None
        ck['pushed'] = False
    ck['to'] = target
    if not ck.get('started'):
        ck['started'] = datetime.now().isoformat(timespec='seconds')

    # 已推送完成且无待办 → 直接收尾
    if ck.get('pushed') and not args.reset:
        print('✓ 上次已推送完成；如需重新校验请跑 --verify')
        if args.push:
            print('  push 已是最新，跳过')
        return

    items = list_shells()
    blobs = read_blobs(items)
    todo = [(s, p) for s, p in items if p not in ck['done']]
    if args.limit:
        todo = todo[:args.limit]

    # 统计（dry-run 时全量看分布）
    scan = todo if not args.dry_run else items
    stat = {'changed': 0, 'already': 0, 'noref': 0}
    for sha, p in scan:
        m = JS_RE.search(blobs[p])
        if not m:
            stat['noref'] += 1
        elif m.group(0).split(b'/')[-1].decode() == target:
            stat['already'] += 1
        else:
            stat['changed'] += 1
    print('目标版本 : %s' % target)
    print('全站壳页 : %d 本' % len(items))
    print('已完成(断点): %d 本' % len(ck['done']))
    print('本轮待办 : %d 本  (需切换 %d / 已是目标 %d / 无引用 %d)' %
          (len(todo), stat['changed'], stat['already'], stat['noref']))
    if args.dry_run:
        print('[dry-run] 未写任何对象或提交')
        return

    t0 = time.time()
    processed = 0
    for sha, p in todo:
        data = blobs[p]
        m = JS_RE.search(data)
        if not m:
            ck['done'][p] = {'old': sha, 'new': sha, 'changed': False}
        else:
            cur = m.group(0).split(b'/')[-1].decode()
            if cur == target:
                ck['done'][p] = {'old': sha, 'new': sha, 'changed': False}
            else:
                newdata = JS_RE.sub(lambda mm: mm.group(1) + target.encode(), data, count=1)
                newsha = write_blob(newdata)
                ck['done'][p] = {'old': sha, 'new': newsha, 'changed': True}
        processed += 1
        if processed % args.flush_every == 0:
            save_ckpt(ck)
            print('  进度 %d/%d (%.1fs)' % (processed, len(todo), time.time() - t0))
    save_ckpt(ck)
    print('处理完成 %d 本，耗时 %.2fs' % (processed, time.time() - t0))

    if args.limit or args.no_commit:
        print('[小批 / no-commit] 未构造提交；checkpoint 已保存')
        return

    # 全量完成才造提交
    if len(ck['done']) < len(items):
        print('! 仍有 %d 本未处理，本次不构造提交（可重跑续做）' % (len(items) - len(ck['done'])))
        return

    if not ck.get('commit') or not blob_exists(ck['commit']):
        msg = ('chore(site): 全站壳页切换 %s（章节知识导图）' % target)
        commit = build_commit(ck['done'], target, msg)
        ck['commit'] = commit
        save_ckpt(ck)
        if commit:
            print('已生成提交 %s' % commit[:10])
        else:
            print('无需提交（全部已是目标版本）')
    else:
        print('复用上次提交 %s' % ck['commit'][:10])

    synced = sync_worktree(ck['done'])
    print('已同步工作区文件 %d 个' % synced)
    print('工作区状态: %s' % (git_text('status', '--porcelain')[:200] or '干净'))

    if args.push and not ck.get('pushed'):
        if push_with_retry():
            ck['pushed'] = True
            save_ckpt(ck)
        else:
            print('✗ push 失败，重跑 --resume --push 即可续')
            sys.exit(1)
    elif not args.push:
        print('未推送；确认后执行 git push origin main 或重跑 --push')


if __name__ == '__main__':
    main()
