"""Synthetic fixtures only: never mutate the live registry or roster."""
import copy
import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "checker", Path(__file__).with_name("check-reading-state.py"))
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)

# Literal fixtures deliberately do not derive authorization from code constants.
LOCK = {
    "run_id": "browser-spring-20261022-2330-233216",
    "agent_id": "wechat-reading-browser",
    "book_id": "rites-of-spring-eksteins",
    "slot": "daily_2330",
    "started_at": "2026-10-22T23:32:16+08:00",
}
PDF = {
    "run_id": "windows-synthetic-test",
    "agent_id": "local-pdf-reader",
    "book_id": "local-modern-finance-housing-curgdbd",
    "slot": "manual_user_requested",
    "started_at": "2026-10-23T00:25:00+08:00",
    "environment_id": "windows:local-pdf-reader",
    "reading_mode": "local_pdf",
    "resource_ids": ["local_pdf:windows-reader"],
    "legacy_exception_run_id": "browser-spring-20261022-2330-233216",
}


def fixture():
    books = []
    for item, platform in ((LOCK, "weread"), (PDF, "local_pdf")):
        books.append({"book_id": item["book_id"], "platform": platform,
                      "owner_agent_id": item["agent_id"], "status": "in_progress",
                      "claim": {"state": "held"}, "completion": None})
    return ({"books": books, "active_session": copy.deepcopy(LOCK),
             "active_sessions": [copy.deepcopy(PDF)],
             "synthesis": {"unique_completed_count": 0, "batch_size": 3, "batches": []}},
            {"agents": [{"id": LOCK["agent_id"], "run_status": "running"},
                        {"id": PDF["agent_id"], "run_status": "running"}]})


class LegacyPdfExceptionTests(unittest.TestCase):
    def test_exact_exception_and_read_only(self):
        state, roster = fixture()
        before = copy.deepcopy((state, roster))
        self.assertEqual([], checker.validate(state, roster))
        self.assertEqual(before, (state, roster))

    def test_every_legacy_field_is_pinned(self):
        for field in LOCK:
            for value in ("different", None):
                with self.subTest(field=field, value=value):
                    state, roster = fixture()
                    state["active_session"][field] = value
                    self.assertTrue(checker.validate(state, roster))
        state, roster = fixture()
        state["active_session"]["extra"] = "not-original"
        self.assertTrue(checker.validate(state, roster))

    def test_each_scope_dimension_fail_closed(self):
        variants = {
            "agent_id": ["another-agent", LOCK["agent_id"]],
            "book_id": ["local-other-book", LOCK["book_id"], None, []],
            "reading_mode": ["other", "weread_browser"],
            "environment_id": ["cloud:pdf", "windows:other"],
            "resource_ids": [["browser:weread-shared"], ["local_pdf:other"],
                             ["local_pdf:windows-reader", "local_pdf:extra"], [], None],
            "legacy_exception_run_id": ["different", "", None],
            "run_id": [LOCK["run_id"], "", None],
        }
        for field, values in variants.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    state, roster = fixture()
                    state["active_sessions"][0][field] = value
                    self.assertTrue(checker.validate(state, roster))
        state, roster = fixture()
        del state["active_sessions"][0]["legacy_exception_run_id"]
        self.assertTrue(checker.validate(state, roster))

    def test_no_second_session_even_if_independent(self):
        state, roster = fixture()
        second = copy.deepcopy(PDF)
        second.update(run_id="other", agent_id="other", book_id="other",
                      environment_id="other", resource_ids=["local_pdf:other"])
        roster["agents"].append({"id": "other", "run_status": "running"})
        state["books"].append({"book_id": "other", "platform": "local_pdf",
                               "owner_agent_id": "other", "status": "in_progress",
                               "claim": {"state": "held"}})
        state["active_sessions"].append(second)
        self.assertTrue(any("不得同时使用" in e for e in checker.validate(state, roster)))

    def test_expiry_missing_null_replaced_or_invalid_lock(self):
        for value in (None, {}, {**LOCK, "run_id": "future-run"}, False):
            with self.subTest(lock=value):
                state, roster = fixture()
                state["active_session"] = value
                roster["agents"][0]["run_status"] = "idle"
                self.assertTrue(any("失效" in e for e in checker.validate(state, roster)))
        state, roster = fixture()
        del state["active_session"]
        roster["agents"][0]["run_status"] = "idle"
        self.assertTrue(any("失效" in e for e in checker.validate(state, roster)))

    def test_book_owner_claim_status_and_platform_still_required(self):
        for index, field, value in ((0, "status", "paused"), (0, "owner_agent_id", "local-pdf-reader"),
                                    (1, "status", "blocked"), (1, "owner_agent_id", "wechat-reading-browser"),
                                    (1, "claim", {"state": "unclaimed"}), (1, "platform", "weread"),
                                    (1, "platform", "unknown")):
            with self.subTest(index=index, field=field):
                state, roster = fixture()
                state["books"][index][field] = value
                self.assertTrue(checker.validate(state, roster))

    def test_unrelated_running_mirror_still_blocked(self):
        state, roster = fixture()
        roster["agents"].append({"id": "unrelated", "run_status": "running"})
        self.assertTrue(any("unrelated" in e for e in checker.validate(state, roster)))

    def test_normal_scoped_mode_only_after_explicit_marker_removal(self):
        state, roster = fixture()
        state["active_session"] = None
        roster["agents"][0]["run_status"] = "idle"
        self.assertTrue(checker.validate(state, roster))
        del state["active_sessions"][0]["legacy_exception_run_id"]
        self.assertEqual([], checker.validate(state, roster))

    def test_original_legacy_only_still_passes(self):
        state, roster = fixture()
        del state["active_sessions"]
        roster["agents"][1]["run_status"] = "blocked"
        self.assertEqual([], checker.validate(state, roster))

    def test_legacy_book_invalidates_exception_marker(self):
        for field, value in (("status", "paused"), ("owner_agent_id", "local-pdf-reader"),
                             ("claim", {"state": "released"})):
            with self.subTest(field=field):
                state, roster = fixture()
                state["books"][0][field] = value
                self.assertTrue(any("失效" in e for e in checker.validate(state, roster)))

    def test_basic_fields_and_malformed_extra_session_rejected(self):
        for field in ("slot", "started_at"):
            for value in ("", None, 123, []):
                with self.subTest(field=field, value=value):
                    state, roster = fixture()
                    state["active_sessions"][0][field] = value
                    self.assertTrue(checker.validate(state, roster))
        for value in (None, {}, False):
            with self.subTest(extra=value):
                state, roster = fixture()
                state["active_sessions"].append(value)
                self.assertTrue(checker.validate(state, roster))

    def test_overwriting_array_cannot_validate_running_windows(self):
        state, roster = fixture()
        # A stale writer deleting the array must not make Windows running legal.
        del state["active_sessions"]
        self.assertTrue(any("running 与 active_session" in e
                            for e in checker.validate(state, roster)))


if __name__ == "__main__":
    unittest.main()
