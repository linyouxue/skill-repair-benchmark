from __future__ import annotations

import unittest
from unittest.mock import Mock

from causal_attribution import CausalAttribution
from schemas import InterventionOutput
from trace_logger import Step, StepType, TraceLogger


def make_trace() -> TraceLogger:
    trace = TraceLogger(problem_statement="demo", gold_answer="1")
    trace.steps = [
        Step(step_id=0, step_type=StepType.REASONING, text="wrong"),
        Step(step_id=1, step_type=StepType.FINAL_ANSWER, text="0"),
    ]
    trace.final_answer = "0"
    return trace


class CausalAttributionSamplingTests(unittest.TestCase):
    def test_multiple_interventions_stop_after_first_flip(self):
        trace = make_trace()
        attribution = CausalAttribution(trace, Mock(), Mock())
        attribution._generate_intervention = Mock(side_effect=[trace.steps[0]] * 3)
        attribution._reexecute = Mock(side_effect=[False, True, False])

        score = attribution._intervene_on_step(
            trace.steps[0], execution_context=None, num_interventions=3
        )

        self.assertEqual(score, 1.0)
        self.assertEqual(attribution._reexecute.call_count, 2)
        result = attribution.intervention_results[0]
        self.assertEqual(result["num_interventions_requested"], 3)
        self.assertEqual(result["num_interventions_evaluated"], 2)
        self.assertTrue(result["flipped_to_success"])
        second_call = attribution._generate_intervention.call_args_list[1]
        self.assertEqual(second_call.kwargs["prior_interventions"], [trace.steps[0]])

    def test_missing_execution_context_is_safe(self):
        trace = make_trace()
        attribution = CausalAttribution(trace, Mock(), Mock())
        attribution._generate_intervention = Mock(return_value=None)

        score = attribution._intervene_on_step(
            trace.steps[0], execution_context=None, num_interventions=1
        )

        self.assertEqual(score, 0.0)
        prompt_feedback = attribution._generate_intervention.call_args.kwargs[
            "end_feedback"
        ]
        self.assertIn("No end feedback provided", prompt_feedback)

    def test_recorded_tool_output_is_used_as_local_failure_feedback(self):
        trace = make_trace()
        trace.steps[0].state_snapshot = {
            "recorded_output_tail": "ls: invalid option -- malformed"
        }
        attribution = CausalAttribution(trace, Mock(), Mock())
        attribution._generate_intervention = Mock(return_value=None)

        attribution._intervene_on_step(
            trace.steps[0], execution_context=None, num_interventions=1
        )

        prompt_feedback = attribution._generate_intervention.call_args.kwargs[
            "end_feedback"
        ]
        self.assertIn("ls: invalid option", prompt_feedback)

    def test_non_positive_intervention_count_is_rejected(self):
        trace = make_trace()
        attribution = CausalAttribution(trace, Mock(), Mock())
        with self.assertRaises(ValueError):
            attribution.compute_causal_responsibility(num_interventions=0)

    def test_intervention_prompt_requires_a_distinct_followup_candidate(self):
        trace = make_trace()
        attribution = CausalAttribution(trace, Mock(), Mock())
        prior = Step(
            step_id=0,
            step_type=StepType.TOOL_CALL,
            tool_name="run_shell",
            tool_args={"command": "ls -al"},
        )

        prompt = attribution._create_intervention_prompt(
            trace.steps[0],
            "failed",
            prior_interventions=[prior],
        )

        self.assertIn("Earlier intervention candidates", prompt)
        self.assertIn("materially different", prompt)
        self.assertIn("ls -al", prompt)

    def test_completion_aware_prompt_requests_missing_deliverables(self):
        trace = TraceLogger(problem_statement="Create /root/output.json")
        step = Step(
            step_id=0,
            step_type=StepType.TOOL_CALL,
            tool_name="run_shell",
            tool_args={"command": "ls -al"},
        )
        trace.steps = [
            step,
            Step(step_id=1, step_type=StepType.FINAL_ANSWER, text="failed"),
        ]
        attribution = CausalAttribution(
            trace,
            Mock(),
            Mock(),
            completion_aware_interventions=True,
        )

        prompt = attribution._create_intervention_prompt(step, "missing output")

        self.assertIn("Completion-aware diagnostic policy", prompt)
        self.assertIn("compound command", prompt)
        self.assertIn("materially change task state", prompt)

    def test_direct_corrected_command_avoids_nested_json(self):
        trace = TraceLogger(problem_statement="Create output")
        step = Step(
            step_id=0,
            step_type=StepType.TOOL_CALL,
            tool_name="run_shell",
            tool_args={"command": "ls -al", "timeout": 10},
        )
        trace.steps = [
            step,
            Step(step_id=1, step_type=StepType.FINAL_ANSWER, text="failed"),
        ]
        llm = Mock()
        llm.model = "test-model"
        llm.generate_structured.return_value = InterventionOutput(
            corrected_command="printf '%s\\n' done > /root/output.txt",
            explanation="Create the missing output",
        )
        attribution = CausalAttribution(trace, Mock(), llm)

        repaired = attribution._generate_intervention(step, "missing output")

        self.assertEqual(
            repaired.tool_args,
            {
                "command": "printf '%s\\n' done > /root/output.txt",
                "timeout": 10,
            },
        )


if __name__ == "__main__":
    unittest.main()
