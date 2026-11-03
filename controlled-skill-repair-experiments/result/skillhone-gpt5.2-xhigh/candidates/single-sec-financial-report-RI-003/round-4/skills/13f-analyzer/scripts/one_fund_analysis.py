import argparse
import csv
import os
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

# Filing data is expected under /root/<quarter>/
# Allow override for local testing / alternate layouts.
data_root = os.environ.get("SEC13F_DATA_ROOT", "/root")

# A pragmatic allow-list of common-equity TITLEOFCLASS values.
# Values are compared case-insensitively after stripping.
# NOTE: Keep in sync with /skills/fuzzy-name-search/scripts/search_stock_cusip.py
title_class_of_stocks = {
    "com",
    "common",
    "common stock",
    "stock",
    "class a",
    "class a com",
    "class b",
    "cl a",
    "cl a com",
    "cl a new",
    "cl b",
    "cl b new",
    "cmn",
    "com cl a",
    "com new",
    "com shs",
    "comm stk",
    "cap stk cl a",
    "cap stk cl c",
    "foreign stock",
    "ord shs",
    "sponsored adr",
    "sponsored ads",
    "adr",
    "equity",
    "shs cl a",
}


def get_args():
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


def _is_common_equity_position(row: dict[str, str]) -> bool:
    """Return True for common-equity (non-option) rows.

    - Filters by TITLEOFCLASS using the allow-list above.
    - Excludes option positions when PUTCALL is present and non-empty.
    """

    title = (row.get("TITLEOFCLASS") or "").strip().lower()
    if title not in title_class_of_stocks:
        return False

    putcall = (row.get("PUTCALL") or "").strip().upper()
    if putcall:
        return False

    return True


@dataclass
class QuarterSummary:
    total_holdings: int
    total_aum: float
    stock_holdings: int
    stock_aum: float


@dataclass
class StockPosition:
    cusip: str
    name: str
    title: str
    value: float


def read_one_quarter_data(accession_number: str, quarter: str) -> tuple[QuarterSummary, dict[str, StockPosition]]:
    """Read and process one quarter's data for a given accession number.

    Returns:
        (summary, positions_by_cusip)

        positions_by_cusip is aggregated at the CUSIP level (VALUE is summed).
    """

    path = os.path.join(data_root, quarter, "INFOTABLE.tsv")
    if not os.path.isfile(path):
        raise SystemExit(
            f"ERROR: Missing INFOTABLE.tsv at {path}. Expected dataset under {data_root}/<quarter>/INFOTABLE.tsv"
        )

    accession_number = accession_number.strip()

    total_holdings = 0
    total_aum = 0.0
    stock_holdings = 0
    stock_aum = 0.0

    # Aggregation.
    value_by_cusip: dict[str, float] = defaultdict(float)
    first_name_by_cusip: dict[str, str] = {}
    first_title_by_cusip: dict[str, str] = {}

    for row in _tsv_rows(path):
        if (row.get("ACCESSION_NUMBER") or "").strip() != accession_number:
            continue

        total_holdings += 1

        value = _parse_float(row.get("VALUE", ""))
        total_aum += value

        if not _is_common_equity_position(row):
            continue

        stock_holdings += 1
        stock_aum += value

        cusip = (row.get("CUSIP") or "").strip().upper()
        if not cusip:
            continue

        value_by_cusip[cusip] += value

        if cusip not in first_name_by_cusip:
            first_name_by_cusip[cusip] = (row.get("NAMEOFISSUER") or "").strip()
        if cusip not in first_title_by_cusip:
            first_title_by_cusip[cusip] = (row.get("TITLEOFCLASS") or "").strip()

    print(f"Summary stats for quarter: {quarter}, accession_number: {accession_number}")
    print(f"- Total number of holdings: {total_holdings}")
    print(f"- Total AUM: {total_aum:.2f}")
    print(f"- Number of stock holdings: {stock_holdings}")
    print(f"- Total stock AUM: {stock_aum:.2f}")

    if stock_holdings == 0:
        raise SystemExit(
            f"ERROR: No common-equity rows found for ACCESSION_NUMBER = {accession_number} in quarter {quarter}"
        )

    positions: dict[str, StockPosition] = {}
    for cusip, value in value_by_cusip.items():
        positions[cusip] = StockPosition(
            cusip=cusip,
            name=first_name_by_cusip.get(cusip, ""),
            title=first_title_by_cusip.get(cusip, ""),
            value=value,
        )

    return QuarterSummary(
        total_holdings=total_holdings,
        total_aum=total_aum,
        stock_holdings=stock_holdings,
        stock_aum=stock_aum,
    ), positions


def _fmt_pct(pct: float | None) -> str:
    if pct is None:
        return "N/A"
    return f"{pct:.2%}"


@dataclass
class PositionChange:
    cusip: str
    name: str
    abs_change: float
    pct_change: float | None


def one_fund_analysis(
    accession_number: str,
    quarter: str,
    baseline_accession_number: str | None,
    baseline_quarter: str | None,
):
    _, current_positions = read_one_quarter_data(accession_number, quarter)

    if baseline_accession_number is None or baseline_quarter is None:
        return

    print(f"Performing comparative analysis using baseline quarter {baseline_quarter}")
    _, baseline_positions = read_one_quarter_data(baseline_accession_number, baseline_quarter)

    all_cusips = set(current_positions.keys()) | set(baseline_positions.keys())

    changes: list[PositionChange] = []
    for cusip in all_cusips:
        cur = current_positions.get(cusip)
        base = baseline_positions.get(cusip)

        cur_val = cur.value if cur else 0.0
        base_val = base.value if base else 0.0

        abs_change = cur_val - base_val
        pct_change = None if base_val == 0 else abs_change / base_val

        name = (cur.name if cur and cur.name else "") or (base.name if base and base.name else "")
        changes.append(PositionChange(cusip=cusip, name=name, abs_change=abs_change, pct_change=pct_change))

    # Top buys: biggest positive VALUE change.
    print(f"Top 10 Buys (VALUE increase) from {baseline_quarter} to {quarter}:")
    top_buys = [c for c in changes if c.abs_change > 0]
    top_buys.sort(key=lambda c: c.abs_change, reverse=True)
    for idx, row in enumerate(top_buys[:10], start=1):
        print(
            f"[{idx}] CUSIP: {row.cusip}, Name: {row.name}"
            f" | Abs change: {row.abs_change:.2f} | pct change: {_fmt_pct(row.pct_change)}"
        )

    # Top sells: biggest negative VALUE change.
    print(f"\nTop 10 Sells (VALUE decrease) from {baseline_quarter} to {quarter}:")
    top_sells = [c for c in changes if c.abs_change < 0]
    top_sells.sort(key=lambda c: c.abs_change)
    for idx, row in enumerate(top_sells[:10], start=1):
        print(
            f"[{idx}] CUSIP: {row.cusip}, Name: {row.name}"
            f" | Abs change: {row.abs_change:.2f} | pct change: {_fmt_pct(row.pct_change)}"
        )


if __name__ == "__main__":
    args = get_args()
    one_fund_analysis(args.accession_number, args.quarter, args.baseline_accession_number, args.baseline_quarter)
