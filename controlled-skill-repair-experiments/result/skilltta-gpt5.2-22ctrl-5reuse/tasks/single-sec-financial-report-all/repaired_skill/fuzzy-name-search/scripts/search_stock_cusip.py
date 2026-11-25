import argparse
from pathlib import Path

import pandas as pd
from rapidfuzz import fuzz, process

DATA_ROOT = Path("/root")

# Conservative equity-like classes; used only as a best-effort filter.
TITLE_CLASS_OF_STOCKS = [
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
]


def _find_one(quarter_dir: Path, candidate_names: list[str]) -> Path:
    for name in candidate_names:
        hits = list(quarter_dir.rglob(name))
        if hits:
            return hits[0]
    raise FileNotFoundError(f"None of {candidate_names} found under {quarter_dir}")


def _read_table(path: Path) -> pd.DataFrame:
    p = str(path)
    if p.endswith(".parquet"):
        return pd.read_parquet(path)
    if p.endswith(".tsv"):
        return pd.read_csv(path, sep="\t", dtype=str)
    return pd.read_csv(path, dtype=str)


def _norm_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [c.strip().lower() for c in df.columns]
    return df


def _choose_default_quarter() -> str:
    # Backwards-compatible default: prefer 2025-q3 if present, else 2025-q2.
    for q in ["2025-q3", "2025-q2"]:
        if (DATA_ROOT / q).exists():
            return q
    raise FileNotFoundError("No default quarter folder found under /root (expected /root/2025-q2 or /root/2025-q3)")


def get_args():
    parser = argparse.ArgumentParser(description="Fuzzy search stock CUSIP by issuer name")
    parser.add_argument(
        "--keywords",
        type=str,
        required=True,
        help="The stock issuer name or keywords to search for",
    )
    parser.add_argument(
        "--quarter",
        type=str,
        default=None,
        required=False,
        help="Quarter to search in (e.g., 2025-q3). If omitted, defaults to 2025-q3 if it exists, else 2025-q2.",
    )
    parser.add_argument(
        "--topk",
        type=int,
        default=10,
        help="The maximum number of results to return",
    )
    return parser.parse_args()


def search_stock_by_name(keywords: str, quarter: str, topk: int = 5):
    quarter_dir = DATA_ROOT / quarter
    infotable_path = _find_one(quarter_dir, ["INFOTABLE.tsv", "INFOTABLE.csv", "INFOTABLE.parquet", "infotable.parquet"])

    df = _norm_cols(_read_table(infotable_path))

    # Required columns
    if "cusip" not in df.columns or "nameofissuer" not in df.columns:
        raise KeyError(f"INFOTABLE missing required columns. Need cusip and nameofissuer; got {sorted(df.columns)[:50]}")

    stocks = df[["cusip", "nameofissuer"] + (["titleofclass"] if "titleofclass" in df.columns else [])].copy()

    # Ignore options if possible
    if "putcall" in df.columns:
        keep_mask = df["putcall"].isna() | (df["putcall"].astype(str).str.strip() == "")
        stocks = stocks.loc[keep_mask.values]

    # Best-effort equity filter
    if "titleofclass" in stocks.columns:
        stocks = stocks[stocks["titleofclass"].astype(str).str.lower().isin(TITLE_CLASS_OF_STOCKS)]

    stocks["cusip"] = stocks["cusip"].astype(str).str.upper()
    stocks["nameofissuer"] = stocks["nameofissuer"].astype(str).str.lower()

    # Deduplicate by CUSIP (keep first name)
    stocks = stocks.dropna(subset=["cusip", "nameofissuer"]).drop_duplicates(subset=["cusip"]).reset_index(drop=True)

    if stocks.empty:
        print(f"No stock rows available for search in quarter {quarter}.")
        return

    choices = stocks["nameofissuer"].tolist()
    matches = process.extract(keywords.lower(), choices, scorer=fuzz.WRatio, limit=topk)

    print(f"Search Results (quarter={quarter}):")
    for idx, (match_name, score, _) in enumerate(matches):
        matched_row = stocks[stocks["nameofissuer"] == match_name].iloc[0]
        print(f"** Rank {idx+1} (score = {score:.3f}) **")
        print(f"  Name: {match_name}")
        print(f"  CUSIP: {matched_row['cusip']}")
        print()


if __name__ == "__main__":
    args = get_args()
    quarter = args.quarter or _choose_default_quarter()
    search_stock_by_name(args.keywords, quarter=quarter, topk=args.topk)
