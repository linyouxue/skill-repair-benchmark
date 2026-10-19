"""Offline tests for the JPG Excel evaluation entry; synthetic cells only."""

import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from xml.sax.saxutils import escape

import evaluate as evaluator


PACKAGE = Path(__file__).resolve().parents[1]


def fixture_xlsx(path, rows):
    """A tiny synthetic XLSX fixture, never a reconstructed real prediction."""
    cells = []
    for i, row in enumerate(rows, 1):
        values = []
        for j, value in enumerate(row):
            ref = f"{chr(65 + j)}{i}"
            if isinstance(value, str):
                values.append(f'<c r="{ref}" t="inlineStr"><is><t>{escape(value)}</t></is></c>')
            elif value is not None:
                values.append(f'<c r="{ref}"><v>{value}</v></c>')
        cells.append(f'<row r="{i}">' + "".join(values) + "</row>")
    parts = {
        "[Content_Types].xml": '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>',
        "_rels/.rels": '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        "xl/workbook.xml": '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="results" sheetId="1" r:id="rId1"/></sheets></workbook>',
        "xl/_rels/workbook.xml.rels": '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>',
        "xl/worksheets/sheet1.xml": '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>' + "".join(cells) + "</sheetData></worksheet>",
    }
    with zipfile.ZipFile(path, "w") as z:
        for name, content in parts.items():
            z.writestr(name, content)


class EvaluationContracts(unittest.TestCase):
    def score(self, sources):
        labels = {"a.jpg": {"filename": "a.jpg", "ground_truth": {"date": "2000-01-01", "total_amount": "10.00"}, "evaluation_stratum": "no_hint_conflict_detected"},
                  "b.jpg": {"filename": "b.jpg", "ground_truth": {"date": "2000-01-02", "total_amount": "20.00"}, "evaluation_stratum": "literal_rule_ambiguous"}}
        with patch.object(evaluator, "split_data", return_value=(labels, [{"batch_id": "batch_01", "image_ids": ["a.jpg", "b.jpg"]}])):
            return evaluator.evaluate(PACKAGE, "test2", sources, method="synthetic-unit-test")

    def test_missing_file_and_numeric_amount_keep_fixed_denominator(self):
        with tempfile.TemporaryDirectory() as tmp:
            correct = Path(tmp) / "correct.xlsx"
            numeric = Path(tmp) / "numeric.xlsx"
            header = ["filename", "date", "total_amount"]
            fixture_xlsx(correct, [header, ["a.jpg", "2000-01-01", "10.00"], ["b.jpg", "2000-01-02", "20.00"]])
            fixture_xlsx(numeric, [header, ["a.jpg", "2000-01-01", 10], ["b.jpg", "2000-01-02", "20.00"]])
            summary, _ = self.score({(1, "batch_01"): correct, (2, "batch_01"): numeric, (3, "batch_01"): None})
            self.assertEqual([r["field_correct"] for r in summary["per_repeat"]], [4, 3, 0])
            self.assertEqual(summary["all_repeated_observations"]["fields"], 12)
            self.assertFalse(summary["all_planned_excels_provided"])
            self.assertIn("invalid_amount_format_or_type", summary["per_batch"][1]["delivery_issues"])

    def test_missing_row_keeps_other_predictions_and_missing_fields_wrong(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "partial.xlsx"
            fixture_xlsx(p, [["filename", "date", "total_amount"], ["a.jpg", "2000-01-01", "10.00"]])
            summary, observations = self.score({(i, "batch_01"): p for i in (1, 2, 3)})
            self.assertEqual(summary["all_repeated_observations"]["field_correct"], 6)
            self.assertEqual(summary["all_repeated_observations"]["fields"], 12)
            self.assertFalse(next(r for r in observations if r["filename"] == "b.jpg")["prediction_present"])

    def test_unreadable_workbook_scores_empty_predictions(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "broken.xlsx"
            p.write_bytes(b"not an xlsx")
            summary, _ = self.score({(i, "batch_01"): p for i in (1, 2, 3)})
            self.assertEqual(summary["all_repeated_observations"]["field_correct"], 0)
            self.assertEqual(summary["input_files"][0]["delivery_issues"], ["unreadable_workbook"])

    def test_wrong_split_submission_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "inputs.json"
            p.write_text(json.dumps({"split": "train", "rounds": []}))
            with self.assertRaisesRegex(ValueError, "split/layout"):
                evaluator.resolve_inputs("test2", [], inputs=p)

    def test_reports_export_booleans_without_answer_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary, observations = self.score({(i, "batch_01"): None for i in (1, 2, 3)})
            out = Path(tmp) / "report"
            evaluator.write_reports(out, summary, observations)
            text = "".join(p.read_text(encoding="utf-8-sig") for p in out.iterdir())
            self.assertNotIn("2000-01-01", text)
            self.assertNotIn('"ground_truth"', text)
            self.assertEqual(summary["native_verifier_replays"], 0)
            with self.assertRaisesRegex(ValueError, "refusing to overwrite"):
                evaluator.write_reports(out, summary, observations)


if __name__ == "__main__":
    unittest.main()
