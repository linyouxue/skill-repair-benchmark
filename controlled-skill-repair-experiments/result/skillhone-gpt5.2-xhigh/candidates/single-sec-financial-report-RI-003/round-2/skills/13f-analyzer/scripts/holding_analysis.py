import argparse

import pandas as pd

# Filing data is expected under /root/<quarter>/
data_root = "/root"


def get_args():
    parser = argparse.ArgumentParser(description="Analyze fund holdings information")
    parser.add_argument("--cusip", type=str, required=True, help="The CUSIP of the stock to analyze")
    parser.add_argument("--quarter", type=str, required=True, help="The quarter to analyze")
    parser.add_argument("--topk", type=int, default=10, help="The maximum number of results to return")
    args = parser.parse_args()
    return args


def topk_managers(cusip: str, quarter: str, topk: int):
    """Find top-k fund managers holding the given stock CUSIP in the specified quarter.

    The result is ranked by total reported holding VALUE for that CUSIP in the
    selected quarter.
    """

    cusip = cusip.strip().upper()

    infotable = pd.read_csv(f"{data_root}/{quarter}/INFOTABLE.tsv", sep="\t", dtype=str)
    if "VALUE" not in infotable.columns:
        raise SystemExit(f"ERROR: Missing VALUE column in {data_root}/{quarter}/INFOTABLE.tsv")

    infotable["VALUE"] = pd.to_numeric(infotable["VALUE"], errors="coerce").fillna(0.0)
    infotable["CUSIP"] = infotable["CUSIP"].fillna("").astype(str).str.upper().str.strip()

    holding_details = infotable[infotable["CUSIP"] == cusip].copy()
    if holding_details.empty:
        print(f"No holdings found for CUSIP {cusip} in quarter {quarter}")
        return

    ranked = (
        holding_details.groupby("ACCESSION_NUMBER", as_index=False)
        .agg(TOTAL_VALUE=("VALUE", "sum"))
        .sort_values("TOTAL_VALUE", ascending=False)
        .head(topk)
    )

    # Map accession numbers to manager names via COVERPAGE.
    coverpage = pd.read_csv(f"{data_root}/{quarter}/COVERPAGE.tsv", sep="\t", dtype=str)
    coverpage = coverpage[coverpage["ACCESSION_NUMBER"].isin(ranked["ACCESSION_NUMBER"])].copy()

    # Prefer non-amendment rows when available.
    if "ISAMENDMENT" in coverpage.columns:
        coverpage["_is_amendment"] = coverpage["ISAMENDMENT"].fillna("").astype(str).str.upper()
        coverpage = coverpage.sort_values(by=["ACCESSION_NUMBER", "_is_amendment"])

    manager_name_by_acc = (
        coverpage.groupby("ACCESSION_NUMBER")["FILINGMANAGER_NAME"].first().to_dict()
        if "FILINGMANAGER_NAME" in coverpage.columns
        else {}
    )

    print(f"Top-{ranked.shape[0]} fund managers holding CUSIP {cusip} in quarter {quarter}:")
    for idx, row in enumerate(ranked.itertuples(index=False), start=1):
        accession_number = row.ACCESSION_NUMBER
        total_value = row.TOTAL_VALUE
        manager_name = manager_name_by_acc.get(accession_number, "(unknown manager)")
        print(
            f"Rank {idx}: {manager_name} | accession number = {accession_number}, Holding value = {total_value:.2f}"
        )


if __name__ == "__main__":
    args = get_args()
    topk_managers(args.cusip, args.quarter, args.topk)
