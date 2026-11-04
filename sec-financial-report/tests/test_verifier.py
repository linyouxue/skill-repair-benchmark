import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "verifier"))
from score_accuracy import load_reference, q1_correct, score

ANSWER = {"q1_answer": 100000, "q2_answer": 75,
          "q3_answer": ["000000001", "000000002", "000000003", "000000004", "000000005"],
          "q4_answer": ["Alpha LLC", "Beta Inc", "Gamma LP"]}


class VerifierTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.ref = {"dataset_version": "fixture", "scoring_version": "sec-answer-accuracy-v1", "layout": "single",
                    "cases": {"original": copy.deepcopy(ANSWER)}, "expected_answer_items": 10}

    def score(self, value, ref=None):
        path = self.base / "answers.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        return score(path, ref or self.ref)

    def test_all_correct_and_q4_case_insensitive(self):
        answer = copy.deepcopy(ANSWER)
        answer["q4_answer"] = [s.upper() for s in answer["q4_answer"]]
        report = self.score(answer)
        self.assertEqual(report["accuracy"], 1)
        self.assertTrue(report["task_passed"])

    def test_one_wrong_slot_and_rank_order(self):
        answer = copy.deepcopy(ANSWER)
        answer["q3_answer"][2] = "999999999"
        self.assertEqual(self.score(answer)["accuracy"], 0.9)
        answer["q3_answer"] = list(reversed(ANSWER["q3_answer"]))
        self.assertEqual(self.score(answer)["correct_items"], 6)

    def test_q1_original_float_predicate(self):
        for value in [100000, 100090, 100100, 100110, 99900, 99890]:
            self.assertEqual(q1_correct(value, ANSWER["q1_answer"]), abs(value / ANSWER["q1_answer"] - 1) < 0.001)
        self.assertFalse(q1_correct("100000", 100000))
        self.assertFalse(q1_correct(float("nan"), 100000))
        self.assertFalse(q1_correct(float("inf"), 100000))

    def test_missing_or_invalid_output_zero(self):
        path = self.base / "missing.json"
        self.assertEqual(score(path, self.ref)["accuracy"], 0)
        path.write_text("{broken", encoding="utf-8")
        self.assertEqual(score(path, self.ref)["accuracy"], 0)
        self.assertEqual(self.score({})["accuracy"], 0)
        self.assertEqual(self.score([])["accuracy"], 0)

    def test_missing_and_extra_ranked_entries(self):
        answer = copy.deepcopy(ANSWER)
        answer["q3_answer"].pop()
        self.assertEqual(self.score(answer)["accuracy"], 0.9)
        answer = copy.deepcopy(ANSWER)
        answer["q4_answer"].append("Extra")
        report = self.score(answer)
        self.assertEqual(report["accuracy"], 10 / 11)
        self.assertFalse(report["strict_success"])

    def test_q4_no_whitespace_normalization(self):
        answer = copy.deepcopy(ANSWER)
        answer["q4_answer"][0] = " Alpha LLC "
        self.assertEqual(self.score(answer)["accuracy"], 0.9)

    def test_batch_missing_case_and_extra_case(self):
        ref = copy.deepcopy(self.ref)
        ref.update(layout="cases", cases={"case_001": ANSWER, "case_002": ANSWER}, expected_answer_items=20)
        self.assertEqual(self.score({"case_001": ANSWER}, ref)["accuracy"], 0.5)
        actual = {"case_001": ANSWER, "case_002": ANSWER, "unknown": ANSWER}
        self.assertEqual(self.score(actual, ref)["accuracy"], 20 / 21)

    def test_reference_failure_is_not_candidate_zero(self):
        with self.assertRaises(FileNotFoundError):
            load_reference(self.base / "no-reference.json")

    def test_native_continuous_reward_and_missing_output(self):
        ref = self.base / "reference.json"
        ref.write_text(json.dumps(self.ref), encoding="utf-8")
        actual = self.base / "actual.json"
        log = self.base / "logs"
        command = [sys.executable, "-B", str(ROOT / "verifier/native_grade.py"), "--reference", str(ref),
                   "--actual", str(actual), "--log-dir", str(log)]
        subprocess.run(command, check=True, capture_output=True)
        self.assertEqual(float((log / "reward.txt").read_text()), 0)
        answer = copy.deepcopy(ANSWER)
        answer["q2_answer"] = -1
        actual.write_text(json.dumps(answer), encoding="utf-8")
        subprocess.run(command, check=True, capture_output=True)
        self.assertEqual(float((log / "reward.txt").read_text()), 0.9)
        report = json.loads((log / "ctrf.json").read_text())
        self.assertEqual(report["results"]["summary"]["passed"], 9)
        self.assertNotIn("100000", (log / "accuracy.json").read_text())


if __name__ == "__main__":
    unittest.main()
