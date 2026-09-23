from __future__ import annotations

import unittest

from replay_graph import (
    ConservativeGraphBuilder,
    FullReplayOracle,
    ReplayIntervention,
    ReplayStatus,
    SelectiveReplayScheduler,
)
from replay_graph.builder import tool_output_resource_id
from math_reexecutor import MathReexecutor
from trace_logger import TraceLogger


def call(step_id, expression, *, reads=()):
    return {
        "step_id": step_id,
        "step_type": "tool_call",
        "dependencies": [],
        "tool_name": "calculator",
        "tool_args": {"expression": expression},
        "resource_reads": list(reads),
    }


def response(step_id, call_id, value):
    return {
        "step_id": step_id,
        "step_type": "tool_response",
        "dependencies": [call_id],
        "tool_name": "calculator",
        "tool_call_result": True,
        "tool_output": str(value),
        "resource_writes": [tool_output_resource_id(step_id)],
    }


def final(step_id, value, *, reads=()):
    return {
        "step_id": step_id,
        "step_type": "final_answer",
        "dependencies": [],
        "text": str(value),
        "resource_reads": list(reads),
    }


class ReplayGraphTests(unittest.TestCase):
    def setUp(self):
        self.builder = ConservativeGraphBuilder()
        self.oracle = FullReplayOracle()
        self.scheduler = SelectiveReplayScheduler(self.oracle)

    def test_equal_values_keep_distinct_producer_identity(self):
        first_eight = tool_output_resource_id(1)
        second_eight = tool_output_resource_id(3)
        nine = tool_output_resource_id(5)
        steps = [
            call(0, "4 + 4"),
            response(1, 0, 8),
            call(2, "10 - 2"),
            response(3, 2, 8),
            call(4, "8 + 1", reads=[second_eight]),
            response(5, 4, 9),
            final(6, 9, reads=[nine]),
        ]
        graph = self.builder.build(steps)

        binding = graph.bindings_for(4)[0]
        self.assertEqual(binding.resolved_resource_id, second_eight)
        self.assertNotIn(first_eight, binding.candidate_resource_ids)

        comparison = self.scheduler.replay(
            steps,
            ReplayIntervention(0, {"expression": "4 + 5"}),
            graph=graph,
        )
        self.assertTrue(comparison.agreement)
        self.assertEqual(comparison.full.final_answer, "9")
        self.assertEqual(comparison.selective.executed_step_ids, [0])
        self.assertEqual(comparison.full.executed_step_ids, [0, 2, 4])
        self.assertEqual(comparison.selective.changed_resource_ids, [first_eight])

    def test_unresolved_equal_values_require_fallback_instead_of_guessing(self):
        steps = [
            call(0, "4 + 4"),
            response(1, 0, 8),
            call(2, "10 - 2"),
            response(3, 2, 8),
            call(4, "8 + 1"),
            response(5, 4, 9),
            final(6, 9),
        ]
        graph = self.builder.build(steps)
        binding = graph.bindings_for(4)[0]
        self.assertTrue(binding.ambiguous)

        result = self.oracle.replay(
            steps,
            ReplayIntervention(0, {"expression": "4 + 5"}),
            graph=graph,
        )
        self.assertEqual(result.status, ReplayStatus.FALLBACK_REQUIRED)
        self.assertEqual(result.unresolved_bindings[0]["consumer_step_id"], 4)

    def test_full_and_selective_replay_match_on_explicit_chain(self):
        eight = tool_output_resource_id(1)
        sixteen = tool_output_resource_id(3)
        steps = [
            call(0, "2 + 6"),
            response(1, 0, 8),
            call(2, "8 * 2", reads=[eight]),
            response(3, 2, 16),
            final(4, 16, reads=[sixteen]),
        ]
        comparison = self.scheduler.replay(
            steps,
            ReplayIntervention(0, {"expression": "3 + 6"}),
        )
        self.assertTrue(comparison.agreement)
        self.assertEqual(comparison.selective.final_answer, "18")
        self.assertEqual(comparison.full.final_answer, "18")

    def test_change_pruning_stops_after_unchanged_output(self):
        two = tool_output_resource_id(1)
        zero = tool_output_resource_id(3)
        five = tool_output_resource_id(5)
        steps = [
            call(0, "1 + 1"),
            response(1, 0, 2),
            call(2, "2 * 0", reads=[two]),
            response(3, 2, 0),
            call(4, "0 + 5", reads=[zero]),
            response(5, 4, 5),
            final(6, 5, reads=[five]),
        ]
        comparison = self.scheduler.replay(
            steps,
            ReplayIntervention(0, {"expression": "1 + 2"}),
        )
        self.assertTrue(comparison.agreement)
        self.assertEqual(comparison.selective.executed_step_ids, [0, 2])
        self.assertEqual(comparison.full.executed_step_ids, [0, 2, 4])
        self.assertAlmostEqual(comparison.replayed_call_reduction, 1 / 3)

    def test_missed_edge_is_detected_and_returns_full_replay(self):
        eight = tool_output_resource_id(1)
        sixteen = tool_output_resource_id(3)
        steps = [
            call(0, "2 + 6"),
            response(1, 0, 8),
            call(2, "8 * 2", reads=[eight]),
            response(3, 2, 16),
            final(4, 16, reads=[sixteen]),
        ]
        graph = self.builder.build(steps)
        graph.edges = [
            edge
            for edge in graph.edges
            if not (edge.source == eight and edge.target == "step:2")
        ]

        comparison = self.scheduler.replay(
            steps,
            ReplayIntervention(0, {"expression": "3 + 6"}),
            graph=graph,
        )
        self.assertFalse(comparison.agreement)
        self.assertTrue(comparison.returned.fallback_used)
        self.assertEqual(comparison.returned.mode, "full")
        self.assertEqual(comparison.returned.final_answer, "18")

    def test_trace_logger_emits_versioned_tool_resource(self):
        trace = TraceLogger("question", "2")
        call_id = trace.log_tool_call("calculator", {"expression": "1 + 1"})
        response_id = trace.log_tool_response("calculator", [call_id], True, "2")
        payload = trace.to_dict()
        self.assertEqual(
            payload["steps"][response_id]["resource_writes"],
            [tool_output_resource_id(response_id)],
        )

    def test_replay_evaluator_supports_whitelisted_safe_functions(self):
        evaluator = MathReexecutor()
        self.assertEqual(evaluator.evaluate_expression("max(125, 96)"), 125.0)
        self.assertEqual(evaluator.evaluate_expression("min(4, 9) + abs(-2)"), 6.0)
        self.assertIsNone(evaluator.evaluate_expression("__import__('os').system('id')"))


if __name__ == "__main__":
    unittest.main()
