import argparse

import pandas as pd

DATA_ROOT = "/root"

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
    parser.add_argument(
        "--include_options",
        action="store_true",
        help=(
            "Include option rows (PUT/CALL) if present. By default the helper excludes rows where PUTCALL is set, "
            "so stock counts and VALUE aggregates reflect common-equity holdings rather than option positions."
        ),
    )
    return parser.parse_args()


def _normalize_titleofclass(series: pd.Series) -> pd.Series:
    # dtype=str read still allows NaN; normalize defensively.
    return series.fillna("").astype(str).str.strip().str.lower()


def _is_blank(series: pd.Series) -> pd.Series:
    # Treat NaN and whitespace as blank.
    return series.isna() | (series.astype(str).str.strip() == "")


def read_one_quarter_data(accession_number: str, quarter: str, include_options: bool = False) -> pd.DataFrame:
    """Read and process one quarter stock holdings for a given accession number.

    Returns a DataFrame with columns: CUSIP, NAMEOFISSUER, TITLEOFCLASS, VALUE.
    VALUE is aggregated (summed) by CUSIP after applying the stock TITLEOFCLASS
    filter.

    By default, rows with a non-blank PUTCALL (options) are excluded when the
    column exists so that counts/aggregates reflect common-equity positions.
    """

    infotable_path = f"{DATA_ROOT}/{quarter}/INFOTABLE.tsv"
    infotable = pd.read_csv(infotable_path, sep="\t", dtype=str)
    if "VALUE" not in infotable.columns:
        raise SystemExit(f"ERROR: Missing VALUE column in {infotable_path}")

    infotable["VALUE"] = infotable["VALUE"].astype(float)
    infotable = infotable[infotable["ACCESSION_NUMBER"] == accession_number]

    if infotable.empty:
        raise SystemExit(f"ERROR: No data found for ACCESSION_NUMBER = {accession_number} in quarter {quarter}")

    # Raw counts are based on the INFOTABLE rows.
    total_rows = int(infotable.shape[0])
    total_unique_cusips = int(infotable["CUSIP"].nunique(dropna=True))

    stock_infotable = infotable[_normalize_titleofclass(infotable["TITLEOFCLASS"]).isin(TITLE_CLASS_OF_STOCKS)]

    # Exclude options by default when the PUTCALL column exists.
    if not include_options and "PUTCALL" in stock_infotable.columns:
        stock_infotable = stock_infotable[_is_blank(stock_infotable["PUTCALL"])]

    stock_rows = int(stock_infotable.shape[0])

    stock = (
        stock_infotable.groupby("CUSIP", as_index=False)
        .agg(
            NAMEOFISSUER=("NAMEOFISSUER", "first"),
            TITLEOFCLASS=("TITLEOFCLASS", "first"),
            VALUE=("VALUE", "sum"),
        )
        .sort_values("VALUE", ascending=False)
    )
    unique_stock_cusips = int(stock.shape[0])

    print(f"Summary stats for quarter: {quarter}, accession_number: {accession_number}")
    print(f"- Total holdings rows (raw INFOTABLE lines): {total_rows}")
    print(f"- Total unique CUSIPs (all holdings): {total_unique_cusips}")
    print(f"- Total AUM: {infotable['VALUE'].sum():.2f}")
    print(f"- Stock holdings rows (TITLEOFCLASS-filtered): {stock_rows}")
    print(f"- Unique stock CUSIPs (TITLEOFCLASS-filtered): {unique_stock_cusips}")
    print(f"- Total stock AUM: {stock_infotable['VALUE'].sum():.2f}")

    if stock.empty:
        raise SystemExit(
            f"ERROR: No stock data found for ACCESSION_NUMBER = {accession_number} in quarter {quarter} "
            f"after applying the TITLEOFCLASS stock filter"
        )

    return stock


def one_fund_analysis(
    accession_number: str,
    quarter: str,
    baseline_accession_number: str | None,
    baseline_quarter: str | None,
    include_options: bool = False,
):
    current = read_one_quarter_data(accession_number, quarter, include_options=include_options)

    if baseline_accession_number is None and baseline_quarter is None:
        return
    if baseline_accession_number is None or baseline_quarter is None:
        raise SystemExit("ERROR: --baseline_accession_number and --baseline_quarter must be provided together")

    print(f"Performing comparative analysis using baseline quarter {baseline_quarter}")
    baseline = read_one_quarter_data(baseline_accession_number, baseline_quarter, include_options=include_options)

    merged = pd.merge(current, baseline, how="outer", suffixes=("", "_base"), on="CUSIP")

    # Analyze changes.
    merged["VALUE"] = merged["VALUE"].fillna(0.0)
    merged["VALUE_base"] = merged["VALUE_base"].fillna(0.0)
    merged["NAMEOFISSUER"] = merged["NAMEOFISSUER"].fillna(merged.get("NAMEOFISSUER_base"))

    merged["ABS_CHANGE"] = merged["VALUE"] - merged["VALUE_base"]

    # Avoid division-by-zero. For new positions (baseline == 0) the percentage
    # change is not meaningful; it will print as nan%.
    denom = merged["VALUE_base"].replace(0.0, float("nan"))
    merged["PCT_CHANGE"] = merged["ABS_CHANGE"] / denom

    # Print top buys and sells by notional VALUE change.
    print(f"Top 10 Buys from {baseline_quarter} to {quarter}:")
    top_buys = merged[merged["ABS_CHANGE"] > 0].sort_values(by="ABS_CHANGE", ascending=False).head(10)
    for rank, row in enumerate(top_buys.itertuples(index=False), start=1):
        print(
            f"[{rank}] CUSIP: {row.CUSIP}, Name: {row.NAMEOFISSUER} | Abs change: {row.ABS_CHANGE:.2f} | pct change: {row.PCT_CHANGE:.2%}"
        )

    print(f"\nTop 10 Sells from {baseline_quarter} to {quarter}:")
    top_sells = merged[merged["ABS_CHANGE"] < 0].sort_values(by="ABS_CHANGE", ascending=True).head(10)
    for rank, row in enumerate(top_sells.itertuples(index=False), start=1):
        print(
            f"[{rank}] CUSIP: {row.CUSIP}, Name: {row.NAMEOFISSUER} | Abs change: {row.ABS_CHANGE:.2f} | pct change: {row.PCT_CHANGE:.2%}"
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
