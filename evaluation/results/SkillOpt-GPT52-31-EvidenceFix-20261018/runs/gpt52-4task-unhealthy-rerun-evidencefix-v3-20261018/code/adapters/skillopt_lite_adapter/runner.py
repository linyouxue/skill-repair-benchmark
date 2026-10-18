from __future__ import annotations

from pathlib import Path

from adapters.common.paths import ROOT
from adapters.common.rewrite_engine import rewrite_bundle_once


def generate_candidate_skill(
    *,
    task_id: str,
    workspace: Path,
    before_skill: Path,
    after_skill: Path,
    baseline_result: Path | None,
    run_id: str | None = None,
    repair_round: int = 1,
    allow_overwrite: bool = False,
    rejected_buffer: list | None = None,
    evidence_paths: list | None = None,
) -> None:
    rewrite_bundle_once(
        method_name="skillopt-lite",
        method_root=ROOT / "SkillOpt-Lite",
        lite=True,
        task_id=task_id,
        workspace=workspace,
        before_skill=before_skill,
        after_skill=after_skill,
        baseline_result=baseline_result,
        run_id=run_id,
        repair_round=repair_round,
        allow_overwrite=allow_overwrite,
        rejected_buffer=rejected_buffer,
        evidence_paths=evidence_paths,
    )
