#!/usr/bin/env python3
"""Fail deployment if the reading progress screen or privacy-safe data regresses."""
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
room = ROOT / 'agent-room'
html = (room / 'index.html').read_text(encoding='utf-8')
js = (room / 'room.js').read_text(encoding='utf-8')
css = (room / 'room.css').read_text(encoding='utf-8')
raw = (room / 'state.json').read_text(encoding='utf-8')
state = json.loads(raw)
for element in ['progress-screen', 'progress-title', 'progress-asof', 'progress-readers', 'daily-plan-slots']:
    assert f'id="{element}"' in html, f'Missing progress screen element: {element}'
assert 'renderProgress();' in js and '.progress-screen{' in css
expected = {
    'wechat-reading-browser': [('06:30', '07:30'), ('14:00', '15:00')],
    'weread-auto': [('08:00', '09:00'), ('16:00', '17:00')],
    'weread-auto-cloud': [('10:00', '11:00'), ('19:00', '20:00')],
    'local-pdf-reader': [],
}
agents = {a['id']: a for a in state['agents']}
for agent_id, slots in expected.items():
    assert agent_id in agents, f'Missing role: {agent_id}'
    agent = agents[agent_id]
    assert [(s['start'], s['end']) for s in agent['schedule']] == slots
    assert isinstance(agent.get('progressDisplay'), dict)
    for key in ['recordedStatus', 'coverage', 'duration', 'durationScope', 'recordedAt']:
        assert key in agent['progressDisplay'], f'Missing field: {agent_id}/{key}'
for pattern in [r'"(?:run_id|session_id|active_session|resume_point|position)"\s*:', r'/workspace/', r'/home/ubuntu/', r'[A-Z]:[\\/]', r'gh[pousr]_\w{10,}']:
    assert not re.search(pattern, raw), f'Unexpected private field or path: {pattern}'
print('PASS: progress screen present, four distinct reader roles, six target slots, privacy-safe facts')
