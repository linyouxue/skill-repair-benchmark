#!/usr/bin/env python3
"""
Batch-convert BenchFlow/OpenHands ACP trajectories into deterministic,
human-readable Markdown timelines.

Design goals
------------
1. The scan root is arbitrary. Nothing is hard-coded to manual_annotation_runs.
2. Recursively find only:
       **/trajectory/acp_trajectory.jsonl
   (so agent/acp_trajectory.jsonl is ignored).
3. Determine before/after from run metadata, not from directory names:
       original-skill -> before
       method-skill   -> after
   Priority:
       executor_request.json: condition
       result.json: executor.evaluation_condition
       benchmark_result.json: condition/evaluation_condition (if present)
4. Write all generated Markdown into one centralized export directory:
       <root>/trajectory_timelines/before/
       <root>/trajectory_timelines/after/
       <root>/trajectory_timelines/unknown/
   The original run/trajectory directories are left untouched.
5. Do not semantically classify actions by wording.
   Each actual tool_call is one Step, in original order.
6. agent_thought bodies are intentionally omitted from the readable Markdown,
   while unknown event types are preserved as generic folded events.
7. Distinguish intermediate agent_message from final agent_message by whether
   another tool_call occurs later in the same trajectory.
8. Generate a root-level trajectory_timeline_index.json so before/after
   runs can be paired by task_id + method_id.

Usage
-----
python export_trajectory.py --root D:\\path\\to\\runs

# Preview without writing Markdown:
python export_trajectory.py --root D:\\path\\to\\runs --dry-run

# Keep existing Markdown files:
python export_trajectory.py --root D:\\path\\to\\runs --skip-existing

# Use a custom centralized output folder name:
python export_trajectory.py --root D:\\path\\to\\runs --export-dir-name readable_trajectories
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Iterable


ANSI_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
WS_RE = re.compile(r"[ \t]+")
EXIT_CODE_RE = re.compile(r"(?:Exit code|exit code)\s*:\s*(-?\d+)", re.I)
WORKDIR_RE = re.compile(r"Working directory\s*:\s*(.+)", re.I)
EDITED_FILE_RE = re.compile(
    r"\[File\s+(.+?)\s+edited with\s+(\d+)\s+changes?\.\]", re.I
)
TOOL_ERROR_RE = re.compile(
    r"(?:^|\n)(?:❌\s*)?\[An error occurred during execution\.\]", re.I
)

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


@dataclass
class RunMeta:
    task_id: str | None = None
    method_id: str | None = None
    run_id: str | None = None
    condition: str | None = None
    label: str = "unknown"  # before / after / unknown
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


@dataclass
class TimelineEntry:
    source: str
    output: str
    run_root: str
    task_id: str | None
    method_id: str | None
    run_id: str | None
    condition: str | None
    label: str
    task_passed: bool | None
    execution_ok: bool | None


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


def normalized_condition(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip().lower()


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

    executor = result.get("executor")
    if not isinstance(executor, dict):
        executor = {}

    protocol = request.get("protocol")
    if not isinstance(protocol, dict):
        protocol = {}

    model_selection = request.get("model_selection")
    if not isinstance(model_selection, dict):
        model_selection = {}

    rewards = result.get("rewards")
    if not isinstance(rewards, dict):
        rewards = {}

    condition = normalized_condition(
        first_non_none(
            request.get("condition"),
            executor.get("evaluation_condition"),
            benchmark.get("condition"),
            benchmark.get("evaluation_condition"),
        )
    )

    return RunMeta(
        task_id=first_non_none(
            benchmark.get("task_id"),
            request.get("task_id"),
            result.get("task_name"),
        ),
        method_id=first_non_none(
            benchmark.get("method_id"),
            request.get("method_id"),
        ),
        run_id=first_non_none(
            benchmark.get("rollout_id"),
            request.get("rollout_id"),
            result.get("rollout_name"),
        ),
        condition=condition,
        label=condition_label(condition),
        model=first_non_none(
            benchmark.get("model"),
            result.get("model"),
            model_selection.get("model"),
            executor.get("model"),
        ),
        reasoning_effort=first_non_none(
            benchmark.get("reasoning_effort"),
            model_selection.get("reasoning_effort"),
        ),
        protocol_id=first_non_none(
            benchmark.get("protocol_id"),
            protocol.get("protocol_id"),
            executor.get("protocol_id"),
        ),
        protocol_version=first_non_none(
            benchmark.get("protocol_version"),
            protocol.get("protocol_version"),
            executor.get("protocol_version"),
        ),
        execution_ok=benchmark.get("execution_ok"),
        task_passed=benchmark.get("task_passed"),
        reward=first_non_none(
            benchmark.get("reward"),
            rewards.get("reward"),
        ),
        agent_iterations=benchmark.get("agent_iterations"),
        provider_requests=benchmark.get("provider_requests"),
        wall_time_sec=benchmark.get("wall_time_sec"),
        cost_usd=benchmark.get("cost_usd"),
        termination_reason=first_non_none(
            benchmark.get("termination_reason"),
            executor.get("stop_reason"),
            result.get("stop_reason"),
        ),
        trajectory_source=result.get("trajectory_source"),
        partial_trajectory=result.get("partial_trajectory"),
    )


def clean_text(text: str) -> str:
    text = ANSI_RE.sub("", text)
    text = CONTROL_RE.sub("", text)
    return text.replace("\r\n", "\n").replace("\r", "\n")


def one_line(text: str, limit: int = 500) -> str:
    text = clean_text(text)
    text = " ".join(part.strip() for part in text.splitlines() if part.strip())
    text = WS_RE.sub(" ", text).strip()
    if len(text) > limit:
        return text[: limit - 1].rstrip() + "…"
    return text


def preview_lines(text: str, max_lines: int = 8, max_chars: int = 1600) -> str:
    text = clean_text(text)
    lines: list[str] = []
    used = 0
    for raw in text.splitlines():
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
    if not lines:
        return "(no textual output)"
    return "\n".join(lines)


def collect_text_values(value: Any) -> list[str]:
    """Collect textual payloads nested under keys named 'text'."""
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


def extract_tool_output(obj: dict[str, Any]) -> str:
    parts = collect_text_values(obj.get("content"))
    return "\n".join(parts)


def split_title(title: str) -> tuple[str, str | None]:
    """
    Deterministically separate a human label from a command when the ACP title
    uses the common "...: $ command" form. No semantic classification.
    """
    title = clean_text(title).strip()
    for marker in (": $ ", ":\n$ ", "\n$ "):
        if marker in title:
            left, right = title.split(marker, 1)
            return one_line(left, 600), "$ " + one_line(right, 1200)
    return one_line(title, 800), None


def extract_exit_code(text: str) -> int | None:
    matches = EXIT_CODE_RE.findall(clean_text(text))
    if not matches:
        return None
    try:
        return int(matches[-1])
    except ValueError:
        return None


def extract_workdir(text: str) -> str | None:
    matches = WORKDIR_RE.findall(clean_text(text))
    return matches[-1].strip() if matches else None


def extract_edit_info(text: str) -> list[tuple[str, int]]:
    """Extract file-editor success records without interpreting task semantics."""
    result: list[tuple[str, int]] = []
    for path, count in EDITED_FILE_RE.findall(clean_text(text)):
        try:
            n = int(count)
        except ValueError:
            n = 0
        result.append((path.strip(), n))
    return result


def observed_tool_result(text: str, exit_code: int | None) -> str | None:
    """Best-effort deterministic result signal separate from ACP transport status."""
    if exit_code is not None:
        return "success" if exit_code == 0 else "error"
    if TOOL_ERROR_RE.search(clean_text(text)):
        return "error"
    return None


def event_type_counts(events: list[tuple[int, dict[str, Any]]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for _, obj in events:
        key = str(obj.get("type") or "<missing>")
        counts[key] = counts.get(key, 0) + 1
    return counts


def tool_kind_counts(events: list[tuple[int, dict[str, Any]]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for _, obj in events:
        if obj.get("type") != "tool_call":
            continue
        key = str(obj.get("kind") or "<missing>")
        counts[key] = counts.get(key, 0) + 1
    return counts


def load_events(acp_path: Path) -> list[tuple[int, dict[str, Any]]]:
    events: list[tuple[int, dict[str, Any]]] = []
    with acp_path.open("r", encoding="utf-8-sig") as f:
        for line_no, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                # Preserve line position but skip malformed records in the
                # readable view. Raw JSONL remains the source of truth.
                continue
            if isinstance(obj, dict):
                events.append((line_no, obj))
    return events


def outcome_text(meta: RunMeta) -> str:
    if meta.execution_ok is False:
        return "INVALID_EXECUTION"
    if meta.task_passed is True:
        return "PASS"
    if meta.task_passed is False:
        return "FAIL"
    return "UNKNOWN"


def md_value(value: Any) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def fenced(text: str, lang: str = "text") -> str:
    # Use four backticks so embedded ``` in tool output does not break Markdown.
    return f"````{lang}\n{text}\n````"


def build_markdown(
    acp_path: Path,
    run_root: Path,
    meta: RunMeta,
    events: list[tuple[int, dict[str, Any]]],
) -> str:
    tool_events = [(ln, obj) for ln, obj in events if obj.get("type") == "tool_call"]
    user_events = [(ln, obj) for ln, obj in events if obj.get("type") == "user_message"]
    agent_messages = [(ln, obj) for ln, obj in events if obj.get("type") == "agent_message"]
    outcomes = [(ln, obj) for ln, obj in events if obj.get("type") == "agent_iteration_outcome"]
    type_counts = event_type_counts(events)
    kind_counts = tool_kind_counts(events)
    tool_line_numbers = [ln for ln, _ in tool_events]

    lines: list[str] = []
    title_task = meta.task_id or run_root.name
    lines.append(f"# {title_task} — Execution Timeline ({meta.label})")
    lines.append("")
    lines.append(
        "> Deterministically generated from `acp_trajectory.jsonl`. "
        "No LLM summarization or semantic action classification is used. "
        "`agent_thought` bodies are intentionally omitted; unknown observable event types are preserved "
        "as generic folded events. The raw JSONL remains the source of truth."
    )
    lines.append("")

    lines.append("## Run metadata")
    lines.append("")
    rows = [
        ("Task", meta.task_id),
        ("Method", meta.method_id),
        ("Run ID", meta.run_id),
        ("Condition", meta.condition),
        ("Before/After", meta.label),
        ("Model", meta.model),
        ("Reasoning effort", meta.reasoning_effort),
        ("Protocol", meta.protocol_id),
        ("Protocol version", meta.protocol_version),
        ("Execution OK", meta.execution_ok),
        ("Task passed", meta.task_passed),
        ("Outcome", outcome_text(meta)),
        ("Reward", meta.reward),
        ("Agent iterations", meta.agent_iterations),
        ("Provider requests", meta.provider_requests),
        ("Wall time (s)", meta.wall_time_sec),
        ("Cost (USD)", meta.cost_usd),
        ("Termination reason", meta.termination_reason),
        ("Trajectory source", meta.trajectory_source),
        ("Partial trajectory", meta.partial_trajectory),
        ("Tool-call steps", len(tool_events)),
        ("Raw ACP events", len(events)),
    ]
    lines.append("| Field | Value |")
    lines.append("|---|---|")
    for key, value in rows:
        value_str = md_value(value).replace("|", r"\|")
        lines.append(f"| {key} | {value_str} |")
    lines.append("")

    lines.append("## Event summary")
    lines.append("")
    lines.append("### ACP event types")
    lines.append("")
    lines.append("| Event type | Count |")
    lines.append("|---|---:|")
    for event_type, count in sorted(type_counts.items()):
        lines.append(f"| `{event_type}` | {count} |")
    lines.append("")
    if type_counts.get("agent_thought", 0):
        lines.append(
            f"> `{type_counts['agent_thought']}` `agent_thought` event(s) exist in the raw trajectory; "
            "their bodies are omitted from this readable export."
        )
        lines.append("")
    if kind_counts:
        lines.append("### Tool-call kinds")
        lines.append("")
        lines.append("| Kind | Count |")
        lines.append("|---|---:|")
        for kind, count in sorted(kind_counts.items()):
            lines.append(f"| `{kind}` | {count} |")
        lines.append("")

    if user_events:
        lines.append("## Task / user prompts")
        lines.append("")
        for i, (line_no, obj) in enumerate(user_events, 1):
            text = obj.get("text")
            if not isinstance(text, str):
                continue
            lines.append(f"### Prompt {i} · raw event {line_no}")
            lines.append("")
            lines.append("<details>")
            lines.append("<summary>Show prompt</summary>")
            lines.append("")
            lines.append(fenced(clean_text(text), "text"))
            lines.append("")
            lines.append("</details>")
            lines.append("")

    lines.append("## Action timeline")
    lines.append("")

    # Structural round number: increment only when a user_message appears.
    current_round = 0
    step = 0
    round_started = False

    for line_no, obj in events:
        event_type = obj.get("type")

        if event_type == "user_message":
            current_round += 1
            round_started = True
            lines.append(f"## Round {current_round}")
            lines.append("")
            lines.append(f"_Started at raw event {line_no}._")
            lines.append("")
            continue

        if event_type == "tool_call":
            if not round_started:
                current_round = max(current_round, 1)
                round_started = True
                lines.append(f"## Round {current_round}")
                lines.append("")

            step += 1
            kind = md_value(obj.get("kind"))
            status = md_value(obj.get("status"))
            title = obj.get("title")
            title = title if isinstance(title, str) else "(untitled tool call)"
            action, command = split_title(title)
            output_text = extract_tool_output(obj)
            exit_code = extract_exit_code(output_text)
            workdir = extract_workdir(output_text)
            edit_info = extract_edit_info(output_text) if kind == "edit" else []
            result_signal = observed_tool_result(output_text, exit_code)

            lines.append(f"### Step {step} · `{kind}` · `{status}`")
            lines.append("")
            lines.append(f"- **Action:** {action}")
            lines.append(f"- **Raw event:** `{line_no}`")
            call_id = obj.get("tool_call_id")
            if call_id:
                lines.append(f"- **Tool call ID:** `{call_id}`")
            if workdir:
                lines.append(f"- **Working directory:** `{workdir}`")
            if exit_code is not None:
                lines.append(f"- **Exit code:** `{exit_code}`")
            if result_signal is not None:
                lines.append(f"- **Observed tool result:** `{result_signal}`")
            for edited_path, change_count in edit_info:
                lines.append(f"- **Edited file:** `{edited_path}`")
                lines.append(f"- **Recorded changes:** `{change_count}`")
            if command:
                lines.append(f"- **Command preview:** `{command.replace('`', 'ˋ')}`")
            lines.append("")

            if output_text.strip():
                lines.append("<details>")
                lines.append("<summary>Show tool-result preview</summary>")
                lines.append("")
                lines.append(fenced(preview_lines(output_text), "text"))
                lines.append("")
                lines.append("</details>")
                lines.append("")
            continue

        if event_type == "agent_message":
            text = obj.get("text")
            if isinstance(text, str) and text.strip():
                has_later_tool_call = any(tool_line > line_no for tool_line in tool_line_numbers)
                message_label = "Agent message" if has_later_tool_call else "Agent final message"
                lines.append(f"### {message_label}")
                lines.append("")
                lines.append(f"- **Raw event:** `{line_no}`")
                lines.append("")
                lines.append("<details>")
                lines.append("<summary>Show message</summary>")
                lines.append("")
                lines.append(fenced(clean_text(text), "text"))
                lines.append("")
                lines.append("</details>")
                lines.append("")
            continue

        if event_type == "agent_iteration_outcome":
            lines.append("### Round outcome")
            lines.append("")
            lines.append(f"- **Raw event:** `{line_no}`")
            for key in (
                "prompt_ordinal",
                "stop_reason",
                "acp_stop_reason",
                "execution_status",
                "error_code",
                "max_iterations",
                "iterations_used",
                "skill_context_preloaded",
                "skill_bundle_sha256",
                "preloaded_skill_count",
                "experimental_text_only_retry_limit",
                "experimental_text_only_retries_used",
                "experimental_text_only_retry_exhausted",
            ):
                if key in obj:
                    lines.append(f"- **{key}:** `{md_value(obj.get(key))}`")
            lines.append("")
            continue

        if event_type == "agent_thought":
            # Deliberately hidden from the human-readable export; counted above.
            continue

        # Forward-compatible fallback: do not silently lose future/unknown
        # observable ACP event types. Keep a compact raw preview instead.
        lines.append(f"### Other event · `{md_value(event_type)}`")
        lines.append("")
        lines.append(f"- **Raw event:** `{line_no}`")
        lines.append("")
        lines.append("<details>")
        lines.append("<summary>Show raw event preview</summary>")
        lines.append("")
        raw_preview = json.dumps(obj, ensure_ascii=False, indent=2)
        lines.append(fenced(preview_lines(raw_preview, max_lines=40, max_chars=6000), "json"))
        lines.append("")
        lines.append("</details>")
        lines.append("")

    lines.append("## Final outcome")
    lines.append("")
    lines.append(f"- **Outcome:** `{outcome_text(meta)}`")
    lines.append(f"- **Execution OK:** `{md_value(meta.execution_ok)}`")
    lines.append(f"- **Task passed:** `{md_value(meta.task_passed)}`")
    lines.append(f"- **Reward:** `{md_value(meta.reward)}`")
    lines.append("")

    verifier_dir = run_root / "verifier"
    reward_txt = verifier_dir / "reward.txt"
    stdout_txt = verifier_dir / "test-stdout.txt"

    if reward_txt.exists() or stdout_txt.exists():
        lines.append("## Verifier evidence")
        lines.append("")
        if reward_txt.exists():
            try:
                raw_reward = clean_text(reward_txt.read_text(encoding="utf-8-sig")).strip()
            except OSError:
                raw_reward = ""
            if raw_reward:
                lines.append(f"- **`verifier/reward.txt`:** `{one_line(raw_reward, 300)}`")
        if stdout_txt.exists():
            try:
                stdout = stdout_txt.read_text(encoding="utf-8-sig")
            except OSError:
                stdout = ""
            if stdout.strip():
                lines.append("")
                lines.append("<details>")
                lines.append("<summary>Show verifier stdout preview</summary>")
                lines.append("")
                lines.append(fenced(preview_lines(stdout, max_lines=12, max_chars=2400), "text"))
                lines.append("")
                lines.append("</details>")
        lines.append("")

    lines.append("## Raw evidence")
    lines.append("")
    lines.append(f"- ACP trajectory: `{acp_path.name}`")
    for filename in ("executor_request.json", "result.json", "benchmark_result.json"):
        if (run_root / filename).exists():
            lines.append(f"- `{filename}`")
    lines.append("")
    lines.append(
        "_This Markdown is a readable index over the raw rollout evidence, not a semantic summary of the agent's reasoning._"
    )
    lines.append("")
    return "\n".join(lines)


def iter_acp_files(root: Path) -> Iterable[Path]:
    if root.is_file():
        if root.name == "acp_trajectory.jsonl" and root.parent.name == "trajectory":
            yield root
        return

    # Scan by filename, then require the canonical trajectory/ parent.
    for path in sorted(root.rglob("acp_trajectory.jsonl")):
        if path.is_file() and path.parent.name == "trajectory":
            yield path


def safe_filename_part(value: Any, fallback: str) -> str:
    """Convert metadata into a Windows/Linux-safe filename component."""
    if value is None:
        value = fallback
    text = str(value).strip()
    if not text:
        text = fallback
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", text)
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip(" .-_")
    return text[:120] or fallback


def timeline_filename(meta: RunMeta, run_root: Path) -> str:
    """
    Use task + method + run id to avoid collisions when many runs of one task
    are exported into the same before/after directory.
    """
    task = safe_filename_part(meta.task_id, "unknown-task")
    method = safe_filename_part(meta.method_id, "unknown-method")
    run_id = safe_filename_part(meta.run_id, run_root.name)
    return f"{task}__{method}__{run_id}.md"


def export_base(root: Path, export_dir_name: str) -> Path:
    """
    For a directory root:
        <root>/<export_dir_name>/
    For a single acp_trajectory.jsonl input:
        <trajectory-parent>/<export_dir_name>/
    """
    if root.is_dir():
        return root / export_dir_name
    return root.parent / export_dir_name


def output_path(export_root: Path, label: str, meta: RunMeta, run_root: Path) -> Path:
    bucket = label if label in {"before", "after"} else "unknown"
    return export_root / bucket / timeline_filename(meta, run_root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Batch-convert ACP trajectories into centralized deterministic Markdown timelines."
    )
    parser.add_argument(
        "--root",
        type=Path,
        required=True,
        help=(
            "Any directory to scan recursively, or one trajectory/acp_trajectory.jsonl file. "
            "No repository-specific directory name is assumed."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Discover trajectories and labels but do not write files.",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Do not overwrite an existing trajectory_before/after/unknown.md.",
    )
    parser.add_argument(
        "--index-name",
        default="trajectory_timeline_index.json",
        help="Index filename inside the centralized export directory.",
    )
    parser.add_argument(
        "--export-dir-name",
        default="trajectory_timelines",
        help=(
            "Directory created under --root for all generated Markdown "
            "(default: trajectory_timelines)."
        ),
    )
    args = parser.parse_args(argv)

    root = args.root.expanduser().resolve()
    if not root.exists():
        print(f"ERROR: root does not exist: {root}", file=sys.stderr)
        return 2

    central_output = export_base(root, args.export_dir_name)

    acp_files = list(iter_acp_files(root))
    if not acp_files:
        print(
            "No canonical **/trajectory/acp_trajectory.jsonl files found.",
            file=sys.stderr,
        )
        return 1

    entries: list[TimelineEntry] = []
    wrote = 0
    skipped = 0

    for acp_path in acp_files:
        run_root = acp_path.parent.parent
        meta = discover_meta(run_root)
        out_path = output_path(central_output, meta.label, meta, run_root)

        print(
            f"[{meta.label.upper():7}] "
            f"task={meta.task_id or '?'} "
            f"method={meta.method_id or '?'} "
            f"condition={meta.condition or '?'} "
            f"run={meta.run_id or run_root.name}"
        )
        print(f"          {acp_path} -> {out_path}")

        if not args.dry_run:
            if args.skip_existing and out_path.exists():
                skipped += 1
            else:
                events = load_events(acp_path)
                md = build_markdown(acp_path, run_root, meta, events)
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(md, encoding="utf-8")
                wrote += 1

        entries.append(
            TimelineEntry(
                source=str(acp_path),
                output=str(out_path),
                run_root=str(run_root),
                task_id=meta.task_id,
                method_id=meta.method_id,
                run_id=meta.run_id,
                condition=meta.condition,
                label=meta.label,
                task_passed=meta.task_passed,
                execution_ok=meta.execution_ok,
            )
        )

    if not args.dry_run:
        central_output.mkdir(parents=True, exist_ok=True)
        index_path = central_output / args.index_name

        # Pairing hint is implicit in task_id + method_id + label.
        index = {
            "schema_version": "1.0",
            "root": str(root),
            "export_root": str(central_output),
            "count": len(entries),
            "pairing_key": ["task_id", "method_id"],
            "layout": {
                "before": str(central_output / "before"),
                "after": str(central_output / "after"),
                "unknown": str(central_output / "unknown"),
            },
            "label_policy": {
                "before": sorted(BEFORE_CONDITIONS),
                "after": sorted(AFTER_CONDITIONS),
                "unknown": "condition missing or not recognized",
            },
            "trajectories": [asdict(entry) for entry in entries],
        }
        index_path.write_text(
            json.dumps(index, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"\nOutput root: {central_output}")
        print(f"Index: {index_path}")
        print(f"Converted: {wrote}; skipped existing: {skipped}; discovered: {len(entries)}")
    else:
        print(f"\nDry run: discovered {len(entries)} trajectory file(s).")

    unknown = sum(entry.label == "unknown" for entry in entries)
    if unknown:
        print(
            f"WARNING: {unknown} trajectory file(s) could not be labeled before/after. "
            "Check executor_request.json/result.json metadata.",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
