#!/usr/bin/env python3
"""Local export of ACP trajectories into the official trajectory_timelines layout."""
from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

BEFORE_CONDITIONS = {
    "original-skill",
    "original_skill",
    "original",
    "baseline",
    "before",
}
AFTER_CONDITIONS = {
    "method-skill",
    "method_skill",
    "repaired-skill",
    "repaired_skill",
    "repair",
    "after",
}
ANSI_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
WS_RE = re.compile(r"[ \t]+")
EXIT_CODE_RE = re.compile(r"(?:Exit code|exit code)\s*:\s*(-?\d+)", re.I)
WORKDIR_RE = re.compile(r"Working directory\s*:\s*(.+)", re.I)


@dataclass
class RunMeta:
    task_id: str | None = None
    method_id: str | None = None
    run_id: str | None = None
    condition: str | None = None
    label: str = "unknown"
    model: str | None = None
    reasoning_effort: str | None = None
    protocol_id: str | None = None
    protocol_version: int | str | None = None
    execution_ok: bool | None = None
    task_passed: bool | None = None
    reward: float | int | None = None
    agent_iterations: int | None = None
    provider_requests: int | None = None
    wall_time_sec: float | int | None = None
    cost_usd: float | int | None = None
    termination_reason: str | None = None
    trajectory_source: str | None = None
    partial_trajectory: bool | None = None


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def first_non_none(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def condition_label(condition: str | None) -> str:
    if condition in BEFORE_CONDITIONS:
        return "before"
    if condition in AFTER_CONDITIONS:
        return "after"
    return "unknown"


def discover_meta(run_root: Path) -> RunMeta:
    request = read_json(run_root / "executor_request.json")
    result = read_json(run_root / "result.json")
    benchmark = read_json(run_root / "benchmark_result.json")
    executor = result.get("executor") if isinstance(result.get("executor"), dict) else {}
    protocol = request.get("protocol") if isinstance(request.get("protocol"), dict) else {}
    model_selection = (
        request.get("model_selection")
        if isinstance(request.get("model_selection"), dict)
        else {}
    )
    rewards = result.get("rewards") if isinstance(result.get("rewards"), dict) else {}
    raw_condition = first_non_none(
        request.get("condition"),
        executor.get("evaluation_condition"),
        benchmark.get("condition"),
        benchmark.get("evaluation_condition"),
    )
    condition = raw_condition.strip().lower() if isinstance(raw_condition, str) else None
    return RunMeta(
        task_id=first_non_none(benchmark.get("task_id"), request.get("task_id"), result.get("task_name")),
        method_id=first_non_none(benchmark.get("method_id"), request.get("method_id")),
        run_id=first_non_none(
            benchmark.get("rollout_id"), request.get("rollout_id"), result.get("rollout_name")
        ),
        condition=condition,
        label=condition_label(condition),
        model=first_non_none(
            benchmark.get("model"), result.get("model"), model_selection.get("model"), executor.get("model")
        ),
        reasoning_effort=first_non_none(
            benchmark.get("reasoning_effort"), model_selection.get("reasoning_effort")
        ),
        protocol_id=first_non_none(
            benchmark.get("protocol_id"), protocol.get("protocol_id"), executor.get("protocol_id")
        ),
        protocol_version=first_non_none(
            benchmark.get("protocol_version"), protocol.get("protocol_version"), executor.get("protocol_version")
        ),
        execution_ok=benchmark.get("execution_ok"),
        task_passed=benchmark.get("task_passed"),
        reward=first_non_none(benchmark.get("reward"), rewards.get("reward")),
        agent_iterations=benchmark.get("agent_iterations"),
        provider_requests=benchmark.get("provider_requests"),
        wall_time_sec=benchmark.get("wall_time_sec"),
        cost_usd=benchmark.get("cost_usd"),
        termination_reason=first_non_none(
            benchmark.get("termination_reason"), executor.get("stop_reason"), result.get("stop_reason")
        ),
        trajectory_source=result.get("trajectory_source"),
        partial_trajectory=result.get("partial_trajectory"),
    )


def clean_text(text: str) -> str:
    text = ANSI_RE.sub("", text)
    text = CONTROL_RE.sub("", text)
    return text.replace("\r\n", "\n").replace("\r", "\n")


def one_line(text: str, limit: int = 500) -> str:
    text = " ".join(part.strip() for part in clean_text(text).splitlines() if part.strip())
    text = WS_RE.sub(" ", text).strip()
    if len(text) > limit:
        return text[: limit - 1].rstrip() + "…"
    return text


def preview_lines(text: str, max_lines: int = 8, max_chars: int = 1600) -> str:
    lines: list[str] = []
    used = 0
    for raw in clean_text(text).splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        remaining = max_chars - used
        if remaining <= 0:
            break
        if len(line) > remaining:
            line = line[: max(0, remaining - 1)] + "…"
        lines.append(line)
        used += len(line) + 1
        if len(lines) >= max_lines:
            break
    return "\n".join(lines) if lines else "(no textual output)"


def collect_text_values(value: Any) -> list[str]:
    out: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "text" and isinstance(item, str):
                out.append(item)
            else:
                out.extend(collect_text_values(item))
    elif isinstance(value, list):
        for item in value:
            out.extend(collect_text_values(item))
    return out


def fenced(text: str, lang: str = "text") -> str:
    return f"````{lang}\n{text}\n````"


def md_value(value: Any) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def outcome_text(meta: RunMeta) -> str:
    if meta.execution_ok is False:
        return "INVALID_EXECUTION"
    if meta.task_passed is True:
        return "PASS"
    if meta.task_passed is False:
        return "FAIL"
    return "UNKNOWN"


def load_events(acp_path: Path) -> list[tuple[int, dict[str, Any]]]:
    events: list[tuple[int, dict[str, Any]]] = []
    with acp_path.open("r", encoding="utf-8-sig") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                events.append((line_no, obj))
    return events


def details(summary: str, body: str) -> list[str]:
    return ["<details>", f"<summary>{summary}</summary>", "", body, "", "</details>", ""]


def build_markdown(acp_path: Path, run_root: Path, meta: RunMeta, events: list[tuple[int, dict[str, Any]]]) -> str:
    tool_events = [(ln, obj) for ln, obj in events if obj.get("type") == "tool_call"]
    user_events = [(ln, obj) for ln, obj in events if obj.get("type") == "user_message"]
    type_counts: dict[str, int] = {}
    kind_counts: dict[str, int] = {}
    for _, obj in events:
        key = str(obj.get("type") or " ")
        type_counts[key] = type_counts.get(key, 0) + 1
        if obj.get("type") == "tool_call":
            kind = str(obj.get("kind") or " ")
            kind_counts[kind] = kind_counts.get(kind, 0) + 1
    tool_line_numbers = [ln for ln, _ in tool_events]
    lines: list[str] = [
        f"# {meta.task_id or run_root.name} — Execution Timeline ({meta.label})",
        "",
        "> Deterministically generated from `acp_trajectory.jsonl`. Raw JSONL remains the source of truth.",
        "",
        "## Run metadata",
        "",
        "| Field | Value |",
        "|---|---|",
    ]
    for key, value in [
        ("Task", meta.task_id),
        ("Method", meta.method_id),
        ("Run ID", meta.run_id),
        ("Condition", meta.condition),
        ("Before/After", meta.label),
        ("Model", meta.model),
        ("Execution OK", meta.execution_ok),
        ("Task passed", meta.task_passed),
        ("Outcome", outcome_text(meta)),
        ("Reward", meta.reward),
        ("Agent iterations", meta.agent_iterations),
        ("Tool-call steps", len(tool_events)),
        ("Raw ACP events", len(events)),
        ("Trajectory bytes", acp_path.stat().st_size),
    ]:
        lines.append(f"| {key} | {md_value(value).replace('|', r'\\|')} |")
    lines += ["", "## Event summary", "", "| Event type | Count |", "|---|---:|"]
    for event_type, count in sorted(type_counts.items()):
        lines.append(f"| `{event_type}` | {count} |")
    if kind_counts:
        lines += ["", "| Kind | Count |", "|---|---:|"]
        for kind, count in sorted(kind_counts.items()):
            lines.append(f"| `{kind}` | {count} |")
    lines.append("")
    if user_events:
        lines += ["## Task / user prompts", ""]
        for i, (line_no, obj) in enumerate(user_events, 1):
            text = obj.get("text")
            if isinstance(text, str):
                lines.append(f"### Prompt {i} · raw event {line_no}")
                lines.append("")
                lines.extend(details("Show prompt", fenced(clean_text(text))))
    lines += ["## Action timeline", ""]
    current_round = 0
    step = 0
    round_started = False
    for line_no, obj in events:
        event_type = obj.get("type")
        if event_type == "user_message":
            current_round += 1
            round_started = True
            lines += [f"## Round {current_round}", "", f"_Started at raw event {line_no}._", ""]
            continue
        if event_type == "tool_call":
            if not round_started:
                current_round = max(current_round, 1)
                round_started = True
                lines += [f"## Round {current_round}", ""]
            step += 1
            title = obj.get("title") if isinstance(obj.get("title"), str) else "(untitled tool call)"
            output_text = "\n".join(collect_text_values(obj.get("content")))
            exit_matches = EXIT_CODE_RE.findall(clean_text(output_text))
            workdir_matches = WORKDIR_RE.findall(clean_text(output_text))
            lines += [
                f"### Step {step} · `{md_value(obj.get('kind'))}` · `{md_value(obj.get('status'))}`",
                "",
                f"- **Action:** {one_line(title, 800)}",
                f"- **Raw event:** `{line_no}`",
            ]
            if exit_matches:
                lines.append(f"- **Exit code:** `{exit_matches[-1]}`")
            if workdir_matches:
                lines.append(f"- **Working directory:** `{workdir_matches[-1].strip()}`")
            lines.append("")
            if output_text.strip():
                lines.extend(details("Show tool-result preview", fenced(preview_lines(output_text))))
            continue
        if event_type == "agent_message":
            text = obj.get("text")
            if isinstance(text, str) and text.strip():
                has_later = any(tool_line > line_no for tool_line in tool_line_numbers)
                label = "Agent message" if has_later else "Agent final message"
                lines += [f"### {label}", "", f"- **Raw event:** `{line_no}`", ""]
                lines.extend(details("Show message", fenced(clean_text(text))))
            continue
        if event_type == "agent_thought":
            continue
        if event_type == "agent_iteration_outcome":
            lines += ["### Round outcome", "", f"- **Raw event:** `{line_no}`"]
            for key in ("stop_reason", "execution_status", "iterations_used", "skill_bundle_sha256"):
                if key in obj:
                    lines.append(f"- **{key}:** `{md_value(obj.get(key))}`")
            lines.append("")
            continue
        lines += [f"### Other event · `{md_value(event_type)}`", "", f"- **Raw event:** `{line_no}`", ""]
    lines += [
        "## Final outcome",
        "",
        f"- **Outcome:** `{outcome_text(meta)}`",
        f"- **Execution OK:** `{md_value(meta.execution_ok)}`",
        f"- **Task passed:** `{md_value(meta.task_passed)}`",
        f"- **Reward:** `{md_value(meta.reward)}`",
        "",
        "## Raw evidence",
        "",
        f"- ACP trajectory: `{acp_path.name}`",
        "",
    ]
    return "\n".join(lines)


def safe_filename_part(value: Any, fallback: str) -> str:
    text = str(value).strip() if value is not None else fallback
    if not text:
        text = fallback
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", text)
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip(" .-_")
    return text[:120] or fallback


def relative_posix(path: Path, base: Path) -> str:
    return path.resolve().relative_to(base.resolve()).as_posix()


def export_root(root: Path) -> int:
    acp_files = sorted(
        path
        for path in root.rglob("acp_trajectory.jsonl")
        if path.is_file() and path.parent.name == "trajectory" and "trajectory_timelines" not in path.parts
    )
    if not acp_files:
        print(f"No trajectories under {root}", file=sys.stderr)
        return 1
    central = root / "trajectory_timelines"
    entries = []
    unknown = 0
    for acp_path in acp_files:
        run_root = acp_path.parent.parent
        meta = discover_meta(run_root)
        bucket = meta.label if meta.label in {"before", "after"} else "unknown"
        if bucket == "unknown":
            unknown += 1
        out_path = central / bucket / f"{safe_filename_part(meta.task_id, 'unknown-task')}__{safe_filename_part(meta.method_id, 'unknown-method')}__{safe_filename_part(meta.run_id, run_root.name)}.md"
        events = load_events(acp_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(build_markdown(acp_path, run_root, meta, events), encoding="utf-8")
        print(f"[{meta.label.upper():7}] {meta.task_id} {meta.condition} -> {out_path.name}")
        entries.append(
            {
                "source": relative_posix(acp_path, root),
                "output": relative_posix(out_path, root),
                "run_root": relative_posix(run_root, root),
                "task_id": meta.task_id,
                "method_id": meta.method_id,
                "run_id": meta.run_id,
                "condition": meta.condition,
                "label": meta.label,
                "task_passed": meta.task_passed,
                "execution_ok": meta.execution_ok,
                "trajectory_empty": acp_path.stat().st_size == 0,
                "trajectory_bytes": acp_path.stat().st_size,
                "raw_event_count": len(events),
            }
        )
    index = {
        "schema_version": "1.0",
        "root": ".",
        "export_root": "trajectory_timelines",
        "count": len(entries),
        "pairing_key": ["task_id", "method_id"],
        "layout": {
            "before": "trajectory_timelines/before",
            "after": "trajectory_timelines/after",
            "unknown": "trajectory_timelines/unknown",
        },
        "label_policy": {
            "before": sorted(BEFORE_CONDITIONS),
            "after": sorted(AFTER_CONDITIONS),
            "unknown": "condition missing or not recognized",
        },
        "trajectories": entries,
    }
    (central / "trajectory_timeline_index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Converted {len(entries)} trajectories under {central}")
    if unknown:
        print(f"WARNING: {unknown} unlabeled trajectories", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    roots = [Path(arg) for arg in sys.argv[1:]]
    if not roots:
        print("usage: export_upload_trajectories.py <method-dir> [...]", file=sys.stderr)
        return 2
    status = 0
    for root in roots:
        status = max(status, export_root(root.resolve()))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
