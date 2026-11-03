import argparse

import pandas as pd

DATA_ROOT = "/root"

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


def _normalize_titleofclass(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.strip().str.lower()


def _is_blank(series: pd.Series) -> pd.Series:
    # Treat NaN and whitespace as blank.
    return series.isna() | (series.astype(str).str.strip() == "")


def topk_managers(cusip: str, quarter: str, topk: int, include_options: bool = False) -> pd.DataFrame:
    """Find top-k fund managers holding the given stock CUSIP in the specified quarter.

    Ranking metric: sum(VALUE) by ACCESSION_NUMBER after applying a conservative
    common-equity filter.

    Returns:
        DataFrame with columns: ACCESSION_NUMBER, FILINGMANAGER_NAME, TOTAL_VALUE.
    """
    cusip = cusip.strip().upper()

    infotable_path = f"{DATA_ROOT}/{quarter}/INFOTABLE.tsv"
    infotable = pd.read_csv(infotable_path, sep="\t", dtype=str)

    required_cols = {"CUSIP", "ACCESSION_NUMBER", "VALUE", "TITLEOFCLASS"}
    missing = required_cols - set(infotable.columns)
    if missing:
        raise SystemExit(f"ERROR: Missing columns {sorted(missing)} in {infotable_path}")

    infotable["CUSIP"] = infotable["CUSIP"].fillna("").astype(str).str.strip().str.upper()
    infotable["VALUE"] = pd.to_numeric(infotable["VALUE"], errors="coerce")

    holding_details = infotable[infotable["CUSIP"] == cusip].copy()
    if holding_details.empty:
        raise SystemExit(f"ERROR: No rows found for CUSIP = {cusip} in {infotable_path}")

    # Apply the same conservative stock filter used by one_fund_analysis.
    holding_details = holding_details[_normalize_titleofclass(holding_details["TITLEOFCLASS"]).isin(TITLE_CLASS_OF_STOCKS)]

    # Exclude options by default when the PUTCALL column exists.
    if not include_options and "PUTCALL" in holding_details.columns:
        holding_details = holding_details[_is_blank(holding_details["PUTCALL"])]

    if holding_details.empty:
        raise SystemExit(
            f"ERROR: No stock holdings remain for CUSIP = {cusip} in {quarter} after applying the stock/option filters"
        )

    ranked = (
        holding_details.groupby("ACCESSION_NUMBER", as_index=False)
        .agg(
            TOTAL_VALUE=("VALUE", "sum"),
        )
        .sort_values("TOTAL_VALUE", ascending=False)
        .head(topk)
    )

    # Join manager names from COVERPAGE for convenience.
    coverpage_path = f"{DATA_ROOT}/{quarter}/COVERPAGE.tsv"
    try:
        coverpage = pd.read_csv(coverpage_path, sep="\t", dtype=str)
        if {"ACCESSION_NUMBER", "FILINGMANAGER_NAME"}.issubset(coverpage.columns):
            cover_cols = ["ACCESSION_NUMBER", "FILINGMANAGER_NAME"]
            if "ISAMENDMENT" in coverpage.columns:
                cover_cols.append("ISAMENDMENT")
            coverpage = coverpage[cover_cols].drop_duplicates(subset=["ACCESSION_NUMBER"], keep="first")
            ranked = ranked.merge(coverpage, on="ACCESSION_NUMBER", how="left")
        else:
            ranked["FILINGMANAGER_NAME"] = pd.NA
    except FileNotFoundError:
        ranked["FILINGMANAGER_NAME"] = pd.NA

    return ranked


def main() -> None:
    args = get_args()
    ranked = topk_managers(args.cusip, args.quarter, args.topk, include_options=args.include_options)

    print(f"Top-{ranked.shape[0]} fund managers holding CUSIP {args.cusip.strip().upper()} in quarter {args.quarter}:")
    for idx, row in enumerate(ranked.itertuples(index=False), start=1):
        accession_number = row.ACCESSION_NUMBER
        total_value = float(row.TOTAL_VALUE)
        manager_name = getattr(row, "FILINGMANAGER_NAME", None)
        if manager_name is None or (isinstance(manager_name, float) and pd.isna(manager_name)) or pd.isna(manager_name):
            manager_part = "(manager name unavailable)"
        else:
            manager_part = str(manager_name)
        print(f"Rank {idx}: {manager_part} | accession number = {accession_number} | Holding value = {total_value:.2f}")


if __name__ == "__main__":
    main()
