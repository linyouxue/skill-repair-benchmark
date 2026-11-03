#!/usr/bin/env python3
"""Analyze SEC 13F holdings for one fund in one quarter.

This script works on the SkillHone-style dataset layout:
  ${DATA_ROOT}/${QUARTER}/INFOTABLE.tsv

It prints:
  - Total positions (INFOTABLE rows)
  - Total distinct CUSIPs
  - Total reported VALUE
  - Common-stock positions and holdings (distinct CUSIPs)

Optionally, it compares two quarters (same manager across filings) and prints
Top Buys / Top Sells ranked by VALUE change at the CUSIP level.

Implementation note:
  The script intentionally avoids third-party dependencies (e.g., pandas) so it
  can run in minimal Python environments.
"""

from __future__ import annotations

import argparse
import csv
import os
import re
from typing import Any, Dict, Iterable, Optional, Tuple

DEFAULT_DATA_ROOT = "/root"

# Pragmatic allowlist of TITLEOFCLASS values that commonly indicate common
# equity. We normalize strings before comparison.
COMMON_STOCK_TITLE_CLASSES = {
    "com",
    "common stock",
    "common",
    "stock",
    "com new",
    "com cl a",
    "com shs",
    "cl a",
    "class a",
    "cl a com",
    "class a com",
    "cl a new",
    "cl b",
    "cl b new",
    "cmn",
    "ord shs",
    "foreign stock",
    "cap stk cl a",
    "cap stk cl c",
    "comm stk",
    "sponsored adr",
    "sponsored ads",
    "adr",
    "equity",
    "shs cl a",
}


def normalize_title(value: Optional[str]) -> str:
    text = (value or "").lower().strip()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^a-z0-9 ]+", "", text)
    return text


def normalize_cusip(value: Optional[str]) -> str:
    return (value or "").upper().strip()


def parse_float(value: Optional[str]) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0


def iter_tsv_rows(path: str) -> Iterable[Dict[str, str]]:
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            # DictReader returns None for missing columns; normalize to "".
            yield {k: (v if v is not None else "") for k, v in row.items()}


def is_common_stock_row(row: Dict[str, str]) -> bool:
    title_ok = normalize_title(row.get("TITLEOFCLASS")) in COMMON_STOCK_TITLE_CLASSES
    if not title_ok:
        return False

    # Exclude option legs when column exists.
    putcall = row.get("PUTCALL", "").strip()
    if putcall:
        return False

    # Prefer share positions if SHRSORPRN is present.
    shrsorprn = row.get("SHRSORPRN", "").strip().upper()
    if shrsorprn and shrsorprn != "SH":
        return False

    return True


def get_args():
    parser = argparse.ArgumentParser(
        description=(
            "Analyze SEC 13F INFOTABLE for one fund in one quarter, optionally "
            "comparing against a baseline quarter."
        )
    )
    parser.add_argument("--accession_number", type=str, required=True, help="Fund accession number")
    parser.add_argument("--quarter", type=str, required=True, help='Quarter folder, e.g. "2025-q3"')

    parser.add_argument("--baseline_quarter", type=str, default=None, help="Baseline quarter folder")
    parser.add_argument("--baseline_accession_number", type=str, default=None, help="Baseline accession number")

    parser.add_argument("--topk", type=int, default=10, help="Top-K to print for buys/sells")
    parser.add_argument(
        "--data_root",
        type=str,
        default=DEFAULT_DATA_ROOT,
        help=f"Dataset root directory (default: {DEFAULT_DATA_ROOT})",
    )
    return parser.parse_args()


def read_one_quarter_stock_holdings(
    data_root: str,
    accession_number: str,
    quarter: str,
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Any]]:
    """Read and aggregate holdings for one accession number in one quarter.

    Returns:
      (holdings_by_cusip, summary)

    holdings_by_cusip maps CUSIP -> {name, title, value}
    summary contains printed stats.
    """

    infotable_path = os.path.join(data_root, quarter, "INFOTABLE.tsv")
    if not os.path.exists(infotable_path):
        raise SystemExit(f"INFOTABLE.tsv not found: {infotable_path}")

    total_rows = 0
    total_value = 0.0
    all_cusips: set[str] = set()

    stock_rows = 0
    stock_value = 0.0
    stock_cusips: set[str] = set()

    agg: Dict[str, Dict[str, Any]] = {}

    for row in iter_tsv_rows(infotable_path):
        if row.get("ACCESSION_NUMBER") != accession_number:
            continue

        total_rows += 1

        cusip = normalize_cusip(row.get("CUSIP"))
        if cusip:
            all_cusips.add(cusip)

        value = parse_float(row.get("VALUE"))
        total_value += value

        if not is_common_stock_row(row):
            continue

        stock_rows += 1
        stock_value += value

        if not cusip:
            # Skip grouping when CUSIP is missing.
            continue

        stock_cusips.add(cusip)
        entry = agg.get(cusip)
        if entry is None:
            entry = {
                "CUSIP": cusip,
                "NAMEOFISSUER": row.get("NAMEOFISSUER", ""),
                "TITLEOFCLASS": row.get("TITLEOFCLASS", ""),
                "VALUE": 0.0,
            }
            agg[cusip] = entry
        entry["VALUE"] = float(entry["VALUE"]) + value

    if total_rows == 0:
        raise SystemExit(
            f"No INFOTABLE rows found for ACCESSION_NUMBER={accession_number} in quarter {quarter} "
            f"(checked {infotable_path})"
        )

    summary = {
        "total_rows": total_rows,
        "total_value": total_value,
        "distinct_cusips": len(all_cusips),
        "stock_rows": stock_rows,
        "stock_value": stock_value,
        "stock_distinct_cusips": len(stock_cusips),
    }

    print(f"Summary stats for quarter: {quarter}, accession_number: {accession_number}")
    print(f"- Total positions (rows): {summary['total_rows']}")
    print(f"- Total distinct CUSIPs: {summary['distinct_cusips']}")
    print(f"- Total reported value (sum of VALUE): {summary['total_value']:.2f}")
    print(f"- Common stock positions (rows): {summary['stock_rows']}")
    print(f"- Common stock holdings (distinct CUSIPs): {summary['stock_distinct_cusips']}")
    print(f"- Common stock reported value: {summary['stock_value']:.2f}")

    if summary["stock_rows"] == 0:
        raise SystemExit(
            "No common-stock rows found after filtering. "
            "(If you need options/bonds too, inspect raw INFOTABLE rows.)"
        )

    return agg, summary


def one_fund_analysis(
    data_root: str,
    accession_number: str,
    quarter: str,
    baseline_accession_number: Optional[str],
    baseline_quarter: Optional[str],
    topk: int = 10,
):
    current, _ = read_one_quarter_stock_holdings(data_root, accession_number, quarter)

    if not baseline_accession_number or not baseline_quarter:
        return

    print(f"\nPerforming comparative analysis using baseline quarter {baseline_quarter}")
    baseline, _ = read_one_quarter_stock_holdings(data_root, baseline_accession_number, baseline_quarter)

    cusips = set(current.keys()) | set(baseline.keys())

    deltas = []
    for cusip in cusips:
        cur_entry = current.get(cusip)
        base_entry = baseline.get(cusip)

        cur_value = float(cur_entry.get("VALUE", 0.0)) if cur_entry else 0.0
        base_value = float(base_entry.get("VALUE", 0.0)) if base_entry else 0.0
        abs_change = cur_value - base_value

        name = ""
        if cur_entry and cur_entry.get("NAMEOFISSUER"):
            name = str(cur_entry.get("NAMEOFISSUER"))
        elif base_entry and base_entry.get("NAMEOFISSUER"):
            name = str(base_entry.get("NAMEOFISSUER"))

        pct_change: Optional[float]
        if base_value != 0:
            pct_change = abs_change / base_value
        else:
            pct_change = None

        deltas.append(
            {
                "CUSIP": cusip,
                "NAMEOFISSUER": name,
                "VALUE": cur_value,
                "VALUE_base": base_value,
                "ABS_CHANGE": abs_change,
                "PCT_CHANGE": pct_change,
            }
        )

    buys = [d for d in deltas if d["ABS_CHANGE"] > 0]
    buys.sort(key=lambda d: float(d["ABS_CHANGE"]), reverse=True)

    print(f"Top {topk} Buys (VALUE increase) from {baseline_quarter} to {quarter}:")
    for idx, row in enumerate(buys[:topk], start=1):
        pct = "n/a" if row["PCT_CHANGE"] is None else f"{row['PCT_CHANGE']:.2%}"
        print(
            f"[{idx}] CUSIP: {row['CUSIP']}, Name: {row['NAMEOFISSUER']} | "
            f"Base: {row['VALUE_base']:.2f} -> Now: {row['VALUE']:.2f} | "
            f"Abs change: {row['ABS_CHANGE']:.2f} | Pct change: {pct}"
        )

    sells = [d for d in deltas if d["ABS_CHANGE"] < 0]
    sells.sort(key=lambda d: float(d["ABS_CHANGE"]))

    print(f"\nTop {topk} Sells (VALUE decrease) from {baseline_quarter} to {quarter}:")
    for idx, row in enumerate(sells[:topk], start=1):
        pct = "n/a" if row["PCT_CHANGE"] is None else f"{row['PCT_CHANGE']:.2%}"
        print(
            f"[{idx}] CUSIP: {row['CUSIP']}, Name: {row['NAMEOFISSUER']} | "
            f"Base: {row['VALUE_base']:.2f} -> Now: {row['VALUE']:.2f} | "
            f"Abs change: {row['ABS_CHANGE']:.2f} | Pct change: {pct}"
        )


def main():
    args = get_args()
    one_fund_analysis(
        data_root=args.data_root,
        accession_number=args.accession_number,
        quarter=args.quarter,
        baseline_accession_number=args.baseline_accession_number,
        baseline_quarter=args.baseline_quarter,
        topk=args.topk,
    )


if __name__ == "__main__":
    main()
