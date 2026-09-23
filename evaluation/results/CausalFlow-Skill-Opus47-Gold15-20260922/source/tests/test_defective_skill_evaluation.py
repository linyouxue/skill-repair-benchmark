from __future__ import annotations

import argparse
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from repro_wrappers.defects.construct_defective_skill_bundles import apply_mutations
from repro_wrappers.defects.run_defective_skill_matrix import (
    attempt_is_comparable,
    command_for,
)
from repro_wrappers.run_unified_skillsbench_task import (
    configure_verifier_proxy,
    docker_install_proxy_url,
    normalize_host_environment,
)
from repro_wrappers.defects.score_defective_skill_evaluation import (
    localization_metrics,
    repaired_bundle_metrics,
)
from repro_wrappers.skillsbench_deployed_skills import resolve_deployed_skills
from repro_wrappers.defects.summarize_defective_skill_matrix import trajectory_usage


class DefectiveSkillMatrixTests(unittest.TestCase):
    def test_noncomparable_verifier_timeout_remains_retryable(self):
        self.assertFalse(
            attempt_is_comparable(
                {
                    "comparable": False,
                    "termination_reason": "end_turn",
                    "verifier_error_category": "verifier_timeout",
                }
            )
        )
        self.assertTrue(attempt_is_comparable({"comparable": True}))

    def test_command_preserves_virtualenv_python_symlink(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            venv_python = root / ".venv" / "bin" / "python"
            venv_python.parent.mkdir(parents=True)
            base_python = root / "python3.12"
            base_python.write_text("", encoding="utf-8")
            venv_python.symlink_to(base_python)
            args = argparse.Namespace(
                executor_python=venv_python,
                jobs_root=root / "jobs",
                model="openrouter/openai/gpt-5.2",
                reasoning_effort="",
            )
            run = {
                "task_id": "task-a",
                "rollout_id": "run-a",
                "condition": "original-skill",
                "arm": "clean",
                "skill_bundle": None,
            }

            command = command_for(run, args)

            self.assertEqual(command[0], str(venv_python.absolute()))
            self.assertNotEqual(command[0], str(venv_python.resolve()))

    def test_host_normalization_uses_bundled_litellm_cost_map(self):
        with patch.dict(
            "os.environ",
            {"DEBUG": "release", "ALL_PROXY": "socks5://127.0.0.1:1080"},
            clear=True,
        ):
            normalize_host_environment()

            self.assertNotIn("DEBUG", __import__("os").environ)
            self.assertNotIn("ALL_PROXY", __import__("os").environ)
            self.assertEqual(
                __import__("os").environ["LITELLM_LOCAL_MODEL_COST_MAP"], "True"
            )

    def test_loopback_proxy_is_translated_for_docker_installer(self):
        self.assertEqual(
            docker_install_proxy_url("http://127.0.0.1:7897"),
            "http://host.docker.internal:7897",
        )
        self.assertIsNone(docker_install_proxy_url("socks5://127.0.0.1:7897"))
        self.assertIsNone(docker_install_proxy_url("http://user:pass@localhost:7897"))

    def test_explicit_verifier_proxy_uses_docker_host_bridge(self):
        with patch.dict(
            "os.environ", {"HTTPS_PROXY": "http://127.0.0.1:7897"}, clear=True
        ):
            self.assertTrue(configure_verifier_proxy("explicit"))
            env = __import__("os").environ
            self.assertEqual(
                env["BENCHMARK_EXECUTOR_VERIFIER_HTTPS_PROXY"],
                "http://host.docker.internal:7897",
            )
            self.assertEqual(
                env["BENCHMARK_EXECUTOR_VERIFIER_HTTP_PROXY"],
                "http://host.docker.internal:7897",
            )

    def test_recorded_skill_snapshot_wins_over_task_original(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            run_dir = root / "run"
            task_dir = root / "task"
            snapshot = run_dir / "inputs" / "skills" / "target"
            original = task_dir / "environment" / "skills" / "target"
            snapshot.mkdir(parents=True)
            original.mkdir(parents=True)
            (snapshot / "SKILL.md").write_text("defective\n", encoding="utf-8")
            (original / "SKILL.md").write_text("original\n", encoding="utf-8")

            selected, source = resolve_deployed_skills(run_dir, task_dir)

            self.assertEqual(selected, snapshot.parent.resolve())
            self.assertEqual(source, "recorded_rollout_snapshot")

    def test_trajectory_usage_recovers_tokens_from_provider_responses(self):
        with tempfile.TemporaryDirectory() as raw_root:
            path = Path(raw_root) / "llm_trajectory.jsonl"
            rows = [
                {"response": {"body": {"usage": {"total_tokens": 12, "cost": 0.1}}}},
                {"response": {"body": {"usage": {"total_tokens": 8, "cost": 0.2}}}},
            ]
            path.write_text(
                "\n".join(__import__("json").dumps(row) for row in rows) + "\n",
                encoding="utf-8",
            )

            usage = trajectory_usage(path)

            self.assertEqual(usage["provider_requests_with_usage"], 2)
            self.assertEqual(usage["total_tokens"], 20)
            self.assertAlmostEqual(usage["cost_usd"], 0.3)


class DefectiveSkillConstructionTests(unittest.TestCase):
    def test_exact_replacement_records_every_original_line(self):
        original = "first\nvalue <= other\nmiddle\nvalue <= other\n"
        defective, locations = apply_mutations(
            original,
            [
                {
                    "operation": "replace_exact",
                    "before": "value <= other",
                    "after": "value >= other",
                    "expected_occurrences": 2,
                }
            ],
        )

        self.assertEqual(defective.count("value >= other"), 2)
        self.assertEqual(
            locations[0]["original_spans"],
            [
                {"start_line": 2, "end_line": 2},
                {"start_line": 4, "end_line": 4},
            ],
        )

    def test_exact_replacement_rejects_source_drift(self):
        with self.assertRaisesRegex(RuntimeError, "expected 1 occurrence"):
            apply_mutations(
                "already changed\n",
                [
                    {
                        "operation": "replace_exact",
                        "before": "original text",
                        "after": "defective text",
                        "expected_occurrences": 1,
                    }
                ],
            )


class DefectiveSkillScoringTests(unittest.TestCase):
    def ground_truth(self):
        return {
            "target_skill": "example-skill",
            "target_file": "example-skill/SKILL.md",
            "defect_type": "logic_error",
            "annotation": {
                "locations": [
                    {
                        "original_spans": [
                            {"start_line": 10, "end_line": 12},
                            {"start_line": 30, "end_line": 30},
                        ]
                    }
                ]
            },
        }

    def test_localization_requires_joint_skill_file_type_and_line_hit(self):
        diagnosis = {
            "predictions": [
                {
                    "skill": "example-skill",
                    "file": "example-skill/SKILL.md",
                    "defect_type": "logic_error",
                    "start_line": 11,
                    "end_line": 11,
                }
            ]
        }

        metrics = localization_metrics(self.ground_truth(), diagnosis)

        self.assertTrue(metrics["top1"]["joint"])
        self.assertTrue(metrics["topk"]["joint"])

    def test_repair_integrity_detects_off_target_changes(self):
        with tempfile.TemporaryDirectory() as raw_root:
            bundle = Path(raw_root)
            skill = bundle / "example-skill"
            other = bundle / "other-skill"
            skill.mkdir()
            other.mkdir()
            (skill / "SKILL.md").write_text("repaired\n", encoding="utf-8")
            (other / "SKILL.md").write_text("changed\n", encoding="utf-8")

            def digest(text):
                import hashlib

                return hashlib.sha256(text.encode()).hexdigest()

            ground_truth = self.ground_truth() | {
                "integrity": {
                    "original_bundle_manifest": {
                        "example-skill/SKILL.md": digest("repaired\n"),
                        "other-skill/SKILL.md": digest("original\n"),
                    },
                    "defective_bundle_manifest": {
                        "example-skill/SKILL.md": digest("defective\n"),
                        "other-skill/SKILL.md": digest("original\n"),
                    },
                }
            }

            metrics = repaired_bundle_metrics(ground_truth, bundle)

            self.assertTrue(metrics["target_file_restored"])
            self.assertFalse(metrics["exact_original_bundle_restored"])
            self.assertEqual(
                metrics["off_target_changes_from_original"],
                ["other-skill/SKILL.md"],
            )


if __name__ == "__main__":
    unittest.main()
