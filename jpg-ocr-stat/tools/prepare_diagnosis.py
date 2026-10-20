"""Build one original 22-image JPG diagnosis package offline; never run an agent."""

import argparse
import base64
import gzip
import importlib.util
import json
import re
import tarfile
import tempfile
from collections import Counter, defaultdict
from pathlib import Path


TASK_ID = "jpg-ocr-stat"
RUN_ID = "jpg-ocr-stat-opus47-original-skill-r003-infra-recovery"
SOURCE_REPOSITORY = "linyouxue/skill-repair-benchmark"
SOURCE_PATH = "evaluation/results/Opus47-OriginalSkill-79Tasks-20260920/runs/opus47-original-skill/" + RUN_ID
SOURCE_COMMIT = "70f97e72aeee8c85f77e8304cbec579e486f7de2"
SKILLS = ("image-ocr", "openai-vision", "pdf", "video-frame-extraction", "xlsx")
LLM_FILE = "trajectory/llm_trajectory.jsonl"
ACP_FILE = "trajectory/acp_trajectory.jsonl"
ATIF_FILE = "trainer/atif.json"
EXCEL_ARCHIVE = "artifacts/pre-verifier-inputs.tar.gz"
EXCEL_MEMBER = "app/workspace/stat_ocr.xlsx"
STREAM_NAMES = ("timeline", "llm_messages", "api_contexts", "llm_exchanges", "atif_steps")
ID_KEYS = ("event_id", "message_id", "context_id", "exchange_id", "tool_record_id")


def module_at(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Offline build dependency is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def helpers(package):
    path = package.parent / "jpg-ocr-skill-repair-dataset/tools/prepare_diagnosis.py"
    if not path.is_file():
        raise RuntimeError("Building requires the repository's existing JPG preprocessing helpers")
    return module_at(path, "jpg_diagnosis_build_helpers")


def serial(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_lines(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def inside(package, relative):
    path = (package / relative).resolve()
    if not path.is_relative_to(package.resolve()):
        raise ValueError("Generated path escapes the task package")
    return path


class SourceRun:
    """Read actual source files; public LLM gzip lines refer to its decoded JSONL."""

    def __init__(self, root, commit):
        self.root = Path(root).resolve()
        if self.root.name != RUN_ID or not self.root.is_dir():
            raise ValueError("Source must be the specified authoritative Opus original-task run")
        if not re.fullmatch(r"[0-9a-fA-F]{40}", commit):
            raise ValueError("Source ref must be an explicit 40-character commit SHA")
        self.commit = commit

    def path(self, relative):
        plain = self.root / relative
        if plain.is_file():
            return plain
        zipped = self.root / (relative + ".gz")
        if zipped.is_file():
            return zipped
        raise FileNotFoundError("Required source file is unavailable: " + relative)

    def public_file(self, relative):
        return relative + ".gz" if relative == LLM_FILE else relative

    def source(self, relative, line=None, pointer=""):
        filename = self.public_file(relative)
        result = {"repository_path": SOURCE_PATH + "/" + filename,
                  "file": filename, "commit": self.commit, "pointer": pointer}
        if line is not None:
            result["line"] = line
        if relative == LLM_FILE:
            result["line_numbering"] = "decoded_gzip_jsonl_lines"
        return result

    def lines(self, relative):
        path = self.path(relative)
        opener = gzip.open if path.suffix == ".gz" else open
        with opener(path, "rt", encoding="utf-8") as stream:
            for line, text in enumerate(stream, 1):
                if text.strip():
                    yield line, json.loads(text)

    def json(self, relative):
        path = self.path(relative)
        opener = gzip.open if path.suffix == ".gz" else open
        with opener(path, "rt", encoding="utf-8") as stream:
            return json.load(stream)


def without_cache(value):
    if isinstance(value, dict):
        return {k: without_cache(v) for k, v in value.items() if k != "cache_control"}
    if isinstance(value, list):
        return [without_cache(v) for v in value]
    return value


class ImageEvidence:
    def __init__(self, package, helper):
        paths = sorted((package / "environment/workspace/dataset/img").glob("*.jpg"))
        if len(paths) != 22:
            raise ValueError("The original task must contain exactly its 22 source JPGs")
        self.rows = [{"asset_id": p.name, "path": p.relative_to(package).as_posix(),
                      "mime_type": "image/jpeg", "kind": "source_task_image"} for p in paths]
        self.raw = [p.read_bytes() for p in paths]
        if any(helper.image_format(b)[0] != "image/jpeg" for b in self.raw):
            raise ValueError("Source JPG header is invalid")
        self.observations = []

    def normalize(self, value, source):
        if isinstance(value, dict):
            kind = value.get("type")
            payload = None
            if kind in ("image_url", "input_image"):
                url = value.get("image_url", "")
                url = url.get("url", "") if isinstance(url, dict) else url
                if isinstance(url, str) and url.startswith("data:image/"):
                    payload = base64.b64decode(url.split(",", 1)[1], validate=True)
                elif url:
                    raise ValueError("Unexpected external historical image; it was not downloaded")
            elif kind == "image":
                origin = value.get("source") or {}
                encoded = value.get("data") or (origin.get("data") if isinstance(origin, dict) else None)
                if isinstance(encoded, str):
                    payload = base64.b64decode(encoded, validate=True)
            if payload is not None:
                if payload not in self.raw:
                    raise ValueError("Unexpected historical crop outside the verified source image inventory")
                asset = self.rows[self.raw.index(payload)]
                self.observations.append({"asset_id": asset["asset_id"], "source": source})
                return {"type": "image_asset", "asset_id": asset["asset_id"],
                        "path": asset["path"], "mime_type": asset["mime_type"]}
            return {k: self.normalize(v, {**source, "pointer": source["pointer"] + "/" + k.replace("~", "~0").replace("/", "~1")})
                    for k, v in value.items() if k != "cache_control"}
        if isinstance(value, list):
            return [self.normalize(v, {**source, "pointer": source["pointer"] + "/" + str(i)})
                    for i, v in enumerate(value)]
        return value


def prepare_records(source, image_evidence, helper):
    messages, contexts, exchanges = [], [], []
    unique_messages, unique_contexts = {}, {}
    messages_by_call = defaultdict(set)

    def remember(message, line, pointer):
        norm = image_evidence.normalize(message, source.source(LLM_FILE, line, pointer))
        key = serial(norm)
        if key not in unique_messages:
            mid = f"{RUN_ID}:m{len(messages) + 1:04d}"
            unique_messages[key] = mid
            messages.append({"message_id": mid, "source": source.source(LLM_FILE, line, pointer), "message": norm})
        mid = unique_messages[key]
        for cid in helper.tool_ids(norm):
            messages_by_call[cid].add(mid)
        return mid

    response_calls = []
    for line, row in source.lines(LLM_FILE):
        request, response = row.get("request") or {}, row.get("response") or {}
        body = request.get("body") or {}
        parameters = without_cache(helper.request_parameters(body))
        key = serial(parameters)
        if key not in unique_contexts:
            cid = f"{RUN_ID}:c{len(contexts) + 1:04d}"
            unique_contexts[key] = cid
            contexts.append({"context_id": cid, "source": source.source(LLM_FILE, line, "/request/body"),
                             "parameters": parameters,
                             "parameter_source_pointers": {k: "/request/body/" + helper.pointer_part(k) for k in parameters},
                             "policy": "safe_parameter_allowlist_no_transport_headers_or_credentials_remove_cache_control"})
        exchange = {"exchange_id": f"{RUN_ID}:e{line:04d}", "source": source.source(LLM_FILE, line),
                    "run_id": RUN_ID, "exchange_line": line, "api_context_id": unique_contexts[key],
                    "request_timestamp": request.get("timestamp"), "response_timestamp": response.get("timestamp"),
                    "status_code": response.get("status_code"), "duration_ms": row.get("duration_ms"),
                    "request_message_ids": [], "request_input_ids": [], "response_message_ids": [],
                    "response_metadata": {}, "choice_metadata": []}
        for key, target in (("messages", "request_message_ids"), ("input", "request_input_ids")):
            values = body.get(key) or []
            if isinstance(values, str):
                values = [{"role": "user", "content": values}]
            for i, message in enumerate(values):
                if not isinstance(message, dict):
                    message = {"type": "unstructured_input", "content": message}
                exchange[target].append(remember(message, line, f"/request/body/{key}/{i}"))
        rb = response.get("body")
        if isinstance(rb, dict):
            exchange["response_metadata"] = {k: helper.safe_api_value(rb[k]) for k in helper.RESPONSE_METADATA_KEYS if k in rb}
            if isinstance(rb.get("usage"), dict):
                exchange["usage"] = helper.safe_usage(rb["usage"])
            for i, choice in enumerate(rb.get("choices") or []):
                message_key = "message" if choice.get("message") else "delta"
                message = choice.get(message_key)
                choice_row = {"choice_index": choice.get("index", i), "finish_reason": choice.get("finish_reason"),
                              "source": source.source(LLM_FILE, line, f"/response/body/choices/{i}"),
                              "response_message_id": None}
                extra = choice.get("provider_specific_fields") or {}
                choice_row["provider_stop_metadata"] = {k: helper.safe_api_value(extra[k])
                                                         for k in ("finish_reason", "stop_reason") if k in extra}
                if message:
                    mid = remember(message, line, f"/response/body/choices/{i}/{message_key}")
                    exchange["response_message_ids"].append(mid)
                    choice_row["response_message_id"] = mid
                    for call in message.get("tool_calls") or []:
                        response_calls.append({"call_id": call.get("id"),
                                               "name": (call.get("function") or {}).get("name"),
                                               "message_id": mid, "exchange_id": exchange["exchange_id"]})
                exchange["choice_metadata"].append(choice_row)
            if not rb.get("choices"):
                exchange["other_response"] = image_evidence.normalize(rb, source.source(LLM_FILE, line, "/response/body"))
        elif rb is not None:
            exchange["other_response"] = rb
        exchanges.append(exchange)

    atif = source.json(ATIF_FILE)
    steps, steps_by_call = [], defaultdict(list)
    for i, step in enumerate(atif.get("steps") or []):
        sid = f"{RUN_ID}:s{i + 1:04d}"
        norm = image_evidence.normalize(step, source.source(ATIF_FILE, pointer=f"/steps/{i}"))
        exact_messages = set()
        for call in step.get("tool_calls") or []:
            cid = call.get("tool_call_id")
            steps_by_call[cid].append(sid)
            exact_messages.update(messages_by_call.get(cid, []))
        steps.append({"tool_record_id": sid, "record_kind": "source_atif_step_not_additional_agent_action",
                      "source": source.source(ATIF_FILE, pointer=f"/steps/{i}"), "step": norm,
                      "exact_llm_message_ids": sorted(exact_messages)})
    by_message = {m["message_id"]: m for m in messages}
    by_step = {s["tool_record_id"]: s for s in steps}
    timeline, prompts = [], []
    for line, event in source.lines(ACP_FILE):
        eid = f"{RUN_ID}:a{line:04d}"
        norm = image_evidence.normalize(event, source.source(ACP_FILE, line))
        cid = event.get("tool_call_id")
        mids = sorted(messages_by_call.get(cid, [])) if cid else []
        sids = steps_by_call.get(cid, []) if cid else []
        timeline.append({"event_id": eid, "run_id": RUN_ID, "source": source.source(ACP_FILE, line),
                         "event": norm, "exact_llm_message_ids": mids, "exact_atif_step_ids": sids,
                         "tool_parameter_link": "tool_call_id_exact" if mids else "not_a_tool_call" if not cid else "not_matched",
                         "image_links": helper.filename_links(
                             [norm, *[by_message[m] for m in mids], *[by_step[s] for s in sids]],
                             [a["asset_id"] for a in image_evidence.rows])})
        if event.get("type") == "user_message":
            prompts.append((event.get("text"), source.source(ACP_FILE, line, "/text")))
    if len(prompts) != 1 or not isinstance(prompts[0][0], str):
        raise ValueError("The authoritative ACP must contain one real task user message")
    if (len(exchanges) != 65 or len(timeline) != 74 or len(steps) != 45
            or sum(e["event"].get("type") == "tool_call" for e in timeline) != 43):
        raise ValueError("Source run differs from the verified original JPG evidence inventory")
    call_counts = Counter(c["name"] for c in response_calls)
    if call_counts["think"] != 22 or sum(call_counts.values()) != 65:
        raise ValueError("Source response call accounting differs from the verified 65 iterations")
    if image_evidence.observations:
        raise ValueError("Source unexpectedly contains historical visual blocks; re-audit before publishing")
    return {"timeline": timeline, "llm_messages": messages, "api_contexts": contexts,
            "llm_exchanges": exchanges, "atif_steps": steps}, prompts[0], dict(call_counts)


def check_skills(package, source):
    result = {}
    for name in SKILLS:
        relative = f"environment/skills/{name}/SKILL.md"
        current = inside(package, relative).read_text(encoding="utf-8")
        original = source.path(f"inputs/skills/{name}/SKILL.md").read_text(encoding="utf-8")
        if current != original:  # read_text applies universal newline conversion only.
            raise ValueError("Published Skill differs beyond line endings from the source snapshot: " + name)
        result[name] = relative
    return result


def excel_bytes(source):
    with tarfile.open(source.path(EXCEL_ARCHIVE), "r:gz") as tar:
        member = tar.getmember(EXCEL_MEMBER)
        if not member.isfile():
            raise ValueError("Source Excel member is not a regular file")
        stream = tar.extractfile(member)
        if stream is None:
            raise ValueError("Original Excel was not archived")
        raw = stream.read()
    if len(raw) != 5367:
        raise ValueError("Original Excel bytes differ from the verified source delivery")
    return raw


def execution_metadata(source, records, call_counts, prompt_source):
    result = source.json("result.json")
    agent = result.get("agent_result") or {}
    executor = result.get("executor") or {}
    ctrf = source.json("verifier/ctrf.json").get("results") or {}
    safe_summary = {k: v for k, v in (ctrf.get("summary") or {}).items()
                    if isinstance(v, (int, float)) and not isinstance(v, bool)}
    reward = (result.get("rewards") or {}).get("reward")
    meta = {"task_id": TASK_ID, "run_id": RUN_ID, "source": source.source("result.json"),
            "model": result.get("model"), "skill_mode": result.get("skill_mode"),
            "started_at": result.get("started_at"), "finished_at": result.get("finished_at"),
            "original_reward": reward, "original_reward_unchanged": True,
            "ordinary_ctrf_summary": safe_summary,
            "ordinary_ctrf_tests": [{"name": t.get("name"), "status": t.get("status")}
                                    for t in ctrf.get("tests") or []],
            "ctrf_source": source.source("verifier/ctrf.json"),
            "agent_iterations": agent.get("iterations_used"),
            "max_iterations_at_source": agent.get("max_iterations_per_run"),
            "termination_reason": agent.get("stop_reason"), "acp_stop_reason": agent.get("acp_stop_reason"),
            "budget_termination_is_not_natural_completion": agent.get("stop_reason") == "max_iterations",
            "partial_trajectory_at_source": result.get("partial_trajectory"),
            "generation_error_category_at_source": result.get("error_category"),
            "n_skill_invocations": result.get("n_skill_invocations"),
            "task_prompt_source": prompt_source, "response_tool_call_counts": call_counts,
            "original_visual_messages_recorded": False,
            "source_images_provided_now_do_not_prove_historical_agent_vision": True,
            "normalization": ["drop_transport_headers_and_credentials",
                              "safe_request_parameter_allowlist", "remove_cache_control",
                              "identical_normalized_messages_referenced_once"],
            "model_calls_by_preprocessor": 0, "verifier_reruns": 0,
            "offline_field_scoring_only": True, "model_usage_limits_set_by_helper": False,
            "source_record_counts": {k: len(v) for k, v in records.items()}}
    allowed = ("name", "protocol_id", "protocol_version", "agent", "model", "provider_protocol",
               "skill_exposure_mode", "evaluation_condition", "max_parent_iterations_per_step",
               "iteration_scope", "skill_context_preloaded", "preloaded_skill_count",
               "iteration_accounting_complete", "iteration_limit_reached", "iteration_limit_hits",
               "stop_reason", "skill_context_preload_observed", "observed_preloaded_skill_count",
               "skill_context_preload_matches_expected")
    meta["executor"] = {k: executor[k] for k in allowed if k in executor}
    if meta["agent_iterations"] != 65 or meta["max_iterations_at_source"] != 65 or reward != 0:
        raise ValueError("Original source termination or binary reward differs from the audited run")
    return meta


def prepare_outputs(package, source, raw, original_reward, image_ids):
    scorer = module_at(package / "verifier/score_accuracy.py", "jpg_original_offline_accuracy")
    with tempfile.TemporaryDirectory(prefix="jpg-original-offline-score-") as tmp:
        actual = Path(tmp) / "stat_ocr.xlsx"
        actual.write_bytes(raw)
        predictions, issues, rows = scorer.read_predictions(actual, image_ids)
        feedback = scorer.score(actual, package / "verifier/stat_oracle.xlsx")
    if issues or len(predictions) != 22 or len(rows) != 23:
        raise ValueError("The original workbook no longer matches the audited 22-row delivery")
    feedback.update(kind="offline_derived_field_feedback", original_reward=original_reward,
                    original_reward_unchanged=True,
                    reward_interpretation="derived_exact_field_accuracy_not_the_original_binary_reward",
                    source={**source.source(EXCEL_ARCHIVE), "archive_member": EXCEL_MEMBER},
                    scoring_source="verifier/score_accuracy.py", verifier_reruns=0)
    predicted = {"run_id": RUN_ID, "columns": ["filename", "date", "total_amount"],
                 "rows": [{"filename": n, "date": predictions[n][0], "total_amount": predictions[n][1]}
                          for n in image_ids], "contains_ground_truth": False,
                 "source": {**source.source(EXCEL_ARCHIVE), "archive_member": EXCEL_MEMBER}}
    inventory = {"run_id": RUN_ID, "files": [{"path": "diagnosis/outputs/stat_ocr.xlsx",
                  "bytes": len(raw), "kind": "original_agent_excel", "source": predicted["source"]}],
                 "delivered_original_excels": 1, "prediction_rows": 22,
                 "original_excel_bytes_preserved": True, "model_calls": 0}
    return predicted, feedback, inventory


def record_id(record):
    return next(record[k] for k in ID_KEYS if isinstance(record.get(k), str))


def generated_path(relative):
    fixed = {"diagnosis/task_prompt.md", "diagnosis/images.json", "diagnosis/index.json", "diagnosis/validation.json",
             "diagnosis/outputs/stat_ocr.xlsx", "diagnosis/outputs/predictions.json",
             "diagnosis/outputs/allowed_feedback.json", "diagnosis/outputs/output_inventory.json",
             "diagnosis/outputs/execution_metadata.json"}
    return (relative in fixed or relative in {f"diagnosis/records/{name}.jsonl" for name in STREAM_NAMES}
            or re.fullmatch(r"diagnosis/windows/w\d{4,}\.json", relative) is not None)


def validate(package):
    package = Path(package).resolve()
    index = read(package / "diagnosis/index.json")
    tables = {}
    by_stream = {}
    for stream in index["streams"]:
        rows = read_lines(inside(package, stream["path"]))
        if len(rows) != stream["records"]:
            raise ValueError("Prepared stream count does not match its index")
        by_stream[stream["name"]] = rows
        for line, row in enumerate(rows, 1):
            rid = record_id(row)
            if rid in tables:
                raise ValueError("Duplicate prepared record ID")
            tables[rid] = (row, stream["path"], line)
    images = read(inside(package, index["images"]))
    image_ids = [a["asset_id"] for a in images["assets"]]
    if len(image_ids) != 22 or len(set(image_ids)) != 22 or images["source_image_count"] != 22:
        raise ValueError("Original source image inventory must contain 22 unique images")
    for asset in images["assets"]:
        if not inside(package, asset["path"]).is_file():
            raise ValueError("Referenced source image is missing")
    spans = defaultdict(list)
    for number, window_row in enumerate(index["windows"], 1):
        window = read(inside(package, window_row["path"]))
        if (window["ordinal"] != number or window["attachments"] != image_ids
                or window["image_count"] != 22 or window_row["image_count"] != 22):
            raise ValueError("Window sequence or full-image attachment references are invalid")
        if sum(len(x["text"]) for x in window["items"]) != window["text_chars"]:
            raise ValueError("Window character accounting is invalid")
        for item in window["items"]:
            if item["record_id"] not in tables:
                raise ValueError("Window refers to an unknown source record")
            _, source_file, source_line = tables[item["record_id"]]
            if item["source_file"] != source_file or item["source_line"] != source_line:
                raise ValueError("Window source mapping is invalid")
            spans[item["record_id"]].append(item)
    for rid, (row, _, _) in tables.items():
        text, offset = serial(row), 0
        for piece in spans.pop(rid, []):
            if piece["char_start"] != offset or piece["record_chars"] != len(text):
                raise ValueError("Record continuation has a missing or repeated range")
            if piece["text"] != text[piece["char_start"]:piece["char_end"]]:
                raise ValueError("Window fragment differs from its original prepared record")
            offset = piece["char_end"]
        if offset != len(text):
            raise ValueError("A source record was not fully covered")
    if spans:
        raise ValueError("Unexpected source spans")
    messages = {r["message_id"] for r in by_stream["llm_messages"]}
    contexts = {r["context_id"] for r in by_stream["api_contexts"]}
    atif_ids = {r["tool_record_id"] for r in by_stream["atif_steps"]}
    exchanges = by_stream["llm_exchanges"]
    if len(exchanges) != 65 or [x["exchange_line"] for x in exchanges] != sorted({x["exchange_line"] for x in exchanges}):
        raise ValueError("Source exchange count or chronological source line sequence is invalid")
    for exchange in exchanges:
        if (exchange["status_code"] != 200
                or exchange["source"]["line"] != exchange["exchange_line"]
                or exchange["source"]["repository_path"] != SOURCE_PATH + "/" + LLM_FILE + ".gz"):
            raise ValueError("Logged source exchange status or provenance changed")
        for field in ("request_timestamp", "response_timestamp", "duration_ms"):
            if field not in exchange:
                raise ValueError("Source exchange timing field is missing")
        if exchange["api_context_id"] not in contexts:
            raise ValueError("Exchange context reference is invalid")
        for key in ("request_message_ids", "request_input_ids", "response_message_ids"):
            if not set(exchange[key]) <= messages:
                raise ValueError("Exchange contains a missing message reference")
        if [c["response_message_id"] for c in exchange["choice_metadata"] if c["response_message_id"]] != exchange["response_message_ids"]:
            raise ValueError("Choice and provider-response references disagree")
    if not exchanges[-1]["response_message_ids"]:
        raise ValueError("The last provider response is missing")
    timeline = by_stream["timeline"]
    tools = [e for e in timeline if e["event"].get("type") == "tool_call"]
    if len(timeline) != 74 or len(tools) != 43:
        raise ValueError("Original ACP action count is invalid")
    for event in timeline:
        if (not set(event["exact_llm_message_ids"]) <= messages
                or not set(event["exact_atif_step_ids"]) <= atif_ids):
            raise ValueError("ACP references are invalid")
        if event in tools and (not event["exact_llm_message_ids"] or not event["exact_atif_step_ids"]):
            raise ValueError("A real ACP action lacks its exact LLM/ATIF evidence")
    return {"passed": True, "source_images": 22, "source_runs": 1,
            "windows": len(index["windows"]), "prepared_records": len(tables),
            "llm_exchanges": len(exchanges), "last_response_preserved": True,
            "all_record_spans_reconstructed": True, "all_43_acp_tool_events_exactly_linked": True,
            "every_window_attaches_all_22_images": True, "model_calls": 0, "verifier_reruns": 0,
            "model_usage_limits_set_by_helper": False, "diagnoser_delivery_or_understanding_tested": False}


def build(package, source_run, source_ref, segment_chars=60000, refresh=False):
    package = Path(package).resolve()
    if segment_chars < 1:
        raise ValueError("Material segmentation length must be positive")
    helper = helpers(package)
    source = SourceRun(source_run, source_ref)
    output = package / "diagnosis"
    index_path = output / "index.json"
    old_files = set()
    if index_path.is_file():
        if not refresh:
            raise ValueError("Diagnosis output exists; use --refresh for owned generated files")
        previous = read(index_path)
        if previous.get("run_id") != RUN_ID or previous.get("source", {}).get("repository_path") != SOURCE_PATH:
            raise ValueError("Refusing to refresh a different source run")
        old_files = set(previous.get("generated_files") or [])
        if not old_files or any(not generated_path(r) or not inside(package, r).is_relative_to(output) for r in old_files):
            raise ValueError("Generated file ownership index is invalid")
    elif output.exists() and any(p.is_file() and p != output / "README.md" for p in output.rglob("*")):
        raise ValueError("Existing diagnosis files have no valid generated ownership index")
    image_evidence = ImageEvidence(package, helper)
    records, (prompt, prompt_source), call_counts = prepare_records(source, image_evidence, helper)
    skills = check_skills(package, source)
    raw = excel_bytes(source)
    metadata = execution_metadata(source, records, call_counts, prompt_source)
    image_ids = [a["asset_id"] for a in image_evidence.rows]
    predictions, feedback, inventory = prepare_outputs(package, source, raw, metadata["original_reward"], image_ids)
    blobs = {}

    def add_json(relative, value):
        blobs[relative] = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")

    streams, windows = [], []
    for name in STREAM_NAMES:
        relative = f"diagnosis/records/{name}.jsonl"
        rows = records[name]
        blobs[relative] = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows).encode("utf-8")
        streams.append({"name": name, "path": relative, "records": len(rows)})
        windows.extend(helper.make_windows(rows, name, RUN_ID, relative, segment_chars))
    window_index = []
    for i, window in enumerate(windows):
        wid = f"w{i + 1:04d}"
        window.update(window_id=wid, ordinal=i + 1, window_count=len(windows),
                      previous_window_id=f"w{i:04d}" if i else None,
                      next_window_id=f"w{i + 2:04d}" if i + 1 < len(windows) else None,
                      remaining_window_range=[i + 2, len(windows)] if i + 1 < len(windows) else [],
                      attachments=list(image_ids), image_count=22, model_calls=0,
                      segmentation_is_not_model_budget=True, model_usage_limits_set_by_helper=False,
                      source_assets_stored_once=True,
                      repeated_image_delivery_may_increase_method_cost=True)
        relative = f"diagnosis/windows/{wid}.json"
        add_json(relative, window)
        window_index.append({"window_id": wid, "path": relative, "stream": window["stream"],
                             "run_id": RUN_ID, "text_chars": window["text_chars"], "image_count": 22})
    blobs["diagnosis/task_prompt.md"] = prompt.encode("utf-8")
    blobs["diagnosis/outputs/stat_ocr.xlsx"] = raw
    add_json("diagnosis/images.json", {"source_image_count": 22, "assets": image_evidence.rows,
                                       "historical_visual_payload_count": 0,
                                       "source_agent_visual_messages_recorded": False,
                                       "source_images_stored_once": True})
    for name, value in (("predictions", predictions), ("allowed_feedback", feedback),
                        ("output_inventory", inventory), ("execution_metadata", metadata)):
        add_json(f"diagnosis/outputs/{name}.json", value)
    index = {"schema_version": 1, "task_id": TASK_ID, "run_id": RUN_ID,
             "source": {"repository_path": SOURCE_PATH, "commit": source_ref,
                        "github_url": f"https://github.com/{SOURCE_REPOSITORY}/tree/{source_ref}/{SOURCE_PATH}"},
             "task_prompt": "diagnosis/task_prompt.md", "skills": skills, "images": "diagnosis/images.json",
             "outputs": {"excel": "diagnosis/outputs/stat_ocr.xlsx", "predictions": "diagnosis/outputs/predictions.json",
                         "feedback": "diagnosis/outputs/allowed_feedback.json", "inventory": "diagnosis/outputs/output_inventory.json",
                         "execution_metadata": "diagnosis/outputs/execution_metadata.json"},
             "streams": streams, "windows": window_index,
             "counts": {"source_images": 22, "source_runs": 1, "llm_exchanges": 65,
                        "acp_events": 74, "non_think_tool_calls": 43, "think_calls": 22,
                        "atif_steps": len(records["atif_steps"]), "windows": len(windows),
                        "unique_llm_messages": len(records["llm_messages"]),
                        "api_contexts": len(records["api_contexts"]),
                        "prepared_records": sum(len(v) for v in records.values())},
             "window_text_segment_chars": segment_chars, "segmentation_is_not_model_budget": True,
             "model_usage_limits_set_by_helper": False, "model_calls": 0, "verifier_reruns": 0,
             "single_original_task_not_the_six_group_training_dataset": True,
             "source_experiments_unchanged": True,
             "normalization_policy": metadata["normalization"]}
    index["generated_files"] = sorted([*blobs, "diagnosis/index.json", "diagnosis/validation.json"])
    add_json("diagnosis/index.json", index)
    for relative in index["generated_files"]:
        path = inside(package, relative)
        if path.exists() and relative not in old_files:
            raise ValueError("Refusing to overwrite a file outside the previous generated ownership index")
    for relative, data in blobs.items():
        path = inside(package, relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    validation = validate(package)
    helper.write(output / "validation.json", validation)
    for relative in old_files - set(index["generated_files"]):
        inside(package, relative).unlink(missing_ok=True)
    return validation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--source-run", type=Path)
    parser.add_argument("--source-ref", default=SOURCE_COMMIT)
    parser.add_argument("--window-chars", type=int, default=60000,
                        help="Lossless material segmentation length; not a model token, call or cost limit")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    if args.validate_only:
        result = validate(args.package)
    else:
        root = args.source_run or args.package.resolve().parent / SOURCE_PATH
        result = build(args.package, root, args.source_ref, args.window_chars, args.refresh)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
