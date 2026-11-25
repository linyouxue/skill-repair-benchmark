import argparse

import pandas as pd


def get_args():
    parser = argparse.ArgumentParser(description="Analyze fund holdings information")
    parser.add_argument("--cusip", type=str, required=True, help="The CUSIP of the stock to analyze")
    parser.add_argument("--quarter", type=str, required=True, help="The quarter to analyze (e.g., 2025-q3)")
    parser.add_argument("--topk", type=int, default=10, help="The maximum number of results to return")
    parser.add_argument(
        "--data_root",
        type=str,
        default="/root",
        help="Dataset root directory that contains per-quarter folders (default: /root)",
    )
    args = parser.parse_args()
    return args


def _load_quarter_tables(data_root: str, quarter: str):
    infotable_path = f"{data_root}/{quarter}/INFOTABLE.tsv"
    coverpage_path = f"{data_root}/{quarter}/COVERPAGE.tsv"

    infotable = pd.read_csv(infotable_path, sep="\t", dtype=str)
    coverpage = pd.read_csv(coverpage_path, sep="\t", dtype=str)
    return infotable, coverpage


def topk_managers(cusip: str, quarter: str, topk: int, data_root: str = "/root"):
    """Find top-k fund managers holding the given stock CUSIP in the specified quarter."""

    cusip = str(cusip).strip().upper()

    infotable, coverpage = _load_quarter_tables(data_root=data_root, quarter=quarter)

    # Normalize columns used in this helper (the dataset is expected to be uppercase)
    for col in ("CUSIP", "ACCESSION_NUMBER", "VALUE"):
        if col not in infotable.columns:
            raise KeyError(f"INFOTABLE missing required column: {col}. Columns={list(infotable.columns)}")

    infotable["CUSIP"] = infotable["CUSIP"].astype(str).str.strip().str.upper()
    infotable["VALUE"] = pd.to_numeric(infotable["VALUE"], errors="coerce").fillna(0.0)

    holding_details = infotable[infotable["CUSIP"] == cusip]
    if holding_details.empty:
        print(f"Top-0 fund managers holding CUSIP {cusip} in quarter {quarter}:")
        return

    topk_df = (
        holding_details.groupby("ACCESSION_NUMBER", as_index=True)
        .agg(
            TOTAL_VALUE=("VALUE", "sum"),
        )
        .sort_values("TOTAL_VALUE", ascending=False)
        .head(topk)
    )

    # Map accession -> manager name (prefer non-amendment if available)
    if "ACCESSION_NUMBER" not in coverpage.columns or "FILINGMANAGER_NAME" not in coverpage.columns:
        raise KeyError(
            "COVERPAGE missing required columns ACCESSION_NUMBER and/or FILINGMANAGER_NAME. "
            f"Columns={list(coverpage.columns)}"
        )

    cover_use = coverpage
    if "ISAMENDMENT" in coverpage.columns:
        non_amend = coverpage[coverpage["ISAMENDMENT"].astype(str) == "N"]
        if not non_amend.empty:
            cover_use = non_amend

    acc_to_name = (
        cover_use[["ACCESSION_NUMBER", "FILINGMANAGER_NAME"]]
        .dropna(subset=["ACCESSION_NUMBER"])
        .drop_duplicates(subset=["ACCESSION_NUMBER"])
        .set_index("ACCESSION_NUMBER")["FILINGMANAGER_NAME"]
        .to_dict()
    )

    print(f"Top-{topk_df.shape[0]} fund managers holding CUSIP {cusip} in quarter {quarter}:")
    for idx, (accession_number, row) in enumerate(topk_df.iterrows()):
        total_value = float(row["TOTAL_VALUE"])
        manager_name = acc_to_name.get(accession_number, "<UNKNOWN_MANAGER>")
        print(
            f"Rank {idx+1}: manager_name = {manager_name}, accession number = {accession_number}, Holding value = {total_value:.2f}"
        )


if __name__ == "__main__":
    args = get_args()
    topk_managers(args.cusip, args.quarter, args.topk, data_root=args.data_root)
