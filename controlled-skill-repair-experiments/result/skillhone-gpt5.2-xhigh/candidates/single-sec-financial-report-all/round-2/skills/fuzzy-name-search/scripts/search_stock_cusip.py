#!/usr/bin/env python3
"""Fuzzy search a stock CUSIP by issuer name.

This tool searches issuer names in the SEC 13F INFOTABLE and prints candidate
CUSIPs.

Dataset layout:
  ${DATA_ROOT}/${QUARTER}/INFOTABLE.tsv

By default, it prefers common-equity (non-option) rows based on TITLEOFCLASS and
PUTCALL/SHRSORPRN when those columns exist.

Implementation note:
  Avoids third-party dependencies (rapidfuzz/pandas) for portability.
"""

from __future__ import annotations

import argparse
import csv
import os
import re
from typing import Dict, Iterable, List, Optional, Tuple

DEFAULT_DATA_ROOT = "/root"

# Keep aligned with 13f-analyzer.
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


def normalize_text(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def token_set_ratio(a: str, b: str) -> float:
    a_tokens = set(normalize_text(a).split())
    b_tokens = set(normalize_text(b).split())
    if not a_tokens and not b_tokens:
        return 100.0
    if not a_tokens or not b_tokens:
        return 0.0
    return 100.0 * (len(a_tokens & b_tokens) / len(a_tokens | b_tokens))


def normalize_cusip(value: Optional[str]) -> str:
    return (value or "").upper().strip()


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
    parser = argparse.ArgumentParser(description="Fuzzy search stock CUSIP by issuer name")
    parser.add_argument("--keywords", type=str, required=True, help="Issuer name / keywords to search (fuzzy)")
    parser.add_argument(
        "--quarter",
        type=str,
        default=None,
        help=(
            "Quarter folder (e.g. 2025-q3). If omitted, scans all quarter folders under data_root "
            "that match YYYY-qN."
        ),
    )
    parser.add_argument("--topk", type=int, default=10, help="Maximum number of results to return")
    parser.add_argument(
        "--data_root",
        type=str,
        default=DEFAULT_DATA_ROOT,
        help=f"Dataset root directory (default: {DEFAULT_DATA_ROOT})",
    )
    return parser.parse_args()


def list_infotable_paths(data_root: str, quarter: Optional[str]) -> List[str]:
    if quarter:
        path = os.path.join(data_root, quarter, "INFOTABLE.tsv")
        return [path]

    paths: List[str] = []
    if not os.path.isdir(data_root):
        return paths

    for name in sorted(os.listdir(data_root)):
        if re.fullmatch(r"\d{4}-q[1-4]", name):
            p = os.path.join(data_root, name, "INFOTABLE.tsv")
            if os.path.exists(p):
                paths.append(p)
    return paths


def load_stock_universe(data_root: str, quarter: Optional[str]) -> Dict[str, str]:
    """Return mapping: issuer_name(lower) -> CUSIP (uppercase).

    Keeps one CUSIP per distinct issuer name; multiple issuer names may map to
    the same CUSIP.
    """

    paths = list_infotable_paths(data_root, quarter)
    if not paths:
        raise SystemExit(
            "No INFOTABLE.tsv files found. Provide --quarter or ensure data_root contains quarter folders."
        )

    mapping: Dict[str, str] = {}
    for p in paths:
        if not os.path.exists(p):
            continue
        for row in iter_tsv_rows(p):
            if not is_common_stock_row(row):
                continue
            cusip = normalize_cusip(row.get("CUSIP"))
            name = normalize_text(row.get("NAMEOFISSUER", ""))
            if not cusip or not name:
                continue
            if name not in mapping:
                mapping[name] = cusip
    return mapping


def search_stock_by_name(data_root: str, keywords: str, quarter: Optional[str], topk: int = 10):
    universe = load_stock_universe(data_root, quarter)
    if not universe:
        print("No stock universe available after filtering.")
        return

    scored: List[Tuple[float, str]] = []
    for name in universe.keys():
        score = token_set_ratio(keywords, name)
        scored.append((score, name))

    scored.sort(key=lambda t: t[0], reverse=True)
    best = scored[: max(topk, 0)]

    print("Search Results:")
    for idx, (score, name) in enumerate(best, start=1):
        print(f"** Rank {idx} (score = {score:.3f}) **")
        print(f"  Name: {name}")
        print(f"  CUSIP: {universe[name]}")
        print()


def main():
    args = get_args()
    search_stock_by_name(args.data_root, args.keywords, args.quarter, topk=args.topk)


if __name__ == "__main__":
    main()
