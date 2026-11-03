import ast
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.util.spec_from_file_location("prepare_sec", ROOT / "evaluation/prepare_task.py")
exporter = importlib.util.module_from_spec(loader)
loader.loader.exec_module(exporter)


def git_blob(path):
    digest = hashlib.sha1(f"blob {path.stat().st_size}\0".encode())
    with path.open("rb") as file:
        for block in iter(lambda: file.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class PackageTests(unittest.TestCase):
    def test_original_material_and_gt_unchanged(self):
        source = json.loads((ROOT / "evaluation/source/SOURCES.json").read_text())
        for record in source["original_files"]:
            relative = record["path"]
            if relative in {"verifier/test.sh", "verifier/test_outputs.py"}:
                relative = "evaluation/source/original_verifier/" + Path(relative).name
            self.assertEqual(git_blob(ROOT / relative), record["git_blob"], relative)
        official = json.loads((ROOT / "verifier/expected_output.json").read_text())
        sys.path.insert(0, str(ROOT / "verifier"))
        from score_accuracy import load_reference
        current = load_reference(ROOT / "verifier/expected_output.json")
        self.assertEqual(current["cases"]["original"], official)

    def test_original_evaluated_stock_policy(self):
        tree = ast.parse((ROOT / "environment/skills/13f-analyzer/scripts/one_fund_analysis.py").read_text())
        classes = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                       and any(isinstance(t, ast.Name) and t.id == "title_class_of_stocks" for t in n.targets))
        contract = json.loads((ROOT / "environment/statistical_contract.json").read_text())
        self.assertEqual(contract["stock_title_classes"], classes)

    def test_frozen_counts_disjoint_targets_and_raw_row_hashes(self):
        used_ciks, used_securities, used_periods = {"0001037389", "0001067983"}, {"69608A108"}, {"2025-q2", "2025-q3"}
        for group in ["group_01", "group_02", "group_03"]:
            base = ROOT / "evaluation" / group
            metadata = json.loads((base / "metadata.json").read_text())
            self.assertFalse(used_ciks.intersection(metadata["selected_query_ciks"]))
            self.assertFalse(used_securities.intersection(metadata["selected_security_cusips"]))
            self.assertFalse(used_periods.intersection(metadata["periods"]))
            used_ciks.update(metadata["selected_query_ciks"])
            used_securities.update(metadata["selected_security_cusips"])
            used_periods.update(metadata["periods"])
            self.assertEqual(metadata["query_cases"], 20)
            self.assertFalse(metadata["rank_ties_at_selected_top_or_cutoff"])
            for period, tables in metadata["source_rows"].items():
                for table, stats in tables.items():
                    with gzip.open(base / "inputs/data" / period / (table + ".tsv.gz"), "rb") as file:
                        digest = hashlib.file_digest(file, "sha256").hexdigest()
                    self.assertEqual(digest, stats["uncompressed_sha256"])

    def test_three_native_exports_exclude_scoring_material_from_environment(self):
        with tempfile.TemporaryDirectory() as temp:
            for group in ["group_01", "group_02", "group_03"]:
                output = Path(temp) / group / "sec-financial-report"
                exporter.prepare(group, output)
                env = output / "environment"
                self.assertFalse((output / "diagnosis").exists())
                self.assertFalse((output / "oracle").exists())
                self.assertFalse(list(env.rglob("*reference*")))
                self.assertFalse(list(env.rglob("*expected*")))
                queries = json.loads((env / "queries.json").read_text())
                self.assertEqual(queries["group"], group)
                deployed = json.loads((output / "verifier/expected_output.json").read_text())
                self.assertEqual(deployed["expected_answer_items"], 200)
                actual = Path(temp) / (group + "-reference-fixture.json")
                actual.write_text(json.dumps(deployed["cases"]), encoding="utf-8")
                log = Path(temp) / (group + "-verifier-logs")
                subprocess.run([sys.executable, "-B", str(output / "verifier/native_grade.py"),
                                "--actual", str(actual), "--log-dir", str(log)], check=True, capture_output=True)
                self.assertEqual(float((log / "reward.txt").read_text()), 1)
                self.assertEqual(json.loads((log / "ctrf.json").read_text())["results"]["summary"]["passed"], 200)
                self.assertEqual({p.name for p in (env / "data").iterdir()}, {queries["baseline_period"], queries["current_period"]})
                for original in (ROOT / "environment/skills").rglob("*"):
                    if original.is_file() and "__pycache__" not in original.parts:
                        self.assertEqual(original.read_bytes(), (env / "skills" / original.relative_to(ROOT / "environment/skills")).read_bytes())
                with self.assertRaises(FileExistsError):
                    exporter.prepare(group, output)


if __name__ == "__main__":
    unittest.main()
