#!/usr/bin/env python3
"""只读筛选候选；不认领、不改排班，也不读取书籍正文。"""
import argparse
import json
import unicodedata
from pathlib import Path


def normalized(value):
    text = unicodedata.normalize("NFKC", value).casefold()
    return "".join(c for c in text if not c.isspace() and not unicodedata.category(c).startswith("P"))


def text(value):
    return isinstance(value, str) and bool(value.strip())


def string_list(value):
    return isinstance(value, list) and all(text(v) for v in value)


def validate_blacklist(data):
    if not isinstance(data, dict) or type(data.get("schema_version")) is not int or data["schema_version"] != 1:
        raise ValueError("黑名单 schema_version 必须为 1")
    if type(data.get("revision")) is not int or data["revision"] < 1:
        raise ValueError("黑名单 revision 必须为正整数")
    for key in ("books", "topic_rules"):
        if not isinstance(data.get(key), list):
            raise ValueError(f"黑名单 {key} 必须为数组")
    ids = set()
    for book in data["books"]:
        if not isinstance(book, dict) or not all(text(book.get(k)) for k in ("book_id", "title", "author", "reason")):
            raise ValueError("黑名单书目缺少有效 ID、题名、作者或理由")
        if book["book_id"] in ids:
            raise ValueError("黑名单 book_id 重复")
        ids.add(book["book_id"])
        if not string_list(book.get("title_aliases")) or not isinstance(book.get("platform_ids"), list):
            raise ValueError("黑名单题名别名或平台 ID 格式无效")
        for item in book["platform_ids"]:
            if not isinstance(item, dict) or not text(item.get("platform")) or not text(item.get("platform_book_id")):
                raise ValueError("黑名单 platform_ids 项须有平台及非空字符串 ID")
        if book.get("basis") != "user_explicit":
            raise ValueError("永久黑名单只接受用户明确决定")
    ids = set()
    for rule in data["topic_rules"]:
        if not isinstance(rule, dict) or not all(text(rule.get(k)) for k in ("rule_id", "label", "scope", "not_scope", "reason")):
            raise ValueError("黑名单主题规则缺少必要字段")
        if rule["rule_id"] in ids:
            raise ValueError("黑名单主题 rule_id 重复")
        ids.add(rule["rule_id"])
        if not string_list(rule.get("topics")) or not rule["topics"] or not string_list(rule.get("title_signals")):
            raise ValueError("黑名单主题或题名信号格式无效")
        if rule.get("basis") != "user_explicit":
            raise ValueError("主题禁读只接受用户明确决定")
    return data


def classify(candidate, blacklist):
    if not isinstance(candidate, dict):
        raise ValueError("每个候选必须为对象")
    for field in ("book_id", "title", "author", "platform", "platform_book_id"):
        if candidate.get(field) is not None and not isinstance(candidate[field], str):
            raise ValueError(f"候选 {field} 必须为字符串或 null")
    if not text(candidate.get("book_id")) and not text(candidate.get("title")):
        raise ValueError("候选缺少可核对的 book_id 或 title")
    topics = candidate.get("topics", [])
    if not string_list(topics):
        raise ValueError("候选 topics 必须为非空字符串组成的数组")
    assessments = candidate.get("topic_assessments", {})
    if not isinstance(assessments, dict):
        raise ValueError("候选 topic_assessments 必须为对象")
    for assessment in assessments.values():
        if not isinstance(assessment, dict) or type(assessment.get("matches")) is not bool or not text(assessment.get("evidence")):
            raise ValueError("主题判断须含 matches 布尔值及非空 evidence 元数据依据")
    blocked, review = [], []
    title = normalized(candidate.get("title") or "")
    author = normalized(candidate.get("author") or "")
    for book in blacklist["books"]:
        rule_id = "book:" + book["book_id"]
        id_match = candidate.get("book_id") == book["book_id"]
        platform_match = any(candidate.get("platform") == item["platform"] and candidate.get("platform_book_id") == item["platform_book_id"] for item in book["platform_ids"])
        title_match = bool(title) and title in {normalized(v) for v in [book["title"], *book["title_aliases"]]}
        if id_match or platform_match or (title_match and (not author or author == normalized(book["author"]))):
            blocked.append({"rule_id": rule_id, "reason": book["reason"]})
        elif title_match:
            review.append({"rule_id": rule_id, "reason": "同名但作者不符，先核对是否同书，不自动放行"})
    topic_keys = {normalized(t) for t in topics}
    for rule in blacklist["topic_rules"]:
        rid = rule["rule_id"]
        assessment = assessments.get(rid)
        topic_match = bool(topic_keys & {normalized(t) for t in rule["topics"]})
        if topic_match or (assessment and assessment["matches"]):
            blocked.append({"rule_id": rid, "reason": rule["reason"]})
        elif not assessment:
            signals = [s for s in rule["title_signals"] if normalized(s) in title]
            reason = "须由选书 Agent 基于题名、简介或目录核清主题；不向用户重复询问"
            if signals:
                reason += "；题名信号：" + "、".join(signals)
            review.append({"rule_id": rid, "reason": reason})
    return {"candidate": candidate, "status": "excluded" if blocked else "needs_review" if review else "not_blacklisted", "matches": blocked or review}


def filter_candidates(candidates, blacklist):
    validate_blacklist(blacklist)
    if not isinstance(candidates, list):
        raise ValueError("候选输入须为数组，或含 books 数组的对象")
    results = {"blacklist_revision": blacklist["revision"], "not_blacklisted": [], "excluded": [], "needs_review": []}
    for candidate in candidates:
        result = classify(candidate, blacklist)
        results[result["status"]].append(result)
    return results


def main(argv=None):
    base = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blacklist", type=Path, default=base / "references/reading-blacklist.json")
    parser.add_argument("--candidates", type=Path, default=base / "references/book-registry.json")
    parser.add_argument("--book-id", help="只核查指定候选 ID；未找到时失败，不视为放行")
    args = parser.parse_args(argv)
    try:
        blacklist = json.loads(args.blacklist.read_text(encoding="utf-8"))
        source = json.loads(args.candidates.read_text(encoding="utf-8"))
        candidates = source.get("books") if isinstance(source, dict) else source
        if args.book_id:
            if not isinstance(candidates, list):
                raise ValueError("候选输入缺少 books 数组")
            candidates = [b for b in candidates if isinstance(b, dict) and b.get("book_id") == args.book_id]
            if len(candidates) != 1:
                raise ValueError("指定候选 ID 未找到或重复；不能默认放行")
        results = filter_candidates(candidates, blacklist)
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc), "selection_allowed": False}, ensure_ascii=False))
        return 1
    print(json.dumps(results, ensure_ascii=False, indent=2))
    # 2 表示指定书不可自动选；批量成功输出三类结果不等于所有候选可读。
    if args.book_id and not results["not_blacklisted"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
