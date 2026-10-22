"""Trace-conditioned selection of repairable Skills in an official bundle.

This module is deliberately outside the original single-Skill SkillRevise
loop.  It makes the bundle-level extension auditable: callers can report
candidate-location quality separately from diagnosis and revision quality.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from skillrevise.core.models import ExecutionTrace, TaskSpec
from skillrevise.llm import LLMClient


@dataclass(frozen=True)
class BundleTargetSelection:
    targets: list[str]
    rationale: str
    raw_response: str = ""


class LLMBundleSkillSelector:
    """Select an ordered, bounded set of ``SKILL.md`` paths from a bundle."""

    def __init__(self, llm: LLMClient, *, max_targets: int = 2) -> None:
        if max_targets < 1:
            raise ValueError("max_targets must be >= 1")
        self.llm = llm
        self.max_targets = max_targets

    def select(
        self,
        task: TaskSpec,
        trace: ExecutionTrace,
        *,
        bundle_root: Path,
        skill_paths: list[str],
    ) -> BundleTargetSelection:
        catalog = []
        for relative_path in skill_paths:
            text = (bundle_root / relative_path).read_text(encoding="utf-8")
            # The prompt needs enough semantics to locate a module, but a
            # bounded excerpt keeps very large bundles feasible.
            catalog.append({"path": relative_path, "content": text[:6000]})
        prompt = self._prompt(task, trace, catalog)
        response = self.llm.complete(prompt, purpose="bundle_skill_selection")
        targets, rationale = self._parse(response.text, allowed=set(skill_paths))
        # A model can validly return an empty list when it cannot ground a
        # failure in any supplied Skill.  This is a task-level no-selection
        # outcome, not a framework error: the caller must retain the frozen
        # original trace and continue with the next task.  Raising here used
        # to abort an entire multi-task experiment (as happened for
        # fix-build-agentops) and discarded otherwise valid results.
        if not targets:
            rationale = (
                rationale
                or "The selector returned no allowed Skill path; no revision was attempted."
            )
        return BundleTargetSelection(
            targets=targets[: self.max_targets], rationale=rationale, raw_response=response.text
        )

    def _prompt(self, task: TaskSpec, trace: ExecutionTrace, catalog: list[dict[str, str]]) -> str:
        events = trace.events
        if len(events) > 14:
            events = [*events[:2], *events[-12:]]
        event_excerpt = [
            {
                "step_index": event.step_index,
                "kind": event.kind,
                "summary": event.summary[:500],
                "evidence": event.evidence[:700],
            }
            for event in events
        ]
        return (
            "You are a Skill-bundle repair target selector. Select the smallest ordered set of "
            "SKILL.md files most likely responsible for the observed failed execution. Do not propose "
            "a repair and do not use information outside this prompt. Return strict JSON only:\n"
            '{"targets":["relative/path/SKILL.md"],"rationale":"brief evidence-based reason"}\n\n'
            f"Task instruction:\n{task.instruction}\n\n"
            f"Acceptance criteria:\n{json.dumps(task.acceptance_criteria, ensure_ascii=False)}\n\n"
            f"Execution status: {trace.status}; success={trace.success}; reward={trace.metadata.get('reward')}\n"
            f"Execution summary:\n{trace.outcome_summary}\n\n"
            f"Trace events (opening context plus the final failure behavior):\n"
            f"{json.dumps(event_excerpt, ensure_ascii=False)}\n\n"
            f"Available Skills:\n{json.dumps(catalog, ensure_ascii=False)}\n"
        )

    def _parse(self, text: str, *, allowed: set[str]) -> tuple[list[str], str]:
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Bundle target selector returned invalid JSON: {exc}") from exc
        raw_targets = payload.get("targets") if isinstance(payload, dict) else None
        if not isinstance(raw_targets, list):
            raise RuntimeError("Bundle target selector JSON requires a targets list.")
        targets = []
        for item in raw_targets:
            if isinstance(item, str) and item in allowed and item not in targets:
                targets.append(item)
        rationale = str(payload.get("rationale", "")) if isinstance(payload, dict) else ""
        return targets, rationale
