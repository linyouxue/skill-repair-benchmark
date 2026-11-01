#!/usr/bin/env python3
"""Refresh deterministic code/config hashes for this isolated experiment."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


WORKSPACE = Path("/Users/elsie/Desktop/SkillOpt-eva")
RUN = WORKSPACE / "experiments/gpt52-skillopt-controlled-location-single-r2l5-v2-20261027"

SHARED_FILES = [
    "adapters/common/rewrite_engine.py",
    "adapters/common/bounded_edit.py",
    "adapters/common/repair_loop.py",
    "skill-repair-controlled-datasets-20261020/tools/runner.py",
    "skill-repair-controlled-datasets-20261020/SHA256SUMS.json",
    "skill-repair-benchmark/src/benchflow/rollout/__init__.py",
    "skill-repair-benchmark/src/benchflow/agents/registry.py",
    "skill-repair-benchmark/src/benchflow/sandbox/docker.py",
]

EXPERIMENT_FILES = [
    "protocol.json",
    "configs/trials.txt",
    "configs/controls.tsv",
]


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def tree_sha256(root: Path) -> str:
    """Hash relative path and bytes for every stable regular file in a tree."""
    digest = hashlib.sha256()
    paths = sorted(
        path for path in root.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix not in {".pyc", ".pyo"}
    )
    for path in paths:
        relative = path.relative_to(root).as_posix().encode("utf-8")
        body = path.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(body).to_bytes(8, "big"))
        digest.update(body)
    return digest.hexdigest()


def main() -> None:
    command_files = sorted(
        path for path in (RUN / "commands").iterdir()
        if path.is_file() and path.name != "refresh_code_snapshot.pyc"
    )
    files = {
        f"commands/{path.name}": file_sha256(path)
        for path in command_files
    }
    for relative in EXPERIMENT_FILES:
        files[relative] = file_sha256(RUN / relative)
    for relative in SHARED_FILES:
        files[f"shared/{relative}"] = file_sha256(WORKSPACE / relative)

    snapshot = {
        "schema_version": 2,
        "experiment_id": RUN.name,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "hash_algorithm": "sha256",
        "tree_hash_algorithm": "sha256(length(path),path,length(content),content) in sorted relative-path order; __pycache__/*.py[co] excluded",
        "files": dict(sorted(files.items())),
        "tree_digests": {
            "SkillOpt/skillopt": tree_sha256(WORKSPACE / "SkillOpt/skillopt"),
            "adapters/common": tree_sha256(WORKSPACE / "adapters/common"),
        },
        "isolation_note": "Hashes only. No legacy GPT-5.2 or Opus result artifact is imported into this experiment.",
    }
    (RUN / "code_snapshot.json").write_text(
        json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "files": len(snapshot["files"]),
        "tree_digests": len(snapshot["tree_digests"]),
        "out": str(RUN / "code_snapshot.json"),
    }, indent=2))


if __name__ == "__main__":
    main()
