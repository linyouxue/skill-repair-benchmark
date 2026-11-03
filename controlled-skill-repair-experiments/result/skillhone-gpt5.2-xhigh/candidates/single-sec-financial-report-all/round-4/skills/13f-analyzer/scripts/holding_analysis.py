#!/usr/bin/env python3
"""Find top managers holding a given stock (CUSIP) in a quarter.

Dataset layout:
  ${DATA_ROOT}/${QUARTER}/INFOTABLE.tsv
  ${DATA_ROOT}/${QUARTER}/COVERPAGE.tsv

The script prints the top-k managers ranked by total 13F reported VALUE for the
CUSIP within each ACCESSION_NUMBER.

Implementation note:
  Avoids third-party dependencies (e.g., pandas) for portability.
"""

from __future__ import annotations

import argparse
import csv
import os
import re
from typing import Dict, Iterable, Optional, Tuple

DEFAULT_DATA_ROOT = "/root"

# Keep aligned with one_fund_analysis.py
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
            yield {k: (v if v is not None else "") for k, v in row.items()}


def is_common_stock_row(row: Dict[str, str]) -> bool:
    title_ok = normalize_title(row.get("TITLEOFCLASS")) in COMMON_STOCK_TITLE_CLASSES
    if not title_ok:
        return False

    putcall = row.get("PUTCALL", "").strip()
    if putcall:
        return False

    shrsorprn = row.get("SHRSORPRN", "").strip().upper()
    if shrsorprn and shrsorprn != "SH":
        return False

    return True


def get_args():
    parser = argparse.ArgumentParser(description="Find top fund managers holding a given stock CUSIP")
    parser.add_argument("--cusip", type=str, required=True, help="CUSIP of the stock to analyze")
    parser.add_argument(
        "--quarter",
        type=str,
        required=True,
        help='Quarter folder name, e.g. "2025-q3" (must exist under data_root)',
    )
    parser.add_argument("--topk", type=int, default=10, help="Maximum number of results to return")
    parser.add_argument(
        "--data_root",
        type=str,
        default=DEFAULT_DATA_ROOT,
        help=f"Dataset root directory (default: {DEFAULT_DATA_ROOT})",
    )
    return parser.parse_args()


def load_manager_names(coverpage_path: str) -> Dict[str, str]:
    """Map ACCESSION_NUMBER -> FILINGMANAGER_NAME."""

    mapping: Dict[str, str] = {}
    if not os.path.exists(coverpage_path):
        return mapping

    for row in iter_tsv_rows(coverpage_path):
        acc = row.get("ACCESSION_NUMBER", "").strip()
        name = row.get("FILINGMANAGER_NAME", "").strip()
        if acc and name and acc not in mapping:
            mapping[acc] = name
    return mapping


def topk_managers(data_root: str, cusip: str, quarter: str, topk: int = 10):
    """Print top-k fund managers holding a stock CUSIP in a quarter."""

    cusip_norm = normalize_cusip(cusip)

    infotable_path = os.path.join(data_root, quarter, "INFOTABLE.tsv")
    coverpage_path = os.path.join(data_root, quarter, "COVERPAGE.tsv")

    if not os.path.exists(infotable_path):
        raise SystemExit(f"INFOTABLE.tsv not found: {infotable_path}")

    # Aggregate VALUE (and shares if present) by accession.
    totals: Dict[str, Dict[str, float]] = {}
    matched_rows = 0

    for row in iter_tsv_rows(infotable_path):
        if normalize_cusip(row.get("CUSIP")) != cusip_norm:
            continue
        if not is_common_stock_row(row):
            continue

        accession = row.get("ACCESSION_NUMBER", "").strip()
        if not accession:
            continue

        matched_rows += 1
        value = parse_float(row.get("VALUE"))
        shares = parse_float(row.get("SSHPRNAMT")) if row.get("SSHPRNAMT", "") != "" else 0.0

        entry = totals.get(accession)
        if entry is None:
            entry = {"TOTAL_VALUE": 0.0, "TOTAL_SHARES": 0.0}
            totals[accession] = entry
        entry["TOTAL_VALUE"] += value
        entry["TOTAL_SHARES"] += shares

    if matched_rows == 0 or not totals:
        print(f"No holdings found for CUSIP {cusip_norm} in quarter {quarter}")
        return

    manager_names = load_manager_names(coverpage_path)

    ranked = sorted(totals.items(), key=lambda kv: kv[1]["TOTAL_VALUE"], reverse=True)
    ranked = ranked[: max(topk, 0)]

    print(f"Top-{len(ranked)} fund managers holding CUSIP {cusip_norm} in quarter {quarter}:")
    for idx, (accession, metrics) in enumerate(ranked, start=1):
        manager = manager_names.get(accession)
        manager_str = manager if manager else "(unknown manager)"
        value = metrics["TOTAL_VALUE"]
        shares = metrics.get("TOTAL_SHARES", 0.0)

        # Only print shares when they were actually present (heuristic: non-zero).
        if shares:
            print(
                f"Rank {idx}: {manager_str} | accession={accession} | "
                f"value={value:.2f} | shares={shares:.0f}"
            )
        else:
            print(f"Rank {idx}: {manager_str} | accession={accession} | value={value:.2f}")


def main():
    args = get_args()
    topk_managers(args.data_root, args.cusip, args.quarter, args.topk)


if __name__ == "__main__":
    main()
