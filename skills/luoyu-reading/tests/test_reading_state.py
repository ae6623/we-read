import copy
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("check_reading_state", ROOT / "scripts/check-reading-state.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ReadingStateTests(unittest.TestCase):
    def setUp(self):
        self.state = json.loads((ROOT / "references/book-registry.json").read_text(encoding="utf-8"))
        self.roster = json.loads((ROOT / "references/agent-roster.json").read_text(encoding="utf-8"))

    def check(self, mutate=None):
        state, roster = copy.deepcopy(self.state), copy.deepcopy(self.roster)
        if mutate:
            mutate(state, roster)
        return module.validate(state, roster)

    def test_initial_fixture_passes(self):
        self.assertEqual([], self.check())

    def test_duplicate_book_id(self):
        self.assertTrue(any("book_id 重复" in x for x in self.check(lambda s, r: s["books"].append(copy.deepcopy(s["books"][0])))))

    def test_unknown_owner(self):
        def change(s, r): s["books"][0]["owner_agent_id"] = "ghost"
        self.assertTrue(any("owner 有效" in x for x in self.check(change)))

    def test_same_owner_can_hold_multiple_books(self):
        def change(s, r):
            s["books"][1]["owner_agent_id"] = s["books"][0]["owner_agent_id"]
        self.assertEqual([], self.check(change))

    def test_queued_requires_null_owner_and_unclaimed(self):
        def change(s, r):
            s["books"][2].update(status="queued", owner_agent_id=None)
            s["books"][2]["claim"]["state"] = "held"
        self.assertTrue(any("queued 必须" in x for x in self.check(change)))

    def test_in_progress_requires_held_valid_owner(self):
        def change(s, r): s["books"][0]["claim"]["state"] = "unclaimed"
        self.assertTrue(any("必须 held" in x for x in self.check(change)))

    def test_completed_requires_released_claim(self):
        def change(s, r): s["books"][2]["claim"]["state"] = "held"
        self.assertTrue(any("completed 必须 released" in x for x in self.check(change)))

    def test_confirmed_without_position(self):
        def change(s, r):
            b=s["books"][0]; b["resume_point"].update(status="confirmed", chapter=None, page=None)
        self.assertTrue(any("不能只用 progress" in x for x in self.check(change)))

    def third(self):
        s=copy.deepcopy(self.state)
        template=copy.deepcopy(s["books"][2])
        for n in (2, 3):
            b=copy.deepcopy(template); b.update(book_id=f"third-{n}", title=f"Third {n}")
            b["completion"].update(event_id=f"event-{n}", sequence=n)
            s["books"].append(b)
        s["synthesis"]["unique_completed_count"] = 3
        return s

    def test_duplicate_completion(self):
        def change(s, r):
            b=copy.deepcopy(s["books"][2]); b.update(book_id="dup-event", title="dup")
            b["completion"]["event_id"]="completed-norway-night-2026-10-17"
            s["books"].append(b); s["synthesis"]["unique_completed_count"]=2
        self.assertTrue(any("event_id 重复" in x for x in self.check(change)))

    def test_rereading_retains_completion_without_counting_again(self):
        def change(s, r):
            book = s["books"][2]
            book.update(status="in_progress", owner_agent_id="wechat-reading-browser")
            book["claim"].update(state="held")
        self.assertEqual([], self.check(change))

    def test_wrong_count(self):
        self.assertTrue(any("完读计数不一致" in x for x in self.check(lambda s,r: s["synthesis"].update(unique_completed_count=9))))

    def test_missing_third_book_batch(self):
        s=self.third()
        self.assertTrue(any("批次数不正确" in x for x in module.validate(s, copy.deepcopy(self.roster))))

    def test_correct_third_book_batch(self):
        s=self.third(); s["synthesis"]["batches"]=[{"batch_id":"batch-001","book_ids":[b["book_id"] for b in sorted([b for b in s["books"] if b.get("completion")], key=lambda b:b["completion"]["sequence"])],"status":"pending","owner_agent_id":"wechat-reading-browser","visibility":"private"}]
        self.assertEqual([], module.validate(s, copy.deepcopy(self.roster)))

    def test_duplicate_batch(self):
        s=self.third(); batch={"batch_id":"batch-001","book_ids":[b["book_id"] for b in s["books"] if b.get("completion")],"status":"pending","owner_agent_id":"wechat-reading-browser","visibility":"private"}
        s["synthesis"]["batches"]=[copy.deepcopy(batch),copy.deepcopy(batch)]
        self.assertTrue(any("批次数不正确" in x or "批次 ID 重复" in x for x in module.validate(s, copy.deepcopy(self.roster))))

    def test_active_conflict(self):
        def change(s,r):
            s["active_session"]={"run_id":"r","agent_id":"wechat-reading-browser","book_id":"zhu-xiao-fang-zi-de-nv-ren","slot":"morning","started_at":"now"}
        self.assertTrue(any("owner/agent 不匹配" in x for x in self.check(change)))

    def test_active_session_requires_held_in_progress_book(self):
        def change(s, r):
            b=s["books"][0]; b.update(status="paused")
            s["active_session"]={"run_id":"r","agent_id":b["owner_agent_id"],"book_id":b["book_id"],"slot":"morning","started_at":"now"}
        self.assertTrue(any("active_session 必须对应" in x for x in self.check(change)))

    def test_running_roster_requires_active_session(self):
        def change(s, r):
            r["agents"][0]["run_status"]="running"
            s["active_session"]=None
        self.assertTrue(any("running agent 但无 active_session" in x for x in self.check(change)))


if __name__ == "__main__": unittest.main()
