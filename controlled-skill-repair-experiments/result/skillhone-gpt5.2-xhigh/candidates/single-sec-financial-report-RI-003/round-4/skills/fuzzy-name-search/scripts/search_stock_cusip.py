import argparse

import pandas as pd
from rapidfuzz import fuzz, process

DATA_ROOT = "/root"

# Normalized (lowercased + stripped) values observed in INFOTABLE.TITLEOFCLASS
# that represent common-equity-like stock positions.
TITLE_CLASS_OF_STOCKS = {
    "com",
    "common stock",
    "common",
    "stock",
    "equity",
    "cmn",
    "com new",
    "com cl a",
    "com shs",
    "cl a",
    "class a",
    "cl b",
    "ord shs",
    "shs cl a",
    "cl a com",
    "class a com",
    "cap stk cl a",
    "cap stk cl c",
    "comm stk",
    "cl b new",
    "cl a new",
    "foreign stock",
    "sponsored adr",
    "sponsored ads",
    "adr",
}


def get_args():
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
        default="",
        required=False,
        help="Quarter to search in (defaults to 2025-q2 if omitted)",
    )
    parser.add_argument(
        "--topk",
        type=int,
        default=10,
        help="The maximum number of results to return",
    )
    return parser.parse_args()


def search_stock_by_name(keywords: str, topk: int = 5, quarter: str = ""):
    """Fuzzy search stock information by issuer name.

    Reads quarter-specific INFOTABLE and filters to stock-like TITLEOFCLASS.
    """
    if not quarter:
        quarter = "2025-q2"

    infotable = pd.read_csv(f"{DATA_ROOT}/{quarter}/INFOTABLE.tsv", sep="\t", dtype=str)[
        ["CUSIP", "NAMEOFISSUER", "TITLEOFCLASS"]
    ]
    title_norm = infotable["TITLEOFCLASS"].fillna("").astype(str).str.lower().str.strip()
    stocks = infotable[title_norm.isin(TITLE_CLASS_OF_STOCKS)].copy()

    stocks["CUSIP"] = stocks["CUSIP"].astype(str).str.upper()
    stocks["NAMEOFISSUER"] = stocks["NAMEOFISSUER"].fillna("").astype(str).str.lower().str.strip()

    stocks = stocks.drop_duplicates(subset=["CUSIP"])

    choices = stocks["NAMEOFISSUER"].tolist()
    matches = process.extract(keywords.lower(), choices, scorer=fuzz.WRatio, limit=topk)

    print("Search Results:")
    for idx, (match_name, score, _) in enumerate(matches, start=1):
        matched_rows = stocks[stocks["NAMEOFISSUER"] == match_name]
        if matched_rows.empty:
            continue
        matched = matched_rows.iloc[0]
        print(f"** Rank {idx} (score = {score:.3f}) **")
        print(f"  Name: {match_name}")
        print(f"  CUSIP: {matched['CUSIP']}")
        print()


if __name__ == "__main__":
    args = get_args()
    search_stock_by_name(args.keywords, topk=args.topk, quarter=args.quarter)
