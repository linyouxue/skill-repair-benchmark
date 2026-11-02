#!/usr/bin/env python3

"""Find top managers holding a given CUSIP in one quarter.

Dependency-light (standard library only).

Inputs are expected as TSV files under:
  <DATA_ROOT>/<quarter>/(INFOTABLE.tsv, COVERPAGE.tsv)

Where DATA_ROOT defaults to /root and can be overridden with SEC_13F_DATA_ROOT.

The script:
- Filters INFOTABLE to the requested CUSIP (uppercased)
- Excludes options when the PUTCALL column exists
- Aggregates VALUE by ACCESSION_NUMBER
- Joins FILINGMANAGER_NAME from COVERPAGE for readability
"""

import argparse
import csv
import os
from typing import Dict, List, Tuple

# Dataset root. By default the tasks place quarterly folders under /root/<quarter>/
DATA_ROOT = os.environ.get("SEC_13F_DATA_ROOT", "/root")


def get_args():
    parser = argparse.ArgumentParser(description="Analyze which managers hold a given CUSIP")
    parser.add_argument("--cusip", type=str, required=True, help="The CUSIP of the stock to analyze")
    parser.add_argument("--quarter", type=str, required=True, help="The quarter to analyze, e.g. 2025-q3")
    parser.add_argument("--topk", type=int, default=10, help="The maximum number of results to return")
    return parser.parse_args()


def _read_tsv(path: str) -> List[Dict[str, str]]:
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        return list(reader)


def _safe_float(x: str) -> float:
    try:
        return float(x)
    except Exception:
        return 0.0


def _load_coverpage_name_map(quarter: str) -> Dict[str, str]:
    path = os.path.join(DATA_ROOT, quarter, "COVERPAGE.tsv")
    rows = _read_tsv(path)
    m: Dict[str, str] = {}
    for r in rows:
        acc = (r.get("ACCESSION_NUMBER") or "").strip()
        if not acc:
            continue
        if acc not in m:
            m[acc] = (r.get("FILINGMANAGER_NAME") or "").strip()
    return m


def _iter_infotable_rows_for_cusip(cusip: str, quarter: str):
    path = os.path.join(DATA_ROOT, quarter, "INFOTABLE.tsv")
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for r in reader:
            rc = (r.get("CUSIP") or "").strip().upper()
            if rc != cusip:
                continue

            # Exclude options when present.
            if "PUTCALL" in r:
                pc = (r.get("PUTCALL") or "").strip().upper()
                if pc:
                    continue

            yield r


def topk_managers(cusip: str, quarter: str, topk: int):
    cusip = cusip.strip().upper()

    name_map = _load_coverpage_name_map(quarter)

    totals: Dict[str, float] = {}
    seen_any = False
    for r in _iter_infotable_rows_for_cusip(cusip, quarter):
        seen_any = True
        acc = (r.get("ACCESSION_NUMBER") or "").strip()
        if not acc:
            continue
        totals[acc] = totals.get(acc, 0.0) + _safe_float(r.get("VALUE") or "0")

    if not seen_any:
        print(f"No holdings found for CUSIP {cusip} in quarter {quarter}")
        return

    ranked: List[Tuple[str, float]] = sorted(totals.items(), key=lambda x: x[1], reverse=True)[:topk]

    print(f"Top-{len(ranked)} managers holding CUSIP {cusip} in quarter {quarter}:")
    for idx, (acc, total) in enumerate(ranked, start=1):
        name = name_map.get(acc) or "(unknown)"
        print(f"Rank {idx}: {name} | accession number = {acc} | Holding value = {total:.2f}")


if __name__ == "__main__":
    args = get_args()
    topk_managers(args.cusip, args.quarter, args.topk)
