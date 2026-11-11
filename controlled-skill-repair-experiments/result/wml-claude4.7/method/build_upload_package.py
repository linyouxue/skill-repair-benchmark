#!/usr/bin/env python3
"""Build the portable GitHub upload for the final 55-run WML experiment.

Only attempts selected by experiment-manifest-55.json are included. Large JSONL
logs are compressed losslessly, and repeated staged task payloads are omitted;
their task identity, Dockerfile, verifier, and execution audits remain included.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def copy_file(source: Path, target: Path, *, gzip_jsonl: bool = False) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    if gzip_jsonl and source.suffix == ".jsonl" and source.stat().st_size >= 64 * 1024:
        target = target.with_suffix(target.suffix + ".gz")
        with source.open("rb") as src, target.open("wb") as raw:
            with gzip.GzipFile(fileobj=raw, mode="wb", compresslevel=9, mtime=0) as dst:
                shutil.copyfileobj(src, dst)
    else:
        shutil.copy2(source, target)
    return target


def copy_tree(source: Path, target: Path, *, gzip_jsonl: bool = False) -> None:
    for path in sorted(source.rglob("*")):
        if path.is_file():
            copy_file(path, target / path.relative_to(source), gzip_jsonl=gzip_jsonl)


def job_root(entry: dict) -> Path:
    return ROOT / Path(entry["result_file"]).parent


def copy_run(entry: dict, destination: Path) -> dict:
    attempt = ROOT / entry["attempt_dir"]
    native_job = job_root(entry)
    run_dir = destination / "run"
    run_dir.mkdir(parents=True, exist_ok=True)

    for name in (
        "EXECUTION_PREFLIGHT.json",
        "EXECUTION_AUDIT.json",
        "RUN_RECORD.json",
        "bench.stdout.txt",
        "bench.stderr.txt",
    ):
        source = attempt / name
        if source.exists():
            copy_file(source, run_dir / name)

    summary = next((attempt / "jobs").glob("summary.json"), None)
    if summary:
        copy_file(summary, run_dir / "job_summary.json")

    skipped_duplicates = {
        Path("agent/acp_trajectory.jsonl"),
        Path("trainer/adp.jsonl"),
        Path("trainer/verifiers.jsonl"),
    }
    copied_logs = []
    for source in sorted(native_job.rglob("*")):
        if not source.is_file():
            continue
        relative = source.relative_to(native_job)
        if relative in skipped_duplicates:
            continue
        output = copy_file(source, run_dir / relative, gzip_jsonl=True)
        if source.suffix == ".jsonl":
            copied_logs.append(
                {
                    "source_name": relative.as_posix(),
                    "packaged_name": output.relative_to(destination).as_posix(),
                    "compression": "gzip" if output.suffix == ".gz" else "none",
                }
            )

    staged = attempt / "staged-task" / entry["unique_task_name"]
    for relative in (Path("task.md"), Path("environment/Dockerfile")):
        source = staged / relative
        if source.exists():
            copy_file(source, destination / "task_metadata" / relative)
    verifier = staged / "verifier"
    if verifier.exists():
        copy_tree(verifier, destination / "task_metadata/verifier")

    with (destination / "experiment.json").open("w", encoding="utf-8") as handle:
        json.dump(entry, handle, indent=2, ensure_ascii=False)
        handle.write("\n")

    return {
        "experiment_id": entry["experiment_id"],
        "experiment_type": entry["experiment_type"],
        "status": entry["status"],
        "reward": entry["reward"],
        "source_attempt_dir": entry["attempt_dir"],
        "package_dir": destination.relative_to(destination.parents[2]).as_posix(),
        "compressed_logs": copied_logs,
    }


def update_semantic_review(manifest: dict, destination: Path) -> None:
    source = ROOT / "review/semantic_review.csv"
    rows = list(csv.DictReader(source.open(encoding="utf-8")))
    fields = list(rows[0])
    repairs = {
        entry["experiment_id"]: entry
        for entry in manifest["experiments"]
        if entry["experiment_type"] == "wml_repair"
    }
    controls = {
        entry["experiment_id"]: entry
        for entry in manifest["experiments"]
        if entry["experiment_type"] == "control"
    }
    for row in rows:
        entry = repairs[row["experiment_id"]]
        positive = controls.get(f'{entry["task_id"]}__full_gold')
        baseline = controls.get(f'{entry["trial_id"]}__condition_baseline')
        row["executor_model"] = manifest["executor_model"]
        row["executor_budget"] = "see experiments/repair/<experiment_id>/run/config.json"
        row["candidate_sha256"] = entry["skill_bundle_sha256"].removeprefix("sha256:")
        row["positive_control_passed"] = (
            str(positive["status"] == "pass").lower() if positive else "N/A"
        )
        row["condition_baseline_passed"] = (
            str(baseline["status"] == "pass").lower() if baseline else "N/A"
        )
        row["native_task_passed"] = str(entry["status"] == "pass").lower()
        row["native_reward"] = str(entry["reward"])
        row["evidence_path"] = ";".join(
            [
                f'repair/candidates/{entry["experiment_id"]}/response.json',
                f'experiments/repair/{entry["experiment_id"]}/run/result.json',
                f'review/semantic_review_evidence.md#{entry["experiment_id"]}',
            ]
        )

    destination.mkdir(parents=True, exist_ok=True)
    with (destination / "semantic_review.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    copy_file(ROOT / "review/semantic_review_evidence.md", destination / "semantic_review_evidence.md")


def write_readme(destination: Path) -> None:
    content = """# WML / Claude Opus 4.7 controlled skill-repair experiments

- Method: Workflow-Localized Mechanism Learning (WML), with its original diagnosis and iterative repair mechanism.
- Controlled dataset: `skill-repair-controlled-datasets-20261020` (8 base tasks; 22 repair experiments and 33 control experiments).
- Repair model: `Claude-Opus-4.7` through Paratera (`https://llmapi.paratera.com/v1`).
- Executor: BenchFlow 0.6.7, `openhands`, model `paratera/Claude-Opus-4.7`, base URL `https://llmapi.paratera.com`.
- Final rerun: 2026-11-10 to 2026-11-11 after adding collision-safe task identities and mandatory persistent Skill preload audits.
- Human involvement: experiment operation, infrastructure-only retry/remediation, packaging, and an AI-assisted manual semantic review. Candidate Skill content was not manually rewritten after WML output.

## Final results

| Scope | Valid | Pass | Fail | Invalid |
|---|---:|---:|---:|---:|
| WML repairs | 22 | 12 | 10 | 0 |
| Controls | 33 | 21 | 12 | 0 |
| Total | 55 | 33 | 22 | 0 |

All 55 selected attempts have a valid `EXECUTION_AUDIT.json`, complete native result data, ACP and LLM trajectories, verifier output, a task-identity collision guard, and executor-level proof that the intended Skill bundle was preloaded. A task verifier failure remains a valid experimental result and is reported as `fail`; no infrastructure failure is counted as an experimental failure.

The manual semantic review reports 5/22 targets fully repaired and 17/22 not fully repaired under the Gold semantic criteria. For the 12 leave-one-out trials, all 12 retained the non-target Gold repairs. This semantic score is separate from the native task verifier score.

## Directory layout

- `manifest/`: authoritative 55-run manifest, repair/control summaries, remediation status, package index, and file checksums.
- `protocol/`: dataset catalog, repair-group definition, schema, and official scoring template.
- `method/`: the WML adapter and the exact evaluation/validation launchers used for this run.
- `repair/inputs/`: the 22 isolated repair inputs exposed to WML.
- `repair/candidates/`: all 22 complete WML output bundles, diagnoses, responses, and API-usage records.
- `review/`: the official-format semantic review CSV and detailed evidence notes.
- `experiments/repair/`: one final valid executor run for each of the 22 repaired candidates.
- `experiments/control/`: one final valid executor run for each of the 33 controls.

Within every experiment directory, `run/` contains the original executor metadata, result, verifier records, Skill snapshot, and trajectories. Large `.jsonl` files are stored losslessly as `.jsonl.gz`; `manifest/upload-package-index.json` records the mapping. Repeated staged task payloads are not duplicated. The task identity, patched Dockerfile, verifier, Skill snapshot, preflight hash, and audit remain present, while the fixed public task payload is identified by the dataset/provenance versions above.

Transient Debian/Ubuntu download failures and the legacy Google Auto CA bootstrap were handled only in per-attempt staging Dockerfiles. Task bodies, candidate Skill bundles, and verifiers were not modified during this remediation.
"""
    (destination / "README.md").write_text(content, encoding="utf-8")


def package_checksums(destination: Path) -> None:
    records = {}
    checksum_path = destination / "manifest/PACKAGE_SHA256.json"
    for path in sorted(destination.rglob("*")):
        if not path.is_file() or path == checksum_path:
            continue
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        records[path.relative_to(destination).as_posix()] = {
            "sha256": digest.hexdigest(),
            "size": path.stat().st_size,
        }
    checksum_path.parent.mkdir(parents=True, exist_ok=True)
    checksum_path.write_text(
        json.dumps({"schema_version": 1, "files": records}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def build(destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)

    manifest = json.loads((ROOT / "experiment-manifest-55.json").read_text(encoding="utf-8"))
    if manifest["counts"] != {
        "total": 55,
        "wml_repairs": 22,
        "controls": 33,
        "valid": 55,
        "invalid": 0,
        "passes": 33,
        "failures": 22,
    }:
        raise RuntimeError(f'Unexpected manifest counts: {manifest["counts"]}')

    for name in (
        "experiment-manifest-55.json",
        "eval_summary.json",
        "control_eval_summary.json",
        "repair_summary.json",
        "REMEDIATION_STATUS.json",
    ):
        copy_file(ROOT / name, destination / "manifest" / name)

    (destination / "COMPLETE.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "status": "complete",
                "counts": manifest["counts"],
                "wml_pass": 12,
                "control_pass": 21,
                "selected_attempts": 55,
                "execution_audits_valid": 55,
                "acp_trajectories": 55,
                "llm_trajectories": 55,
                "final_manifest": "manifest/experiment-manifest-55.json",
                "rerun_completed_at": manifest["updated_at"],
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    (destination / "EXPERIMENT_CONFIG.json").write_text(
        json.dumps(
            {
                "experiment_id": manifest["experiment_id"],
                "repair_method": manifest["repair_method"],
                "repair_model": manifest["repair_model"],
                "executor_agent": manifest["executor_agent"],
                "executor_model": manifest["executor_model"],
                "base_url": manifest["base_url"],
                "dataset": "skill-repair-controlled-datasets-20261020",
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    (destination / "results-summary.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "counts": manifest["counts"],
                "repair_summary": "manifest/eval_summary.json",
                "control_summary": "manifest/control_eval_summary.json",
                "experiments": manifest["experiments"],
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    copy_tree(ROOT / "protocol", destination / "protocol")
    copy_tree(ROOT / "method", destination / "method")

    repair_entries = [
        entry for entry in manifest["experiments"] if entry["experiment_type"] == "wml_repair"
    ]
    for entry in repair_entries:
        experiment_id = entry["experiment_id"]
        copy_tree(ROOT / entry["input_dir"], destination / "repair/inputs" / experiment_id)
        copy_tree(ROOT / entry["candidate_dir"], destination / "repair/candidates" / experiment_id)

    update_semantic_review(manifest, destination / "review")

    index = []
    for entry in manifest["experiments"]:
        category = "repair" if entry["experiment_type"] == "wml_repair" else "control"
        target = destination / "experiments" / category / entry["experiment_id"]
        index.append(copy_run(entry, target))
    (destination / "manifest/upload-package-index.json").write_text(
        json.dumps({"schema_version": 1, "experiments": index}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    write_readme(destination)
    package_checksums(destination)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    build(args.destination.resolve())


if __name__ == "__main__":
    main()
