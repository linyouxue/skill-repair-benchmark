"""Build three frozen source-row subsets and Python integer references. No models."""
import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime
from decimal import Decimal
import gzip
import hashlib
import io
import json
from pathlib import Path
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = "sec-original-accuracy-v1"
GROUPS = {"group_01": ("2024-q1", "2024-q2"), "group_02": ("2024-q3", "2024-q4"),
          "group_03": ("2025-q4", "2026-q1")}
MONTHS = {x: i for i, x in enumerate("JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split(), 1)}


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def report_date(quarter):
    return {"1": "31-MAR", "2": "30-JUN", "3": "30-SEP", "4": "31-DEC"}[quarter[-1]] + "-" + quarter[:4]


def date_key(text):
    d, m, y = text.upper().split("-")
    return int(y), MONTHS[m], int(d)


def cik(text):
    return str(int(text)).zfill(10)


def member(archive, kind):
    return next(n for n in archive.namelist() if Path(n).name.upper() == kind + ".TSV")


class TrackedLines:
    def __init__(self, file):
        self.file, self.parts = file, []

    def __iter__(self):
        return self

    def __next__(self):
        text = next(self.file)
        self.parts.append(text)
        return text


class Quarter:
    def __init__(self, record):
        self.record, self.quarter = record, record["quarter"]
        self.archive = zipfile.ZipFile(ROOT / record["path"])
        self.submission = self.small("SUBMISSION")
        self.cover = self.small("COVERPAGE")
        self.summary = self.small("SUMMARYPAGE")
        candidates = defaultdict(list)
        for accession, row in self.cover.items():
            s = self.submission[accession]
            if (row["REPORTCALENDARORQUARTER"] == report_date(self.quarter)
                    and s["PERIODOFREPORT"] == report_date(self.quarter)
                    and s["SUBMISSIONTYPE"] == "13F-HR" and row["ISAMENDMENT"] != "Y"):
                candidates[cik(s["CIK"])].append(accession)
        self.chosen = {c: min(accs, key=lambda a: (date_key(self.submission[a]["FILING_DATE"]), a))
                       for c, accs in candidates.items()}
        self.acc_cik = {a: c for c, a in self.chosen.items()}

    def raw_table(self, kind):
        with self.archive.open(member(self.archive, kind)) as raw:
            lines = TrackedLines(io.TextIOWrapper(raw, encoding="utf-8-sig", newline=""))
            reader = csv.DictReader(lines, delimiter="\t")
            columns = reader.fieldnames
            self.last_header = "".join(lines.parts)
            while True:
                lines.parts.clear()
                try:
                    row = next(reader)
                except StopIteration:
                    break
                if None in row or any(v is None for v in row.values()):
                    raise ValueError("Malformed SEC row")
                yield row, "".join(lines.parts)

    def small(self, kind):
        return {r["ACCESSION_NUMBER"]: r for r, _ in self.raw_table(kind)}

    def manager(self, c):
        return {"cik": c, "name": self.cover[self.chosen[c]]["FILINGMANAGER_NAME"]}

    def collect(self, fund_ciks, classes, securities=()):
        fund_acc = {self.chosen[c] for c in fund_ciks}
        funds = {c: {"value": 0, "stock_rows": 0, "stocks": Counter()} for c in fund_ciks}
        stock_meta = {}
        holders = {s: Counter() for s in securities}
        total = 0
        for row, _ in self.raw_table("INFOTABLE"):
            total += 1
            acc, security = row["ACCESSION_NUMBER"], row["CUSIP"]
            if acc not in fund_acc and (security not in holders or acc not in self.acc_cik):
                continue
            value_decimal = Decimal(row["VALUE"])
            if value_decimal != value_decimal.to_integral_value():
                raise ValueError("Non-integer VALUE in selected data")
            value = int(value_decimal)
            if acc in fund_acc:
                f = funds[self.acc_cik[acc]]
                f["value"] += value
                if row["TITLEOFCLASS"].lower() in classes:
                    f["stock_rows"] += 1
                    f["stocks"][security] += value
                    stock_meta.setdefault(security, {"cusip": security, "issuer": row["NAMEOFISSUER"], "title": row["TITLEOFCLASS"]})
            if security in holders and acc in self.acc_cik:
                holders[security][self.acc_cik[acc]] += value
        print(json.dumps({"python_source_pass": self.quarter, "raw_rows": total}), flush=True)
        return funds, stock_meta, holders, total

    def export(self, target, fund_ciks, securities):
        target.mkdir(parents=True, exist_ok=True)
        fund_acc = {self.chosen[c] for c in fund_ciks}
        counts = {}
        for kind in ["COVERPAGE", "SUBMISSION", "SUMMARYPAGE", "INFOTABLE"]:
            dest = target / (kind + ".tsv.gz")
            count, digest = 0, hashlib.sha256()
            with dest.open("wb") as output, gzip.GzipFile(filename="", mode="wb", fileobj=output, mtime=0) as gz:
                iterator = self.raw_table(kind)
                first = True
                for row, text in iterator:
                    if first:
                        header = self.last_header.encode("utf-8")
                        gz.write(header)
                        digest.update(header)
                        first = False
                    acc = row["ACCESSION_NUMBER"]
                    keep = acc in self.acc_cik if kind != "INFOTABLE" else (
                        acc in fund_acc or (acc in self.acc_cik and row["CUSIP"] in securities))
                    if keep:
                        data = text.encode("utf-8")
                        gz.write(data)
                        digest.update(data)
                        count += 1
            counts[kind] = {"rows": count, "uncompressed_sha256": digest.hexdigest(), "bytes_gz": dest.stat().st_size}
        print(json.dumps({"exported_period": self.quarter, "positions": counts["INFOTABLE"]["rows"]}), flush=True)
        return counts


def top_changes(previous, current):
    values = {s: current.get(s, 0) - previous.get(s, 0) for s in previous.keys() | current.keys()}
    return sorted((s for s, v in values.items() if v > 0), key=lambda s: (-values[s], s))[:5]


def unique_top(values, k):
    """Do not introduce a tie-breaking convention absent from the old task."""
    ordered = sorted((v for v in values if v > 0), reverse=True)
    return len(ordered) >= k and len(set(ordered[:k])) == k and (len(ordered) == k or ordered[k-1] > ordered[k])


def unambiguous_changes(previous, current):
    return unique_top([current.get(s, 0) - previous.get(s, 0)
                       for s in previous.keys() | current.keys()], 5)


def answer(query, old, new, holders, current):
    a, b, security = query["summary_manager"]["cik"], query["change_manager"]["cik"], query["security"]["cusip"]
    top3 = sorted(holders[security], key=lambda c: (-holders[security][c], c))[:3]
    return {"q1_answer": new[a]["value"], "q2_answer": new[a]["stock_rows"],
            "q3_answer": top_changes(old[b]["stocks"], new[b]["stocks"]),
            "q4_answer": [current.manager(c)["name"] for c in top3]}


def reference(cases, layout):
    return {"dataset_version": VERSION, "scoring_version": "sec-answer-accuracy-v1", "layout": layout,
            "cases": cases, "expected_answer_items": 10 * len(cases)}


def main():
    contract = json.loads((ROOT / "environment/statistical_contract.json").read_text(encoding="utf-8"))
    classes = set(contract["stock_title_classes"])
    sources = json.loads((ROOT / "evaluation/source/SOURCES.json").read_text(encoding="utf-8"))
    quarters = {r["quarter"]: Quarter(r) for r in sources["archives"]}
    # Original four questions; recompute independently of the legacy expected file.
    train_old, train_new = quarters["2025-q2"], quarters["2025-q3"]
    train_ciks = {"0001037389", "0001067983"}
    old, _, _, _ = train_old.collect(train_ciks, classes)
    new, _, holders, _ = train_new.collect(train_ciks, classes, ["69608A108"])
    query = {"case_id": "original", "summary_manager": train_new.manager("0001037389"),
             "change_manager": train_new.manager("0001067983"), "security": {"cusip": "69608A108"}}
    train_answer = answer(query, old, new, holders, train_new)
    write_json(ROOT / "validation/training_query_spec.json", {"baseline_period": "2025-q2", "current_period": "2025-q3", "queries": [query]})
    legacy = json.loads((ROOT / "verifier/expected_output.json").read_text(encoding="utf-8"))
    assert train_answer == legacy, "Original-semantics calculation must match unchanged official GT"
    write_json(ROOT / "validation/legacy_reference_comparison.json", {
        "legacy_source": "SkillsBench b63b7b2 verifier/expected_output.json", "new_reference_independently_calculated": True,
        "equal_by_question": {k: train_answer[k] == legacy[k] for k in train_answer},
        "official_gt_preserved": True,
        "explanation": "Keep the evaluated original helper allowlist, including concatenated literals. This changes scoring granularity, not the task's answer semantics."})
    used_ciks = set(train_ciks)
    used_securities = {"69608A108"}
    batches = []
    for group, (previous_period, current_period) in GROUPS.items():
        previous, current = quarters[previous_period], quarters[current_period]
        pool = [c for c in previous.chosen.keys() & current.chosen.keys() if c not in used_ciks
                and int(previous.summary[previous.chosen[c]].get("TABLEENTRYTOTAL") or 0) >= 50
                and int(current.summary[current.chosen[c]].get("TABLEENTRYTOTAL") or 0) >= 50]
        pool.sort(key=lambda c: hashlib.sha256(f"{VERSION}|{group}|manager|{c}".encode()).hexdigest())
        candidates = pool[:100]
        old, _, _, old_total = previous.collect(candidates, classes)
        new, meta, _, new_total = current.collect(candidates, classes)
        usable = [c for c in candidates if unambiguous_changes(old[c]["stocks"], new[c]["stocks"])
                  and new[c]["stock_rows"] > 0]
        if len(usable) < 40:
            raise ValueError("Not enough deterministic eligible manager pairs")
        selected = usable[:40]
        securities = sorted((s for c in selected[20:] for s in new[c]["stocks"] if s not in used_securities),
                            key=lambda s: hashlib.sha256(f"{VERSION}|{group}|security|{s}".encode()).hexdigest())
        securities = list(dict.fromkeys(securities))[:100]
        _, _, holders, _ = current.collect([], classes, securities)
        eligible_securities = [s for s in securities if unique_top(holders[s].values(), 3)]
        if len(eligible_securities) < 20:
            raise ValueError("Not enough securities with three reporting managers")
        selected_securities = eligible_securities[:20]
        queries = [{"case_id": f"case_{i + 1:03d}", "summary_manager": current.manager(selected[i]),
                    "change_manager": current.manager(selected[i + 20]), "security": meta[selected_securities[i]]}
                   for i in range(20)]
        group_root = ROOT / "evaluation" / group
        spec = {"dataset_version": VERSION, "group": group, "baseline_period": previous_period,
                "current_period": current_period, "queries": queries}
        write_json(group_root / "inputs/queries.json", spec)
        write_json(group_root / "verifier/reference_answers.json", reference({q["case_id"]: answer(q, old, new, holders, current) for q in queries}, "cases"))
        source_rows = {
            previous_period: previous.export(group_root / "inputs/data" / previous_period, selected, set()),
            current_period: current.export(group_root / "inputs/data" / current_period, selected, set(selected_securities)),
        }
        info = {"group": group, "periods": [previous_period, current_period], "query_cases": 20, "answer_items": 200,
                "source_urls": [previous.record["url"], current.record["url"]],
                "source_sha256": [previous.record["sha256"], current.record["sha256"]],
                "selected_query_ciks": selected, "selected_security_cusips": selected_securities,
                "manager_candidate_pool": len(pool), "managers_predeclared_hash_prefix_checked": len(candidates),
                "managers_with_five_positive_increases": len(usable), "security_candidates_checked": len(securities),
                "securities_with_at_least_three_holders": len(eligible_securities),
                "source_rows": source_rows, "source_position_rows": [old_total, new_total],
                "selection": "Fixed SHA256 order on public identifiers; eligibility only for complete four-query cases with unambiguous top ranks/cutoffs, no method-score selection.",
                "rank_ties_at_selected_top_or_cutoff": False,
                "distribution": "Same-source temporal and query-entity challenge, not difficulty-matched IID.",
                "row_filter": "Keep complete filings for all 40 queried managers in both periods; current period additionally keeps every eligible filing row for all 20 query securities. Metadata keeps the complete eligible filing cohort.",
                "raw_selected_rows_reencoded": False, "raw_selected_rows_preserved": True}
        write_json(group_root / "metadata.json", info)
        batches.append(info)
        used_ciks.update(selected)
        used_securities.update(selected_securities)
    write_json(ROOT / "evaluation/manifest.json", {"dataset_version": VERSION, "groups": batches,
                "test_cases": 60, "test_answer_items": 600, "training_answer_items": 10,
                "report_periods_disjoint": True, "query_target_ciks_disjoint": True,
                "security_query_cusips_disjoint": True, "model_calls": 0})
    print(json.dumps({"python_reference_cases": 61, "python_reference_items": 610, "model_calls": 0}), flush=True)


if __name__ == "__main__":
    main()
