#!/usr/bin/env python3

"""Analyze a single 13F manager's holdings.

This script is intentionally dependency-light (standard library only) so it can
run in minimal environments.

Inputs are expected as TSV files under:
  <DATA_ROOT>/<quarter>/INFOTABLE.tsv

Where DATA_ROOT defaults to /root and can be overridden with SEC_13F_DATA_ROOT.

It supports:
- One-quarter summary (row counts, AUM proxy, and unique common-equity CUSIPs)
- Two-quarter comparison (Top Buys / Top Sells by VALUE change)

Notes on definitions:
- "How many stocks" is interpreted as number of unique common-equity CUSIPs
  (not raw INFOTABLE row count).
- Options are excluded when the INFOTABLE has a PUTCALL column.
"""

import argparse
import csv
import os
from collections import defaultdict
from typing import Dict, Iterable, List, Optional, Tuple

# Dataset root. By default the tasks place quarterly folders under /root/<quarter>/
DATA_ROOT = os.environ.get("SEC_13F_DATA_ROOT", "/root")

# Common equity / stock-like TITLEOFCLASS values observed in 13F filings.
TITLE_CLASS_OF_STOCKS = {
    "com",
    "common stock",
    "cl a",
    "com new",
    "class a",
    "stock",
    "common",
    "com cl a",
    "com shs",
    "sponsored adr",
    "sponsored ads",
    "adr",
    "equity",
    "cmn",
    "cl b",
    "ord shs",
    "cl a com",
    "class a com",
    "cap stk cl a",
    "comm stk",
    "cl b new",
    "cap stk cl c",
    "cl a new",
    "foreign stock",
    "shs cl a",
}


def get_args():
    parser = argparse.ArgumentParser(description="Analyze SEC 13F holdings for one manager")
    parser.add_argument(
        "--accession_number",
        type=str,
        required=True,
        help="The accession number of the fund/filing to analyze",
    )
    parser.add_argument(
        "--quarter",
        type=str,
        required=True,
        help="The quarter to analyze, e.g. 2025-q3",
    )

    parser.add_argument(
        "--baseline_quarter",
        type=str,
        default=None,
        required=False,
        help="Baseline quarter for comparison, e.g. 2025-q2",
    )
    parser.add_argument(
        "--baseline_accession_number",
        type=str,
        default=None,
        required=False,
        help="Baseline accession number for comparison",
    )
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


def _is_common_equity_row(row: Dict[str, str]) -> bool:
    title = (row.get("TITLEOFCLASS") or "").strip().lower()
    if title and title not in TITLE_CLASS_OF_STOCKS:
        return False

    # Exclude options when present.
    if "PUTCALL" in row:
        pc = (row.get("PUTCALL") or "").strip().upper()
        if pc:  # CALL/PUT
            return False

    return True


def _load_infotable_rows(accession_number: str, quarter: str) -> List[Dict[str, str]]:
    path = os.path.join(DATA_ROOT, quarter, "INFOTABLE.tsv")
    rows = _read_tsv(path)
    return [r for r in rows if (r.get("ACCESSION_NUMBER") or "") == accession_number]


def _aggregate_common_equity_by_cusip(rows: Iterable[Dict[str, str]]) -> Dict[str, Dict[str, object]]:
    """Aggregate common-equity rows by CUSIP.

    Returns mapping:
      cusip -> {"name": str, "title": str, "value": float}
    """
    agg: Dict[str, Dict[str, object]] = {}
    for r in rows:
        if not _is_common_equity_row(r):
            continue
        cusip = (r.get("CUSIP") or "").strip().upper()
        if not cusip:
            continue
        if cusip not in agg:
            agg[cusip] = {
                "name": (r.get("NAMEOFISSUER") or "").strip(),
                "title": (r.get("TITLEOFCLASS") or "").strip(),
                "value": 0.0,
            }
        agg[cusip]["value"] = float(agg[cusip]["value"]) + _safe_float(r.get("VALUE") or "0")
    return agg


def read_one_quarter_data(accession_number: str, quarter: str) -> Tuple[List[Dict[str, str]], Dict[str, Dict[str, object]]]:
    """Load one quarter's data for an accession number.

    Returns:
      (raw_rows, common_equity_agg_by_cusip)
    """
    rows = _load_infotable_rows(accession_number, quarter)
    if not rows:
        raise SystemExit(f"ERROR: No INFOTABLE rows found for ACCESSION_NUMBER={accession_number} in {quarter}")

    total_rows = len(rows)
    total_value = sum(_safe_float(r.get("VALUE") or "0") for r in rows)

    common_equity_rows = [r for r in rows if _is_common_equity_row(r)]
    common_equity_value = sum(_safe_float(r.get("VALUE") or "0") for r in common_equity_rows)
    common_equity_by_cusip = _aggregate_common_equity_by_cusip(common_equity_rows)

    print(f"Summary stats for quarter: {quarter}, accession_number: {accession_number}")
    print(f"- Total number of rows (positions): {total_rows}")
    print(f"- Total AUM (sum of VALUE): {total_value:.2f}")
    print(f"- Number of common-equity rows: {len(common_equity_rows)}")
    print(f"- Number of common-equity stocks (unique CUSIPs): {len(common_equity_by_cusip)}")
    print(f"- Total common-equity AUM (sum of VALUE): {common_equity_value:.2f}")

    if not common_equity_by_cusip:
        raise SystemExit(
            f"ERROR: No common-equity rows found for ACCESSION_NUMBER={accession_number} in quarter {quarter}"
        )

    return rows, common_equity_by_cusip


def one_fund_analysis(
    accession_number: str,
    quarter: str,
    baseline_accession_number: Optional[str],
    baseline_quarter: Optional[str],
):
    _, cur = read_one_quarter_data(accession_number, quarter)

    if baseline_accession_number is None or baseline_quarter is None:
        return

    print(f"Performing comparative analysis using baseline quarter {baseline_quarter}")
    _, base = read_one_quarter_data(baseline_accession_number, baseline_quarter)

    all_cusips = set(cur.keys()) | set(base.keys())

    changes: List[Tuple[str, float, float, float, str]] = []
    # (cusip, cur_value, base_value, abs_change, name)
    for cusip in all_cusips:
        cur_val = float(cur.get(cusip, {}).get("value", 0.0))
        base_val = float(base.get(cusip, {}).get("value", 0.0))
        name = str(cur.get(cusip, {}).get("name") or base.get(cusip, {}).get("name") or "")
        abs_change = cur_val - base_val
        changes.append((cusip, cur_val, base_val, abs_change, name))

    # Top buys: positive change, descending by abs_change.
    buys = sorted([c for c in changes if c[3] > 0], key=lambda x: x[3], reverse=True)[:10]
    print(f"Top 10 Buys from {baseline_quarter} to {quarter}:")
    for idx, (cusip, _cur, _base, abs_change, name) in enumerate(buys, start=1):
        print(f"[{idx}] CUSIP: {cusip}, Name: {name} | Abs change: {abs_change:.2f}")

    # Top sells: negative change, ascending (most negative first).
    sells = sorted([c for c in changes if c[3] < 0], key=lambda x: x[3])[:10]
    print(f"\nTop 10 Sells from {baseline_quarter} to {quarter}:")
    for idx, (cusip, _cur, _base, abs_change, name) in enumerate(sells, start=1):
        print(f"[{idx}] CUSIP: {cusip}, Name: {name} | Abs change: {abs_change:.2f}")


if __name__ == "__main__":
    args = get_args()
    one_fund_analysis(args.accession_number, args.quarter, args.baseline_accession_number, args.baseline_quarter)
