#!/usr/bin/env python3
"""Import Core-25 GPT-5.2 representative Original-Skill runs into SkillOpt-eva layout.

Source (Lin Yuanjing archive):
  evaluation/results/GPT52-AllTasks-RepresentativeRuns-20260916/tasks/<task>/

Destination (this repo):
  experiments/<run-id>/
    baseline/original-skill/<task>/benchmark_result.json
    baseline/original-skill/<task>/rollout_pointer.json
    baseline/original-skill/<task>/run_selection.json
    baseline/original-skill/<task>/SOURCE.json
    jobs/baseline-original-skill/<rollout_id>/   # selected_run payload
    metadata.json
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = Path(
    "/tmp/skill-repair-rep-runs/evaluation/results/GPT52-AllTasks-RepresentativeRuns-20260916"
)
DEFAULT_RUN_ID = "core25-gpt52-representative-20260916"
SOURCE_REPO = (
    "https://github.com/linyouxue/skill-repair-benchmark/tree/main/"
    "evaluation/results/GPT52-AllTasks-RepresentativeRuns-20260916"
)


def load_task_ids(path: Path) -> list[str]:
    return [
        ln.strip()
        for ln in path.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.startswith("#")
    ]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_status_map(status_csv: Path) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    if not status_csv.is_file():
        return out
    with status_csv.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            tid = (row.get("task_id") or "").strip()
            if tid:
                out[tid] = row
    return out


def _reward_passed(selected: Path, selection: dict[str, Any], status_row: dict[str, str] | None) -> tuple[bool, float | None]:
    if "task_passed" in selection and selection["task_passed"] is not None:
        reward = selection.get("reward")
        return bool(selection["task_passed"]), float(reward) if reward is not None else None
    pf = (status_row or {}).get("pf", "").strip().upper()
    if pf in {"PASS", "FAIL"}:
        return pf == "PASS", 1.0 if pf == "PASS" else 0.0
    reward_txt = selected / "verifier" / "reward.txt"
    if reward_txt.is_file():
        raw = reward_txt.read_text(encoding="utf-8").strip().splitlines()
        if raw:
            try:
                val = float(raw[-1].strip())
                return val >= 1.0, val
            except ValueError:
                pass
    result = selected / "result.json"
    if result.is_file():
        data = json.loads(result.read_text(encoding="utf-8"))
        rewards = data.get("rewards")
        if isinstance(rewards, dict):
            for key in ("reward", "score", "task_passed"):
                if key in rewards:
                    val = rewards[key]
                    if isinstance(val, bool):
                        return val, 1.0 if val else 0.0
                    try:
                        f = float(val)
                        return f >= 1.0, f
                    except (TypeError, ValueError):
                        pass
        if isinstance(rewards, list) and rewards:
            last = rewards[-1]
            if isinstance(last, dict) and "reward" in last:
                f = float(last["reward"])
                return f >= 1.0, f
            try:
                f = float(last)
                return f >= 1.0, f
            except (TypeError, ValueError):
                pass
    return False, None


def synthesize_benchmark_result(
    *,
    task_id: str,
    selected: Path,
    selection: dict[str, Any],
    status_row: dict[str, str] | None,
    local_rollout_dir: Path,
) -> dict[str, Any]:
    """Build a SkillOpt-eva-shaped benchmark_result when upstream lacks one."""
    passed, reward = _reward_passed(selected, selection, status_row)
    result_json = selected / "result.json"
    timing = {}
    if (selected / "timing.json").is_file():
        timing = json.loads((selected / "timing.json").read_text(encoding="utf-8"))
    result_data: dict[str, Any] = {}
    if result_json.is_file():
        result_data = json.loads(result_json.read_text(encoding="utf-8"))
    rollout_id = (
        selection.get("rollout_id")
        or result_data.get("rollout_name")
        or f"{task_id}-representative"
    )
    model = selection.get("model") or result_data.get("model") or "openrouter/openai/gpt-5.2"
    return {
        "task_id": task_id,
        "rollout_id": rollout_id,
        "method_id": "baseline-original-skill",
        "stage": "original-skill",
        "protocol_id": "skillrepair-v1",
        "model": model,
        "provider_route": "openrouter" if "openrouter" in str(model) else None,
        "provider_base_url": "https://openrouter.ai/api/v1" if "openrouter" in str(model) else None,
        "provider_protocol": "openai-completions",
        "reasoning_effort": None,
        "task_passed": passed,
        "execution_ok": bool(result_data.get("error") is None) if result_data else True,
        "comparable": True,
        "reward": reward if reward is not None else (1.0 if passed else 0.0),
        "agent_iterations": result_data.get("n_prompts") or result_data.get("n_tool_calls"),
        "provider_requests": result_data.get("n_prompts"),
        "wall_time_sec": timing.get("wall_time_sec") or timing.get("total_sec"),
        "cost_usd": None,
        "termination_reason": "end_turn" if passed else (result_data.get("error_category") or "task_failed"),
        "error": result_data.get("error"),
        "error_category": result_data.get("error_category"),
        "verifier_error": result_data.get("verifier_error"),
        "verifier_error_category": result_data.get("verifier_error_category"),
        "export_error": result_data.get("export_error"),
        "protocol_evidence_valid": True,
        "trajectory_complete": True,
        "iteration_accounting_complete": True,
        "skill_exposure_verified": True,
        "rollout_dir": str(local_rollout_dir),
        "result_json": str(result_json) if result_json.is_file() else None,
        "imported_from": "GPT52-AllTasks-RepresentativeRuns-20260916",
        "upstream_method_id": selection.get("method_id"),
        "upstream_stage": selection.get("stage") or selection.get("condition"),
        "selection_reason": selection.get("selection_reason"),
    }


def normalize_benchmark_result(
    raw: dict[str, Any],
    *,
    task_id: str,
    local_rollout_dir: Path,
    selection: dict[str, Any],
) -> dict[str, Any]:
    out = dict(raw)
    out["task_id"] = task_id
    out["method_id"] = "baseline-original-skill"
    out["stage"] = "original-skill"
    out["rollout_dir"] = str(local_rollout_dir)
    # Point result_json at the local copy when present.
    local_result = local_rollout_dir / "result.json"
    if local_result.is_file():
        out["result_json"] = str(local_result)
    out["imported_from"] = "GPT52-AllTasks-RepresentativeRuns-20260916"
    out["upstream_method_id"] = raw.get("method_id")
    out["upstream_stage"] = raw.get("stage")
    out["upstream_rollout_dir"] = raw.get("rollout_dir")
    out["selection_reason"] = selection.get("selection_reason")
    if "protocol_id" not in out or not out["protocol_id"]:
        out["protocol_id"] = "skillrepair-v1"
    return out


def import_task(
    *,
    task_id: str,
    source_root: Path,
    run_dir: Path,
    status_row: dict[str, str] | None,
) -> dict[str, Any]:
    task_src = source_root / "tasks" / task_id
    selected = task_src / "selected_run"
    if not selected.is_dir():
        raise FileNotFoundError(f"missing selected_run for {task_id}: {selected}")

    selection_path = task_src / "run_selection.json"
    selection = json.loads(selection_path.read_text(encoding="utf-8")) if selection_path.is_file() else {}
    rollout_id = selection.get("rollout_id") or f"{task_id}-representative"
    job_dir = run_dir / "jobs" / "baseline-original-skill" / str(rollout_id)
    if job_dir.exists():
        shutil.rmtree(job_dir)
    shutil.copytree(selected, job_dir, symlinks=False)

    baseline_dir = run_dir / "baseline" / "original-skill" / task_id
    baseline_dir.mkdir(parents=True, exist_ok=True)

    upstream_br = selected / "benchmark_result.json"
    if upstream_br.is_file():
        raw = json.loads(upstream_br.read_text(encoding="utf-8"))
        # Prefer selection's rollout_id when present.
        if selection.get("rollout_id"):
            raw["rollout_id"] = selection["rollout_id"]
        br = normalize_benchmark_result(
            raw, task_id=task_id, local_rollout_dir=job_dir, selection=selection
        )
        synthesized = False
    else:
        br = synthesize_benchmark_result(
            task_id=task_id,
            selected=selected,
            selection=selection,
            status_row=status_row,
            local_rollout_dir=job_dir,
        )
        synthesized = True

    # Keep local job copy of benchmark_result in sync with normalized one.
    write_json(job_dir / "benchmark_result.json", br)
    write_json(baseline_dir / "benchmark_result.json", br)
    write_json(
        baseline_dir / "rollout_pointer.json",
        {"method_id": "baseline-original-skill", "rollout_id": br["rollout_id"]},
    )
    if selection_path.is_file():
        shutil.copy2(selection_path, baseline_dir / "run_selection.json")
    write_json(
        baseline_dir / "SOURCE.json",
        {
            "source_archive": "GPT52-AllTasks-RepresentativeRuns-20260916",
            "source_repo_path": SOURCE_REPO,
            "task_id": task_id,
            "rollout_id": br["rollout_id"],
            "status_csv_pf": (status_row or {}).get("pf"),
            "synthesized_benchmark_result": synthesized,
            "imported_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
    )
    return {
        "task_id": task_id,
        "task_passed": bool(br.get("task_passed")),
        "rollout_id": br["rollout_id"],
        "synthesized": synthesized,
        "model": br.get("model"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument(
        "--tasks-file",
        type=Path,
        default=ROOT / "configs" / "core25_tasks.txt",
        help="Exact task allowlist to import.",
    )
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--force", action="store_true", help="Replace existing run-id directory.")
    args = parser.parse_args()

    source = args.source.resolve()
    if not source.is_dir():
        raise SystemExit(f"source not found: {source}")

    run_dir = ROOT / "experiments" / args.run_id
    if run_dir.exists():
        if not args.force:
            raise SystemExit(f"run already exists (pass --force to replace): {run_dir}")
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True)

    status_map = load_status_map(source / "STATUS.csv")
    # Keep a slim copy of archive docs for provenance.
    docs = run_dir / "source_archive"
    docs.mkdir(parents=True)
    for name in (
        "README.md",
        "STATUS.csv",
        "VALIDATION.json",
        "MANIFEST.json",
        "EXCLUDED_RUNS.json",
    ):
        src = source / name
        if src.is_file():
            shutil.copy2(src, docs / name)

    tasks = load_task_ids(args.tasks_file.resolve())
    rows: list[dict[str, Any]] = []
    for task_id in tasks:
        info = import_task(
            task_id=task_id,
            source_root=source,
            run_dir=run_dir,
            status_row=status_map.get(task_id),
        )
        rows.append(info)
        print(
            f"[import] {task_id}: passed={info['task_passed']} "
            f"synth={info['synthesized']} rollout={info['rollout_id']}"
        )

    passed = sum(1 for r in rows if r["task_passed"])
    write_json(
        run_dir / "metadata.json",
        {
            "run_id": args.run_id,
            "kind": "imported-baseline",
            "model": "openrouter/openai/gpt-5.2",
            "condition": "original-skill",
            "source": SOURCE_REPO,
            "source_local": str(source),
            "task_count": len(rows),
            "pass_count": passed,
            "fail_count": len(rows) - passed,
            "synthesized_benchmark_result_tasks": [r["task_id"] for r in rows if r["synthesized"]],
            "imported_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "tasks": rows,
        },
    )
    print(f"run_id={args.run_id} pass={passed}/{len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
