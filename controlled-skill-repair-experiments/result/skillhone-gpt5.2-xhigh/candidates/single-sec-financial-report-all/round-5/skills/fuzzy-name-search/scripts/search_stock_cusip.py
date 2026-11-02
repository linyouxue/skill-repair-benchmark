#!/usr/bin/env python3

"""Fuzzy search stock CUSIPs by issuer name in INFOTABLE.tsv.

Dependency-light (standard library only).

Inputs are expected as TSV files under:
  <DATA_ROOT>/<quarter>/INFOTABLE.tsv

Where DATA_ROOT defaults to /root and can be overridden with SEC_13F_DATA_ROOT.

The script:
- Filters to common-equity rows by TITLEOFCLASS heuristics
- Excludes options when the PUTCALL column exists
- De-duplicates by CUSIP
- Fuzzy matches NAMEOFISSUER against the query
"""

import argparse
import csv
import os
from typing import Dict, List, Tuple

# Dataset root. By default the tasks place quarterly folders under /root/<quarter>/
DATA_ROOT = os.environ.get("SEC_13F_DATA_ROOT", "/root")

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
    parser = argparse.ArgumentParser(description="Fuzzy search stock CUSIP by issuer name")
    parser.add_argument("--keywords", type=str, required=True, help="Issuer name / keywords to search for")
    parser.add_argument("--quarter", type=str, required=True, help="Quarter to search in, e.g. 2025-q3")
    parser.add_argument("--topk", type=int, default=10, help="The maximum number of results to return")
    return parser.parse_args()


def _read_tsv(path: str) -> List[Dict[str, str]]:
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        return list(reader)


def _normalize(s: str) -> str:
    s = (s or "").lower().strip()
    out = []
    prev_space = False
    for ch in s:
        if ch.isalnum():
            out.append(ch)
            prev_space = False
        else:
            if not prev_space:
                out.append(" ")
                prev_space = True
    return "".join(out).strip()


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    if len(a) > len(b):
        a, b = b, a
    prev = list(range(len(a) + 1))
    for i, cb in enumerate(b, start=1):
        cur = [i]
        for j, ca in enumerate(a, start=1):
            ins = cur[j - 1] + 1
            delete = prev[j] + 1
            sub = prev[j - 1] + (0 if ca == cb else 1)
            cur.append(min(ins, delete, sub))
        prev = cur
    return prev[-1]


def _similarity(a: str, b: str) -> float:
    a_n = _normalize(a)
    b_n = _normalize(b)
    if not a_n and not b_n:
        return 100.0
    if not a_n or not b_n:
        return 0.0
    dist = _levenshtein(a_n, b_n)
    max_len = max(len(a_n), len(b_n))
    return 100.0 * (1.0 - dist / max_len) if max_len else 100.0


def _is_common_equity_row(row: Dict[str, str]) -> bool:
    title = (row.get("TITLEOFCLASS") or "").strip().lower()
    if title and title not in TITLE_CLASS_OF_STOCKS:
        return False

    if "PUTCALL" in row:
        pc = (row.get("PUTCALL") or "").strip().upper()
        if pc:
            return False

    return True


def _load_common_equity_cusips(quarter: str) -> Dict[str, str]:
    """Return mapping CUSIP -> normalized issuer name (lowercase)."""
    path = os.path.join(DATA_ROOT, quarter, "INFOTABLE.tsv")
    rows = _read_tsv(path)

    m: Dict[str, str] = {}
    for r in rows:
        if not _is_common_equity_row(r):
            continue
        cusip = (r.get("CUSIP") or "").strip().upper()
        if not cusip:
            continue
        if cusip in m:
            continue
        name = (r.get("NAMEOFISSUER") or "").strip().lower()
        m[cusip] = name
    return m


def search_stock_by_name(keywords: str, quarter: str, topk: int = 10):
    stocks = _load_common_equity_cusips(quarter)
    if not stocks:
        print(f"No stock rows found in quarter {quarter}")
        return

    scored: List[Tuple[str, str, float]] = []
    # (cusip, name, score)
    for cusip, name in stocks.items():
        scored.append((cusip, name, _similarity(keywords, name)))

    scored.sort(key=lambda x: x[2], reverse=True)

    print("Search Results:")
    for idx, (cusip, name, score) in enumerate(scored[:topk], start=1):
        print(f"** Rank {idx} (score = {score:.3f}) **")
        print(f"  Name: {name}")
        print(f"  CUSIP: {cusip}")
        print()


if __name__ == "__main__":
    args = get_args()
    search_stock_by_name(args.keywords, quarter=args.quarter, topk=args.topk)
