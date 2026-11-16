#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import json
import os
import shutil
import sys
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters.common.bundles import copy_original_bundle, ensure_complete_skill_bundle, write_bundle_diff  # noqa: E402
from adapters.common.executor_api import run_method_skill, write_json  # noqa: E402
from adapters.common.diagnosis_report import write_method_diagnosis_report  # noqa: E402
from adapters.common.method_profile import method_profile  # noqa: E402
from adapters.common.repair_loop import repair_rounds_r, score_benchmark_result, smoke_mode  # noqa: E402


METHODS = {
    "skillopt": "adapters.skillopt_adapter.runner",
    "skillopt-lite": "adapters.skillopt_lite_adapter.runner",
}

SAME_TASK_GATE_LEAKAGE = (
    "Acceptance uses the same task that is reported (same-task leakage). "
    "This is NOT held-out val/test selection as in original SkillOpt / Lite."
)


def write_method_failure(out_dir: Path, task_id: str, method_id: str, category: str, exc: BaseException) -> None:
    write_json(
        out_dir / "method_result.json",
        {
            "task_id": task_id,
            "method_id": method_id,
            "task_passed": False,
            "comparable": False,
            "error_category": category,
            "error": repr(exc),
            "traceback": traceback.format_exc(),
        },
    )


def _load_json(path: Path | None) -> dict | None:
    if not path or not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _collect_rejected_proposal(round_ws: Path, repair_round: int, reason: str) -> dict[str, Any] | None:
    """Capture rejected edits/suggestions so the next round can avoid repeating them."""
    manifest = _load_json(round_ws / "optimization_manifest.json")
    if not isinstance(manifest, dict):
        return None
    proposals: list[dict[str, Any]] = []
    for item in manifest.get("rewritten_files") or []:
        if not isinstance(item, dict):
            continue
        proposals.append(
            {
                "path": item.get("path"),
                "update_mode_used": item.get("update_mode_used"),
                "proposed_edits": item.get("proposed_edits") or [],
                "edit_reports": item.get("edit_reports") or [],
                "suggestion_prefix": str(item.get("suggestion") or "")[:800],
                "change_summary": item.get("change_summary") or [],
                "fallback_reason": item.get("fallback_reason"),
            }
        )
    return {
        "round": repair_round,
        "reason": reason,
        "method": manifest.get("method"),
        "update_mode": (manifest.get("route_b") or {}).get("update_mode") if isinstance(manifest.get("route_b"), dict) else None,
        "proposals": proposals,
    }


def _is_failure_result(data: dict | None) -> bool:
    """Treat missing/non-pass as failure evidence worth carrying forward."""
    if not isinstance(data, dict):
        return True
    if data.get("ok") is False and "task_passed" not in data:
        return True
    return data.get("task_passed") is not True


def _gate_invalid_reason(data: dict | None) -> str | None:
    """Return why a gate is unusable as Skill evidence, or ``None`` if healthy."""
    if not isinstance(data, dict):
        return "missing_gate_result"
    termination = str(data.get("termination_reason") or "").strip().lower()
    error_category = str(data.get("error_category") or "").strip().lower()
    if termination in {"infrastructure_error", "provider_error", "setup_error"}:
        return f"termination_reason:{termination}"
    if error_category in {
        "timeout",
        "infrastructure",
        "provider",
        "sandbox",
        "dependency",
        "setup",
    }:
        return f"error_category:{error_category}"
    if data.get("execution_ok") is False:
        return "execution_ok:false"
    if data.get("comparable") is not True:
        return "comparable:not_true"
    if not isinstance(data.get("task_passed"), bool):
        return "task_passed:not_boolean"
    if not isinstance(data.get("reward"), (int, float)):
        return "reward:missing"
    return None


def _gate_attempt_limit() -> int:
    raw = os.environ.get("SKILLOPT_EVA_GATE_INFRA_ATTEMPTS", "2")
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError("SKILLOPT_EVA_GATE_INFRA_ATTEMPTS must be an integer") from exc
    if value < 1:
        raise ValueError("SKILLOPT_EVA_GATE_INFRA_ATTEMPTS must be >= 1")
    return value


def _append_failure_evidence(
    bundle: list[tuple[str, Path]],
    *,
    label: str,
    path: Path,
    payload: dict | None,
) -> None:
    if not path.is_file():
        return
    if not _is_failure_result(payload):
        return
    # Avoid duplicate paths if the same file is appended twice.
    resolved = str(path.resolve())
    if any(str(existing.resolve()) == resolved for _, existing in bundle):
        return
    bundle.append((label, path))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--method", required=True, choices=sorted(METHODS))
    parser.add_argument("--task", required=True)
    parser.add_argument("--run-id", default=f"run-{datetime.now(UTC):%Y%m%dT%H%M%SZ}")
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()

    # These tasks pin x86_64-only PyTorch-family CPU wheels. On Apple Silicon,
    # build and run their unmodified upstream images under Docker's amd64
    # emulation rather than changing the benchmark dependency versions.
    if args.task in {"multilingual-video-dubbing", "simpo-code-reproduction"}:
        os.environ.setdefault("DOCKER_DEFAULT_PLATFORM", "linux/amd64")

    out_dir = ROOT / "experiments" / args.run_id / "methods" / args.method / args.task
    result_path = out_dir / "method_result.json"
    if result_path.is_file():
        print(f"[skip existing] {result_path}")
        return 0
    if out_dir.exists() and any(out_dir.iterdir()):
        raise FileExistsError(f"Partial method directory exists without result; inspect or move it before retrying: {out_dir}")

    workspace = out_dir / "workspace"
    before_skill = out_dir / "before_skill"
    after_skill = out_dir / "after_skill"
    best_skill = out_dir / "best_skill"

    baseline_result = ROOT / "experiments" / args.run_id / "baseline" / "original-skill" / args.task / "benchmark_result.json"
    baseline_arg = baseline_result if baseline_result.is_file() else None
    baseline_data = _load_json(baseline_arg)
    profile = method_profile(args.method)

    try:
        copy_original_bundle(args.task, before_skill)
        if best_skill.exists():
            shutil.rmtree(best_skill)
        shutil.copytree(before_skill, best_skill, symlinks=False)

        generate = importlib.import_module(METHODS[args.method]).generate_candidate_skill
        max_rounds = repair_rounds_r(bonus=int(profile.get("repair_rounds_bonus") or 0))
        rounds_log: list[dict] = []
        rejected_buffer: list[dict[str, Any]] = []
        best_score = score_benchmark_result(baseline_data)
        best_passed = bool(baseline_data and baseline_data.get("task_passed") is True)
        best_comparable = bool(baseline_data and baseline_data.get("comparable") is True)
        best_result = baseline_data
        # Accumulate ALL prior failure trajectories for later rounds (baseline + failed gates).
        evidence_bundle: list[tuple[str, Path]] = []
        if baseline_arg:
            _append_failure_evidence(
                evidence_bundle,
                label="baseline",
                path=baseline_arg,
                payload=baseline_data,
            )
        edit_from = best_skill

        for repair_round in range(1, max_rounds + 1):
            round_ws = workspace / f"round_{repair_round}"
            candidate_id = f"{args.task}-round-{repair_round}-candidate-1"
            print(
                f"[repair] method={args.method} task={args.task} round={repair_round}/{max_rounds} "
                f"profile={profile.get('label')} rejected_buffer={len(rejected_buffer)} "
                f"failure_evidence={len(evidence_bundle)}",
                flush=True,
            )
            generate(
                task_id=args.task,
                workspace=round_ws,
                before_skill=edit_from,
                after_skill=after_skill,
                baseline_result=baseline_arg,
                run_id=args.run_id,
                repair_round=repair_round,
                allow_overwrite=True,
                rejected_buffer=rejected_buffer,
                evidence_paths=list(evidence_bundle),
            )
            ensure_complete_skill_bundle(after_skill)
            candidate_skill = round_ws / "candidate_skill"
            if candidate_skill.exists():
                shutil.rmtree(candidate_skill)
            shutil.copytree(after_skill, candidate_skill, symlinks=False)
            write_json(
                round_ws / "candidate_manifest.json",
                {
                    "candidate_id": candidate_id,
                    "task_id": args.task,
                    "repair_round": repair_round,
                    "skill_bundle": str(candidate_skill),
                    "generated_from": str(edit_from),
                    "optimization_manifest": str(round_ws / "optimization_manifest.json"),
                },
            )
            # Keep root workspace pointers for diagnosis_report compatibility.
            for name in ("diagnosis.json", "diagnosis_raw.json", "optimization_manifest.json"):
                src = round_ws / name
                if src.is_file():
                    shutil.copy2(src, workspace / name)

            if args.prepare_only:
                decision_payload = {
                    "round": repair_round,
                    "candidate_id": candidate_id,
                    "decision": "prepare_only",
                    "reason": "evaluation_disabled",
                    "evaluated": False,
                }
                write_json(round_ws / "decision.json", decision_payload)
                rounds_log.append(decision_payload)
                break

            gate_attempts: list[dict[str, Any]] = []
            result: dict[str, Any] | None = None
            invalid_reason: str | None = None
            max_gate_attempts = _gate_attempt_limit()
            for gate_attempt in range(1, max_gate_attempts + 1):
                try:
                    attempt_result = run_method_skill(
                        task_id=args.task,
                        method_id=args.method,
                        run_id=args.run_id,
                        skill_bundle=after_skill,
                        stage=f"round-{repair_round}-gate-attempt-{gate_attempt}",
                        persist_method_result=False,
                    )
                except Exception as exc:  # noqa: BLE001
                    attempt_result = {
                        "ok": False,
                        "task_passed": None,
                        "execution_ok": False,
                        "comparable": False,
                        "termination_reason": "infrastructure_error",
                        "error_category": "evaluation_exception",
                        "error": repr(exc),
                        "traceback": traceback.format_exc(),
                    }
                invalid_reason = _gate_invalid_reason(attempt_result)
                attempt_path = round_ws / "gate_attempts" / f"attempt_{gate_attempt}.json"
                write_json(attempt_path, attempt_result)
                gate_attempts.append(
                    {
                        "attempt": gate_attempt,
                        "result": str(attempt_path),
                        "rollout_id": attempt_result.get("rollout_id"),
                        "rollout_dir": attempt_result.get("rollout_dir"),
                        "valid": invalid_reason is None,
                        "invalid_reason": invalid_reason,
                    }
                )
                if invalid_reason is None:
                    result = attempt_result
                    break
                print(
                    f"[gate-invalid] round={repair_round} attempt={gate_attempt}/{max_gate_attempts} "
                    f"reason={invalid_reason} rollout_id={attempt_result.get('rollout_id')}",
                    flush=True,
                )

            if result is None:
                last_result = _load_json(Path(gate_attempts[-1]["result"])) or {}
                write_json(round_ws / "gate_result.json", last_result)
                decision_payload = {
                    "round": repair_round,
                    "candidate_id": candidate_id,
                    "decision": "invalid",
                    "reason": "infrastructure_evaluation_failed",
                    "invalid_reason": invalid_reason,
                    "score": None,
                    "best_score": best_score,
                    "rejected_buffer_size": len(rejected_buffer),
                    "failure_evidence_size": len(evidence_bundle),
                    "candidate_skill": str(candidate_skill),
                    "gate_result": str(round_ws / "gate_result.json"),
                    "gate_attempts": gate_attempts,
                }
                write_json(round_ws / "decision.json", decision_payload)
                write_json(
                    round_ws / "round_manifest.json",
                    {
                        "candidate_id": candidate_id,
                        "diagnosis_evidence": str(round_ws / "evidence_bundle.json"),
                        "diagnosis": str(round_ws / "diagnosis.json"),
                        "diagnosis_samples": str(round_ws / "diagnosis_samples"),
                        "diagnosis_merge": str(round_ws / "diagnosis_merge.json"),
                        "proposal": str(round_ws / "optimization_manifest.json"),
                        "rewrite_attempts": str(round_ws / "rewrite_raw"),
                        "candidate_skill": str(candidate_skill),
                        "gate_attempts": gate_attempts,
                        "gate_result": str(round_ws / "gate_result.json"),
                        "decision": str(round_ws / "decision.json"),
                    },
                )
                rounds_log.append(decision_payload)
                raise RuntimeError(
                    f"candidate gate remained infrastructure-invalid after {max_gate_attempts} attempts: "
                    f"{invalid_reason}"
                )

            write_json(round_ws / "gate_result.json", result)
            score = score_benchmark_result(result)
            passed = bool(result.get("task_passed") is True)
            comparable = bool(result.get("comparable") is True)
            # A valid gate result must outrank a non-comparable imported
            # baseline even when both have the same numeric reward. Otherwise
            # a healthy repair evaluation can incorrectly finish by selecting
            # the unusable baseline artifact as the gated "best" result.
            improved = (
                (comparable and not best_comparable)
                or (comparable == best_comparable and score > best_score + 1e-12)
                or (passed and not best_passed)
            )
            if improved:
                if best_skill.exists():
                    shutil.rmtree(best_skill)
                shutil.copytree(after_skill, best_skill, symlinks=False)
                best_score = score
                best_passed = passed
                best_comparable = comparable
                best_result = result
                decision = "keep"
                decision_reason = "gate_improved"
            else:
                rejected = _collect_rejected_proposal(round_ws, repair_round, "gate_no_improve")
                if rejected:
                    rejected_buffer.append(rejected)
                if after_skill.exists():
                    shutil.rmtree(after_skill)
                shutil.copytree(best_skill, after_skill, symlinks=False)
                decision = "revert"
                decision_reason = "gate_no_improve"

            # Carry forward every non-passing gate trajectory for later rounds.
            _append_failure_evidence(
                evidence_bundle,
                label=f"round_{repair_round}_gate",
                path=round_ws / "gate_result.json",
                payload=result,
            )

            rollout_id = result.get("rollout_id")
            rollout_dir = result.get("rollout_dir")
            decision_payload = {
                "round": repair_round,
                "candidate_id": candidate_id,
                "decision": decision,
                "reason": decision_reason,
                "score": score,
                "passed": passed,
                "comparable": comparable,
                "best_score": best_score,
                "best_passed": best_passed,
                "rollout_id": rollout_id,
                "rollout_dir": rollout_dir,
                "candidate_skill": str(candidate_skill),
                "gate_result": str(round_ws / "gate_result.json"),
                "rejected_buffer_size": len(rejected_buffer),
                "failure_evidence_size": len(evidence_bundle),
                "gate_attempts": gate_attempts,
            }
            write_json(round_ws / "decision.json", decision_payload)
            write_json(
                round_ws / "round_manifest.json",
                {
                    "candidate_id": candidate_id,
                    "diagnosis_evidence": str(round_ws / "evidence_bundle.json"),
                    "diagnosis": str(round_ws / "diagnosis.json"),
                    "diagnosis_samples": str(round_ws / "diagnosis_samples"),
                    "diagnosis_merge": str(round_ws / "diagnosis_merge.json"),
                    "proposal": str(round_ws / "optimization_manifest.json"),
                    "rewrite_attempts": str(round_ws / "rewrite_raw"),
                    "candidate_skill": str(candidate_skill),
                    "gate_attempts": gate_attempts,
                    "rollout_id": rollout_id,
                    "rollout_dir": rollout_dir,
                    "gate_result": str(round_ws / "gate_result.json"),
                    "decision": str(round_ws / "decision.json"),
                },
            )
            rounds_log.append(decision_payload)
            print(
                f"[gate] round={repair_round} decision={decision} "
                f"score={score:.4f} best={best_score:.4f} passed={passed} "
                f"failure_evidence={len(evidence_bundle)}",
                flush=True,
            )
            edit_from = best_skill
            if best_passed:
                break

        write_bundle_diff(before_skill, after_skill, out_dir / "diff.patch")
        write_json(
            workspace / "repair_loop.json",
            {
                "method_profile": profile,
                "smoke_mode": smoke_mode(),
                "diagnosis_n_env": "SKILLOPT_EVA_DIAGNOSIS_N",
                "edit_budget_l_env": "SKILLOPT_EVA_EDIT_BUDGET_L",
                "repair_rounds_r": max_rounds,
                "rounds": rounds_log,
                "rejected_buffer": rejected_buffer,
                "failure_evidence": [
                    {"label": label, "path": str(path)} for label, path in evidence_bundle
                ],
                "final_best_score": best_score,
                "final_best_passed": best_passed,
                "same_task_gate": True,
                "same_task_gate_leakage": SAME_TASK_GATE_LEAKAGE,
                "note": (
                    "Gate uses the same task (not held-out val). "
                    "n=independent diagnosis samples; R=progressive repair rounds; "
                    "L=merge/edit budget. Rejected proposals feed the next round. "
                    "All prior failure trajectories (baseline + failed gates) are "
                    "accumulated into later-round diagnosis/edit evidence."
                ),
            },
        )
    except Exception as exc:  # noqa: BLE001
        write_method_failure(out_dir, args.task, args.method, "method_generation_failed", exc)
        try:
            write_method_diagnosis_report(run_id=args.run_id, method_id=args.method, task_id=args.task)
        except Exception as report_exc:  # noqa: BLE001
            print(f"report_failed={report_exc!r}", file=sys.stderr)
        print(f"generation_failed={exc!r}", file=sys.stderr)
        return 1

    if args.prepare_only:
        write_json(
            result_path,
            {
                "task_id": args.task,
                "method_id": args.method,
                "prepare_only": True,
                "task_passed": None,
                "comparable": None,
                "generated_skill": str(after_skill),
                "baseline_result": str(baseline_arg) if baseline_arg else None,
                "repair_rounds": rounds_log,
                "method_profile": profile,
            },
        )
        write_method_diagnosis_report(run_id=args.run_id, method_id=args.method, task_id=args.task)
        print(after_skill)
        return 0

    # Persist the best gated result as method_result.json
    if isinstance(best_result, dict):
        payload = dict(best_result)
        payload["repair_loop"] = rounds_log
        payload["gated_best"] = True
        payload["same_task_gate_leakage"] = SAME_TASK_GATE_LEAKAGE
        write_json(result_path, payload)
        if payload.get("rollout_id"):
            write_json(
                out_dir / "rollout_pointer.json",
                {
                    "method_id": args.method,
                    "rollout_id": payload["rollout_id"],
                    "selected_by_gate": True,
                },
            )
    write_method_diagnosis_report(run_id=args.run_id, method_id=args.method, task_id=args.task)
    print(f"comparable={(best_result or {}).get('comparable')} passed={best_passed} best_score={best_score}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
