#!/usr/bin/env python3
"""Verify GPT-5.2/Opus isolation using structured metadata, not text search."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


WORKSPACE = Path("/Users/elsie/Desktop/SkillOpt-eva")
RUN = WORKSPACE / "experiments/gpt52-skillopt-controlled-location-single-r2l5-v2-20261027"
REPAIR_MODEL = "openai/gpt-5.2"
EXECUTOR_MODEL = "ai360/openai/gpt-5.2"
METHOD = "skillopt-controlled-oracle-hint-r2l5-v2"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def keyed_values(value: Any, keys: set[str], prefix: str = "$") -> list[tuple[str, str, Any]]:
    found: list[tuple[str, str, Any]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}"
            if key in keys:
                found.append((child_prefix, key, child))
            found.extend(keyed_values(child, keys, child_prefix))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(keyed_values(child, keys, f"{prefix}[{index}]"))
    return found


def relative(path: Path) -> str:
    return path.relative_to(RUN).as_posix()


def main() -> None:
    violations: list[dict[str, Any]] = []
    checks: dict[str, Any] = {}

    responses = sorted((RUN / "candidates").rglob("response.json"))
    complete_responses = []
    for path in responses:
        data = read_json(path)
        if not (path.parent / "CANDIDATE_SHA256.json").is_file():
            continue
        complete_responses.append(path)
        expected = {
            "method_id": METHOD,
            "provider": "ai360",
            "repair_model": REPAIR_MODEL,
        }
        for key, wanted in expected.items():
            if data.get(key) != wanted:
                violations.append({
                    "kind": "candidate_metadata",
                    "path": relative(path),
                    "field": key,
                    "expected": wanted,
                    "actual": data.get(key),
                })
        trace = Path(str(data.get("trace_directory", "")))
        try:
            trace.relative_to(RUN / "repair_traces")
        except ValueError:
            violations.append({
                "kind": "trace_outside_experiment",
                "path": relative(path),
                "trace_directory": str(trace),
            })
    checks["complete_candidate_responses"] = len(complete_responses)

    trace_jsons = sorted((RUN / "repair_traces").rglob("*.json"))
    structured_model_fields = 0
    structured_provider_fields = 0
    for path in trace_jsons:
        try:
            data = read_json(path)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            violations.append({"kind": "invalid_trace_json", "path": relative(path), "error": str(exc)})
            continue
        for pointer, key, value in keyed_values(
            data, {"model", "optimizer_model", "repair_model", "provider"}
        ):
            if key == "provider":
                structured_provider_fields += 1
                if value != "ai360":
                    violations.append({
                        "kind": "repair_provider_mismatch",
                        "path": relative(path),
                        "pointer": pointer,
                        "actual": value,
                    })
            else:
                structured_model_fields += 1
                if value != REPAIR_MODEL:
                    violations.append({
                        "kind": "repair_model_mismatch",
                        "path": relative(path),
                        "pointer": pointer,
                        "actual": value,
                    })
    checks["repair_trace_json_files"] = len(trace_jsons)
    checks["repair_model_fields_checked"] = structured_model_fields
    checks["repair_provider_fields_checked"] = structured_provider_fields

    run_records = sorted((RUN / "eval_runs").rglob("RUN_RECORD.json"))
    result_files_checked = 0
    for path in run_records:
        data = read_json(path)
        is_control = relative(path).startswith("eval_runs/controls/")
        expected = {
            "model": EXECUTOR_MODEL,
            "agent": "openhands",
            "method_id": "control" if is_control else METHOD,
            "repair_model": "none" if is_control else REPAIR_MODEL,
        }
        for key, wanted in expected.items():
            if data.get(key) != wanted:
                violations.append({
                    "kind": "run_record_metadata",
                    "path": relative(path),
                    "field": key,
                    "expected": wanted,
                    "actual": data.get(key),
                })
        for result_path in sorted((path.parent / "jobs").rglob("result.json")):
            result = read_json(result_path)
            if not any(key in result for key in ("rewards", "task_name", "verifier_result")):
                continue
            result_files_checked += 1
            if result.get("model") != EXECUTOR_MODEL:
                violations.append({
                    "kind": "result_model_mismatch",
                    "path": relative(result_path),
                    "expected": EXECUTOR_MODEL,
                    "actual": result.get("model"),
                })
            if (result.get("agent") or result.get("agent_name")) != "openhands":
                violations.append({
                    "kind": "result_agent_mismatch",
                    "path": relative(result_path),
                    "actual": result.get("agent") or result.get("agent_name"),
                })
    checks["run_records_checked"] = len(run_records)
    checks["result_files_checked"] = result_files_checked

    symlinks = sorted(path for path in RUN.rglob("*") if path.is_symlink())
    escaping_symlinks = []
    for path in symlinks:
        try:
            path.resolve(strict=True).relative_to(RUN)
        except (ValueError, FileNotFoundError):
            escaping_symlinks.append(relative(path))
    if escaping_symlinks:
        violations.append({"kind": "escaping_symlinks", "paths": escaping_symlinks})
    checks["symlinks"] = len(symlinks)
    checks["escaping_symlinks"] = len(escaping_symlinks)

    env_text = (RUN / "commands/env.sh").read_text(encoding="utf-8")
    required_barriers = [
        'export TATU_API_KEY=""',
        'export TATU_BASE_URL=""',
        'export TATU_MODEL=""',
        'export AWS_BEARER_TOKEN_BEDROCK=""',
        '*opus*|*claude*|*tatu*',
        '[[ "$SKILLOPT_MODEL" == "openai/gpt-5.2" ]]',
        '[[ "$BENCHMARK_MODEL" == "ai360/openai/gpt-5.2" ]]',
    ]
    missing_barriers = [item for item in required_barriers if item not in env_text]
    if missing_barriers:
        violations.append({"kind": "missing_environment_barriers", "items": missing_barriers})
    checks["environment_barriers_checked"] = len(required_barriers)

    report = {
        "schema_version": 1,
        "experiment_id": RUN.name,
        "passed": not violations,
        "expected": {
            "repair_provider": "ai360",
            "repair_model": REPAIR_MODEL,
            "executor_agent": "openhands",
            "executor_model": EXECUTOR_MODEL,
            "method_id": METHOD,
        },
        "checks": checks,
        "violations": violations,
        "interpretation": "Structured metadata and path-boundary audit only. Text mentions such as OpenHands' compatibility path /root/.claude/skills are not model/provider evidence.",
    }
    out = RUN / "summaries/isolation-audit.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "checks": checks, "violations": len(violations)}, indent=2))
    if violations:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
