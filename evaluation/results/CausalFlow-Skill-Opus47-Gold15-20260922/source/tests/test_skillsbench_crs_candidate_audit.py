from __future__ import annotations

import unittest

from repro_wrappers.subset25.audit_skillsbench_crs_candidates import (
    aggregate,
    audit_result,
)


class SkillsBenchCrsCandidateAuditTests(unittest.TestCase):
    def test_candidate_and_branch_classes_are_counted_separately(self):
        payload = {
            "task": "demo",
            "baseline_official_reward": 0.5,
            "causal_attribution": {
                "intervention_results": {
                    "0": {
                        "original_step": {"tool_args": {"command": "old"}},
                        "attempts": [
                            {"intervened_step": {"tool_args": {"command": "old"}}},
                            {"intervened_step": {"tool_args": {"command": "new"}}},
                            {"intervened_step": {"tool_args": {"mode": "text"}}},
                            {"reason": "generation failed"},
                        ],
                    }
                }
            },
            "reexecution_evaluations": [
                {"phase": "crs_attribution", "reward": 0.5},
                {"phase": "crs_attribution", "reward": 0.75},
            ],
        }

        record = audit_result(payload, "demo.json")

        self.assertEqual(record["proposals"], 4)
        self.assertEqual(record["no_op_proposals"], 1)
        self.assertEqual(record["changed_proposals"], 1)
        self.assertEqual(record["missing_command_proposals"], 1)
        self.assertEqual(record["generation_failures"], 1)
        self.assertEqual(record["executed_branches"], 2)
        self.assertEqual(record["reward_same"], 1)
        self.assertEqual(record["reward_higher"], 1)
        self.assertEqual(aggregate([record])["proposals"], 4)


if __name__ == "__main__":
    unittest.main()
