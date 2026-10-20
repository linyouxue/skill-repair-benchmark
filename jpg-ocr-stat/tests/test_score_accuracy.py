"""Synthetic offline checks for data/jpg-ocr-stat-accuracy-20261020.

No real oracle values or past model predictions are embedded in these tests.
"""

import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "verifier"))

import score_accuracy as scorer


def fixture_xlsx(path, rows, sheet="results"):
    """Write minimal synthetic OOXML fixtures, never real output workbooks."""
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
        "xl/workbook.xml": '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="' + escape(sheet) + '" sheetId="1" r:id="rId1"/></sheets></workbook>',
        "xl/_rels/workbook.xml.rels": '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>',
        "xl/worksheets/sheet1.xml": '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>' + "".join(cells) + "</sheetData></worksheet>",
    }
    with zipfile.ZipFile(path, "w") as z:
        for name, content in parts.items():
            z.writestr(name, content)


class ExactFieldAccuracy(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="jpg-accuracy-synthetic-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.rows = [list(scorer.HEADER)] + [[f"synthetic_{i:02d}.jpg", "2000-01-01", "10.00"] for i in range(22)]
        self.oracle = self.root / "oracle.xlsx"
        fixture_xlsx(self.oracle, self.rows)
        self.actual = self.root / "actual.xlsx"

    def run_score(self, rows=None, sheet="results"):
        if rows is not None:
            fixture_xlsx(self.actual, rows, sheet)
        result = scorer.score(self.actual, self.oracle)
        self.assertEqual(result["all_receipts"]["fields"], 44)
        return result

    def test_perfect_and_one_wrong_field_give_continuous_reward(self):
        self.assertEqual(self.run_score(self.rows)["reward"], 1.0)
        self.rows[1][2] = "11.00"
        result = self.run_score(self.rows)
        self.assertEqual(result["reward"], 43 / 44)
        self.assertEqual(result["all_receipts"]["date_correct"], 22)
        self.assertEqual(result["all_receipts"]["amount_correct"], 21)
        self.assertEqual(result["all_receipts"]["receipt_joint_correct"], 21)
        self.assertEqual(result["delivery_issues"], [])

    def test_missing_file_and_unreadable_file_score_zero(self):
        result = self.run_score()
        self.assertEqual(result["reward"], 0)
        self.assertEqual(result["delivery_issues"], ["output_missing"])
        self.actual.write_bytes(b"not a workbook")
        result = self.run_score()
        self.assertEqual(result["reward"], 0)
        self.assertEqual(result["delivery_issues"], ["unreadable_workbook"])

    def test_missing_row_keeps_fixed_denominator(self):
        result = self.run_score(self.rows[:-1])
        self.assertEqual(result["reward"], 42 / 44)
        self.assertEqual(result["field_feedback"][-1]["prediction_present"], False)
        self.assertIn("wrong_row_count", result["delivery_issues"])

    def test_null_fields_are_wrong_but_permitted_fallback(self):
        self.rows[1][1:] = [None, None]
        result = self.run_score(self.rows)
        self.assertEqual(result["reward"], 42 / 44)
        self.assertEqual(result["delivery_issues"], [])

    def test_numeric_amount_is_not_coerced_into_two_decimal_string(self):
        self.rows[1][2] = 10
        result = self.run_score(self.rows)
        self.assertEqual(result["reward"], 43 / 44)
        self.assertIn("invalid_amount_format_or_type", result["delivery_issues"])

    def test_wrong_sheet_and_header_score_empty_predictions(self):
        result = self.run_score(self.rows, "other")
        self.assertEqual(result["reward"], 0)
        self.assertEqual(result["delivery_issues"], ["invalid_sheets"])
        self.rows[0][2] = "amount"
        result = self.run_score(self.rows)
        self.assertEqual(result["reward"], 0)
        self.assertEqual(result["delivery_issues"], ["invalid_header_or_columns"])

    def test_duplicate_filename_uses_later_prediction_and_marks_invalid(self):
        self.rows.append([self.rows[1][0], "2000-01-01", "11.00"])
        result = self.run_score(self.rows)
        self.assertEqual(result["reward"], 43 / 44)
        self.assertIn("duplicate_filenames", result["delivery_issues"])
        self.assertEqual(result["delivery_status"], "invalid")

    def test_wrong_order_and_extra_receipt_do_not_change_field_values(self):
        self.rows[1:] = reversed(self.rows[1:])
        result = self.run_score(self.rows)
        self.assertEqual(result["reward"], 1.0)
        self.assertIn("wrong_filename_order", result["delivery_issues"])
        self.rows.append(["extra.jpg", "2000-01-01", "10.00"])
        result = self.run_score(self.rows)
        self.assertEqual(result["reward"], 1.0)
        self.assertIn("missing_or_unexpected_filenames", result["delivery_issues"])

    def test_invalid_oracle_is_infrastructure_error_without_values(self):
        fixture_xlsx(self.oracle, self.rows[:-1])
        with self.assertRaisesRegex(RuntimeError, "Frozen oracle unavailable or invalid") as caught:
            scorer.score(self.actual, self.oracle)
        self.assertNotIn("2000-01-01", str(caught.exception))
        self.assertNotIn("10.00", str(caught.exception))

    def test_cli_writes_boolean_report_without_answer_or_prediction_values(self):
        fixture_xlsx(self.actual, self.rows)
        report = self.root / "report.json"
        result = subprocess.run([sys.executable, str(Path(scorer.__file__)), "--actual", str(self.actual),
                                 "--oracle", str(self.oracle), "--report", str(report)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        text = report.read_text(encoding="utf-8")
        self.assertNotIn("2000-01-01", text)
        self.assertNotIn("10.00", text)
        data = json.loads(text)
        self.assertEqual(data["reward"], 1)
        self.assertEqual(len(data["field_feedback"]), 22)
        self.assertFalse(data["answer_values_exported"])


if __name__ == "__main__":
    unittest.main()
