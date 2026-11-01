#!/usr/bin/env python3
"""Audit the isolated GPT-5.2 controlled repair experiment.

This script is intentionally experiment-local.  It never discovers or reads
legacy GPT-5.2 or Opus result roots.  It produces two machine-readable reports:

* result-audit.json: one classification for every BenchFlow attempt/result;
* candidate-static-audit.json: candidate/input scope and exact Gold-atom checks.

Exact atom matches are a conservative aid for the later semantic review.  A
missing exact match is not automatically a semantic failure because an
equivalent repair may use different wording or code.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Optional


WORKSPACE = Path("/Users/elsie/Desktop/SkillOpt-eva")
RUN = WORKSPACE / "experiments/gpt52-skillopt-controlled-location-single-r2l5-v2-20261027"
PACKAGE = WORKSPACE / "skill-repair-controlled-datasets-20261020"
EXPECTED_EXECUTOR_MODEL = "ai360/openai/gpt-5.2"
EXPECTED_REPAIR_MODEL = "openai/gpt-5.2"
EXPECTED_METHOD = "skillopt-controlled-oracle-hint-r2l5-v2"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def files(root: Path) -> dict[str, Path]:
    if not root.is_dir():
        return {}
    return {
        path.relative_to(root).as_posix(): path
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def reward_from_result(result: dict[str, Any]) -> Optional[float]:
    rewards = result.get("rewards")
    if not isinstance(rewards, dict):
        verifier = result.get("verifier_result")
        rewards = verifier.get("rewards") if isinstance(verifier, dict) else None
    reward = rewards.get("reward") if isinstance(rewards, dict) else None
    if isinstance(reward, bool):
        reward = float(reward)
    if isinstance(reward, (int, float)) and 0 <= reward <= 1:
        return float(reward)
    return None


def classify_result(result: dict[str, Any]) -> tuple[str, Optional[float], list[str]]:
    errors = [
        str(result[key])
        for key in ("error", "verifier_error", "exception_info", "exception", "error_message")
        if result.get(key)
    ]
    if result.get("partial_trajectory"):
        errors.append("partial_trajectory=true")
    reward = reward_from_result(result)
    if errors:
        return "invalid_or_incomplete", None, errors
    if reward is None:
        return "missing_verifier_result", None, []
    return "valid", reward, []


def attempt_evidence_text(attempt_dir: Path, row: dict[str, Any]) -> str:
    chunks = [json.dumps(row, ensure_ascii=False)]
    candidates = [
        attempt_dir / "RUN_RECORD.json",
        attempt_dir / "bench.stdout.txt",
        attempt_dir / "bench.stderr.txt",
    ]
    candidates.extend(sorted((attempt_dir / "jobs").rglob("acp_trajectory.jsonl")))
    # Provider-side failures are recorded by the local proxy in this stream,
    # while the ACP result may expose only a generic -32603 error.
    candidates.extend(sorted((attempt_dir / "jobs").rglob("llm_trajectory.jsonl")))
    candidates.extend(sorted((attempt_dir / "jobs").rglob("install-stdout.txt")))
    candidates.extend(sorted((attempt_dir / "jobs").rglob("install-stderr.txt")))
    for path in candidates:
        if not path.is_file():
            continue
        try:
            chunks.append(path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
    return "\n".join(chunks).lower()


def classify_infra_reason(attempt_dir: Path, row: dict[str, Any]) -> str:
    text = attempt_evidence_text(attempt_dir, row)
    # Preserve a specific provider-balance diagnosis even when the outer bench
    # process was interrupted before it could write its terminal exit code.
    if any(needle in text for needle in ("余额不足", '"code":"1004"', "'code': '1004'")):
        return "provider_balance"
    # No terminal bench record and no result object is authoritative evidence
    # of interruption.  Do this before broad log keyword matching: task/model
    # text can mention a network or verifier error without that being the
    # infrastructure failure that ended the attempt.
    if row.get("bench_exit_code") is None and not row.get("results"):
        return "interrupted_or_no_terminal_record"
    patterns = [
        ("litellm_proxy_config", ("invalid value for '--debug'", "litellm exited before becoming healthy")),
        ("iteration_protocol", ("non-canonical iteration cap", "expected none")),
        ("docker_image_tag_race", ("notfound: content digest", "manifest unknown")),
        ("docker_host_permission", (".docker/buildx/activity", "permission denied while trying to connect to the docker daemon", "docker.sock: connect: operation not permitted")),
        ("agent_install_network", ("agent openhands install failed", "curl: (6)", "curl: (28)", "curl: (35)", "curl: (60)", "certificate verify failed", "failed to download")),
        ("verifier_dependency_network", ("verifier_error", "bad gateway", "502")),
        ("agent_transport_or_tool_hang", ("acp error", "partial_trajectory=true", "partial_trajectory\": true", "stuck")),
    ]
    for reason, needles in patterns:
        if any(needle in text for needle in needles):
            return reason
    if row.get("bench_exit_code") is None:
        return "interrupted_or_no_terminal_record"
    return "unclassified_infrastructure"


def compact_errors(errors: list[str]) -> list[dict[str, Any]]:
    return [
        {
            "length": len(error),
            "sha256": hashlib.sha256(error.encode("utf-8")).hexdigest(),
            "excerpt": error[:2000] + ("…" if len(error) > 2000 else ""),
        }
        for error in errors
    ]


def result_unit_key(record: dict[str, Any], relative_attempt: str) -> str:
    """Return the experiment-unique unit key for a completed attempt.

    Repaired trials intentionally use the bare trial ID.  Controls must keep
    their condition namespace because ``condition_baseline`` reuses the same
    trial ID as its paired repaired candidate.  Collapsing both to
    ``trial_id`` falsely turns every completed pair into a duplicate.
    """
    if relative_attempt.startswith("controls/"):
        item = record.get("trial_id") or record.get("task_id")
        return f"{record.get('condition')}/{item}"
    trial_id = record.get("trial_id")
    if not trial_id:
        raise ValueError(f"Repaired attempt has no trial_id: {relative_attempt}")
    return str(trial_id)


def audit_results() -> dict[str, Any]:
    attempts: list[dict[str, Any]] = []
    selected_by_unit: dict[str, list[dict[str, Any]]] = {}
    for record_path in sorted((RUN / "eval_runs").rglob("RUN_RECORD.json")):
        record = read_json(record_path)
        attempt_dir = record_path.parent
        relative_attempt = attempt_dir.relative_to(RUN / "eval_runs").as_posix()
        launch_error = record.get("launch_error")
        launch_error_text = str(launch_error) if launch_error else ""
        row: dict[str, Any] = {
            "attempt": relative_attempt,
            "task_id": record.get("task_id"),
            "trial_id": record.get("trial_id"),
            "condition": record.get("condition"),
            "method_id": record.get("method_id"),
            "repair_model": record.get("repair_model"),
            "agent": record.get("agent"),
            "model": record.get("model"),
            "bench_exit_code": record.get("bench_exit_code"),
            "launch_error_present": bool(launch_error),
            "launch_error_excerpt": (
                launch_error_text[:2000] + ("…" if len(launch_error_text) > 2000 else "")
            ),
            "launch_error_sha256": (
                hashlib.sha256(launch_error_text.encode("utf-8")).hexdigest()
                if launch_error_text else None
            ),
            "results": [],
        }
        for result_path in sorted((attempt_dir / "jobs").rglob("result.json")):
            result = read_json(result_path)
            if not any(key in result for key in ("rewards", "verifier_result", "task_name")):
                continue
            status, reward, errors = classify_result(result)
            row["results"].append({
                "path": result_path.relative_to(RUN).as_posix(),
                "status": status,
                "reward": reward,
                "errors": compact_errors(errors),
                "model": result.get("model"),
                "agent": result.get("agent") or result.get("agent_name"),
                "total_prompt_tokens": (result.get("final_metrics") or {}).get("total_prompt_tokens"),
                "total_completion_tokens": (result.get("final_metrics") or {}).get("total_completion_tokens"),
            })
        valid = [item for item in row["results"] if item["status"] == "valid"]
        metadata_ok = (
            record.get("bench_exit_code") == 0
            and not launch_error
            and record.get("model") == EXPECTED_EXECUTOR_MODEL
            and record.get("agent") == "openhands"
            and (
                (
                    relative_attempt.startswith("repaired/")
                    and record.get("method_id") == EXPECTED_METHOD
                    and record.get("repair_model") == EXPECTED_REPAIR_MODEL
                )
                or (
                    relative_attempt.startswith("controls/")
                    and record.get("method_id") == "control"
                    and record.get("repair_model") == "none"
                )
            )
        )
        row["metadata_ok"] = metadata_ok
        row["attempt_status"] = (
            "valid" if metadata_ok and len(valid) == 1
            else "ambiguous_valid_results" if metadata_ok and len(valid) > 1
            else "invalid_or_incomplete"
        )
        if row["attempt_status"] != "valid":
            row["infra_reason"] = classify_infra_reason(attempt_dir, row)
        if row["attempt_status"] == "valid":
            row["selected_result"] = valid[0]["path"]
            row["reward"] = valid[0]["reward"]
            unit = result_unit_key(record, relative_attempt)
            selected_by_unit.setdefault(unit, []).append({
                "attempt": relative_attempt,
                "reward": valid[0]["reward"],
                "result": valid[0]["path"],
            })
        attempts.append(row)

    trial_ids = {
        line.strip()
        for line in (RUN / "configs/trials.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }
    control_ids = {
        f"{condition}/{task}"
        for raw in (RUN / "configs/controls.tsv").read_text(encoding="utf-8").splitlines()
        if raw.strip() and not raw.startswith("#")
        for condition, task, *_ in [raw.split("\t")]
    }
    expected_units = sorted(trial_ids | control_ids)
    missing = [unit for unit in expected_units if not selected_by_unit.get(unit)]
    duplicates = {
        unit: values for unit, values in selected_by_unit.items() if len(values) != 1
    }
    selected = {
        unit: values[0] for unit, values in selected_by_unit.items() if len(values) == 1
    }
    infra_counts = Counter(
        row.get("infra_reason") for row in attempts if row.get("infra_reason")
    )
    return {
        "schema_version": 2,
        "scope": str(RUN.relative_to(WORKSPACE)),
        "expected_executor_model": EXPECTED_EXECUTOR_MODEL,
        "expected_repair_model": EXPECTED_REPAIR_MODEL,
        "expected_method": EXPECTED_METHOD,
        "expected_units": len(expected_units),
        "selected_valid_units": len(selected),
        "missing_units": missing,
        "duplicate_valid_units": duplicates,
        "invalid_attempts_by_infra_reason": dict(sorted(infra_counts.items())),
        "selected": selected,
        "attempts": attempts,
    }


def candidate_attempt(trial: dict[str, Any]) -> Path:
    root = RUN / "candidates" / trial["dataset"] / trial["trial_id"]
    candidates = sorted(path.parent for path in root.glob("attempt-*/CANDIDATE_SHA256.json"))
    if len(candidates) != 1:
        raise RuntimeError(f"Expected one complete candidate for {trial['trial_id']}, found {candidates}")
    return candidates[0]


def audit_candidates() -> dict[str, Any]:
    catalog = read_json(PACKAGE / "datasets/catalog.json")
    repair_groups = {
        task["task_id"]: task for task in read_json(PACKAGE / "organizer/repair_groups.json")["tasks"]
    }
    configured = {
        line.strip()
        for line in (RUN / "configs/trials.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }
    rows: list[dict[str, Any]] = []
    for trial in catalog["trials"]:
        if trial["trial_id"] not in configured:
            continue
        attempt = candidate_attempt(trial)
        candidate_root = attempt / "skills"
        input_root = RUN / "inputs" / trial["dataset"] / trial["trial_id"] / "skills"
        candidate_files = files(candidate_root)
        input_files = files(input_root)
        added = sorted(candidate_files.keys() - input_files.keys())
        removed = sorted(input_files.keys() - candidate_files.keys())
        changed = sorted(
            name for name in candidate_files.keys() & input_files.keys()
            if sha256(candidate_files[name]) != sha256(input_files[name])
        )
        # repair_groups.json covers the five controlled single-point tasks.
        # Three location-only tasks are represented by their full Gold diff
        # and therefore have no atom-level decomposition in this release.
        task_groups = repair_groups.get(trial["task_id"], {"repair_atoms": []})
        target_ids = set(trial["target_repair_ids"])
        target_atoms = [
            atom for atom in task_groups["repair_atoms"]
            if set(atom.get("groups", [atom.get("group")])) & target_ids
        ]
        non_target_atoms = [
            atom for atom in task_groups["repair_atoms"]
            if not (set(atom.get("groups", [atom.get("group")])) & target_ids)
        ]
        target_files = {atom["file"] for atom in target_atoms}
        if not target_files:
            annotation_path = PACKAGE / "organizer/annotations" / f"{trial['task_id']}.json"
            if annotation_path.is_file():
                annotation = read_json(annotation_path)
                for repair_id in trial["target_repair_ids"]:
                    for location in (annotation.get(repair_id) or {}).get("skill_location", []):
                        name = location.get("skill_file", "")
                        if name.startswith("skills/"):
                            name = name[len("skills/"):]
                        if name:
                            target_files.add(name)
        out_of_scope_changed = sorted(set(changed) - target_files)

        def atom_match(atom: dict[str, Any]) -> dict[str, Any]:
            path = candidate_root / atom["file"]
            after = atom.get("after", "")
            present = path.is_file() and (not after or after in path.read_text(encoding="utf-8"))
            return {"atom_id": atom["atom_id"], "file": atom["file"], "exact_after_present": present}

        target_matches = [atom_match(atom) for atom in target_atoms]
        non_target_matches = [atom_match(atom) for atom in non_target_atoms]
        rows.append({
            "trial_id": trial["trial_id"],
            "dataset": trial["dataset"],
            "task_id": trial["task_id"],
            "condition": trial["condition"],
            "target_repair_ids": trial["target_repair_ids"],
            "candidate": attempt.relative_to(RUN).as_posix(),
            "file_set_preserved": not added and not removed,
            "added_files": added,
            "removed_files": removed,
            "changed_files": changed,
            "target_files": sorted(target_files),
            "out_of_scope_changed_files": out_of_scope_changed,
            "all_changes_within_target_files": not out_of_scope_changed,
            "target_exact_atoms": target_matches,
            "target_exact_atom_count": sum(item["exact_after_present"] for item in target_matches),
            "target_atom_count": len(target_matches),
            "non_target_exact_atoms": non_target_matches,
            "non_target_gold_preserved_exact": all(
                item["exact_after_present"] for item in non_target_matches
            ),
            "semantic_review_required": True,
        })
    return {
        "schema_version": 1,
        "scope": str(RUN.relative_to(WORKSPACE)),
        "warning": "Exact atom checks are evidence aids, not semantic verdicts.",
        "expected_trials": len(configured),
        "audited_trials": len(rows),
        "all_file_sets_preserved": all(row["file_set_preserved"] for row in rows),
        "all_changes_within_target_files": all(
            row["all_changes_within_target_files"] for row in rows
        ),
        "all_non_target_gold_preserved_exact": all(
            row["non_target_gold_preserved_exact"] for row in rows
        ),
        "trials": rows,
    }


def main() -> None:
    result_audit = audit_results()
    candidate_audit = audit_candidates()
    write_json(RUN / "summaries/result-audit.json", result_audit)
    write_json(RUN / "summaries/candidate-static-audit.json", candidate_audit)
    print(json.dumps({
        "results": {
            "expected_units": result_audit["expected_units"],
            "selected_valid_units": result_audit["selected_valid_units"],
            "missing_units": len(result_audit["missing_units"]),
            "duplicate_valid_units": len(result_audit["duplicate_valid_units"]),
        },
        "candidates": {
            "expected_trials": candidate_audit["expected_trials"],
            "audited_trials": candidate_audit["audited_trials"],
            "all_file_sets_preserved": candidate_audit["all_file_sets_preserved"],
            "all_changes_within_target_files": candidate_audit["all_changes_within_target_files"],
            "all_non_target_gold_preserved_exact": candidate_audit["all_non_target_gold_preserved_exact"],
        },
    }, indent=2))


if __name__ == "__main__":
    main()
