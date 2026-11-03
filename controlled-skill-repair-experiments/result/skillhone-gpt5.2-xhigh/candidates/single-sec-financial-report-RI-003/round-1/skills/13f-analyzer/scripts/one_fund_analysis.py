import argparse

import pandas as pd

# Filing data is expected under /root/<quarter>/
data_root = "/root"

# A pragmatic allow-list of common-equity TITLEOFCLASS values.
# Values are compared case-insensitively after stripping.
# NOTE: This is intentionally a set; ordering does not matter.
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


def _is_common_equity_position(df: pd.DataFrame) -> pd.Series:
    """Return a boolean mask for common-equity (non-option) rows.

    - Filters by TITLEOFCLASS using the allow-list above.
    - Excludes option positions when PUTCALL is present and non-empty.
    """

    title = df["TITLEOFCLASS"].fillna("").astype(str).str.lower().str.strip()
    mask = title.isin(title_class_of_stocks)

    # Many 13F INFOTABLE files include a PUTCALL column for options.
    if "PUTCALL" in df.columns:
        putcall = df["PUTCALL"].fillna("").astype(str).str.strip().str.upper()
        mask &= putcall.eq("")

    return mask


def read_one_quarter_data(accession_number: str, quarter: str) -> pd.DataFrame:
    """Read and process one quarter's data for a given accession number.

    Returns:
        pd.DataFrame with columns: CUSIP, NAMEOFISSUER, TITLEOFCLASS, VALUE
        aggregated at the CUSIP level (VALUE is summed).
    """

    infotable = pd.read_csv(f"{data_root}/{quarter}/INFOTABLE.tsv", sep="\t", dtype=str)
    if "VALUE" not in infotable.columns:
        raise SystemExit(f"ERROR: Missing VALUE column in {data_root}/{quarter}/INFOTABLE.tsv")

    infotable["VALUE"] = pd.to_numeric(infotable["VALUE"], errors="coerce").fillna(0.0)
    infotable = infotable[infotable["ACCESSION_NUMBER"] == accession_number].copy()

    print(f"Summary stats for quarter: {quarter}, accession_number: {accession_number}")
    print(f"- Total number of holdings: {infotable.shape[0]}")
    print(f"- Total AUM: {infotable['VALUE'].sum():.2f}")

    stock_rows = _is_common_equity_position(infotable)
    stock_infotable = infotable[stock_rows].copy()

    print(f"- Number of stock holdings: {stock_infotable.shape[0]}")
    print(f"- Total stock AUM: {stock_infotable['VALUE'].sum():.2f}")

    if stock_infotable.empty:
        raise SystemExit(
            f"ERROR: No common-equity rows found for ACCESSION_NUMBER = {accession_number} in quarter {quarter}"
        )

    stock_infotable["CUSIP"] = stock_infotable["CUSIP"].fillna("").astype(str).str.upper().str.strip()
    stock_infotable = stock_infotable[stock_infotable["CUSIP"] != ""]

    stock = (
        stock_infotable.groupby("CUSIP", as_index=False)
        .agg(
            NAMEOFISSUER=("NAMEOFISSUER", "first"),
            TITLEOFCLASS=("TITLEOFCLASS", "first"),
            VALUE=("VALUE", "sum"),
        )
        .sort_values("VALUE", ascending=False)
    )

    return stock


def _fmt_pct(pct) -> str:
    if pct is None or pd.isna(pct):
        return "N/A"
    return f"{pct:.2%}"


def one_fund_analysis(accession_number: str, quarter: str, baseline_accession_number: str | None, baseline_quarter: str | None):
    current = read_one_quarter_data(accession_number, quarter)

    if baseline_accession_number is None or baseline_quarter is None:
        return

    print(f"Performing comparative analysis using baseline quarter {baseline_quarter}")
    baseline = read_one_quarter_data(baseline_accession_number, baseline_quarter)

    merged = pd.merge(current, baseline, how="outer", suffixes=("", "_base"), on="CUSIP")

    # Analyze changes (VALUE is the 13F reported holding value; commonly in $1,000).
    merged["VALUE"] = merged["VALUE"].fillna(0.0)
    merged["VALUE_base"] = merged["VALUE_base"].fillna(0.0)
    merged["NAMEOFISSUER"] = merged["NAMEOFISSUER"].fillna(merged["NAMEOFISSUER_base"])
    merged["TITLEOFCLASS"] = merged["TITLEOFCLASS"].fillna(merged["TITLEOFCLASS_base"])

    merged["ABS_CHANGE"] = merged["VALUE"] - merged["VALUE_base"]
    denom = merged["VALUE_base"].replace(0, pd.NA)
    merged["PCT_CHANGE"] = merged["ABS_CHANGE"] / denom

    # Top buys: biggest positive VALUE change.
    print(f"Top 10 Buys (VALUE increase) from {baseline_quarter} to {quarter}:")
    top_buys = merged[merged["ABS_CHANGE"] > 0].sort_values(by="ABS_CHANGE", ascending=False).head(10)
    for idx, row in enumerate(top_buys.itertuples(index=False), start=1):
        print(
            f"[{idx}] CUSIP: {row.CUSIP}, Name: {row.NAMEOFISSUER}"
            f" | Abs change: {row.ABS_CHANGE:.2f} | pct change: {_fmt_pct(row.PCT_CHANGE)}"
        )

    # Top sells: biggest negative VALUE change.
    print(f"\nTop 10 Sells (VALUE decrease) from {baseline_quarter} to {quarter}:")
    top_sells = merged[merged["ABS_CHANGE"] < 0].sort_values(by="ABS_CHANGE", ascending=True).head(10)
    for idx, row in enumerate(top_sells.itertuples(index=False), start=1):
        print(
            f"[{idx}] CUSIP: {row.CUSIP}, Name: {row.NAMEOFISSUER}"
            f" | Abs change: {row.ABS_CHANGE:.2f} | pct change: {_fmt_pct(row.PCT_CHANGE)}"
        )


if __name__ == "__main__":
    args = get_args()
    one_fund_analysis(args.accession_number, args.quarter, args.baseline_accession_number, args.baseline_quarter)
