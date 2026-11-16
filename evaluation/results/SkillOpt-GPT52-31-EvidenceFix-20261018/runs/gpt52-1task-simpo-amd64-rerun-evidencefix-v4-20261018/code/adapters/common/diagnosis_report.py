from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from adapters.common.executor_api import write_json
from adapters.common.paths import ROOT


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {"error_category": "invalid_json", "error": repr(exc)}


def _short(text: Any, limit: int = 1200) -> str:
    value = json.dumps(text, ensure_ascii=False) if not isinstance(text, str) else text
    value = value.replace("", "")
    return value if len(value) <= limit else value[:limit] + f"\n[truncated to {limit} chars]"


def _trajectory_files(result: dict[str, Any]) -> list[dict[str, Any]]:
    rollout_dir = result.get("rollout_dir") or ""
    if not rollout_dir:
        return []
    root = Path(rollout_dir)
    if not root.exists():
        return []
    files = []
    for path in sorted((root / "trajectory").glob("*.jsonl")):
        text = path.read_text(encoding="utf-8", errors="replace")
        files.append(
            {
                "path": str(path),
                "lines": len(text.splitlines()),
                "bytes": len(text.encode("utf-8", errors="replace")),
            }
        )
    return files


def _trajectory_text(result: dict[str, Any], limit: int = 500_000) -> str:
    rollout_dir = result.get("rollout_dir") or ""
    if not rollout_dir:
        return ""
    root = Path(rollout_dir) / "trajectory"
    chunks: list[str] = []
    used = 0
    for path in sorted(root.glob("*.jsonl")):
        text = path.read_text(encoding="utf-8", errors="replace")
        room = limit - used
        if room <= 0:
            break
        chunks.append(text[:room])
        used += min(len(text), room)
    return "\n".join(chunks)


def _trajectory_summary(result: dict[str, Any]) -> dict[str, Any]:
    text = _trajectory_text(result, 80_000)
    first_user = ""
    notable_errors: list[str] = []
    for line in text.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not first_user and event.get("type") == "user_message":
            first_user = _short(event.get("text", ""), 800)
        joined = json.dumps(event, ensure_ascii=False)
        low = joined.lower()
        if any(token in low for token in ("error", "traceback", "failed", "exception", "module not found")):
            notable_errors.append(_short(joined, 500))
        if len(notable_errors) >= 5:
            break
    return {
        "rollout_dir": result.get("rollout_dir"),
        "trajectory_files": _trajectory_files(result),
        "first_user_message": first_user,
        "notable_errors": notable_errors,
    }


def _diff_stats(diff_path: Path) -> dict[str, dict[str, int]]:
    stats: dict[str, dict[str, int]] = {}
    current = ""
    if not diff_path.is_file():
        return stats
    for line in diff_path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("+++ after/"):
            current = line[len("+++ after/") :]
            stats.setdefault(current, {"added_lines": 0, "removed_lines": 0})
            continue
        if not current:
            continue
        if line.startswith("+") and not line.startswith("+++"):
            stats[current]["added_lines"] += 1
        elif line.startswith("-") and not line.startswith("---"):
            stats[current]["removed_lines"] += 1
    return stats


def _rewrite_usage(method_dir: Path) -> dict[str, Any]:
    raw_dir = method_dir / "workspace" / "rewrite_raw"
    by_skill = []
    total_tokens = 0
    total_duration = 0.0
    if raw_dir.is_dir():
        for path in sorted(raw_dir.glob("*.json")):
            data = _load_json(path)
            usage = data.get("usage") or {}
            tokens = int(usage.get("total_tokens") or 0)
            duration = float(data.get("duration_sec") or 0.0)
            total_tokens += tokens
            total_duration += duration
            by_skill.append(
                {
                    "skill_log": str(path),
                    "ok": data.get("ok"),
                    "usage": usage,
                    "duration_sec": duration,
                    "parsed_keys": data.get("parsed_keys", []),
                }
            )
    diag_raw = _load_json(method_dir / "workspace" / "diagnosis_raw.json")
    diag_usage = diag_raw.get("usage") or {}
    total_tokens += int(diag_usage.get("total_tokens") or 0)
    total_duration += float(diag_raw.get("duration_sec") or 0.0)
    return {
        "diagnosis_usage": diag_usage,
        "diagnosis_duration_sec": diag_raw.get("duration_sec"),
        "rewrite_by_skill": by_skill,
        "total_optimizer_tokens": total_tokens,
        "total_optimizer_duration_sec": round(total_duration, 3),
    }


def _skill_usage_evidence(result: dict[str, Any], skill_paths: list[str]) -> dict[str, Any]:
    text = _trajectory_text(result)
    low = text.lower()
    evidence = {}
    for path in skill_paths:
        name = Path(path).parent.name.lower()
        evidence[path] = {
            "mentioned_in_trajectory": bool(name and name in low) or path.lower() in low,
            "searched_terms": [path, name],
        }
    return evidence


def _classify_outcome(
    *,
    baseline: dict[str, Any],
    method_result: dict[str, Any],
    manifest: dict[str, Any],
    usage_evidence: dict[str, Any],
) -> tuple[str, str]:
    if not method_result:
        return "missing_method_result", "No method_result.json was found. The method has not been evaluated or recorded."
    if method_result.get("prepare_only") is True:
        return "prepared_not_evaluated", "The repaired skill bundle was generated, but method-skill evaluation has not been run yet."
    if method_result.get("error_category") == "method_generation_failed":
        return "method_generation_failed", "The optimizer failed before producing a complete repaired skill bundle."
    if method_result.get("error_category") == "method_evaluation_failed":
        return "method_evaluation_failed", "The repaired skill was generated, but BenchmarkExecutor failed while evaluating it."
    if method_result.get("comparable") is not True:
        if method_result.get("skill_exposure_verified") is False:
            return "skill_not_exposed", "Benchmark evidence says the candidate skill was not verified as exposed to the model, so this result is not comparable."
        return "non_comparable", "Benchmark marked the run as non-comparable; inspect error fields and rollout logs before counting it."
    if method_result.get("task_passed") is True:
        return "repair_success", "The method-skill run is comparable and passed the task verifier."
    rewritten = manifest.get("rewritten_files") or []
    if not rewritten:
        return "skill_not_located", "No skill was selected and rewritten, so the failure is best treated as localization failure."
    if usage_evidence and not any(v.get("mentioned_in_trajectory") for v in usage_evidence.values()):
        return "skill_maybe_not_called", "The repaired skill was exposed, but the trajectory did not contain an obvious mention of the repaired skill name; this is a heuristic signal, not proof."
    if baseline.get("task_passed") is True:
        return "regression_after_repair", "Baseline passed but the repaired-skill run failed, so the repair likely introduced a regression or changed agent behavior harmfully."
    return "located_but_not_fixed", "A skill was localized and rewritten, but the comparable method-skill run still failed; likely causes are insufficient repair content or downstream model execution limits."


def _evaluation_cost(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "wall_time_sec": result.get("wall_time_sec") or result.get("duration_sec"),
        "cost_usd": result.get("cost_usd"),
        "provider_requests": result.get("provider_requests"),
        "agent_iterations": result.get("agent_iterations"),
        "termination_reason": result.get("termination_reason"),
    }


def write_method_diagnosis_report(*, run_id: str, method_id: str, task_id: str) -> dict[str, Any]:
    method_dir = ROOT / "experiments" / run_id / "methods" / method_id / task_id
    baseline_path = ROOT / "experiments" / run_id / "baseline" / "original-skill" / task_id / "benchmark_result.json"
    method_result_path = method_dir / "method_result.json"
    manifest_path = method_dir / "workspace" / "optimization_manifest.json"
    diff_path = method_dir / "diff.patch"

    baseline = _load_json(baseline_path)
    method_result = _load_json(method_result_path)
    manifest = _load_json(manifest_path)
    diff_stats = _diff_stats(diff_path)
    rewritten = manifest.get("rewritten_files") or []
    skill_paths = [str(item.get("path")) for item in rewritten if isinstance(item, dict) and item.get("path")]
    usage_evidence = _skill_usage_evidence(method_result, skill_paths) if method_result else {}
    outcome_category, outcome_analysis = _classify_outcome(
        baseline=baseline,
        method_result=method_result,
        manifest=manifest,
        usage_evidence=usage_evidence,
    )
    rewrite_usage = _rewrite_usage(method_dir)

    skills = []
    by_path = {str(item.get("path")): item for item in rewritten if isinstance(item, dict)}
    inventory = manifest.get("skill_inventory") or []
    seen_paths = set()
    for item in inventory:
        path = str(item.get("path", ""))
        if not path:
            continue
        seen_paths.add(path)
        rewritten_item = by_path.get(path, {})
        skills.append(
            {
                "path": path,
                "name": item.get("name"),
                "heading": item.get("heading"),
                "diagnosed_for_repair": path in by_path,
                "diagnosis": rewritten_item.get("diagnosis", ""),
                "repair_instruction": rewritten_item.get("repair_instruction", ""),
                "confidence": rewritten_item.get("confidence", ""),
                "change_summary": rewritten_item.get("change_summary", []),
                "diff_stats": diff_stats.get(path, {"added_lines": 0, "removed_lines": 0}),
                "usage_evidence": usage_evidence.get(path, {}),
            }
        )
    for path, rewritten_item in by_path.items():
        if path not in seen_paths:
            skills.append(
                {
                    "path": path,
                    "diagnosed_for_repair": True,
                    "diagnosis": rewritten_item.get("diagnosis", ""),
                    "repair_instruction": rewritten_item.get("repair_instruction", ""),
                    "confidence": rewritten_item.get("confidence", ""),
                    "change_summary": rewritten_item.get("change_summary", []),
                    "diff_stats": diff_stats.get(path, {"added_lines": 0, "removed_lines": 0}),
                    "usage_evidence": usage_evidence.get(path, {}),
                }
            )

    report = {
        "schema_version": "skillopt-eva-diagnosis-v1",
        "run_id": run_id,
        "method_id": method_id,
        "task_id": task_id,
        "questions": {
            "diagnosis_pre_repair_trajectory": {
                "baseline_result": str(baseline_path) if baseline_path.exists() else None,
                "baseline_task_passed": baseline.get("task_passed"),
                "baseline_comparable": baseline.get("comparable"),
                "baseline_error_category": baseline.get("error_category") or baseline.get("verifier_error_category"),
                "trajectory": _trajectory_summary(baseline),
            },
            "diagnosed_skill_and_repair": {
                "diagnosis_file": str(method_dir / "workspace" / "diagnosis.json"),
                "manifest_file": str(manifest_path) if manifest_path.exists() else None,
                "diff_file": str(diff_path) if diff_path.exists() else None,
                "overall_diagnosis": (manifest.get("diagnosis") or {}).get("overall_diagnosis"),
                "skills": skills,
            },
            "repair_outcome": {
                "task_passed": method_result.get("task_passed"),
                "comparable": method_result.get("comparable"),
                "skill_exposure_verified": method_result.get("skill_exposure_verified"),
                "outcome_category": outcome_category,
                "analysis": outcome_analysis,
                "method_error_category": method_result.get("error_category") or method_result.get("verifier_error_category"),
                "method_error": _short(method_result.get("error") or method_result.get("verifier_error") or "", 1200),
                "method_trajectory": _trajectory_summary(method_result),
            },
            "repair_time_and_cost": {
                "optimizer": rewrite_usage,
                "baseline_evaluation": _evaluation_cost(baseline),
                "method_evaluation": _evaluation_cost(method_result),
                "known_total_cost_usd": sum(
                    float(x or 0.0)
                    for x in (baseline.get("cost_usd"), method_result.get("cost_usd"))
                    if isinstance(x, int | float)
                ),
            },
        },
    }
    write_json(method_dir / "diagnosis_report.json", report)
    (method_dir / "diagnosis_report.md").write_text(_render_markdown(report), encoding="utf-8")
    return report


def _render_markdown(report: dict[str, Any]) -> str:
    q = report["questions"]
    pre = q["diagnosis_pre_repair_trajectory"]
    repair = q["diagnosed_skill_and_repair"]
    outcome = q["repair_outcome"]
    cost = q["repair_time_and_cost"]
    lines = [
        f"# Diagnosis Report: {report['method_id']} / {report['task_id']}",
        "",
        "## 1. 诊断修复前轨迹",
        f"- baseline_result: `{pre.get('baseline_result')}`",
        f"- baseline comparable/pass: `{pre.get('baseline_comparable')}` / `{pre.get('baseline_task_passed')}`",
        f"- baseline error category: `{pre.get('baseline_error_category')}`",
        f"- rollout_dir: `{pre.get('trajectory', {}).get('rollout_dir')}`",
        "",
        "## 2. 诊断定位的 skill，以及如何修复",
        f"- overall diagnosis: {repair.get('overall_diagnosis') or ''}",
        f"- diff: `{repair.get('diff_file')}`",
    ]
    for skill in repair.get("skills", []):
        lines.extend(
            [
                f"- `{skill.get('path')}` diagnosed={skill.get('diagnosed_for_repair')} confidence={skill.get('confidence') or 'n/a'}",
                f"  - diagnosis: {skill.get('diagnosis') or ''}",
                f"  - repair: {skill.get('repair_instruction') or ''}",
                f"  - change_summary: {skill.get('change_summary') or []}",
                f"  - diff_stats: {skill.get('diff_stats')}",
            ]
        )
    lines.extend(
        [
            "",
            "## 3. 是否修复成功及原因",
            f"- comparable/pass: `{outcome.get('comparable')}` / `{outcome.get('task_passed')}`",
            f"- skill_exposure_verified: `{outcome.get('skill_exposure_verified')}`",
            f"- outcome_category: `{outcome.get('outcome_category')}`",
            f"- analysis: {outcome.get('analysis')}",
            "",
            "## 4. 修复时间及成本开销",
            f"- optimizer total tokens: `{cost.get('optimizer', {}).get('total_optimizer_tokens')}`",
            f"- optimizer duration sec: `{cost.get('optimizer', {}).get('total_optimizer_duration_sec')}`",
            f"- baseline evaluation: `{cost.get('baseline_evaluation')}`",
            f"- method evaluation: `{cost.get('method_evaluation')}`",
            f"- known_total_cost_usd: `{cost.get('known_total_cost_usd')}`",
            "",
        ]
    )
    return "\n".join(lines)
