import argparse

import pandas as pd
from rapidfuzz import fuzz, process

data_root = "/root"



import os
import sys


def _load_coverpage(quarter: str) -> pd.DataFrame:
    """Load COVERPAGE.tsv for a given quarter as strings.

    Tries the canonical filename first, then a few common variants.
    """
    candidates = [
        os.path.join(data_root, quarter, "COVERPAGE.tsv"),
        os.path.join(data_root, quarter, "coverpage.tsv"),
        os.path.join(data_root, quarter, "Coverpage.tsv"),
    ]
    path = next((p for p in candidates if os.path.exists(p)), None)
    if path is None:
        raise FileNotFoundError(
            f"Coverpage file not found under {os.path.join(data_root, quarter)}. Tried: {candidates}"
        )
    return pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False)


def _col(df: pd.DataFrame, name: str, default: str = ""):
    """Safe column accessor."""
    if name not in df.columns:
        return pd.Series([default] * len(df), index=df.index)
    return df[name]

def get_args():
    parser = argparse.ArgumentParser(description="Fuzzy search fund by name")
    parser.add_argument(
        "--keywords",
        type=str,
        default="",
        required=False,
        help="The fund name or keywords to search for",
    )
    parser.add_argument(
        "--accession_number",
        type=str,
        default="",
        help="The accession number to search for",
    )
    parser.add_argument("--quarter", type=str, required=True, help="The quarter to search in")
    parser.add_argument(
        "--topk",
        type=int,
        default=10,
        help="The maximum number of results to return",
    )
    return parser.parse_args()


def pretty_print(matched_cover, idx, score):
    # tolerate missing columns
    def g(col: str) -> str:
        return str(matched_cover.get(col, ""))

    ACCESSION_NUMBER = g("ACCESSION_NUMBER")
    REPORTCALENDARORQUARTER = g("REPORTCALENDARORQUARTER")
    FILINGMANAGER_NAME = g("FILINGMANAGER_NAME")
    FILINGMANAGER_STREET1 = g("FILINGMANAGER_STREET1")
    FILINGMANAGER_CITY = g("FILINGMANAGER_CITY")
    FILINGMANAGER_STATEORCOUNTRY = g("FILINGMANAGER_STATEORCOUNTRY")
    FORM13FFILENUMBER = g("FORM13FFILENUMBER")

    print(f"** Rank {idx+1} (score = {score:.3f}) **")
    print(f"  ACCESSION_NUMBER: {ACCESSION_NUMBER}")
    print(f"  REPORTCALENDARORQUARTER: {REPORTCALENDARORQUARTER}")
    print(f"  FILINGMANAGER_NAME: {FILINGMANAGER_NAME}")
    print(f"  FILINGMANAGER_STREET: {FILINGMANAGER_STREET1}")
    print(f"  FILINGMANAGER_CITY: {FILINGMANAGER_CITY}")
    print(f"  FILINGMANAGER_STATEORCOUNTRY: {FILINGMANAGER_STATEORCOUNTRY}")
    print(f"  FORM13FFILENUMBER: {FORM13FFILENUMBER}")
    print()


def search_fund_by_name(keywords: str, quarter: str, topk: int = 5):
    """Fuzzy search fund information by name."""
    if not keywords:
        print("--keywords is required when --accession_number is not provided", file=sys.stderr)
        return

    coverpage = _load_coverpage(quarter)
    if "FILINGMANAGER_NAME" not in coverpage.columns:
        print("COVERPAGE is missing required column FILINGMANAGER_NAME", file=sys.stderr)
        return

    # Prefer non-amendment rows if ISAMENDMENT exists; otherwise search all rows.
    if "ISAMENDMENT" in coverpage.columns:
        base = coverpage[_col(coverpage, "ISAMENDMENT").astype(str).str.upper().eq("N")]
        if base.empty:
            base = coverpage
    else:
        base = coverpage

    choices = _col(base, "FILINGMANAGER_NAME").astype(str).fillna("").tolist()
    # Use stable scorer
    matches = process.extract(keywords, choices, scorer=fuzz.WRatio, limit=topk)

    for idx, (match_name, score, match_row_idx) in enumerate(matches):
        # match_row_idx corresponds to index in `choices` list; use iloc on base
        try:
            matched_cover = base.iloc[int(match_row_idx)]
        except Exception:
            # Fallback: first row with the matched name
            subset = base[_col(base, "FILINGMANAGER_NAME").astype(str) == str(match_name)]
            if subset.empty:
                continue
            matched_cover = subset.iloc[0]
        pretty_print(matched_cover, idx, float(score))


def search_fund_by_accession_number(accession_number: str, quarter: str):
    """Exact search fund information by accession_number."""
    if not accession_number:
        print("--accession_number must be non-empty", file=sys.stderr)
        return

    coverpage = _load_coverpage(quarter)
    if "ACCESSION_NUMBER" not in coverpage.columns:
        print("COVERPAGE is missing required column ACCESSION_NUMBER", file=sys.stderr)
        return

    matched_cover = coverpage[_col(coverpage, "ACCESSION_NUMBER").astype(str) == str(accession_number)]
    if matched_cover.empty:
        print(f"No fund found with ACCESSION_NUMBER = {accession_number} in quarter {quarter}")
        return

    # Print exactly one row with score=100 as required
    pretty_print(matched_cover.iloc[0], 0, 100.0)


if __name__ == "__main__":
    args = get_args()
    try:
        if args.accession_number:
            search_fund_by_accession_number(args.accession_number, args.quarter)
        else:
            search_fund_by_name(args.keywords, args.quarter, topk=args.topk)
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        sys.exit(2)
