import argparse
import csv
import os
from pathlib import Path
from typing import Any

# Default data location is /root/<quarter> as used by the task downloads.
# Allow overriding for local testing via an environment variable.
DATA_ROOT = os.environ.get("SEC13F_DATA_ROOT", "/root")

# Keep this list aligned with one_fund_analysis.py. It defines the conservative
# stock-selection semantics for this skill.
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
    parser = argparse.ArgumentParser(description="Analyze which fund managers hold a given stock")
    parser.add_argument("--cusip", type=str, required=True, help="The CUSIP of the stock to analyze")
    parser.add_argument("--quarter", type=str, required=True, help="The quarter to analyze (e.g., 2025-q3)")
    parser.add_argument("--topk", type=int, default=10, help="The maximum number of results to return")
    parser.add_argument(
        "--include_options",
        action="store_true",
        help=(
            "Include option rows (PUT/CALL) if present. By default the helper excludes rows where PUTCALL is set, "
            "so the ranking reflects common-equity holdings rather than option positions."
        ),
    )
    return parser.parse_args()


def _normalize_titleofclass(value: Any) -> str:
    return str(value or "").strip().lower()


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    return str(value).strip() == ""


def _parse_value(value: Any, *, path: Path) -> float:
    raw = "" if value is None else str(value).strip()
    if raw == "":
        return 0.0
    try:
        return float(raw)
    except ValueError as exc:
        raise SystemExit(f"ERROR: Could not parse VALUE='{raw}' as float in {path}") from exc


def topk_managers(cusip: str, quarter: str, topk: int, include_options: bool = False) -> list[dict[str, Any]]:
    """Find top-k fund managers holding the given stock CUSIP in the specified quarter.

    Ranking metric: sum(VALUE) by ACCESSION_NUMBER after applying a conservative
    common-equity filter.

    Returns:
        List of dict rows with keys: ACCESSION_NUMBER, TOTAL_VALUE, FILINGMANAGER_NAME (optional).
    """
    cusip = cusip.strip().upper()

    infotable_path = Path(DATA_ROOT) / quarter / "INFOTABLE.tsv"
    if not infotable_path.exists():
        raise SystemExit(f"ERROR: INFOTABLE.tsv not found at {infotable_path}")

    # Aggregate holdings for this CUSIP by accession number.
    totals: dict[str, float] = {}

    with infotable_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        if not reader.fieldnames:
            raise SystemExit(f"ERROR: Empty or malformed TSV at {infotable_path}")

        required_cols = {"CUSIP", "ACCESSION_NUMBER", "VALUE", "TITLEOFCLASS"}
        missing = required_cols - set(reader.fieldnames)
        if missing:
            raise SystemExit(f"ERROR: Missing columns {sorted(missing)} in {infotable_path}")

        for row in reader:
            row_cusip = str(row.get("CUSIP", "") or "").strip().upper()
            if row_cusip != cusip:
                continue

            # Apply the same conservative stock filter used by one_fund_analysis.
            if _normalize_titleofclass(row.get("TITLEOFCLASS")) not in TITLE_CLASS_OF_STOCKS:
                continue

            # Exclude options by default when the PUTCALL column exists.
            if not include_options and "PUTCALL" in row and not _is_blank(row.get("PUTCALL")):
                continue

            accession = str(row.get("ACCESSION_NUMBER", "") or "").strip()
            if accession == "":
                continue

            totals[accession] = totals.get(accession, 0.0) + _parse_value(row.get("VALUE"), path=infotable_path)

    if not totals:
        raise SystemExit(
            f"ERROR: No stock holdings remain for CUSIP = {cusip} in {quarter} after applying the stock/option filters"
        )

    ranked = [
        {
            "ACCESSION_NUMBER": accession,
            "TOTAL_VALUE": total_value,
        }
        for accession, total_value in totals.items()
    ]
    ranked.sort(key=lambda r: r["TOTAL_VALUE"], reverse=True)
    ranked = ranked[: max(int(topk), 0)]

    # Join manager names from COVERPAGE for convenience.
    coverpage_path = Path(DATA_ROOT) / quarter / "COVERPAGE.tsv"
    accession_to_manager: dict[str, str] = {}
    if coverpage_path.exists():
        with coverpage_path.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="\t")
            if reader.fieldnames and {"ACCESSION_NUMBER", "FILINGMANAGER_NAME"}.issubset(reader.fieldnames):
                for row in reader:
                    accession = str(row.get("ACCESSION_NUMBER", "") or "").strip()
                    if accession == "" or accession in accession_to_manager:
                        continue
                    accession_to_manager[accession] = str(row.get("FILINGMANAGER_NAME", "") or "").strip()

    for row in ranked:
        row["FILINGMANAGER_NAME"] = accession_to_manager.get(row["ACCESSION_NUMBER"], "")

    return ranked


def main() -> None:
    args = get_args()
    ranked = topk_managers(args.cusip, args.quarter, args.topk, include_options=args.include_options)

    print(f"Top-{len(ranked)} fund managers holding CUSIP {args.cusip.strip().upper()} in quarter {args.quarter}:")
    for idx, row in enumerate(ranked, start=1):
        accession_number = row["ACCESSION_NUMBER"]
        total_value = float(row["TOTAL_VALUE"])
        manager_name = row.get("FILINGMANAGER_NAME", "")
        manager_part = manager_name if manager_name else "(manager name unavailable)"
        print(f"Rank {idx}: {manager_part} | accession number = {accession_number} | Holding value = {total_value:.2f}")


if __name__ == "__main__":
    main()
