"""Report each frozen receipt's two date/amount checks individually."""

import json
import os
from pathlib import Path

from score_accuracy import score


ACTUAL = Path(os.environ.get("JPG_OCR_ACTUAL_PATH", "/app/workspace/stat_ocr.xlsx"))
ORACLE = Path(os.environ.get("JPG_OCR_ORACLE_PATH", str(Path(__file__).with_name("stat_oracle.xlsx"))))
REPORT_PATH = Path(os.environ.get("JPG_OCR_REPORT_PATH", "/logs/verifier/accuracy.json"))
REPORT = score(ACTUAL, ORACLE)
REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
REPORT_PATH.write_text(json.dumps(REPORT, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def _field_test(row, field, name):
    def check():
        """Guards the field-accuracy contract introduced in commit 2e1a410."""
        assert row[f"{field}_correct"], f"{row['filename']}: {field} incorrect or missing"

    check.__name__ = name
    check.__qualname__ = name
    return check


# pytest-json-ctrf 0.3.5 treats parametrizations as retries and merges their
# results. Distinct function names preserve every frozen field outcome.
for index, row in enumerate(REPORT["field_feedback"]):
    for field in ("date", "amount"):
        name = f"test_receipt_{index:02d}_{field}"
        globals()[name] = _field_test(row, field, name)
