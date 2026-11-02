import argparse

import pandas as pd

# Filing data is expected under /root/<quarter>/ (e.g., /root/2025-q3/INFOTABLE.tsv)
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

    The ranking is based on total notional VALUE summed across all line items for
    the given (ACCESSION_NUMBER, CUSIP).
    """

    cusip = cusip.upper().strip()

    infotable = pd.read_csv(f"{data_root}/{quarter}/INFOTABLE.tsv", sep="\t", dtype=str)
    infotable = infotable[infotable["CUSIP"].astype(str).str.upper() == cusip].copy()

    if infotable.empty:
        print(f"No holdings found for CUSIP {cusip} in quarter {quarter}")
        return

    infotable["VALUE"] = pd.to_numeric(infotable["VALUE"], errors="coerce").fillna(0.0)

    topk_df = (
        infotable.groupby("ACCESSION_NUMBER", as_index=False)
        .agg(TOTAL_VALUE=("VALUE", "sum"))
        .sort_values("TOTAL_VALUE", ascending=False)
        .head(topk)
    )

    # Join to coverpage to show manager names.
    coverpage = pd.read_csv(f"{data_root}/{quarter}/COVERPAGE.tsv", sep="\t", dtype=str)
    coverpage = coverpage[coverpage.get("ISAMENDMENT", "N") == "N"].copy()
    coverpage = coverpage.drop_duplicates(subset=["ACCESSION_NUMBER"], keep="first")

    topk_df = topk_df.merge(
        coverpage[["ACCESSION_NUMBER", "FILINGMANAGER_NAME"]],
        how="left",
        on="ACCESSION_NUMBER",
    )

    print(f"Top-{topk_df.shape[0]} fund managers holding CUSIP {cusip} in quarter {quarter}:")
    for idx, row in enumerate(topk_df.itertuples(index=False), start=1):
        manager = row.FILINGMANAGER_NAME if isinstance(row.FILINGMANAGER_NAME, str) else "(unknown)"
        print(
            f"Rank {idx}: {manager} | accession number = {row.ACCESSION_NUMBER}, "
            f"Holding value = {row.TOTAL_VALUE:.2f}"
        )


if __name__ == "__main__":
    args = get_args()
    topk_managers(args.cusip, args.quarter, args.topk)
