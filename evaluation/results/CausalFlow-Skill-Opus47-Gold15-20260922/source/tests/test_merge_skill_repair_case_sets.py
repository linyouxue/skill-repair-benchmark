from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from repro_wrappers.defects.merge_skill_repair_case_sets import (
    CaseMergeError,
    merge_case_sets,
)


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _case_set(tmp_path: Path, case_id: str) -> tuple[Path, Path]:
    root = tmp_path / case_id
    case_dir = root / "cases" / case_id
    skill = case_dir / "bundle" / "skill-a" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("# Skill\n", encoding="utf-8")
    digest = hashlib.sha256(skill.read_bytes()).hexdigest()
    case = {
        "schema": "causalflow.skill-repair-case.v1",
        "case_id": case_id,
        "inputs": {"defective_bundle": "bundle"},
        "integrity": {
            "payload_sha256": {"bundle/skill-a/SKILL.md": digest}
        },
    }
    _write_json(case_dir / "case.json", case)
    public = {
        "schema": "causalflow.skill-repair-public-registry.v1",
        "skillsbench_commit": "abc",
        "protocol_id": "skillrepair-v1",
        "model": "openrouter/openai/gpt-5.2",
        "case_count": 1,
        "cases": [{"case_id": case_id, "case": f"cases/{case_id}/case.json"}],
    }
    public_path = root / "registry.json"
    _write_json(public_path, public)
    private_path = tmp_path / f"{case_id}.private.json"
    private = {
        "schema": "causalflow.skill-repair-private-registry.v1",
        "public_registry_sha256": hashlib.sha256(public_path.read_bytes()).hexdigest(),
        "cases": [{"case_id": case_id, "variant_id": f"private-{case_id}"}],
    }
    _write_json(private_path, private)
    return public_path, private_path


def test_merge_verified_case_sets(tmp_path: Path):
    public_a, private_a = _case_set(tmp_path, "dsr-000000000001")
    public_b, private_b = _case_set(tmp_path, "dsr-000000000002")
    output_root = tmp_path / "combined"
    output_private = tmp_path / "combined.private.json"

    public, private = merge_case_sets(
        public_registries=[public_a, public_b],
        private_registries=[private_a, private_b],
        public_root=output_root,
        private_registry_path=output_private,
    )

    assert public["case_count"] == 2
    assert len(private["cases"]) == 2
    assert (output_root / "cases" / "dsr-000000000001" / "case.json").is_file()
    assert private["public_registry_sha256"] == hashlib.sha256(
        (output_root / "registry.json").read_bytes()
    ).hexdigest()


def test_merge_rejects_duplicate_case_ids(tmp_path: Path):
    public_a, private_a = _case_set(tmp_path / "a", "dsr-000000000001")
    public_b, private_b = _case_set(tmp_path / "b", "dsr-000000000001")

    with pytest.raises(CaseMergeError, match="duplicate case_id"):
        merge_case_sets(
            public_registries=[public_a, public_b],
            private_registries=[private_a, private_b],
            public_root=tmp_path / "combined",
            private_registry_path=tmp_path / "combined.private.json",
        )


def test_merge_cli_imports_workspace_package_outside_repo(tmp_path: Path):
    workspace = Path(__file__).resolve().parents[1]
    script = workspace / "repro_wrappers" / "defects" / "merge_skill_repair_case_sets.py"

    completed = subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "--public-registry" in completed.stdout
