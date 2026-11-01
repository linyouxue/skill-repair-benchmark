#!/usr/bin/env python3
"""GPT-5.2 SkillOpt adapter for isolated controlled location/single trials."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
PACKAGE_TOOLS = ROOT / "skill-repair-controlled-datasets-20261020" / "tools"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(PACKAGE_TOOLS))

from runner import (  # noqa: E402
    fresh_directory,
    hashes,
    inside,
    outside_directory,
    validate_candidate,
    validate_export,
    write_json,
)
from adapters.common.rewrite_engine import rewrite_bundle_once  # noqa: E402
from adapters.common.repair_loop import (  # noqa: E402
    diagnosis_sample_count,
    edit_budget_l,
    repair_rounds_r,
)


METHOD_ID = "skillopt-controlled-oracle-hint-r2l5-v2"
EXPECTED_MODEL = "openai/gpt-5.2"


def assert_gpt52_environment() -> None:
    values = {
        "MODEL_PROVIDER": os.environ.get("MODEL_PROVIDER", ""),
        "SKILLOPT_MODEL": os.environ.get("SKILLOPT_MODEL", ""),
        "BENCHMARK_MODEL": os.environ.get("BENCHMARK_MODEL", ""),
    }
    if values != {
        "MODEL_PROVIDER": "ai360",
        "SKILLOPT_MODEL": EXPECTED_MODEL,
        "BENCHMARK_MODEL": "ai360/openai/gpt-5.2",
    }:
        raise RuntimeError(f"Refusing non-GPT-5.2 controlled environment: {values!r}")
    lowered = json.dumps(dict(os.environ), ensure_ascii=False).lower()
    for forbidden in ("claude-opus", "opus-4", "tatu/claude"):
        if forbidden in lowered:
            raise RuntimeError(f"Forbidden Opus marker remains in environment: {forbidden}")
    if os.environ.get("SKILLOPT_EVA_SHARED_DIAGNOSIS") != "0":
        raise RuntimeError("Controlled trials require SKILLOPT_EVA_SHARED_DIAGNOSIS=0")
    if os.environ.get("SKILLOPT_EVA_DIAGNOSIS_SOURCE_RUN"):
        raise RuntimeError("Cross-run diagnosis reuse is forbidden")
    controlled_knobs = {
        "diagnosis_n": diagnosis_sample_count(),
        "edit_budget_l": edit_budget_l(),
        "repair_rounds_r": repair_rounds_r(),
    }
    if controlled_knobs != {
        "diagnosis_n": 3,
        "edit_budget_l": 5,
        "repair_rounds_r": 2,
    }:
        raise RuntimeError(f"Refusing unexpected R2L5 configuration: {controlled_knobs!r}")


def bundle_digest(root: Path) -> str:
    payload = json.dumps(hashes(root), sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request_json")
    parser.add_argument("output_directory")
    args = parser.parse_args(argv)

    assert_gpt52_environment()
    request_file = Path(args.request_json).resolve()
    exported = request_file.parent
    request = validate_export(exported)
    if request_file != exported / "request.json":
        raise ValueError("Expected the validated exported request.json")

    output = Path(args.output_directory).resolve()
    outside_directory(output, exported)
    fresh_directory(output)

    trial_id = request["trial_id"]
    dataset = trial_id.split("-", 1)[0]
    if dataset not in {"location", "single"}:
        raise ValueError(f"Unexpected controlled dataset: {dataset}")
    trace_root = Path(os.environ["CONTROLLED_TRACE_ROOT"]).resolve()
    attempt_id = output.name
    if not attempt_id.startswith("attempt-"):
        raise ValueError(f"Output directory must have an attempt-* basename: {output}")
    trace = trace_root / dataset / trial_id / attempt_id
    fresh_directory(trace)

    prompt = inside(exported, request["prompt_file"]).read_text(encoding="utf-8")
    hint = inside(exported, request["hint_file"]).read_text(encoding="utf-8")
    before = inside(exported, request["skills_dir"])
    task_context = (
        "## Controlled repair instruction\n"
        + request["instruction"]
        + "\n\n## Task statement\n"
        + prompt
        + "\n\n## Organizer-provided location-only hint\n"
        + hint
    )
    evidence_context = (
        "This controlled trial intentionally supplies no execution failure trajectory. "
        "Use only the organizer-provided location hint to determine the defect and repair. "
        "Do not infer or retrieve Gold or another trial.\n\n"
        + hint
    )

    rounds = repair_rounds_r()
    manifests: list[dict[str, object]] = []
    current_before = before
    for round_number in range(1, rounds + 1):
        round_workspace = trace / f"round-{round_number:03d}"
        round_after = (
            output / "skills"
            if round_number == rounds
            else round_workspace / "candidate_skills"
        )
        round_task_context = task_context
        if round_number > 1:
            round_task_context += (
                f"\n\n## Repair round {round_number} of {rounds}\n"
                "Re-check every organizer-provided hint bullet against the current candidate. "
                "Correct remaining omissions, contradictions, or overly broad rules while "
                "preserving already-correct guidance."
            )
        manifest = rewrite_bundle_once(
            method_name=METHOD_ID,
            method_root=ROOT / "SkillOpt",
            lite=False,
            task_id=request["task_id"],
            workspace=round_workspace,
            before_skill=current_before,
            after_skill=round_after,
            baseline_result=None,
            run_id=os.environ["CONTROLLED_EXPERIMENT_ID"],
            repair_round=round_number,
            allow_overwrite=False,
            rejected_buffer=[],
            evidence_paths=[],
            task_context_override=round_task_context,
            baseline_context_override=("oracle_location_hint", evidence_context),
            include_text_attachments=True,
        )
        manifests.append(manifest)
        current_before = round_after

    validate_candidate(output, exported)
    before_hashes = hashes(before)
    after_hashes = hashes(output / "skills")
    changed = sorted(
        path for path in set(before_hashes) | set(after_hashes)
        if before_hashes.get(path) != after_hashes.get(path)
    )
    response = {
        "schema_version": 2,
        "trial_id": trial_id,
        "task_id": request["task_id"],
        "method_id": METHOD_ID,
        "provider": "ai360",
        "repair_model": EXPECTED_MODEL,
        "diagnosis_n": diagnosis_sample_count(),
        "edit_budget_l": edit_budget_l(),
        "repair_rounds_r": rounds,
        "same_task_gate": False,
        "attempt_id": attempt_id,
        "input_bundle_sha256": bundle_digest(before),
        "candidate_bundle_sha256": bundle_digest(output / "skills"),
        "changed_files": changed,
        "trace_directory": str(trace),
        "diagnosed_files": sorted({
            str(item.get("path"))
            for manifest in manifests
            for item in manifest.get("diagnosis", {}).get("diagnosed_skills", [])
            if item.get("path")
        }),
        "rounds": [
            {
                "repair_round": round_number,
                "trace_directory": str(trace / f"round-{round_number:03d}"),
                "diagnosed_files": [
                    item.get("path")
                    for item in manifest.get("diagnosis", {}).get("diagnosed_skills", [])
                ],
                "rewritten_files": [
                    item.get("path") for item in manifest.get("rewritten_files", [])
                ],
            }
            for round_number, manifest in enumerate(manifests, start=1)
        ],
    }
    write_json(output / "response.json", response)
    write_json(trace / "candidate_summary.json", response)
    print(json.dumps({"trial_id": trial_id, "changed_files": changed}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

