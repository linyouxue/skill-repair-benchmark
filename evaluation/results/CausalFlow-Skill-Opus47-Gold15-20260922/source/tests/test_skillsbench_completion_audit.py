from __future__ import annotations

import unittest

from repro_wrappers.subset25.audit_skillsbench_trajectory_completion import (
    fisher_exact_two_sided,
    has_unexecuted_continuation_intent,
    reward_class,
    summarize_records,
)


class SkillsBenchCompletionAuditTests(unittest.TestCase):
    def test_detects_unexecuted_future_action_language(self):
        self.assertTrue(has_unexecuted_continuation_intent("I’ll inspect the file."))
        self.assertTrue(has_unexecuted_continuation_intent("Next I'll run tests."))
        self.assertFalse(has_unexecuted_continuation_intent("The task is complete."))

    def test_reward_classes(self):
        self.assertEqual(reward_class(0.0), "zero")
        self.assertEqual(reward_class(0.55), "partial")
        self.assertEqual(reward_class(1.0), "full")

    def test_short_zero_no_write_is_summarized_without_becoming_a_gate(self):
        records = [
            {
                "task": "short-failure",
                "reward_class": "zero",
                "command_count": 1,
                "recorded_write_count": 0,
                "unexecuted_continuation_intent": True,
            },
            {
                "task": "successful-unobserved-write",
                "reward_class": "full",
                "command_count": 3,
                "recorded_write_count": 0,
                "unexecuted_continuation_intent": False,
            },
        ]

        summary = summarize_records(records)

        self.assertEqual(summary["short_zero_no_write_tasks"], ["short-failure"])
        self.assertEqual(summary["by_reward_class"]["full"]["no_recorded_writes"], 1)
        self.assertEqual(summary["unexecuted_continuation_intent_count"], 1)

    def test_one_command_success_association_uses_two_sided_fisher_exact(self):
        p_value = fisher_exact_two_sided(0, 9, 8, 7)

        self.assertAlmostEqual(p_value, 0.009495955652908136)


if __name__ == "__main__":
    unittest.main()
