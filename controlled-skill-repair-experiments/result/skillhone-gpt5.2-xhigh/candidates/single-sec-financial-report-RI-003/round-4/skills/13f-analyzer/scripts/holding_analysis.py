import argparse
import csv
import os
from collections import defaultdict
from typing import Iterable

# Filing data is expected under /root/<quarter>/
# Allow override for local testing / alternate layouts.
data_root = os.environ.get("SEC13F_DATA_ROOT", "/root")


def get_args():
    parser = argparse.ArgumentParser(description="Analyze fund holdings information")
    parser.add_argument("--cusip", type=str, required=True, help="The CUSIP of the stock to analyze")
    parser.add_argument("--quarter", type=str, required=True, help="The quarter to analyze")
    parser.add_argument("--topk", type=int, default=10, help="The maximum number of results to return")
    return parser.parse_args()


def _tsv_rows(path: str) -> Iterable[dict[str, str]]:
    with open(path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            yield {k: (v if v is not None else "") for k, v in row.items()}


def _parse_float(v: str) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def topk_managers(cusip: str, quarter: str, topk: int):
    """Find top-k fund managers holding the given stock CUSIP in the specified quarter.

    The result is ranked by total reported holding VALUE for that CUSIP in the
    selected quarter.
    """

    cusip = cusip.strip().upper()

    infotable_path = os.path.join(data_root, quarter, "INFOTABLE.tsv")
    if not os.path.isfile(infotable_path):
        raise SystemExit(
            f"ERROR: Missing INFOTABLE.tsv at {infotable_path}. Expected dataset under {data_root}/<quarter>/INFOTABLE.tsv"
        )

    total_value_by_acc: dict[str, float] = defaultdict(float)
    for row in _tsv_rows(infotable_path):
        row_cusip = (row.get("CUSIP") or "").strip().upper()
        if row_cusip != cusip:
            continue
        acc = (row.get("ACCESSION_NUMBER") or "").strip()
        if not acc:
            continue
        total_value_by_acc[acc] += _parse_float(row.get("VALUE", ""))

    if not total_value_by_acc:
        print(f"No holdings found for CUSIP {cusip} in quarter {quarter}")
        return

    ranked = sorted(total_value_by_acc.items(), key=lambda kv: kv[1], reverse=True)[:topk]

    # Map accession numbers to manager names via COVERPAGE.
    coverpage_path = os.path.join(data_root, quarter, "COVERPAGE.tsv")
    manager_name_by_acc: dict[str, str] = {}
    if os.path.isfile(coverpage_path):
        # Prefer non-amendment rows when available.
        best_row_by_acc: dict[str, dict[str, str]] = {}
        for row in _tsv_rows(coverpage_path):
            acc = (row.get("ACCESSION_NUMBER") or "").strip()
            if not acc or acc not in total_value_by_acc:
                continue

            # Prefer ISAMENDMENT != 'Y' when present.
            is_amend = (row.get("ISAMENDMENT") or "").strip().upper()
            amend_rank = 1 if is_amend in {"Y", "YES", "TRUE", "1"} else 0

            prev = best_row_by_acc.get(acc)
            if prev is None:
                best_row_by_acc[acc] = {**row, "_amend_rank": str(amend_rank)}
                continue

            prev_rank = 1 if (prev.get("_amend_rank") or "1") == "1" else 0
            if amend_rank < prev_rank:
                best_row_by_acc[acc] = {**row, "_amend_rank": str(amend_rank)}

        for acc, row in best_row_by_acc.items():
            manager_name_by_acc[acc] = (row.get("FILINGMANAGER_NAME") or "").strip() or "(unknown manager)"

    print(f"Top-{len(ranked)} fund managers holding CUSIP {cusip} in quarter {quarter}:")
    for idx, (acc, total_value) in enumerate(ranked, start=1):
        manager_name = manager_name_by_acc.get(acc, "(unknown manager)")
        print(f"Rank {idx}: {manager_name} | accession number = {acc}, Holding value = {total_value:.2f}")


if __name__ == "__main__":
    args = get_args()
    topk_managers(args.cusip, args.quarter, args.topk)
