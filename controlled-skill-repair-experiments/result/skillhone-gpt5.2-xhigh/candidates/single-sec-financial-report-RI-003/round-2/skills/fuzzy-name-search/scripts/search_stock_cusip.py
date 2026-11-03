import argparse
import os
import re
from typing import Iterable

import pandas as pd
from rapidfuzz import fuzz, process

# Filing data is expected under /root/<quarter>/
data_root = "/root"

# A pragmatic allow-list of common-equity TITLEOFCLASS values.
# Values are compared case-insensitively after stripping.
title_class_of_stocks = {
    "com",
    "common",
    "common stock",
    "stock",
    "class a",
    "class a com",
    "class b",
    "cl a",
    "cl a com",
    "cl a new",
    "cl b",
    "cl b new",
    "cmn",
    "com cl a",
    "com new",
    "com shs",
    "comm stk",
    "cap stk cl a",
    "cap stk cl c",
    "foreign stock",
    "ord shs",
    "sponsored adr",
    "sponsored ads",
    "adr",
    "equity",
    "shs cl a",
}


def get_args():
    parser = argparse.ArgumentParser(description="Fuzzy search stock CUSIP by issuer name")
    parser.add_argument(
        "--keywords",
        type=str,
        required=True,
        help="Issuer name / keywords to search for",
    )
    parser.add_argument(
        "--quarter",
        type=str,
        default="",
        required=False,
        help=(
            "Quarter to search in (e.g., 2025-q3). "
            "If omitted, the helper scans all available /root/<quarter>/INFOTABLE.tsv datasets."
        ),
    )
    parser.add_argument(
        "--topk",
        type=int,
        default=10,
        help="The maximum number of results to return",
    )
    return parser.parse_args()


def _is_common_equity_position(df: pd.DataFrame) -> pd.Series:
    """Return a boolean mask for common-equity (non-option) rows."""

    title = df["TITLEOFCLASS"].fillna("").astype(str).str.lower().str.strip()
    mask = title.isin(title_class_of_stocks)

    if "PUTCALL" in df.columns:
        putcall = df["PUTCALL"].fillna("").astype(str).str.strip().str.upper()
        mask &= putcall.eq("")

    return mask


def _discover_quarters(root: str) -> list[str]:
    """Return a sorted list of quarter directory names under root."""

    quarter_re = re.compile(r"^\d{4}-q[1-4]$", re.IGNORECASE)
    quarters: list[str] = []
    try:
        for name in os.listdir(root):
            if not quarter_re.match(name):
                continue
            if os.path.isfile(os.path.join(root, name, "INFOTABLE.tsv")):
                quarters.append(name)
    except FileNotFoundError:
        return []

    return sorted(quarters)


def _iter_quarters(requested_quarter: str) -> Iterable[str]:
    if requested_quarter:
        return [requested_quarter]
    return _discover_quarters(data_root)


def _load_stock_universe(quarters: Iterable[str]) -> pd.DataFrame:
    """Load a CUSIP/name universe from one or more quarters."""

    frames: list[pd.DataFrame] = []
    for q in quarters:
        path = os.path.join(data_root, q, "INFOTABLE.tsv")
        if not os.path.isfile(path):
            continue

        # Read only the columns we need.
        df = pd.read_csv(path, sep="\t", dtype=str, usecols=lambda c: c in {"CUSIP", "NAMEOFISSUER", "TITLEOFCLASS", "PUTCALL"})
        if df.empty:
            continue

        df = df[_is_common_equity_position(df)].copy()
        df["CUSIP"] = df["CUSIP"].fillna("").astype(str).str.upper().str.strip()
        df["NAMEOFISSUER"] = df["NAMEOFISSUER"].fillna("").astype(str).str.lower().str.strip()
        df = df[(df["CUSIP"] != "") & (df["NAMEOFISSUER"] != "")]
        frames.append(df[["CUSIP", "NAMEOFISSUER"]])

    if not frames:
        return pd.DataFrame(columns=["CUSIP", "NAMEOFISSUER"]).astype(str)

    stocks = pd.concat(frames, ignore_index=True)

    # De-duplicate: keep unique (CUSIP, issuer) pairs, then group by issuer.
    stocks = stocks.drop_duplicates(subset=["CUSIP", "NAMEOFISSUER"])
    return stocks


def search_stock_by_name(keywords: str, topk: int = 10, quarter: str = ""):
    """Fuzzy-search a stock issuer name and print candidate common-equity CUSIPs."""

    quarters = list(_iter_quarters(quarter))
    if not quarters:
        raise SystemExit(
            "ERROR: No quarter datasets found under /root. Expected /root/<quarter>/INFOTABLE.tsv (e.g., /root/2025-q3/INFOTABLE.tsv)."
        )

    stocks = _load_stock_universe(quarters)
    if stocks.empty:
        raise SystemExit("ERROR: No common-equity rows found in the available INFOTABLE datasets.")

    # Map issuer name -> list of CUSIPs so we can avoid printing duplicate issuer matches.
    issuer_to_cusips = (
        stocks.groupby("NAMEOFISSUER")["CUSIP"].apply(lambda s: sorted(set(s))).to_dict()
    )

    choices = list(issuer_to_cusips.keys())
    matches = process.extract(keywords.lower().strip(), choices, scorer=fuzz.WRatio, limit=topk)

    quarter_desc = quarter if quarter else ", ".join(quarters)
    print(f"Search Results (quarters scanned: {quarter_desc}):")
    for idx, (match_name, score, _) in enumerate(matches, start=1):
        cusips = issuer_to_cusips.get(match_name, [])
        if not cusips:
            continue
        print(f"** Rank {idx} (score = {score:.3f}) **")
        print(f"  Name: {match_name}")
        if len(cusips) == 1:
            print(f"  CUSIP: {cusips[0]}")
        else:
            print("  CUSIPs:")
            for c in cusips:
                print(f"    - {c}")
        print()


if __name__ == "__main__":
    args = get_args()
    search_stock_by_name(args.keywords, topk=args.topk, quarter=args.quarter)
