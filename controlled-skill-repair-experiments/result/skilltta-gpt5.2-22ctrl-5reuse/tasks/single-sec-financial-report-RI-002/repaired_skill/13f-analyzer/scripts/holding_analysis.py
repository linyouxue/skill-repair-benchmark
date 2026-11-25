import argparse

import pandas as pd


data_root = "/root"

# Match the equity TITLEOFCLASS filter used by one_fund_analysis.py (do not broaden).
_TITLE_CLASS_OF_STOCKS = [
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
TITLE_CLASS_OF_STOCKS = set(s.strip().lower() for s in _TITLE_CLASS_OF_STOCKS if isinstance(s, str))


def get_args():
    parser = argparse.ArgumentParser(description="Analyze fund holdings information")
    parser.add_argument("--cusip", type=str, required=True, help="The CUSIP of the stock to analyze")
    parser.add_argument("--quarter", type=str, required=True, help="The quarter to analyze")
    parser.add_argument("--topk", type=int, default=10, help="The maximum number of results to return")
    return parser.parse_args()


def topk_managers(cusip: str, quarter: str, topk_n: int):
    """Find top-k fund managers holding the given stock CUSIP in the specified quarter.

    Ranking is by summed VALUE (as represented in the dataset) across all rows of the
    given CUSIP per ACCESSION_NUMBER, after applying the helper's intended equity
    TITLEOFCLASS filter (if TITLEOFCLASS exists).
    """

    infotable_path = f"{data_root}/{quarter}/INFOTABLE.tsv"
    coverpage_path = f"{data_root}/{quarter}/COVERPAGE.tsv"

    infotable = pd.read_csv(infotable_path, sep="\t", dtype=str)

    required_cols = {"ACCESSION_NUMBER", "CUSIP"}
    missing = [c for c in required_cols if c not in infotable.columns]
    if missing:
        raise KeyError(f"INFOTABLE missing required columns {missing} in {infotable_path}")

    # Normalize CUSIP
    infotable["CUSIP"] = infotable["CUSIP"].fillna("").astype(str).str.strip().str.upper()

    # Normalize VALUE
    if "VALUE" in infotable.columns:
        infotable["VALUE"] = pd.to_numeric(infotable["VALUE"], errors="coerce").fillna(0.0)
    else:
        infotable["VALUE"] = 0.0

    # Apply the same intended equity filter (TITLEOFCLASS), if available.
    if "TITLEOFCLASS" in infotable.columns:
        title = infotable["TITLEOFCLASS"].fillna("").astype(str).str.strip().str.lower()
        infotable = infotable[title.isin(TITLE_CLASS_OF_STOCKS)]

    target_cusip = cusip.strip().upper()
    holding_details = infotable[infotable["CUSIP"] == target_cusip]

    by_accession = (
        holding_details.groupby("ACCESSION_NUMBER", as_index=False)
        .agg(TOTAL_VALUE=("VALUE", "sum"))
        .sort_values("TOTAL_VALUE", ascending=False)
        .head(topk_n)
    )

    # Join COVERPAGE for manager names
    coverpage = pd.read_csv(coverpage_path, sep="\t", dtype=str)
    if "ACCESSION_NUMBER" not in coverpage.columns:
        raise KeyError(f"COVERPAGE missing ACCESSION_NUMBER in {coverpage_path}")

    # Keep only relevant columns when present
    keep_cols = [c for c in ["ACCESSION_NUMBER", "FILINGMANAGER_NAME", "ISAMENDMENT"] if c in coverpage.columns]
    coverpage_small = coverpage[keep_cols].copy()

    merged = by_accession.merge(
        coverpage_small,
        how="left",
        on="ACCESSION_NUMBER",
    )

    print(f"Top-{merged.shape[0]} fund managers holding CUSIP {target_cusip} in quarter {quarter}:")
    for idx, row in merged.reset_index(drop=True).iterrows():
        accession_number = row["ACCESSION_NUMBER"]
        total_value = float(row["TOTAL_VALUE"]) if pd.notna(row["TOTAL_VALUE"]) else 0.0
        manager_name = row.get("FILINGMANAGER_NAME")
        is_amendment = row.get("ISAMENDMENT")

        name_part = (
            f"manager = {manager_name}"
            if pd.notna(manager_name) and str(manager_name).strip()
            else "manager = <unknown>"
        )
        amend_part = f", ISAMENDMENT = {is_amendment}" if pd.notna(is_amendment) else ""
        print(f"Rank {idx+1}: {name_part}, accession number = {accession_number}{amend_part}, Holding value = {total_value:.2f}")


if __name__ == "__main__":
    args = get_args()
    topk_managers(args.cusip, args.quarter, args.topk)
