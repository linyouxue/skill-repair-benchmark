#!/usr/bin/env python3
"""Package SkillOpt runs into the official evaluation/results upload layout."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
UPLOAD_ROOT = ROOT / "upload" / "evaluation-results"

GOLD_TASKS = [
    "dialogue-parser",
    "exoplanet-detection-period",
    "python-scala-translation",
    "sec-financial-report",
    "paratransit-routing",
    "software-dependency-audit",
    "video-silence-remover",
]

RUN_FILES = [
    "executor_request.json",
    "result.json",
    "benchmark_result.json",
    "config.json",
    "prompts.json",
    "timing.json",
    "rewards.jsonl",
    "results.jsonl",
]
RUN_DIRS = ["verifier", "trainer"]
SKIP_NAMES = {
    "llm_trajectory.jsonl",
    "inputs",
    "agent",
    "logs",
    "artifacts",
    "run_metadata",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def find_job(rollout_id: str, search_roots: list[Path]) -> Path:
    for root in search_roots:
        if not root.is_dir():
            continue
        direct = root / rollout_id
        if direct.is_dir():
            return direct
        for child in root.iterdir():
            if child.is_dir() and child.name == rollout_id:
                return child
    raise FileNotFoundError(f"rollout not found: {rollout_id}")


def copy_run(src: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for name in RUN_FILES:
        src_file = src / name
        if src_file.is_file():
            shutil.copy2(src_file, dest / name)
    traj_src = src / "trajectory" / "acp_trajectory.jsonl"
    if not traj_src.is_file():
        raise FileNotFoundError(f"missing trajectory: {traj_src}")
    traj_dest = dest / "trajectory"
    traj_dest.mkdir(parents=True, exist_ok=True)
    shutil.copy2(traj_src, traj_dest / "acp_trajectory.jsonl")
    for dirname in RUN_DIRS:
        src_dir = src / dirname
        if src_dir.is_dir():
            shutil.copytree(src_dir, dest / dirname, dirs_exist_ok=True)


def copy_bundle(src: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(
        src,
        dest,
        ignore=shutil.ignore_patterns(".DS_Store", "__pycache__"),
    )


def diagnoses_from(method_task_dir: Path) -> list[dict[str, Any]]:
    diagnosis = load_json(method_task_dir / "workspace" / "diagnosis.json")
    items = []
    for index, skill in enumerate(diagnosis.get("diagnosed_skills") or [], start=1):
        path = str(skill.get("path") or "").lstrip("./")
        description = str(skill.get("diagnosis") or "").strip()
        if not path or not description:
            continue
        items.append(
            {
                "prediction_id": f"P{index:03d}",
                "description": description,
                "locations": [{"file": path, "section": Path(path).parent.as_posix()}],
            }
        )
    return items


def package_method(spec: dict[str, Any]) -> None:
    method_root = UPLOAD_ROOT / spec["folder"]
    if method_root.exists():
        shutil.rmtree(method_root)
    method_root.mkdir(parents=True)

    experiment = ROOT / spec["experiment"]
    baseline_root = ROOT / spec["baseline_root"]
    job_roots = [ROOT / path for path in spec["job_search"]]
    original_pass = set(spec.get("original_pass_tasks") or [])
    tasks_payload: list[dict[str, Any]] = []

    for task_id in GOLD_TASKS:
        method_task = experiment / "methods" / "skillopt" / task_id
        baseline_pointer = load_json(
            baseline_root / "baseline" / "original-skill" / task_id / "rollout_pointer.json"
        )
        original_rollout_id = baseline_pointer["rollout_id"]
        original_job = find_job(original_rollout_id, job_roots)
        task_dir = method_root / "tasks" / task_id
        copy_run(original_job, task_dir / "original_run")

        if task_id in original_pass:
            tasks_payload.append(
                {
                    "task_id": task_id,
                    "original_pass": True,
                    "original_run_id": original_rollout_id,
                    "diagnoses": [],
                }
            )
            continue

        pointer = load_json(method_task / "rollout_pointer.json")
        method_result = load_json(method_task / "method_result.json")
        repaired_rollout_id = pointer["rollout_id"]
        if method_result.get("method_id") == "skillopt" and method_result.get("rollout_id"):
            repaired_rollout_id = method_result["rollout_id"]
        repaired_job = find_job(repaired_rollout_id, job_roots)
        request = load_json(repaired_job / "executor_request.json")
        if request.get("condition") != "method-skill":
            raise RuntimeError(
                f"{task_id}: repaired run {repaired_rollout_id} is {request.get('condition')}, not method-skill"
            )
        bundle_src = Path(request["skill_bundle"])
        if not bundle_src.is_dir():
            raise FileNotFoundError(f"{task_id}: skill bundle missing: {bundle_src}")
        copy_bundle(bundle_src, task_dir / "repaired_skill")
        copy_run(repaired_job, task_dir / "repaired_run")
        tasks_payload.append(
            {
                "task_id": task_id,
                "diagnoses": diagnoses_from(method_task),
                "repaired_bundle": f"tasks/{task_id}/repaired_skill",
                "executor_run_id": repaired_rollout_id,
            }
        )

    write_json(
        method_root / "submission.json",
        {
            "method_id": spec["method_id"],
            "benchmark_version": "core25-gold-defects-20260909-v1",
            "tasks": tasks_payload,
        },
    )
    write_json(method_root / "PACKAGING.json", spec["packaging_meta"])


def main() -> None:
    if UPLOAD_ROOT.exists():
        shutil.rmtree(UPLOAD_ROOT)
    UPLOAD_ROOT.mkdir(parents=True)

    package_method(
        {
            "folder": "SkillOpt-adapted-gpt52-n3L4R2-20260919",
            "method_id": "skillopt-adapted-gpt52-n3L4R2",
            "experiment": "experiments/core25-gpt52-skillopt-20260919T034426Z",
            "baseline_root": "experiments/core25-gpt52-representative-20260916",
            "job_search": [
                "experiments/core25-gpt52-representative-20260916/jobs/skillopt",
                "experiments/core25-gpt52-representative-20260916/jobs/baseline-original-skill",
                "experiments/core25-gpt52-skillopt-20260919T034426Z/jobs/skillopt",
                "experiments/core25-gpt52-skillopt-20260919T034426Z/jobs/baseline-original-skill",
            ],
            "original_pass_tasks": ["paratransit-routing"],
            "packaging_meta": {
                "source_run_id": "core25-gpt52-skillopt-20260919T034426Z",
                "baseline_run_id": "core25-gpt52-representative-20260916",
                "baseline_model": "openrouter/openai/gpt-5.2",
                "optimizer_model": "tatu/gpt-5.5@CODING_TATU",
                "params": {"n": 3, "L": 4, "R": 2},
                "gold_tasks": GOLD_TASKS,
                "original_pass_tasks": ["paratransit-routing"],
                "notes": [
                    "Official Gold subset only (7 tasks), not full Core-25.",
                    "paratransit-routing uses verified original_pass skip; no repaired_skill.",
                    "video-silence-remover both repair rounds reverted; repaired_skill/repaired_run are the last method-skill attempt that failed.",
                ],
            },
        }
    )

    package_method(
        {
            "folder": "SkillOpt-adapted-gpt55-n3L4R2-20260912",
            "method_id": "skillopt-adapted-gpt55-n3L4R2",
            "experiment": "experiments/core25-tatu-gpt55-20260912T095513Z",
            "baseline_root": "experiments/core25-tatu-gpt55-20260914T130130Z",
            "job_search": [
                "experiments/core25-tatu-gpt55-20260912T095513Z/jobs/skillopt",
                "experiments/core25-tatu-gpt55-20260912T095513Z/jobs/baseline-original-skill",
                "experiments/core25-tatu-gpt55-20260914T130130Z/jobs/baseline-original-skill",
                "experiments/core25-tatu-gpt55-20260906T123854Z/jobs/baseline-original-skill",
                "experiments/core25-tatu-gpt55-20260906T123854Z/jobs/skillopt",
            ],
            "original_pass_tasks": ["exoplanet-detection-period"],
            "packaging_meta": {
                "source_run_id": "core25-tatu-gpt55-20260912T095513Z",
                "baseline_run_id": "core25-tatu-gpt55-20260906T123854Z",
                "baseline_model": "tatu/gpt-5.5@CODING_TATU",
                "optimizer_model": "tatu/gpt-5.5@CODING_TATU",
                "params": {"n": 3, "L": 4, "R": 2},
                "gold_tasks": GOLD_TASKS,
                "original_pass_tasks": ["exoplanet-detection-period"],
                "notes": [
                    "Official Gold subset only (7 tasks).",
                    "Baseline original-skill reused from core25-tatu-gpt55-20260906T123854Z.",
                    "exoplanet-detection-period uses verified original_pass skip.",
                ],
            },
        }
    )


if __name__ == "__main__":
    main()
