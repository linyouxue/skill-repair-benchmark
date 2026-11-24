from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path
from typing import Any, Iterable


ANSI = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))")


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def nested_values(value: Any, keys: set[str]) -> Iterable[str]:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in keys and isinstance(child, str):
                yield child
            yield from nested_values(child, keys)
    elif isinstance(value, list):
        for child in value:
            yield from nested_values(child, keys)


def metadata(run_dir: Path, task_id: str) -> tuple[str, str, str]:
    documents = [
        read_json(run_dir / "executor_request.json"),
        read_json(run_dir / "result.json"),
        read_json(run_dir / "benchmark_result.json"),
    ]
    conditions = []
    for document in documents:
        conditions.extend(
            value.lower()
            for value in nested_values(
                document, {"condition", "evaluation_condition"}
            )
        )
    # The packaged run-directory role is authoritative when present. Some
    # preserved legacy result.json files omit the condition or contain a stale
    # nested condition from the producer that assembled the evidence bundle.
    if run_dir.name == "original_run":
        condition, stage = "original-skill", "before"
    elif run_dir.name == "repaired_run":
        condition, stage = "method-skill", "after"
    elif "original-skill" in conditions:
        condition, stage = "original-skill", "before"
    elif "method-skill" in conditions:
        condition, stage = "method-skill", "after"
    else:
        condition, stage = "unknown", "unknown"

    run_id = ""
    for document in documents:
        for key in ("rollout_id", "rollout_name", "executor_run_id"):
            value = document.get(key)
            if isinstance(value, str) and value:
                run_id = value
                break
        if run_id:
            break
    return condition, stage, run_id or f"{task_id}-{run_dir.name}"


def plain(value: str) -> str:
    return ANSI.sub("", value).replace("\r\n", "\n").replace("\r", "\n")


def text_fragments(value: Any) -> list[str]:
    fragments: list[str] = []
    if isinstance(value, str):
        return [plain(value)]
    if isinstance(value, dict):
        for key in ("text", "output", "message"):
            child = value.get(key)
            if isinstance(child, str):
                fragments.append(plain(child))
        if not fragments:
            for child in value.values():
                fragments.extend(text_fragments(child))
    elif isinstance(value, list):
        for child in value:
            fragments.extend(text_fragments(child))
    return fragments


def render_event(index: int, event: dict[str, Any]) -> str:
    kind = str(event.get("type") or "unknown")
    lines = [f"## Event {index}: `{kind}`", ""]
    for key in ("timestamp", "title", "status", "kind", "tool_call_id"):
        value = event.get(key)
        if value not in (None, ""):
            lines.append(f"- {key}: `{plain(str(value))}`")
    if len(lines) > 2:
        lines.append("")

    emitted = False
    for key in ("text", "content"):
        if key not in event:
            continue
        fragments = [part for part in text_fragments(event[key]) if part.strip()]
        for fragment in fragments:
            lines.extend([f"### {key}", "", "```text", fragment, "```", ""])
            emitted = True
    if not emitted:
        lines.extend(
            ["```json", json.dumps(event, ensure_ascii=False, indent=2), "```", ""]
        )
    return "\n".join(lines)


def convert(source: Path, output: Path, header: dict[str, Any]) -> tuple[int, int]:
    rendered = [
        f"# {header['task_id']} — {header['stage']} trajectory",
        "",
        f"- Method: `{header['method']}`",
        f"- Run ID: `{header['run_id']}`",
        f"- Condition: `{header['condition']}`",
        f"- Source: `{header['source']}`",
        "",
    ]
    events = 0
    errors = 0
    with source.open(encoding="utf-8", errors="replace") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
                if not isinstance(event, dict):
                    raise ValueError("event is not an object")
                events += 1
                rendered.append(render_event(events, event))
            except (json.JSONDecodeError, ValueError) as exc:
                errors += 1
                rendered.extend(
                    [
                        f"## Parse error at JSONL line {line_number}",
                        "",
                        f"`{exc}`",
                        "",
                        "```text",
                        plain(line.rstrip("\n")),
                        "```",
                        "",
                    ]
                )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(rendered).rstrip() + "\n", encoding="utf-8")
    return events, errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    if not root.is_dir():
        raise SystemExit(f"Result root does not exist: {root}")
    method = root.name
    timeline_root = root / "trajectory_timelines"

    records = []
    # Controlled experiment package uses experiments/{repair,control}/<id>/run
    # and unhinted-reuse/<configuration>/<task>/{original_run,repaired_run}.
    sources = sorted(path for path in root.rglob("trajectory/acp_trajectory.jsonl")
                     if path.is_file() and "trajectory_timelines" not in path.parts)
    for source in sources:
        relative = source.relative_to(root)
        if relative.parts[0] == "rerun4":
            task_id = "rerun4__" + relative.parts[1]
        elif "experiments" in relative.parts:
            marker = relative.parts.index("experiments")
            task_id = relative.parts[marker+1] + "__" + relative.parts[marker+2]
        elif relative.parts[0] == "unhinted5":
            task_id = "unhinted__" + relative.parts[2] + "__" + relative.parts[3]
        else:
            task_id = "__".join(relative.parts[:-3])
        if "prior_selections" in relative.parts:
            task_id = "prior__" + task_id
        run_dir = source.parent.parent
        condition, stage, run_id = metadata(run_dir, task_id)
        if relative.parts[:3] == ("shared_controls33", "experiments", "control"):
            record = read_json(root / "shared_controls33" / "experiments" / "control" / relative.parts[3] / "RUN_RECORD.json")
            control_condition = record.get("condition", "unknown")
            # Full Gold and leave-one controls are not method repairs.
            condition = "control-" + control_condition
            stage = "before" if control_condition == "original" else "unknown"
        if "prior_selections" in relative.parts:
            stage = "unknown"
            condition = "archived-prior-selection-" + condition
        safe_run_id = re.sub(r"[^A-Za-z0-9._-]+", "-", run_id).strip("-")
        name = f"{task_id}__{method}__{safe_run_id}.md"
        output = timeline_root / stage / name
        record = {
            "task_id": task_id,
            "method": method,
            "run_id": run_id,
            "condition": condition,
            "stage": stage,
            "source": relative.as_posix(),
            "output": output.relative_to(root).as_posix(),
        }
        records.append(record)
        print(f"{stage:7} {relative} -> {output.relative_to(root)}")

    if args.dry_run:
        counts = {stage: sum(r["stage"] == stage for r in records) for stage in ("before", "after", "unknown")}
        print(json.dumps({"total": len(records), **counts}, ensure_ascii=False))
        return 0

    if timeline_root.exists():
        shutil.rmtree(timeline_root)
    for stage in ("before", "after", "unknown"):
        (timeline_root / stage).mkdir(parents=True, exist_ok=True)
    for record in records:
        output = root / record["output"]
        events, errors = convert(
            root / record["source"],
            output,
            record,
        )
        record["event_count"] = events
        record["parse_error_count"] = errors

    index = {
        "method": method,
        "trajectory_count": len(records),
        "before_count": sum(r["stage"] == "before" for r in records),
        "after_count": sum(r["stage"] == "after" for r in records),
        "unknown_count": sum(r["stage"] == "unknown" for r in records),
        "tasks": records,
    }
    (timeline_root / "trajectory_timeline_index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({key: index[key] for key in ("trajectory_count", "before_count", "after_count", "unknown_count")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
