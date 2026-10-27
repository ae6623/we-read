#!/usr/bin/env python3
"""Build a privacy-safe, public agent-room state snapshot."""
import argparse
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import json
from pathlib import Path
import re


def parse_time(value):
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=ZoneInfo("Asia/Shanghai"))
        return parsed
    except ValueError:
        return None


def iso(value):
    parsed = parse_time(value)
    return parsed.isoformat() if parsed else None


# Public, structured facts transcribed from dated communication (never resume positions).
# Keep these entries aligned with the latest reliable end events in the daily log.
PUBLIC_PROGRESS = {
    "local-pdf-reader": {"bookTitle": "职业如何规划？大城市，小城市，如何抉择？我来说说我的个人经历和思考", "bookStatus": "paused", "recordedStatus": "未能开始阅读（受阻）", "coverage": "10月19日最新尝试未开读；此前续读至原帖 2014-05-24 09:53 回复（作者答复未读）", "duration": "最近成功选读窗口约9分48秒；最新受阻尝试0秒", "durationScope": "前者含本地解析与等待，并非纯阅读或平台时长；后者仅为最新受阻尝试，不合计", "recordedAt": "2026-10-19T01:41:39+08:00", "sourceLabel": "2026-10-19 沟通核实", "note": "本机工具及替代篇目预检受阻；保留已有续读点，未声称完成。"},
    "wechat-reading-browser": {"bookTitle": "大转向：世界如何步入现代", "bookStatus": "in_progress", "recordedStatus": "最近已确认部分阅读 · 非当前在线状态", "coverage": "第三章《寻找卢克莱修》开篇至西塞罗评价段末（截至 2026-10-18）", "duration": "未知", "durationScope": "未记录本段有效时长", "recordedAt": "2026-10-18T14:38:27+08:00", "sourceLabel": "注册表已确认边界", "note": "最近已确认的书目覆盖如上；不根据计划推断正在阅读。旧书《世界这么大，我想到处躺》已暂停。"},
    "weread-auto": {"bookTitle": "住小房子的女人", "bookStatus": "in_progress", "recordedStatus": "最近登记休息；本机任务停用", "coverage": "公开确认进度 12%；章节边界待确认", "duration": "未知", "durationScope": "无较新确认场次时长", "recordedAt": "2026-10-17T23:01:22+08:00", "sourceLabel": "运行清单与注册表", "note": "本机计划任务已停用；今日未有实际运行结束记录。"},
    "weread-auto-cloud": {"bookTitle": "大转折：现代债务与可持续的增长", "bookStatus": "in_progress", "recordedStatus": "阅读已结束；收尾延迟补报，活动锁记录不一致", "coverage": "《泡沫是好还是坏？》章内；未声称全书完成", "duration": "平台有效时长约 11.9 分钟；浏览窗口约 13 分钟", "durationScope": "前者为平台累计时长差，后者为运行窗口；不可互换", "recordedAt": "2026-10-19T02:19:13+08:00", "sourceLabel": "2026-10-19 沟通核实（02:21核实）", "note": "registry active_session 仍显示 01:58 开始的旧锁，但通信确认 02:19:13 run_active=False；close 曾进入待补队列，故标注记录不一致，不据旧锁称当前运行。"},
}

# User-approved target schedule, Asia/Shanghai. These are plans, not execution evidence.
TARGET_SCHEDULES = {
    "wechat-reading-browser": [("06:30", "07:30", "06:30"), ("14:00", "15:00", "14:00")],
    "weread-auto": [("08:00", "09:00", "08:00"), ("16:00", "17:00", "16:00")],
    "weread-auto-cloud": [("10:00", "11:00", "10:00"), ("19:00", "20:00", "19:00")],
    "local-pdf-reader": [],
}


def public_note_url(root, book_id):
    """Return the newest existing public date note, never invent an archive path."""
    if not isinstance(book_id, str) or not re.fullmatch(r"[a-z0-9-]+", book_id):
        return None
    candidates = list((root / "reading-notes/books" / book_id / "notes").glob("????-??-??.html"))
    legacy_slug = {"norway-night": "norway-night", "world-is-wide": "world-is-wide", "zhu-xiao-fang-zi-de-nv-ren": "zhu-xiao-fang-zi-de-nv-ren"}.get(book_id)
    if legacy_slug:
        candidates.extend((root / "notes").glob(f"*/????-??-??-{legacy_slug}.html"))
    candidates = [p for p in candidates if p.is_file() and re.match(r"\d{4}-\d{2}-\d{2}", p.name)]
    if not candidates:
        return None
    latest = max(candidates, key=lambda p: (p.name[:10], p.as_posix()))
    return "../" + latest.relative_to(root).as_posix()


def build(root):
    refs = root / "skills/luoyu-reading/references"
    roster = json.loads((refs / "agent-roster.json").read_text(encoding="utf-8"))
    registry = json.loads((refs / "book-registry.json").read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc)
    day = now.astimezone(ZoneInfo("Asia/Shanghai")).date().isoformat()
    comm = refs / "agent-communication" / day[:4] / day[5:7] / f"{day}.md"
    comm_text = comm.read_text(encoding="utf-8") if comm.exists() else ""
    session = registry.get("active_session") if isinstance(registry.get("active_session"), dict) else None
    active_agent = (session or {}).get("owner_agent_id") or (session or {}).get("agent_id")
    session_start = parse_time((session or {}).get("started_at"))

    def books_for(agent_id):
        return [b for b in registry.get("books", []) if isinstance(b, dict) and b.get("owner_agent_id") == agent_id and isinstance(b.get("claim"), dict) and b["claim"].get("state") == "held"]

    def progress_for(agent_id, fallback):
        owned = books_for(agent_id)
        active = [b for b in owned if b.get("status") == "in_progress"]
        # In-progress held book wins. Paused history only wins when no active assignment.
        selected = active[0] if active else None
        if selected is None:
            paused = [b for b in owned if b.get("status") == "paused"]
            def book_time(b):
                cp = b.get("last_confirmed_progress")
                rp = b.get("resume_point")
                return parse_time(cp.get("confirmed_at") if isinstance(cp, dict) else None) or parse_time(rp.get("confirmed_at") if isinstance(rp, dict) else None) or datetime.min.replace(tzinfo=timezone.utc)
            paused.sort(key=book_time, reverse=True)
            selected = paused[0] if paused else None
        if not selected:
            return fallback
        out = dict(fallback)
        if selected.get("title") != fallback.get("bookTitle"):
            out.update(recordedStatus="书目已有更新；当前运行状态待确认", coverage="新书章节覆盖未确认", duration="未知", durationScope="不沿用旧书场次时长", recordedAt=None, sourceLabel="最新共享书目登记", note="书目归属按最新注册表；不沿用旧书阅读事实。")
        out["bookTitle"] = selected.get("title")
        out["bookStatus"] = selected.get("status", "unknown")
        rp = selected.get("resume_point") if isinstance(selected.get("resume_point"), dict) else {}
        conf = selected.get("last_confirmed_progress") if isinstance(selected.get("last_confirmed_progress"), dict) else {}
        chapter = conf.get("chapter") or rp.get("chapter")
        confirmed = parse_time(conf.get("confirmed_at") or rp.get("confirmed_at"))
        fallback_time = parse_time(out.get("recordedAt"))
        if chapter and confirmed and (not fallback_time or confirmed > fallback_time):
            out["coverage"] = f"已确认章节：《{chapter}》；具体阅读位置不公开"
        if confirmed and (not fallback_time or confirmed > fallback_time):
            out["recordedAt"] = confirmed.isoformat()
            out["sourceLabel"] = "注册表已确认进度"
            out["recordedStatus"] = "已有确认进度；当前场次状态待核验"
            out["duration"] = "未知"
            out["durationScope"] = "没有本次场次的确认时长"
        prog=selected.get("last_confirmed_progress")
        if isinstance(prog, str) and re.fullmatch(r"\s*\d+(?:\.\d+)?%\s*",prog):
            label = "注册表确认进度 " + prog.strip()
            if out.get("coverage") and "章节边界待确认" not in out["coverage"]:
                out["coverage"] += "；" + label
            else:
                out["coverage"] = label + "；章节边界待确认"
        return out

    agents = []
    for source in roster.get("agents", []):
        agent_id = source.get("id")
        start_raw, end_raw = source.get("last_started_at"), source.get("last_ended_at")
        start, end = parse_time(start_raw), parse_time(source.get("last_ended_at"))
        status = source.get("run_status")
        status = status if status in {"idle", "running", "completed", "failed", "blocked", "unknown"} else "unknown"
        # Fresh roster starts override any dated fallback terminal event.
        fallback = dict(PUBLIC_PROGRESS.get(agent_id, {"bookTitle": None, "bookStatus": "unknown", "recordedStatus": "未知", "coverage": None, "duration": "未知", "durationScope": "未知", "recordedAt": None, "sourceLabel": None, "note": None}))
        fallback_time = parse_time(fallback.get("recordedAt"))
        fresh_start = start and (not fallback_time or start > fallback_time)
        is_session = agent_id == active_agent and session_start
        if is_session:
            status = "running"
        if fresh_start:
            status = source.get("run_status") if source.get("run_status") in {"running","completed","failed","blocked","idle"} else "unknown"
            labels = {"running":"较新登记运行中 · 非在线探测", "completed":"较新场次登记结束；成果待核验", "blocked":"较新记录受阻；实读结果待核验", "failed":"较新场次失败；实读结果待核验", "idle":"最近登记休息；阅读结果待核验"}
            fallback.update(recordedStatus=labels.get(status,"较新场次状态待确认"), duration="未知", durationScope="较新场次时长待核验", sourceLabel="较新运行登记", recordedAt=(end if end and end > start else start).isoformat(), note="较新记录优先；已确认的历史章节覆盖不代表本场新增阅读。")
        # Today’s appended communication can invalidate fallback certainty if it contains a newer reading event for the role.
        role_terms = {"weread-auto-cloud": r"云端|weread-auto-cloud", "weread-auto": r"本机|weread-auto(?!-cloud)", "wechat-reading-browser": r"AI读书|微信读书|wechat-reading-browser", "local-pdf-reader": r"本地试读|Windows读书|local-pdf-reader"}.get(agent_id, re.escape(str(agent_id)))
        if fallback_time and comm_text:
            # Inspect dated event headings, not arbitrary mentions elsewhere in the daily file.
            for line in comm_text.splitlines():
                if not line.startswith("###") or not re.search(role_terms, line, re.I):
                    continue
                match = re.search(r"(2026-\d\d-\d\d[T ]\d\d:\d\d(?::\d\d)?(?:\+08:00)?)", line)
                event_time = parse_time(match.group(1)) if match else None
                # Administrative reviews, handoffs and preflight checks are not reading-session events.
                if re.search(r"核查|核实|verify|review|交接|预检|工具与换篇|user-ruling|代补收尾", line, re.I):
                    continue
                if not re.search(r"开始登记|开始\b|结束|中断|未开读|completed_reading|blocked_before_reading|run_start|run_end", line, re.I):
                    continue
                if event_time and event_time > fallback_time:
                    fallback["recordedStatus"] = "今日通信有较新阅读事件；结果待核验"
                    fallback["duration"] = "未知"
                    fallback["durationScope"] = "较新阅读场次时长待核验"
                    fallback["sourceLabel"] = "今日通信（阅读事件待核验）"
                    break
        progress = progress_for(agent_id, fallback)
        if agent_id == "weread-auto":
            # Confirmed disabled facts in today’s dated communication, not legacy schedule_basis wording.
            if not fresh_start:
                progress["note"] = "2026-10-19 沟通确认本机计划任务停用；未见较新运行记录。"
        if agent_id == "weread-auto-cloud":
            verified_end = parse_time("2026-10-19T02:19:13+08:00")
            no_new_roster_start = not (start and start > verified_end)
            if session_start and session_start <= verified_end and no_new_roster_start:
                status = "completed"
            elif session_start and session_start > verified_end:
                status = "running"
                progress["recordedStatus"] = "较新活动锁存在；运行状态待核验"
                progress["duration"] = "未知"
                progress["durationScope"] = "较新场次时长未知"
            else:
                status = "unknown" if status == "running" else status
            if not (session_start and session_start > verified_end) and no_new_roster_start:
                progress["note"] = "2026-10-19 02:19核实该场已结束；旧活动锁未同步。注册表73%，沟通报告约74%，保留差异、不覆盖源记录。"
                progress["runningConfirmed"] = False
        if is_session and session_start and (not fallback_time or session_start > fallback_time):
            if not end or end < session_start:
                start_raw = session_start.isoformat()
                end_raw = None
                age = (now - session_start).total_seconds()
                progress["recordedAt"] = session_start.isoformat()
                progress["runningConfirmed"] = 0 <= age < 1800
                progress["recordedStatus"] = "近期登记运行中 · 非在线探测" if progress["runningConfirmed"] else "旧活动登记 · 当前运行待确认"
                progress["duration"] = "未知"
                progress["durationScope"] = "活动登记不等于实际阅读时长"
                progress["note"] = "以较新活动登记为准，未确认本场新增覆盖或结束结果。"
        schedules = []
        target = TARGET_SCHEDULES.get(agent_id)
        if target is not None:
            schedules = [{"start": a, "end": b, "trigger": c} for a, b, c in target]
        else:
            for slot in source.get("schedule", []) if isinstance(source.get("schedule", []), list) else []:
                if isinstance(slot, dict):
                    schedules.append({"start": slot.get("window_start"), "end": slot.get("window_end"), "trigger": slot.get("trigger_at")})
        agents.append({"id": agent_id, "name": source.get("display_name") if isinstance(source.get("display_name"), str) else None, "type": source.get("type") if isinstance(source.get("type"), str) else None, "runStatus": status, "lastStartedAt": iso(start_raw), "lastEndedAt": iso(end_raw), "schedule": schedules, "scheduleBasis": "用户确认的目标计划；执行未据此推断", "schedulePaused": agent_id == "weread-auto" and not fresh_start and bool(re.search(r"WeReadDaily.{0,80}(?:Disabled|停用)|(?:停用|Disabled).{0,80}WeReadDaily|本机计划任务仍 Disabled", comm_text, re.I)), "progressDisplay": progress, **({"statusUnconfirmed": True} if status == "running" and start and not end and (now-start).total_seconds() > 1800 else {})})
    books=[]
    for source in registry.get("books", []):
        if not isinstance(source, dict): continue
        claim=source.get("claim") if isinstance(source.get("claim"),dict) else {}
        progress=source.get("last_confirmed_progress")
        safe_progress=progress.strip() if isinstance(progress,str) and re.fullmatch(r"\s*\d+(?:\.\d+)?%\s*",progress) else None
        books.append({"id":source.get("book_id"),"title":source.get("title"),"author":source.get("author"),"status":source.get("status","unknown"),"owner":source.get("owner_agent_id"),"claimState":claim.get("state","unknown"),"priority":source.get("priority"),"progress":safe_progress,"noteUrl":public_note_url(root, source.get("book_id"))})
    return {"schemaVersion":1,"generatedAt":now.isoformat(),"progressAsOf":day,"communicationDate":day,"rosterUpdatedAt":iso(roster.get("updated_at")),"revision":registry.get("revision"),"timezone":roster.get("timezone","unknown"),"agents":agents,"books":books}


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
