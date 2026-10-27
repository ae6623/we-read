#!/usr/bin/env python3
"""Guard current team labels and file-backed public note links."""
from pathlib import Path
from html.parser import HTMLParser
import importlib.util
import json
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('dashboard', ROOT / 'scripts/build-agent-dashboard.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
state = json.loads((ROOT / 'agent-room/state.json').read_text())
expected = {
    'zhu-xiao-fang-zi-de-nv-ren': '../notes/2026/2026-10-17-zhu-xiao-fang-zi-de-nv-ren.html',
    'king-return-dalrymple': '../reading-notes/books/king-return-dalrymple/notes/2026-10-20.html',
    'camino-qingyouji': '../reading-notes/books/camino-qingyouji/notes/2026-10-20.html',
}
books = {b['id']: b for b in state['books']}
for book_id, baseline in expected.items():
    url = books[book_id]['noteUrl']
    assert url and (ROOT / 'agent-room' / url).is_file(), (book_id, url)
    # May advance to a later existing daily note, but never regress below this fix's baseline.
    assert Path(url).name[:10] >= Path(baseline).name[:10]
for b in state['books']:
    if b['noteUrl']:
        assert b['noteUrl'].startswith('../') and (ROOT / 'agent-room' / b['noteUrl']).resolve().is_relative_to(ROOT)
        assert (ROOT / 'agent-room' / b['noteUrl']).is_file()
with tempfile.TemporaryDirectory() as d:
    root = Path(d)
    assert module.public_note_url(root, 'missing') is None
    assert module.public_note_url(root, '../../private') is None
    notes = root / 'reading-notes/books/example/notes'
    notes.mkdir(parents=True)
    for date in ['2026-10-19', '2026-10-20']:
        (notes / (date + '.html')).write_text('<h1>Public note</h1>')
    assert module.public_note_url(root, 'example').endswith('/2026-10-20.html')
labels = {'wechat-reading-browser': '阅读员-AI读书', 'local-pdf-reader': '阅读员-Windows读书', 'cue-qingyouji-reader': '阅读员-轻游记读书员'}
agents = {a['id']: a for a in state['agents']}
for agent_id, label in labels.items():
    assert agents[agent_id]['name'] == label
html = (ROOT / 'agent-room/index.html').read_text()
for label in [*labels.values(), '管理员-读书管理员']:
    assert label in html
assert '只读汇报员' not in html
assert '阅读团队统筹、错峰排班、任务分发和共享页面／组件设计规范' in html
class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.hrefs = []
    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.hrefs.extend(v for k, v in attrs if k == 'href')
for page in (ROOT / 'agent-room/tracks').glob('*.html'):
    parser = Links(); parser.feed(page.read_text())
    for url in parser.hrefs:
        if url and not url.startswith(('https:', 'http:', '#')):
            assert (page.parent / url.split('#')[0]).exists(), (page, url)
print('PASS: current team labels, admin duties, existing public note URLs, latest-note selection and track links')
