"""Resolve the exact Skill bundle that a recorded SkillsBench rollout saw."""

from __future__ import annotations

from pathlib import Path


def resolve_deployed_skills(
    run_dir: Path, task_dir: Path, explicit: Path | None = None
) -> tuple[Path, str]:
    if explicit is not None:
        candidate = explicit.expanduser().resolve(strict=True)
        source = "explicit"
    else:
        snapshot = run_dir / "inputs" / "skills"
        if snapshot.is_dir():
            candidate = snapshot.resolve(strict=True)
            source = "recorded_rollout_snapshot"
        else:
            candidate = (task_dir / "environment" / "skills").resolve(strict=True)
            source = "task_original"
    if not candidate.is_dir() or not any(candidate.rglob("SKILL.md")):
        raise ValueError(f"deployed Skill bundle is invalid: {candidate}")
    return candidate, source
