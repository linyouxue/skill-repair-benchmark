import argparse
import os
import re
from typing import Optional, Sequence, Tuple

import pandas as pd
from rapidfuzz import fuzz, process

# The dataset is expected to live under DATA_ROOT/<quarter>/, e.g. /root/2025-q3/INFOTABLE.tsv
DATA_ROOT_DEFAULT = os.environ.get("SEC13F_DATA_ROOT", "/root")

# Keep this list explicit and consistent with other helpers.
TITLE_CLASS_OF_STOCKS = {
    "com",
    "com new",
    "common stock",
    "common",
    "stock",
    "class a",
    "class a com",
    "cl a",
    "cl a com",
    "cl a new",
    "cl b",
    "cl b new",
    "cap stk cl a",
    "cap stk cl c",
    "com cl a",
    "com shs",
    "comm stk",
    "cmn",
    "ord shs",
    "shs cl a",
    "foreign stock",
    "sponsored adr",
    "sponsored ads",
    "adr",
    "equity",
}

_QUARTER_RE = re.compile(r"^(?P<year>\d{4})-q(?P<q>[1-4])$", re.IGNORECASE)


def get_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fuzzy search stock CUSIP by its name")
    parser.add_argument(
        "--keywords",
        type=str,
        required=True,
        help="The stock name or keywords to search for",
    )
    parser.add_argument(
        "--quarter",
        type=str,
        default=None,
        required=False,
        help="Quarter to search within (e.g. 2025-q3). If omitted, auto-detect the latest available quarter under data_root.",
    )
    parser.add_argument(
        "--topk",
        type=int,
        default=10,
        help="The maximum number of results to return",
    )
    parser.add_argument(
        "--data_root",
        type=str,
        default=DATA_ROOT_DEFAULT,
        help="Root directory that contains <quarter>/INFOTABLE.tsv (default: /root)",
    )
    return parser.parse_args()


def _require_columns(df: pd.DataFrame, required: Sequence[str], source: str) -> None:
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise KeyError(f"Missing required columns {missing} in {source}")


def _available_quarters(data_root: str) -> list[Tuple[int, int, str]]:
    """Return available quarters as (year, q, name) tuples."""
    quarters: list[Tuple[int, int, str]] = []

    try:
        entries = os.listdir(data_root)
    except FileNotFoundError:
        return quarters

    for name in entries:
        m = _QUARTER_RE.match(name)
        if not m:
            continue
        path = os.path.join(data_root, name, "INFOTABLE.tsv")
        if not os.path.exists(path):
            continue
        quarters.append((int(m.group("year")), int(m.group("q")), name))

    return quarters


def _default_quarter(data_root: str) -> str:
    """Pick the latest available quarter if not provided."""
    candidates = _available_quarters(data_root)
    if not candidates:
        raise ValueError(
            f"Could not auto-detect a quarter under data_root={data_root!r}. "
            "Pass --quarter explicitly (e.g. 2025-q3) and ensure <quarter>/INFOTABLE.tsv exists."
        )
    candidates.sort(key=lambda t: (t[0], t[1]), reverse=True)
    return candidates[0][2]


def search_stock_by_name(keywords: str, quarter: str, topk: int, data_root: str) -> None:
    """Fuzzy search stock CUSIP by issuer name within a quarter's INFOTABLE."""

    path = f"{data_root}/{quarter}/INFOTABLE.tsv"
    infotable = pd.read_csv(path, sep="\t", dtype=str)
    _require_columns(infotable, ["CUSIP", "NAMEOFISSUER", "TITLEOFCLASS"], source=path)

    # Keep only common-equity-like positions.
    title_norm = infotable["TITLEOFCLASS"].fillna("").astype(str).str.lower().str.strip()
    stocks = infotable[title_norm.isin(TITLE_CLASS_OF_STOCKS)][["CUSIP", "NAMEOFISSUER"]].copy()

    stocks["CUSIP"] = stocks["CUSIP"].astype(str).str.upper().str.strip()
    stocks = stocks.dropna(subset=["CUSIP", "NAMEOFISSUER"]).drop_duplicates(subset=["CUSIP"])

    # Normalize names for matching.
    stocks["NAMEOFISSUER_NORM"] = stocks["NAMEOFISSUER"].astype(str).str.lower().str.strip()

    choices = stocks["NAMEOFISSUER_NORM"].tolist()
    matches = process.extract(keywords.lower(), choices, scorer=fuzz.WRatio, limit=topk)

    print(f"Search Results (quarter={quarter}):")
    for idx, (match_name, score, _) in enumerate(matches):
        matched_row = stocks[stocks["NAMEOFISSUER_NORM"] == match_name].iloc[0]
        print(f"** Rank {idx+1} (score = {score:.3f}) **")
        print(f"  Name: {matched_row['NAMEOFISSUER']}")
        print(f"  CUSIP: {matched_row['CUSIP']}")
        print()


if __name__ == "__main__":
    args = get_args()
    quarter = args.quarter or _default_quarter(args.data_root)
    search_stock_by_name(args.keywords, quarter=quarter, topk=args.topk, data_root=args.data_root)
