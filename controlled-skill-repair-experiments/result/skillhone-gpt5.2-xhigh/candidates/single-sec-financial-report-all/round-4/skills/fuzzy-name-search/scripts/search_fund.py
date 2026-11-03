#!/usr/bin/env python3
"""Fuzzy (or exact) search for funds/managers in COVERPAGE.tsv.

Dataset layout:
  ${DATA_ROOT}/${QUARTER}/COVERPAGE.tsv

This script prints the best matches by a simple built-in fuzzy scorer (no
third-party dependencies).
"""

from __future__ import annotations

import argparse
import csv
import os
import re
from typing import Dict, Iterable, List, Optional, Tuple

DEFAULT_DATA_ROOT = "/root"


def get_args():
    parser = argparse.ArgumentParser(description="Fuzzy search fund/manager name (COVERPAGE.tsv)")
    parser.add_argument(
        "--keywords",
        type=str,
        default="",
        required=False,
        help="Fund/manager name keywords to search for (fuzzy)",
    )
    parser.add_argument(
        "--accession_number",
        type=str,
        default="",
        help="Accession number to search for (exact)",
    )
    parser.add_argument("--quarter", type=str, required=True, help="Quarter folder name, e.g. 2025-q3")
    parser.add_argument("--topk", type=int, default=10, help="Maximum number of results to return")
    parser.add_argument(
        "--data_root",
        type=str,
        default=DEFAULT_DATA_ROOT,
        help=f"Dataset root directory (default: {DEFAULT_DATA_ROOT})",
    )
    return parser.parse_args()


def iter_tsv_rows(path: str) -> Iterable[Dict[str, str]]:
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            yield {k: (v if v is not None else "") for k, v in row.items()}


def normalize_text(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    # Keep alnum and spaces only.
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def token_set_ratio(a: str, b: str) -> float:
    """A small token-set similarity scorer (0..100).

    Inspired by fuzzywuzzy/rapidfuzz token_set_ratio but implemented locally.
    """

    a_tokens = set(normalize_text(a).split())
    b_tokens = set(normalize_text(b).split())
    if not a_tokens and not b_tokens:
        return 100.0
    if not a_tokens or not b_tokens:
        return 0.0

    intersection = a_tokens & b_tokens
    union = a_tokens | b_tokens
    return 100.0 * (len(intersection) / len(union))


def pretty_print(matched_cover: Dict[str, str], idx: int, score: float):
    print(f"** Rank {idx+1} (score = {score:.3f}) **")
    print(f"  ACCESSION_NUMBER: {matched_cover.get('ACCESSION_NUMBER')}")
    print(f"  REPORTCALENDARORQUARTER: {matched_cover.get('REPORTCALENDARORQUARTER')}")
    print(f"  FILINGMANAGER_NAME: {matched_cover.get('FILINGMANAGER_NAME')}")
    # Some datasets use STREET1/STREET2; keep behavior consistent with prior script.
    street = matched_cover.get("FILINGMANAGER_STREET1") or matched_cover.get("FILINGMANAGER_STREET")
    print(f"  FILINGMANAGER_STREET: {street}")
    print(f"  FILINGMANAGER_CITY: {matched_cover.get('FILINGMANAGER_CITY')}")
    print(f"  FILINGMANAGER_STATEORCOUNTRY: {matched_cover.get('FILINGMANAGER_STATEORCOUNTRY')}")
    print(f"  FORM13FFILENUMBER: {matched_cover.get('FORM13FFILENUMBER')}")
    print()


def load_coverpage_rows(data_root: str, quarter: str) -> List[Dict[str, str]]:
    path = os.path.join(data_root, quarter, "COVERPAGE.tsv")
    if not os.path.exists(path):
        raise SystemExit(f"COVERPAGE.tsv not found: {path}")
    return list(iter_tsv_rows(path))


def search_fund_by_accession_number(data_root: str, accession_number: str, quarter: str):
    rows = load_coverpage_rows(data_root, quarter)
    for row in rows:
        if row.get("ACCESSION_NUMBER") == accession_number:
            pretty_print(row, 0, 100.0)
            return
    print(f"No fund found with ACCESSION_NUMBER = {accession_number} in quarter {quarter}")


def search_fund_by_name(data_root: str, keywords: str, quarter: str, topk: int = 10):
    rows = load_coverpage_rows(data_root, quarter)

    # Prefer non-amendments when ISAMENDMENT is available.
    filtered = [r for r in rows if r.get("ISAMENDMENT") in ("", "N")]
    if not filtered:
        filtered = rows

    # Build one representative record per distinct manager name.
    by_name: Dict[str, Dict[str, str]] = {}
    for row in filtered:
        name = row.get("FILINGMANAGER_NAME", "")
        if name and name not in by_name:
            by_name[name] = row

    scored: List[Tuple[float, str]] = []
    for name in by_name.keys():
        score = token_set_ratio(keywords, name)
        scored.append((score, name))

    scored.sort(key=lambda t: t[0], reverse=True)
    best = scored[: max(topk, 0)]

    printed = 0
    for score, name in best:
        pretty_print(by_name[name], printed, score)
        printed += 1


def main():
    args = get_args()

    if args.accession_number:
        search_fund_by_accession_number(args.data_root, args.accession_number, args.quarter)
    else:
        search_fund_by_name(args.data_root, args.keywords, args.quarter, topk=args.topk)


if __name__ == "__main__":
    main()
