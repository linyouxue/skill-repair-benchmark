import argparse
from pathlib import Path

import pandas as pd
from rapidfuzz import fuzz, process

DATA_ROOT = "/root"

# Keep this list aligned with 13f-analyzer/one_fund_analysis.py.
# It defines the conservative common-equity TITLEOFCLASS universe.
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


def get_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fuzzy search a stock CUSIP by issuer name")
    parser.add_argument(
        "--keywords",
        type=str,
        required=True,
        help="Stock/issuer name or keywords to search for",
    )
    parser.add_argument(
        "--topk",
        type=int,
        default=10,
        help="The maximum number of results to return",
    )
    parser.add_argument(
        "--quarter",
        type=str,
        default=None,
        help=(
            "Optional quarter to search in (e.g., 2025-q3). If omitted, the helper searches across all "
            "available /root/<quarter>/INFOTABLE.tsv files."
        ),
    )
    parser.add_argument(
        "--include_options",
        action="store_true",
        help=(
            "Include option rows (PUT/CALL) if present. By default the helper excludes rows where PUTCALL is set, "
            "so the returned CUSIPs reflect common-equity positions."
        ),
    )
    return parser.parse_args()


def _normalize_titleofclass(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.strip().str.lower()


def _is_blank(series: pd.Series) -> pd.Series:
    return series.isna() | (series.astype(str).str.strip() == "")


def _discover_quarters(data_root: str) -> list[str]:
    root = Path(data_root)
    if not root.exists():
        return []

    quarters: list[str] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        infotable = child / "INFOTABLE.tsv"
        if infotable.exists():
            quarters.append(child.name)
    return quarters


def _load_stock_universe(quarters: list[str], include_options: bool) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for quarter in quarters:
        path = Path(DATA_ROOT) / quarter / "INFOTABLE.tsv"
        df = pd.read_csv(path, sep="\t", dtype=str)

        required = {"CUSIP", "NAMEOFISSUER", "TITLEOFCLASS"}
        missing = required - set(df.columns)
        if missing:
            raise SystemExit(f"ERROR: Missing columns {sorted(missing)} in {path}")

        cols = ["CUSIP", "NAMEOFISSUER", "TITLEOFCLASS"]
        if "PUTCALL" in df.columns:
            cols.append("PUTCALL")

        df = df[cols].copy()
        df["QUARTER"] = quarter
        frames.append(df)

    if not frames:
        raise SystemExit("ERROR: No INFOTABLE.tsv files found to build a stock universe")

    stocks = pd.concat(frames, ignore_index=True)

    # Conservative common-equity filter.
    stocks = stocks[_normalize_titleofclass(stocks["TITLEOFCLASS"]).isin(TITLE_CLASS_OF_STOCKS)]

    if not include_options and "PUTCALL" in stocks.columns:
        stocks = stocks[_is_blank(stocks["PUTCALL"])]

    stocks["CUSIP"] = stocks["CUSIP"].fillna("").astype(str).str.strip().str.upper()
    stocks["NAMEOFISSUER"] = stocks["NAMEOFISSUER"].fillna("").astype(str).str.strip().str.lower()

    stocks = stocks[stocks["CUSIP"] != ""]

    # One canonical issuer-name per CUSIP.
    stocks = stocks.drop_duplicates(subset=["CUSIP"], keep="first").reset_index(drop=True)

    return stocks


def search_stock_by_name(keywords: str, topk: int = 10, quarter: str | None = None, include_options: bool = False) -> None:
    # Build the stock universe from one or more quarters.
    if quarter:
        quarters = [quarter]
    else:
        quarters = _discover_quarters(DATA_ROOT)

    if not quarters:
        raise SystemExit(
            "ERROR: Could not discover any quarters under /root. Provide --quarter explicitly (e.g., --quarter 2025-q3)."
        )

    stocks = _load_stock_universe(quarters, include_options=include_options)

    choices = stocks["NAMEOFISSUER"].tolist()
    matches = process.extract(keywords.strip().lower(), choices, scorer=fuzz.WRatio, limit=topk)

    print("Search Results:")
    for rank, (match_name, score, match_idx) in enumerate(matches, start=1):
        matched = stocks.iloc[int(match_idx)]
        print(f"** Rank {rank} (score = {score:.3f}) **")
        print(f"  Name: {match_name}")
        print(f"  CUSIP: {matched['CUSIP']}")
        if quarter is None:
            print(f"  Quarter (sampled from): {matched['QUARTER']}")
        print()


if __name__ == "__main__":
    args = get_args()
    search_stock_by_name(args.keywords, topk=args.topk, quarter=args.quarter, include_options=args.include_options)
