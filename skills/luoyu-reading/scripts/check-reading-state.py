#!/usr/bin/env python3
"""Read-only validation of the shared WeRead registry and roster."""
import argparse
import json
from pathlib import Path

VALID_STATUSES = {"queued", "in_progress", "paused", "blocked", "completed"}
READING_MODES = {"weread_browser", "local_pdf", "other"}
SHARED_WEREAD_RESOURCE = "browser:weread-shared"
DURATION_WEREAD_RESOURCE = "browser:weread-duration"
CONFIRMED_WEREAD_RESOURCES = {SHARED_WEREAD_RESOURCE, DURATION_WEREAD_RESOURCE}
SHARED_WEREAD_AGENTS = {"cue-qingyouji-reader", "wechat-reading-browser"}


def validate(state, roster):
    errors = []
    agents = roster.get("agents", [])
    owners = {a.get("id") for a in agents if isinstance(a, dict) and a.get("id")}
    books = state.get("books", [])
    seen_ids = set()
    events, sequences = {}, {}
    for i, book in enumerate(books):
        label = book.get("book_id", f"books[{i}]")
        bid = book.get("book_id")
        if not bid:
            errors.append(f"书目缺少 book_id: {label}")
        elif bid in seen_ids:
            errors.append(f"book_id 重复: {bid}")
        else:
            seen_ids.add(bid)
        status = book.get("status")
        if status not in VALID_STATUSES:
            errors.append(f"{label}: 非法 status {status!r}")
        owner = book.get("owner_agent_id")
        claim = book.get("claim") or {}
        claim_state = claim.get("state")
        if status == "queued":
            if owner is not None or claim_state != "unclaimed":
                errors.append(f"{label}: queued 必须 owner 为空且 claim 为 unclaimed")
        elif status in {"in_progress", "paused", "blocked"}:
            if claim_state != "held" or not owner or owner not in owners:
                errors.append(f"{label}: {status} 必须 held 且 owner 有效")
        elif status == "completed":
            if claim_state != "released" or owner is not None:
                errors.append(f"{label}: completed 必须 released 且无 owner")

        completion = book.get("completion")
        if completion:
            eid, seq = completion.get("event_id"), completion.get("sequence")
            if not eid or not isinstance(seq, int) or isinstance(seq, bool):
                errors.append(f"{label}: completion 缺少 event_id/sequence")
            else:
                if eid in events:
                    errors.append(f"completion event_id 重复: {eid}")
                events[eid] = label
                if seq in sequences:
                    errors.append(f"completion sequence 重复: {seq}")
                sequences[seq] = label
        rp = book.get("resume_point") or {}
        if rp.get("status") == "confirmed":
            if not rp.get("chapter") and not rp.get("page"):
                errors.append(f"{label}: confirmed 续读点必须有 chapter 或 page，不能只用 progress")
            if rp.get("chapter") and not rp.get("position"):
                errors.append(f"{label}: confirmed chapter 续读点缺少 position")
    count = len(events)
    if sorted(sequences) != list(range(1, count + 1)):
        errors.append("completion sequence 必须从 1 连续递增")
    synthesis = state.get("synthesis") or {}
    if synthesis.get("unique_completed_count") != count:
        errors.append(f"完读计数不一致: 实际 {count}，登记 {synthesis.get('unique_completed_count')}")
    size = synthesis.get("batch_size")
    if size != 3:
        errors.append("synthesis.batch_size 必须为 3")
    batches = synthesis.get("batches", [])
    expected = count // 3
    if len(batches) != expected:
        errors.append(f"批次数不正确: 应为 {expected}，实际 {len(batches)}")
    ordered = sorted((b for b in books if b.get("completion") and isinstance((b.get("completion") or {}).get("sequence"), int)), key=lambda b: b["completion"]["sequence"])
    batch_ids = set()
    for i, batch in enumerate(batches):
        expected_id = f"batch-{i+1:03d}"
        if batch.get("batch_id") in batch_ids:
            errors.append(f"批次 ID 重复: {batch.get('batch_id')}")
        batch_ids.add(batch.get("batch_id"))
        if batch.get("batch_id") != expected_id:
            errors.append(f"批次 ID 应为 {expected_id}")
        wanted = [b["book_id"] for b in ordered[i*3:(i+1)*3]]
        if batch.get("book_ids") != wanted:
            errors.append(f"{expected_id}: 成员须按 completion.sequence 分组为 {wanted}")
        if batch.get("visibility") != "private":
            errors.append(f"{expected_id}: visibility 必须为 private")
        if batch.get("owner_agent_id") not in owners:
            errors.append(f"{expected_id}: owner_agent_id 无效")
        if batch.get("status") not in {"pending", "blocked", "completed", "needs-review"}:
            errors.append(f"{expected_id}: 批次状态无效")

    book_by_id = {b.get("book_id"): b for b in books if isinstance(b, dict)}
    legacy = state.get("active_session")
    legacy_present = legacy is not None
    legacy_valid = False
    if legacy_present:
        fields = ("run_id", "agent_id", "book_id", "slot", "started_at")
        legacy_valid = isinstance(legacy, dict) and all(isinstance(legacy.get(k), str) and legacy[k].strip() for k in fields)
        if not legacy_valid:
            errors.append("active_session 字段不完整或格式无效")
        else:
            book = book_by_id.get(legacy["book_id"])
            if legacy["agent_id"] not in owners or book is None or book.get("owner_agent_id") != legacy["agent_id"]:
                errors.append("active_session 的书目 owner/agent 不匹配")
                legacy_valid = False
            if book is not None and ((book.get("claim") or {}).get("state") != "held" or book.get("status") != "in_progress"):
                errors.append("active_session 必须对应 held 且 in_progress 的书目")
                legacy_valid = False

    scoped_value = state.get("active_sessions", [])
    if not isinstance(scoped_value, list):
        errors.append("active_sessions 必须为数组")
        scoped_sessions = []
    else:
        scoped_sessions = scoped_value
    if legacy_present and scoped_sessions:
        errors.append("active_session 与 active_sessions 不得同时使用")

    valid_scoped = []
    unique_fields = {key: set() for key in ("run_id", "book_id", "agent_id", "environment_id")}
    used_resources = set()
    for i, session in enumerate(scoped_sessions):
        label = f"active_sessions[{i}]"
        if not isinstance(session, dict):
            errors.append(f"{label} 必须为对象")
            continue
        required = ("run_id", "agent_id", "book_id", "slot", "started_at", "environment_id", "reading_mode")
        malformed = False
        for key in required:
            if not isinstance(session.get(key), str) or not session[key].strip():
                errors.append(f"{label}: {key} 必须为非空字符串")
                malformed = True
        resources = session.get("resource_ids")
        resources_ok = isinstance(resources, list) and bool(resources) and all(isinstance(r, str) and r.strip() for r in resources) and len(set(resources)) == len(resources)
        if not resources_ok:
            errors.append(f"{label}: resource_ids 必须为非空、无重复的非空字符串数组")
            malformed = True
        mode = session.get("reading_mode")
        if isinstance(mode, str) and mode not in READING_MODES:
            errors.append(f"{label}: reading_mode 无效")
            malformed = True
        bid = session.get("book_id")
        book_for_mode = book_by_id.get(bid) if isinstance(bid, str) else None
        if book_for_mode is not None and book_for_mode.get("platform") == "weread" and mode != "weread_browser":
            errors.append(f"{label}: weread 平台书目必须使用 weread_browser")
            malformed = True
        if isinstance(mode, str) and mode == "weread_browser" and isinstance(resources, list):
            browser_resources = [r for r in resources if isinstance(r, str) and r.startswith("browser:")]
            if len(browser_resources) != 1 or browser_resources[0] not in CONFIRMED_WEREAD_RESOURCES:
                errors.append(f"{label}: weread_browser 必须且仅能使用一个已确认浏览器资源（{SHARED_WEREAD_RESOURCE} 或 {DURATION_WEREAD_RESOURCE}）")
                malformed = True
            if isinstance(session.get("agent_id"), str) and session["agent_id"] in SHARED_WEREAD_AGENTS and browser_resources != [SHARED_WEREAD_RESOURCE]:
                errors.append(f"{label}: 已确认共享角色必须使用 {SHARED_WEREAD_RESOURCE}")
                malformed = True
        if isinstance(mode, str) and mode == "local_pdf":
            if book_for_mode is not None and book_for_mode.get("platform") == "weread":
                errors.append(f"{label}: local_pdf 不得用于 weread 平台书目")
                malformed = True
            if isinstance(resources, list) and any(isinstance(r, str) and r.startswith("browser:") for r in resources):
                errors.append(f"{label}: local_pdf 不得包含任何 browser:* 资源")
                malformed = True
        for key in unique_fields:
            value = session.get(key)
            if isinstance(value, str) and value.strip():
                if value in unique_fields[key]:
                    errors.append(f"{label}: {key} 重复")
                    malformed = True
                unique_fields[key].add(value)
        if resources_ok:
            overlap = used_resources.intersection(resources)
            if overlap:
                errors.append(f"{label}: resource_ids 与其他活动场次冲突: {sorted(overlap)}")
                malformed = True
            used_resources.update(resources)
        book = book_for_mode
        if isinstance(session.get("agent_id"), str) and session.get("agent_id") not in owners:
            errors.append(f"{label}: agent 无效")
            malformed = True
        if book is None or book.get("owner_agent_id") != session.get("agent_id"):
            errors.append(f"{label}: 书目 owner/agent 不匹配")
            malformed = True
        elif (book.get("claim") or {}).get("state") != "held" or book.get("status") != "in_progress":
            errors.append(f"{label}: 必须对应 held 且 in_progress 的书目")
            malformed = True
        if not malformed:
            valid_scoped.append(session)

    running_agents = [a for a in agents if isinstance(a, dict) and a.get("run_status") == "running"]
    if legacy_present:
        if legacy_valid:
            for agent in running_agents:
                if agent.get("id") != legacy.get("agent_id"):
                    errors.append(f"roster agent {agent.get('id')} running 与 active_session 锁冲突")
        elif running_agents:
            errors.append("roster 有 running agent 但无 active_session 或有效锁")
    else:
        for agent in running_agents:
            matches = [s for s in valid_scoped if s.get("agent_id") == agent.get("id")]
            if len(matches) != 1:
                errors.append(f"roster 有 running agent 但无 active_session；agent {agent.get('id')} 必须有且只有一个有效 active_session")
    return errors


def main(argv=None):
    base = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description="只读检查 WeRead 共享状态")
    parser.add_argument("--registry", type=Path, default=base / "references/book-registry.json")
    parser.add_argument("--roster", type=Path, default=base / "references/agent-roster.json")
    args = parser.parse_args(argv)
    try:
        state = json.loads(args.registry.read_text(encoding="utf-8"))
        roster = json.loads(args.roster.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"读取状态失败: {exc}")
        return 1
    errors = validate(state, roster)
    count = (state.get("synthesis") or {}).get("unique_completed_count", 0)
    next_threshold = (count // 3 + 1) * 3
    batches = state.get("synthesis", {}).get("batches", [])
    pending = [b.get("batch_id") for b in batches if b.get("status") in {"pending", "blocked"}]
    print(f"唯一完读数: {count}；下一阈值: {next_threshold}")
    print("待处理批次: " + (", ".join(pending) if pending else "无"))
    if errors:
        for error in errors:
            print(f"错误: {error}")
        return 1
    print("校验通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
