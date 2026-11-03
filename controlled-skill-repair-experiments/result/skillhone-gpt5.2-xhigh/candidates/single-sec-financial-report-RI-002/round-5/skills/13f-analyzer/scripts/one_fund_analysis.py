import argparse
import csv
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Default data location is /root/<quarter> as used by the task downloads.
# Allow overriding for local testing via an environment variable.
DATA_ROOT = os.environ.get("SEC13F_DATA_ROOT", "/root")

# NOTE: This list defines the stock-selection semantics for the skill.
# Keep it conservative and do not broaden silently.
TITLE_CLASS_OF_STOCKS = {
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
        "--include_options",
        action="store_true",
        help=(
            "Include option rows (PUT/CALL) if present. By default the helper excludes rows where PUTCALL is set, "
            "so stock counts and VALUE aggregates reflect common-equity holdings rather than option positions."
        ),
    )
    return parser.parse_args()


def _normalize_titleofclass(value: Any) -> str:
    return str(value or "").strip().lower()


def _is_blank(value: Any) -> bool:
    # Treat None and whitespace as blank.
    return value is None or str(value).strip() == ""


def _parse_value(value: Any, *, path: Path) -> float:
    raw = "" if value is None else str(value).strip()
    if raw == "":
        return 0.0
    try:
        return float(raw)
    except ValueError as exc:
        raise SystemExit(f"ERROR: Could not parse VALUE='{raw}' as float in {path}") from exc


@dataclass
class Holding:
    cusip: str
    nameofissuer: str
    titleofclass: str
    value: float


def read_one_quarter_data(accession_number: str, quarter: str, include_options: bool = False) -> dict[str, Holding]:
    """Read and process one quarter stock holdings for a given accession number.

    Returns a dict keyed by CUSIP with aggregated (summed) VALUE after applying
    the conservative stock TITLEOFCLASS filter.

    By default, rows with a non-blank PUTCALL (options) are excluded when the
    column exists so that counts/aggregates reflect common-equity positions.
    """

    accession_number = (accession_number or "").strip()
    if accession_number == "":
        raise SystemExit("ERROR: accession_number must be non-empty")

    infotable_path = Path(DATA_ROOT) / quarter / "INFOTABLE.tsv"
    if not infotable_path.exists():
        raise SystemExit(f"ERROR: INFOTABLE.tsv not found at {infotable_path}")

    with infotable_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        if not reader.fieldnames:
            raise SystemExit(f"ERROR: Empty or malformed TSV at {infotable_path}")

        # Collect the rows for this accession number first so we can compute the
        # raw stats (total rows, total unique CUSIPs, total AUM).
        rows: list[dict[str, Any]] = []
        for row in reader:
            if str(row.get("ACCESSION_NUMBER", "") or "").strip() != accession_number:
                continue
            rows.append(row)

    if not rows:
        raise SystemExit(f"ERROR: No data found for ACCESSION_NUMBER = {accession_number} in quarter {quarter}")

    # Raw counts are based on the INFOTABLE rows.
    total_rows = len(rows)

    cusip_set: set[str] = set()
    total_aum = 0.0

    for row in rows:
        cusip = str(row.get("CUSIP", "") or "").strip().upper()
        if cusip:
            cusip_set.add(cusip)
        total_aum += _parse_value(row.get("VALUE"), path=infotable_path)

    total_unique_cusips = len(cusip_set)

    # Apply conservative stock filter and option filter.
    stock_rows = 0
    total_stock_aum = 0.0
    by_cusip: dict[str, Holding] = {}

    for row in rows:
        title_norm = _normalize_titleofclass(row.get("TITLEOFCLASS"))
        if title_norm not in TITLE_CLASS_OF_STOCKS:
            continue

        if not include_options and "PUTCALL" in row and not _is_blank(row.get("PUTCALL")):
            continue

        stock_rows += 1

        cusip = str(row.get("CUSIP", "") or "").strip().upper()
        if cusip == "":
            # Skip malformed rows; they cannot be grouped.
            continue

        value = _parse_value(row.get("VALUE"), path=infotable_path)
        total_stock_aum += value

        if cusip not in by_cusip:
            by_cusip[cusip] = Holding(
                cusip=cusip,
                nameofissuer=str(row.get("NAMEOFISSUER", "") or "").strip(),
                titleofclass=str(row.get("TITLEOFCLASS", "") or "").strip(),
                value=value,
            )
        else:
            by_cusip[cusip].value += value

    unique_stock_cusips = len(by_cusip)

    print(f"Summary stats for quarter: {quarter}, accession_number: {accession_number}")
    print(f"- Total holdings rows (raw INFOTABLE lines): {total_rows}")
    print(f"- Total unique CUSIPs (all holdings): {total_unique_cusips}")
    print(f"- Total AUM: {total_aum:.2f}")
    print(f"- Stock holdings rows (TITLEOFCLASS-filtered): {stock_rows}")
    print(f"- Unique stock CUSIPs (TITLEOFCLASS-filtered): {unique_stock_cusips}")
    print(f"- Total stock AUM: {total_stock_aum:.2f}")

    if not by_cusip:
        raise SystemExit(
            f"ERROR: No stock data found for ACCESSION_NUMBER = {accession_number} in quarter {quarter} "
            f"after applying the TITLEOFCLASS stock filter"
        )

    # Return holdings keyed by CUSIP. (Caller can sort as needed.)
    return by_cusip


def one_fund_analysis(
    accession_number: str,
    quarter: str,
    baseline_accession_number: str | None,
    baseline_quarter: str | None,
    include_options: bool = False,
) -> None:
    current = read_one_quarter_data(accession_number, quarter, include_options=include_options)

    if baseline_accession_number is None and baseline_quarter is None:
        return
    if baseline_accession_number is None or baseline_quarter is None:
        raise SystemExit("ERROR: --baseline_accession_number and --baseline_quarter must be provided together")

    print(f"Performing comparative analysis using baseline quarter {baseline_quarter}")
    baseline = read_one_quarter_data(baseline_accession_number, baseline_quarter, include_options=include_options)

    all_cusips = set(current) | set(baseline)

    merged_rows: list[dict[str, Any]] = []
    for cusip in all_cusips:
        cur = current.get(cusip)
        base = baseline.get(cusip)

        cur_value = 0.0 if cur is None else cur.value
        base_value = 0.0 if base is None else base.value

        name = ""
        if cur is not None and cur.nameofissuer:
            name = cur.nameofissuer
        elif base is not None and base.nameofissuer:
            name = base.nameofissuer

        abs_change = cur_value - base_value
        pct_change = abs_change / base_value if base_value != 0 else math.nan

        merged_rows.append(
            {
                "CUSIP": cusip,
                "NAMEOFISSUER": name,
                "VALUE": cur_value,
                "VALUE_base": base_value,
                "ABS_CHANGE": abs_change,
                "PCT_CHANGE": pct_change,
            }
        )

    # Print top buys and sells by notional VALUE change.
    print(f"Top 10 Buys from {baseline_quarter} to {quarter}:")
    top_buys = sorted((r for r in merged_rows if r["ABS_CHANGE"] > 0), key=lambda r: r["ABS_CHANGE"], reverse=True)[:10]
    for rank, row in enumerate(top_buys, start=1):
        print(
            f"[{rank}] CUSIP: {row['CUSIP']}, Name: {row['NAMEOFISSUER']} | Abs change: {row['ABS_CHANGE']:.2f} | pct change: {row['PCT_CHANGE']:.2%}"
        )

    print(f"\nTop 10 Sells from {baseline_quarter} to {quarter}:")
    top_sells = sorted((r for r in merged_rows if r["ABS_CHANGE"] < 0), key=lambda r: r["ABS_CHANGE"])[:10]
    for rank, row in enumerate(top_sells, start=1):
        print(
            f"[{rank}] CUSIP: {row['CUSIP']}, Name: {row['NAMEOFISSUER']} | Abs change: {row['ABS_CHANGE']:.2f} | pct change: {row['PCT_CHANGE']:.2%}"
        )


if __name__ == "__main__":
    args = get_args()
    one_fund_analysis(
        args.accession_number,
        args.quarter,
        args.baseline_accession_number,
        args.baseline_quarter,
        include_options=args.include_options,
    )
