import argparse
import os
import sys

# Allow running this script directly without installing the repo as a package.
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from skills._shared.tsv_utils import iter_tsv, safe_float


data_root = "/root"


def get_args():
    parser = argparse.ArgumentParser(description="Analyze fund holdings information")
    parser.add_argument("--cusip", type=str, required=True, help="The CUSIP of the stock to analyze")
    parser.add_argument("--quarter", type=str, required=True, help="The quarter to analyze")
    parser.add_argument("--topk", type=int, default=10, help="The maximum number of results to return")
    args = parser.parse_args()
    return args


def _accession_to_manager_name(quarter: str):
    cover_path = f"{data_root}/{quarter}/COVERPAGE.tsv"

    # Prefer non-amendment filings when possible.
    rows = list(iter_tsv(cover_path))
    if rows and any("ISAMENDMENT" in r for r in rows):
        rows = [r for r in rows if (r.get("ISAMENDMENT") or "N") == "N"]

    name_map = {}
    for r in rows:
        acc = r.get("ACCESSION_NUMBER")
        name = (r.get("FILINGMANAGER_NAME") or "").strip()
        if acc and acc not in name_map:
            name_map[acc] = name
    return name_map


def topk_managers(cusip, quarter, topk):
    """Find top-k fund managers holding a given CUSIP for a quarter."""
    target = (cusip or "").upper().strip()
    info_path = f"{data_root}/{quarter}/INFOTABLE.tsv"

    acc_value = {}
    for row in iter_tsv(info_path):
        if (row.get("CUSIP") or "").upper().strip() != target:
            continue
        acc = (row.get("ACCESSION_NUMBER") or "").strip()
        if not acc:
            continue
        v = safe_float(row.get("VALUE", ""), 0.0)
        acc_value[acc] = acc_value.get(acc, 0.0) + v

    name_map = _accession_to_manager_name(quarter)

    ranked = sorted(acc_value.items(), key=lambda kv: kv[1], reverse=True)[: max(0, int(topk))]

    print(f"Top-{len(ranked)} fund managers holding CUSIP {target} in quarter {quarter}:")
    for idx, (acc, total_value) in enumerate(ranked):
        manager_name = name_map.get(acc) or "<unknown>"
        print(
            f"Rank {idx+1}: manager = {manager_name} | accession number = {acc} | Holding value = {total_value:.2f}"
        )


if __name__ == "__main__":
    args = get_args()
    topk_managers(args.cusip, args.quarter, args.topk)
