#!/usr/bin/env python3
"""Execute the frozen JPG SkillTTA bundle with the 65-iteration adapter."""

from __future__ import annotations

import json
import os
from pathlib import Path

from benchmark_executor import BenchmarkExecutor


ROOT = Path(__file__).resolve().parent
ENV_FILE = Path(
    "/Users/king/Documents/Codex/2026-09-18/"
    "skillaxe-20-17-skillaxe-39-48-2/claudeapikey.env"
)


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def main() -> None:
    env = load_env(ENV_FILE)
    api_key = env.get("API_KEY", "")
    if not api_key:
        raise RuntimeError("API_KEY is missing")
    os.environ["PARATERA_API_KEY"] = api_key

    executor = BenchmarkExecutor(
        tasks_root=Path("/tmp/skilltta-runtime/execution_tasks/jpg-ocr-stat"),
        jobs_root=ROOT / "runs" / "final_jobs",
        model="paratera/Claude-Opus-4.7",
        experimental_text_only_retry_limit=1,
    )
    result = executor.run(
        task_id="jpg-ocr-stat",
        method_id="skilltta-claude47-paratera-jpg-strict",
        stage="final-repaired-skill-rollout-65-parent-iterations",
        rollout_id="jpg-ocr-stat-skilltta-claude47-paratera-strict-final-r003",
        condition="method-skill",
        skill_bundle=(
            ROOT / "runs" / "skilltta-claude47-paratera-strict-full" / "skills"
        ),
    )
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
