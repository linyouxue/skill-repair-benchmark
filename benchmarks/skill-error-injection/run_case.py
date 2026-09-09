#!/usr/bin/env python3
"""Check and run the published defective Skill cases."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from benchflow.benchmark_executor import build_skill_bundle_manifest
from benchmark_executor import BenchmarkExecutor

PACKAGE_ROOT = Path(__file__).resolve().parent
DEFAULT_MANIFEST = PACKAGE_ROOT / "manifest.json"


def load_manifest(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != "skill-repair-benchmark.injected-skills.v1":
        raise ValueError(f"unsupported manifest schema: {payload.get('schema')!r}")
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("manifest must contain a non-empty cases list")
    case_ids = [case.get("case_id") for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("manifest contains duplicate case_id values")
    return payload


def case_map(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {case["case_id"]: case for case in manifest["cases"]}


def bundle_path(case: dict[str, Any]) -> Path:
    candidate = (PACKAGE_ROOT / case["skills_dir"]).resolve(strict=True)
    if not candidate.is_relative_to(PACKAGE_ROOT):
        raise ValueError(f"skills_dir escapes package root: {case['skills_dir']}")
    return candidate


def command_list(manifest: dict[str, Any]) -> int:
    print("case_id\ttask_id\tcategory\tvalidation")
    for case in manifest["cases"]:
        print(
            f"{case['case_id']}\t{case['task_id']}\t"
            f"{case['category']}\t{case['validation']}"
        )
    return 0


def command_check(manifest: dict[str, Any]) -> int:
    rows = []
    for case in manifest["cases"]:
        path = bundle_path(case)
        bundle = build_skill_bundle_manifest(path)
        observed_sha256 = f"sha256:{bundle.sha256}"
        if observed_sha256 != case["skill_bundle_sha256"]:
            raise ValueError(
                f"bundle digest mismatch for {case['case_id']}: "
                f"expected {case['skill_bundle_sha256']}, got {observed_sha256}"
            )
        rows.append(
            {
                "case_id": case["case_id"],
                "task_id": case["task_id"],
                "skill_bundle_sha256": observed_sha256,
                "file_count": bundle.file_count,
                "total_bytes": bundle.total_bytes,
            }
        )
    print(json.dumps({"ok": True, "cases": rows}, ensure_ascii=False, indent=2))
    return 0


def required_value(value: str | None, *, option: str, env_name: str) -> str:
    resolved = (value or os.environ.get(env_name, "")).strip()
    if not resolved:
        raise ValueError(f"{option} is required; it may also be set with {env_name}")
    return resolved


def command_run(args: argparse.Namespace, manifest: dict[str, Any]) -> int:
    cases = case_map(manifest)
    if args.case not in cases:
        raise ValueError(f"unknown case_id: {args.case}")
    case = cases[args.case]

    tasks_root = required_value(
        args.tasks_root, option="--tasks-root", env_name="SKILLSBENCH_TASKS_ROOT"
    )
    jobs_root = required_value(
        args.jobs_root, option="--jobs-root", env_name="BENCHMARK_JOBS_ROOT"
    )
    model = required_value(
        args.model, option="--model", env_name="BENCHMARK_MODEL"
    )
    reasoning_effort = (
        args.reasoning_effort
        if args.reasoning_effort is not None
        else os.environ.get("BENCHMARK_REASONING_EFFORT", "")
    ).strip() or None

    if args.condition == "defective":
        condition = "method-skill"
        skills = bundle_path(case)
    elif args.condition == "repaired":
        if args.skills_dir is None:
            raise ValueError("--condition repaired requires --skills-dir")
        condition = "method-skill"
        skills = args.skills_dir.expanduser().resolve(strict=True)
    else:
        if args.skills_dir is not None:
            raise ValueError("--condition original does not accept --skills-dir")
        condition = "original-skill"
        skills = None

    executor = BenchmarkExecutor(
        tasks_root=tasks_root,
        jobs_root=jobs_root,
        model=model,
        reasoning_effort=reasoning_effort,
        verifier_proxy_mode=args.verifier_proxy_mode,
    )
    result = executor.run(
        task_id=case["task_id"],
        condition=condition,
        method_id=args.method_id,
        stage=f"skill-error-injection-{args.condition}",
        rollout_id=args.rollout_id,
        skill_bundle=skills,
    )
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0 if result.execution_ok else 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list")
    subparsers.add_parser("check")

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--case", required=True)
    run_parser.add_argument(
        "--condition", choices=("defective", "repaired", "original"), required=True
    )
    run_parser.add_argument("--skills-dir", type=Path)
    run_parser.add_argument("--tasks-root")
    run_parser.add_argument("--jobs-root")
    run_parser.add_argument("--model")
    run_parser.add_argument("--reasoning-effort")
    run_parser.add_argument(
        "--verifier-proxy-mode", choices=("off", "inherit", "explicit"), default="off"
    )
    run_parser.add_argument("--method-id", default="skill-error-injection")
    run_parser.add_argument("--rollout-id", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = load_manifest(args.manifest.resolve(strict=True))
    if args.command == "list":
        return command_list(manifest)
    if args.command == "check":
        return command_check(manifest)
    return command_run(args, manifest)


if __name__ == "__main__":
    raise SystemExit(main())
