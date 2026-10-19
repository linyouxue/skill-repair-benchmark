"""Offline contract tests for the JPG diagnosis preprocessing change; no model requests."""

import base64
import json
import shutil
import tarfile
import tempfile
import unittest
from pathlib import Path

from diagnosis_io import load_window, save_stage, training_path, validate_bundle
from prepare_diagnosis import Assets, atif_fallback, filename_links, make_windows, serial, write


PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jK1sAAAAASUVORK5CYII=")


class DiagnosisContracts(unittest.TestCase):
    def test_large_step_and_middle_steps_have_exact_contiguous_spans(self):
        records = [{"event_id": f"r:a{i}", "text": str(i) * (1000 if i == 2 else 40)} for i in range(5)]
        windows = make_windows(records, "acp", "r", "train/e.jsonl", 256)
        self.assertTrue(any(p["continues_in_next"] for w in windows for p in w["items"]))
        for line, record in enumerate(records, 1):
            pieces = [p for w in windows for p in w["items"] if p["source_line"] == line]
            self.assertEqual("".join(p["text"] for p in pieces), serial(record))
            self.assertEqual([p["char_start"] for p in pieces[1:]], [p["char_end"] for p in pieces[:-1]])

    def test_batch_script_does_not_invent_single_image_processing(self):
        links = filename_links({"command": "for p in glob('dataset/img/*.jpg'): ocr(p)"}, ["a.jpg", "b.jpg"])
        self.assertEqual(links["association_scope"], "batch_context_only")
        self.assertEqual(links["explicit_filename_mentions"], [])
        self.assertTrue(links["each_image_processed_or_seen_not_proven_by_mentions"])

    def test_same_original_image_is_not_published_as_a_new_crop(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image = root / "train/images/a.jpg"
            image.parent.mkdir(parents=True)
            image.write_bytes(PNG)
            pool = Assets(root, root / "train/diagnosis/batch_01", [{"asset_id": "a", "path": "train/images/a.jpg", "mime_type": "image/png"}])
            url = "data:image/png;base64," + base64.b64encode(PNG).decode()
            source = {"member": "trajectory/llm_trajectory.jsonl", "line": 1}
            owner = {"run_id": "r", "role": "tool", "tool_call_id": "t"}
            block = pool.normalize({"type": "image_url", "image_url": {"url": url, "detail": "high"}}, source, owner, True)
            self.assertEqual(block["asset_id"], "a")
            self.assertEqual(len(pool.rows), 1)
            self.assertEqual(block["original_image_block_metadata"]["image_url"]["detail"], "high")
            self.assertTrue(next(iter(pool.observations.values()))["included_in_successful_logged_request"])

    def test_atif_fallback_uses_exact_ids_and_does_not_invent_a_provider_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "atif.json"
            write(source, {"steps": [{"tool_calls": [{"tool_call_id": "real-id", "function_name": "terminal", "arguments": {"command": "synthetic-noop"}}]}]})
            archive = root / "train/archives/r.tar.xz"
            archive.parent.mkdir(parents=True)
            with tarfile.open(archive, "w:xz") as tar:
                tar.add(source, arcname="trainer/atif.json")
            event = {"event": {"tool_call_id": "real-id"}, "exact_llm_message_ids": [], "tool_parameter_link": "not_matched", "image_links": {"batch_image_ids": ["a.jpg"]}}
            records = atif_fallback(root, {"archive": "train/archives/r.tar.xz", "run_id": "r"}, [event])
            self.assertEqual(event["tool_parameter_link"], "atif_tool_call_id_exact")
            self.assertTrue(records[0]["not_a_reconstructed_provider_exchange"])
            event["event"]["tool_call_id"] = "different-id"
            event["tool_parameter_link"] = "not_matched"
            self.assertEqual(atif_fallback(root, {"archive": "train/archives/r.tar.xz", "run_id": "r"}, [event]), [])
            self.assertEqual(event["tool_parameter_link"], "not_matched")

    def fixture(self, root):
        for name in ("image-ocr", "openai-vision", "pdf", "video-frame-extraction", "xlsx"):
            p = root / "train/skills/original" / name / "SKILL.md"
            p.parent.mkdir(parents=True)
            p.write_text("Original skill " + name, encoding="utf-8")
        (root / "train/skills/original/pdf/helper.py").write_text("original helper", encoding="utf-8")
        (root / "train/task_prompt.md").write_text("Extract dates and totals.", encoding="utf-8")
        p = root / "train/images/a.png"
        p.parent.mkdir(parents=True)
        p.write_bytes(PNG)
        runs = []
        for i in range(3):
            selected = f"train/runs/r{i}/selected_run"
            for name in ("allowed_execution_metadata.json", "allowed_feedback.json", "agent_predictions.json", "output_inventory.json"):
                write(root / selected / name, {})
            runs.append({"run_id": f"r{i}", "selected_run": selected})
        prefix = "train/diagnosis/batch_01"
        write(root / prefix / "images.json", {"assets": [{"asset_id": "a", "path": "train/images/a.png", "mime_type": "image/png", "kind": "source_training_image"}]})
        write(root / prefix / "windows/w0001.json", {"window_id": "w0001", "attachments": ["a"], "items": [], "ordinal": 1})
        group = {"batch_id": "batch_01", "runs": [{"run_id": f"r{i}"} for i in range(3)],
                 "images": prefix + "/images.json", "windows": [{"window_id": "w0001", "path": prefix + "/windows/w0001.json"}],
                 "common": {"task": "train/task_prompt.md", "feedback_and_outputs": runs}}
        write(root / prefix / "index.json", group)

    def test_packet_has_real_image_block_and_budget_failure_does_not_truncate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            packet = load_window(root, 1, "w0001")
            parts = packet["messages"][0]["content"]
            self.assertEqual(parts[1]["type"], "image_url")
            self.assertEqual(base64.b64decode(parts[1]["image_url"]["url"].split(",", 1)[1]), PNG)
            self.assertFalse(packet["actual_model_delivery_verified"])
            with self.assertRaisesRegex(ValueError, "no text was truncated"):
                load_window(root, 1, "w0001", max_text_chars=10)

    def test_evaluation_inputs_cannot_enter_window_reader(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(ValueError):
                training_path(root, "evaluation_only/test2/annotations.json")
            with self.assertRaises(ValueError):
                training_path(root, "../outside.json")

    def test_changed_support_script_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root)
            original = root / "train/skills/original"
            candidate = root / "candidate"
            shutil.copytree(original, candidate)
            (candidate / "pdf/helper.py").write_text("changed", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Support file changed"):
                validate_bundle(original, candidate)

    def test_save_real_stage_requires_coverage_then_supplies_next_stage_draft(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "package"
            self.fixture(root)
            candidate = Path(tmp) / "candidate"
            shutil.copytree(root / "train/skills/original", candidate)
            (candidate / "image-ocr/SKILL.md").write_text("Fixture method revision", encoding="utf-8")
            diagnosis = Path(tmp) / "diagnosis.md"
            history = Path(tmp) / "history.md"
            diagnosis.write_text("Synthetic test diagnosis, not an executed model.", encoding="utf-8")
            history.write_text("Synthetic cumulative record.", encoding="utf-8")
            coverage = Path(tmp) / "coverage.json"
            write(coverage, [{"window_id": "w0001", "status": "skipped"}])
            state = Path(tmp) / "method"
            with self.assertRaisesRegex(ValueError, "explicit reason"):
                save_stage(root, 1, state, diagnosis, candidate, history, coverage)
            write(coverage, [{"window_id": "w0001", "status": "consumed", "request_or_tool_record": "synthetic-fixture-only"}])
            result = save_stage(root, 1, state, diagnosis, candidate, history, coverage)
            self.assertEqual(result["changed_skill_documents"], ["image-ocr/SKILL.md"])
            self.assertEqual(result["model_calls_by_helper"], 0)
            self.assertEqual((state / "stage_01/skills/image-ocr/SKILL.md").read_text(), "Fixture method revision")
            with self.assertRaisesRegex(ValueError, "already saved"):
                save_stage(root, 1, state, diagnosis, candidate, history, coverage)


if __name__ == "__main__":
    unittest.main()
