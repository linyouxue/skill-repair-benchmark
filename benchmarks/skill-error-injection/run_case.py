#!/usr/bin/env python3
"""Check and run the published defective Skill cases."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tempfile
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


def overlay_root(case: dict[str, Any]) -> Path:
    candidate = (PACKAGE_ROOT / "cases" / case["case_id"] / "overlay").resolve(
        strict=True
    )
    if not candidate.is_relative_to(PACKAGE_ROOT):
        raise ValueError(f"overlay escapes package root: {case['case_id']}")
    return candidate


def validated_overlay_files(case: dict[str, Any]) -> list[tuple[Path, Path]]:
    root = overlay_root(case)
    declared = case.get("files")
    if not isinstance(declared, list) or not declared:
        raise ValueError(f"case has no changed files: {case['case_id']}")

    rows: list[tuple[Path, Path]] = []
    declared_paths: set[str] = set()
    for item in declared:
        relative = Path(item["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"invalid changed file path: {relative}")
        relative_text = relative.as_posix()
        if relative_text in declared_paths:
            raise ValueError(f"duplicate changed file path: {relative_text}")
        declared_paths.add(relative_text)

        source = (root / relative).resolve(strict=True)
        if not source.is_relative_to(root) or not source.is_file() or source.is_symlink():
            raise ValueError(f"invalid changed file: {relative_text}")
        observed_sha256 = f"sha256:{hashlib.sha256(source.read_bytes()).hexdigest()}"
        if observed_sha256 != item["sha256"]:
            raise ValueError(
                f"file digest mismatch for {case['case_id']}/{relative_text}: "
                f"expected {item['sha256']}, got {observed_sha256}"
            )
        rows.append((relative, source))

    observed_paths = {
        path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()
    }
    if observed_paths != declared_paths:
        raise ValueError(
            f"changed file list mismatch for {case['case_id']}: "
            f"expected {sorted(declared_paths)}, got {sorted(observed_paths)}"
        )
    return rows


def task_skills_path(tasks_root: Path, task_id: str) -> Path:
    root = tasks_root.expanduser().resolve(strict=True)
    task = root if root.name == task_id else (root / task_id).resolve(strict=True)
    if task != root and not task.is_relative_to(root):
        raise ValueError(f"task escapes tasks root: {task_id}")
    skills = (task / "environment" / "skills").resolve(strict=True)
    if not skills.is_dir():
        raise ValueError(f"original Skill directory is missing: {skills}")
    return skills


def materialize_bundle(
    case: dict[str, Any], tasks_root: Path, output: Path
) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing output: {output}")
    original = task_skills_path(tasks_root, case["task_id"])
    shutil.copytree(original, output)
    for relative, source in validated_overlay_files(case):
        target = output / relative
        if not target.is_file():
            raise ValueError(f"changed file is absent from original bundle: {relative}")
        shutil.copy2(source, target)

    bundle = build_skill_bundle_manifest(output)
    observed_sha256 = f"sha256:{bundle.sha256}"
    if observed_sha256 != case["full_skill_bundle_sha256"]:
        raise ValueError(
            f"materialized bundle digest mismatch for {case['case_id']}: "
            f"expected {case['full_skill_bundle_sha256']}, got {observed_sha256}. "
            "Check the SkillsBench commit."
        )
    return bundle.to_metadata()


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
        files = validated_overlay_files(case)
        rows.append(
            {
                "case_id": case["case_id"],
                "task_id": case["task_id"],
                "changed_files": [relative.as_posix() for relative, _ in files],
                "full_skill_bundle_sha256": case["full_skill_bundle_sha256"],
            }
        )
    print(json.dumps({"ok": True, "cases": rows}, ensure_ascii=False, indent=2))
    return 0


def required_value(value: str | None, *, option: str, env_name: str) -> str:
    resolved = (value or os.environ.get(env_name, "")).strip()
    if not resolved:
        raise ValueError(f"{option} is required; it may also be set with {env_name}")
    return resolved


def selected_case(args: argparse.Namespace, manifest: dict[str, Any]) -> dict[str, Any]:
    cases = case_map(manifest)
    if args.case not in cases:
        raise ValueError(f"unknown case_id: {args.case}")
    return cases[args.case]


def command_materialize(args: argparse.Namespace, manifest: dict[str, Any]) -> int:
    case = selected_case(args, manifest)
    tasks_root = Path(
        required_value(
            args.tasks_root,
            option="--tasks-root",
            env_name="SKILLSBENCH_TASKS_ROOT",
        )
    )
    output = args.output.expanduser().resolve()
    metadata = materialize_bundle(case, tasks_root, output)
    print(
        json.dumps(
            {"ok": True, "case_id": case["case_id"], "output": str(output), **metadata},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def execute_case(
    args: argparse.Namespace,
    case: dict[str, Any],
    *,
    tasks_root: str,
    skills: Path | None,
    condition: str,
) -> int:

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


def command_run(args: argparse.Namespace, manifest: dict[str, Any]) -> int:
    case = selected_case(args, manifest)
    tasks_root = required_value(
        args.tasks_root, option="--tasks-root", env_name="SKILLSBENCH_TASKS_ROOT"
    )

    if args.condition == "defective":
        with tempfile.TemporaryDirectory(prefix=f"{case['case_id']}-") as temporary:
            skills = Path(temporary) / "skills"
            materialize_bundle(case, Path(tasks_root), skills)
            return execute_case(
                args,
                case,
                tasks_root=tasks_root,
                skills=skills,
                condition="method-skill",
            )
    if args.condition == "repaired":
        if args.skills_dir is None:
            raise ValueError("--condition repaired requires --skills-dir")
        skills = args.skills_dir.expanduser().resolve(strict=True)
        return execute_case(
            args,
            case,
            tasks_root=tasks_root,
            skills=skills,
            condition="method-skill",
        )
    if args.skills_dir is not None:
        raise ValueError("--condition original does not accept --skills-dir")
    return execute_case(
        args,
        case,
        tasks_root=tasks_root,
        skills=None,
        condition="original-skill",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list")
    subparsers.add_parser("check")

    materialize_parser = subparsers.add_parser("materialize")
    materialize_parser.add_argument("--case", required=True)
    materialize_parser.add_argument("--tasks-root")
    materialize_parser.add_argument("--output", type=Path, required=True)

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
    if args.command == "materialize":
        return command_materialize(args, manifest)
    return command_run(args, manifest)


if __name__ == "__main__":
    raise SystemExit(main())
