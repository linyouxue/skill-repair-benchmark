import argparse
import csv
import os
from typing import Sequence

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


def _require_columns(fieldnames: Sequence[str] | None, required: Sequence[str], source: str) -> None:
    if not fieldnames:
        raise ValueError(f"No header found in {source}")
    missing = [c for c in required if c not in fieldnames]
    if missing:
        raise KeyError(f"Missing required columns {missing} in {source}")


def _safe_float(value: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def topk_managers(cusip: str, quarter: str, topk: int, data_root: str) -> list[tuple[str, float]]:
    """Find top-k fund managers holding the given stock CUSIP in the specified quarter.

    Returns a list of (ACCESSION_NUMBER, TOTAL_VALUE) tuples.
    """

    path = f"{data_root}/{quarter}/INFOTABLE.tsv"

    cusip_norm = (cusip or "").upper().strip()

    totals: dict[str, float] = {}

    with open(path, "r", encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        _require_columns(reader.fieldnames, ["CUSIP", "ACCESSION_NUMBER", "VALUE"], source=path)

        for row in reader:
            row_cusip = (row.get("CUSIP") or "").upper().strip()
            if row_cusip != cusip_norm:
                continue

            acc = (row.get("ACCESSION_NUMBER") or "").strip()
            if not acc:
                continue

            totals[acc] = totals.get(acc, 0.0) + _safe_float((row.get("VALUE") or "").strip())

    ranked = sorted(totals.items(), key=lambda t: (-t[1], t[0]))[: max(0, int(topk))]

    print(f"Top-{len(ranked)} accession numbers holding CUSIP {cusip_norm} in quarter {quarter}:")
    for idx, (acc, total_value) in enumerate(ranked, start=1):
        print(f"Rank {idx}: accession number = {acc}, Holding value = {total_value:.2f}")

    return ranked


if __name__ == "__main__":
    args = get_args()
    topk_managers(args.cusip, args.quarter, args.topk, data_root=args.data_root)
