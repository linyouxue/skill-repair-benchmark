"""Second calculation from source rows using SQLite; no primary-builder imports."""
import argparse
import ast
import csv
from datetime import datetime
from decimal import Decimal
import gzip
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SQL = {
    "q1": "SELECT SUM(value) FROM positions WHERE period=:current AND accession=:summary_acc",
    "q2": "SELECT COUNT(*) FROM positions WHERE period=:current AND accession=:summary_acc AND title IN (SELECT title FROM stock_classes)",
    "q3": """SELECT cusip, SUM(CASE WHEN period=:current THEN value ELSE -value END) AS delta
        FROM positions WHERE ((period=:current AND accession=:change_acc) OR (period=:previous AND accession=:previous_acc))
        AND title IN (SELECT title FROM stock_classes)
        GROUP BY cusip HAVING delta > 0 ORDER BY delta DESC, cusip ASC LIMIT 6""",
    "q4": """SELECT c.manager, SUM(p.value) AS amount FROM positions p JOIN chosen c
        ON p.period=c.period AND p.accession=c.accession
        WHERE p.period=:current AND p.cusip=:cusip GROUP BY p.accession
        ORDER BY amount DESC, p.accession ASC LIMIT 4""",
    "training_q4": """SELECT c.manager, SUM(p.value) AS amount FROM positions p JOIN cover c
        ON p.period=c.period AND p.accession=c.accession
        WHERE p.period=:current AND p.cusip=:cusip GROUP BY p.accession
        ORDER BY amount DESC, p.accession ASC LIMIT 4""",
}


def stock_classes():
    tree = ast.parse((ROOT / "environment/skills/13f-analyzer/scripts/one_fund_analysis.py").read_text(encoding="utf-8"))
    return next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "title_class_of_stocks" for t in n.targets))


def rows(period, table, group):
    if group == "original":
        with zipfile.ZipFile(ROOT / f"environment/13f-{period}.zip") as archive:
            name = next(n for n in archive.namelist() if Path(n).name.upper() == table + ".TSV")
            with archive.open(name) as raw:
                yield from csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline=""), delimiter="\t")
    else:
        path = ROOT / "evaluation" / group / "inputs/data" / period / (table + ".tsv.gz")
        with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as raw:
            yield from csv.DictReader(raw, delimiter="\t")


def period_date(period):
    return {"q1": "31-MAR-", "q2": "30-JUN-", "q3": "30-SEP-", "q4": "31-DEC-"}[period[-2:]] + period[:4]


def check(group, answer_output=None):
    original = group == "original"
    spec = json.loads((ROOT / ("validation/training_query_spec.json" if original else f"evaluation/{group}/inputs/queries.json")).read_text(encoding="utf-8"))
    ref = json.loads((ROOT / ("verifier/expected_output.json" if original else f"evaluation/{group}/verifier/reference_answers.json")).read_text(encoding="utf-8"))
    if original:
        ref = {"cases": {"original": ref}}
    previous, current = spec["baseline_period"], spec["current_period"]
    connection = sqlite3.connect(":memory:")
    connection.executescript("""
        CREATE TABLE cover(period TEXT, accession TEXT, manager TEXT, report TEXT, amendment TEXT);
        CREATE TABLE submission(period TEXT, accession TEXT, cik TEXT, report TEXT, kind TEXT, filed TEXT);
        CREATE TABLE summary(period TEXT, accession TEXT, value INTEGER, rows INTEGER);
        CREATE TABLE positions(period TEXT, accession TEXT, cusip TEXT, title TEXT, value INTEGER);
        CREATE TABLE stock_classes(title TEXT PRIMARY KEY);
    """)
    connection.executemany("INSERT INTO stock_classes VALUES (?)", [(t,) for t in stock_classes()])
    for period in [previous, current]:
        connection.executemany("INSERT INTO cover VALUES (?,?,?,?,?)", ((period, r["ACCESSION_NUMBER"], r["FILINGMANAGER_NAME"],
                                r["REPORTCALENDARORQUARTER"], r["ISAMENDMENT"]) for r in rows(period, "COVERPAGE", group)))
        connection.executemany("INSERT INTO submission VALUES (?,?,?,?,?,?)", ((period, r["ACCESSION_NUMBER"], str(int(r["CIK"])).zfill(10),
                                r["PERIODOFREPORT"], r["SUBMISSIONTYPE"], datetime.strptime(r["FILING_DATE"], "%d-%b-%Y").isoformat())
                                for r in rows(period, "SUBMISSION", group)))
        connection.executemany("INSERT INTO summary VALUES (?,?,?,?)", ((period, r["ACCESSION_NUMBER"], int(Decimal(r["TABLEVALUETOTAL"] or "0")),
                                int(r["TABLEENTRYTOTAL"] or "0")) for r in rows(period, "SUMMARYPAGE", group)))
    connection.executescript("CREATE INDEX cover_acc ON cover(period, accession); CREATE INDEX sub_acc ON submission(period, accession);")
    connection.execute("CREATE TABLE report_dates(period TEXT, report TEXT)")
    connection.executemany("INSERT INTO report_dates VALUES (?,?)", [(p, period_date(p)) for p in [previous, current]])
    connection.executescript("""CREATE VIEW chosen AS SELECT period, accession, cik, manager FROM (
        SELECT c.period, c.accession, s.cik, c.manager,
               ROW_NUMBER() OVER (PARTITION BY c.period,s.cik ORDER BY s.filed,c.accession) AS rn
        FROM cover c JOIN submission s ON c.period=s.period AND c.accession=s.accession
        JOIN report_dates d ON c.period=d.period
        WHERE c.report=d.report AND s.report=d.report AND c.amendment!='Y' AND s.kind='13F-HR') WHERE rn=1;
    """)
    ciks = {q[key]["cik"] for q in spec["queries"] for key in ["summary_manager", "change_manager"]}
    securities = {q["security"]["cusip"] for q in spec["queries"]}
    for period in [previous, current]:
        accessions = {a for a, c in connection.execute("SELECT accession,cik FROM chosen WHERE period=?", (period,)) if c in ciks}
        def positions():
            for r in rows(period, "INFOTABLE", group):
                if r["ACCESSION_NUMBER"] in accessions or (period == current and r["CUSIP"] in securities):
                    value = Decimal(r["VALUE"])
                    if value != value.to_integral_value():
                        raise ValueError("Non-integral source VALUE")
                    yield period, r["ACCESSION_NUMBER"], r["CUSIP"], r["TITLEOFCLASS"].lower(), int(value)
        connection.executemany("INSERT INTO positions VALUES (?,?,?,?,?)", positions())
    connection.executescript("CREATE INDEX position_acc ON positions(period,accession); CREATE INDEX position_cusip ON positions(period,cusip);")
    summary_agreement, summary_mismatches, results, calculated_answers = [], [], {}, {}
    for q in spec["queries"]:
        def acc(period, cik):
            hits = connection.execute("SELECT accession FROM chosen WHERE period=? AND cik=?", (period, cik)).fetchall()
            if len(hits) != 1:
                raise ValueError("Ambiguous or missing manager filing")
            return hits[0][0]
        params = {"current": current, "previous": previous,
                  "summary_acc": acc(current, q["summary_manager"]["cik"]),
                  "change_acc": acc(current, q["change_manager"]["cik"]),
                  "previous_acc": acc(previous, q["change_manager"]["cik"]), "cusip": q["security"]["cusip"]}
        changes = connection.execute(SQL["q3"], params).fetchall()
        holders = connection.execute(SQL["training_q4" if original else "q4"], params).fetchall()
        for ranking, k in [(changes, 5), (holders, 3)]:
            values = [r[1] for r in ranking]
            assert len(values) >= k and len(set(values[:k])) == k and (len(values) == k or values[k-1] > values[k]), "Ambiguous top ranking"
        answer = {"q1_answer": connection.execute(SQL["q1"], params).fetchone()[0],
                  "q2_answer": connection.execute(SQL["q2"], params).fetchone()[0],
                  "q3_answer": [r[0] for r in changes[:5]], "q4_answer": [r[0] for r in holders[:3]]}
        expected = ref["cases"][q["case_id"]]
        if answer != expected:
            diagnostics = {"questions_equal": {k: answer[k] == expected[k] for k in answer},
                           "q4_equal_if_trimmed": [s.strip() for s in answer["q4_answer"]] == expected["q4_answer"]}
            raise ValueError(f"Independent reference mismatch: {group}/{q['case_id']}; {diagnostics}")
        total = connection.execute("SELECT value FROM summary WHERE period=? AND accession=?", (current, params["summary_acc"])).fetchone()[0]
        summary_agreement.append(total == answer["q1_answer"])
        if total != answer["q1_answer"]:
            summary_mismatches.append(q["case_id"])
        results[q["case_id"]] = True
        calculated_answers[q["case_id"]] = answer
    if original:
        official = json.loads((ROOT / "verifier/expected_output.json").read_text(encoding="utf-8"))
        assert ref["cases"]["original"] == official, "Original GT changed"
    connection.close()
    if answer_output is not None:
        answer_output = Path(answer_output)
        answer_output.parent.mkdir(parents=True, exist_ok=True)
        payload = calculated_answers["original"] if original else calculated_answers
        answer_output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"group": group, "cases": len(results), "answer_items": 10 * len(results),
            "all_answers_equal": all(results.values()), "q1_matches_summarypage": all(summary_agreement),
            "q1_summary_mismatching_cases": summary_mismatches,
            "q1_authoritative_rule": "Sum raw INFOTABLE.VALUE, as in the original helper; SUMMARYPAGE is only a secondary source-quality check.",
            "source": "original_zip" if original else "actual_exported_input_rows",
            "top_ranks_unambiguous": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--answer-output-dir", type=Path, help="Optional grading-side export of independently computed answers")
    args = parser.parse_args()
    reports = []
    for group in ["original", "group_01", "group_02", "group_03"]:
        output = args.answer_output_dir / group / "answers.json" if args.answer_output_dir else None
        result = check(group, output)
        reports.append(result)
        print(json.dumps(result), flush=True)
    result = {"independent_implementations": ["Python integer aggregation from complete source ZIPs", "SQLite queries from original ZIPs / actual test input rows"],
              "primary_builder_imported": False, "evaluated_original_helper_classes": True,
              "groups": reports, "all_610_items_equal": all(r["all_answers_equal"] for r in reports),
              "original_gt_unchanged": True, "model_calls": 0, "docker_runs": 0,
              "code_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__), ROOT / "tools/build_dataset.py"]}}
    (ROOT / "validation/sqlite_queries.json").write_text(json.dumps(SQL, indent=2) + "\n", encoding="utf-8")
    (ROOT / "validation/reference_crosscheck.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
