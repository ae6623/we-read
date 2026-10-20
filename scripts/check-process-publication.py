#!/usr/bin/env python3
"""只读核验获授权的阅读过程归档；不扫描仓库外文件。"""
import copy
import hashlib
import importlib.util
import json
import re
import subprocess
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent.parent
PROCESS = ROOT / 'reading-notes/process'

class Page(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.links, self.ids, self.headings = [], set(), 0
        self.text = []
        self.feed(text)
    def handle_data(self, data):
        self.text.append(data)
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if 'href' in a:
            self.links.append(a['href'])
        if 'id' in a:
            self.ids.add(a['id'])
        self.headings += tag == 'h1'

def assert_safe(text):
    # 针对这批来源中已审查的凭据操作／账户状态，不将字数本身当作风险。
    pattern = r'登录态有效|重导登录态|导入登录态|导登录态|导出登录态|storage_state|\d+\s*cookie|shared\.token|一次性注入令牌|账号 [AB]|本账号后续范围|/api/check|C:/Users/'
    assert not re.search(pattern, text, re.I), '公开副本仍含已排除的账户／认证操作描述'

def main():
    manifest = json.loads((PROCESS / 'publication-manifest.json').read_text())
    checked = 0
    for f in manifest['files']:
        raw = subprocess.check_output(['git', 'show', f"{f['source_commit']}:{f['source_path']}"], cwd=ROOT)
        assert hashlib.sha256(raw).hexdigest() == f['source_sha256'], f['source_path']
        assert f['source_commit'] == manifest['source_commit']
        assert (PROCESS / f['page']).exists()
        rendered = ' '.join(''.join(Page((PROCESS / f['page']).read_text()).text).split())
        assert_safe(rendered)
        lines = raw.decode().splitlines()
        for redaction in f['redactions']:
            for line in lines[redaction['start_line'] - 1:redaction['end_line']]:
                plain = re.sub(r'[`*]', '', line).removeprefix('- ').strip()
                plain = ' '.join(plain.split())
                if len(plain) >= 32:
                    assert plain not in rendered, (f['page'], redaction, '删节行仍在实际正文')
        checked += 1
    try:
        assert_safe('负例：登录态有效')
    except AssertionError:
        pass
    else:
        raise AssertionError('残留扫描负例没有失败')
    for p in PROCESS.glob('*.html'):
        parsed = Page(p.read_text())
        assert parsed.headings == 1, (p, 'h1')
        assert not re.search(r'<[^>]+data-visibility="private"', p.read_text())
        for link in parsed.links:
            u = urlsplit(link)
            if u.scheme or u.netloc:
                continue
            dest = (p.parent / unquote(u.path)).resolve() if u.path else p
            assert dest.is_relative_to(ROOT), (p, link, '路径越界')
            assert dest.exists(), (p, link, '目标不存在')
            if u.fragment and dest.suffix == '.html':
                assert unquote(u.fragment) in Page(dest.read_text()).ids, (p, link, '锚点不存在')
    registry = json.loads((ROOT / 'skills/luoyu-reading/references/book-registry.json').read_text())
    template = json.loads((ROOT / 'skills/luoyu-reading/templates/session-close.json').read_text())
    assert registry['synthesis']['visibility'] == template['visibility'] == 'public'
    assert template['publication_review']['status'] == 'pending-safety-review'
    spec = importlib.util.spec_from_file_location('reading_state', ROOT / 'skills/luoyu-reading/scripts/check-reading-state.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    roster = json.loads((ROOT / 'skills/luoyu-reading/references/agent-roster.json').read_text())
    assert not module.validate(registry, roster)
    # 合成三本夹具：只在内存验证未来批次 public；不改真实完读事实。
    fixture = copy.deepcopy(registry)
    books = fixture['books'][:3]
    for n, b in enumerate(books, 1):
        b['completion'] = {'event_id': f'test-{n}', 'sequence': n}
        b.update(status='completed', owner_agent_id=None, claim={'state': 'released'})
    fixture['books'] = books
    fixture['active_session'] = None
    fixture['synthesis'].update(unique_completed_count=3, batches=[{
        'batch_id': 'batch-001', 'book_ids': [b['book_id'] for b in books],
        'status': 'pending', 'owner_agent_id': roster['agents'][0]['id'], 'visibility': 'public'}])
    assert not module.validate(fixture, roster)
    fixture['synthesis']['batches'][0]['visibility'] = 'private'
    assert any('visibility' in err for err in module.validate(fixture, roster))
    print(f'PASS: {checked} 份历史来源SHA256、实际删节与残留负例、全部过程页链接/锚点、默认安全审查及未来公开批次正反例')

if __name__ == '__main__':
    main()
