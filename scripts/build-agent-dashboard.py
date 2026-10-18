#!/usr/bin/env python3
"""Build a privacy-safe, public agent-room state snapshot."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re


def parse_time(value):
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        return None


def iso(value):
    parsed = parse_time(value)
    return parsed.isoformat() if parsed else None


def build(root):
    refs = root / "skills/luoyu-reading/references"
    roster = json.loads((refs / "agent-roster.json").read_text(encoding="utf-8"))
    registry = json.loads((refs / "book-registry.json").read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc)
    session = registry.get("active_session")
    active_agent = None
    if isinstance(session, dict):
        active_agent = session.get("owner_agent_id") or session.get("agent_id")
    agents = []
    for source in roster.get("agents", []):
        agent_id = source.get("id")
        start_raw, end_raw = source.get("last_started_at"), source.get("last_ended_at")
        start, end = parse_time(start_raw), parse_time(end_raw)
        status = source.get("run_status")
        status = status if status in {"idle", "running", "completed", "failed", "unknown"} else "unknown"
        if agent_id and agent_id == active_agent:
            status = "running"
        schedules = []
        for slot in source.get("schedule", []) if isinstance(source.get("schedule", []), list) else []:
            if not isinstance(slot, dict):
                continue
            schedules.append({"start": slot.get("window_start") if isinstance(slot.get("window_start"), str) else None,
                              "end": slot.get("window_end") if isinstance(slot.get("window_end"), str) else None,
                              "trigger": slot.get("trigger_at") if isinstance(slot.get("trigger_at"), str) else None})
        basis = source.get("schedule_basis", "")
        agents.append({
            "id": agent_id,
            "name": source.get("display_name") if isinstance(source.get("display_name"), str) else None,
            "type": source.get("type") if isinstance(source.get("type"), str) else None,
            "runStatus": status,
            "lastStartedAt": iso(start_raw),
            "lastEndedAt": iso(end_raw),
            "schedule": schedules,
            "schedulePaused": bool(agent_id == "weread-auto" and isinstance(basis, str) and re.search(r"停用中", basis)),
            **({"statusUnconfirmed": True} if status == "running" and start and not end and (now - start).total_seconds() > 1800 else {}),
        })
    books = []
    for source in registry.get("books", []):
        if not isinstance(source, dict):
            continue
        claim = source.get("claim") if isinstance(source.get("claim"), dict) else {}
        progress = source.get("last_confirmed_progress")
        if isinstance(progress, str) and re.fullmatch(r"\s*\d+(?:\.\d+)?%\s*", progress):
            safe_progress = progress.strip()
        else:
            safe_progress = None
        books.append({
            "id": source.get("book_id") if isinstance(source.get("book_id"), str) else None,
            "title": source.get("title") if isinstance(source.get("title"), str) else None,
            "author": source.get("author") if isinstance(source.get("author"), str) else None,
            "status": source.get("status") if isinstance(source.get("status"), str) else "unknown",
            "owner": source.get("owner_agent_id") if isinstance(source.get("owner_agent_id"), str) else None,
            "claimState": claim.get("state") if isinstance(claim.get("state"), str) else "unknown",
            "priority": source.get("priority") if isinstance(source.get("priority"), str) else None,
            "progress": safe_progress,
        })
    return {"schemaVersion": 1, "generatedAt": now.isoformat(),
            "rosterUpdatedAt": iso(roster.get("updated_at")), "revision": registry.get("revision"),
            "timezone": roster.get("timezone") if isinstance(roster.get("timezone"), str) else "unknown",
            "agents": agents, "books": books}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1], help="repository root")
    args = parser.parse_args()
    root = args.root.resolve()
    output = root / "agent-room/state.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(build(root), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
