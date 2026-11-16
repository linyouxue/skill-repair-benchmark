#!/usr/bin/env python3
"""Run the diagnosis-only stage of SkillOpt for one SkillsBench task."""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters.common.executor_api import write_json  # noqa: E402
from adapters.common.paths import SKILLOPT_ROOT, original_skill_bundle  # noqa: E402
from adapters.common.rewrite_engine import (  # noqa: E402
    diagnose_skills_once,
    load_evidence_bundle,
    load_task_context,
    skill_inventory,
)


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return data


def selected_run(archive: Path, task_id: str) -> Path:
    index = load_json(archive / "final_task_results.json")
    for row in index.get("tasks") or []:
        if isinstance(row, dict) and row.get("task_id") == task_id:
            if row.get("status") != "FAIL":
                raise ValueError(f"Expected selected Opus47 task to be FAIL: {task_id}")
            path = archive / str(row.get("path") or "")
            if not path.is_dir():
                raise FileNotFoundError(f"Selected run is missing: {path}")
            return path
    raise KeyError(f"Task is absent from Opus47 archive: {task_id}")


def compact_verifier(ctrf: dict[str, Any]) -> dict[str, Any]:
    results = ctrf.get("results") if isinstance(ctrf.get("results"), dict) else ctrf
    tests = results.get("tests") if isinstance(results, dict) else []
    failed = []
    for test in tests or []:
        if not isinstance(test, dict) or test.get("status") in {"passed", "skipped"}:
            continue
        failed.append(
            {
                key: test.get(key)
                for key in ("name", "status", "message", "trace", "file_path")
                if test.get(key) not in (None, "")
            }
        )
    return {
        "summary": results.get("summary") if isinstance(results, dict) else None,
        "failed_tests": failed,
    }


def tail_text(path: Path, limit: int) -> str:
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    return text[-limit:]


def build_evidence(run_dir: Path, destination: Path) -> Path:
    benchmark = load_json(run_dir / "benchmark_result.json")
    result = load_json(run_dir / "result.json") if (run_dir / "result.json").is_file() else {}
    ctrf = load_json(run_dir / "verifier" / "ctrf.json") if (run_dir / "verifier" / "ctrf.json").is_file() else {}
    agent_result = result.get("agent_result") if isinstance(result.get("agent_result"), dict) else {}
    evidence = {
        "task_passed": False,
        "error": benchmark.get("error") or result.get("error"),
        "summary": {
            "baseline_model": benchmark.get("model") or result.get("model"),
            "rollout_id": benchmark.get("rollout_id") or result.get("rollout_name"),
            "reward": benchmark.get("reward") or (result.get("rewards") or {}).get("reward"),
            "termination_reason": benchmark.get("termination_reason"),
            "n_tool_calls": result.get("n_tool_calls"),
            "n_skill_invocations": result.get("n_skill_invocations"),
            "trajectory_summary": result.get("trajectory_summary"),
            "agent_final_output": agent_result.get("final_output") or agent_result.get("output"),
        },
        "verifier_result": compact_verifier(ctrf),
        "stdout": tail_text(run_dir / "verifier" / "test-stdout.txt", 6000),
        "transcript": tail_text(run_dir / "trajectory" / "acp_trajectory.jsonl", 7000),
    }
    write_json(destination, evidence)
    return destination


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--baseline-archive", type=Path, required=True)
    args = parser.parse_args()

    workspace = ROOT / "experiments" / args.run_id / "diagnosis" / "skillopt" / args.task
    diagnosis_path = workspace / "diagnosis.json"
    if diagnosis_path.is_file():
        existing = load_json(diagnosis_path)
        if not existing.get("fallback_used"):
            print(f"[skip existing] {diagnosis_path}", flush=True)
            return 0

    workspace.mkdir(parents=True, exist_ok=True)
    baseline_run = selected_run(args.baseline_archive.resolve(), args.task)
    evidence_path = build_evidence(baseline_run, workspace / "opus47_baseline_evidence.json")
    source_type, context = load_evidence_bundle([("opus47_baseline_failure", evidence_path)])
    inventory = skill_inventory(original_skill_bundle(args.task))
    diagnosis = diagnose_skills_once(
        method_name="skillopt",
        method_root=SKILLOPT_ROOT,
        lite=False,
        task_id=args.task,
        workspace=workspace,
        inventory=inventory,
        task_context=load_task_context(args.task),
        baseline_source_type=source_type,
        baseline_context=context,
        run_id=args.run_id,
        repair_round=1,
        merge_samples=True,
    )
    write_json(
        workspace / "run_metadata.json",
        {
            "task_id": args.task,
            "run_id": args.run_id,
            "stage": "diagnosis-only",
            "method": "skillopt",
            "model": os.environ.get("TATU_MODEL") or os.environ.get("SKILLOPT_MODEL"),
            "baseline_run": str(baseline_run),
            "baseline_evidence": str(evidence_path),
            "created_at": datetime.now(UTC).isoformat(),
            "fallback_used": bool(diagnosis.get("fallback_used")),
        },
    )
    if diagnosis.get("fallback_used"):
        print(f"[fallback] {args.task}: {diagnosis.get('fallback_reason')}", file=sys.stderr, flush=True)
        return 2
    print(
        f"[ok] {args.task}: diagnosed={len(diagnosis.get('diagnosed_skills') or [])} "
        f"samples={diagnosis.get('diagnosis_n')}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
