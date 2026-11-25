import argparse
from pathlib import Path

import pandas as pd

DATA_ROOT = Path("/root")

# A conservative list of equity-like classes often seen in 13F.
# NOTE: We *do not rely solely* on this list for correctness; if TITLEOFCLASS
# is missing or uninformative, we still aggregate by CUSIP.
TITLE_CLASS_OF_STOCKS = [
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
]


def _find_one(quarter_dir: Path, candidate_names: list[str]) -> Path:
    for name in candidate_names:
        hits = list(quarter_dir.rglob(name))
        if hits:
            return hits[0]
    raise FileNotFoundError(f"None of {candidate_names} found under {quarter_dir}")


def _read_table(path: Path) -> pd.DataFrame:
    p = str(path)
    if p.endswith(".parquet"):
        return pd.read_parquet(path)
    if p.endswith(".tsv"):
        return pd.read_csv(path, sep="\t", dtype=str)
    return pd.read_csv(path, dtype=str)


def _to_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.astype(str).str.replace(",", "", regex=False), errors="coerce")


def _norm_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [c.strip().lower() for c in df.columns]
    return df


def _first_existing_col(df: pd.DataFrame, candidates: list[str], *, optional: bool = False) -> str | None:
    cols = set(df.columns)
    for c in candidates:
        if c in cols:
            return c
    if optional:
        return None
    raise KeyError(f"None of columns {candidates} exist. Existing columns: {sorted(cols)[:50]}")


def _clean_cusip(s: pd.Series) -> pd.Series:
    out = s.astype(str).str.upper().str.strip()
    # treat literal strings as missing
    out = out.replace({"NAN": "", "NONE": ""})
    return out


def get_args():
    parser = argparse.ArgumentParser(description="Analyze grouped fund holdings information")
    parser.add_argument(
        "--accession_number",
        type=str,
        required=True,
        help="The accession number of the fund to analyze",
    )
    parser.add_argument("--quarter", type=str, required=True, help="The quarter of the fund to analyze (e.g., 2025-q3)")

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
        "--value_in_thousands",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Assume 13F VALUE is in $ thousands and convert to dollars for outputs and deltas.",
    )

    return parser.parse_args()


def _load_infotable(quarter: str) -> pd.DataFrame:
    quarter_dir = DATA_ROOT / quarter
    infotable_path = _find_one(quarter_dir, ["INFOTABLE.tsv", "INFOTABLE.csv", "INFOTABLE.parquet", "infotable.parquet"])
    return _norm_cols(_read_table(infotable_path))


def _load_coverpage_optional(quarter: str) -> pd.DataFrame | None:
    """Load COVERPAGE if present; return None if not found."""
    quarter_dir = DATA_ROOT / quarter
    try:
        coverpage_path = _find_one(quarter_dir, ["COVERPAGE.tsv", "COVERPAGE.csv", "COVERPAGE.parquet", "coverpage.parquet"])
    except FileNotFoundError:
        return None
    return _norm_cols(_read_table(coverpage_path))


def positions_by_cusip(infotable: pd.DataFrame, accession_number: str, value_in_thousands: bool) -> pd.DataFrame:
    acc_col = _first_existing_col(infotable, ["accession_number", "accessionnumber"])
    cusip_col = _first_existing_col(infotable, ["cusip"])
    val_col = _first_existing_col(infotable, ["value"])

    df = infotable[infotable[acc_col].astype(str) == str(accession_number)].copy()

    if df.empty:
        return pd.DataFrame(columns=["cusip", "nameofissuer", "value", "value_dollars"])

    # Remove options if column exists
    if "putcall" in df.columns:
        df = df[df["putcall"].isna() | (df["putcall"].astype(str).str.strip() == "")]

    df[val_col] = _to_num(df[val_col]).fillna(0.0)

    df["_cusip_clean"] = _clean_cusip(df[cusip_col])
    df = df[df["_cusip_clean"] != ""]

    # Keep issuer name if present
    issuer_col = "nameofissuer" if "nameofissuer" in df.columns else None

    agg_dict = {val_col: "sum"}
    if issuer_col:
        # first is OK for display only
        agg_dict[issuer_col] = "first"

    out = df.groupby("_cusip_clean", as_index=False).agg(agg_dict)
    out = out.rename(columns={"_cusip_clean": "cusip", val_col: "value"})

    if issuer_col:
        out = out.rename(columns={issuer_col: "nameofissuer"})
    else:
        out["nameofissuer"] = None

    if value_in_thousands:
        out["value_dollars"] = out["value"] * 1000.0
    else:
        out["value_dollars"] = out["value"]

    return out[["cusip", "nameofissuer", "value", "value_dollars"]]


def _coverpage_total_value(coverpage: pd.DataFrame, accession_number: str) -> float | None:
    """Best-effort: extract total 13F value for an accession from COVERPAGE.

    Returns the raw numeric value from COVERPAGE (units unknown; caller applies value_in_thousands).
    """
    if coverpage is None or coverpage.empty:
        return None

    acc_col = _first_existing_col(coverpage, ["accession_number", "accessionnumber"], optional=True)
    if not acc_col:
        return None

    rows = coverpage[coverpage[acc_col].astype(str) == str(accession_number)]
    if rows.empty:
        return None

    total_col = _first_existing_col(
        rows,
        [
            "total_value",
            "tablevalue",
            "totalvalue",
            "totalsecvalue",
            "totalmarketvalue",
        ],
        optional=True,
    )
    if not total_col:
        return None

    v = _to_num(rows.iloc[0][total_col:total_col]).iloc[0] if False else _to_num(pd.Series([rows.iloc[0][total_col]])).iloc[0]
    if pd.isna(v):
        return None
    return float(v)


def _coverpage_manager_name(coverpage: pd.DataFrame, accession_number: str) -> str | None:
    if coverpage is None or coverpage.empty:
        return None

    acc_col = _first_existing_col(coverpage, ["accession_number", "accessionnumber"], optional=True)
    if not acc_col:
        return None

    rows = coverpage[coverpage[acc_col].astype(str) == str(accession_number)]
    if rows.empty:
        return None

    name_col = _first_existing_col(
        rows,
        ["filingmanager_name", "manager_name", "nameofinstitution", "company_name"],
        optional=True,
    )
    if not name_col:
        return None

    v = rows.iloc[0][name_col]
    if pd.isna(v):
        return None
    return str(v)


def read_one_quarter_summary(accession_number: str, quarter: str, value_in_thousands: bool):
    infotable = _load_infotable(quarter)

    acc_col = _first_existing_col(infotable, ["accession_number", "accessionnumber"])
    cusip_col = _first_existing_col(infotable, ["cusip"])
    val_col = _first_existing_col(infotable, ["value"])

    df = infotable[infotable[acc_col].astype(str) == str(accession_number)].copy()

    if df.empty:
        raise ValueError(f"No data found for ACCESSION_NUMBER = {accession_number} in quarter {quarter}")

    # Remove options if column exists
    if "putcall" in df.columns:
        df = df[df["putcall"].isna() | (df["putcall"].astype(str).str.strip() == "")]

    df[val_col] = _to_num(df[val_col]).fillna(0.0)
    df["_cusip_clean"] = _clean_cusip(df[cusip_col])

    # "How many stocks" definition: distinct CUSIPs with a meaningful position
    # (exclude blank CUSIPs; exclude VALUE<=0).
    meaningful_mask = (df["_cusip_clean"] != "") & (df[val_col] > 0)
    n_distinct_cusips = int(df.loc[meaningful_mask, "_cusip_clean"].nunique())

    # Optional stock-only filter for extra stats (but not used for correctness)
    stock_df = df
    if "titleofclass" in df.columns:
        stock_df = df[df["titleofclass"].astype(str).str.lower().isin(TITLE_CLASS_OF_STOCKS)]

    total_value_raw = float(df[val_col].sum())
    stock_value_raw = float(stock_df[val_col].sum())

    mult = 1000.0 if value_in_thousands else 1.0

    coverpage = _load_coverpage_optional(quarter)
    mgr_name = _coverpage_manager_name(coverpage, accession_number) if coverpage is not None else None
    cp_total_raw = _coverpage_total_value(coverpage, accession_number) if coverpage is not None else None

    print(f"Summary stats for quarter: {quarter}, accession_number: {accession_number}")
    if mgr_name:
        print(f"- Manager (from COVERPAGE): {mgr_name}")

    print(f"- Total number of reported lines (after removing options): {df.shape[0]}")
    print(f"- Number of distinct CUSIPs (VALUE>0, non-empty CUSIP): {n_distinct_cusips}")

    # Prefer coverpage total if available; still print computed total.
    if cp_total_raw is not None:
        print(f"- COVERPAGE total 13F value (raw units): {cp_total_raw:.2f}")
        print(f"- COVERPAGE total 13F value (dollars): {cp_total_raw * mult:.2f}")

    print(f"- Computed total 13F value from INFOTABLE (raw units): {total_value_raw:.2f}")
    print(f"- Computed total 13F value from INFOTABLE (dollars): {total_value_raw * mult:.2f}")

    if "titleofclass" in df.columns:
        print(f"- Stock-like lines (TITLEOFCLASS filter): {stock_df.shape[0]}")
        print(f"- Stock-like value (raw units): {stock_value_raw:.2f}")
        print(f"- Stock-like value (dollars): {stock_value_raw * mult:.2f}")


def one_fund_analysis(
    accession_number: str,
    quarter: str,
    baseline_accession_number: str | None,
    baseline_quarter: str | None,
    value_in_thousands: bool,
):
    infotable_q = _load_infotable(quarter)
    read_one_quarter_summary(accession_number, quarter, value_in_thousands=value_in_thousands)

    if baseline_accession_number is None or baseline_quarter is None:
        return

    infotable_b = _load_infotable(baseline_quarter)

    print(f"\nPerforming comparative analysis using baseline quarter {baseline_quarter}")

    p_q = positions_by_cusip(infotable_q, accession_number, value_in_thousands=value_in_thousands).rename(
        columns={"value_dollars": "v_q", "value": "v_q_raw"}
    )
    p_b = positions_by_cusip(infotable_b, baseline_accession_number, value_in_thousands=value_in_thousands).rename(
        columns={"value_dollars": "v_b", "value": "v_b_raw"}
    )

    merged = p_b.merge(p_q, on="cusip", how="outer", suffixes=("_b", "_q"))

    # Fill missing values
    merged["v_b"] = merged["v_b"].fillna(0.0)
    merged["v_q"] = merged["v_q"].fillna(0.0)

    # Create a display issuer column
    if "nameofissuer_q" in merged.columns and "nameofissuer_b" in merged.columns:
        merged["nameofissuer"] = merged["nameofissuer_q"].fillna(merged["nameofissuer_b"])
    elif "nameofissuer_q" in merged.columns:
        merged["nameofissuer"] = merged["nameofissuer_q"]
    elif "nameofissuer_b" in merged.columns:
        merged["nameofissuer"] = merged["nameofissuer_b"]
    else:
        merged["nameofissuer"] = None

    merged["delta"] = merged["v_q"] - merged["v_b"]

    # Avoid divide-by-zero; pct is relative to baseline
    merged["pct_change"] = merged["delta"] / merged["v_b"].replace(0.0, pd.NA)

    print(f"\nTop 10 Buys from {baseline_quarter} to {quarter} (ranked by dollar value increase):")
    top_buys = merged[merged["delta"] > 0].sort_values(by="delta", ascending=False).head(10)
    for idx, row in enumerate(top_buys.itertuples(index=False), start=1):
        cusip = getattr(row, "cusip")
        issuer = getattr(row, "nameofissuer")
        delta = getattr(row, "delta")
        pct = getattr(row, "pct_change")
        pct_str = "N/A" if pd.isna(pct) else f"{pct:.2%}"
        print(f"[{idx}] CUSIP: {cusip} | Name: {issuer} | Delta: {delta:.2f} | Pct change vs baseline: {pct_str}")

    print(f"\nTop 10 Sells from {baseline_quarter} to {quarter} (ranked by dollar value decrease):")
    top_sells = merged[merged["delta"] < 0].sort_values(by="delta", ascending=True).head(10)
    for idx, row in enumerate(top_sells.itertuples(index=False), start=1):
        cusip = getattr(row, "cusip")
        issuer = getattr(row, "nameofissuer")
        delta = getattr(row, "delta")
        pct = getattr(row, "pct_change")
        pct_str = "N/A" if pd.isna(pct) else f"{pct:.2%}"
        print(f"[{idx}] CUSIP: {cusip} | Name: {issuer} | Delta: {delta:.2f} | Pct change vs baseline: {pct_str}")


if __name__ == "__main__":
    args = get_args()
    one_fund_analysis(
        args.accession_number,
        args.quarter,
        args.baseline_accession_number,
        args.baseline_quarter,
        value_in_thousands=args.value_in_thousands,
    )
