"""Read BenchFlow/SkillsBench rollout artifacts without importing BenchFlow."""

from __future__ import annotations

import json
import re
import base64
import zlib
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from skillsbench_replay.schema import CommandEvent, ParsedRun
from skillsbench_replay.shell_io import extract_command, infer_shell_access


RESOURCE_EVENT_RE = re.compile(r"(?m)^CAUSALFLOW_RESOURCE_EVENT=(\{.*\})\s*$")
COMMAND_JSON_RE = re.compile(r"(?m)^CAUSALFLOW_COMMAND_JSON=(\".*\")\s*$")
COMMAND_ZLIB_RE = re.compile(r"(?m)^CAUSALFLOW_COMMAND_ZLIB_B64=([A-Za-z0-9+/=]+)\s*$")


def materialize_replay_command(event: CommandEvent) -> str | None:
    """Return the shell action that actually reached the historical runtime.

    Some terminal frontends rejected multi-command payloads before spawning a
    shell while still recording the requested command in the trajectory.  A
    replay must preserve the event but not execute a command that never ran.
    """
    if not event.command:
        return event.command
    output = event.output or ""
    if (
        "Cannot execute multiple commands at once" in output
        and "An error occurred during execution" in output
    ):
        return ":"
    return event.command


def parse_atif(
    record: Dict[str, Any],
    *,
    llm_tool_calls: Mapping[str, tuple[str, Dict[str, Any]]] | None = None,
) -> ParsedRun:
    agent = record.get("agent") if isinstance(record.get("agent"), dict) else {}
    events: list[CommandEvent] = []
    warnings: list[str] = []
    next_event_id = 1

    for step in record.get("steps") or []:
        if not isinstance(step, dict) or step.get("source") != "agent":
            continue
        observations = _observation_map(step.get("observation"))
        tool_calls = step.get("tool_calls")
        if not isinstance(tool_calls, list):
            continue
        for call in tool_calls:
            if not isinstance(call, dict):
                continue
            call_id = str(call.get("tool_call_id") or f"call_{next_event_id}")
            extra = call.get("extra") if isinstance(call.get("extra"), dict) else {}
            title = str(extra.get("title") or "")
            function_name = str(call.get("function_name") or "tool")
            exact_tool = (llm_tool_calls or {}).get(call_id)
            exact_name = exact_tool[0] if exact_tool else ""
            exact_arguments = exact_tool[1] if exact_tool else {}
            file_editor_access: tuple[
                tuple[str, ...], tuple[str, ...], tuple[str, ...]
            ] | None = None
            if exact_name == "terminal":
                command, argument_source = extract_command(exact_arguments, title)
                if command is not None:
                    argument_source = "llm_trajectory.arguments.command"
            elif exact_name == "file_editor":
                command, file_editor_access = _file_editor_command(exact_arguments)
                argument_source = (
                    f"llm_trajectory.file_editor.{exact_arguments.get('command')}"
                    if command is not None
                    else "unsupported_file_editor"
                )
                if command is not None:
                    function_name = "execute"
            else:
                command, argument_source = extract_command(call.get("arguments"), title)
            output = observations.get(call_id, "")
            marker_command = _command_from_marker(output)
            if marker_command is not None:
                command = marker_command
                argument_source = "result_marker"
            elif argument_source == "title_fallback" and (
                title.endswith("...[truncated]") or len(title) >= 3990
            ):
                # ACP titles are display fields.  BenchFlow 0.6.3 used to
                # retain only roughly 4k characters, which made a truncated
                # heredoc look executable and could accidentally consume the
                # following replay commands.  Refuse that evidence unless a
                # lossless result marker is present.
                command = None
                argument_source = "truncated_title"
            # Infer accesses only after preferring the lossless marker.  Doing
            # this before replacement would build the graph from the truncated
            # title even when the full command had been recovered.
            access = infer_shell_access(command) if command else None
            resource_event = _resource_event(output)
            observed_reads = tuple(
                str(path) for path in resource_event.get("observed_reads", [])
            )
            observed_writes = tuple(
                str(path) for path in resource_event.get("observed_writes", [])
            )
            raw_write_hashes = resource_event.get("observed_write_hashes")
            observed_write_hashes = (
                {
                    str(path): str(digest)
                    for path, digest in raw_write_hashes.items()
                    if isinstance(path, str) and isinstance(digest, str)
                }
                if isinstance(raw_write_hashes, dict)
                else {}
            )
            observed_deletes = tuple(
                str(path) for path in resource_event.get("observed_deletes", [])
            )
            event_warnings = list(access.warnings if access else ())
            if exact_name == "file_editor" and command is not None:
                event_warnings.append(
                    "file_editor mutation converted to an equivalent replay command"
                )
            if exact_name == "file_editor" and command is None:
                event_warnings.append(
                    "unsupported file_editor operation; replay disabled"
                )
            if argument_source == "title_fallback":
                event_warnings.append(
                    "BenchFlow ATIF omitted structured arguments; command recovered from extra.title"
                )
            if argument_source == "truncated_title":
                event_warnings.append(
                    "ACP title is truncated and no lossless command marker exists; replay disabled"
                )
            if command is None:
                event_warnings.append("no executable command found; replay disabled")
            event = CommandEvent(
                step_id=next_event_id,
                atif_step_id=int(step.get("step_id") or 0),
                tool_call_id=call_id,
                kind=function_name,
                title=title,
                command=command,
                argument_source=argument_source,
                status=str(extra.get("status") or "unknown"),
                output=output,
                inferred_reads=(
                    file_editor_access[0]
                    if file_editor_access is not None
                    else (access.reads if access else ())
                ),
                inferred_writes=(
                    file_editor_access[1]
                    if file_editor_access is not None
                    else (access.writes if access else ())
                ),
                inferred_deletes=tuple(
                    dict.fromkeys(
                        (
                            *(
                                file_editor_access[2]
                                if file_editor_access is not None
                                else (access.deletes if access else ())
                            ),
                            *observed_deletes,
                        )
                    )
                ),
                observed_reads=observed_reads,
                observed_writes=observed_writes,
                observed_write_hashes=observed_write_hashes,
                replayable=command is not None,
                warnings=tuple(dict.fromkeys(event_warnings)),
            )
            events.append(event)
            if exact_name == "terminal":
                event.terminal_arguments = dict(exact_arguments)
                recorded_timeout = exact_arguments.get("timeout")
                if (isinstance(recorded_timeout, (int, float))
                        and not isinstance(recorded_timeout, bool)
                        and recorded_timeout > 0):
                    event.replay_timeout = recorded_timeout
            next_event_id += 1

    # An empty terminal call polls the preceding live process. Keep its raw
    # evidence, but replay the original command synchronously to completion.
    # Refuse orphan/unfinished polls rather than inventing a shell command.
    for index, event in enumerate(events):
        if event.terminal_arguments.get("command") != "" or index == 0:
            continue
        previous = events[index - 1]
        initial_timeout = previous.terminal_arguments.get("timeout")
        wait_timeout = event.terminal_arguments.get("timeout")
        if (previous.command and "Process still running (soft timeout)" in previous.output
                and re.search(r"Exit code\s*[:=]\s*-?\d+", event.output)
                and isinstance(initial_timeout, (int, float)) and initial_timeout > 0
                and isinstance(wait_timeout, (int, float)) and wait_timeout > 0):
            event.kind = "terminal_wait"
            event.command = None
            event.argument_source = "llm_trajectory.arguments.terminal_wait"
            event.wait_for_step_id = previous.step_id
            event.replayable = True
            event.warnings = ("wait folded into preceding command completion",)
            previous.replay_timeout = initial_timeout + wait_timeout
            previous.completion_output = event.output

    if not events:
        warnings.append("trajectory contains no command-level tool calls")
    if any(event.argument_source == "title_fallback" for event in events):
        warnings.append(
            "command arguments use title_fallback because BenchFlow 0.6.3 ATIF exports ACP arguments as empty objects"
        )
    if any(not event.replayable for event in events):
        warnings.append(
            "one or more tool calls cannot be replayed from this trajectory"
        )
    if any(
        event.argument_source.startswith("llm_trajectory.file_editor.")
        for event in events
    ):
        warnings.append(
            "file_editor mutations were converted from exact LLM tool arguments"
        )

    return ParsedRun(
        session_id=str(record.get("session_id") or ""),
        agent_name=str(agent.get("name") or "unknown"),
        model_name=str(agent["model_name"]) if agent.get("model_name") else None,
        events=events,
        warnings=warnings,
    )


def load_run(run_dir: str | Path) -> ParsedRun:
    root = Path(run_dir)
    atif_path = _first_existing(
        root / "trainer" / "atif.json",
        root / "atif.json",
    )
    if atif_path is None:
        raise FileNotFoundError(f"No ATIF artifact found below {root}")
    record = json.loads(atif_path.read_text())
    llm_path = root / "trajectory" / "llm_trajectory.jsonl"
    llm_tool_calls = _load_llm_tool_calls(llm_path) if llm_path.exists() else None
    parsed = parse_atif(record, llm_tool_calls=llm_tool_calls)
    parsed.source_paths["atif"] = str(atif_path)
    if llm_tool_calls is not None:
        parsed.source_paths["llm_trajectory"] = str(llm_path)
    provenance = root / 'input-provenance.json'
    if provenance.is_file():
        parsed.source_paths['input_provenance'] = str(provenance)
        parsed.warnings.append('User-authorized reconstructed input; missing redacted code inferred from context, not losslessly recovered.')

    result_path = root / "result.json"
    if result_path.exists():
        result = json.loads(result_path.read_text())
        parsed.reward = _reward(result.get("rewards"))
        parsed.verifier_passed = (
            parsed.reward == 1.0 if parsed.reward is not None else None
        )
        parsed.source_paths["result"] = str(result_path)
    reward_path = root / "verifier" / "reward.txt"
    if reward_path.exists():
        try:
            reward = float(reward_path.read_text().strip())
        except ValueError:
            parsed.warnings.append(f"invalid verifier reward: {reward_path}")
        else:
            parsed.reward = reward
            parsed.verifier_passed = reward == 1.0
            parsed.source_paths["verifier_reward"] = str(reward_path)
    return parsed


def _load_llm_tool_calls(
    path: Path,
) -> Dict[str, tuple[str, Dict[str, Any]]]:
    calls: Dict[str, tuple[str, Dict[str, Any]]] = {}
    for line_number, raw_line in enumerate(path.read_text().splitlines(), start=1):
        if not raw_line.strip():
            continue
        try:
            exchange = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"invalid LLM trajectory JSON at {path}:{line_number}"
            ) from exc
        output = (
            exchange.get("response", {}).get("body", {}).get("output", [])
            if isinstance(exchange, dict)
            else []
        )
        # Historical Claude rollouts used Chat Completions. Preserve recorded
        # IDs/arguments exactly, translating only the API envelope.
        output = list(output) if isinstance(output, list) else []
        body = exchange.get("response", {}).get("body", {}) if isinstance(exchange, dict) else {}
        for choice in body.get("choices", []):
            for call in choice.get("message", {}).get("tool_calls", []) or []:
                function = call.get("function") or {}
                output.append({"type": "function_call", "call_id": call.get("id"),
                               "name": function.get("name"), "arguments": function.get("arguments")})
        for item in output if isinstance(output, list) else []:
            if not isinstance(item, dict) or item.get("type") != "function_call":
                continue
            call_id = item.get("call_id")
            name = item.get("name")
            raw_arguments = item.get("arguments")
            if not isinstance(call_id, str) or not isinstance(name, str):
                continue
            try:
                arguments = (
                    json.loads(raw_arguments)
                    if isinstance(raw_arguments, str)
                    else raw_arguments
                )
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"invalid tool arguments for {call_id} at {path}:{line_number}"
                ) from exc
            if not isinstance(arguments, dict):
                continue
            current = (name, arguments)
            previous = calls.get(call_id)
            if previous is not None and previous != current:
                raise ValueError(f"conflicting LLM tool arguments for {call_id}")
            calls[call_id] = current
    return calls


def _file_editor_command(
    arguments: Mapping[str, Any],
) -> tuple[
    Optional[str],
    tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]] | None,
]:
    operation = arguments.get("command")
    path = arguments.get("path")
    if not isinstance(operation, str) or not isinstance(path, str) or not path:
        return None, None
    path_literal = json.dumps(path, ensure_ascii=False)
    if operation == "create" and isinstance(arguments.get("file_text"), str):
        text_literal = json.dumps(arguments["file_text"], ensure_ascii=False)
        command = (
            "python3 - <<'PY'\n"
            "from pathlib import Path\n"
            f"path = Path({path_literal})\n"
            "if path.exists():\n"
            "    raise SystemExit(f'file already exists: {path}')\n"
            "path.parent.mkdir(parents=True, exist_ok=True)\n"
            f"path.write_text({text_literal}, encoding='utf-8')\n"
            "PY"
        )
        return command, ((), (path,), ())
    if (
        operation == "str_replace"
        and isinstance(arguments.get("old_str"), str)
        and isinstance(arguments.get("new_str"), str)
    ):
        old_literal = json.dumps(arguments["old_str"], ensure_ascii=False)
        new_literal = json.dumps(arguments["new_str"], ensure_ascii=False)
        command = (
            "python3 - <<'PY'\n"
            "from pathlib import Path\n"
            f"path = Path({path_literal})\n"
            "text = path.read_text(encoding='utf-8')\n"
            f"old = {old_literal}\n"
            "if text.count(old) != 1:\n"
            "    raise SystemExit(f'expected exactly one replacement target, got {text.count(old)}')\n"
            f"path.write_text(text.replace(old, {new_literal}, 1), encoding='utf-8')\n"
            "PY"
        )
        return command, ((path,), (path,), ())
    return None, None


def _observation_map(observation: object) -> Dict[str, str]:
    if not isinstance(observation, dict):
        return {}
    mapped: Dict[str, str] = {}
    for result in observation.get("results") or []:
        if not isinstance(result, dict):
            continue
        call_id = result.get("source_call_id")
        if call_id is not None:
            mapped[str(call_id)] = str(result.get("content") or "")
    return mapped


def _reward(value: object) -> Optional[float]:
    if isinstance(value, dict):
        value = value.get("reward")
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _resource_event(output: str) -> Dict[str, Any]:
    matches = RESOURCE_EVENT_RE.findall(output)
    if not matches:
        return {}
    try:
        payload = json.loads(matches[-1])
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _command_from_marker(output: str) -> Optional[str]:
    compressed = COMMAND_ZLIB_RE.findall(output)
    if compressed:
        try:
            value = zlib.decompress(base64.b64decode(compressed[-1])).decode(
                "utf-8"
            )
        except (ValueError, zlib.error, UnicodeDecodeError):
            pass
        else:
            if value.strip():
                return value
    matches = COMMAND_JSON_RE.findall(output)
    if not matches:
        return None
    try:
        value = json.loads(matches[-1])
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, str) and value.strip() else None


def _first_existing(*paths: Path) -> Optional[Path]:
    return next((path for path in paths if path.exists()), None)
