#!/usr/bin/env python3
"""Import selected Opus47 Original-Skill failures into an experiment run."""
from __future__ import annotations

import argparse
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return data


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_tasks(path: Path) -> list[str]:
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def clipped(value: Any, limit: int = 1200) -> Any:
    if isinstance(value, str):
        return value[:limit]
    return value


def compact_verifier(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    ctrf = load_json(path)
    results = ctrf.get("results") if isinstance(ctrf.get("results"), dict) else ctrf
    tests = results.get("tests") if isinstance(results, dict) else []
    failed: list[dict[str, Any]] = []
    for test in tests or []:
        if not isinstance(test, dict) or test.get("status") in {"passed", "skipped"}:
            continue
        failed.append(
            {
                key: clipped(test.get(key))
                for key in ("name", "status", "message", "trace", "file_path")
                if test.get(key) not in (None, "")
            }
        )
        if len(failed) >= 8:
            break
    return {
        "summary": results.get("summary") if isinstance(results, dict) else None,
        "failed_tests": failed,
    }


def tail(path: Path, limit: int) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")[-limit:]


def enrich_result(source_run: Path, local_run: Path, task_id: str) -> dict[str, Any]:
    raw = load_json(source_run / "benchmark_result.json")
    result = load_json(source_run / "result.json") if (source_run / "result.json").is_file() else {}
    agent_result = result.get("agent_result") if isinstance(result.get("agent_result"), dict) else {}
    out = dict(raw)
    out.update(
        {
            "task_id": task_id,
            "method_id": "baseline-original-skill",
            "stage": "original-skill",
            "task_passed": False,
            "comparable": True,
            "rollout_dir": str(local_run),
            "result_json": str(local_run / "result.json"),
            "imported_from": "Opus47-OriginalSkill-79Tasks-20260920",
            "summary": {
                "baseline_model": raw.get("model") or result.get("model"),
                "reward": raw.get("reward") or (result.get("rewards") or {}).get("reward"),
                "termination_reason": raw.get("termination_reason"),
                "n_tool_calls": result.get("n_tool_calls"),
                "n_skill_invocations": result.get("n_skill_invocations"),
                "trajectory_summary": result.get("trajectory_summary"),
                "agent_final_output": clipped(
                    agent_result.get("final_output") or agent_result.get("output"), 3000
                ),
            },
            "verifier_result": compact_verifier(source_run / "verifier" / "ctrf.json"),
            "transcript": tail(source_run / "trajectory" / "acp_trajectory.jsonl", 5000),
            "stdout": tail(source_run / "verifier" / "test-stdout.txt", 3000),
        }
    )
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--tasks-file", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()

    source = args.source.resolve()
    run_dir = ROOT / "experiments" / args.run_id
    if run_dir.exists():
        raise SystemExit(f"Refusing to overwrite existing run: {run_dir}")

    index = load_json(source / "final_task_results.json")
    by_task = {
        str(row.get("task_id")): row
        for row in index.get("tasks") or []
        if isinstance(row, dict) and row.get("task_id")
    }
    tasks = load_tasks(args.tasks_file)
    rows: list[dict[str, Any]] = []
    for task_id in tasks:
        row = by_task.get(task_id)
        if not row:
            raise KeyError(f"Task absent from Opus47 archive: {task_id}")
        if row.get("status") != "FAIL":
            raise ValueError(f"Task is not an Opus47 failure: {task_id} ({row.get('status')})")
        source_run = (source / str(row["path"])).resolve()
        rollout_id = str(row["rollout_id"])
        local_run = run_dir / "jobs" / "baseline-original-skill" / rollout_id
        local_run.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source_run, local_run, symlinks=False)

        baseline_dir = run_dir / "baseline" / "original-skill" / task_id
        result = enrich_result(source_run, local_run, task_id)
        write_json(baseline_dir / "benchmark_result.json", result)
        write_json(
            baseline_dir / "rollout_pointer.json",
            {"method_id": "baseline-original-skill", "rollout_id": rollout_id},
        )
        write_json(
            baseline_dir / "SOURCE.json",
            {
                "source_archive": str(source),
                "task_id": task_id,
                "rollout_id": rollout_id,
                "status": "FAIL",
                "imported_at": datetime.now(UTC).isoformat(),
            },
        )
        rows.append({"task_id": task_id, "rollout_id": rollout_id, "task_passed": False})
        print(f"[import] {task_id}: FAIL {rollout_id}", flush=True)

    docs = run_dir / "source_archive"
    docs.mkdir(parents=True, exist_ok=True)
    for name in (
        "README.md",
        "summary.json",
        "final_task_results.json",
        "PUBLICATION_VALIDATION.json",
        "FILE_MANIFEST.json",
        "claude_protocol.json",
    ):
        src = source / name
        if src.is_file():
            shutil.copy2(src, docs / name)

    write_json(
        run_dir / "metadata.json",
        {
            "run_id": args.run_id,
            "kind": "opus47-baseline-plus-skillopt",
            "baseline_model": "openrouter/anthropic/claude-opus-4.7",
            "optimizer_model": "claude-opus-4-7",
            "benchmark_model": "tatu/claude-opus-4-7",
            "task_count": len(rows),
            "baseline_fail_count": len(rows),
            "tasks": rows,
            "created_at": datetime.now(UTC).isoformat(),
        },
    )
    print(f"run_id={args.run_id} imported={len(rows)} failures", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
