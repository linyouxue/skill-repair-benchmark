"""Independently recompute SEC v2 answers from the six complete input ZIPs."""

import argparse
import ast
from collections import defaultdict
import csv
from datetime import datetime
import io
import json
from pathlib import Path
import sqlite3
import sys
from tempfile import TemporaryDirectory
from zipfile import ZipFile

PACKAGE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(PACKAGE / "verifier"), str(PACKAGE / "evaluation")]
from prepare_task import DEFAULT_ARCHIVES, source_archives
from score_accuracy import load_reference, score


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def rows(archive, kind):
    names = [name for name in archive.namelist() if Path(name).name.upper() == f"{kind}.TSV"]
    if len(names) != 1:
        raise ValueError(f"Expected one {kind} table")
    with archive.open(names[0]) as raw, io.TextIOWrapper(raw, encoding="utf-8-sig", newline="") as stream:
        yield from csv.DictReader(stream, delimiter="\t")


def verify_classes():
    classes = read_json(PACKAGE / "stock_classes.json")
    assert len(classes) == len(set(classes)) == 25
    for script in ("13f-analyzer/scripts/one_fund_analysis.py",
                   "fuzzy-name-search/scripts/search_stock_cusip.py"):
        tree = ast.parse((PACKAGE / "environment/skills" / script).read_text(encoding="utf-8"))
        assignment = next(node for node in tree.body if isinstance(node, ast.Assign)
                          and any(getattr(t, "id", None) == "title_class_of_stocks" for t in node.targets))
        assert ast.literal_eval(assignment.value) == classes
    return classes


def period_date(period):
    end = {"1": "31-MAR", "2": "30-JUN", "3": "30-SEP", "4": "31-DEC"}
    return f"{end[period[-1]]}-{period[:4]}"


def normalized_name(name):
    return " ".join(name.casefold().split())


def load_period(db, archive, period, manager_ids, security_ids, lookup_keys, classes):
    date = period_date(period)
    candidates = {}
    for r in rows(archive, "SUBMISSION"):
        if r["SUBMISSIONTYPE"] == "13F-HR" and r["PERIODOFREPORT"] == date:
            candidates[r["ACCESSION_NUMBER"]] = (
                str(int(r["CIK"])).zfill(10), datetime.strptime(r["FILING_DATE"], "%d-%b-%Y")
            )
    chosen = {}
    for r in rows(archive, "COVERPAGE"):
        acc = r["ACCESSION_NUMBER"]
        if acc not in candidates or r["REPORTCALENDARORQUARTER"] != date or r["ISAMENDMENT"] == "Y":
            continue
        cik, filed = candidates[acc]
        entry = filed, acc, r["FILINGMANAGER_NAME"]
        if cik not in chosen or entry[:2] < chosen[cik][:2]:
            chosen[cik] = entry
    db.executemany("INSERT INTO filings VALUES (?, ?, ?, ?)",
                   ((period, acc, cik, name) for cik, (_, acc, name) in chosen.items()))
    eligible = {acc: cik for cik, (_, acc, _) in chosen.items()}
    issuer_matches = defaultdict(set)
    scanned = 0

    def relevant_rows():
        nonlocal scanned
        for row in rows(archive, "INFOTABLE"):
            scanned += 1
            acc, cusip = row["ACCESSION_NUMBER"], row["CUSIP"]
            if acc not in eligible:
                continue
            if lookup_keys and not row["PUTCALL"] and row["TITLEOFCLASS"].lower() in classes:
                key = (normalized_name(row["NAMEOFISSUER"]), row["TITLEOFCLASS"].lower())
                if key in lookup_keys:
                    issuer_matches[key].add(cusip)
            if eligible[acc] in manager_ids or cusip in security_ids:
                yield period, acc, cusip, int(row["VALUE"]), row["TITLEOFCLASS"]

    db.executemany("INSERT INTO holdings VALUES (?, ?, ?, ?, ?)", relevant_rows())
    return issuer_matches, scanned


def summary(db, period, cik):
    return db.execute("""
        SELECT SUM(h.value), COUNT(c.title), COUNT(*)
          FROM holdings h JOIN filings f USING (period, accession)
          LEFT JOIN classes c ON LOWER(h.title) = c.title
         WHERE f.period = ? AND f.cik = ?
        """, (period, cik)).fetchone()


def unambiguous_ranks(ranked):
    assert len(ranked) >= 2 and ranked[0][1] != ranked[1][1]
    assert len(ranked) < 3 or ranked[1][1] != ranked[2][1]
    return [row[0] for row in ranked[:2]]


def ranked_changes(db, previous, current, cik, sign):
    rows = db.execute("""
        WITH differences AS (
            SELECT h.cusip, SUM(CASE h.period WHEN ? THEN h.value ELSE -h.value END) AS delta
              FROM holdings h JOIN filings f USING (period, accession)
              JOIN classes c ON LOWER(h.title) = c.title
             WHERE f.cik = ? AND h.period IN (?, ?)
             GROUP BY h.cusip
        )
        SELECT cusip, delta * ? AS magnitude FROM differences
         WHERE delta * ? > 0 ORDER BY magnitude DESC LIMIT 3
        """, (current, cik, previous, current, sign, sign)).fetchall()
    return unambiguous_ranks(rows)


def ranked_holders(db, current, cusip):
    rows = db.execute("""
        SELECT f.name, SUM(h.value) AS value
          FROM holdings h JOIN filings f USING (period, accession)
         WHERE h.period = ? AND h.cusip = ?
         GROUP BY f.cik HAVING value > 0 ORDER BY value DESC LIMIT 3
        """, (current, cusip)).fetchall()
    return unambiguous_ranks(rows)


def verify_split(db, folder, spec, manifest, issuer_matches):
    previous, current = spec["baseline"], spec["current"]
    computed = {}
    for c in spec["cases"]:
        cik, cusip = c["manager"]["cik"], c["security"]["cusip"]
        prior_value, prior_count, prior_rows = summary(db, previous, cik)
        value, count, current_rows = summary(db, current, cik)
        assert prior_rows == manifest["source_manager_rows"][previous][cik]
        assert current_rows == manifest["source_manager_rows"][current][cik]
        holder_rows = db.execute("SELECT COUNT(*) FROM holdings WHERE period = ? AND cusip = ?",
                                 (current, cusip)).fetchone()[0]
        assert holder_rows == manifest["source_current_target_rows"][cusip]
        for period in (previous, current):
            names = db.execute("SELECT cik, name FROM filings WHERE period = ?", (period,))
            key = normalized_name(c["manager"]["name"])
            assert [i for i, name in names if normalized_name(name) == key] == [cik]
        key = (normalized_name(c["security"]["issuer"]), c["security"]["title"])
        assert issuer_matches[current][key] == {cusip}
        computed[c["id"]] = {
            "q1_answer": prior_value, "q2_answer": value,
            "q3_answer": prior_count, "q4_answer": count,
            "q5_answer": ranked_changes(db, previous, current, cik, 1),
            "q6_answer": ranked_changes(db, previous, current, cik, -1),
            "q7_answer": ranked_holders(db, current, cusip),
        }
    reference = load_reference(folder / "verifier/expected_output.json")
    if computed != reference:
        mismatches = [(case, key) for case in reference for key in reference[case]
                      if computed.get(case, {}).get(key) != reference[case][key]]
        raise ValueError(f"{folder.name} reference mismatch at {mismatches}")
    return computed, reference


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--answers-dir", type=Path, help="Optional directory for independently computed outputs")
    parser.add_argument("--archives-dir", type=Path, default=DEFAULT_ARCHIVES)
    args = parser.parse_args()
    data = PACKAGE / "data"
    manifest = read_json(data / "manifest.json")["splits"]
    classes = verify_classes()
    groups = {s: read_json(data / s / "queries.json") for s in manifest}
    a, b = groups["train"]["cases"], groups["test_entity"]["cases"]
    assert a == groups["test_period"]["cases"] and b == groups["test_both"]["cases"]
    assert not ({c["manager"]["cik"] for c in a} & {c["manager"]["cik"] for c in b})
    assert not ({c["security"]["cusip"] for c in a} & {c["security"]["cusip"] for c in b})
    assert (groups["train"]["baseline"], groups["train"]["current"]) == (
        groups["test_entity"]["baseline"], groups["test_entity"]["current"])
    managers, securities, lookup_keys = defaultdict(set), defaultdict(set), defaultdict(set)
    for spec in groups.values():
        previous, current = spec["baseline"], spec["current"]
        for c in spec["cases"]:
            managers[previous].add(c["manager"]["cik"])
            managers[current].add(c["manager"]["cik"])
            securities[current].add(c["security"]["cusip"])
            lookup_keys[current].add((normalized_name(c["security"]["issuer"]), c["security"]["title"]))
    archives = source_archives(args.archives_dir, sorted(managers))
    db = sqlite3.connect(":memory:")
    db.executescript("""
        PRAGMA foreign_keys = ON;
        CREATE TABLE filings(period TEXT, accession TEXT, cik TEXT, name TEXT,
          PRIMARY KEY(period, accession), UNIQUE(period, cik));
        CREATE TABLE classes(title TEXT PRIMARY KEY);
        CREATE TABLE holdings(period TEXT, accession TEXT, cusip TEXT, value INTEGER,
          title TEXT, FOREIGN KEY(period, accession) REFERENCES filings);
        CREATE INDEX holding_filing ON holdings(period, accession);
        CREATE INDEX holding_cusip ON holdings(period, cusip);
    """)
    db.executemany("INSERT INTO classes VALUES (?)", [(s,) for s in classes])
    issuer_matches, full_rows = {}, {}
    for period, path in archives.items():
        with ZipFile(path) as archive:
            issuer_matches[period], full_rows[period] = load_period(
                db, archive, period, managers[period], securities[period], lookup_keys[period], set(classes))
        print(f"{period}: scanned {full_rows[period]} source holding rows", file=sys.stderr, flush=True)
    with TemporaryDirectory(prefix="sec-v2-sqlite-") as tmp:
        output = args.answers_dir or Path(tmp)
        if args.answers_dir:
            output.mkdir(parents=True, exist_ok=False)
        report = {}
        for split, details in manifest.items():
            independent, reference = verify_split(db, data / split, groups[split], details, issuer_matches)
            actual = output / f"{split}.json"
            actual.write_text(json.dumps(independent, ensure_ascii=False) + "\n", encoding="utf-8")
            grading = score(actual, reference)
            assert grading["correct_items"] == grading["denominator"] == 100
            report[split] = {"independent_exact_matches": 100, "scorer_accuracy": grading["accuracy"],
                             "full_source_manager_and_target_row_counts_match": True}
            print(f"{split}: 100/100 exact, scorer={grading['accuracy']:.1f}", file=sys.stderr, flush=True)
        print(json.dumps({"method": "independent SQLite queries after streaming all six complete source ZIPs",
                          "stock_classes": len(classes), "full_source_holding_rows": full_rows,
                          "splits": report}, indent=2))
    db.close()


if __name__ == "__main__":
    main()
