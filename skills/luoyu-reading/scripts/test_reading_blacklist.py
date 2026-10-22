import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts/filter-reading-candidates.py"
spec = importlib.util.spec_from_file_location("reading_blacklist", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class BlacklistTests(unittest.TestCase):
    def setUp(self):
        self.rules = json.loads((ROOT / "references/reading-blacklist.json").read_text(encoding="utf-8"))
        self.denied = self.rules["books"][0]

    def candidate(self, bid="history-book", title="历史与城市", matches=False):
        return {"book_id": bid, "title": title, "topic_assessments": {"career-related": {"matches": matches, "evidence": "测试用书目元数据，非正文"}}}

    def check(self, candidate):
        return module.filter_candidates([candidate], self.rules)

    def test_rules_valid(self):
        module.validate_blacklist(self.rules)

    def test_exact_id_denied_even_with_negative_topic(self):
        result = self.check(self.candidate(self.denied["book_id"], "不同文件名"))
        self.assertEqual(1, len(result["excluded"]))

    def test_normalized_title_denied_without_id(self):
        candidate = {"title": self.denied["title"].replace("？", "? ").replace("，", ", ")}
        self.assertEqual(1, len(self.check(candidate)["excluded"]))

    def test_different_author_same_title_needs_review(self):
        candidate = self.candidate(title=self.denied["title"])
        candidate["author"] = "另一位作者"
        self.assertEqual(1, len(self.check(candidate)["needs_review"]))

    def test_platform_id_matches_across_filename(self):
        self.rules["books"][0]["platform_ids"] = [{"platform": "weread", "platform_book_id": "1234"}]
        candidate = self.candidate()
        candidate.update(platform="weread", platform_book_id="1234")
        self.assertEqual(1, len(self.check(candidate)["excluded"]))

    def test_title_alias(self):
        self.rules["books"][0]["title_aliases"] = ["旧名"]
        self.assertEqual(1, len(self.check({"title": "旧名"})["excluded"]))

    def test_career_metadata_denied_even_when_title_has_no_signal(self):
        candidate = self.candidate(title="下一站在哪里")
        candidate["topics"] = [" Career "]
        self.assertEqual(1, len(self.check(candidate)["excluded"]))

    def test_semantic_assessment_denied(self):
        self.assertEqual(1, len(self.check(self.candidate(matches=True))["excluded"]))

    def test_missing_assessment_never_silently_passes(self):
        self.assertEqual(1, len(self.check({"book_id": "unknown", "title": "未知书"})["needs_review"]))

    def test_title_signal_alone_is_not_permanent_blacklisting(self):
        result = self.check({"title": "职业与文学"})
        self.assertEqual([], result["excluded"])
        self.assertEqual(1, len(result["needs_review"]))

    def test_noncareer_with_checked_metadata_passes(self):
        self.assertEqual(1, len(self.check(self.candidate())["not_blacklisted"]))

    def test_general_finance_not_blacklisted(self):
        candidate = self.candidate("finance", "现代金融的本质以及房价")
        self.assertEqual(1, len(self.check(candidate)["not_blacklisted"]))

    def test_skipped_candidates_are_not_permanently_denied(self):
        candidates = [self.candidate("76", "蒋介石为什么失掉大陆：1945——1949"), self.candidate("129", "从内斗的华夏到固化的中国")]
        result = module.filter_candidates(candidates, self.rules)
        self.assertEqual(2, len(result["not_blacklisted"]))
        self.assertEqual([self.denied["book_id"]], [b["book_id"] for b in self.rules["books"]])

    def test_pass_does_not_change_paused_or_owner(self):
        candidate = self.candidate()
        candidate.update(status="paused", owner_agent_id="original-owner", claim={"state": "held"})
        before = copy.deepcopy(candidate)
        result = self.check(candidate)
        self.assertEqual(before, candidate)
        self.assertEqual("paused", result["not_blacklisted"][0]["candidate"]["status"])

    def test_inputs_and_sort_order_preserved(self):
        candidates = [self.candidate("z"), self.candidate(self.denied["book_id"]), self.candidate("a")]
        before, rules_before = copy.deepcopy(candidates), copy.deepcopy(self.rules)
        result = module.filter_candidates(candidates, self.rules)
        self.assertEqual(["z", "a"], [v["candidate"]["book_id"] for v in result["not_blacklisted"]])
        self.assertEqual(before, candidates)
        self.assertEqual(rules_before, self.rules)

    def test_bad_rules_fail_closed(self):
        for field, value in (("schema_version", 2), ("schema_version", True), ("revision", 0), ("books", None), ("topic_rules", {})):
            with self.subTest(field=field, value=value):
                bad = copy.deepcopy(self.rules)
                bad[field] = value
                with self.assertRaises(ValueError):
                    module.filter_candidates([], bad)

    def test_rule_must_be_user_explicit(self):
        self.rules["books"][0]["basis"] = "inferred_from_skipped"
        with self.assertRaises(ValueError):
            module.filter_candidates([], self.rules)

    def test_bad_assessment_fails_closed(self):
        for assessment in ({"matches": False}, {"matches": "false", "evidence": "测试"}, {"matches": False, "evidence": ""}):
            candidate = self.candidate()
            candidate["topic_assessments"]["career-related"] = assessment
            with self.assertRaises(ValueError):
                self.check(candidate)

    def test_missing_identity_fails_closed(self):
        with self.assertRaises(ValueError):
            self.check({})

    def test_bad_candidate_shape_fails_closed(self):
        for candidate in (None, [], {"book_id": 123}, {"title": "测试", "topics": "career"}):
            with self.assertRaises(ValueError):
                self.check(candidate)

    def test_cli_exact_denied_exit_two(self):
        result = subprocess.run([sys.executable, str(SCRIPT), "--book-id", self.denied["book_id"]], capture_output=True, text=True)
        self.assertEqual(2, result.returncode)
        self.assertTrue(json.loads(result.stdout)["excluded"])

    def test_cli_unknown_id_exit_one(self):
        result = subprocess.run([sys.executable, str(SCRIPT), "--book-id", "does-not-exist"], capture_output=True, text=True)
        self.assertEqual(1, result.returncode)
        self.assertFalse(json.loads(result.stdout)["selection_allowed"])

    def test_cli_missing_config_exit_one(self):
        result = subprocess.run([sys.executable, str(SCRIPT), "--blacklist", str(ROOT / "missing-file.json")], capture_output=True, text=True)
        self.assertEqual(1, result.returncode)
        self.assertFalse(json.loads(result.stdout)["selection_allowed"])

    def test_cli_bad_json_and_unicode_path(self):
        with tempfile.TemporaryDirectory(prefix="阅读 黑名单 ") as temp:
            path = Path(temp) / "候选.json"
            path.write_text("{bad json", encoding="utf-8")
            result = subprocess.run([sys.executable, str(SCRIPT), "--candidates", str(path)], capture_output=True, text=True)
            self.assertEqual(1, result.returncode)
            path.write_text(json.dumps([self.candidate()], ensure_ascii=False), encoding="utf-8")
            result = subprocess.run([sys.executable, str(SCRIPT), "--candidates", str(path)], capture_output=True, text=True)
            self.assertEqual(0, result.returncode)
            self.assertEqual(1, len(json.loads(result.stdout)["not_blacklisted"]))


if __name__ == "__main__":
    unittest.main()
