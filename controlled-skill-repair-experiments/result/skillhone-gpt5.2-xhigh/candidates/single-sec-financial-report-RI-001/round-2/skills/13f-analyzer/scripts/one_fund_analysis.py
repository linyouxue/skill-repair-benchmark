import argparse
import os
from typing import Optional, Sequence

import pandas as pd

# The dataset is expected to live under DATA_ROOT/<quarter>/, e.g. /root/2025-q3/INFOTABLE.tsv
DATA_ROOT_DEFAULT = os.environ.get("SEC13F_DATA_ROOT", "/root")

# Keep this list explicit: it defines the stock universe used by this helper.
# Normalize TITLEOFCLASS with: .str.lower().str.strip() before matching.
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


def get_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze grouped fund holdings information")
    parser.add_argument(
        "--accession_number",
        type=str,
        required=True,
        help="The accession number of the fund to analyze",
    )
    parser.add_argument("--quarter", type=str, required=True, help="The quarter of the fund to analyze")

    parser.add_argument(
        "--baseline_quarter",
        type=str,
        default=None,
        required=False,
        help="The baseline quarter for comparison",
    )
    parser.add_argument(
        "--baseline_accession_number",
        type=str,
        default=None,
        required=False,
        help="The baseline accession number for comparison",
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


def read_one_quarter_data(accession_number: str, quarter: str, data_root: str) -> pd.DataFrame:
    """Read and process one quarter data for a given accession number.

    Returns a CUSIP-level dataframe with columns: CUSIP, NAMEOFISSUER, TITLEOFCLASS, VALUE.
    """

    path = f"{data_root}/{quarter}/INFOTABLE.tsv"
    infotable = pd.read_csv(path, sep="\t", dtype=str)
    _require_columns(
        infotable,
        ["ACCESSION_NUMBER", "CUSIP", "NAMEOFISSUER", "TITLEOFCLASS", "VALUE"],
        source=path,
    )

    infotable = infotable[infotable["ACCESSION_NUMBER"] == accession_number].copy()

    print(f"Summary stats for quarter: {quarter}, accession_number: {accession_number}")
    print(f"- Total number of holdings: {infotable.shape[0]}")

    if infotable.empty:
        print(f"ERROR: No data found for ACCESSION_NUMBER = {accession_number} in quarter {quarter}")
        raise SystemExit(1)

    infotable["VALUE"] = infotable["VALUE"].astype(float)
    print(f"- Total AUM: {infotable['VALUE'].sum():.2f}")

    title_norm = infotable["TITLEOFCLASS"].fillna("").astype(str).str.lower().str.strip()
    stock_infotable = infotable[title_norm.isin(TITLE_CLASS_OF_STOCKS)].copy()

    print(f"- Number of stock holdings: {stock_infotable.shape[0]}")
    print(f"- Total stock AUM: {stock_infotable['VALUE'].sum():.2f}")

    if stock_infotable.empty:
        print(
            f"ERROR: No stock holdings found after TITLEOFCLASS filter for ACCESSION_NUMBER = {accession_number} in quarter {quarter}"
        )
        raise SystemExit(1)

    stock = (
        stock_infotable.groupby("CUSIP", as_index=False)
        .agg(
            NAMEOFISSUER=("NAMEOFISSUER", "first"),
            TITLEOFCLASS=("TITLEOFCLASS", "first"),
            VALUE=("VALUE", "sum"),
        )
        .copy()
    )

    return stock


def one_fund_analysis(
    accession_number: str,
    quarter: str,
    baseline_accession_number: Optional[str],
    baseline_quarter: Optional[str],
    data_root: str,
) -> None:
    current = read_one_quarter_data(accession_number, quarter, data_root=data_root)

    if baseline_accession_number is None and baseline_quarter is None:
        return

    if not baseline_accession_number or not baseline_quarter:
        print("ERROR: baseline_quarter and baseline_accession_number must be provided together")
        raise SystemExit(2)

    print(f"Performing comparative analysis using baseline quarter {baseline_quarter}")
    baseline = read_one_quarter_data(baseline_accession_number, baseline_quarter, data_root=data_root)

    merged = pd.merge(current, baseline, how="outer", on="CUSIP", suffixes=("", "_base"))

    # Analyze changes
    merged["VALUE"] = merged["VALUE"].fillna(0.0)
    merged["VALUE_base"] = merged["VALUE_base"].fillna(0.0)
    merged["NAMEOFISSUER"] = merged["NAMEOFISSUER"].fillna(merged["NAMEOFISSUER_base"])

    merged["ABS_CHANGE"] = merged["VALUE"] - merged["VALUE_base"]

    # Print top buy and sell. Rank by dollar-value change (VALUE) only.
    print(f"Top 10 Buys from {baseline_quarter} to {quarter}:")
    top_buys = merged[merged["ABS_CHANGE"] > 0].sort_values(by="ABS_CHANGE", ascending=False).head(10)
    for idx, row in enumerate(top_buys.itertuples(index=False), start=1):
        print(
            f"[{idx}] CUSIP: {row.CUSIP}, Name: {row.NAMEOFISSUER} | Abs change: {row.ABS_CHANGE:.2f}"
        )

    print(f"\nTop 10 Sells from {baseline_quarter} to {quarter}:")
    top_sells = merged[merged["ABS_CHANGE"] < 0].sort_values(by="ABS_CHANGE", ascending=True).head(10)
    for idx, row in enumerate(top_sells.itertuples(index=False), start=1):
        print(
            f"[{idx}] CUSIP: {row.CUSIP}, Name: {row.NAMEOFISSUER} | Abs change: {row.ABS_CHANGE:.2f}"
        )


if __name__ == "__main__":
    args = get_args()
    one_fund_analysis(
        args.accession_number,
        args.quarter,
        args.baseline_accession_number,
        args.baseline_quarter,
        data_root=args.data_root,
    )
