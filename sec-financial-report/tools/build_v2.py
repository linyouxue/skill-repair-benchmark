"""Recompute the frozen seven-question GT from the complete SEC ZIPs."""

import argparse
from collections import Counter, defaultdict
import csv
from decimal import Decimal
import io
import json
from pathlib import Path
import sys
from zipfile import ZipFile

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "evaluation"))
from prepare_task import DEFAULT_ARCHIVES, SPLITS, source_archives

MONTHS = {name: index for index, name in enumerate(
    "JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split(), 1
)}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def table(archive, kind):
    name = next(name for name in archive.namelist() if Path(name).name.upper() == f"{kind}.TSV")
    with archive.open(name) as raw, io.TextIOWrapper(raw, encoding="utf-8-sig", newline="") as stream:
        yield from csv.DictReader(stream, delimiter="\t")


def date_key(date):
    day, month, year = date.upper().split("-")
    return int(year), MONTHS[month], int(day)


def selected_filings(archive, period):
    date = {"1": "31-MAR", "2": "30-JUN", "3": "30-SEP", "4": "31-DEC"}[period[-1]] + "-" + period[:4]
    submissions = {
        row["ACCESSION_NUMBER"]: row for row in table(archive, "SUBMISSION")
        if row["SUBMISSIONTYPE"] == "13F-HR" and row["PERIODOFREPORT"] == date
    }
    best = {}
    for cover in table(archive, "COVERPAGE"):
        acc = cover["ACCESSION_NUMBER"]
        if acc not in submissions or cover["REPORTCALENDARORQUARTER"] != date or cover["ISAMENDMENT"] == "Y":
            continue
        submission = submissions[acc]
        cik = str(int(submission["CIK"])).zfill(10)
        choice = date_key(submission["FILING_DATE"]), acc, cover["FILINGMANAGER_NAME"]
        if cik not in best or choice[:2] < best[cik][:2]:
            best[cik] = choice
    return {acc: cik for cik, (_, acc, _) in best.items()}, {cik: name for cik, (_, _, name) in best.items()}


def summarize_period(path, period, manager_ids, security_ids, classes):
    values = Counter()
    counts = Counter()
    stock_values = {cik: Counter() for cik in manager_ids}
    holders = {cusip: Counter() for cusip in security_ids}
    with ZipFile(path) as archive:
        accession_map, manager_names = selected_filings(archive, period)
        for row in table(archive, "INFOTABLE"):
            cik = accession_map.get(row["ACCESSION_NUMBER"])
            cusip = row["CUSIP"]
            if cik is None or (cik not in manager_ids and cusip not in security_ids):
                continue
            amount = Decimal(row["VALUE"])
            if amount != amount.to_integral_value():
                raise ValueError(f"Noninteger VALUE in {period}")
            value = int(amount)
            if cik in manager_ids:
                values[cik] += value
                if row["TITLEOFCLASS"].lower() in classes:
                    counts[cik] += 1
                    stock_values[cik][cusip] += value
            if cusip in security_ids:
                holders[cusip][cik] += value
    print(f"{period}: complete INFOTABLE scanned", file=sys.stderr, flush=True)
    return values, counts, stock_values, holders, manager_names


def top_two(values):
    ranked = sorted(((value, key) for key, value in values.items() if value > 0), reverse=True)
    if len(ranked) < 2 or ranked[0][0] == ranked[1][0] or (len(ranked) > 2 and ranked[1][0] == ranked[2][0]):
        raise ValueError("Insufficient candidates or ambiguous top two")
    return [key for _, key in ranked[:2]]


def answer(case, old, new):
    cik, cusip = case["manager"]["cik"], case["security"]["cusip"]
    old_values, old_counts, old_stocks, _, _ = old
    values, counts, stocks, holders, names = new
    prior, current = old_stocks[cik], stocks[cik]
    change = {key: current[key] - prior[key] for key in prior.keys() | current.keys()}
    return {
        "q1_answer": old_values[cik],
        "q2_answer": values[cik],
        "q3_answer": old_counts[cik],
        "q4_answer": counts[cik],
        "q5_answer": top_two(change),
        "q6_answer": top_two({key: -value for key, value in change.items()}),
        "q7_answer": [names[holder] for holder in top_two(holders[cusip])],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--archives-dir", type=Path, default=DEFAULT_ARCHIVES)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    data = PACKAGE / "data"
    specs = {split: read_json(data / split / "queries.json") for split in SPLITS}
    managers, securities = defaultdict(set), defaultdict(set)
    for spec in specs.values():
        for case in spec["cases"]:
            cik = case["manager"]["cik"]
            managers[spec["baseline"]].add(cik)
            managers[spec["current"]].add(cik)
            securities[spec["current"]].add(case["security"]["cusip"])
    classes = set(read_json(PACKAGE / "stock_classes.json"))
    archives = source_archives(args.archives_dir, sorted(managers))
    results = {p: summarize_period(path, p, managers[p], securities[p], classes)
               for p, path in archives.items()}
    answers = {
        split: {case["id"]: answer(case, results[spec["baseline"]], results[spec["current"]])
                for case in spec["cases"]}
        for split, spec in specs.items()
    }
    args.output.mkdir(parents=True)
    for split, result in answers.items():
        (args.output / f"{split}.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
        )


if __name__ == "__main__":
    main()
