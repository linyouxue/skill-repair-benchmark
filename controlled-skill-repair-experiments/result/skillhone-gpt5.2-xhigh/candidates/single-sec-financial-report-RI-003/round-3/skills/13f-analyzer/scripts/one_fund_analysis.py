from __future__ import annotations

import argparse

import pandas as pd

DEFAULT_DATA_ROOT = "/root"

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
        "--topk_changes",
        type=int,
        default=10,
        help="Top-k buys/sells to print in cross-quarter analysis (default: 10)",
    )
    parser.add_argument(
        "--data_root",
        type=str,
        default=DEFAULT_DATA_ROOT,
        help=f"Root directory containing quarter folders (default: {DEFAULT_DATA_ROOT})",
    )
    return parser.parse_args()


def _load_infotable(data_root: str, quarter: str) -> pd.DataFrame:
    return pd.read_csv(f"{data_root}/{quarter}/INFOTABLE.tsv", sep="\t", dtype=str)


def _option_position_mask(infotable: pd.DataFrame) -> pd.Series:
    """Return True for rows that are options (PUT/CALL).

    SEC 13F infotables typically represent option positions using a PUTCALL
    column (values like PUT/CALL) while keeping TITLEOFCLASS as the underlying
    security class (e.g., COM). For "stock" questions we usually must exclude
    those option rows.

    If the dataset doesn't include a put/call column, returns all False.
    """

    putcall_col = None
    for candidate in ("PUTCALL", "PUT_CALL", "PUT/CALL"):
        if candidate in infotable.columns:
            putcall_col = candidate
            break

    if not putcall_col:
        return pd.Series(False, index=infotable.index)

    putcall = infotable[putcall_col].fillna("").astype(str).str.upper().str.strip()
    # Be tolerant of abbreviations.
    return putcall.isin({"PUT", "CALL", "P", "C"})


def read_one_quarter_data(data_root: str, accession_number: str, quarter: str) -> pd.DataFrame:
    """Read and process one quarter data for a given accession number.

    Returns a DataFrame indexed by CUSIP, with VALUE aggregated (summed) by CUSIP
    over *non-option stock* positions.
    """

    infotable = _load_infotable(data_root, quarter)
    infotable = infotable[infotable["ACCESSION_NUMBER"] == accession_number].copy()

    if infotable.empty:
        print(f"ERROR: No data found for ACCESSION_NUMBER = {accession_number} in quarter {quarter}")
        raise SystemExit(1)

    infotable["VALUE"] = pd.to_numeric(infotable["VALUE"], errors="coerce").fillna(0.0)
    infotable["CUSIP"] = infotable["CUSIP"].astype(str).str.upper()

    print(f"Summary stats for quarter: {quarter}, accession_number: {accession_number}")
    print(f"- Total number of holdings: {infotable.shape[0]}")
    print(f"- Total AUM: {infotable['VALUE'].sum():.2f}")

    option_mask = _option_position_mask(infotable)
    num_options = int(option_mask.sum())
    if num_options:
        print(f"- Option positions (PUT/CALL rows): {num_options}")

    title_norm = infotable["TITLEOFCLASS"].fillna("").astype(str).str.lower().str.strip()
    stock_mask = title_norm.isin(TITLE_CLASS_OF_STOCKS) & (~option_mask)
    stock_infotable = infotable[stock_mask]

    # Keep the original field name but ensure it reflects *non-option* stock rows.
    print(f"- Number of stock holdings: {stock_infotable.shape[0]}")
    print(f"- Number of unique stock CUSIPs: {stock_infotable['CUSIP'].nunique()}")
    print(f"- Total stock AUM: {stock_infotable['VALUE'].sum():.2f}")

    if stock_infotable.empty:
        print(
            "ERROR: Found fund rows but no non-option stock rows after filters for "
            f"ACCESSION_NUMBER = {accession_number} in quarter {quarter}"
        )
        raise SystemExit(1)

    stock = (
        stock_infotable.groupby("CUSIP")
        .agg(
            {
                "NAMEOFISSUER": "first",
                "TITLEOFCLASS": "first",
                "VALUE": "sum",
            }
        )
        .sort_values("VALUE", ascending=False)
    )
    return stock


def _format_pct_change(abs_change: float, base_value: float) -> str:
    if base_value == 0:
        return "N/A"
    return f"{abs_change / base_value:.2%}"


def one_fund_analysis(
    accession_number: str,
    quarter: str,
    baseline_accession_number: str | None,
    baseline_quarter: str | None,
    *,
    data_root: str = DEFAULT_DATA_ROOT,
    topk_changes: int = 10,
):
    current = read_one_quarter_data(data_root, accession_number, quarter)

    if baseline_accession_number is None and baseline_quarter is None:
        return
    if baseline_accession_number is None or baseline_quarter is None:
        print("ERROR: baseline_quarter and baseline_accession_number must be provided together")
        raise SystemExit(2)

    print(f"Performing comparative analysis using baseline quarter {baseline_quarter}")
    baseline = read_one_quarter_data(data_root, baseline_accession_number, baseline_quarter)

    # Merge on CUSIP (index) and compute value deltas.
    merged = current.merge(
        baseline,
        how="outer",
        left_index=True,
        right_index=True,
        suffixes=("", "_base"),
    )
    merged["VALUE"] = merged["VALUE"].fillna(0.0)
    merged["VALUE_base"] = merged["VALUE_base"].fillna(0.0)
    merged["NAMEOFISSUER"] = merged["NAMEOFISSUER"].fillna(merged["NAMEOFISSUER_base"])

    merged["ABS_CHANGE"] = merged["VALUE"] - merged["VALUE_base"]
    merged = merged.sort_values(by="ABS_CHANGE", ascending=False)

    print(
        f"Top {topk_changes} Buys from {baseline_quarter} to {quarter} "
        "(ranked by $ value increase, aggregated by CUSIP):"
    )
    top_buys = merged[merged["ABS_CHANGE"] > 0].head(topk_changes)
    for idx, (cusip, row) in enumerate(top_buys.iterrows(), start=1):
        pct = _format_pct_change(row["ABS_CHANGE"], row["VALUE_base"])
        print(
            f"[{idx}] CUSIP: {cusip}, Name: {row['NAMEOFISSUER']} | "
            f"ΔValue: {row['ABS_CHANGE']:.2f} (from {row['VALUE_base']:.2f} to {row['VALUE']:.2f}) | "
            f"pct change: {pct}"
        )

    print(
        f"\nTop {topk_changes} Sells from {baseline_quarter} to {quarter} "
        "(ranked by $ value decrease, aggregated by CUSIP):"
    )
    top_sells = merged[merged["ABS_CHANGE"] < 0].tail(topk_changes)[::-1]
    for idx, (cusip, row) in enumerate(top_sells.iterrows(), start=1):
        pct = _format_pct_change(row["ABS_CHANGE"], row["VALUE_base"])
        print(
            f"[{idx}] CUSIP: {cusip}, Name: {row['NAMEOFISSUER']} | "
            f"ΔValue: {row['ABS_CHANGE']:.2f} (from {row['VALUE_base']:.2f} to {row['VALUE']:.2f}) | "
            f"pct change: {pct}"
        )


if __name__ == "__main__":
    args = get_args()
    one_fund_analysis(
        args.accession_number,
        args.quarter,
        args.baseline_accession_number,
        args.baseline_quarter,
        data_root=args.data_root,
        topk_changes=args.topk_changes,
    )
