#!/usr/bin/env python3
"""Run MMG2Skill's published trajectory analyzer on frozen SkillsBench traces.

This is a diagnosis-only adapter. It does not run MMG2Skill's skill extractor,
refiner, agent, or the SkillsBench verifier, and is not the full paper method.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
TASK_PATTERN = re.compile(r"(?m)^(\d+)\. `([a-z0-9-]+)`\s*$")
ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return f"sha256:{value.hexdigest()}"


def observation_digest(source: Path) -> str:
    value = hashlib.sha256()
    paths = sorted(source.glob("step_*/observation.txt"))
    for path in paths:
        value.update(path.relative_to(source).as_posix().encode("utf-8"))
        value.update(b"\0")
        value.update(path.read_bytes())
        value.update(b"\0")
    return f"sha256:{value.hexdigest()}"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def protocol_tasks(path: Path) -> list[str]:
    rows = TASK_PATTERN.findall(path.read_text(encoding="utf-8"))
    if len(rows) != 25 or [int(number) for number, _ in rows] != list(range(1, 26)):
        raise ValueError(f"Expected the frozen, numbered 25-task protocol: {path}")
    ids = [task_id for _, task_id in rows]
    if len(set(ids)) != 25:
        raise ValueError("Task IDs in protocol are not unique")
    return ids


def status_rows(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    result = {row["task_id"]: row for row in rows}
    if len(result) != len(rows):
        raise ValueError("Duplicate task_id in STATUS.csv")
    return result


def clean_text(value: str) -> str:
    return ANSI.sub("", value).replace("\x00", "")


def bounded(value: str, limit: int) -> tuple[str, bool]:
    value = clean_text(value)
    if len(value) <= limit:
        return value, False
    head = limit // 4
    return value[:head] + f"\n[... {len(value) - limit} characters omitted ...]\n" + value[-(limit - head):], True


def visible_tool_result(row: dict[str, Any]) -> str:
    parts: list[str] = []
    for item in row.get("content") or []:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        if isinstance(content, dict) and isinstance(content.get("text"), str):
            parts.append(content["text"])
    return "\n".join(parts)


def convert_trace(acp: Path, dest: Path, observation_limit: int) -> dict[str, Any]:
    """Map each visible ACP tool event to one approximate analyzer turn.

    ACP does not expose MMG2Skill's predict_num. Agent thoughts are omitted:
    they can contain an entire system prompt and are not needed to reconstruct
    the observable action/result sequence. No verifier files are read.
    """
    rows: list[dict[str, Any]] = []
    truncated_observations: list[int] = []
    truncated_actions: list[int] = []
    final_messages: list[str] = []
    outcome: dict[str, Any] | None = None
    with acp.open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                row = json.loads(line)
                if row.get("type") == "tool_call":
                    index = len(rows) + 1
                    observation, cut = bounded(visible_tool_result(row), observation_limit)
                    if cut:
                        truncated_observations.append(index)
                    action, action_cut = bounded(
                        str(row.get("title") or row.get("kind") or "tool call"),
                        observation_limit,
                    )
                    if action_cut:
                        truncated_actions.append(index)
                    step_dir = dest / f"step_{index}_obs"
                    step_dir.mkdir(parents=True)
                    (step_dir / "observation.txt").write_text(
                        observation or "(empty tool result)", encoding="utf-8"
                    )
                    rows.append({
                        "predict_num": index,
                        "step_num": index,
                        "action_timestamp": "obs",
                        "response": "",
                        "action": action,
                        "phase": "ACP tool call",
                    })
                elif row.get("type") == "agent_message" and isinstance(row.get("text"), str):
                    final_messages.append(row["text"])
                elif row.get("type") == "agent_iteration_outcome":
                    outcome = row
    if not rows:
        raise ValueError(f"No visible tool calls in {acp}")
    if final_messages:
        index = len(rows) + 1
        final_text, cut = bounded(final_messages[-1], observation_limit)
        if cut:
            truncated_actions.append(index)
        rows.append({
            "predict_num": index,
            "step_num": index,
            "action_timestamp": "obs",
            "response": final_text,
            "action": "Final answer",
            "phase": "ACP agent message",
        })
        step_dir = dest / f"step_{index}_obs"
        step_dir.mkdir(parents=True)
        (step_dir / "observation.txt").write_text(
            "(No observation after the final answer)", encoding="utf-8"
        )
    with (dest / "traj.jsonl").open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    return {
        "tool_calls": len(rows) - bool(final_messages),
        "final_answer_present": bool(final_messages),
        "approximate_turns": len(rows),
        "truncated_observation_turns": truncated_observations,
        "truncated_action_turns": truncated_actions,
        "agent_execution_status": outcome.get("execution_status") if outcome else None,
        "skill_context_preloaded": outcome.get("skill_context_preloaded") if outcome else None,
        "original_skill_bundle_sha256": outcome.get("skill_bundle_sha256") if outcome else None,
    }


def prepare(args: argparse.Namespace) -> None:
    archive = args.archive.resolve(strict=True)
    protocol = args.protocol.resolve(strict=True)
    output = args.output.resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Output must be new or empty: {output}")
    if output == archive or output in archive.parents or archive in output.parents:
        raise ValueError("Output must not overlap the source archive")
    ids = protocol_tasks(protocol)
    statuses = status_rows(archive / "STATUS.csv")
    if not set(ids) <= set(statuses):
        raise ValueError("Archive is missing tasks from the frozen protocol")
    output.mkdir(parents=True, exist_ok=True)
    prepared: list[dict[str, Any]] = []
    for task_id in ids:
        selected = archive / "tasks" / task_id / "selected_run"
        acp = selected / "trajectory" / "acp_trajectory.jsonl"
        prompts_path = selected / "prompts.json"
        prompts = read_json(prompts_path)
        if not isinstance(prompts, list) or not prompts or not all(isinstance(p, str) for p in prompts):
            raise ValueError(f"Invalid prompts.json for {task_id}")
        entry = statuses[task_id]
        if entry.get("pf") not in {"PASS", "FAIL"}:
            raise ValueError(f"Unknown archive status for {task_id}")
        dest = output / "prepared" / task_id
        dest.mkdir(parents=True)
        (dest / "instruction.txt").write_text("\n\n".join(prompts), encoding="utf-8")
        trace_meta = convert_trace(acp, dest, args.observation_chars)
        meta = {
            "task_id": task_id,
            "archived_result": entry["pf"],
            "condition": entry["condition"],
            "guard_used": entry["guard_used"] == "true",
            "rollout_id": entry["rollout_id"],
            "source_acp": str(acp),
            "source_acp_sha256": digest(acp),
            "source_prompts_sha256": digest(prompts_path),
            "prepared_trajectory_sha256": digest(dest / "traj.jsonl"),
            "prepared_instruction_sha256": digest(dest / "instruction.txt"),
            "prepared_observations_sha256": observation_digest(dest),
            **trace_meta,
        }
        write_json(dest / "metadata.json", meta)
        prepared.append(meta)
    manifest = {
        "method": "MMG2Skill ReviserAnalyzer / SkillsBench ACP adapter",
        "scope": "trajectory diagnosis only; no Skill-file attribution or repair",
        "upstream_commit": upstream_commit(),
        "adapter_sha256": digest(Path(__file__)),
        "protocol": str(protocol),
        "protocol_sha256": digest(protocol),
        "archive": str(archive),
        "archive_manifest_sha256": digest(archive / "MANIFEST.json") if (archive / "MANIFEST.json").is_file() else None,
        "comparison_status": "exploratory archive diagnosis; not the frozen shared-trajectory main table",
        "task_ids": ids,
        "tasks": prepared,
    }
    write_json(output / "manifest.json", manifest)
    print(f"Prepared {len(ids)} tasks in {output}")
    from collections import Counter
    print("Conditions:", dict(Counter((m["archived_result"], m["condition"], m["guard_used"]) for m in prepared)))


def verify(args: argparse.Namespace) -> None:
    output = args.output.resolve(strict=True)
    manifest = read_json(output / "manifest.json")
    ids = manifest.get("task_ids")
    if not isinstance(ids, list) or len(ids) != 25 or len(set(ids)) != 25:
        raise ValueError("Expected exactly 25 unique prepared task IDs")
    if manifest.get("upstream_commit") != upstream_commit() or manifest.get("adapter_sha256") != digest(Path(__file__)):
        raise ValueError("Upstream or adapter code differs from the prepared manifest")
    for task_id in ids:
        source = output / "prepared" / task_id
        meta = read_json(source / "metadata.json")
        if meta.get("task_id") != task_id:
            raise ValueError(f"Task metadata mismatch: {task_id}")
        for filename, field in (
            ("traj.jsonl", "prepared_trajectory_sha256"),
            ("instruction.txt", "prepared_instruction_sha256"),
        ):
            if digest(source / filename) != meta[field]:
                raise ValueError(f"Prepared input changed: {task_id}/{filename}")
        if observation_digest(source) != meta["prepared_observations_sha256"]:
            raise ValueError(f"Prepared observations changed: {task_id}")
        if len(list(source.glob("step_*/observation.txt"))) != meta["approximate_turns"]:
            raise ValueError(f"Prepared observation count mismatch: {task_id}")
    print(f"Verified {len(ids)} prepared tasks; code and input hashes match")


def upstream_commit() -> str:
    import subprocess

    marker = REPO / "UPSTREAM_COMMIT"
    if marker.is_file():
        value = marker.read_text(encoding="utf-8").strip()
        if re.fullmatch(r"[0-9a-f]{40}", value):
            return value
        raise ValueError(f"Invalid upstream commit marker: {marker}")
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()


class TextObservationKit:
    reviser_guidance = (
        "The domain is a software task. Judge only the visible user instruction, "
        "tool actions, tool results, and final answer. A tool event here is an "
        "approximation of one agent predict-turn; the original ACP trace does "
        "not provide MMG2Skill predict_num. Do not infer a Skill-file defect "
        "from agent failure alone."
    )

    @staticmethod
    def load_saved_observation(step_dir: Path) -> list[dict[str, str]]:
        path = step_dir / "observation.txt"
        if not path.is_file():
            return []
        return [{"type": "text", "text": path.read_text(encoding="utf-8")}]


class MeteredClient:
    def __init__(self, model: str, base_url: str, api_key: str, token_key: str):
        from openai import OpenAI

        self.model = model
        self.token_key = token_key
        self.client = OpenAI(base_url=base_url, api_key=api_key, timeout=600.0)
        self.calls: list[dict[str, Any]] = []

    def chat(self, messages: list[dict[str, Any]], max_tokens: int, temperature: float | None) -> str:
        import time

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            self.token_key: max_tokens,
        }
        if temperature is not None:
            kwargs["temperature"] = temperature
        started = time.monotonic()
        reply = self.client.chat.completions.create(**kwargs)
        content = reply.choices[0].message.content
        if not content:
            raise ValueError("Empty model response")
        usage = reply.usage.model_dump(exclude_none=True) if reply.usage else None
        self.calls.append({
            "request_model": self.model,
            "response_model": str(reply.model or ""),
            "response_id": reply.id,
            "wall_seconds": round(time.monotonic() - started, 3),
            "usage": usage,
        })
        return content


def run(args: argparse.Namespace) -> None:
    sys.path.insert(0, str(REPO))
    from anything2skill.reviser.analyzer import ReviserAnalyzer

    output = args.output.resolve(strict=True)
    manifest = read_json(output / "manifest.json")
    if manifest.get("upstream_commit") != upstream_commit() or manifest.get("adapter_sha256") != digest(Path(__file__)):
        raise ValueError("Code changed after prepare; use a new output directory")
    ids = manifest["task_ids"]
    selected = args.task or ids
    if not set(selected) <= set(ids):
        raise ValueError("Selected task is outside the frozen 25")
    key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not key:
        raise ValueError("Set OPENROUTER_API_KEY or OPENAI_API_KEY in the environment")
    client = MeteredClient(args.model, args.base_url, key, args.token_key)
    for task_id in selected:
        source = output / "prepared" / task_id
        source_meta = read_json(source / "metadata.json")
        if digest(source / "traj.jsonl") != source_meta["prepared_trajectory_sha256"]:
            raise ValueError(f"Prepared trajectory changed after preflight: {task_id}")
        if digest(source / "instruction.txt") != source_meta["prepared_instruction_sha256"]:
            raise ValueError(f"Prepared instruction changed after preflight: {task_id}")
        if observation_digest(source) != source_meta["prepared_observations_sha256"]:
            raise ValueError(f"Prepared observations changed after preflight: {task_id}")
        if len(list(source.glob("step_*/observation.txt"))) != source_meta["approximate_turns"]:
            raise ValueError(f"Prepared observation count mismatch: {task_id}")
        dest = output / "diagnoses" / task_id
        if dest.exists():
            if args.resume and (dest / "analysis.json").is_file():
                previous = read_json(dest / "analysis.json")
                if (previous.get("model_requested") == args.model
                        and previous.get("source_acp_sha256") == source_meta["source_acp_sha256"]
                        and previous.get("base_url") == args.base_url
                        and previous.get("token_parameter") == args.token_key
                        and previous.get("chunk_size") == args.chunk_size
                        and previous.get("max_tokens") == args.max_tokens
                        and previous.get("upstream_commit") == upstream_commit()
                        and previous.get("adapter_sha256") == digest(Path(__file__))):
                    print(f"{task_id}: already complete, skipped", flush=True)
                    continue
            raise FileExistsError(f"Refusing to overwrite diagnosis: {dest}")
        dest.mkdir(parents=True)
        start_index = len(client.calls)
        analyzer = ReviserAnalyzer(
            client, TextObservationKit(), chunk_size=args.chunk_size,
            max_tokens=args.max_tokens, temperature=None,
            response_char_limit=4000, rolling_summary_char_limit=1500,
        )
        instruction = (source / "instruction.txt").read_text(encoding="utf-8")
        result = analyzer.analyze(
            str(source / "traj.jsonl"), instruction, str(source), audit_dir=str(dest)
        )
        calls = client.calls[start_index:]
        write_json(dest / "api_calls.json", calls)
        if not result.raw_xml or result.outcome_assessment not in {
            "likely_success", "uncertain", "likely_failure"
        }:
            write_json(dest / "error.json", {
                "error": "Analyzer did not return a valid root_cause with outcome_assessment",
                "raw_response": result.raw_response,
            })
            raise RuntimeError(f"Invalid analyzer result for {task_id}; see {dest}")
        (dest / "root_cause.xml").write_text(result.raw_xml + "\n", encoding="utf-8")
        write_json(dest / "analysis.json", {
            "task_id": task_id,
            "method": "official MMG2Skill ReviserAnalyzer with SkillsBench ACP adapter",
            "trajectory_summary": result.trajectory_summary,
            "what_worked": result.what_worked,
            "issues": result.issues,
            "outcome_assessment": result.outcome_assessment,
            "outcome_rationale": result.outcome_rationale,
            "model_requested": args.model,
            "model_returned": sorted({c["response_model"] for c in calls}),
            "api_call_count": len(calls),
            "base_url": args.base_url,
            "token_parameter": args.token_key,
            "chunk_size": args.chunk_size,
            "max_tokens": args.max_tokens,
            "upstream_commit": upstream_commit(),
            "adapter_sha256": digest(Path(__file__)),
            "source_acp_sha256": source_meta["source_acp_sha256"],
        })
        print(f"{task_id}: {result.outcome_assessment}, {len(result.issues)} issues, {len(calls)} calls", flush=True)


def summarize(args: argparse.Namespace) -> None:
    output = args.output.resolve(strict=True)
    manifest = read_json(output / "manifest.json")
    records: list[dict[str, Any]] = []
    for task_meta in manifest["tasks"]:
        task_id = task_meta["task_id"]
        directory = output / "diagnoses" / task_id
        analysis_path = directory / "analysis.json"
        calls_path = directory / "api_calls.json"
        result = read_json(analysis_path) if analysis_path.is_file() else {}
        calls = read_json(calls_path) if calls_path.is_file() else []
        usage = [call.get("usage") or {} for call in calls]
        status = "complete" if result else "error" if (directory / "error.json").exists() else "missing"
        clean_subset = task_meta["condition"] == "original-skill" and not task_meta["guard_used"]
        prediction = result.get("outcome_assessment", "")
        predicted_pass = {"likely_success": "PASS", "likely_failure": "FAIL"}.get(prediction, "")
        records.append({
            "task_id": task_id,
            "status": status,
            "archived_result": task_meta["archived_result"],
            "condition": task_meta["condition"],
            "guard_used": task_meta["guard_used"],
            "clean_original_subset": clean_subset,
            "outcome_assessment": prediction,
            "binary_prediction": predicted_pass,
            "binary_correct": predicted_pass == task_meta["archived_result"] if predicted_pass else "",
            "issue_count": len(result.get("issues", [])),
            "api_calls": len(calls),
            "prompt_tokens": sum(int(item.get("prompt_tokens") or 0) for item in usage),
            "completion_tokens": sum(int(item.get("completion_tokens") or 0) for item in usage),
            "model_returned": ",".join(result.get("model_returned", [])),
            "source_acp_sha256": task_meta["source_acp_sha256"],
        })
    path = output / "diagnosis_summary.csv"
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    clean = [row for row in records if row["clean_original_subset"]]
    evaluated = [row for row in clean if row["binary_prediction"]]
    totals = {
        "tasks": len(records),
        "complete": sum(row["status"] == "complete" for row in records),
        "clean_original_subset": len(clean),
        "clean_subset_binary_evaluated": len(evaluated),
        "clean_subset_binary_correct": sum(row["binary_correct"] is True for row in evaluated),
        "clean_subset_uncertain": sum(row["outcome_assessment"] == "uncertain" for row in clean),
        "note": "Outcome assessment only. This is not Skill-file localization accuracy or repair success.",
    }
    write_json(output / "diagnosis_summary.json", totals)
    print(json.dumps(totals, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare", help="Validate and convert the 25 archived ACP traces; no API calls")
    prep.add_argument("--protocol", type=Path, required=True)
    prep.add_argument("--archive", type=Path, required=True)
    prep.add_argument("--output", type=Path, required=True)
    prep.add_argument("--observation-chars", type=int, default=2400)
    check = sub.add_parser("verify", help="Verify packaged code and all prepared inputs; no API calls")
    check.add_argument("--output", type=Path, required=True)
    execute = sub.add_parser("run", help="Run the official MMG2Skill analyzer on prepared traces")
    execute.add_argument("--output", type=Path, required=True)
    execute.add_argument("--task", action="append", help="Repeat for selected tasks; default: all 25")
    execute.add_argument("--model", default="openai/gpt-5.2")
    execute.add_argument("--base-url", default="https://openrouter.ai/api/v1")
    execute.add_argument("--token-key", choices=("max_tokens", "max_completion_tokens"), default="max_tokens")
    execute.add_argument("--chunk-size", type=int, default=15)
    execute.add_argument("--max-tokens", type=int, default=2048)
    execute.add_argument("--resume", action="store_true", help="Skip completed tasks with matching model and source digest")
    report = sub.add_parser("summarize", help="Summarize diagnosis outputs; no API calls")
    report.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        if args.observation_chars < 300:
            parser.error("--observation-chars must be at least 300")
        prepare(args)
    elif args.command == "verify":
        verify(args)
    elif args.command == "run":
        if args.chunk_size < 1 or args.max_tokens < 1:
            parser.error("--chunk-size and --max-tokens must be positive")
        run(args)
    else:
        summarize(args)


if __name__ == "__main__":
    main()
