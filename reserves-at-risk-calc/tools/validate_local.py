"""Check the frozen inputs and run the native Docker verifier against formula workbooks."""
import argparse
from contextlib import closing
import json
import math
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evaluation"))
from prepare_task import YEARS, prepare, task_prompt


def check_workbooks(split, inputs, snapshot):
    panel = snapshot["panels"][split]
    expected_prices = snapshot["prices_usd_per_troy_ounce"][str(panel["year"])]
    expected_months = [period[:4] + "M" + str(int(period[5:])) for period in expected_prices]
    with closing(load_workbook(inputs / "gold-prices.xlsx", read_only=True, data_only=True)) as raw:
        rows = list(raw["External"].values)
        assert len(rows) == 15 and rows[0] == ("Commodity", "PGOLD"), split
        assert [row[0] for row in rows[2:]] == expected_months, split
        assert all(math.isclose(row[1], float(price), rel_tol=1e-12)
                   for row, price in zip(rows[2:], expected_prices.values())), split

    template = ROOT / "diagnosis/inputs/test-rar.xlsx"
    with closing(load_workbook(inputs / "test-rar.xlsx", read_only=True)) as book, \
            closing(load_workbook(template, read_only=True)) as original:
        assert book.sheetnames == original.sheetnames, split
        expected_answer = original["Answer"].iter_rows(max_row=24, max_col=11, values_only=True)
        actual_answer = book["Answer"].iter_rows(max_row=24, max_col=11, values_only=True)
        assert list(actual_answer) == list(expected_answer), split
        gold = list(book["Gold price"].iter_rows(min_row=2, max_row=430, max_col=5, values_only=True))
        assert [r[0] for r in gold[:13]] == expected_months, split
        assert not any(any(value is not None for value in row[1:]) for row in gold[:13]), split
        assert not any(any(value is not None for value in row) for row in gold[13:]), split
        for tab, field in (("Value", "value"), ("Volume", "volume"), ("Total Reserves", "total")):
            rows = list(book[tab].iter_rows(max_row=18, max_col=18, values_only=True))
            assert all(all(v is None for v in row) for row in rows[9:17]), (split, tab)
            assert rows[17][:2] == (str(panel["year"]), None), (split, tab)
            data = {header.split(":")[0]: value for header, value in zip(rows[0][2:], rows[17][2:])
                    if header is not None}
            expected = {row["country"]: float(row[field]) for row in panel["countries"] if field in row}
            assert data.keys() == expected.keys(), (split, tab)
            assert all(math.isclose(data[name], value, rel_tol=1e-12)
                       for name, value in expected.items()), (split, tab)


def docker(*args):
    result = subprocess.run(["docker", *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode:
        raise RuntimeError(f"Docker exited {result.returncode}\n{result.stdout}\n{result.stderr}")
    return result.stdout


def grade(image, task, workbook, logs, expected):
    logs.mkdir()
    command = ["run", "--rm", "--network", "none",
               "--mount", f"type=bind,source={task / 'verifier'},target=/verifier,readonly",
               "--mount", f"type=bind,source={logs},target=/logs/verifier"]
    if workbook is not None:
        command += ["--mount", f"type=bind,source={workbook},target=/root/output/rar_result.xlsx,readonly"]
    docker(*command, image, "bash", "/verifier/test.sh")
    report = json.loads((logs / "accuracy.json").read_text(encoding="utf-8"))
    ctrf = json.loads((logs / "ctrf.json").read_text(encoding="utf-8"))["results"]["summary"]
    assert report["correct_items"] == ctrf["passed"] == expected, (logs.name, report)
    assert report["total_items"] == ctrf["tests"] == 43, logs.name
    reward = float((logs / "reward.txt").read_text(encoding="utf-8"))
    assert reward == expected / 43, logs.name
    print(f"{logs.name}: {expected}/43", flush=True)
    return {"correct": expected, "total": 43, "accuracy": reward, "status": report["input_status"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", required=True, type=Path)
    parser.add_argument("--scratch", required=True, type=Path, help="New validation work directory")
    args = parser.parse_args()
    fixtures, scratch = args.fixtures.resolve(), args.scratch.resolve()
    scratch.mkdir()
    snapshot = json.loads((ROOT / "source/snapshot.json").read_text(encoding="utf-8"))
    assert (ROOT / "task.md").read_text(encoding="utf-8") == task_prompt(YEARS["train"])
    roster = {name: [c["code"] for c in panel["countries"]] for name, panel in snapshot["panels"].items()}
    assert roster["train"] == roster["group_02"] and roster["group_01"] == roster["group_03"]
    assert not set(roster["train"]) & set(roster["group_01"])
    assert YEARS == {name: row["year"] for name, row in snapshot["panels"].items()}
    assert not set(snapshot["prices_usd_per_troy_ounce"]["2023"]) & set(snapshot["prices_usd_per_troy_ounce"]["2025"])

    results = {}
    image = f"codex-rar-validation:{uuid4().hex[:12]}"
    docker("build", "-t", image, "-f", str(ROOT / "environment/Verifier.Dockerfile"),
           str(ROOT / "environment"))
    try:
        for split in YEARS:
            task = prepare(split, scratch / split / "reserves-at-risk-calc")
            check_workbooks(split, task / "environment", snapshot)
            results[split] = grade(image, task, fixtures / f"{split}.xlsx", scratch / f"{split}-logs", 43)
            if split == "train":
                results["one_wrong"] = grade(image, task, fixtures / "one-wrong.xlsx", scratch / "one-wrong-logs", 42)
                results["missing"] = grade(image, task, None, scratch / "missing-logs", 0)
    finally:
        docker("image", "rm", image)
    output = ROOT / "validation/local_results.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps({"runtime": "Docker with network disabled for verification",
                                  "reference": "Decimal from IMF observations",
                                  "crosscheck": "LibreOffice formula recalculation from exported workbooks",
                                  "runs": results}, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
