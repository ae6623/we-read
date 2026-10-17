#!/usr/bin/env python3
"""Read-only validation of the shared WeRead registry and roster."""
import argparse
import json
from pathlib import Path

VALID_STATUSES = {"queued", "in_progress", "paused", "blocked", "completed"}


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
    session = state.get("active_session")
    if session is not None:
        required = ("run_id", "agent_id", "book_id", "slot", "started_at")
        if not isinstance(session, dict) or any(not session.get(k) for k in required):
            errors.append("active_session 字段不完整")
        else:
            book = next((b for b in books if b.get("book_id") == session["book_id"]), None)
            if session["agent_id"] not in owners or book is None or book.get("owner_agent_id") != session["agent_id"]:
                errors.append("active_session 的书目 owner/agent 不匹配")
            if book is not None and ((book.get("claim") or {}).get("state") != "held" or book.get("status") != "in_progress"):
                errors.append("active_session 必须对应 held 且 in_progress 的书目")
    running_agents = [a for a in agents if isinstance(a, dict) and a.get("run_status") == "running"]
    if running_agents and session is None:
        errors.append("roster 有 running agent 但无 active_session")
    if session is not None:
        for agent in running_agents:
            if not isinstance(session, dict) or agent.get("id") != session.get("agent_id"):
                errors.append(f"roster agent {agent.get('id')} running 与 active_session 锁冲突")
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
