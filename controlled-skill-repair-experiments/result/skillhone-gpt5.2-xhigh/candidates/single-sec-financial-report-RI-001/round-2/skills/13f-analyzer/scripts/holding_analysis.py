import argparse
import os
from typing import Sequence

import pandas as pd

# The dataset is expected to live under DATA_ROOT/<quarter>/, e.g. /root/2025-q3/INFOTABLE.tsv
DATA_ROOT_DEFAULT = os.environ.get("SEC13F_DATA_ROOT", "/root")


def get_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze fund holdings information")
    parser.add_argument("--cusip", type=str, required=True, help="The CUSIP of the stock to analyze")
    parser.add_argument("--quarter", type=str, required=True, help="The quarter to analyze")
    parser.add_argument("--topk", type=int, default=10, help="The maximum number of results to return")
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


def topk_managers(cusip: str, quarter: str, topk: int, data_root: str) -> pd.DataFrame:
    """Find top-k fund managers holding the given stock CUSIP in the specified quarter."""

    path = f"{data_root}/{quarter}/INFOTABLE.tsv"
    infotable = pd.read_csv(path, sep="\t", dtype=str)
    _require_columns(infotable, ["CUSIP", "ACCESSION_NUMBER", "VALUE"], source=path)

    # Normalize
    infotable["CUSIP"] = infotable["CUSIP"].astype(str).str.upper().str.strip()
    cusip_norm = cusip.upper().strip()

    infotable["VALUE"] = infotable["VALUE"].astype(float)
    holding_details = infotable[infotable["CUSIP"] == cusip_norm]

    result = (
        holding_details.groupby("ACCESSION_NUMBER", as_index=False)
        .agg(TOTAL_VALUE=("VALUE", "sum"))
        .sort_values("TOTAL_VALUE", ascending=False)
        .head(topk)
    )

    print(f"Top-{result.shape[0]} accession numbers holding CUSIP {cusip_norm} in quarter {quarter}:")
    for idx, row in enumerate(result.itertuples(index=False), start=1):
        print(f"Rank {idx}: accession number = {row.ACCESSION_NUMBER}, Holding value = {row.TOTAL_VALUE:.2f}")

    return result


if __name__ == "__main__":
    args = get_args()
    topk_managers(args.cusip, args.quarter, args.topk, data_root=args.data_root)
