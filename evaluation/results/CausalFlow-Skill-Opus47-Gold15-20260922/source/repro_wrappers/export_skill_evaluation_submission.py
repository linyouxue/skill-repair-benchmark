"""Export CausalFlow results to the shared Skill diagnosis/repair submission format.

The exporter does not inspect Gold or infer Skill defects from action-level CRS
steps. It copies the method's final complete Skill bundles into a portable
submission directory and can optionally invoke the shared evaluator.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path, PureWindowsPath
from typing import Any


class ExportError(ValueError):
    """A plan or method artifact cannot produce an honest submission."""


def _read_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExportError(f"cannot read JSON object {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ExportError(f"expected a JSON object: {path}")
    return value


def _nonempty(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ExportError(f"{label} must be a non-empty string")
    return value.strip()


def _task_id(value: Any) -> str:
    task_id = _nonempty(value, "task_id")
    if task_id in {".", ".."} or "/" in task_id or "\\" in task_id:
        raise ExportError(f"task_id must be one path component: {task_id}")
    return task_id


def _source_path(plan_path: Path, value: Any, label: str) -> Path:
    raw = _nonempty(value, label)
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = plan_path.parent / path
    return path.resolve(strict=True)


def _relative_file(value: Any, label: str) -> str:
    raw = _nonempty(value, label).replace("\\", "/")
    path = Path(raw)
    windows = PureWindowsPath(raw)
    if (
        raw == "."
        or path.is_absolute()
        or windows.drive
        or windows.root
        or ".." in path.parts
    ):
        raise ExportError(f"{label} must be relative to the Skill bundle: {raw}")
    return path.as_posix()


def _locations(prediction: dict[str, Any], label: str) -> list[dict[str, Any]]:
    supplied = prediction.get("locations")
    if supplied is None:
        supplied = [prediction] if "file" in prediction else []
    if not isinstance(supplied, list):
        raise ExportError(f"{label}.locations must be an array")
    locations: list[dict[str, Any]] = []
    for index, row in enumerate(supplied, 1):
        if not isinstance(row, dict):
            raise ExportError(f"{label}.locations[{index}] must be an object")
        location: dict[str, Any] = {
            "file": _relative_file(row.get("file"), f"{label}.locations[{index}].file")
        }
        if "section" in row:
            location["section"] = _nonempty(
                row["section"], f"{label}.locations[{index}].section"
            )
        if "start_line" in row or "end_line" in row:
            start, end = row.get("start_line"), row.get("end_line")
            if type(start) is not int or type(end) is not int or not 1 <= start <= end:
                raise ExportError(f"{label}.locations[{index}] has invalid line range")
            location.update(start_line=start, end_line=end)
        locations.append(location)
    return locations


def _diagnoses(
    payload: dict[str, Any], task_id: str
) -> tuple[list[dict[str, Any]], list[str]]:
    if (
        payload.get("status") == "invalid_baseline_replay"
        or payload.get("strict_baseline_replay_matches") is False
    ):
        raise ExportError(f"{task_id}: invalid baseline replay cannot be submitted")
    summary = payload.get("summary")
    if isinstance(summary, dict) and summary.get("audit_only") is True:
        raise ExportError(f"{task_id}: replay audit is not a diagnosis run")

    reported = payload.get("task_id")
    if reported is not None and reported != task_id:
        raise ExportError(f"{task_id}: diagnosis result reports task_id={reported!r}")
    warnings: list[str] = []
    if payload.get("task") not in (None, task_id):
        warnings.append("result_task_label_differs_from_task_id")

    if "diagnoses" in payload:
        predictions = payload["diagnoses"]
    elif "skill_diagnoses" in payload:
        predictions = payload["skill_diagnoses"]
    elif "predictions" in payload:
        predictions = payload["predictions"]
    elif "causal_attribution" in payload:
        predictions = []
        warnings.append("action_level_crs_has_no_explicit_skill_diagnosis")
        repair = payload.get("counterfactual_repair")
        if isinstance(repair, dict) and any(key.isdigit() for key in repair):
            warnings.append("action_level_repairs_do_not_modify_skill_bundle")
    else:
        raise ExportError(f"{task_id}: no diagnoses, predictions, or CausalFlow result")
    if not isinstance(predictions, list):
        raise ExportError(f"{task_id}: diagnoses must be an array")

    converted: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, prediction in enumerate(predictions, 1):
        if not isinstance(prediction, dict):
            raise ExportError(f"{task_id}: prediction {index} must be an object")
        label = f"{task_id}.prediction[{index}]"
        prediction_id = _nonempty(
            prediction.get("prediction_id", f"P{index}"), f"{label}.prediction_id"
        )
        if prediction_id in seen:
            raise ExportError(f"{task_id}: duplicate prediction_id {prediction_id}")
        seen.add(prediction_id)
        description = _nonempty(
            prediction.get("description") or prediction.get("explanation"),
            f"{label}.description",
        )
        converted.append(
            {
                "prediction_id": prediction_id,
                "description": description,
                "locations": _locations(prediction, label),
            }
        )
    return converted, warnings


def _bundle_files(root: Path) -> list[Path]:
    if not root.is_dir() or root.is_symlink():
        raise ExportError(f"final_bundle must be a real directory: {root}")
    files: list[Path] = []

    def walk_error(error: OSError) -> None:
        raise error

    for directory, directories, names in os.walk(
        root, topdown=True, followlinks=False, onerror=walk_error
    ):
        directories.sort()
        names.sort()
        for name in directories + names:
            path = Path(directory) / name
            if path.is_symlink():
                raise ExportError(f"Skill bundle contains a link: {path}")
        for name in names:
            path = Path(directory) / name
            if not path.is_file():
                raise ExportError(f"Skill bundle contains a non-file: {path}")
            files.append(path)
    if not files or not any(path.name == "SKILL.md" for path in files):
        raise ExportError(f"final_bundle has no SKILL.md: {root}")
    return files


def export_submission(
    plan_path: Path, template_path: Path, output: Path
) -> dict[str, Any]:
    plan_path = plan_path.resolve(strict=True)
    template_path = template_path.resolve(strict=True)
    output = output.expanduser().resolve()
    if output.exists():
        raise ExportError(f"refusing to overwrite existing output: {output}")
    plan = _read_object(plan_path)
    template = _read_object(template_path)
    method_id = _nonempty(plan.get("method_id"), "method_id")
    version = _nonempty(template.get("benchmark_version"), "benchmark_version")
    if plan.get("benchmark_version") != version:
        raise ExportError("plan benchmark_version differs from evaluation template")
    template_tasks = template.get("tasks")
    plan_tasks = plan.get("tasks")
    if not isinstance(template_tasks, list) or not isinstance(plan_tasks, list):
        raise ExportError("template and plan must both contain tasks arrays")
    if not all(isinstance(row, dict) for row in template_tasks + plan_tasks):
        raise ExportError("template and plan tasks must be objects")
    expected = [_task_id(row.get("task_id")) for row in template_tasks]
    rows = {_task_id(row.get("task_id")): row for row in plan_tasks}
    if len(rows) != len(plan_tasks) or len(expected) != len(set(expected)):
        raise ExportError("duplicate or malformed task entries")
    if set(rows) != set(expected):
        raise ExportError("plan must contain exactly the template task IDs")

    submission_tasks: list[dict[str, Any]] = []
    report_tasks: list[dict[str, Any]] = []
    bundles: list[tuple[Path, Path]] = []
    for task_id in expected:
        row = rows[task_id]
        original_pass = row.get("original_pass", False)
        if type(original_pass) is not bool:
            raise ExportError(f"{task_id}.original_pass must be boolean")
        if original_pass:
            run_id = _nonempty(row.get("original_run_id"), f"{task_id}.original_run_id")
            if "diagnosis_result" in row or "final_bundle" in row:
                raise ExportError(
                    f"{task_id}: original_pass cannot include diagnosis or final bundle"
                )
            submission_tasks.append(
                {"task_id": task_id, "original_pass": True, "original_run_id": run_id}
            )
            report_tasks.append(
                {"task_id": task_id, "status": "original_pass_requested"}
            )
            continue

        source = _source_path(
            plan_path, row.get("diagnosis_result"), f"{task_id}.diagnosis_result"
        )
        payload = _read_object(source)
        source_method = payload.get("method_id")
        if source_method is not None and source_method != method_id:
            raise ExportError(f"{task_id}: diagnosis method_id differs from plan")
        diagnoses, warnings = _diagnoses(payload, task_id)
        bundle = _source_path(
            plan_path, row.get("final_bundle"), f"{task_id}.final_bundle"
        )
        files = _bundle_files(bundle)
        if output.is_relative_to(bundle):
            raise ExportError(f"{task_id}: output cannot be inside final_bundle")
        relative_bundle = Path("tasks") / task_id / "skills"
        bundles.append((bundle, output / relative_bundle))
        submission_row: dict[str, Any] = {
            "task_id": task_id,
            "diagnoses": diagnoses,
            "repaired_bundle": relative_bundle.as_posix(),
        }
        if "executor_run_id" in row:
            submission_row["executor_run_id"] = _nonempty(
                row["executor_run_id"], f"{task_id}.executor_run_id"
            )
        submission_tasks.append(submission_row)
        report_tasks.append(
            {
                "task_id": task_id,
                "status": "ready_for_evaluation",
                "diagnosis_count": len(diagnoses),
                "bundle_file_count": len(files),
                "warnings": warnings,
            }
        )

    output.mkdir(parents=True)
    for source, target in bundles:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, target, symlinks=True)
        _bundle_files(target)
    submission = {
        "method_id": method_id,
        "benchmark_version": version,
        "tasks": submission_tasks,
    }
    (output / "submission.json").write_text(
        json.dumps(submission, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    report = {"submission": str(output / "submission.json"), "tasks": report_tasks}
    (output / "conversion_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--evaluator-script",
        type=Path,
        help="Optionally invoke the shared evaluator after export",
    )
    parser.add_argument(
        "--evaluation-mode",
        choices=("dry-run", "execute", "responses"),
        default="dry-run",
    )
    parser.add_argument("--gold", type=Path, help="Gold to use with the evaluator")
    parser.add_argument("--executor-runs-dir", type=Path)
    parser.add_argument("--judge-responses", type=Path)
    parser.add_argument("--judge-model")
    parser.add_argument("--api-key-env", default="OPENROUTER_API_KEY")
    parser.add_argument(
        "--reasoning-effort", choices=("none", "low", "medium", "high", "xhigh")
    )
    parser.add_argument("--omit-temperature", action="store_true")
    parser.add_argument("--max-input-chars", type=int, default=2_000_000)
    args = parser.parse_args(argv)
    try:
        if args.max_input_chars <= 0:
            raise ExportError("max-input-chars must be positive")
        if args.evaluator_script is None and (
            args.evaluation_mode != "dry-run"
            or args.gold is not None
            or args.executor_runs_dir is not None
            or args.judge_responses is not None
            or args.judge_model is not None
            or args.reasoning_effort is not None
            or args.omit_temperature
        ):
            raise ExportError("evaluation options require --evaluator-script")
        if args.evaluation_mode == "responses" and args.judge_responses is None:
            raise ExportError("responses mode requires --judge-responses")
        if args.evaluation_mode == "execute" and not args.judge_model:
            raise ExportError("execute mode requires --judge-model")
        if args.evaluation_mode != "responses" and args.judge_responses is not None:
            raise ExportError("--judge-responses requires responses mode")
        report = export_submission(args.plan, args.template, args.output)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        if args.evaluator_script is not None:
            script = args.evaluator_script.resolve(strict=True)
            command = [
                sys.executable,
                str(script),
                "--submission",
                report["submission"],
                "--output",
                str(args.output.resolve() / "evaluation-output"),
                "--max-input-chars",
                str(args.max_input_chars),
            ]
            if args.gold is not None:
                command.extend(["--gold", str(args.gold.resolve(strict=True))])
            if args.executor_runs_dir is not None:
                command.extend(
                    [
                        "--executor-runs-dir",
                        str(args.executor_runs_dir.resolve(strict=True)),
                    ]
                )
            if args.evaluation_mode == "dry-run":
                command.append("--dry-run")
            elif args.evaluation_mode == "responses":
                command.extend(
                    [
                        "--judge-responses",
                        str(args.judge_responses.resolve(strict=True)),
                    ]
                )
            else:
                command.extend(
                    [
                        "--execute",
                        "--judge-model",
                        args.judge_model,
                        "--api-key-env",
                        args.api_key_env,
                    ]
                )
                if args.reasoning_effort is not None:
                    command.extend(["--reasoning-effort", args.reasoning_effort])
                if args.omit_temperature:
                    command.append("--omit-temperature")
            return subprocess.run(command, check=False).returncode
        return 0
    except (ExportError, OSError) as exc:
        print(f"export error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
