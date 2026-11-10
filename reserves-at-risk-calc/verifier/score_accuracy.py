"""Recalculate the Excel output and score the 43 requested numeric fields."""
import argparse
from io import BytesIO
import json
import math
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import time
from xml.etree.ElementTree import ParseError
from zipfile import BadZipFile, ZipFile

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

STEP1 = ("C3", "C4", "C5", "C6")
TABLES = {
    "step2": (11, 11, {"gold_value": 12, "exposure": 13}),
    "step3": (20, 9, {"gold_value": 21, "total_reserves": 23, "rar_percent": 24}),
}
TOTAL = 43


def key(name):
    return " ".join(name.split()).casefold() if isinstance(name, str) else None


def fields(reference):
    if set(reference) != {"step1", *TABLES} or set(reference["step1"]) != set(STEP1):
        raise ValueError("Unexpected reference sections")
    for cell in STEP1:
        yield "step1", cell, reference["step1"][cell], cell
    for step, (header_row, last_column, metrics) in TABLES.items():
        countries = reference[step]
        if len(countries) != last_column - 2 or len({key(name) for name in countries}) != len(countries):
            raise ValueError(f"Invalid reference roster for {step}")
        for name, answers in countries.items():
            if not key(name) or set(answers) != set(metrics):
                raise ValueError(f"Invalid reference fields for {step}")
            for metric, row in metrics.items():
                yield step, f"{name}:{metric}", answers[metric], (key(name), header_row, last_column, row)


def is_number(value):
    return type(value) in (float, int) and math.isfinite(value)


def score(sheet, reference, input_status="ok"):
    cells = tuple(sheet.iter_rows(min_row=1, max_row=24, min_col=3, max_col=11,
                                  values_only=True)) if sheet is not None else ()
    feedback = []
    for step, item, expected, address in fields(reference):
        if not is_number(expected):
            raise ValueError("Invalid numeric reference")
        observed = None
        if cells:
            if step == "step1":
                observed = cells[int(address[1:]) - 1][0]
            else:
                country, header, last_column, row = address
                columns = [col for col in range(last_column - 2)
                           if key(cells[header - 1][col]) == country]
                if len(columns) == 1:
                    observed = cells[row - 1][columns[0]]
        correct = is_number(observed) and math.isclose(observed, expected, rel_tol=1e-6, abs_tol=1e-6)
        feedback.append({"section": step, "item": item, "correct": correct})
    if len(feedback) != TOTAL:
        raise ValueError("Expected exactly 43 scoring items")
    correct = sum(row["correct"] for row in feedback)
    return {"correct_items": correct, "total_items": TOTAL, "accuracy": correct / TOTAL,
            "input_status": input_status, "item_feedback": feedback}


def recalculate_and_score(actual, reference):
    if not actual.is_file():
        return score(None, reference, "missing_workbook")
    try:
        book = read_values(actual)
        has_answer = "Answer" in book.sheetnames
        book.close()
    except (BadZipFile, InvalidFileException, KeyError, ValueError, ParseError):
        return score(None, reference, "invalid_workbook")
    if not has_answer:
        return score(None, reference, "missing_answer_sheet")

    with TemporaryDirectory(prefix="rar-grade-") as directory:
        temp = Path(directory)
        result = subprocess.run(
            ["soffice", f"-env:UserInstallation={(temp / 'profile').as_uri()}",
             "--headless", "--convert-to", "xlsx", "--outdir", str(temp), str(actual.resolve())],
            capture_output=True, text=True, timeout=120, check=False,
        )
        recalculated = temp / actual.name
        if result.returncode or not recalculated.is_file():
            raise RuntimeError(f"LibreOffice recalculation failed: {result.stderr or result.stdout}")
        book = read_values(recalculated)
        try:
            return score(book["Answer"], reference)
        finally:
            book.close()


def read_values(path):
    # Score the stored numbers even when an Excel engine exports incompatible named styles.
    data = BytesIO()
    with ZipFile(path) as original, ZipFile(data, "w") as values:
        for member in original.infolist():
            if member.filename != "xl/styles.xml":
                values.writestr(member, original.read(member))
    data.seek(0)
    return load_workbook(data, read_only=True, data_only=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--actual", type=Path, default=Path("/root/output/rar_result.xlsx"))
    parser.add_argument("--reference", type=Path, default=Path(__file__).with_name("expected_output.json"))
    parser.add_argument("--log-dir", type=Path, default=Path("/logs/verifier"))
    args = parser.parse_args()
    args.log_dir.mkdir(parents=True, exist_ok=True)
    reward = args.log_dir / "reward.txt"
    reward.unlink(missing_ok=True)
    started = int(time.time() * 1000)
    reference = json.loads(args.reference.read_text(encoding="utf-8"))
    report = recalculate_and_score(args.actual, reference)
    tests = [{"name": f"{row['section']}:{row['item']}",
              "status": "passed" if row["correct"] else "failed"} for row in report["item_feedback"]]
    passed = report["correct_items"]
    ctrf = {"results": {"tool": {"name": "rar-answer-accuracy"},
                       "summary": {"tests": TOTAL, "passed": passed, "failed": TOTAL - passed,
                                   "pending": 0, "skipped": 0, "other": 0, "start": started,
                                   "stop": int(time.time() * 1000)},
                       "tests": tests}}
    for name, data in (("accuracy.json", report), ("ctrf.json", ctrf)):
        (args.log_dir / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    reward.write_text(f"{report['accuracy']}\n", encoding="utf-8")
    print(f"{passed}/{TOTAL} ({report['accuracy']:.2%})")


if __name__ == "__main__":
    main()
