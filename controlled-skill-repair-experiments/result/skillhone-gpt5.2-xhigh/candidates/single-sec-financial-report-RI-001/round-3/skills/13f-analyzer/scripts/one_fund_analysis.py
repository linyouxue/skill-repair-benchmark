import argparse
import csv
import os
from typing import Optional, Sequence

# The dataset is expected to live under DATA_ROOT/<quarter>/, e.g. /root/2025-q3/INFOTABLE.tsv
DATA_ROOT_DEFAULT = os.environ.get("SEC13F_DATA_ROOT", "/root")

# Keep this list explicit: it defines the stock universe used by this helper.
# Normalize TITLEOFCLASS with: .lower().strip() before matching.
TITLE_CLASS_OF_STOCKS = {
    "com",
    "com new",
    "common stock",
    "common",
    "stock",
    "class a",
    "class a com",
    "cl a",
    "cl a com",
    "cl a new",
    "cl b",
    "cl b new",
    "cap stk cl a",
    "cap stk cl c",
    "com cl a",
    "com shs",
    "comm stk",
    "cmn",
    "ord shs",
    "shs cl a",
    "foreign stock",
    "sponsored adr",
    "sponsored ads",
    "adr",
    "equity",
}


def get_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze grouped fund holdings information")
    parser.add_argument(
        "--accession_number",
        type=str,
        required=True,
        help="The accession number of the fund to analyze",
    )
    parser.add_argument("--quarter", type=str, required=True, help="The quarter of the fund to analyze")

    parser.add_argument(
        "--baseline_quarter",
        type=str,
        default=None,
        required=False,
        help="The baseline quarter for comparison",
    )
    parser.add_argument(
        "--baseline_accession_number",
        type=str,
        default=None,
        required=False,
        help="The baseline accession number for comparison",
    )

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


def _normalize_cusip(cusip: str) -> str:
    return (cusip or "").strip().upper()


def read_one_quarter_data(accession_number: str, quarter: str, data_root: str) -> dict[str, dict[str, object]]:
    """Read and process one quarter data for a given accession number.

    Returns a CUSIP-keyed mapping. Each value contains: CUSIP, NAMEOFISSUER,
    TITLEOFCLASS, VALUE (aggregated).
    """

    path = f"{data_root}/{quarter}/INFOTABLE.tsv"

    accession_number_norm = accession_number.strip()

    total_holdings = 0
    total_aum = 0.0
    stock_holdings = 0
    stock_aum = 0.0

    grouped: dict[str, dict[str, object]] = {}

    with open(path, "r", encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        _require_columns(
            reader.fieldnames,
            ["ACCESSION_NUMBER", "CUSIP", "NAMEOFISSUER", "TITLEOFCLASS", "VALUE"],
            source=path,
        )

        for row in reader:
            row_accession = (row.get("ACCESSION_NUMBER") or "").strip()
            if row_accession != accession_number_norm:
                continue

            total_holdings += 1

            value = _safe_float((row.get("VALUE") or "").strip())
            total_aum += value

            title_norm = (row.get("TITLEOFCLASS") or "").lower().strip()
            if title_norm not in TITLE_CLASS_OF_STOCKS:
                continue

            stock_holdings += 1
            stock_aum += value

            cusip = _normalize_cusip(row.get("CUSIP") or "")
            if not cusip:
                # Skip malformed rows.
                continue

            if cusip not in grouped:
                grouped[cusip] = {
                    "CUSIP": cusip,
                    "NAMEOFISSUER": (row.get("NAMEOFISSUER") or ""),
                    "TITLEOFCLASS": (row.get("TITLEOFCLASS") or ""),
                    "VALUE": 0.0,
                }

            grouped[cusip]["VALUE"] = float(grouped[cusip]["VALUE"]) + value

    print(f"Summary stats for quarter: {quarter}, accession_number: {accession_number}")
    print(f"- Total number of holdings: {total_holdings}")

    if total_holdings == 0:
        print(f"ERROR: No data found for ACCESSION_NUMBER = {accession_number} in quarter {quarter}")
        raise SystemExit(1)

    # Note: VALUE is printed in the same unit as INFOTABLE.tsv (commonly thousands of USD in raw 13F data).
    print(f"- Total AUM: {total_aum:.2f}")

    print(f"- Number of stock holdings: {stock_holdings}")
    print(f"- Total stock AUM: {stock_aum:.2f}")

    if stock_holdings == 0:
        print(
            f"ERROR: No stock holdings found after TITLEOFCLASS filter for ACCESSION_NUMBER = {accession_number} in quarter {quarter}"
        )
        raise SystemExit(1)

    return grouped


def one_fund_analysis(
    accession_number: str,
    quarter: str,
    baseline_accession_number: Optional[str],
    baseline_quarter: Optional[str],
    data_root: str,
) -> None:
    current = read_one_quarter_data(accession_number, quarter, data_root=data_root)

    if baseline_accession_number is None and baseline_quarter is None:
        return

    if not baseline_accession_number or not baseline_quarter:
        print("ERROR: baseline_quarter and baseline_accession_number must be provided together")
        raise SystemExit(2)

    print(f"Performing comparative analysis using baseline quarter {baseline_quarter}")
    baseline = read_one_quarter_data(baseline_accession_number, baseline_quarter, data_root=data_root)

    all_cusips = set(current.keys()) | set(baseline.keys())

    merged_rows: list[dict[str, object]] = []
    for cusip in all_cusips:
        cur = current.get(cusip)
        base = baseline.get(cusip)

        cur_value = float(cur.get("VALUE", 0.0)) if cur else 0.0
        base_value = float(base.get("VALUE", 0.0)) if base else 0.0

        name = ""
        if cur and cur.get("NAMEOFISSUER"):
            name = str(cur.get("NAMEOFISSUER"))
        elif base and base.get("NAMEOFISSUER"):
            name = str(base.get("NAMEOFISSUER"))

        merged_rows.append(
            {
                "CUSIP": cusip,
                "NAMEOFISSUER": name,
                "ABS_CHANGE": cur_value - base_value,
            }
        )

    # Print top buy and sell. Rank by dollar-value change (VALUE) only.
    print(f"Top 10 Buys from {baseline_quarter} to {quarter}:")
    buys = [r for r in merged_rows if float(r["ABS_CHANGE"]) > 0]
    buys.sort(key=lambda r: (-float(r["ABS_CHANGE"]), str(r["CUSIP"])))
    for idx, row in enumerate(buys[:10], start=1):
        print(
            f"[{idx}] CUSIP: {row['CUSIP']}, Name: {row['NAMEOFISSUER']} | Abs change: {float(row['ABS_CHANGE']):.2f}"
        )

    print(f"\nTop 10 Sells from {baseline_quarter} to {quarter}:")
    sells = [r for r in merged_rows if float(r["ABS_CHANGE"]) < 0]
    sells.sort(key=lambda r: (float(r["ABS_CHANGE"]), str(r["CUSIP"])))
    for idx, row in enumerate(sells[:10], start=1):
        print(
            f"[{idx}] CUSIP: {row['CUSIP']}, Name: {row['NAMEOFISSUER']} | Abs change: {float(row['ABS_CHANGE']):.2f}"
        )


if __name__ == "__main__":
    args = get_args()
    one_fund_analysis(
        args.accession_number,
        args.quarter,
        args.baseline_accession_number,
        args.baseline_quarter,
        data_root=args.data_root,
    )
