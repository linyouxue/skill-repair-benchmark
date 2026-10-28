"""Guards GPT52 source bee9b0df and accuracy packaging from base 29948896."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

PACKAGE = Path(__file__).resolve().parents[1]


def module(name, relative):
    spec = importlib.util.spec_from_file_location(name, PACKAGE / relative)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


PREP = module("task_diagnosis_builder", "tools/prepare_diagnosis.py")
EXPORT = module("task_export", "evaluation/prepare_task.py")
NATIVE = module("task_native", "verifier/native_grade.py")
SCORER = module("task_scorer", "verifier/score_pddl.py" if PACKAGE.name.startswith("pddl") else "verifier/score_flink.py")


class PackageTests(unittest.TestCase):
    """Guards PR #42 native trajectory handoff and item-accuracy-v1."""

    def test_complete_records_and_final_response(self):
        validation = PREP.validate(PACKAGE)
        self.assertTrue(validation["provider_and_tool_references_resolved"])
        index = json.loads((PACKAGE / "diagnosis/index.json").read_text(encoding="utf-8"))
        streams = {s["name"]: s for s in index["streams"]}
        exchanges = PREP.rows(PACKAGE / streams["llm_exchanges"]["path"])
        messages = {r["message_id"]: r for r in PREP.rows(PACKAGE / streams["llm_messages"]["path"])}
        final_ids = exchanges[-1]["response_message_ids"]
        self.assertTrue(final_ids)
        for message_id in final_ids:
            self.assertTrue(messages[message_id]["message"])
        self.assertEqual(len(exchanges), 21 if PACKAGE.name.startswith("pddl") else 40)

    def test_missing_original_artifact_is_not_a_zero_accuracy(self):
        index = json.loads((PACKAGE / "diagnosis/index.json").read_text())
        self.assertEqual(index["source"]["commit"], "bee9b0df5b04a300735e5009f5238f5d5c8aaf61")
        self.assertGreaterEqual(len(index["source"]["verified_git_blobs"]), 7)
        feedback = json.loads((PACKAGE / index["outputs"]["feedback"]).read_text())
        self.assertIsNone(feedback["current_accuracy"])
        self.assertEqual(feedback["original_reward"], 0)
        meta = json.loads((PACKAGE / index["outputs"]["execution_metadata"]).read_text())
        self.assertTrue(meta["execution_ok"])
        self.assertEqual(meta["n_skill_invocations"], 0)
        self.assertEqual(meta["skill_body_preload_evidence"]["pointer"], "/response/body/instructions")


    def test_missing_provider_message_reference_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            shutil.copytree(PACKAGE / "diagnosis", base / "diagnosis")
            index = json.loads((base / "diagnosis/index.json").read_text(encoding="utf-8"))
            stream = next(s for s in index["streams"] if s["name"] == "llm_exchanges")
            path = base / stream["path"]
            exchanges = PREP.rows(path)
            exchanges[-1]["response_message_ids"] = ["missing-final-message"]
            path.write_text("".join(json.dumps(r) + "\n" for r in exchanges), encoding="utf-8")
            with self.assertRaises(ValueError):
                PREP.validate(base)

    def test_all_exports_keep_only_selected_input(self):
        for group in ["group_01", "group_02", "group_03"]:
            with tempfile.TemporaryDirectory() as tmp:
                dst = EXPORT.prepare(group, Path(tmp) / "task")
                self.assertEqual((dst / "task.md").read_bytes(), (PACKAGE / "task.md").read_bytes())
                self.assertFalse((dst / "oracle").exists())
                self.assertFalse((dst / "diagnosis").exists())
                files = [p for p in (dst / "environment").rglob("*") if p.is_file()]
                self.assertFalse(any(p.name in {"expected.json", "negative_ids.json", "metadata.json"} for p in files))
                for p in (PACKAGE / "environment/skills").rglob("*"):
                    if p.is_file():
                        self.assertEqual(p.read_bytes(), (dst / "environment/skills" / p.relative_to(PACKAGE / "environment/skills")).read_bytes())
                if PACKAGE.name.startswith("pddl"):
                    entries = json.loads((dst / "environment/problem.json").read_text())
                    self.assertEqual(len(entries), 2)
                    self.assertEqual(len(list((dst / "environment/airport").iterdir())), 4)
                else:
                    self.assertEqual(len(list((dst / "environment/workspace/data").rglob("*.gz"))), 2)
                    expected = json.loads((dst / "verifier/expected.json").read_text())
                    self.assertEqual(len(expected), {"group_01": 49, "group_02": 53, "group_03": 60}[group])
                with self.assertRaises(FileExistsError):
                    EXPORT.prepare(group, dst)

    def test_partial_score(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            if PACKAGE.name.startswith("pddl"):
                (base / "d.pddl").write_text("(define (domain d) (:requirements :strips) (:predicates (a) (b)) (:action move :parameters () :precondition (a) :effect (and (not (a)) (b))))")
                (base / "p.pddl").write_text("(define (problem p) (:domain d) (:init (a)) (:goal (b)))")
                entries = [{"id": str(n), "domain": "d.pddl", "problem": "p.pddl", "plan_output": f"{n}.txt"} for n in [1, 2]]
                (base / "problem.json").write_text(json.dumps(entries))
                (base / "1.txt").write_text("(move)\n")
                report = SCORER.score(base, base)
                self.assertEqual(report["score"], 0.5)
                self.assertFalse(report["strict_success"])
            else:
                actual = base / "out.txt"
                actual.write_text("(1,3)\n")
                report = SCORER.score(actual, {"1": 3, "2": 5}, {"exclude": ["3", "4"]})
                self.assertEqual(report["score"], 0.75)
                self.assertFalse(report["strict_success"])
                actual.write_text("(1,3)\n(2,5)\n(3,0)\n")
                self.assertEqual(SCORER.score(actual, {"1": 3, "2": 5}, {"exclude": ["3", "4"]})["score"], 0.75)
                self.assertEqual(SCORER.score(base / "missing", {"1": 3}, {"exclude": ["4"]})["score"], 0)

    def test_native_reward_is_fraction_not_bool(self):
        with tempfile.TemporaryDirectory() as tmp:
            before = NATIVE.LOG
            try:
                NATIVE.LOG = Path(tmp)
                NATIVE.finish({"score": 0.5, "accuracy": 0.5}, [{"name": "a", "status": "passed"}, {"name": "b", "status": "failed"}], 0)
                self.assertEqual(float((NATIVE.LOG / "reward.txt").read_text()), 0.5)
                self.assertFalse(json.loads((NATIVE.LOG / "accuracy.json").read_text())["task_passed"])
            finally:
                NATIVE.LOG = before



if __name__ == "__main__":
    unittest.main()
