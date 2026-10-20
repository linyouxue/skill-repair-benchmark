"""Synthetic API/context/window regressions. No network, models or real archives."""

import base64
import copy
import json
import tarfile
import tempfile
import unittest
from pathlib import Path

from prepare_diagnosis import (
    Assets, IMAGE_DELIVERY_POLICY, LLM_MEMBER, VERSION, jsonl, prepare_run,
    read, read_lines, record_streams, safe_api_value, validate_group,
    validate_run_api, write, write_windows,
)


PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jK1sAAAAASUVORK5CYII=")


class APIDiagnosisContracts(unittest.TestCase):
    def fixture(self, root):
        images = []
        for i in range(20):
            p = root / f"train/images/receipt_{i:04d}.png"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(PNG)
            images.append({"asset_id": p.name, "path": p.relative_to(root).as_posix(),
                           "mime_type": "image/png"})
        source = {"run_id": "fixture-run-a01", "path": "train/runs/fixture-run-a01",
                  "archive": "train/archives/fixture-run-a01.tar.xz"}
        call = {"id": "call-fixture", "type": "function", "function": {
            "name": "terminal", "arguments": '{"command":"synthetic-only"}'}}
        prompt = {"role": "user", "content": "Synthetic evidence only."}
        parameters = {"model": "fixture-model", "max_tokens": 64, "stream": False,
                      "tool_choice": "auto", "tools": [{"type": "function", "function": {
                          "name": "terminal", "parameters": {"type": "object", "properties": {
                              "command": {"type": "string"}, "token": {"type": "string"},
                              "password": {"type": "string"}, "headers": {"type": "object"}}}}}],
                      "provider": {"order": ["fixture-provider"], "credentials": "synthetic-secret"},
                      "api_key": "synthetic-secret", "headers": {"Authorization": "synthetic-secret"}}
        rows = []
        for i, status in enumerate((500, 200, 200)):
            body = {**copy.deepcopy(parameters), "messages": [prompt]}
            if i == 2:
                body["max_tokens"] = 128
                body["messages"].append({"role": "tool", "tool_call_id": "call-fixture",
                                         "content": "Synthetic tool result."})
            response = {"error": {"message": "Synthetic upstream failure."}}
            if status == 200:
                response = {"id": f"fixture-response-{i}", "model": "fixture-model",
                            "choices": [{"index": 0, "finish_reason": "length" if i == 1 else "tool_calls",
                                         "message": {"role": "assistant", "content": None,
                                                     "tool_calls": [copy.deepcopy(call)]}}],
                            "usage": {"prompt_tokens": 10, "completion_tokens": 3,
                                      "completion_tokens_details": {"reasoning_tokens": 2},
                                      "credentials": "synthetic-secret", "provider_text": "not-numeric"},
                            "headers": {"Authorization": "synthetic-secret"}}
            rows.append({"request": {"timestamp": f"2026-01-01T00:00:0{i}Z", "body": body,
                                     "headers": {"Authorization": "synthetic-secret"}},
                         "response": {"timestamp": f"2026-01-01T00:00:0{i}Z", "status_code": status,
                                      "body": response}, "duration_ms": i + 1})
        original = root / "synthetic-log.jsonl"
        original.write_text(json.dumps(rows[0]) + "\n\n" + "\n".join(json.dumps(r) for r in rows[1:]) + "\n",
                            encoding="utf-8")
        archive = root / source["archive"]
        archive.parent.mkdir(parents=True)
        with tarfile.open(archive, "w:xz") as tar:
            tar.add(original, arcname=LLM_MEMBER)
        acp = root / source["path"] / "selected_run/trajectory/acp_trajectory.jsonl"
        jsonl(acp, [{"tool_call_id": "call-fixture", "status": "completed"}])
        output = root / "train/diagnosis/batch_01"
        assets = Assets(root, output, images)
        run = prepare_run(root, output, source, assets, [r["asset_id"] for r in images])
        return output, assets, run, rows

    def test_api_contexts_deduplicate_safe_parameters_and_preserve_failure_and_finish_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            _, _, run, source_rows = self.fixture(root)
            directory = root / run["directory"]
            contexts = read_lines(directory / "api_contexts.jsonl")
            exchanges = read_lines(directory / "llm_exchanges.jsonl")
            messages = read_lines(directory / "llm_messages.jsonl")
            self.assertEqual(len(contexts), 2)
            self.assertEqual([e["api_context_id"] for e in exchanges],
                             [contexts[0]["context_id"], contexts[0]["context_id"], contexts[1]["context_id"]])
            self.assertEqual(contexts[0]["parameters"]["tools"], source_rows[0]["request"]["body"]["tools"])
            self.assertEqual(contexts[0]["parameters"]["provider"], {"order": ["fixture-provider"]})
            self.assertEqual(contexts[0]["parameter_source_pointers"]["tools"], "/request/body/tools")
            self.assertEqual([e["exchange_line"] for e in exchanges], [1, 3, 4])
            self.assertEqual([e["status_code"] for e in exchanges], [500, 200, 200])
            self.assertEqual(exchanges[0]["other_response"], source_rows[0]["response"]["body"])
            self.assertEqual(exchanges[1]["choice_metadata"][0]["finish_reason"], "length")
            self.assertEqual(exchanges[2]["choice_metadata"][0]["finish_reason"], "tool_calls")
            self.assertEqual(exchanges[1]["usage"]["completion_tokens_details"], {"reasoning_tokens": 2})
            self.assertNotIn("provider_text", exchanges[1]["usage"])
            self.assertNotIn("synthetic-secret", json.dumps(contexts + exchanges))
            self.assertEqual([e["duration_ms"] for e in exchanges], [1, 2, 3])
            self.assertEqual({m["message"]["role"] for m in messages}, {"user", "assistant", "tool"})
            args = [m["message"]["tool_calls"][0]["function"]["arguments"]
                    for m in messages if m["message"].get("tool_calls")]
            self.assertTrue(args and all(x == '{"command":"synthetic-only"}' for x in args))
            self.assertEqual(validate_run_api(root, run)["failed_logged_exchanges"], 1)

    def test_all_text_windows_contain_every_group_image_and_api_streams(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            output, assets, run, _ = self.fixture(root)
            windows = write_windows(root, output, [run], assets.rows, 256)
            self.assertTrue(windows)
            streams = {w["stream"] for w in windows}
            self.assertTrue({"api_request_contexts", "llm_exchanges", "llm_unique_messages", "acp"} <= streams)
            self.assertNotIn("source_training_image", streams)
            for row in windows:
                window = read(root / row["path"])
                self.assertEqual(window["attachments"], [a["asset_id"] for a in assets.rows])
                self.assertEqual(window["image_delivery_policy"], IMAGE_DELIVERY_POLICY)
                self.assertTrue(all(i["record_id"] for i in window["items"]))
            write(output / "images.json", {"assets": assets.rows})
            group = {"version": VERSION, "batch_id": "batch_01", "runs": [run],
                     "images": "train/diagnosis/batch_01/images.json", "windows": windows,
                     "window_text_segment_chars": 256,
                     "historical_visual_assets": 0, "image_delivery_policy": IMAGE_DELIVERY_POLICY,
                     "source_assets_stored_once": True}
            result = validate_group(root, group)
            self.assertTrue(result["api_source_sequence_and_references_valid"])
            damaged = read(root / windows[0]["path"])
            damaged["attachments"].pop()
            write(root / windows[0]["path"], damaged)
            with self.assertRaises(AssertionError):
                validate_group(root, group)

    def test_more_than_the_old_image_limit_still_includes_every_asset(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            output, assets, run, _ = self.fixture(root)
            extra = [{**assets.rows[0], "asset_id": f"synthetic-observation-{i}"} for i in range(25)]
            images = assets.rows + extra
            windows = write_windows(root, output, [run], images, 64000)
            self.assertTrue(windows)
            for row in windows:
                window = read(root / row["path"])
                self.assertEqual(window["attachments"], [a["asset_id"] for a in images])
                self.assertEqual(len(window["attachments"]), 45)
                self.assertFalse(window["model_usage_limits_set_by_helper"])
                self.assertTrue(window["segmentation_is_not_model_budget"])

    def test_validator_rejects_wrong_context_source_order_status_and_choice_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            _, _, run, _ = self.fixture(root)
            path = root / run["directory"] / "llm_exchanges.jsonl"
            original = read_lines(path)
            edits = (
                lambda r: r[0].update(api_context_id="nonexistent"),
                lambda r: r.reverse(),
                lambda r: r[0].update(status_code=200),
                lambda r: r[1]["source"].update(line=99),
                lambda r: r[1]["choice_metadata"][0].update(response_message_id="wrong-message"),
            )
            for edit in edits:
                damaged = copy.deepcopy(original)
                edit(damaged)
                jsonl(path, damaged)
                with self.assertRaises(AssertionError):
                    validate_run_api(root, run)
            jsonl(path, original)
            self.assertEqual(validate_run_api(root, run)["llm_exchanges"], 3)

    def test_nested_authentication_fields_are_not_retained_in_api_context(self):
        self.assertEqual(safe_api_value({"reasoning": {"effort": "high", "credentials": {"key": "secret"}},
                                         "headers": {"Authorization": "secret"}}),
                         {"reasoning": {"effort": "high"}})


if __name__ == "__main__":
    unittest.main()
