"""Prepare the pinned GPT-5.2 failure offline; never execute historical code."""
import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

PACKAGE = Path(__file__).resolve().parents[1]
SOURCE_COMMIT = "bee9b0df5b04a300735e5009f5238f5d5c8aaf61"
ARCHIVE = "evaluation/results/GPT52-AllTasks-RepresentativeRuns-20260916/tasks"
RUNS = {"pddl-airport-planning": "pddl-airport-planning-original-skill-v11x-20260908-guarddiag-infra-r003",
        "flink-query": "flink-query-original-skill-v11x-20260903-r002"}
ID_KEYS = ("event_id", "message_id", "context_id", "exchange_id", "tool_record_id")


def serial(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def record_id(record):
    return next(record[k] for k in ID_KEYS if record.get(k))


def helpers(package):
    path = package.parent / "jpg-ocr-skill-repair-dataset/tools/prepare_diagnosis.py"
    spec = importlib.util.spec_from_file_location("existing_lossless_helpers", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def normalize(value):
    if isinstance(value, dict):
        if value.get("type") in {"image_url", "input_image", "image"}:
            raise ValueError("Historical image requires explicit asset extraction; do not drop it")
        return {k: normalize(v) for k, v in value.items() if k != "cache_control"}
    if isinstance(value, list):
        return [normalize(v) for v in value]
    return value


class Source:
    def __init__(self, package, root, commit):
        self.root, self.commit = Path(root).resolve(), commit
        self.path_prefix = f"{ARCHIVE}/{package.name}/selected_run"
        self.run_id = RUNS[package.name]
        selection = read(self.root.parent / "run_selection.json")
        if (selection["rollout_id"] != self.run_id or selection["model"] != "openrouter/openai/gpt-5.2"
                or selection["condition"] != "original-skill" or not selection["execution_ok"]
                or selection["task_passed"] is not False or selection["reward"] != 0):
            raise ValueError("Source is not the specified healthy GPT-5.2 Original-Skill failure")
        self.fingerprints = {}
        for name in ["trajectory/acp_trajectory.jsonl", "trajectory/llm_trajectory.jsonl", "trainer/atif.json",
                     "results.jsonl", "result.json", "benchmark_result.json", "executor_request.json"]:
            path = self.root / name
            relative = self.path_prefix + "/" + name
            expected = subprocess.check_output(["git", "rev-parse", f"{commit}:{relative}"], cwd=package.parent, text=True).strip()
            actual = subprocess.check_output(["git", "hash-object", "--path", relative, "--stdin"],
                                             cwd=package.parent, input=path.read_bytes()).decode().strip()
            if actual != expected:
                raise ValueError("Source differs from pinned Git blob: " + name)
            self.fingerprints[name] = expected

    def source(self, name, line=None, pointer=""):
        result = {"repository_path": self.path_prefix + "/" + name, "file": name,
                  "commit": self.commit, "pointer": pointer}
        if line is not None:
            result["line"] = line
        return result

    def json(self, name):
        return read(self.root / name)

    def lines(self, name):
        for line, value in enumerate(rows(self.root / name), 1):
            yield line, value


def prepare_records(source, helper):
    run = source.run_id
    messages, contexts, exchanges = [], [], []
    message_ids, context_ids = {}, {}
    by_call = defaultdict(set)
    calls = Counter()

    def remember(value, line, pointer):
        value = normalize(value)
        key = serial(value)
        if key not in message_ids:
            mid = f"{run}:m{len(messages) + 1:04d}"
            message_ids[key] = mid
            messages.append({"message_id": mid, "source": source.source("trajectory/llm_trajectory.jsonl", line, pointer), "message": value})
        mid = message_ids[key]
        for cid in helper.tool_ids(value):
            by_call[cid].add(mid)
        return mid

    for line, row in source.lines("trajectory/llm_trajectory.jsonl"):
        request, response = row.get("request") or {}, row.get("response") or {}
        body, rb = request.get("body") or {}, response.get("body") or {}
        if response.get("status_code") != 200 or not isinstance(rb, dict) or not rb.get("usage"):
            raise ValueError("Missing successful provider exchange or usage evidence")
        params = {"request": normalize(helper.request_parameters(body)),
                  "response": normalize(helper.request_parameters(rb))}
        key = serial(params)
        if key not in context_ids:
            cid = f"{run}:c{len(contexts) + 1:04d}"
            context_ids[key] = cid
            contexts.append({"context_id": cid, "source": source.source("trajectory/llm_trajectory.jsonl", line),
                             "parameters": params, "source_pointers": ["/request/body", "/response/body"],
                             "policy": "existing_safe_parameter_allowlist; no_transport_headers; preserve_tool_schemas; remove_cache_control"})
        exchange = {"exchange_id": f"{run}:e{line:04d}", "run_id": run, "exchange_line": line,
                    "source": source.source("trajectory/llm_trajectory.jsonl", line), "api_context_id": context_ids[key],
                    "request_timestamp": request.get("timestamp"), "response_timestamp": response.get("timestamp"),
                    "duration_ms": row.get("duration_ms"), "status_code": response.get("status_code"),
                    "usage": helper.safe_usage(rb["usage"]), "request_message_ids": [], "request_input_ids": [],
                    "response_message_ids": [], "choice_metadata": [],
                    "response_metadata": {k: helper.safe_api_value(rb[k]) for k in
                        [*helper.RESPONSE_METADATA_KEYS, "created_at", "completed_at", "status", "error", "incomplete_details", "previous_response_id"] if k in rb}}
        for field, target in [("messages", "request_message_ids"), ("input", "request_input_ids")]:
            values = body.get(field) or []
            if isinstance(values, str):
                values = [{"role": "user", "content": values}]
            for i, value in enumerate(values):
                exchange[target].append(remember(value, line, f"/request/body/{field}/{i}"))
        for i, value in enumerate(rb.get("output") or []):
            exchange["response_message_ids"].append(remember(value, line, f"/response/body/output/{i}"))
            if value.get("type") == "function_call":
                calls[value.get("name")] += 1
        for i, choice in enumerate(rb.get("choices") or []):
            value = choice.get("message") or choice.get("delta")
            if value:
                mid = remember(value, line, f"/response/body/choices/{i}/message")
                exchange["response_message_ids"].append(mid)
                exchange["choice_metadata"].append({"response_message_id": mid, "finish_reason": choice.get("finish_reason")})
                calls.update((c.get("function") or {}).get("name") for c in value.get("tool_calls") or [])
        if not exchange["response_message_ids"]:
            raise ValueError("A full provider response is not represented")
        exchanges.append(exchange)
    steps, by_atif_call = [], defaultdict(list)
    for i, step in enumerate(source.json("trainer/atif.json").get("steps") or []):
        sid = f"{run}:s{i + 1:04d}"
        mids = set()
        for call in step.get("tool_calls") or []:
            cid = call.get("tool_call_id")
            by_atif_call[cid].append(sid)
            mids.update(by_call.get(cid, []))
        steps.append({"tool_record_id": sid, "source": source.source("trainer/atif.json", pointer=f"/steps/{i}"),
                      "record_kind": "source_atif_step_not_additional_action", "step": normalize(step),
                      "exact_llm_message_ids": sorted(mids)})
    timeline, prompts = [], []
    for line, event in source.lines("trajectory/acp_trajectory.jsonl"):
        cid = event.get("tool_call_id")
        timeline.append({"event_id": f"{run}:a{line:04d}", "run_id": run,
                         "source": source.source("trajectory/acp_trajectory.jsonl", line), "event": normalize(event),
                         "exact_llm_message_ids": sorted(by_call.get(cid, [])) if cid else [],
                         "exact_atif_step_ids": by_atif_call.get(cid, []) if cid else []})
        if event.get("type") == "user_message":
            prompts.append((event["text"], source.source("trajectory/acp_trajectory.jsonl", line, "/text")))
    if len(prompts) != 1:
        raise ValueError("Expected one actual task user message")
    return {"timeline": timeline, "llm_messages": messages, "api_contexts": contexts,
            "llm_exchanges": exchanges, "atif_steps": steps}, prompts[0], dict(calls)


def validate(package):
    index = read(package / "diagnosis/index.json")
    table, streams = {}, {}
    for stream in index["streams"]:
        records = rows(package / stream["path"])
        if len(records) != stream["records"]:
            raise ValueError("Record count differs from index")
        streams[stream["name"]] = records
        for line, row in enumerate(records, 1):
            rid = record_id(row)
            if rid in table:
                raise ValueError("Duplicate record ID")
            table[rid] = (row, stream["path"], line)
    spans = defaultdict(list)
    for number, entry in enumerate(index["windows"], 1):
        window = read(package / entry["path"])
        if window["ordinal"] != number or window["text_chars"] != sum(len(x["text"]) for x in window["items"]):
            raise ValueError("Window order or character count differs")
        for item in window["items"]:
            row, path, line = table[item["record_id"]]
            if item["source_file"] != path or item["source_line"] != line:
                raise ValueError("Wrong window source")
            spans[item["record_id"]].append(item)
    for rid, (row, _, _) in table.items():
        text, offset = serial(row), 0
        for item in spans.pop(rid, []):
            if item["char_start"] != offset or item["record_chars"] != len(text) or item["text"] != text[offset:item["char_end"]]:
                raise ValueError("A record was truncated, changed or repeated")
            offset = item["char_end"]
        if offset != len(text):
            raise ValueError("Incomplete record coverage")
    messages = {x["message_id"] for x in streams["llm_messages"]}
    contexts = {x["context_id"] for x in streams["api_contexts"]}
    steps = {x["tool_record_id"] for x in streams["atif_steps"]}
    exchanges = streams["llm_exchanges"]
    if not exchanges or not exchanges[-1]["response_message_ids"]:
        raise ValueError("Last response missing")
    for i, exchange in enumerate(exchanges, 1):
        if exchange["exchange_line"] != i or exchange["api_context_id"] not in contexts or exchange["status_code"] != 200:
            raise ValueError("Exchange provenance differs")
        for key in ["request_message_ids", "request_input_ids", "response_message_ids"]:
            if not set(exchange[key]) <= messages:
                raise ValueError("Missing message reference")
    tools = [x for x in streams["timeline"] if x["event"].get("type") == "tool_call"]
    for event in tools:
        if (not event["exact_llm_message_ids"] or not event["exact_atif_step_ids"]
                or not set(event["exact_llm_message_ids"]) <= messages or not set(event["exact_atif_step_ids"]) <= steps):
            raise ValueError("Tool action lacks exact call/observation/ATIF links")
    return {"passed": True, "source_runs": 1, "windows": len(index["windows"]), "prepared_records": len(table),
            "llm_exchanges": len(exchanges), "acp_events": len(streams["timeline"]), "actual_tool_actions": len(tools),
            "all_record_spans_reconstructed": True, "last_response_preserved": True,
            "all_tool_events_exactly_linked": True, "model_calls": 0, "verifier_reruns": 0,
            "diagnoser_delivery_or_understanding_tested": False}


def build(package, root, commit, segment_chars, refresh=False):
    if segment_chars < 1:
        raise ValueError("Window length must be positive; it is not a model budget")
    source, helper = Source(package, root, commit), helpers(package)
    records, (prompt, prompt_source), calls = prepare_records(source, helper)
    result = source.json("result.json")
    benchmark = source.json("benchmark_result.json")
    agent, executor = result.get("agent_result") or {}, result.get("executor") or {}
    ctrf = source.json("verifier/ctrf.json")["results"]
    skills = {p.parent.name: p.relative_to(package).as_posix() for p in sorted((package / "environment/skills").glob("*/SKILL.md"))}
    public_inputs = [p for p in (package / "environment").rglob("*") if p.is_file()
                     and not p.is_relative_to(package / "environment/skills") and p.name != "Dockerfile"]
    inputs = {"files": [{"path": p.relative_to(package).as_posix(), "bytes": p.stat().st_size} for p in sorted(public_inputs)],
              "source": "original SkillsBench task environment at b63b7b2850226b6aa4fb5929a8c1ac7bc4d9a6af",
              "evaluation_inputs_not_included": True}
    metadata = {"task_id": package.name, "run_id": source.run_id, "model": benchmark["model"],
                "condition": "original-skill", "execution_ok": benchmark["execution_ok"],
                "historical_task_passed": benchmark["task_passed"], "original_reward": benchmark["reward"],
                "original_reward_unchanged": True, "agent_iterations": agent.get("iterations_used"),
                "max_parent_iterations_at_source": executor.get("max_parent_iterations_per_step"),
                "stop_reason": agent.get("stop_reason"), "n_skill_invocations": result.get("n_skill_invocations"),
                "skill_body_preload_evidence": source.source("trajectory/llm_trajectory.jsonl", 1, "/response/body/instructions"),
                "historical_task_digest": source.json("executor_request.json")["task_digest"],
                "historical_full_task_snapshot_archived": False, "current_task_not_claimed_historical_exact_tree": True,
                "historical_redactions_preserved": True, "original_artifacts": "not_archived",
                "artifact_missing_does_not_mean_model_did_not_generate_it": True,
                "ordinary_ctrf_summary": ctrf["summary"],
                "ordinary_ctrf_tests": [{"name": x["name"], "status": x["status"]} for x in ctrf["tests"]],
                "response_tool_call_counts": calls, "task_prompt_source": prompt_source,
                "model_calls_by_helper": 0, "verifier_reruns": 0}
    feedback = {"original_reward": benchmark["reward"], "historical_task_passed": benchmark["task_passed"],
                "tests": metadata["ordinary_ctrf_tests"], "current_accuracy": None,
                "current_accuracy_unavailable_reason": "original_output_not_archived",
                "test_pass_ratio_is_not_item_accuracy": True,
                "reference_values_or_verifier_assertions_included": False}
    inventory = {"original_output_status": "not_archived", "original_output_files": [],
                 "do_not_substitute_curator_solutions_or_other_runs": True}
    blobs = {"diagnosis/task_prompt.md": prompt.encode("utf-8")}

    def add(name, value):
        blobs[name] = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")

    add("diagnosis/inputs.json", inputs)
    add("diagnosis/outputs/execution_metadata.json", metadata)
    add("diagnosis/outputs/allowed_feedback.json", feedback)
    add("diagnosis/outputs/output_inventory.json", inventory)
    streams, windows = [], []
    for name, values in records.items():
        path = f"diagnosis/records/{name}.jsonl"
        blobs[path] = "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in values).encode("utf-8")
        streams.append({"name": name, "path": path, "records": len(values)})
        windows.extend(helper.make_windows(values, name, source.run_id, path, segment_chars))
    entries = []
    for i, window in enumerate(windows):
        wid = f"w{i + 1:04d}"
        window.update(window_id=wid, ordinal=i + 1, window_count=len(windows),
                      previous_window_id=f"w{i:04d}" if i else None,
                      next_window_id=f"w{i + 2:04d}" if i + 1 < len(windows) else None,
                      segmentation_is_not_model_budget=True, model_usage_limits_set_by_helper=False, model_calls=0)
        path = f"diagnosis/windows/{wid}.json"
        add(path, window)
        entries.append({"window_id": wid, "path": path, "stream": window["stream"], "text_chars": window["text_chars"]})
    index = {"schema_version": 1, "task_id": package.name, "run_id": source.run_id,
             "source": {"commit": commit, "repository_path": source.path_prefix,
                        "github_url": f"https://github.com/linyouxue/skill-repair-benchmark/tree/{commit}/{source.path_prefix}",
                        "verified_git_blobs": source.fingerprints},
             "task_prompt": "diagnosis/task_prompt.md", "skills": skills, "inputs": "diagnosis/inputs.json",
             "outputs": {"feedback": "diagnosis/outputs/allowed_feedback.json", "inventory": "diagnosis/outputs/output_inventory.json",
                         "execution_metadata": "diagnosis/outputs/execution_metadata.json"},
             "streams": streams, "windows": entries, "counts": {k: len(v) for k, v in records.items()},
             "window_text_segment_chars": segment_chars, "normalization": ["remove_cache_control", "deduplicate_identical_messages_by_reference", "safe_API_parameter_allowlist_no_transport_headers"],
             "model_usage_limits_set_by_helper": False, "model_calls": 0, "source_experiments_unchanged": True}
    index["generated_files"] = sorted([*blobs, "diagnosis/index.json", "diagnosis/validation.json"])
    old_files = set()
    old_index = package / "diagnosis/index.json"
    if old_index.exists():
        old = read(old_index)
        if not refresh or old["run_id"] != source.run_id or old["source"]["commit"] != commit:
            raise ValueError("Existing generation must explicitly refresh the identical pinned source")
        old_files = set(old["generated_files"])
    for relative in index["generated_files"]:
        path = (package / relative).resolve()
        if not path.is_relative_to((package / "diagnosis").resolve()):
            raise ValueError("Generated path escapes diagnosis")
        if path.exists() and relative not in old_files:
            raise ValueError("Refusing to overwrite an unowned file")
    add("diagnosis/index.json", index)
    for relative, value in blobs.items():
        path = package / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value)
    validation = validate(package)
    (package / "diagnosis/validation.json").write_text(json.dumps(validation, indent=2) + "\n")
    for relative in old_files - set(index["generated_files"]):
        path = (package / relative).resolve()
        if not path.is_relative_to((package / "diagnosis").resolve()):
            raise ValueError("Old generated path escapes diagnosis")
        path.unlink(missing_ok=True)
    return validation


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, default=PACKAGE)
    parser.add_argument("--source-run", type=Path)
    parser.add_argument("--source-ref", default=SOURCE_COMMIT)
    parser.add_argument("--window-chars", type=int, default=60000)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    package = args.package.resolve()
    print(json.dumps(validate(package) if args.validate_only else build(package,
        args.source_run or package.parent / ARCHIVE / package.name / "selected_run",
        args.source_ref, args.window_chars, args.refresh)))
