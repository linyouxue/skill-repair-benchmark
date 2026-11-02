#!/usr/bin/env python3

"""Fuzzy search 13F managers in COVERPAGE.tsv.

Dependency-light (standard library only).

Inputs are expected as TSV files under:
  <DATA_ROOT>/<quarter>/COVERPAGE.tsv

Where DATA_ROOT defaults to /root and can be overridden with SEC_13F_DATA_ROOT.

The script supports:
- Fuzzy search by manager name via --keywords
- Exact lookup via --accession_number

Fuzzy matching uses a simple normalized Levenshtein similarity implementation.
"""

import argparse
import csv
import os
from typing import Dict, List, Tuple

# Dataset root. By default the tasks place quarterly folders under /root/<quarter>/
DATA_ROOT = os.environ.get("SEC_13F_DATA_ROOT", "/root")


def get_args():
    parser = argparse.ArgumentParser(description="Fuzzy search fund by name")
    parser.add_argument(
        "--keywords",
        type=str,
        default="",
        required=False,
        help="Fund name / keywords to search for",
    )
    parser.add_argument(
        "--accession_number",
        type=str,
        default="",
        help="Accession number to search for (exact match)",
    )
    parser.add_argument("--quarter", type=str, required=True, help="Quarter to search in, e.g. 2025-q3")
    parser.add_argument("--topk", type=int, default=10, help="The maximum number of results to return")
    return parser.parse_args()


def _read_tsv(path: str) -> List[Dict[str, str]]:
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        return list(reader)


def _normalize(s: str) -> str:
    s = (s or "").lower().strip()
    # Cheap normalization: keep alphanumerics and spaces.
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
    """Classic Levenshtein edit distance (iterative DP, O(len(a)*len(b)))."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)

    # Ensure a is the shorter string to reduce memory.
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
    """Return similarity score in [0, 100]."""
    a_n = _normalize(a)
    b_n = _normalize(b)
    if not a_n and not b_n:
        return 100.0
    if not a_n or not b_n:
        return 0.0

    dist = _levenshtein(a_n, b_n)
    max_len = max(len(a_n), len(b_n))
    if max_len == 0:
        return 100.0
    return 100.0 * (1.0 - dist / max_len)


def _read_coverpage(quarter: str) -> List[Dict[str, str]]:
    path = os.path.join(DATA_ROOT, quarter, "COVERPAGE.tsv")
    return _read_tsv(path)


def pretty_print(matched_cover: Dict[str, str], idx: int, score: float):
    print(f"** Rank {idx+1} (score = {score:.3f}) **")
    print(f"  ACCESSION_NUMBER: {matched_cover.get('ACCESSION_NUMBER', '')}")
    print(f"  REPORTCALENDARORQUARTER: {matched_cover.get('REPORTCALENDARORQUARTER', '')}")
    print(f"  FILINGMANAGER_NAME: {matched_cover.get('FILINGMANAGER_NAME', '')}")
    print(f"  FILINGMANAGER_STREET: {matched_cover.get('FILINGMANAGER_STREET1', '')}")
    print(f"  FILINGMANAGER_CITY: {matched_cover.get('FILINGMANAGER_CITY', '')}")
    print(f"  FILINGMANAGER_STATEORCOUNTRY: {matched_cover.get('FILINGMANAGER_STATEORCOUNTRY', '')}")
    print(f"  FORM13FFILENUMBER: {matched_cover.get('FORM13FFILENUMBER', '')}")
    print()


def search_fund_by_name(keywords: str, quarter: str, topk: int = 10):
    coverpage = _read_coverpage(quarter)
    if not coverpage:
        print(f"No COVERPAGE data found for quarter {quarter}")
        return

    # Prefer non-amendments when that field exists.
    if "ISAMENDMENT" in coverpage[0]:
        coverpage = [r for r in coverpage if (r.get("ISAMENDMENT") or "").strip().upper() == "N"]

    # Compute scores per unique manager name.
    best_row_by_name: Dict[str, Dict[str, str]] = {}
    for r in coverpage:
        name = (r.get("FILINGMANAGER_NAME") or "").strip()
        if not name:
            continue
        if name not in best_row_by_name:
            best_row_by_name[name] = r

    scored: List[Tuple[str, float]] = []
    for name in best_row_by_name.keys():
        scored.append((name, _similarity(keywords, name)))

    scored.sort(key=lambda x: x[1], reverse=True)

    for idx, (name, score) in enumerate(scored[:topk]):
        pretty_print(best_row_by_name[name], idx, score)


def search_fund_by_accession_number(accession_number: str, quarter: str):
    coverpage = _read_coverpage(quarter)
    for r in coverpage:
        if (r.get("ACCESSION_NUMBER") or "").strip() == accession_number:
            pretty_print(r, 0, 100.0)
            return
    print(f"No fund found with ACCESSION_NUMBER = {accession_number} in quarter {quarter}")


if __name__ == "__main__":
    args = get_args()
    if args.accession_number:
        search_fund_by_accession_number(args.accession_number, args.quarter)
    else:
        search_fund_by_name(args.keywords, args.quarter, topk=args.topk)
