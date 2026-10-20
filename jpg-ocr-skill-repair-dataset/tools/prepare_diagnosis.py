"""Prepare training evidence offline. Standard library only; no network or model calls."""

import argparse
import base64
import json
import tarfile
from collections import Counter, defaultdict
from pathlib import Path


VERSION = "jpg-diagnosis-preprocessed-v2"
LLM_MEMBER = "trajectory/llm_trajectory.jsonl"
ACP_MEMBER = "trajectory/acp_trajectory.jsonl"
IMAGE_DELIVERY_POLICY = "all_group_images_per_independent_window"
# Transport headers, arbitrary provider metadata and credentials are not copied.
REQUEST_PARAMETER_KEYS = frozenset((
    "model", "tools", "tool_choice", "parallel_tool_calls", "max_tokens",
    "max_completion_tokens", "max_output_tokens", "temperature", "top_p", "top_k",
    "seed", "stop", "stream", "stream_options", "reasoning", "reasoning_effort",
    "thinking", "response_format", "frequency_penalty", "presence_penalty",
    "logit_bias", "n", "modalities", "text", "max_tool_calls", "truncation",
    "verbosity", "instructions", "provider",
))
PRIVATE_API_KEYS = frozenset((
    "authorization", "proxy-authorization", "headers", "api_key", "apikey",
    "access_token", "refresh_token", "credentials", "password", "secret", "token",
))
RESPONSE_METADATA_KEYS = ("id", "created", "model", "object", "system_fingerprint",
                          "service_tier", "provider")


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def serial(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def safe_api_value(value):
    """Keep allowed JSON values, excluding credential-shaped keys at any level."""
    if isinstance(value, dict):
        return {k: safe_api_value(v) for k, v in value.items()
                if k.lower() not in PRIVATE_API_KEYS}
    if isinstance(value, list):
        return [safe_api_value(v) for v in value]
    return value


def request_parameters(body):
    # Tool definitions are JSON Schemas, not actual call arguments or credentials.
    # A schema property called token/password/headers must retain its real definition.
    return {k: v if k == "tools" else safe_api_value(v)
            for k, v in body.items() if k in REQUEST_PARAMETER_KEYS}


def safe_usage(value):
    """Usage is numeric evidence; do not copy arbitrary nested provider strings."""
    if isinstance(value, dict):
        return {k: safe_usage(v) for k, v in value.items()
                if k.lower() not in PRIVATE_API_KEYS
                and isinstance(v, (dict, int, float)) and not isinstance(v, bool)}
    return value


def pointer_part(value):
    return value.replace("~", "~0").replace("/", "~1")


def inside(root, path):
    resolved = (root / path).resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError("Path escapes package")
    return resolved


def image_format(data):
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", ".png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", ".jpg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif", ".gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp", ".webp"
    raise ValueError("Unrecognized embedded image header")


def tool_ids(value):
    ids = set()
    if isinstance(value, dict):
        for key in ("tool_call_id", "call_id"):
            if isinstance(value.get(key), str):
                ids.add(value[key])
        for call in value.get("tool_calls") or []:
            if call.get("id"):
                ids.add(call["id"])
        for child in value.values():
            if isinstance(child, (dict, list)):
                ids.update(tool_ids(child))
    elif isinstance(value, list):
        for child in value:
            ids.update(tool_ids(child))
    return ids


class Assets:
    """Exact byte comparison, no perceptual matching or new digest files."""

    def __init__(self, package, output, images):
        self.package = package
        self.output = output
        self.rows = []
        self.bytes = []
        self.observations = {}
        for image in images:
            self.rows.append({**image, "kind": "source_training_image"})
            self.bytes.append(inside(package, image["path"]).read_bytes())

    def add(self, data, source, owner, delivered):
        mime, suffix = image_format(data)
        for index, old in enumerate(self.bytes):
            if data == old:
                row = self.rows[index]
                break
        else:
            number = len(self.rows) - 20 + 1
            aid = f"observed_{number:04d}"
            path = self.output / "assets" / (aid + suffix)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            row = {"asset_id": aid, "path": path.relative_to(self.package).as_posix(),
                   "mime_type": mime, "kind": "historical_visual_payload", "bytes": len(data)}
            self.rows.append(row)
            self.bytes.append(data)
        # Repeated API prefixes are represented by message/exchange references, not duplicate assets.
        key = (row["asset_id"], owner["run_id"], owner.get("tool_call_id"), owner.get("role"),
               source["member"], delivered)
        if key not in self.observations:
            self.observations[key] = {
                "observation_id": f"v{len(self.observations) + 1:05d}",
                "asset_id": row["asset_id"], **owner, "first_source": source,
                "included_in_successful_logged_request": delivered,
                "evidence_meaning": "payload_present_not_proof_of_model_understanding",
                "repeated_source_occurrences": 0,
            }
        else:
            self.observations[key]["repeated_source_occurrences"] += 1
        return {"type": "image_asset", "asset_id": row["asset_id"], "path": row["path"],
                "mime_type": mime}

    def normalize(self, obj, source, owner, delivered=False, pointer=""):
        if isinstance(obj, dict):
            kind = obj.get("type")
            payload = None
            if kind in ("image_url", "input_image"):
                url = obj.get("image_url", "")
                url = url.get("url", "") if isinstance(url, dict) else url
                if isinstance(url, str) and url.startswith("data:image/"):
                    payload = base64.b64decode(url.split(",", 1)[1], validate=True)
                elif url:
                    return {"type": "external_image_reference", "url": url,
                            "not_downloaded": True, "source": {**source, "pointer": pointer}}
            elif kind == "image":
                src = obj.get("source", {})
                encoded = obj.get("data") or (src.get("data") if isinstance(src, dict) else None)
                if isinstance(encoded, str):
                    payload = base64.b64decode(encoded, validate=True)
            if payload is not None:
                result = self.add(payload, {**source, "pointer": pointer}, owner, delivered)
                metadata = {k: v for k, v in obj.items() if k not in ("data", "image_url", "source", "cache_control")}
                if isinstance(obj.get("image_url"), dict):
                    metadata["image_url"] = {k: v for k, v in obj["image_url"].items() if k != "url"}
                if isinstance(obj.get("source"), dict):
                    metadata["source"] = {k: v for k, v in obj["source"].items() if k != "data"}
                result["original_image_block_metadata"] = metadata
                return result
            return {k: self.normalize(v, source, owner, delivered, f"{pointer}/{k}")
                    for k, v in obj.items() if k != "cache_control"}
        if isinstance(obj, list):
            return [self.normalize(v, source, owner, delivered, f"{pointer}/{i}")
                    for i, v in enumerate(obj)]
        return obj


def filename_links(value, image_ids):
    text = serial(value)
    found = sorted(name for name in image_ids if name in text)
    return {"explicit_filename_mentions": found,
            "association_scope": "explicit_mentions" if found else "batch_context_only",
            "batch_image_ids": image_ids,
            "each_image_processed_or_seen_not_proven_by_mentions": True}


def atif_fallback(package, source_run, events):
    """Use real ATIF call IDs when the separate provider log lacks that call."""
    missing = {e["event"]["tool_call_id"] for e in events
               if e["event"].get("tool_call_id") and not e["exact_llm_message_ids"]}
    records = []
    if missing:
        with tarfile.open(inside(package, source_run["archive"]), "r:xz") as tar:
            member = "trainer/atif.json"
            if member in tar.getnames():
                atif = json.load(tar.extractfile(member))
                for i, step in enumerate(atif.get("steps", [])):
                    for j, call in enumerate(step.get("tool_calls") or []):
                        if call.get("tool_call_id") not in missing:
                            continue
                        results = [{"source_pointer": f"/steps/{i}/observation/results/{k}", "result": result}
                                   for k, result in enumerate((step.get("observation") or {}).get("results", []))
                                   if result.get("source_call_id") == call["tool_call_id"]]
                        records.append({"tool_record_id": f"{source_run['run_id']}:t{len(records) + 1:04d}",
                                        "source": {"archive": source_run["archive"], "member": member,
                                                   "pointer": f"/steps/{i}/tool_calls/{j}"},
                                        "tool_call": call, "observations": results,
                                        "not_a_reconstructed_provider_exchange": True})
    by_id = {r["tool_call"]["tool_call_id"]: r for r in records}
    for event in events:
        match = by_id.get(event["event"].get("tool_call_id"))
        event["exact_atif_tool_record_ids"] = [match["tool_record_id"]] if match else []
        if match:
            event["tool_parameter_link"] = "atif_tool_call_id_exact"
            event["image_links"] = filename_links([event["event"], match], event["image_links"]["batch_image_ids"])
    return records


def record_streams(run):
    streams = [("timeline.jsonl", "acp"), ("api_contexts.jsonl", "api_request_contexts"),
               ("llm_exchanges.jsonl", "llm_exchanges"),
               ("llm_messages.jsonl", "llm_unique_messages")]
    if run.get("exact_atif_tool_links"):
        streams.append(("atif_tool_calls.jsonl", "atif_exact_tool_fallback"))
    return streams


def prepare_run(package, group_dir, source_run, assets, image_ids, refresh=False):
    run_id = source_run["run_id"]
    out = group_dir / "runs" / run_id
    if out.exists():
        if not refresh or read(out / "index.json")["archive"] != source_run["archive"]:
            raise ValueError(f"Refusing to overwrite prepared run: {run_id}")
    out.mkdir(parents=True, exist_ok=True)
    selected = inside(package, source_run["path"]) / "selected_run"
    archive = source_run["archive"]
    acp_path = selected / "trajectory/acp_trajectory.jsonl"
    acp = read_lines(acp_path)
    messages, exchanges, lookup = [], [], {}
    contexts, context_lookup = [], {}
    calls = defaultdict(set)

    def remember(message, line_no, pointer, successful):
        source = {"archive": archive, "member": LLM_MEMBER, "line": line_no, "pointer": pointer}
        owner = {"run_id": run_id, "role": message.get("role", message.get("type", "unknown")),
                 "tool_call_id": message.get("tool_call_id", message.get("call_id"))}
        norm = assets.normalize(message, source, owner, successful, pointer)
        key = serial(norm)
        if key not in lookup:
            mid = f"{run_id}:m{len(messages) + 1:04d}"
            lookup[key] = mid
            messages.append({"message_id": mid, "first_source": source, "message": norm})
        mid = lookup[key]
        for tid in tool_ids(norm):
            calls[tid].add(mid)
        return mid

    with tarfile.open(inside(package, archive), "r:xz") as tar:
        stream = tar.extractfile(LLM_MEMBER)
        if stream is None:
            raise ValueError(f"Missing LLM archive member: {run_id}")
        for line_no, line in enumerate(stream, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            request = row.get("request", {})
            response = row.get("response", {})
            body = request.get("body") or {}
            parameters = request_parameters(body)
            context_key = serial(parameters)
            if context_key not in context_lookup:
                context_id = f"{run_id}:c{len(contexts) + 1:04d}"
                context_lookup[context_key] = context_id
                contexts.append({"context_id": context_id, "run_id": run_id,
                                 "parameters": parameters,
                                 "first_source": {"archive": archive, "member": LLM_MEMBER,
                                                  "line": line_no, "pointer": "/request/body"},
                                 "parameter_source_pointers": {
                                     k: "/request/body/" + pointer_part(k) for k in parameters},
                                 "selection_policy": "explicit_request_parameter_allowlist_no_authentication"})
            successful = response.get("status_code") == 200
            record = {"exchange_id": f"{run_id}:e{line_no:04d}", "run_id": run_id,
                      "exchange_line": line_no, "source_archive": archive,
                      "source_member": LLM_MEMBER, "request_timestamp": request.get("timestamp"),
                      "response_timestamp": response.get("timestamp"),
                      "status_code": response.get("status_code"), "duration_ms": row.get("duration_ms"),
                      "api_context_id": context_lookup[context_key],
                      "source": {"archive": archive, "member": LLM_MEMBER,
                                 "line": line_no, "pointer": ""},
                      "field_source_pointers": {
                          "api_context_id": "/request/body", "request_timestamp": "/request/timestamp",
                          "response_timestamp": "/response/timestamp", "status_code": "/response/status_code",
                          "duration_ms": "/duration_ms", "response_metadata": "/response/body",
                          "usage": "/response/body/usage", "choice_metadata": "/response/body/choices"},
                      "request_message_ids": [], "request_input_ids": [], "response_message_ids": [],
                      "response_metadata": {}, "choice_metadata": []}
            for key, target in (("messages", "request_message_ids"), ("input", "request_input_ids")):
                values = body.get(key, [])
                if isinstance(values, str):
                    values = [{"role": "user", "content": values}]
                for i, message in enumerate(values or []):
                    if not isinstance(message, dict):
                        message = {"type": "unstructured_input", "content": message}
                    record[target].append(remember(message, line_no, f"/request/body/{key}/{i}", successful))
            rb = response.get("body")
            if isinstance(rb, dict):
                record["response_metadata"] = {k: safe_api_value(rb[k])
                                               for k in RESPONSE_METADATA_KEYS if k in rb}
                if isinstance(rb.get("usage"), dict):
                    record["usage"] = safe_usage(rb["usage"])
                for i, choice in enumerate(rb.get("choices") or []):
                    message_key = "message" if choice.get("message") else "delta"
                    message = choice.get(message_key)
                    cm = {"choice_index": choice.get("index", i),
                          "finish_reason": choice.get("finish_reason"),
                          "source_pointer": f"/response/body/choices/{i}",
                          "response_message_id": None}
                    fields = choice.get("provider_specific_fields") or {}
                    cm["provider_stop_metadata"] = {
                        k: safe_api_value(fields[k]) for k in ("stop_reason", "finish_reason") if k in fields}
                    if message:
                        mid = remember(message, line_no, f"/response/body/choices/{i}/{message_key}", False)
                        record["response_message_ids"].append(mid)
                        cm["response_message_id"] = mid
                    record["choice_metadata"].append(cm)
                if not rb.get("choices"):
                    # Keep non-chat errors/responses; never include transport headers or key metadata.
                    record["other_response"] = rb
            elif rb is not None:
                record["other_response"] = rb
            exchanges.append(record)

    events = []
    for line_no, event in enumerate(acp, 1):
        tid = event.get("tool_call_id")
        source = {"path": acp_path.relative_to(package).as_posix(), "member": ACP_MEMBER, "line": line_no}
        normalized = assets.normalize(event, source, {"run_id": run_id,
                                      "role": "acp_tool_return", "tool_call_id": tid})
        linked = sorted(calls.get(tid, [])) if tid else []
        exact = [m["message"] for m in messages if m["message_id"] in linked]
        events.append({"event_id": f"{run_id}:a{line_no:04d}", "run_id": run_id,
                       "acp_line": line_no, "source": source, "event": normalized,
                       "exact_llm_message_ids": linked,
                       "tool_parameter_link": "tool_call_id_exact" if linked else "not_matched",
                       "image_links": filename_links([normalized, *exact], image_ids)})
    atif_records = atif_fallback(package, source_run, events)
    jsonl(out / "timeline.jsonl", events)
    jsonl(out / "llm_messages.jsonl", messages)
    jsonl(out / "api_contexts.jsonl", contexts)
    jsonl(out / "llm_exchanges.jsonl", exchanges)
    jsonl(out / "atif_tool_calls.jsonl", atif_records)
    result = {**source_run, "directory": out.relative_to(package).as_posix(),
              "acp_events": len(events), "unique_llm_messages": len(messages),
              "api_contexts": len(contexts),
              "llm_exchanges": len(exchanges),
              "source_exchange_lines": [r["exchange_line"] for r in exchanges],
              "exchange_status_counts": dict(Counter(str(r["status_code"]) for r in exchanges)),
              "api_parameter_policy": "explicit_allowlist_excludes_authentication_headers_and_credentials",
              "acp_tool_events": sum(bool(x.get("tool_call_id")) for x in acp),
              "exact_tool_links": sum(bool(x["exact_llm_message_ids"]) for x in events if x["event"].get("tool_call_id")),
              "exact_atif_tool_links": len(atif_records),
              "unmatched_acp_tool_events": sum(x["tool_parameter_link"] == "not_matched" for x in events if x["event"].get("tool_call_id")),
              "api_prefix_deduplication": "identical_normalized_messages_referenced_once",
              "normalization": ["remove_cache_control", "externalize_structured_image_payloads"],
              "atif": {"archive": archive, "member": "trainer/atif.json", "retained_in_original_archive": True}}
    write(out / "index.json", result)
    return result


def make_windows(records, stream, run_id, source_file, max_chars):
    """Lossless serialized spans. A large event is continued, never silently shortened."""
    windows, current = [], []
    count = 0
    for line, record in enumerate(records, 1):
        text = serial(record)
        rid = next((record[k] for k in ("event_id", "message_id", "tool_record_id", "context_id", "exchange_id")
                    if record.get(k)), None)
        if rid is None:
            raise ValueError("Window record needs a stable source ID")
        start = 0
        while start < len(text):
            capacity = max_chars - count
            end = min(len(text), start + capacity)
            current.append({"record_id": rid, "source_file": source_file, "source_line": line,
                            "char_start": start, "char_end": end, "record_chars": len(text),
                            "continued_from_previous": start > 0, "continues_in_next": end < len(text),
                            "text": text[start:end]})
            count += end - start
            start = end
            if count == max_chars:
                windows.append({"run_id": run_id, "stream": stream, "items": current,
                                "text_chars": count, "attachments": []})
                current, count = [], 0
    if current:
        windows.append({"run_id": run_id, "stream": stream, "items": current,
                        "text_chars": count, "attachments": []})
    return windows


def read_lines(path):
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def write_windows(package, output, runs, image_rows, max_chars):
    asset_ids = [r["asset_id"] for r in image_rows]
    if len(set(asset_ids)) != len(asset_ids) or not asset_ids:
        raise ValueError("Group image assets must have unique nonempty IDs")
    windows = []
    for run in runs:
        for name, stream in record_streams(run):
            file = run["directory"] + "/" + name
            windows.extend(make_windows(read_lines(inside(package, file)), stream, run["run_id"], file, max_chars))
    total = len(windows)
    for index, window in enumerate(windows):
        wid = f"w{index + 1:04d}"
        window.update({"window_id": wid, "batch_id": output.name, "ordinal": index + 1,
                       "window_count": total, "previous_window_id": f"w{index:04d}" if index else None,
                       "next_window_id": f"w{index + 2:04d}" if index + 1 < total else None,
                       "remaining_window_range": [index + 2, total] if index + 1 < total else [],
                       "source_runs_not_interleaved": True, "model_calls": 0,
                       "attachments": list(asset_ids),
                       "image_delivery_policy": IMAGE_DELIVERY_POLICY,
                       "source_assets_stored_once": True,
                       "model_usage_limits_set_by_helper": False,
                       "segmentation_is_not_model_budget": True,
                       "repeated_image_delivery_may_increase_method_cost": True})
        write(output / "windows" / (wid + ".json"), window)
    return [{"window_id": w["window_id"], "path": (output / "windows" / (w["window_id"] + ".json")).relative_to(package).as_posix(),
             "stream": w["stream"], "run_id": w["run_id"], "text_chars": w["text_chars"], "image_count": len(w["attachments"])} for w in windows]


def prepare_group(package, stage, max_chars, refresh=False):
    manifest_path = f"train/batches/batch_{stage:02d}/manifest.json"
    manifest = read(inside(package, manifest_path))
    output = package / "train/diagnosis" / manifest["batch_id"]
    old_window_paths = set()
    if output.exists():
        previous = read(output / "index.json")
        fields = ("run_id", "archive", "path")
        old_sources = [tuple(r[k] for k in fields) for r in previous["runs"]]
        new_sources = [tuple(r[k] for k in fields) for r in manifest["source_runs"]]
        if (not refresh or previous["version"] not in (VERSION, "jpg-diagnosis-preprocessed-v1")
                or previous["batch_id"] != manifest["batch_id"] or old_sources != new_sources):
            raise ValueError("Output exists; use --reuse-existing or --refresh for generated data")
        old_window_paths = {inside(package, w["path"]) for w in previous["windows"]}
        if any(p.parent != output / "windows" for p in old_window_paths):
            raise ValueError("Unexpected old window location")
    output.mkdir(parents=True, exist_ok=True)
    assets = Assets(package, output, manifest["images"])
    runs = [prepare_run(package, output, r, assets, manifest["image_ids"], refresh) for r in manifest["source_runs"]]
    windows = write_windows(package, output, runs, assets.rows, max_chars)
    new_window_paths = {inside(package, w["path"]) for w in windows}
    for path in old_window_paths - new_window_paths:
        path.unlink(missing_ok=True)  # Only previously indexed, generated windows.
    observations = list(assets.observations.values())
    for observation in observations:
        observation.update(filename_links(observation, manifest["image_ids"]))
    jsonl(output / "visual_observations.jsonl", observations)
    write(output / "images.json", {"source_image_count": 20, "assets": assets.rows,
                                   "matching": "exact_bytes_only_no_inferred_crop_identity",
                                   "observations": "visual_observations.jsonl"})
    index = {"version": VERSION, "batch_id": manifest["batch_id"], "stage": stage,
             "source_manifest": manifest_path, "runs": runs,
             "common": {"task": "train/task_prompt.md", "original_skills": "train/skills/original",
                        "feedback_and_outputs": [{"run_id": r["run_id"], "selected_run": r["path"] + "/selected_run"} for r in runs]},
             "images": (output / "images.json").relative_to(package).as_posix(),
             "visual_observations": (output / "visual_observations.jsonl").relative_to(package).as_posix(),
             "windows": windows,
             "window_text_segment_chars": max_chars,
             "model_usage_limits_set_by_helper": False,
             "segmentation_is_not_model_budget": True,
             "diagnosis_and_drafts": "created_by_method_only_use_diagnosis_io_save_stage",
             "source_assets_stored_once": True,
             "image_delivery_policy": IMAGE_DELIVERY_POLICY,
             "repeated_image_delivery_may_increase_method_cost": True,
             "historical_visual_assets": len(assets.rows) - 20,
             "no_semantic_image_association_invented": True, "model_calls": 0}
    write(output / "index.json", index)
    return index


def rewindow_group(package, group, max_chars):
    output = package / "train/diagnosis" / group["batch_id"]
    old_paths = {inside(package, w["path"]) for w in group["windows"]}
    if any(p.parent != output / "windows" for p in old_paths):
        raise ValueError("Unexpected old window location")
    assets = read(inside(package, group["images"]))["assets"]
    windows = write_windows(package, output, group["runs"], assets, max_chars)
    new_paths = {inside(package, w["path"]) for w in windows}
    for path in old_paths - new_paths:
        path.unlink()  # Only previously indexed, generated window files.
    group.pop("all_source_images_attached_once_per_group_in_default_window_sequence", None)
    for old_field in ("window_text_char_budget", "window_image_budget", "budget_unit"):
        group.pop(old_field, None)
    group.update(windows=windows, window_text_segment_chars=max_chars,
                 model_usage_limits_set_by_helper=False, segmentation_is_not_model_budget=True,
                 source_assets_stored_once=True, image_delivery_policy=IMAGE_DELIVERY_POLICY,
                 repeated_image_delivery_may_increase_method_cost=True)
    write(output / "index.json", group)
    return group


def validate_run_api(package, run):
    """Check source order, IDs and references independently of serialized spans."""
    directory = inside(package, run["directory"])
    contexts = read_lines(directory / "api_contexts.jsonl")
    exchanges = read_lines(directory / "llm_exchanges.jsonl")
    messages = read_lines(directory / "llm_messages.jsonl")
    ids = {m["message_id"] for m in messages}
    context_ids = {c["context_id"] for c in contexts}
    assert len(context_ids) == len(contexts) == run["api_contexts"]
    assert len({serial(c["parameters"]) for c in contexts}) == len(contexts)
    for number, context in enumerate(contexts, 1):
        assert context["context_id"] == f"{run['run_id']}:c{number:04d}"
        assert context["run_id"] == run["run_id"]
        assert set(context["parameters"]) <= REQUEST_PARAMETER_KEYS
        assert context["parameters"] == request_parameters(context["parameters"])
        assert context["parameter_source_pointers"] == {
            k: "/request/body/" + pointer_part(k) for k in context["parameters"]}
        assert context["first_source"]["archive"] == run["archive"]
        assert context["first_source"]["member"] == LLM_MEMBER
        assert context["first_source"]["pointer"] == "/request/body"
    lines = [e["exchange_line"] for e in exchanges]
    assert len(exchanges) == run["llm_exchanges"]
    assert lines == run["source_exchange_lines"]
    assert all(isinstance(line, int) and not isinstance(line, bool) and line > 0 for line in lines)
    assert lines == sorted(set(lines))
    assert dict(Counter(str(e["status_code"]) for e in exchanges)) == run["exchange_status_counts"]
    used_contexts = {}
    for exchange in exchanges:
        line = exchange["exchange_line"]
        assert exchange["exchange_id"] == f"{run['run_id']}:e{line:04d}"
        assert exchange["run_id"] == run["run_id"]
        assert exchange["source_archive"] == run["archive"]
        assert exchange["source_member"] == LLM_MEMBER
        assert exchange["source"] == {"archive": run["archive"], "member": LLM_MEMBER,
                                      "line": line, "pointer": ""}
        assert exchange["api_context_id"] in context_ids
        used_contexts.setdefault(exchange["api_context_id"], line)
        status = exchange["status_code"]
        assert status is None or (isinstance(status, int) and not isinstance(status, bool) and 100 <= status <= 599)
        for key in ("request_timestamp", "response_timestamp", "duration_ms"):
            assert key in exchange
        for key in ("request_message_ids", "request_input_ids", "response_message_ids"):
            assert set(exchange[key]) <= ids
        assert set(exchange["response_metadata"]) <= set(RESPONSE_METADATA_KEYS)
        assert exchange.get("usage", {}) == safe_usage(exchange.get("usage", {}))
        choice_messages = []
        for number, choice in enumerate(exchange["choice_metadata"]):
            assert "finish_reason" in choice
            assert choice["source_pointer"] == f"/response/body/choices/{number}"
            if choice["response_message_id"] is not None:
                choice_messages.append(choice["response_message_id"])
        assert choice_messages == exchange["response_message_ids"]
    assert set(used_contexts) == context_ids
    for context in contexts:
        assert context["first_source"]["line"] == used_contexts[context["context_id"]]
    for message in messages:
        assert message["first_source"]["archive"] == run["archive"]
        assert message["first_source"]["member"] == LLM_MEMBER
        assert message["first_source"]["line"] in set(lines)
    return {"api_contexts": len(contexts), "llm_exchanges": len(exchanges),
            "failed_logged_exchanges": sum(e["status_code"] != 200 for e in exchanges)}


def validate_group(package, group):
    """Check actual spans, not just declared counts; missing a middle span must fail."""
    spans = defaultdict(list)
    image_index = read(inside(package, group["images"]))
    expected = [a["asset_id"] for a in image_index["assets"]]
    assert len(expected) == len(set(expected))
    assert group["image_delivery_policy"] == IMAGE_DELIVERY_POLICY
    assert group["source_assets_stored_once"] is True
    for ordinal, row in enumerate(group["windows"], 1):
        window = read(inside(package, row["path"]))
        assert window["ordinal"] == ordinal
        assert sum(len(x["text"]) for x in window["items"]) == window["text_chars"]
        assert window["text_chars"] <= group["window_text_segment_chars"]
        assert window["attachments"] == expected
        assert window["image_delivery_policy"] == IMAGE_DELIVERY_POLICY
        assert row["image_count"] == len(expected)
        for item in window["items"]:
            spans[(item["source_file"], item["source_line"])].append(item)
    covered = 0
    api_counts = Counter()
    for run in group["runs"]:
        api_counts.update(validate_run_api(package, run))
        for filename, _ in record_streams(run):
            path = run["directory"] + "/" + filename
            for line, record in enumerate(read_lines(inside(package, path)), 1):
                pieces = spans.pop((path, line))
                text = serial(record)
                offset = 0
                for piece in pieces:
                    assert piece["char_start"] == offset
                    assert piece["text"] == text[piece["char_start"]:piece["char_end"]]
                    offset = piece["char_end"]
                assert offset == len(text)
                covered += 1
        original = read_lines(inside(package, run["path"] + "/selected_run/trajectory/acp_trajectory.jsonl"))
        assert len(original) == run["acp_events"]
        ids = {m["message_id"] for m in read_lines(inside(package, run["directory"] + "/llm_messages.jsonl"))}
        fallback_ids = {r["tool_record_id"] for r in read_lines(inside(package, run["directory"] + "/atif_tool_calls.jsonl"))}
        for event in read_lines(inside(package, run["directory"] + "/timeline.jsonl")):
            assert set(event["exact_llm_message_ids"]) <= ids
            assert set(event.get("exact_atif_tool_record_ids", [])) <= fallback_ids
    assert not spans
    assert group["windows"]
    for asset in image_index["assets"]:
        image_format(inside(package, asset["path"]).read_bytes())
    return {"batch_id": group["batch_id"], "runs": 3, "windows": len(group["windows"]),
            "covered_records": covered, "all_serialized_record_spans_reconstructed": True,
            "source_images": 20, "historical_visual_assets": group["historical_visual_assets"],
            "attachment_assets": len(expected), "pending_or_missing_record_spans": 0,
            "image_delivery_policy": IMAGE_DELIVERY_POLICY,
            "all_group_assets_attached_to_every_independent_window": True,
            "api_contexts": api_counts["api_contexts"], "llm_exchanges": api_counts["llm_exchanges"],
            "failed_logged_exchanges": api_counts["failed_logged_exchanges"],
            "api_source_sequence_and_references_valid": True,
            "exact_tool_links": sum(r["exact_tool_links"] for r in group["runs"]),
            "exact_atif_tool_links": sum(r.get("exact_atif_tool_links", 0) for r in group["runs"]),
            "unmatched_acp_tool_events": sum(r.get("unmatched_acp_tool_events", 0) for r in group["runs"])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--batch", type=int, choices=range(1, 7))
    parser.add_argument("--window-chars", type=int, default=64000,
                        help="Lossless material segmentation length, not a model token/call/cost limit")
    parser.add_argument("--reuse-existing", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--rewindow", action="store_true", help="Rebuild only windows from prepared records; no archive extraction")
    parser.add_argument("--refresh", action="store_true", help="Refresh generated records in place from the same source archives")
    args = parser.parse_args()
    if args.window_chars < 1:
        parser.error("Material segmentation length must be positive")
    package = args.package.resolve()
    output = package / "train/diagnosis"
    for stage in ([args.batch] if args.batch else range(1, 7)):
        path = output / f"batch_{stage:02d}/index.json"
        if path.exists() and (args.reuse_existing or args.validate_only or args.rewindow) and not args.refresh:
            group = read(path)
            assert group["version"] == VERSION
            if args.rewindow:
                group = rewindow_group(package, group, args.window_chars)
        elif args.validate_only:
            raise ValueError("Prepared group missing")
        else:
            group = prepare_group(package, stage, args.window_chars, args.refresh)
        result = validate_group(package, group)
        print(json.dumps(result), flush=True)
    groups = [read(p) for p in sorted(output.glob("batch_*/index.json"))]
    validation = {"passed": len(groups) == 6, "prepared_batches": len(groups),
                  "groups": [validate_group(package, g) for g in groups],
                  "model_calls": 0, "verifier_calls": 0, "baseline_reruns": 0,
                  "diagnoser_delivery_or_understanding_tested": False}
    if args.validate_only:
        print(json.dumps({"validation_passed": validation["passed"], "read_only": True,
                          "prepared_batches": len(groups), "model_calls": 0}))
        return
    write(output / "validation.json", validation)
    write(output / "index.json", {"version": VERSION, "split": "train", "groups": [
        {"batch_id": g["batch_id"], "stage": g["stage"],
         "path": f"train/diagnosis/{g['batch_id']}/index.json", "windows": len(g["windows"])} for g in groups],
        "source_images": 120, "source_runs": 18, "prepared_batches": len(groups),
        "all_six_batches_prepared": len(groups) == 6, "model_calls": 0,
        "source_assets_stored_once": True, "image_delivery_policy": IMAGE_DELIVERY_POLICY,
        "model_usage_limits_set_by_helper": False, "segmentation_is_not_model_budget": True,
        "repeated_image_delivery_may_increase_method_cost": True,
        "source_experiments_unchanged": True, "consumer": "tools/diagnosis_io.py"})


if __name__ == "__main__":
    main()
