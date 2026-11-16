"""Multi-sample diagnosis + merge + gate helpers (adapted SkillOpt-style repair).

Parameter meanings
------------------
n (SKILLOPT_EVA_DIAGNOSIS_N):
  Number of independent diagnosis samples for the same task evidence.
  They are *independent LLM samples* of localization/repair suggestions.
  Can be run sequentially (default) or in parallel threads
  (SKILLOPT_EVA_DIAGNOSIS_PARALLEL=1). Not “n different tasks”.

L (SKILLOPT_EVA_EDIT_BUDGET_L):
  Merge budget: after reflecting over the n samples, keep at most L
  diagnosed skills / repair foci (analogous to SkillOpt learning-rate).

R (SKILLOPT_EVA_REPAIR_ROUNDS_R):
  Outer progressive repair rounds: each round does
  diagnose(n)→merge/loose(≤L)→patch|rewrite→same-task gate(keep/revert).
  Round r>1 may use the previous round’s gate failure as new evidence.
  Rejected proposals accumulate in a buffer for later rounds.
  All prior *failure* trajectories (baseline + failed gates) are concatenated
  into later-round diagnosis/edit evidence (not replaced by the latest gate only).

SKILLOPT_EVA_SMOKE=1 forces n=1 and R=1 for cheap debugging.
"""
from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable


def env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return max(1, int(raw))
    except ValueError:
        return default


def smoke_mode() -> bool:
    raw = os.environ.get("SKILLOPT_EVA_SMOKE", "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def diagnosis_sample_count() -> int:
    if smoke_mode():
        return 1
    return env_int("SKILLOPT_EVA_DIAGNOSIS_N", 3)


def edit_budget_l() -> int:
    if smoke_mode():
        return env_int("SKILLOPT_EVA_EDIT_BUDGET_L", 2)
    return env_int("SKILLOPT_EVA_EDIT_BUDGET_L", 4)


def repair_rounds_r(*, bonus: int = 0) -> int:
    if smoke_mode():
        return 1
    return env_int("SKILLOPT_EVA_REPAIR_ROUNDS_R", 2) + max(0, int(bonus))


def diagnosis_parallel() -> bool:
    raw = os.environ.get("SKILLOPT_EVA_DIAGNOSIS_PARALLEL", "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def score_benchmark_result(data: dict[str, Any] | None) -> float:
    """Comparable scalar for keep/revert. Pass >> partial scores >> fail."""
    if not isinstance(data, dict):
        return 0.0
    if data.get("task_passed") is True:
        return 1.0
    # Prefer explicit numeric rewards when present.
    for key in ("reward", "score", "accuracy"):
        value = data.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    grader = data.get("grader_result")
    if isinstance(grader, dict):
        for key in ("score", "reward", "accuracy"):
            value = grader.get(key)
            if isinstance(value, (int, float)):
                return float(value)
    verifier = data.get("verifier_result")
    if isinstance(verifier, dict):
        passed = verifier.get("passed")
        failed = verifier.get("failed")
        if isinstance(passed, int) and isinstance(failed, int) and (passed + failed) > 0:
            return passed / (passed + failed)
        tests = verifier.get("tests")
        if isinstance(tests, list) and tests:
            ok = sum(1 for t in tests if isinstance(t, dict) and t.get("passed") is True)
            return ok / len(tests)
    return 0.0


def truncate_diagnosed_skills(diagnosis: dict[str, Any], limit: int) -> dict[str, Any]:
    out = dict(diagnosis)
    skills = list(out.get("diagnosed_skills") or [])
    if len(skills) <= limit:
        return out

    def conf_key(item: dict[str, Any]) -> float:
        raw = str(item.get("confidence", "")).strip().lower()
        if raw in {"high", "fallback"}:
            return 0.9 if raw == "high" else 0.1
        try:
            return float(raw)
        except ValueError:
            return 0.5

    ranked = sorted((s for s in skills if isinstance(s, dict)), key=conf_key, reverse=True)
    kept = ranked[:limit]
    kept_paths = {str(s.get("path")) for s in kept}
    out["diagnosed_skills"] = kept
    prev_unselected = [p for p in (out.get("unselected_skills") or []) if p not in kept_paths]
    dropped = [str(s.get("path")) for s in ranked[limit:] if s.get("path")]
    out["unselected_skills"] = list(dict.fromkeys([*prev_unselected, *dropped]))
    out["edit_budget_l"] = limit
    out["truncated_by_budget"] = True
    return out


def merge_diagnosis_samples(
    *,
    samples: list[dict[str, Any]],
    inventory: list[dict[str, Any]],
    task_id: str,
    budget_l: int,
    chat_fn: Callable[..., tuple[str, dict[str, Any]]],
    extract_json_fn: Callable[[str], dict[str, Any] | None],
    fallback_extract_fn: Callable[[str], dict[str, Any] | None],
    normalize_fn: Callable[[dict[str, Any] | None, list[dict[str, Any]], str], dict[str, Any]],
    rejected_buffer: list[dict[str, Any]] | None = None,
    capture: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], str, dict[str, Any], float]:
    """Reflect over n diagnosis samples → one merged diagnosis with ≤ L skills."""
    if not samples:
        raise ValueError("merge_diagnosis_samples requires at least one sample")
    if len(samples) == 1:
        merged = truncate_diagnosed_skills(dict(samples[0]), budget_l)
        merged["diagnosis_sample_count"] = 1
        merged["merged_from_samples"] = False
        return merged, "", {}, 0.0

    compact_samples = []
    for idx, sample in enumerate(samples, start=1):
        compact_samples.append(
            {
                "sample_id": idx,
                "fallback_used": bool(sample.get("fallback_used")),
                "overall_diagnosis": sample.get("overall_diagnosis", ""),
                "diagnosed_skills": sample.get("diagnosed_skills", []),
            }
        )
    system = (
        "You are a SkillOpt reflect/merge planner. You receive multiple independent "
        "diagnoses for the SAME single SkillsBench task. Merge them into one coherent "
        "diagnosis. Prefer skill paths that recur across samples. Combine complementary "
        "repair instructions; drop contradictory or low-value ones. "
        f"Return at most {budget_l} diagnosed_skills (learning-rate budget L={budget_l}). "
        "Return exactly one valid JSON object and no markdown. "
        "Required keys: overall_diagnosis:string, diagnosed_skills:array, unselected_skills:array. "
        "Each diagnosed_skills item must have path, confidence, diagnosis, repair_instruction. "
        "Use only paths from the skill inventory."
    )
    user = (
        f"## Task ID\n{task_id}\n\n"
        f"## Skill Inventory\n{json.dumps(inventory, ensure_ascii=False, indent=2)}\n\n"
        f"## Diagnosis Samples (n={len(compact_samples)})\n"
        f"{json.dumps(compact_samples, ensure_ascii=False, indent=2)}\n\n"
    )
    if rejected_buffer:
        user += (
            "## Rejected Updates From Earlier Rounds (avoid repeating)\n"
            f"{json.dumps(rejected_buffer[-8:], ensure_ascii=False, indent=2)}\n\n"
        )
    user += f"Merge into one diagnosis with at most {budget_l} skills to repair."
    if capture is not None:
        capture["request"] = {
            "stage": "reflect_merge",
            "system": system,
            "user": user,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "parameters": {"max_completion_tokens": 12000, "budget_l": budget_l},
        }
    started = time.monotonic()
    raw_text, usage = chat_fn(system=system, user=user)
    parsed = extract_json_fn(raw_text) or fallback_extract_fn(raw_text)
    duration = round(time.monotonic() - started, 3)
    merged = normalize_fn(parsed if isinstance(parsed, dict) else None, inventory, task_id)
    merged = truncate_diagnosed_skills(merged, budget_l)
    merged["diagnosis_sample_count"] = len(samples)
    merged["merged_from_samples"] = True
    merged["edit_budget_l"] = budget_l
    if capture is not None:
        capture["response"] = {
            "raw_text": raw_text,
            "usage": usage,
            "duration_sec": duration,
        }
    return merged, raw_text, usage, duration


def pick_loose_diagnosis(
    samples: list[dict[str, Any]],
    *,
    budget_l: int,
) -> dict[str, Any]:
    """Lite-style: skip LLM merge; prefer richest non-fallback sample, then truncate softly."""
    if not samples:
        raise ValueError("pick_loose_diagnosis requires samples")
    ranked = sorted(
        samples,
        key=lambda s: (
            0 if s.get("fallback_used") else 1,
            len(s.get("diagnosed_skills") or []),
        ),
        reverse=True,
    )
    chosen = truncate_diagnosed_skills(dict(ranked[0]), budget_l)
    chosen["diagnosis_sample_count"] = len(samples)
    chosen["merged_from_samples"] = False
    chosen["loose_pick"] = True
    chosen["edit_budget_l"] = budget_l
    return chosen


def run_diagnosis_samples(
    *,
    n: int,
    runner: Callable[[], tuple[dict[str, Any], str, dict[str, Any], float]],
    parallel: bool = False,
) -> list[tuple[dict[str, Any], str, dict[str, Any], float]]:
    """Run diagnosis n times. Parallel uses threads; default is sequential for import safety."""
    n = max(1, n)
    if n == 1 or not parallel:
        return [runner() for _ in range(n)]

    out: list[tuple[dict[str, Any], str, dict[str, Any], float] | None] = [None] * n

    def _job(i: int) -> tuple[int, tuple[dict[str, Any], str, dict[str, Any], float]]:
        return i, runner()

    with ThreadPoolExecutor(max_workers=min(n, 4)) as pool:
        futures = [pool.submit(_job, i) for i in range(n)]
        for fut in as_completed(futures):
            i, result = fut.result()
            out[i] = result
    return [item for item in out if item is not None]
