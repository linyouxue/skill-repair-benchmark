#!/usr/bin/env python3
"""Unit tests for high-priority repair knobs (no network)."""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters.common.bounded_edit import (  # noqa: E402
    BoundedEditValidationError,
    apply_edits_local,
    propose_bounded_edits,
)
from adapters.common.method_profile import method_profile  # noqa: E402
from adapters.common.repair_loop import (  # noqa: E402
    diagnosis_sample_count,
    edit_budget_l,
    pick_loose_diagnosis,
    repair_rounds_r,
    smoke_mode,
)


class ApplyEditsTests(unittest.TestCase):
    def test_replace_append_delete(self) -> None:
        skill = "# Title\n\n## A\nold line\n\n## B\nkeep\n"
        new, reports = apply_edits_local(
            skill,
            [
                {"op": "replace", "target": "old line", "content": "new line"},
                {"op": "append", "content": "tail note"},
                {"op": "delete", "target": "## B\nkeep\n"},
            ],
        )
        self.assertIn("new line", new)
        self.assertNotIn("old line", new)
        self.assertIn("tail note", new)
        self.assertNotIn("## B", new)
        statuses = [r["status"] for r in reports]
        self.assertTrue(any(s.startswith("applied_") for s in statuses))

    def test_missing_content_never_deletes_or_mutates_skill(self) -> None:
        """Guards the strict content contract against silent replacement deletion."""
        skill = "# Title\n\nold line\n"
        with self.assertRaises(BoundedEditValidationError):
            apply_edits_local(skill, [{"op": "replace", "target": "old line"}])
        self.assertEqual(skill, "# Title\n\nold line\n")

    def test_retries_replacement_alias_then_accepts_content(self) -> None:
        """Guards the repair retry path for models that emit replacement/value."""
        replies = iter(
            [
                '{"reasoning":"x","edits":[{"op":"replace","target":"old","replacement":"new"}]}',
                '{"reasoning":"x","edits":[{"op":"replace","target":"old","content":"new"}]}',
            ]
        )

        def chat_fn(*, system: str, user: str):
            _ = system, user
            return next(replies), {"total_tokens": 1}

        edits, _reasoning, _usage, _raw, attempts = propose_bounded_edits(
            chat_fn=chat_fn,
            extract_json_fn=lambda text: __import__("json").loads(text),
            fallback_extract_fn=lambda _text: None,
            skill_content="# Skill\nold\n",
            skill_path="demo/SKILL.md",
            task_id="demo",
            diagnosis_item={},
            task_context="ctx",
            baseline_source_type="failure",
            baseline_context="evidence",
            budget_l=2,
        )
        self.assertEqual(edits[0]["content"], "new")
        self.assertEqual(len(attempts), 2)
        self.assertFalse(attempts[0]["accepted"])
        self.assertTrue(attempts[1]["accepted"])
        self.assertIn("replacement", attempts[0]["validation_errors"][0])

    def test_retries_sequential_target_conflict(self) -> None:
        """Reject proposals whose later anchors are destroyed by earlier edits."""
        replies = iter(
            [
                (
                    '{"reasoning":"x","edits":['
                    '{"op":"replace","target":"old","content":"new"},'
                    '{"op":"insert_after","target":"old","content":"note"}]}'
                ),
                (
                    '{"reasoning":"x","edits":['
                    '{"op":"insert_after","target":"old","content":"note"},'
                    '{"op":"replace","target":"old","content":"new"}]}'
                ),
            ]
        )

        def chat_fn(*, system: str, user: str):
            _ = system, user
            return next(replies), {"total_tokens": 1}

        edits, _reasoning, _usage, _raw, attempts = propose_bounded_edits(
            chat_fn=chat_fn,
            extract_json_fn=lambda text: __import__("json").loads(text),
            fallback_extract_fn=lambda _text: None,
            skill_content="# Skill\nold\n",
            skill_path="demo/SKILL.md",
            task_id="demo",
            diagnosis_item={},
            task_context="ctx",
            baseline_source_type="failure",
            baseline_context="evidence",
            budget_l=2,
        )
        self.assertEqual(edits[0]["op"], "insert_after")
        self.assertEqual(len(attempts), 2)
        self.assertFalse(attempts[0]["accepted"])
        self.assertIn("application failed", attempts[0]["validation_errors"][0])
        self.assertTrue(attempts[1]["accepted"])


class MethodProfileTests(unittest.TestCase):
    def test_skillopt_defaults_to_patch_merge(self) -> None:
        for key in list(os.environ):
            if key.startswith("SKILLOPT_EVA_"):
                os.environ.pop(key, None)
        p = method_profile("skillopt")
        self.assertEqual(p["update_mode"], "patch")
        self.assertTrue(p["merge_samples"])
        self.assertEqual(p["repair_rounds_bonus"], 0)

    def test_lite_defaults_to_rewrite_loose(self) -> None:
        for key in list(os.environ):
            if key.startswith("SKILLOPT_EVA_"):
                os.environ.pop(key, None)
        p = method_profile("skillopt-lite")
        self.assertEqual(p["update_mode"], "rewrite")
        self.assertFalse(p["merge_samples"])
        self.assertGreaterEqual(p["repair_rounds_bonus"], 1)


class SmokeModeTests(unittest.TestCase):
    def tearDown(self) -> None:
        os.environ.pop("SKILLOPT_EVA_SMOKE", None)
        os.environ.pop("SKILLOPT_EVA_DIAGNOSIS_N", None)
        os.environ.pop("SKILLOPT_EVA_REPAIR_ROUNDS_R", None)

    def test_smoke_forces_n_and_r(self) -> None:
        os.environ["SKILLOPT_EVA_SMOKE"] = "1"
        os.environ["SKILLOPT_EVA_DIAGNOSIS_N"] = "9"
        os.environ["SKILLOPT_EVA_REPAIR_ROUNDS_R"] = "9"
        self.assertTrue(smoke_mode())
        self.assertEqual(diagnosis_sample_count(), 1)
        self.assertEqual(repair_rounds_r(bonus=3), 1)
        self.assertGreaterEqual(edit_budget_l(), 1)


class LoosePickTests(unittest.TestCase):
    def test_prefers_non_fallback(self) -> None:
        samples = [
            {"fallback_used": True, "diagnosed_skills": [{"path": "a", "confidence": "high"}]},
            {
                "fallback_used": False,
                "diagnosed_skills": [
                    {"path": "b", "confidence": "high"},
                    {"path": "c", "confidence": "low"},
                ],
            },
        ]
        chosen = pick_loose_diagnosis(samples, budget_l=1)
        self.assertTrue(chosen.get("loose_pick"))
        self.assertEqual(len(chosen["diagnosed_skills"]), 1)
        self.assertEqual(chosen["diagnosed_skills"][0]["path"], "b")


class EvidenceBundleTests(unittest.TestCase):
    def test_accumulates_labeled_failures(self) -> None:
        import tempfile
        import json
        from adapters.common.rewrite_engine import load_evidence_bundle

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            b = root / "baseline.json"
            r1 = root / "round1.json"
            b.write_text(json.dumps({"task_passed": False, "summary": "baseline fail AAA"}), encoding="utf-8")
            r1.write_text(json.dumps({"task_passed": False, "summary": "round1 fail BBB"}), encoding="utf-8")
            source, ctx = load_evidence_bundle(
                [("baseline", b), ("round_1_gate", r1)],
                total_chars=8000,
            )
            self.assertEqual(source, "failure")
            self.assertIn("Evidence: baseline", ctx)
            self.assertIn("Evidence: round_1_gate", ctx)
            self.assertIn("AAA", ctx)
            self.assertIn("BBB", ctx)
            self.assertIn("Accumulated execution evidence (2", ctx)

    def test_includes_actual_trajectory_and_verifier_details(self) -> None:
        """Guards diagnosis evidence against status-only benchmark summaries."""
        import json
        import tempfile
        from adapters.common.rewrite_engine import load_evidence_bundle_detailed

        experiments = ROOT / "experiments"
        experiments.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=experiments) as td:
            run = Path(td)
            result = run / "baseline" / "original-skill" / "demo" / "benchmark_result.json"
            job = run / "jobs" / "baseline-original-skill" / "demo-rollout"
            result.parent.mkdir(parents=True)
            (job / "trajectory").mkdir(parents=True)
            (job / "verifier").mkdir(parents=True)
            result.write_text(
                json.dumps(
                    {
                        "task_passed": False,
                        "method_id": "baseline-original-skill",
                        "rollout_id": "demo-rollout",
                    }
                ),
                encoding="utf-8",
            )
            (job / "trajectory" / "llm_trajectory.jsonl").write_text(
                '{"tool":"python","output":"actual agent mistake XYZ"}\n', encoding="utf-8"
            )
            (job / "verifier" / "ctrf.json").write_text(
                json.dumps({"tests": [{"name": "check-output", "status": "failed"}]}),
                encoding="utf-8",
            )
            (job / "verifier" / "test-stdout.txt").write_text(
                "expected 4 but got 3", encoding="utf-8"
            )
            source, ctx, manifest = load_evidence_bundle_detailed([("baseline", result)])
            self.assertEqual(source, "failure")
            self.assertIn("actual agent mistake XYZ", ctx)
            self.assertIn("expected 4 but got 3", ctx)
            roles = {item["role"] for item in manifest["entries"][0]["sources"]}
            self.assertIn("agent_llm_trajectory", roles)
            self.assertIn("verifier_structured_checks", roles)


class GateHealthTests(unittest.TestCase):
    def test_infrastructure_timeout_is_invalid_not_a_skill_rejection(self) -> None:
        """Guards invalid infrastructure attempts from entering Skill selection."""
        from scripts.run_method import _gate_invalid_reason

        result = {
            "task_passed": None,
            "execution_ok": False,
            "comparable": False,
            "reward": None,
            "termination_reason": "infrastructure_error",
            "error_category": "timeout",
        }
        self.assertEqual(
            _gate_invalid_reason(result),
            "termination_reason:infrastructure_error",
        )

    def test_scored_agent_failure_is_a_valid_gate(self) -> None:
        """Guards healthy scored failures so they remain valid Skill evidence."""
        from scripts.run_method import _gate_invalid_reason

        result = {
            "task_passed": False,
            "execution_ok": True,
            "comparable": True,
            "reward": 0.0,
            "termination_reason": "completed",
        }
        self.assertIsNone(_gate_invalid_reason(result))


if __name__ == "__main__":
    raise SystemExit(unittest.main())
