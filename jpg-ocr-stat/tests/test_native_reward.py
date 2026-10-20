"""Guards commit 2e1a410 native fractional reward and complete CTRF evidence."""

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from test_score_accuracy import fixture_xlsx

VERIFIER = Path(__file__).resolve().parents[1] / "verifier"
sys.path.insert(0, str(VERIFIER))
from write_reward import validated_reward


class NativeReward(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="jpg-native-reward-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.rows = [["filename", "date", "total_amount"]] + [
            [f"synthetic_{i:02d}.jpg", "2000-01-01", "10.00"] for i in range(22)
        ]
        self.oracle = self.root / "oracle.xlsx"
        fixture_xlsx(self.oracle, self.rows)

    def native(self, actual_rows):
        actual = self.root / "actual.xlsx"
        if actual_rows is not None:
            fixture_xlsx(actual, actual_rows)
        accuracy = self.root / "accuracy.json"
        ctrf = self.root / "ctrf.json"
        reward = self.root / "reward.txt"
        env = dict(os.environ, JPG_OCR_ACTUAL_PATH=str(actual), JPG_OCR_ORACLE_PATH=str(self.oracle),
                   JPG_OCR_REPORT_PATH=str(accuracy), PYTEST_DISABLE_PLUGIN_AUTOLOAD="1")
        result = subprocess.run([
            sys.executable, "-m", "pytest", "-p", "ctrf.main",
            "--ctrf", str(ctrf), str(VERIFIER / "test_outputs.py"), "-q", "--tb=no",
            "--override-ini", "addopts=",
        ], cwd=self.root, env=env, capture_output=True, text=True)
        self.assertIn(result.returncode, (0, 1), result.stdout + result.stderr)
        self.assertTrue(ctrf.is_file(), result.stdout + result.stderr)
        write = subprocess.run([sys.executable, str(VERIFIER / "write_reward.py"),
                                "--ctrf", str(ctrf), "--accuracy", str(accuracy), "--reward", str(reward)],
                               capture_output=True, text=True)
        self.assertEqual(write.returncode, 0, write.stderr)
        return result.returncode, float(reward.read_text()), json.loads(ctrf.read_text()), json.loads(accuracy.read_text())

    def test_native_perfect_reward_is_one(self):
        code, reward, ctrf, _ = self.native(self.rows)
        self.assertEqual(code, 0)
        self.assertEqual(reward, 1)
        self.assertEqual(ctrf["results"]["summary"]["passed"], 44)

    def test_native_partial_failure_keeps_fractional_reward(self):
        self.rows[1][2] = "11.00"
        code, reward, ctrf, accuracy = self.native(self.rows)
        self.assertEqual(code, 1)
        self.assertEqual(reward, 43 / 44)
        self.assertEqual(accuracy["all_receipts"]["receipt_joint_correct"], 21)
        self.assertEqual(ctrf["results"]["summary"]["failed"], 1)

    def test_native_missing_delivery_is_completed_zero(self):
        code, reward, ctrf, _ = self.native(None)
        self.assertEqual(code, 1)
        self.assertEqual(reward, 0)
        self.assertEqual(ctrf["results"]["summary"]["failed"], 44)

    def test_incomplete_or_inconsistent_evidence_is_rejected(self):
        _, _, ctrf, accuracy = self.native(self.rows)
        mutations = [
            lambda x: x["results"]["tests"].pop(),
            lambda x: x["results"]["summary"].update(passed=43),
            lambda x: x["results"]["tests"][0].update(status="skipped"),
            lambda x: x["results"]["summary"].update(errors=1),
        ]
        for mutate in mutations:
            broken = copy.deepcopy(ctrf)
            mutate(broken)
            with self.subTest(mutation=mutations.index(mutate)), self.assertRaises(ValueError):
                validated_reward(broken, accuracy)
        broken = copy.deepcopy(accuracy)
        broken["field_feedback"][0]["date_correct"] = False
        with self.assertRaises(ValueError):
            validated_reward(ctrf, broken)

    def test_missing_or_malformed_ctrf_removes_stale_reward(self):
        reward = self.root / "reward.txt"
        ctrf = self.root / "ctrf.json"
        for content in (None, "not-json"):
            reward.write_text("1\n")
            if content is not None:
                ctrf.write_text(content)
            result = subprocess.run([sys.executable, str(VERIFIER / "write_reward.py"),
                                     "--ctrf", str(ctrf), "--accuracy", str(self.root / "accuracy.json"),
                                     "--reward", str(reward)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(reward.exists())


if __name__ == "__main__":
    unittest.main()
