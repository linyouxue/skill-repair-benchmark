#!/usr/bin/env python3
"""Run one controlled experiment with collision-safe environments and Skill proof.

The controlled-dataset organizer exports every task below a directory literally
named ``task``.  BenchFlow uses that basename when naming the Docker image, so
running those exports directly can reuse an image built for a different task.
This launcher stages the task under a unique, content-bound name and refuses to
accept a rollout unless the executor proves that the complete repaired Skill
bundle was preloaded into the model's persistent context.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): file_sha256(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def bundle_manifest(root: Path) -> dict:
    """Match the canonical benchmark executor's length-delimited bundle hash."""

    digest = hashlib.sha256()
    skill_files: list[str] = []
    file_count = 0
    total_bytes = 0
    for path in sorted(root.rglob("*"), key=lambda p: p.relative_to(root).as_posix()):
        if path.is_symlink():
            raise ValueError(f"Skill bundle contains a symlink: {path}")
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        body = path.read_bytes()
        encoded = relative.encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
        digest.update(len(body).to_bytes(8, "big"))
        digest.update(body)
        file_count += 1
        total_bytes += len(body)
        if path.name == "SKILL.md":
            body.decode("utf-8")
            skill_files.append(relative)
    if not skill_files:
        raise ValueError(f"Skill bundle contains no SKILL.md: {root}")
    return {
        "skill_bundle_sha256": f"sha256:{digest.hexdigest()}",
        "preloaded_skill_count": len(skill_files),
        "preloaded_skill_files": skill_files,
        "skill_bundle_file_count": file_count,
        "skill_bundle_bytes": total_bytes,
    }


def safe_name(value: str) -> str:
    value = re.sub(r"[^a-z0-9_.-]+", "-", value.lower()).strip("-._")
    return value or "controlled-task"


def apply_apt_portability_patch(dockerfile: Path) -> list[dict]:
    """Harden transient Debian/Ubuntu package downloads without changing the task."""

    if not dockerfile.is_file():
        return []
    text = dockerfile.read_text(encoding="utf-8")
    if "apt-get update" not in text:
        return []
    before = file_sha256(dockerfile)
    mirror_guard = (
        "RUN if [ \"$(id -u)\" = 0 ]; then "
        "find /etc/apt -type f \\( -name '*.list' -o -name '*.sources' \\) "
        "-exec sed -i "
        "-e 's|http://deb.debian.org|https://deb.debian.org|g' "
        "-e 's|http://archive.ubuntu.com|https://archive.ubuntu.com|g' "
        "-e 's|http://security.ubuntu.com|https://security.ubuntu.com|g' {} +; "
        "fi\n"
    )
    lines = text.splitlines(keepends=True)
    guarded_lines: list[str] = []
    for line in lines:
        guarded_lines.append(line)
        if line.lstrip().upper().startswith("FROM "):
            guarded_lines.append("\n" + mirror_guard)
    text = "".join(guarded_lines)
    text = text.replace(
        "FROM --platform=linux/amd64 ubuntu:20.04",
        "FROM --platform=linux/amd64 mirror.gcr.io/library/ubuntu:20.04",
    )
    if "AS auto" in text and "mirror.gcr.io/library/ubuntu:20.04 AS final" in text:
        text = text.replace(
            "FROM --platform=linux/amd64 mirror.gcr.io/library/ubuntu:20.04 AS final\n",
            "FROM --platform=linux/amd64 mirror.gcr.io/library/alpine:3.20 AS ca_bundle\n"
            "FROM --platform=linux/amd64 mirror.gcr.io/library/ubuntu:20.04 AS final\n"
            "COPY --from=ca_bundle /etc/ssl/certs/ca-certificates.crt "
            "/etc/ssl/certs/ca-certificates.crt\n",
            1,
        )
    options = (
        "-o Acquire::Retries=10 -o Acquire::http::Timeout=60 "
        "-o Acquire::https::Timeout=60"
    )
    text = text.replace("apt-get update", f"apt-get {options} update")
    text = text.replace("apt-get install", f"apt-get {options} install")
    dockerfile.write_text(text, encoding="utf-8")
    return [
        {
            "file": "environment/Dockerfile",
            "kind": "infrastructure_only",
            "change": "Docker Hub mirror for amd64 Ubuntu 20.04, CA bootstrap for legacy BugSwarm stages, HTTPS normalization, and bounded APT retries/timeouts",
            "reason": "Prevent transient mirror 502/connection failures from becoming task outcomes.",
            "before_sha256": before,
            "after_sha256": file_sha256(dockerfile),
        }
    ]


def find_result_files(jobs: Path) -> list[Path]:
    return sorted(jobs.glob("jobs/*/*/result.json"))


def executor_metadata(data: dict) -> dict:
    value = data.get("executor")
    return value if isinstance(value, dict) else {}


def audit_result(result_path: Path, expected: dict) -> dict:
    data = load_json(result_path)
    executor = executor_metadata(data)
    expected_sha = expected["skill_bundle_sha256"]
    expected_count = expected["preloaded_skill_count"]
    checks = {
        "skill_mode_with_skill": data.get("skill_mode") == "with-skill",
        "skill_source_custom_runtime": data.get("skill_source") == "custom_runtime",
        "skill_context_preloaded": executor.get("skill_context_preloaded") is True,
        "skill_context_preload_observed": executor.get(
            "skill_context_preload_observed"
        )
        is True,
        "skill_context_preload_matches_expected": executor.get(
            "skill_context_preload_matches_expected"
        )
        is True,
        "expected_bundle_sha256_matches": executor.get("skill_bundle_sha256")
        == expected_sha,
        "observed_bundle_sha256_matches": executor.get(
            "observed_skill_bundle_sha256"
        )
        == expected_sha,
        "expected_skill_count_matches": executor.get("preloaded_skill_count")
        == expected_count,
        "observed_skill_count_matches": executor.get(
            "observed_preloaded_skill_count"
        )
        == expected_count,
        "preloaded_skill_files_match": sorted(
            executor.get("preloaded_skill_files") or []
        )
        == sorted(expected["preloaded_skill_files"]),
    }
    return {
        "schema_version": 1,
        "result_file": str(result_path),
        "checks": checks,
        "valid": all(checks.values()),
        "expected_skill_bundle": expected,
        "observed_executor_metadata": {
            key: executor.get(key)
            for key in (
                "skill_exposure_mode",
                "skill_context_preloaded",
                "skill_bundle_sha256",
                "preloaded_skill_count",
                "preloaded_skill_files",
                "skill_context_preload_observed",
                "observed_skill_bundle_sha256",
                "observed_preloaded_skill_count",
                "skill_context_preload_matches_expected",
            )
        },
        "audited_at": now(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepared", required=True, type=Path)
    parser.add_argument("--jobs", required=True, type=Path)
    parser.add_argument("--agent", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--method")
    parser.add_argument("--repair-model")
    parser.add_argument("--bench", default="bench")
    parser.add_argument("--sandbox", default="docker")
    parser.add_argument("--reasoning-effort")
    parser.add_argument("--sandbox-user")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    prepared = args.prepared.resolve()
    jobs = args.jobs.resolve()
    if jobs.exists():
        raise ValueError(f"Jobs directory must be new: {jobs}")
    record = load_json(prepared / "RUN.json")
    expected_hashes = load_json(prepared / "PREPARED_SHA256.json")
    actual_hashes = tree_hashes(prepared)
    actual_hashes.pop("PREPARED_SHA256.json", None)
    if expected_hashes != actual_hashes:
        raise ValueError("Prepared evaluation checksum mismatch")
    if (record.get("task_dir"), record.get("skills_dir")) != ("task", "skills"):
        raise ValueError("Unexpected prepared directory layout")

    task_source = prepared / "task"
    skills_source = prepared / "skills"
    task_hashes = tree_hashes(task_source)
    skills = bundle_manifest(skills_source)
    experiment_id = prepared.name

    jobs.mkdir(parents=True)
    staging_root = jobs / "staged-task"
    staging_root.mkdir()
    pending_task = staging_root / ".pending"
    shutil.copytree(task_source, pending_task, symlinks=False)
    portability_patches = apply_apt_portability_patch(
        pending_task / "environment" / "Dockerfile"
    )
    staged_hashes = tree_hashes(pending_task)
    task_identity = hashlib.sha256(
        json.dumps(staged_hashes, sort_keys=True).encode("utf-8")
    ).hexdigest()
    unique_task_name = safe_name(
        f"controlled-{record['task_id']}-{experiment_id}-{task_identity[:12]}"
    )
    staged_task = staging_root / unique_task_name
    pending_task.rename(staged_task)
    staged_hashes = tree_hashes(staged_task)
    dockerfile = staged_task / "environment" / "Dockerfile"
    dockerfile_sha = file_sha256(dockerfile) if dockerfile.is_file() else None
    changed = {row["file"] for row in portability_patches}
    unexpected = [
        name for name, digest in task_hashes.items()
        if name not in changed and staged_hashes.get(name) != digest
    ]
    if unexpected or set(staged_hashes) != set(task_hashes):
        raise RuntimeError(f"Unexpected staged task changes: {unexpected}")

    preflight = {
        "schema_version": 1,
        "experiment_id": experiment_id,
        "task_id": record["task_id"],
        "trial_id": record.get("trial_id"),
        "condition": record.get("condition"),
        "unique_task_name": unique_task_name,
        "task_identity_sha256": task_identity,
        "dockerfile_sha256": dockerfile_sha,
        "prepared_task_hashes": task_hashes,
        "staged_task_hashes": staged_hashes,
        "portability_patches": portability_patches,
        "staged_task_integrity_verified": True,
        "skill_bundle": skills,
        "collision_guard": {
            "enabled": True,
            "strategy": "unique-task-basename-bound-to-task-id-experiment-id-and-tree-hash",
        },
        "created_at": now(),
    }
    write_json(jobs / "EXECUTION_PREFLIGHT.json", preflight)

    command = [
        args.bench,
        "eval",
        "run",
        "--tasks-dir",
        str(staged_task),
        "--agent",
        args.agent,
        "--model",
        args.model,
        "--sandbox",
        args.sandbox,
        "--skill-mode",
        "with-skill",
        "--skills-dir",
        str(skills_source),
        "--jobs-dir",
        str(jobs / "jobs"),
        "--expected-tasks",
        "1",
        "--concurrency",
        "1",
        "--loop-strategy",
        "single-shot",
    ]
    if args.reasoning_effort:
        command += ["--reasoning-effort", args.reasoning_effort]
    if args.sandbox_user:
        command += ["--sandbox-user", args.sandbox_user]
    run_record = {
        **record,
        "agent": args.agent,
        "model": args.model,
        "sandbox": args.sandbox,
        "method_id": args.method,
        "repair_model": args.repair_model,
        "command": command,
        "started_at": now(),
        "dry_run": args.dry_run,
        "bench_exit_code": None,
        "environment_collision_guard": preflight["collision_guard"],
        "unique_task_name": unique_task_name,
        **skills,
    }
    write_json(jobs / "RUN_RECORD.json", run_record)
    if args.dry_run:
        return 0

    with (jobs / "bench.stdout.txt").open("w", encoding="utf-8") as stdout, (
        jobs / "bench.stderr.txt"
    ).open("w", encoding="utf-8") as stderr:
        completed = subprocess.run(command, stdout=stdout, stderr=stderr, env=os.environ)
    run_record["bench_exit_code"] = completed.returncode
    run_record["finished_at"] = now()
    result_files = find_result_files(jobs)
    if completed.returncode == 0 and len(result_files) == 1:
        audit = audit_result(result_files[0], skills)
    else:
        audit = {
            "schema_version": 1,
            "valid": False,
            "error": "BenchFlow failed or did not produce exactly one result",
            "bench_exit_code": completed.returncode,
            "result_count": len(result_files),
            "audited_at": now(),
        }
    write_json(jobs / "EXECUTION_AUDIT.json", audit)
    run_record["execution_audit_valid"] = audit["valid"]
    write_json(jobs / "RUN_RECORD.json", run_record)
    if completed.returncode != 0:
        return completed.returncode
    if not audit["valid"]:
        print("Execution rejected: environment/Skill evidence audit failed", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
