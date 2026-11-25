import argparse
import re

import pandas as pd


data_root = "/root"


def get_args():
    parser = argparse.ArgumentParser(description="Analyze fund holdings information")
    parser.add_argument("--cusip", type=str, required=True, help="The CUSIP of the stock to analyze")
    parser.add_argument("--quarter", type=str, required=True, help="The quarter to analyze")
    parser.add_argument("--topk", type=int, default=10, help="The maximum number of results to return")
    parser.add_argument(
        "--equity_only",
        action="store_true",
        help="If set, exclude option rows (PUT/CALL) when the dataset has a Put/Call column",
    )
    args = parser.parse_args()
    return args


def _find_putcall_col(df: pd.DataFrame):
    for c in df.columns:
        if re.search(r"put\s*call|putcall", c, re.I):
            return c
    return None


def topk_managers(cusip: str, quarter: str, topk: int, equity_only: bool = False):
    """Find top-k fund managers holding the given stock CUSIP in the specified quarter."""
    infotable_path = f"{data_root}/{quarter}/INFOTABLE.tsv"
    coverpage_path = f"{data_root}/{quarter}/COVERPAGE.tsv"

    infotable = pd.read_csv(infotable_path, sep="\t", dtype=str)
    # Normalize
    if "VALUE" in infotable.columns:
        infotable["VALUE"] = pd.to_numeric(infotable["VALUE"], errors="coerce").fillna(0.0)
    else:
        raise KeyError(f"INFOTABLE missing VALUE column: {infotable_path}")

    if "CUSIP" not in infotable.columns or "ACCESSION_NUMBER" not in infotable.columns:
        raise KeyError(f"INFOTABLE missing required columns (CUSIP, ACCESSION_NUMBER): {infotable_path}")

    infotable["CUSIP"] = infotable["CUSIP"].astype(str).str.upper().str.strip()
    target_cusip = str(cusip).upper().strip()

    holding_details = infotable[infotable["CUSIP"] == target_cusip].copy()

    # Optionally exclude options
    putcall_col = _find_putcall_col(holding_details)
    if equity_only and putcall_col is not None:
        pc = holding_details[putcall_col].astype(str).str.upper().str.strip()
        holding_details = holding_details[~pc.isin(["PUT", "CALL"])].copy()

    topk_df = (
        holding_details.groupby("ACCESSION_NUMBER", as_index=False)
        .agg(
            TOTAL_VALUE=("VALUE", "sum"),
        )
        .sort_values("TOTAL_VALUE", ascending=False)
        .head(topk)
    )

    # Map accession -> manager name (best-effort)
    manager_name_map = {}
    try:
        coverpage = pd.read_csv(coverpage_path, sep="\t", dtype=str)
        if "ACCESSION_NUMBER" in coverpage.columns and "FILINGMANAGER_NAME" in coverpage.columns:
            manager_name_map = dict(
                zip(
                    coverpage["ACCESSION_NUMBER"].astype(str),
                    coverpage["FILINGMANAGER_NAME"].astype(str),
                )
            )
    except Exception:
        manager_name_map = {}

    label = "equity-only" if (equity_only and putcall_col is not None) else "all rows"
    print(f"Top-{topk_df.shape[0]} fund managers holding CUSIP {target_cusip} in quarter {quarter} ({label}):")
    for idx, row in topk_df.reset_index(drop=True).iterrows():
        accession_number = row["ACCESSION_NUMBER"]
        total_value = row["TOTAL_VALUE"]
        mgr_name = manager_name_map.get(str(accession_number), "<UNKNOWN_MANAGER>")
        print(
            f"Rank {idx+1}: manager = {mgr_name}, accession number = {accession_number}, Holding value = {total_value:.2f}"
        )


if __name__ == "__main__":
    args = get_args()
    topk_managers(args.cusip, args.quarter, args.topk, equity_only=args.equity_only)
