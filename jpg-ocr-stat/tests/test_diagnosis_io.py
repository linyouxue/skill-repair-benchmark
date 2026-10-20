"""Offline synthetic diagnosis I/O tests for PR #34; no model execution."""

import base64
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("jpg_original_diagnosis_io", ROOT / "tools/diagnosis_io.py")
diagnosis_io = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(diagnosis_io)
SKILLS = ("image-ocr", "openai-vision", "pdf", "video-frame-extraction", "xlsx")


class DiagnosisIO(unittest.TestCase):
    """PR #34: all method-produced files below are explicitly synthetic fixtures."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="jpg-diagnosis-io-synthetic-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.package = self.root / "package"
        self.package.mkdir()
        self.long_text = "BEGIN_FULL_SEGMENT " + "process-image-batch " * 6000 + "END_FULL_SEGMENT"
        self.records = [
            {"record_id": "event-000001", "run_id": "synthetic-run", "kind": "batch_event", "text": self.long_text,
             "related_record": "message-000001"},
            {"record_id": "message-000001", "run_id": "synthetic-run", "kind": "related_message", "text": "SYNTHETIC_RELATED_MESSAGE",
             "related_response": "response-final"},
            {"record_id": "response-final", "run_id": "synthetic-run", "kind": "final_response", "text": "SYNTHETIC_LAST_RESPONSE"},
        ]
        self.write("diagnosis/task_prompt.md", "SYNTHETIC_ORIGINAL_TASK_PROMPT")
        skill_paths = {}
        for name in SKILLS:
            skill_paths[name] = f"environment/skills/{name}/SKILL.md"
            self.write(skill_paths[name], f"# {name}\nSYNTHETIC_ORIGINAL_SKILL_{name}\n")
        self.write("environment/skills/pdf/reference.md", "SYNTHETIC_SUPPORT_KEEP_IDENTICAL")
        self.write("environment/skills/xlsx/LICENSE.txt", "SYNTHETIC_LICENSE_KEEP_IDENTICAL")
        self.asset_bytes = {}
        assets = []
        for index in range(22):
            asset_id = f"{index:03d}.jpg"
            relative = f"environment/workspace/dataset/img/{asset_id}"
            # Only JPEG header bytes, sufficient to audit base64 I/O; no real image.
            payload = b"\xff\xd8\xff\xe0SYNTHETIC_JPEG_" + bytes([index]) + b"\xff\xd9"
            self.asset_bytes[asset_id] = payload
            self.write(relative, payload)
            assets.append({"asset_id": asset_id, "path": relative, "mime_type": "image/jpeg", "kind": "source_task_image"})
        self.write_json("diagnosis/images.json", {"source_image_count": 22, "assets": assets})
        streams = []
        for name, record in zip(("timeline", "messages", "final_response"), self.records):
            path = f"diagnosis/records/{name}.jsonl"
            self.write(path, json.dumps(record) + "\n")
            streams.append({"name": name, "path": path, "records": 1})
        windows = []
        for index, record in enumerate(self.records[:2], 1):
            window_id = f"window_{index:03d}"
            window_path = f"diagnosis/windows/{window_id}.json"
            source = streams[index - 1]["path"]
            serial = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            self.write_json(window_path, {"window_id": window_id, "run_id": "synthetic-run",
                                         "attachments": list(self.asset_bytes),
                                         "text_chars": len(serial),
                                         "items": [{"record_id": record["record_id"], "source_file": source,
                                                    "source_line": 1, "char_start": 0,
                                                    "char_end": len(serial),
                                                    "record_chars": len(serial), "text": serial}]})
            windows.append({"window_id": window_id, "path": window_path})
        outputs = {}
        for key in ("predictions", "feedback", "inventory", "execution_metadata"):
            outputs[key] = f"diagnosis/outputs/{key}.json"
            self.write_json(outputs[key], {"synthetic_not_execution_evidence": True, "marker": f"SYNTHETIC_{key.upper()}"})
        outputs["excel"] = "diagnosis/outputs/stat_ocr.xlsx"
        self.write(outputs["excel"], b"SYNTHETIC_INVENTORY_ONLY_NOT_AN_EXCEL")
        self.index = {"run_id": "synthetic-run", "task_prompt": "diagnosis/task_prompt.md",
                      "source": {"synthetic_not_execution_evidence": True},
                      "skills": skill_paths, "images": "diagnosis/images.json",
                      "outputs": outputs, "streams": streams, "windows": windows}
        self.write_json("diagnosis/index.json", self.index)
        self.write("verifier/forbidden.txt", "SYNTHETIC_FORBIDDEN_GRADER_CONTENT")
        self.write("oracle/forbidden.txt", "SYNTHETIC_FORBIDDEN_ORACLE_CONTENT")
        self.candidate = self.root / "candidate"
        shutil.copytree(self.package / "environment/skills", self.candidate)
        self.diagnosis = self.root / "diagnosis.md"
        self.diagnosis.write_text("Synthetic method diagnosis fixture; no model ran.", encoding="utf-8")
        self.history = self.root / "history.md"
        self.history.write_text("Synthetic cumulative history fixture; no model ran.", encoding="utf-8")
        self.coverage_path = self.root / "coverage.json"
        self.request_record = self.root / "synthetic_request_record.json"
        self.request_record.write_text(json.dumps({"synthetic_not_execution_evidence": True}), encoding="utf-8")

    def write(self, relative, data):
        path = self.package / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, bytes):
            path.write_bytes(data)
        else:
            path.write_text(data, encoding="utf-8")
        return path

    def write_json(self, relative, data):
        return self.write(relative, json.dumps(data, ensure_ascii=False, indent=2) + "\n")

    def coverage(self, rows=None):
        if rows is None:
            rows = [{"window_id": "window_001", "status": "consumed", "request_or_tool_record": str(self.request_record)},
                    {"window_id": "window_002", "status": "skipped", "reason": "Synthetic test intentionally skips second window"}]
        self.coverage_path.write_text(json.dumps(rows), encoding="utf-8")
        return self.coverage_path

    def save(self, state=None):
        return diagnosis_io.save_result(self.package, state or self.root / "state", self.diagnosis,
                                        self.candidate, self.history, self.coverage_path)

    def test_packet_contains_22_real_base64_image_blocks_and_all_text(self):
        """PR #34: prepared I/O includes complete text and actual image bytes."""
        result = diagnosis_io.load_window(self.package, "window_001")
        blocks = [block for message in result["messages"] for block in message["content"]]
        images = [block for block in blocks if block["type"] == "image_url"]
        self.assertEqual(len(images), 22)
        decoded = []
        for block in images:
            prefix, encoded = block["image_url"]["url"].split(",", 1)
            self.assertEqual(prefix, "data:image/jpeg;base64")
            decoded.append(base64.b64decode(encoded, validate=True))
        self.assertCountEqual(decoded, self.asset_bytes.values())
        text = "\n".join(block["text"] for block in blocks if block["type"] == "text")
        self.assertIn(self.long_text, text)
        self.assertIn("SYNTHETIC_RELATED_MESSAGE", text)
        self.assertIn("SYNTHETIC_LAST_RESPONSE", text)
        self.assertEqual(result["resolved_related_record_ids"], ["message-000001", "response-final"])
        self.assertIn("SYNTHETIC_ORIGINAL_TASK_PROMPT", text)
        for name in SKILLS:
            self.assertIn(f"SYNTHETIC_ORIGINAL_SKILL_{name}", text)
        for key in ("predictions", "feedback", "inventory", "execution_metadata"):
            self.assertIn(f"SYNTHETIC_{key.upper()}", text)
        self.assertEqual(result["record_kind"], "prepared_input_not_execution_evidence")
        self.assertEqual(result["model_calls"], 0)
        self.assertFalse(result["actual_model_delivery_verified"])
        self.assertFalse(result["model_usage_limits_set_by_helper"])

    def test_current_draft_and_history_are_available(self):
        """PR #34: later requests can receive method draft and concise history."""
        draft = self.candidate / "image-ocr/SKILL.md"
        draft.write_text("SYNTHETIC_CURRENT_METHOD_DRAFT", encoding="utf-8")
        result = diagnosis_io.load_window(self.package, "window_002", draft_dir=self.candidate, history_file=self.history)
        text = "\n".join(block["text"] for message in result["messages"] for block in message["content"] if block["type"] == "text")
        self.assertIn("SYNTHETIC_CURRENT_METHOD_DRAFT", text)
        self.assertIn(self.history.read_text(encoding="utf-8"), text)

    def test_related_message_and_final_response_can_be_looked_up(self):
        """PR #34: full records remain accessible beyond window excerpts."""
        for record in self.records:
            with self.subTest(record_id=record["record_id"]):
                self.assertEqual(diagnosis_io.load_record(self.package, record["record_id"]), record)

    def test_request_history_keeps_ids_and_supports_explicit_full_expansion(self):
        """PR #34: avoid repeated request bodies without truncating any evidence."""
        historical = [
            {"record_id": "prior-request-message", "kind": "provider_message",
             "text": "SYNTHETIC_PRIOR_MESSAGE_BODY_" * 1000},
            {"record_id": "prior-request-input", "kind": "provider_input",
             "text": "SYNTHETIC_PRIOR_INPUT_BODY_" * 1000},
        ]
        history_path = "diagnosis/records/request_history.jsonl"
        self.write(history_path, "".join(json.dumps(row) + "\n" for row in historical))
        self.index["streams"].append({"name": "request_history", "path": history_path, "records": 2})
        self.write_json("diagnosis/index.json", self.index)
        self.records[0]["request_message_ids"] = [historical[0]["record_id"]]
        self.records[0]["request_input_ids"] = [historical[1]["record_id"]]
        self.write("diagnosis/records/timeline.jsonl", json.dumps(self.records[0]) + "\n")
        window_path = "diagnosis/windows/window_001.json"
        window = json.loads((self.package / window_path).read_text(encoding="utf-8"))
        serial = json.dumps(self.records[0], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        window["items"][0].update({"text": serial, "char_end": len(serial), "record_chars": len(serial)})
        window["text_chars"] = len(serial)
        self.write_json(window_path, window)

        default = diagnosis_io.load_window(self.package, "window_001")
        default_text = "\n".join(block["text"] for message in default["messages"]
                                 for block in message["content"] if block["type"] == "text")
        self.assertFalse(default["full_request_history_expanded"])
        for row in historical:
            self.assertIn(row["record_id"], default_text)
            self.assertNotIn(row["text"], default_text)
            self.assertEqual(diagnosis_io.load_record(self.package, row["record_id"]), row)
        self.assertIn("SYNTHETIC_LAST_RESPONSE", default_text)
        self.assertIn("response-final", default["resolved_related_record_ids"])

        expanded = diagnosis_io.load_window(self.package, "window_001", expand_request_history=True)
        expanded_text = "\n".join(block["text"] for message in expanded["messages"]
                                  for block in message["content"] if block["type"] == "text")
        self.assertTrue(expanded["full_request_history_expanded"])
        for row in historical:
            self.assertIn(row["text"], expanded_text)
            self.assertIn(row["record_id"], expanded["resolved_related_record_ids"])
        self.assertIn("SYNTHETIC_LAST_RESPONSE", expanded_text)

    def test_reader_rejects_grader_oracle_and_outside_paths(self):
        """PR #34: diagnostics never read grading or package-external paths."""
        outside = self.root / "outside.md"
        outside.write_text("SYNTHETIC_OUTSIDE_FILE", encoding="utf-8")
        for path in ("verifier/forbidden.txt", "oracle/forbidden.txt", "../outside.md"):
            with self.subTest(path=path):
                self.index["task_prompt"] = path
                self.write_json("diagnosis/index.json", self.index)
                with self.assertRaises(ValueError):
                    diagnosis_io.load_window(self.package, "window_001")

    def test_record_lookup_rejects_forbidden_stream_path(self):
        """PR #34: on-demand record lookup uses the same path boundary."""
        self.index["streams"][0]["path"] = "verifier/forbidden.txt"
        self.write_json("diagnosis/index.json", self.index)
        with self.assertRaises(ValueError):
            diagnosis_io.load_record(self.package, "event-000001")

    def test_window_fragments_must_match_their_real_source_span(self):
        """PR #34: excerpt text and line coordinates cannot fabricate evidence."""
        relative = "diagnosis/windows/window_001.json"
        original = json.loads((self.package / relative).read_text(encoding="utf-8"))
        for key, replacement in (("text", "fabricated synthetic text"), ("source_line", 2), ("char_end", 1)):
            with self.subTest(key=key):
                window = json.loads(json.dumps(original))
                window["items"][0][key] = replacement
                self.write_json(relative, window)
                with self.assertRaises(ValueError):
                    diagnosis_io.load_window(self.package, "window_001")

    def test_coverage_needs_every_window_and_explicit_request_or_skip_reason(self):
        """PR #34: omitted/duplicate windows and unsubstantiated coverage fail."""
        invalid = [[], [{"window_id": "window_001", "status": "consumed", "request_or_tool_record": str(self.request_record)}],
                   [{"window_id": "window_001", "status": "consumed"}, {"window_id": "window_002", "status": "skipped", "reason": "synthetic"}],
                   [{"window_id": "window_001", "status": "skipped", "reason": "synthetic"}, {"window_id": "window_002", "status": "skipped"}],
                   [{"window_id": "window_001", "status": "skipped", "reason": "synthetic"}] * 2]
        for rows in invalid:
            with self.subTest(rows=rows):
                self.coverage(rows)
                with self.assertRaises(ValueError):
                    self.save()

    def test_only_existing_five_skill_documents_may_change(self):
        """PR #34: allowed edits are existing SKILL.md bodies, not support files."""
        self.coverage()
        (self.candidate / "image-ocr/SKILL.md").write_text("Synthetic repaired skill; test fixture only.", encoding="utf-8")
        receipt = self.save()
        self.assertIsInstance(receipt, dict)
        self.assertTrue((self.root / "state").is_dir())

    def test_support_file_changes_are_rejected(self):
        """PR #34: support files must remain byte-identical in candidate bundles."""
        self.coverage()
        (self.candidate / "pdf/reference.md").write_text("Synthetic forbidden support edit", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.save()

    def test_new_helpers_or_missing_bundle_files_are_rejected(self):
        """PR #34: candidates cannot add helpers or remove original bundle files."""
        self.coverage()
        extra = self.candidate / "extra.py"
        extra.write_text("synthetic", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.save()
        extra.unlink()
        (self.candidate / "xlsx/LICENSE.txt").unlink()
        with self.assertRaises(ValueError):
            self.save()

    def test_result_directory_inside_candidate_is_rejected_before_writes(self):
        """PR #34: direct and normalized candidate descendants cannot be save targets."""
        self.coverage()
        before_files = {p.relative_to(self.candidate): p.read_bytes()
                        for p in self.candidate.rglob("*") if p.is_file()}
        before_directories = {p.relative_to(self.candidate)
                              for p in self.candidate.rglob("*") if p.is_dir()}
        targets = (self.candidate / "result-direct",
                   self.candidate / "image-ocr" / ".." / "result-normalized")
        for target in targets:
            with self.subTest(target=target):
                self.assertTrue(target.resolve().is_relative_to(self.candidate.resolve()))
                with patch.object(diagnosis_io.shutil, "copytree",
                                  side_effect=AssertionError("Saving inside candidate reached copytree")) as copytree:
                    with self.assertRaises(ValueError):
                        self.save(target)
                    copytree.assert_not_called()
                self.assertFalse(target.resolve().exists())
                self.assertEqual(before_files, {p.relative_to(self.candidate): p.read_bytes()
                                                for p in self.candidate.rglob("*") if p.is_file()})
                self.assertEqual(before_directories, {p.relative_to(self.candidate)
                                                      for p in self.candidate.rglob("*") if p.is_dir()})

    def test_results_stay_outside_package_and_saved_results_are_not_overwritten(self):
        """PR #34: save is package-external and immutable after first write."""
        self.coverage()
        with self.assertRaises(ValueError):
            self.save(self.package / "method-state")
        self.save()
        state = self.root / "state"
        original = {p.relative_to(state): p.read_bytes() for p in state.rglob("*") if p.is_file()}
        self.diagnosis.write_text("Synthetic second diagnosis must not overwrite", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.save()
        self.assertEqual(original, {p.relative_to(state): p.read_bytes() for p in state.rglob("*") if p.is_file()})


if __name__ == "__main__":
    unittest.main()
