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
    parser = argparse.ArgumentParser(description="Analyze fund holdings information")
    parser.add_argument("--cusip", type=str, required=True, help="The CUSIP of the stock to analyze")
    parser.add_argument("--quarter", type=str, required=True, help="The quarter to analyze")
    parser.add_argument("--topk", type=int, default=10, help="The maximum number of results to return")
    parser.add_argument(
        "--data_root",
        type=str,
        default=DEFAULT_DATA_ROOT,
        help=f"Root directory containing quarter folders (default: {DEFAULT_DATA_ROOT})",
    )
    return parser.parse_args()


def _option_position_mask(infotable: pd.DataFrame) -> pd.Series:
    """Return True for rows that are options (PUT/CALL)."""

    putcall_col = None
    for candidate in ("PUTCALL", "PUT_CALL", "PUT/CALL"):
        if candidate in infotable.columns:
            putcall_col = candidate
            break

    if not putcall_col:
        return pd.Series(False, index=infotable.index)

    putcall = infotable[putcall_col].fillna("").astype(str).str.upper().str.strip()
    return putcall.isin({"PUT", "CALL", "P", "C"})


def topk_managers(cusip: str, quarter: str, topk: int, *, data_root: str = DEFAULT_DATA_ROOT):
    """Find top-k fund managers holding the given stock CUSIP in the specified quarter.

    For "stock" requests, the ranking is computed using **non-option stock
    positions** (i.e., excludes PUTCALL rows when available).

    Prints manager names (from COVERPAGE) alongside accession numbers.
    """

    cusip = cusip.upper()

    infotable = pd.read_csv(f"{data_root}/{quarter}/INFOTABLE.tsv", sep="\t", dtype=str)
    infotable["VALUE"] = pd.to_numeric(infotable["VALUE"], errors="coerce").fillna(0.0)
    infotable["CUSIP"] = infotable["CUSIP"].astype(str).str.upper()

    holding_details = infotable[infotable["CUSIP"] == cusip].copy()
    if holding_details.empty:
        print(f"ERROR: No holdings found for CUSIP {cusip} in quarter {quarter}")
        raise SystemExit(1)

    option_mask = _option_position_mask(holding_details)
    title_norm = holding_details["TITLEOFCLASS"].fillna("").astype(str).str.lower().str.strip()

    stock_non_option = holding_details[title_norm.isin(TITLE_CLASS_OF_STOCKS) & (~option_mask)].copy()

    if stock_non_option.empty:
        stock_with_options = holding_details[title_norm.isin(TITLE_CLASS_OF_STOCKS)].copy()
        if not stock_with_options.empty:
            print(
                "WARNING: No non-option stock rows found for this CUSIP; "
                "falling back to stock-like rows including PUT/CALL positions."
            )
            filtered = stock_with_options
        else:
            print(
                "WARNING: No stock-like TITLEOFCLASS rows found for this CUSIP; "
                "falling back to all matching rows (may include non-stock/derivatives)."
            )
            filtered = holding_details
    else:
        filtered = stock_non_option

    ranked = (
        filtered.groupby("ACCESSION_NUMBER")
        .agg(
            TOTAL_VALUE=("VALUE", "sum"),
        )
        .sort_values("TOTAL_VALUE", ascending=False)
        .head(topk)
    )

    # Enrich with manager names from COVERPAGE where possible.
    try:
        coverpage = pd.read_csv(f"{data_root}/{quarter}/COVERPAGE.tsv", sep="\t", dtype=str)
        coverpage = coverpage[coverpage["ACCESSION_NUMBER"].isin(ranked.index)].copy()
        if "ISAMENDMENT" in coverpage.columns:
            non_amend = coverpage[coverpage["ISAMENDMENT"] == "N"]
            if not non_amend.empty:
                coverpage = non_amend
        coverpage = coverpage.drop_duplicates(subset=["ACCESSION_NUMBER"])
        name_map = coverpage.set_index("ACCESSION_NUMBER")["FILINGMANAGER_NAME"].to_dict()
    except Exception:
        name_map = {}

    print(f"Top-{ranked.shape[0]} fund managers holding CUSIP {cusip} in quarter {quarter}:")
    for idx, (accession_number, row) in enumerate(ranked.iterrows(), start=1):
        total_value = float(row["TOTAL_VALUE"])
        manager_name = name_map.get(accession_number, "")
        manager_part = f", Manager = {manager_name}" if manager_name else ""
        print(f"Rank {idx}: accession number = {accession_number}{manager_part}, Holding value = {total_value:.2f}")


if __name__ == "__main__":
    args = get_args()
    topk_managers(args.cusip, args.quarter, args.topk, data_root=args.data_root)
