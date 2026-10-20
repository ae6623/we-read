#!/usr/bin/env python3
"""Validate shared archive entry drawers without third-party packages."""
from html.parser import HTMLParser
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]

class Node:
    def __init__(self, tag='', attrs=(), parent=None):
        self.tag, self.attrs, self.parent = tag, dict(attrs), parent
        self.children, self.text = [], ''
    def has(self, name):
        return name in self.attrs.get('class', '').split()
    def all(self, tag=None):
        for child in self.children:
            if tag is None or child.tag == tag:
                yield child
            yield from child.all(tag)
    def content(self):
        return self.text + ''.join(c.content() for c in self.children)

class Document(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.root = Node()
        self.stack = [self.root]
        self.feed(text)
    def handle_starttag(self, tag, attrs):
        n = Node(tag, attrs, self.stack[-1])
        self.stack[-1].children.append(n)
        if tag not in {'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}:
            self.stack.append(n)
    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)
    def handle_endtag(self, tag):
        for i in range(len(self.stack)-1, 0, -1):
            if self.stack[i].tag == tag:
                self.stack = self.stack[:i]
                break
    def handle_data(self, data):
        self.stack[-1].text += data

def check():
    total = pages = 0
    for path in ROOT.rglob('*.html'):
        if '.git' in path.parts or 'templates' in path.parts or 'skills' in path.parts:
            continue
        root = Document(path.read_text()).root
        drawers = [n for n in root.all('details') if n.has('book-link-drawer')]
        if not drawers:
            continue
        pages += 1
        styles = [n.attrs.get('href', '') for n in root.all('link')]
        assert any(h.endswith('assets/css/book-link-drawer.css') for h in styles), path
        for drawer in drawers:
            total += 1
            assert 'open' not in drawer.attrs, f'{path}: must default to collapsed'
            summaries = [n for n in drawer.children if n.tag == 'summary']
            lists = [n for n in drawer.children if n.tag == 'ol' and n.has('book-link-list')]
            assert len(summaries) == len(lists) == 1, path
            assert not list(summaries[0].all('a')), f'{path}: summary contains a link'
            items = [n for n in lists[0].children if n.tag == 'li']
            assert items, f'{path}: empty drawer'
            count = next(n for n in summaries[0].all() if n.has('drawer-count'))
            assert count.content().strip() == f'{len(items)} 项', f'{path}: incorrect count'
            for item in items:
                links = list(item.all('a'))
                assert len(links) == 1, f'{path}: each item needs exactly one link'
                href = links[0].attrs.get('href', '')
                assert href and not href.startswith('javascript:'), path
                url = urlsplit(href)
                if url.scheme or url.netloc:
                    continue
                target = unquote(url.path)
                if target.startswith('/we-read/'):
                    dest = ROOT / target[len('/we-read/'):]
                elif target.startswith('/'):
                    dest = ROOT / target.lstrip('/')
                else:
                    dest = path.parent / target if target else path
                if dest.is_dir():
                    dest = dest / 'index.html'
                assert dest.exists(), f'{path}: missing target {href}'
                if url.fragment and dest.suffix == '.html':
                    ids = {n.attrs.get('id') for n in Document(dest.read_text()).root.all()}
                    assert unquote(url.fragment) in ids, f'{path}: missing fragment {href}'
        # Searchable cards keep their action targets inside the shared component.
        for card in [n for n in root.all('article') if n.has('archive-card') and not n.has('archive-note')]:
            for link in card.all('a'):
                if link.has('card-link') or link.has('download-link'):
                    raise AssertionError(f'{path}: legacy ungrouped card action')
    assert total > 0
    css = (ROOT / 'assets/css/book-link-drawer.css').read_text()
    assert 'counter(book-entry)' in css and 'focus-visible' in css
    print(f'PASS: {total} collapsed numbered drawers across {pages} pages; counts, targets, fragments and shared stylesheet valid')

if __name__ == '__main__':
    check()
