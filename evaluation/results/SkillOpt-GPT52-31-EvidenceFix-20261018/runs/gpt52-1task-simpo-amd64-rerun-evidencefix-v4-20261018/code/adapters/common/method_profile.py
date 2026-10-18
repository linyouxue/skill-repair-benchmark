"""Method profiles that differentiate SkillOpt vs SkillOpt-Lite adapters."""
from __future__ import annotations

import os
from typing import Any


def _env_override(name: str) -> str | None:
    raw = os.environ.get(name, "").strip().lower()
    return raw or None


def method_profile(method_name: str) -> dict[str, Any]:
    """Return algorithm knobs for a method label.

    SkillOpt (default): bounded patch edits, merge n samples, strict L.
    SkillOpt-Lite (default): full rewrite, skip LLM merge (looser), +1 repair round.
    """
    name = (method_name or "").strip().lower()
    is_lite = name in {"skillopt-lite", "skillopt_lite", "lite"}

    if is_lite:
        update_mode = _env_override("SKILLOPT_EVA_LITE_UPDATE_MODE") or "rewrite"
        merge_samples = os.environ.get("SKILLOPT_EVA_LITE_MERGE_SAMPLES", "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        # Default lite: do NOT merge (looser). Opt-in merge via env.
        if "SKILLOPT_EVA_LITE_MERGE_SAMPLES" not in os.environ:
            merge_samples = False
        budget_multiplier = float(os.environ.get("SKILLOPT_EVA_LITE_BUDGET_MULT", "2") or "2")
        rounds_bonus = int(os.environ.get("SKILLOPT_EVA_LITE_ROUNDS_BONUS", "1") or "1")
        profile = {
            "method_name": "skillopt-lite",
            "update_mode": update_mode if update_mode in {"patch", "rewrite"} else "rewrite",
            "merge_samples": merge_samples,
            "strict_budget": False,
            "budget_multiplier": max(1.0, budget_multiplier),
            "repair_rounds_bonus": max(0, rounds_bonus),
            "label": "lite-rewrite-loose",
        }
    else:
        update_mode = _env_override("SKILLOPT_EVA_UPDATE_MODE") or "patch"
        profile = {
            "method_name": "skillopt",
            "update_mode": update_mode if update_mode in {"patch", "rewrite"} else "patch",
            "merge_samples": True,
            "strict_budget": True,
            "budget_multiplier": 1.0,
            "repair_rounds_bonus": 0,
            "label": "skillopt-bounded-edit",
        }

    # Global force override
    forced = _env_override("SKILLOPT_EVA_UPDATE_MODE")
    if forced in {"patch", "rewrite"} and not is_lite:
        profile["update_mode"] = forced
    forced_lite = _env_override("SKILLOPT_EVA_LITE_UPDATE_MODE")
    if forced_lite in {"patch", "rewrite"} and is_lite:
        profile["update_mode"] = forced_lite
    return profile
