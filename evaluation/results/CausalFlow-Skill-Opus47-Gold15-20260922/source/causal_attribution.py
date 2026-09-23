import copy
import json
import re
from typing import Dict, List, Any, Optional, Set
from trace_logger import TraceLogger, Step, StepType
from causal_graph import CausalGraph
from llm_client import LLMClient
from text_processor import parse_json_object
from utils import summarize_step


class CausalAttribution:

    def __init__(
        self,
        trace: TraceLogger,
        causal_graph: CausalGraph,
        llm_client: LLMClient,
        re_executor: Optional[Any] = None,
        completion_aware_interventions: bool = False,
    ):

        self.trace = trace #The failed execution trace
        self.causal_graph = causal_graph #The causal graph constructed from the trace
        self.llm_client = llm_client #LLM client for generating interventions
        self.re_executor = re_executor #Function to re-execute agent from a given step
        self.completion_aware_interventions = completion_aware_interventions

        self.crs_scores: Dict[int, float] = {} #Causal Responsibility Scores for each step
        self.intervention_results: Dict[int, Dict[str, Any]] = {} #Store intervention results

    def compute_causal_responsibility(
        self,
        execution_context: Optional[Dict[str, Any]] = None,
        intervene_step_types: Optional[Set[StepType]] = None,
        num_interventions: int = 1,
    ) -> Dict[int, float]:
        if num_interventions < 1:
            raise ValueError("num_interventions must be positive")
        steps_to_check = self.trace.steps[:-1]  # Exclude the final step
        
        for step in steps_to_check:
            if intervene_step_types is not None and step.step_type not in intervene_step_types:
                self.crs_scores[step.step_id] = 0.0
                self.intervention_results[step.step_id] = {
                    "success": False,
                    "reason": f"Skipped: step type {step.step_type.value} not in intervene_step_types"
                }
                continue
            
            self.crs_scores[step.step_id] = self._intervene_on_step(
                step,
                execution_context=execution_context,
                num_interventions=num_interventions,
            )

        return self.crs_scores

    def _intervene_on_step(
        self,
        step: Step,
        execution_context: Optional[Dict[str, Any]] = None,
        num_interventions: int = 1,
    ) -> float:
        """
        Perform intervention on a single step and compute CRS.

        Process:
        1. Copy the trace
        2. Apply intervention to step i
        3. Re-execute from step i forward
        4. Compare new outcome to original

        Args:
            step_id: The step to intervene on

        Returns:
            CRS score (1.0 if intervention flipped outcome to success, 0.0 otherwise)
        """
        logs = (execution_context or {}).get("logs")
        if not logs and isinstance(step.state_snapshot, dict):
            logs = step.state_snapshot.get("recorded_output_tail")
        end_feedback = (
            "The execution in this run failed. The following logs were generated: "
            + (str(logs) if logs else "No end feedback provided")
        )
        attempts: List[Dict[str, Any]] = []
        prior_interventions: List[Step] = []
        for proposal_index in range(num_interventions):
            intervened_step = self._generate_intervention(
                step,
                end_feedback=end_feedback,
                prior_interventions=list(prior_interventions),
            )
            if intervened_step is None:
                attempts.append(
                    {
                        "proposal_index": proposal_index,
                        "success": False,
                        "reason": "Could not generate intervention",
                    }
                )
                continue
            prior_interventions.append(intervened_step)
            new_outcome = self._reexecute(step.step_id, intervened_step)
            attempts.append(
                {
                    "proposal_index": proposal_index,
                    "intervened_step": intervened_step.to_dict(),
                    "new_outcome": new_outcome,
                    "flipped_to_success": new_outcome,
                }
            )
            if new_outcome:
                break

        flipped = any(item.get("flipped_to_success") for item in attempts)
        self.intervention_results[step.step_id] = {
            "original_step": step.to_dict(),
            "attempts": attempts,
            "num_interventions_requested": num_interventions,
            "num_interventions_evaluated": len(attempts),
            "flipped_to_success": flipped,
        }
        # Preserve the legacy one-proposal fields for existing result readers.
        if attempts:
            self.intervention_results[step.step_id].update(
                {
                    key: attempts[0].get(key)
                    for key in ("intervened_step", "new_outcome")
                }
            )

        return 1.0 if flipped else 0.0 # CRS = 1 if any intervention flipped the outcome

    def _generate_intervention(
        self,
        step: Step,
        end_feedback: str,
        prior_interventions: Optional[List[Step]] = None,
    ) -> Optional[Step]:
        intervention_prompt = self._create_intervention_prompt(
            step,
            end_feedback,
            prior_interventions=prior_interventions,
        )

        try:
            result = self.llm_client.generate_structured(
                intervention_prompt,
                schema_name="intervention",
                system_message="You are an expert at debugging and correcting agent reasoning steps. Always respond using the provided schema in JSON format.",
                model_name=self.llm_client.model
            )

            intervened_step = copy.deepcopy(step)

            if step.step_type == StepType.REASONING:
                intervened_step.text = result.corrected_reasoning or step.text
            elif step.step_type == StepType.TOOL_CALL:
                # Prefer a direct command field for shell actions.  Embedding a
                # long shell program inside a second JSON string creates an
                # avoidable layer of escaping and was observed to reject an
                # otherwise structured SkillsBench intervention.
                if result.corrected_command is not None and isinstance(
                    step.tool_args, dict
                ) and "command" in step.tool_args:
                    intervened_step.tool_args = dict(step.tool_args)
                    intervened_step.tool_args["command"] = result.corrected_command
                elif result.corrected_tool_args_json is not None:
                    intervened_step.tool_args = parse_json_object(
                        result.corrected_tool_args_json
                    )
                # Constrain the intervention to the legal action space: the LLM
                # frequently hallucinates tool names that do not exist (e.g.
                # "python_code_executor"), which makes the intervened step
                # unexecutable and aborts the whole analysis downstream.
                # Only accept a renamed tool if it actually occurs in the trace.
                if result.corrected_tool_name is not None:
                    known_tools = {
                        s.tool_name for s in self.trace.steps if s.tool_name
                    }
                    if result.corrected_tool_name in known_tools:
                        intervened_step.tool_name = result.corrected_tool_name
                    else:
                        print(
                            f"Ignoring hallucinated tool name "
                            f"'{result.corrected_tool_name}' for step {step.step_id} "
                            f"(keeping '{step.tool_name}')"
                        )
            elif step.step_type == StepType.MEMORY_ACCESS:
                intervened_step.memory_value = result.corrected_reasoning or step.memory_value
            else:
                # For other types, update the text field
                intervened_step.text = result.corrected_reasoning or result.corrected_text or step.text

            return intervened_step

        except Exception as e:
            print(f"Error generating intervention for step {step.step_id}: {e}")
            return None

    def _create_intervention_prompt(
        self,
        step: Step,
        end_feedback: str,
        prior_interventions: Optional[List[Step]] = None,
    ) -> str:
        context = self._get_step_context(step)

        prompt = f"""You are analyzing a failed agent execution. The agent produced an incorrect final answer.

Problem Statement: {self.trace.problem_statement or "No problem statement provided"}
Gold Answer (correct answer): {self.trace.gold_answer or "No gold answer provided"}
Environment feedback at the point of failure: {end_feedback}

Context from previous steps:
{context if context else "No earlier context"}

Current step (Step {step.step_id}, Type: {step.step_type.value}):
"""

        if step.step_type == StepType.REASONING:
            prompt += f"Original Reasoning: {step.text}\n\n"
            prompt += "Provide a corrected version of this reasoning step that would lead to the correct answer.\n"
            prompt += "CRITICAL: Compare the reasoning against the Problem Statement. If the logic contradicts the problem statement (e.g. ignoring a constraint like 'restart from beginning'), you MUST correct it.\n"
            prompt += "Fill in the 'corrected_reasoning' field."

        elif step.step_type == StepType.TOOL_CALL:
            prompt += f"Tool: {step.tool_name}\n"
            prompt += f"Arguments: {json.dumps(step.tool_args)}\n\n"
            prompt += (
                "Provide corrected tool name and arguments. For a shell tool "
                "whose arguments contain a command key, put the executable "
                "command directly in 'corrected_command'. Use "
                "'corrected_tool_args_json' only for other argument shapes."
            )
            if self.completion_aware_interventions:
                prompt += """

Completion-aware diagnostic policy:
- Check whether the recorded trace stopped before creating or modifying the deliverables required by the Problem Statement.
- If required work is missing, replace this step with one executable compound command that completes the remaining task, rather than returning another inspection-only command.
- A shell command may create a temporary script, run it, validate the required output, and clean up temporary files.
- The replacement must materially change task state when the original failure is a missing deliverable.
- Do not claim completion in prose. Put the full executable workflow directly in corrected_command.
"""

        elif step.step_type == StepType.LLM_RESPONSE:
            prompt += f"LLM Response: {step.text}\n\n"
            prompt += "Provide a corrected version of this LLM response in the 'corrected_reasoning' field."

        elif step.step_type == StepType.TOOL_RESPONSE:
            prompt += f"Tool Call Result: {step.tool_call_result}\n"
            prompt += f"Tool Output: {step.tool_output}\n\n"
            prompt += "Provide a corrected version of this tool response in the 'corrected_reasoning' field."

        elif step.step_type == StepType.MEMORY_ACCESS:
            prompt += f"Memory Key: {step.memory_key}\n"
            prompt += f"Memory Value: {step.memory_value}\n\n"
            prompt += "Provide the correct memory value in the 'corrected_reasoning' field."

        else:
            prompt += f"Content: {step.text or step.action or step.observation}\n\n"
            prompt += "Provide a corrected version of this step in the 'corrected_reasoning' field."

        if prior_interventions:
            prompt += "\n\nEarlier intervention candidates for this same step:\n"
            for index, prior in enumerate(prior_interventions, start=1):
                prompt += f"Candidate {index}: {summarize_step(prior)}\n"
            prompt += (
                "Return a materially different executable correction. Do not "
                "repeat an earlier candidate."
            )

        prompt += "\n\nAlso provide a brief explanation of what was corrected and why in the 'explanation' field."

        return prompt

    def _get_step_context(self, step: Step, max_context_steps: int = 3) -> str:
        dependencies = step.dependencies
        if not dependencies:
            return "No previous dependencies."

        context_lines = []
        for dep_id in dependencies[-max_context_steps:]:
            dep_step = self.trace.get_step(dep_id)
            if dep_step:
                summary = summarize_step(dep_step)
                context_lines.append(f"Step {dep_id}: {summary}")

        return "\n".join(context_lines)

    def _reexecute(self, step_id: int, intervened_step: Step) -> bool:
        if self.re_executor is None:
            return self._llm_predict_outcome(step_id, intervened_step, self.trace.problem_statement)

        history = [copy.deepcopy(step) for step in self.trace.steps if step.step_id < step_id]
        history.append(intervened_step)

        new_trace = self.re_executor.run_remaining_steps(history)
        return new_trace.success

    def _llm_predict_outcome(self, step_id: int, intervened_step: Step, problem_statement: str) -> bool:
        prompt = f"""You are analyzing an agent execution trace.

Problem Statement: {problem_statement}
Original Final Answer: {self.trace.final_answer}
Correct Answer: {self.trace.gold_answer}
Original Outcome: FAILED

An intervention was made at Step {step_id}:
Original: {summarize_step(self.trace.get_step(step_id))}
Intervened: {summarize_step(intervened_step)}

Descendants of this step (affected by the intervention):
"""
        descendants = self.causal_graph.get_descendants(step_id)
        for desc_id in sorted(descendants):
            desc_step = self.trace.get_step(desc_id)
            if desc_step:
                prompt += f"  Step {desc_id}: {summarize_step(desc_step)}\n"

        prompt += f"\nWould this intervention cause the final answer to change to the correct answer ({self.trace.gold_answer})?"
        prompt += "\nIMPORTANT: Be conservative. If the intervention is trivial (e.g. only formatting changes, removing units) or does not address the root logical error, answer FALSE."
        prompt += "\n\nProvide your prediction, confidence level, and reasoning."

        try:
            result = self.llm_client.generate_structured(
                prompt,
                schema_name="outcome_prediction",
                temperature=0.0,
                model_name=self.llm_client.model,
            )
            return result.would_succeed
        except Exception as e:
            print(f"Error predicting outcome: {e}")
            return False

    def get_causal_steps(self) -> List[int]:
        return [
            step_id for step_id, score in self.crs_scores.items()
            if score >= 0.5
        ]

    def get_top_causal_steps(self) -> List[tuple]:

        return [
            (step_id, score) for step_id, score in self.crs_scores.items()
            if score >= 0.5
        ]
