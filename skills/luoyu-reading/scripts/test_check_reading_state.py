import copy
import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("check-reading-state.py")
spec = importlib.util.spec_from_file_location("check_reading_state", SCRIPT)
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


def fixture():
    agents = [
        {"id": "agent-a", "run_status": "idle"},
        {"id": "agent-b", "run_status": "idle"},
        {"id": "agent-c", "run_status": "idle"},
    ]
    books = []
    for i, (owner, platform) in enumerate((("agent-a", "weread"), ("agent-b", "local_pdf"), ("agent-c", "weread")), 1):
        books.append({"book_id": f"book-{i}", "platform": platform, "owner_agent_id": owner,
                      "status": "in_progress", "claim": {"state": "held"},
                      "resume_point": {"status": "needs-confirmation"}, "completion": None})
    return ({"books": books, "synthesis": {"unique_completed_count": 0, "batch_size": 3, "batches": []}}, {"agents": agents})


def session(run, agent, book, env, mode="weread_browser", resources=None):
    resources = resources if resources is not None else [f"disk:{book}"]
    if mode == "weread_browser" and checker.SHARED_WEREAD_RESOURCE not in resources:
        resources = resources + [checker.SHARED_WEREAD_RESOURCE]
    return {"run_id": run, "agent_id": agent, "book_id": book, "slot": "slot-1",
            "started_at": "2026-10-22T10:00:00+08:00", "environment_id": env,
            "reading_mode": mode, "resource_ids": resources}


class ActiveSessionTests(unittest.TestCase):
    def valid(self, mutate=None):
        state, roster = fixture()
        if mutate:
            mutate(state, roster)
        return checker.validate(state, roster)

    def test_parallel_sessions_allowed(self):
        def change(s, r):
            s["active_sessions"] = [
                session("run-a", "agent-a", "book-1", "env-a"),
                session("run-b", "agent-b", "book-2", "env-b", "local_pdf"),
            ]
            r["agents"][0]["run_status"] = "running"
            r["agents"][1]["run_status"] = "running"
        self.assertEqual([], self.valid(change))

    def test_shared_browser_conflicts_across_environments(self):
        def change(s, r):
            s["active_sessions"] = [
                session("a", "agent-a", "book-1", "env-a"),
                session("c", "agent-c", "book-3", "env-c"),
            ]
        self.assertTrue(any("resource_ids 与其他" in e for e in self.valid(change)))

    def test_malformed_book_id_and_null_claim_fail_safely(self):
        for bid in ([], {}, 1, None):
            with self.subTest(book_id=bid):
                item = session("r", "agent-a", "book-1", "env")
                item["book_id"] = bid
                self.assertTrue(self.valid(lambda s, r: s.update(active_sessions=[item])))
        def null_claim(s, r):
            s["books"][0]["claim"] = None
            s["active_sessions"] = [session("r", "agent-a", "book-1", "env")]
        self.assertTrue(self.valid(null_claim))

    def test_same_book_environment_resource_agent_or_run_rejected(self):
        variants = [
            (session("run-b", "agent-b", "book-1", "env-b", "other"), "book_id 重复"),
            (session("run-b", "agent-b", "book-2", "env-a", "other"), "environment_id 重复"),
            (session("run-b", "agent-b", "book-2", "env-b", "other", ["disk:book-1"]), "resource_ids 与其他"),
            (session("run-b", "agent-a", "book-2", "env-b", "other"), "agent_id 重复"),
            (session("run-a", "agent-b", "book-2", "env-b", "other"), "run_id 重复"),
        ]
        for second, expected in variants:
            with self.subTest(expected=expected):
                def change(s, r):
                    s["active_sessions"] = [session("run-a", "agent-a", "book-1", "env-a"), second]
                self.assertTrue(any(expected in e for e in self.valid(change)))

    def test_legacy_compatible_and_mixed_refused(self):
        def legacy(s, r):
            s["active_session"] = {"run_id": "old", "agent_id": "agent-a", "book_id": "book-1", "slot": "x", "started_at": "now"}
        self.assertEqual([], self.valid(legacy))
        def mixed(s, r):
            legacy(s, r)
            s["active_sessions"] = [session("new", "agent-b", "book-2", "env-b", "local_pdf")]
        self.assertTrue(any("不得同时使用" in e for e in self.valid(mixed)))

    def test_legacy_malformed_empty_objects_not_ignored(self):
        for value in ({}, False, ""):
            with self.subTest(value=value):
                self.assertTrue(any("active_session" in e for e in self.valid(lambda s, r: s.update(active_session=value))))

    def test_missing_scoped_field_and_null_array_errors(self):
        for value in (None, {}, [None], [{"run_id": "x", "resource_ids": [1]}]):
            with self.subTest(value=value):
                errors = self.valid(lambda s, r: s.update(active_sessions=value))
                self.assertTrue(errors)

    def test_owner_and_book_state_required(self):
        def wrong_owner(s, r):
            x = session("r", "agent-b", "book-1", "env")
            s["active_sessions"] = [x]
        self.assertTrue(any("owner/agent 不匹配" in e for e in self.valid(wrong_owner)))
        def wrong_status(s, r):
            s["books"][0]["status"] = "paused"
            s["active_sessions"] = [session("r", "agent-a", "book-1", "env")]
        self.assertTrue(any("held 且 in_progress" in e for e in self.valid(wrong_status)))

    def test_running_requires_exactly_one_valid_scoped_session(self):
        def running_without(s, r):
            r["agents"][0]["run_status"] = "running"
            s["active_sessions"] = []
        self.assertTrue(any("但无 active_session" in e for e in self.valid(running_without)))
        def independent_running(s, r):
            r["agents"][0]["run_status"] = "running"
            r["agents"][2]["run_status"] = "running"
            s["active_sessions"] = [session("r", "agent-a", "book-1", "env-a")]
        self.assertTrue(any("agent-c" in e for e in self.valid(independent_running)))
        def delayed_mirror(s, r):
            s["active_sessions"] = [session("r", "agent-a", "book-1", "env-a")]
        self.assertEqual([], self.valid(delayed_mirror))

    def test_mode_platform_and_shared_browser_resource_rules(self):
        cases = [
            (session("r", "agent-a", "book-1", "e", "weread_browser", ["local:x"]), "必须包含"),
            (session("r", "agent-a", "book-1", "e", "other"), "必须使用 weread_browser"),
            (session("r", "agent-b", "book-2", "e", "local_pdf", ["browser:weread-shared"]), "不得包含"),
            (session("r", "agent-a", "book-1", "e", "local_pdf", ["local:x"]), "不得用于 weread"),
            (session("r", "agent-c", "book-3", "e", "unknown"), "reading_mode 无效"),
        ]
        for item, expected in cases:
            with self.subTest(expected=expected):
                if expected == "必须包含":
                    item["resource_ids"] = ["local:x"]
                self.assertTrue(any(expected in e for e in self.valid(lambda s, r: s.update(active_sessions=[item]))))

    def test_resource_ids_duplicate_and_non_string_fail_safely(self):
        for resources in (["x", "x"], ["x", 1], [], "x"):
            with self.subTest(resources=resources):
                item = session("r", "agent-b", "book-2", "env", "local_pdf", resources if isinstance(resources, list) else [])
                item["resource_ids"] = resources
                errors = self.valid(lambda s, r: s.update(active_sessions=[item]))
                self.assertTrue(any("resource_ids" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
