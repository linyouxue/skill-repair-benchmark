import unittest
from types import SimpleNamespace

from causal_graph import CausalGraph
from counterfactual_repair import CounterfactualRepair, Repair
from repair_context import build_repair_context
from trace_logger import Step, StepType, TraceLogger
from utils import extract_step_text


class _Repair:
    proposal_idx = 0
    repaired_text = "old failed patch"
    success_predicted = False
    behavioral_invariant = "keep order"
    repaired_trace = None


class RepairContextTests(unittest.TestCase):
    def _trace(self):
        trace = TraceLogger(problem_statement="Implement f", gold_answer="pass")
        trace.steps = [
            Step(0, StepType.REASONING, text="plan"),
            Step(
                1,
                StepType.LLM_RESPONSE,
                dependencies=[0],
                text="bad code",
                resource_reads=["spec:v1"],
                resource_writes=["code:v1"],
            ),
            Step(
                2,
                StepType.TOOL_RESPONSE,
                dependencies=[1],
                tool_call_result=False,
                tool_output="AssertionError: wrong value",
            ),
            Step(3, StepType.FINAL_ANSWER, dependencies=[2], text="fail"),
        ]
        trace.current_step_id = 4
        trace.final_answer = "fail"
        trace.success = False
        return trace

    def test_pack_contains_graph_neighbors_failure_and_constraints(self):
        trace = self._trace()
        pack = build_repair_context(
            trace,
            CausalGraph(trace),
            1,
            execution_context={"entry_point": "f", "tests": "assert f() == 1"},
            causal_step_ids=[0, 1],
            prior_repairs=[_Repair()],
        )
        self.assertEqual([item["step_id"] for item in pack["direct_inputs"]], [0])
        self.assertEqual([item["step_id"] for item in pack["direct_consumers"]], [2])
        self.assertEqual(pack["task_constraints"]["entry_point"], "f")
        self.assertEqual(pack["acceptance_obligations"], ["assert f() == 1"])
        self.assertEqual(pack["expected_output_examples"], ["1"])
        self.assertIn("AssertionError", pack["downstream_failure_evidence"][0]["summary"])
        self.assertEqual(pack["other_attributed_causes"][0]["step_id"], 0)
        self.assertEqual(pack["prior_candidate_attempts"][0]["succeeded"], False)
        self.assertEqual(
            pack["prior_candidate_attempts"][0]["behavioral_invariant"],
            "keep order",
        )
        self.assertTrue(pack["replay_scope"]["requires_joint_plan"])
        self.assertEqual(
            [item["step_id"] for item in pack["downstream_failure_evidence"]],
            [2, 3],
        )

    def test_gold_answer_is_not_in_evidence_pack(self):
        trace = self._trace()
        pack = build_repair_context(trace, CausalGraph(trace), 1)
        self.assertNotIn("pass", str(pack))

    def test_counterfactual_prompt_includes_local_evidence_and_prior_attempt(self):
        trace = self._trace()
        attribution = SimpleNamespace(
            causal_graph=CausalGraph(trace),
            get_causal_steps=lambda: [0, 1],
        )
        repairer = CounterfactualRepair(
            trace,
            attribution,
            llm_client=object(),
            execution_context={"entry_point": "f", "tests": "assert f() == 1"},
            use_gold_in_prompts=False,
        )
        failed = Repair(
            step_id=1,
            original_step=trace.steps[1],
            repaired_step=trace.steps[1],
            minimality_lex=1.0,
            success_predicted=False,
            repaired_text="old failed patch",
            proposal_idx=0,
            behavioral_invariant="preserve length",
        )
        prompt = repairer._create_repair_prompt(
            trace.steps[1],
            trace.steps[:1],
            proposal_idx=1,
            proposal_total=3,
            prior_repairs=[failed],
        )
        self.assertIn("STRUCTURED LOCAL EVIDENCE", prompt)
        self.assertIn('"direct_inputs"', prompt)
        self.assertIn("old failed patch", prompt)
        self.assertIn("candidate 2 of 3", prompt)
        self.assertNotIn("Correct Answer (FOR REFERENCE ONLY)", prompt)

    def test_empty_success_list_is_not_counted_as_successful_step(self):
        trace = self._trace()
        attribution = SimpleNamespace(causal_graph=CausalGraph(trace))
        repairer = CounterfactualRepair(trace, attribution, llm_client=object())
        failed = Repair(
            step_id=1,
            original_step=trace.steps[1],
            repaired_step=trace.steps[1],
            minimality_lex=1.0,
            success_predicted=False,
        )
        succeeded = Repair(
            step_id=2,
            original_step=trace.steps[2],
            repaired_step=trace.steps[2],
            minimality_lex=1.0,
            success_predicted=True,
        )
        repairer.repairs = {1: [failed], 2: [succeeded]}
        self.assertEqual(set(repairer.get_all_successful_repairs()), {2})

    def test_llm_response_text_participates_in_minimality(self):
        trace = self._trace()
        self.assertEqual(extract_step_text(trace.steps[1]), "bad code")

    def test_duplicate_candidate_is_resampled(self):
        trace = TraceLogger(problem_statement="problem", gold_answer="right")
        trace.steps = [
            Step(0, StepType.REASONING, text="old"),
            Step(1, StepType.FINAL_ANSWER, dependencies=[0], text="wrong"),
        ]
        graph = CausalGraph(trace)
        attribution = SimpleNamespace(
            causal_graph=graph,
            get_causal_steps=lambda: [0],
            _llm_predict_outcome=lambda *_args, **_kwargs: False,
        )

        class FakeLLM:
            model = "fake"

            def __init__(self):
                self.values = iter(["new one", "new one", "new two"])
                self.calls = 0

            def generate_structured(self, *_args, **_kwargs):
                self.calls += 1
                return SimpleNamespace(
                    diagnosis="bad logic",
                    expected_output_contract="reasoning text",
                    behavioral_invariant="preserve the goal",
                    evidence_used=["step 0"],
                    repaired_text=next(self.values),
                    repaired_tool_args_json=None,
                    repaired_tool_name=None,
                    changes_made=["change"],
                    minimality_justification="minimal",
                )

        llm = FakeLLM()
        repairer = CounterfactualRepair(trace, attribution, llm_client=llm)
        repairs = repairer.generate_repairs([0], num_proposals=2)[0]
        self.assertEqual([repair.repaired_text for repair in repairs], ["new one", "new two"])
        self.assertEqual(llm.calls, 3)


if __name__ == "__main__":
    unittest.main()
