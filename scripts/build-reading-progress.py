#!/usr/bin/env python3
"""Generate a public, high-level reading progress page from main's safe sources.

Only book titles, coarse status flags, and existing public HTML note links are
emitted. Never serialize owners, run IDs, resume points, lock payloads, or notes.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "skills/luoyu-reading/references/book-registry.json"
TEMPLATE = ROOT / "templates/reading-progress.html"
OUTPUT = ROOT / "progress/index.html"
TZ = ZoneInfo("Asia/Shanghai")

# Only these public site artifacts are eligible as reading links.
TOP_LEVEL_ARTIFACTS = {
    "final.html": "整书汇编",
    "overview.html": "全书视角",
    "outline.html": "AI 大纲",
    "mindmap.html": "读书地图",
    "index.html": "公开归档页",
}


def within_root(path: Path) -> bool:
    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(ROOT.resolve())
        return resolved.exists()
    except (OSError, ValueError):
        return False


def artifact_label(path: Path) -> str:
    name = path.name
    if name in TOP_LEVEL_ARTIFACTS:
        if name == "index.html" and path.parts[:1] == ("books",):
            return "整书归档"
        return TOP_LEVEL_ARTIFACTS[name]
    if "notes" in path.parts:
        stem = path.stem
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", stem):
            return f"{stem} 日期笔记"
        if stem in {"deep-read", "deep_read"}:
            return "深读笔记"
        return "公开笔记"
    return "公开笔记"


def get_public_artifacts(book_id: str) -> list[dict[str, str]]:
    # Stable IDs are directory names, never arbitrary paths.
    if not re.fullmatch(r"[A-Za-z0-9._-]+", book_id):
        raise ValueError("Invalid book_id in registry; refusing to build public page")

    found: dict[str, dict[str, str]] = {}
    roots = [ROOT / "reading-notes" / "books" / book_id, ROOT / "books" / book_id]
    for book_dir in roots:
        if not book_dir.is_dir() or not within_root(book_dir):
            continue
        for name, label in TOP_LEVEL_ARTIFACTS.items():
            candidate = book_dir / name
            if candidate.is_file() and within_root(candidate):
                if name == "index.html" and book_dir.parent.name == "books":
                    label = "整书归档"
                found[candidate.relative_to(ROOT).as_posix()] = {
                    "label": label,
                    "path": candidate.relative_to(ROOT).as_posix(),
                }
        notes_dir = book_dir / "notes"
        if notes_dir.is_dir() and within_root(notes_dir):
            for candidate in sorted(notes_dir.glob("*.html")):
                if candidate.is_file() and within_root(candidate):
                    rel = candidate.relative_to(ROOT).as_posix()
                    found[rel] = {"label": artifact_label(candidate.relative_to(ROOT)), "path": rel}

    def sort_key(item: dict[str, str]) -> tuple[int, str]:
        order = {
            "整书汇编": 0,
            "整书归档": 0,
            "全书视角": 1,
            "深读笔记": 2,
            "公开笔记": 2,
            "AI 大纲": 3,
            "读书地图": 4,
        }
        label = item["label"]
        if label.endswith(" 日期笔记"):
            return (2, label)
        return (order.get(label, 5), label)

    return sorted(found.values(), key=sort_key)


def is_public_note(item: dict[str, str]) -> bool:
    path = item["path"]
    return "/notes/" in f"/{path}" or path.endswith(
        ("/overview.html", "/final.html", "/mindmap.html", "/index.html")
    )


def active_records(registry: dict) -> tuple[list[dict], int]:
    """Return modern activity registrations and count any legacy opaque lock."""
    unverified_legacy = 0
    sessions = registry.get("active_sessions", [])
    if not isinstance(sessions, list):
        return [], 1
    records = [x for x in sessions if isinstance(x, dict)]
    unverified_legacy += sum(not isinstance(x, dict) for x in sessions)
    legacy = registry.get("active_session")
    if legacy:
        # The legacy lock is deliberately not expanded or interpreted publicly.
        unverified_legacy += 1
    return records, unverified_legacy


def read_head_subject() -> str:
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%s"],
            cwd=ROOT,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        return result.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def current_day_log() -> str:
    now = datetime.now(TZ)
    path = ROOT / "skills/luoyu-reading/references/agent-communication" / now.strftime("%Y/%m/%Y-%m-%d.md")
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def has_current_run_evidence(run_id: str, head_subject: str, day_log: str) -> bool:
    """Be conservative: only call a run current when all three main-state signals match."""
    if not run_id or not head_subject.startswith("reading-state:") or run_id not in head_subject:
        return False
    if re.search(r"(?:结束|收尾|closed|completed)", head_subject, re.IGNORECASE):
        return False

    sections = re.split(r"(?m)(?=^### )", day_log)
    matching = [section for section in sections if run_id in section]
    if not matching:
        return False
    section = matching[-1]
    started = bool(
        re.search(r"(?m)^\s*-\s*实际开始\s*[:：]\s*\d{4}-\d{2}-\d{2}", section)
        and re.search(r"(?im)^\s*-\s*(?:状态|status)\s*[:：]\s*(?:started|进行中|running)", section)
    )
    end_values = re.findall(r"(?m)^\s*-\s*实际结束\s*[:：]\s*(.*)$", section)
    still_open = not end_values or all(
        value.strip() in {"本场进行中", "进行中", "未结束", "started"}
        for value in end_values
    )
    return started and still_open


def build_payload() -> dict:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    books = registry.get("books")
    if not isinstance(books, list):
        raise ValueError("Registry books must be a list; refusing to publish")

    sessions, invalid_or_legacy = active_records(registry)
    head_subject = read_head_subject()
    day_log = current_day_log()
    books_by_id = {
        item.get("book_id"): item
        for item in books
        if isinstance(item, dict) and isinstance(item.get("book_id"), str)
    }
    active_book_ids: set[str] = set()
    unverified_active = invalid_or_legacy
    seen_run_ids: set[str] = set()
    seen_book_ids: set[str] = set()
    for session in sessions:
        book_id = session.get("book_id")
        run_id = session.get("run_id")
        book = books_by_id.get(book_id) if isinstance(book_id, str) else None
        claim = book.get("claim") if isinstance(book, dict) and isinstance(book.get("claim"), dict) else {}
        owner_matches = (
            isinstance(book, dict)
            and isinstance(session.get("agent_id"), str)
            and session.get("agent_id") == book.get("owner_agent_id")
        )
        registry_matches = (
            isinstance(book, dict)
            and book.get("status") == "in_progress"
            and claim.get("state") == "held"
            and bool(book.get("resume_point"))
            and owner_matches
        )
        unique = isinstance(book_id, str) and isinstance(run_id, str) and run_id not in seen_run_ids and book_id not in seen_book_ids
        if isinstance(run_id, str):
            seen_run_ids.add(run_id)
        if isinstance(book_id, str):
            seen_book_ids.add(book_id)
        if unique and registry_matches and has_current_run_evidence(run_id, head_subject, day_log):
            active_book_ids.add(book_id)
        else:
            unverified_active += 1

    safe_books = []
    for raw in books:
        if not isinstance(raw, dict):
            raise ValueError("Invalid book entry in registry; refusing to publish")
        book_id = raw.get("book_id")
        title = raw.get("title")
        if not isinstance(book_id, str) or not isinstance(title, str) or not title.strip():
            raise ValueError("Book is missing a stable ID or title; refusing to publish")
        claim = raw.get("claim") if isinstance(raw.get("claim"), dict) else {}
        status = raw.get("status")
        completion = raw.get("completion")
        links = get_public_artifacts(book_id)
        safe_books.append(
            {
                "title": title.strip(),
                "planned": status == "queued",
                "claimed": claim.get("state") == "held",
                "actual_running": book_id in active_book_ids,
                "published": any(is_public_note(item) for item in links),
                "outline_published": any(item["label"] == "AI 大纲" for item in links),
                "completed": status == "completed" and isinstance(completion, dict) and bool(completion),
                "paused_or_blocked": status in {"paused", "blocked"},
                "links": links,
            }
        )

    counts = {
        "planned": sum(book["planned"] for book in safe_books),
        "claimed": sum(book["claimed"] for book in safe_books),
        "actual_running": sum(book["actual_running"] for book in safe_books),
        "published": sum(book["published"] for book in safe_books),
        "completed": sum(book["completed"] for book in safe_books),
    }
    return {
        "generated_at": datetime.now(TZ).isoformat(timespec="minutes"),
        "registry_revision": registry.get("revision"),
        "total_books": len(safe_books),
        "counts": counts,
        "unverified_active": unverified_active,
        "books": safe_books,
    }


def render_book(book: dict, index: int) -> str:
    title = html.escape(book["title"])
    search_terms = " ".join(
        [book["title"]] + [item["label"] for item in book["links"]]
    )
    search = html.escape(search_terms, quote=True)
    tags = []
    if book["planned"]:
        tags.append("<span class=\"status-chip plan\">计划中</span>")
    if book["claimed"]:
        tags.append("<span class=\"status-chip claim\">责任已登记（不等于当前运行）</span>")
    if book["actual_running"]:
        tags.append("<span class=\"status-chip running\">实际运行 · 已核验</span>")
    if book["published"]:
        tags.append("<span class=\"status-chip published\">笔记已发布</span>")
    elif book["outline_published"]:
        tags.append("<span class=\"status-chip published\">AI 大纲已发布</span>")
    if book["paused_or_blocked"]:
        tags.append("<span class=\"status-chip paused\">暂停／受阻 · 非当前运行</span>")
    if book["completed"]:
        tags.append("<span class=\"status-chip completed\">已完读</span>")
    if not any((book["planned"], book["claimed"], book["actual_running"], book["published"], book["outline_published"], book["completed"])):
        tags.append("<span class=\"status-chip neutral\">未认领</span>")

    notes = book["links"]
    if notes:
        entries = []
        for note in notes:
            href = "../" + "/".join(html.escape(part, quote=True) for part in note["path"].split("/"))
            label = html.escape(note["label"])
            entries.append(
                f'<li><div class="drawer-item"><a href="{href}">{label}</a></div></li>'
            )
        drawer = (
            '<details class="book-link-drawer">'
            '<summary><span>公开笔记链接</span>'
            f'<span class="drawer-count">{len(entries)} 项</span></summary>'
            f'<ol class="book-link-list">{"".join(entries)}</ol>'
            '</details>'
        )
        online = '<p class="online-state" data-online-state>线上可用性：打开页面后检查</p>'
    else:
        drawer = '<p class="book-empty-note">暂无已发布的公开笔记链接。</p>'
        online = '<p class="online-state muted">暂无链接可供线上检查</p>'

    return (
        f'<article class="book-card" data-book-index="{index}" data-search="{search}">'
        f'<h3>{title}</h3>'
        f'<div class="book-stages">{"".join(tags)}</div>'
        f'{online}{drawer}</article>'
    )


def json_for_html(payload: dict) -> str:
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return (
        text.replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT, help="Generated HTML page path")
    args = parser.parse_args()

    payload = build_payload()
    template = TEMPLATE.read_text(encoding="utf-8")
    stats = payload["counts"]
    substitutions = {
        "<!--READING_PROGRESS_SNAPSHOT-->": (
            f"<time datetime=\"{html.escape(payload['generated_at'], quote=True)}\">"
            f"{html.escape(payload['generated_at'])}</time> · registry revision "
            f"{html.escape(str(payload['registry_revision']))} · 共 {payload['total_books']} 本"
        ),
        "<!--TOTAL_BOOKS-->": str(payload["total_books"]),
        "<!--READING_PROGRESS_STATS-->": (
            f'<article class="metric-card"><p class="metric-label">计划中</p><p class="metric-value">{stats["planned"]}</p><p class="metric-note">队列中的书目</p></article>'
            f'<article class="metric-card"><p class="metric-label">责任登记</p><p class="metric-value">{stats["claimed"]}</p><p class="metric-note">已认领；不表示当前运行</p></article>'
            f'<article class="metric-card"><p class="metric-label">实际运行</p><p class="metric-value">{stats["actual_running"]}</p><p class="metric-note">仅显示可互证的当前场次</p></article>'
            f'<article class="metric-card"><p class="metric-label">笔记已发布</p><p class="metric-value">{stats["published"]}</p><p class="metric-note">至少有一个真实公开笔记页</p></article>'
            '<article class="metric-card"><p class="metric-label">线上可用</p><p class="metric-value" id="online-book-count">—</p><p class="metric-note" id="online-summary">打开本页后逐条检查链接</p></article>'
            f'<article class="metric-card"><p class="metric-label">已完读</p><p class="metric-value">{stats["completed"]} / {payload["total_books"]}</p><p class="metric-note">以 registry 完读登记为准</p></article>'
        ),
        "<!--READING_PROGRESS_BOOKS-->": "\n".join(render_book(book, i) for i, book in enumerate(payload["books"])),
        "<!--READING_PROGRESS_DATA-->": json_for_html(payload),
        "<!--READING_PROGRESS_UNVERIFIED-->": (
            f'<p class="verification-note" role="status">另有 {payload["unverified_active"]} 项活动登记未能与当前主线提交及当日记录互证，暂不计为正在运行。</p>'
            if payload["unverified_active"]
            else '<p class="verification-note" role="status">“实际运行”只计有权威活动登记、当前开始事件与当日记录相互印证的书；没有证据时不从“in_progress”推断。</p>'
        ),
    }
    rendered = template
    for marker, replacement in substitutions.items():
        if marker not in rendered:
            raise ValueError(f"Missing template marker: {marker}")
        rendered = rendered.replace(marker, replacement)
    if "<!--READING_PROGRESS_" in rendered:
        raise ValueError("Unresolved template marker; refusing to publish")

    # Fail closed if private/internal field names accidentally enter the public payload.
    forbidden = {"owner_agent_id", "resume_point", "run_id", "active_sessions", "last_run", "blocked_reason"}
    serialized_payload = json.dumps(payload, ensure_ascii=False)
    if any(key in serialized_payload for key in forbidden):
        raise ValueError("Private/internal registry field leaked into the public payload")

    output = args.output if args.output.is_absolute() else ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    print(
        f"Generated {output.relative_to(ROOT) if output.is_relative_to(ROOT) else output}: "
        f"revision={payload['registry_revision']}, books={payload['total_books']}, "
        f"planned={stats['planned']}, claimed={stats['claimed']}, "
        f"verified_running={stats['actual_running']}, published={stats['published']}, "
        f"completed={stats['completed']}"
    )


if __name__ == "__main__":
    main()
