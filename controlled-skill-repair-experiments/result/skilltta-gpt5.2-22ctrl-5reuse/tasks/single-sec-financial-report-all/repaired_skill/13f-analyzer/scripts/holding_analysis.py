import argparse
from pathlib import Path

import pandas as pd

DATA_ROOT = Path("/root")


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
    # remove commas, coerce errors to NaN
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


def get_args():
    parser = argparse.ArgumentParser(description="Analyze fund holdings information")
    parser.add_argument("--cusip", type=str, required=True, help="The CUSIP of the stock to analyze")
    parser.add_argument("--quarter", type=str, required=True, help="The quarter to analyze (e.g., 2025-q3)")
    parser.add_argument("--topk", type=int, default=10, help="The maximum number of results to return")
    parser.add_argument(
        "--value_in_thousands",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Assume 13F VALUE is in $ thousands and convert to dollars for ranking/output.",
    )
    return parser.parse_args()


def topk_managers(cusip: str, quarter: str, topk: int, value_in_thousands: bool = True):
    """Find top-k fund managers holding the given stock CUSIP in the specified quarter.

    Output is ranked by summed position VALUE (market value) for that CUSIP.
    """
    quarter_dir = DATA_ROOT / quarter

    infotable_path = _find_one(quarter_dir, ["INFOTABLE.tsv", "INFOTABLE.csv", "INFOTABLE.parquet", "infotable.parquet"])
    coverpage_path = _find_one(quarter_dir, ["COVERPAGE.tsv", "COVERPAGE.csv", "COVERPAGE.parquet", "coverpage.parquet"])

    infotable = _norm_cols(_read_table(infotable_path))
    coverpage = _norm_cols(_read_table(coverpage_path))

    cusip_col = _first_existing_col(infotable, ["cusip"])
    acc_col = _first_existing_col(infotable, ["accession_number", "accessionnumber"])
    val_col = _first_existing_col(infotable, ["value"])

    # Optional: avoid options lines if a put/call column exists
    if "putcall" in infotable.columns:
        infotable = infotable[infotable["putcall"].isna() | (infotable["putcall"].astype(str).str.strip() == "")]

    infotable[val_col] = _to_num(infotable[val_col]).fillna(0.0)

    q_cusip = cusip.strip().upper()
    holding_details = infotable[infotable[cusip_col].astype(str).str.upper().str.strip() == q_cusip]

    if holding_details.empty:
        print(f"No holdings found for CUSIP {q_cusip} in quarter {quarter}")
        return

    by_acc = holding_details.groupby(acc_col, as_index=False).agg(total_value=(val_col, "sum"))

    # Map accession -> manager name using coverpage
    cp_acc_col = _first_existing_col(coverpage, ["accession_number", "accessionnumber"])
    name_col = _first_existing_col(
        coverpage,
        ["filingmanager_name", "manager_name", "nameofinstitution", "company_name"],
        optional=True,
    )

    acc2name = {}
    if name_col is not None:
        tmp = coverpage[[cp_acc_col, name_col]].dropna(subset=[cp_acc_col])
        acc2name = dict(zip(tmp[cp_acc_col].astype(str), tmp[name_col].astype(str)))

    by_acc["manager"] = by_acc[acc_col].astype(str).map(acc2name).fillna("<UNKNOWN_MANAGER>")

    # Q4 needs manager names, not just accessions: aggregate by manager
    by_mgr = by_acc.groupby("manager", as_index=False).agg(total_value=("total_value", "sum"))
    by_mgr = by_mgr.sort_values("total_value", ascending=False).head(topk)

    if value_in_thousands:
        by_mgr["total_value_dollars"] = by_mgr["total_value"] * 1000.0
        value_label = "Holding value ($)"
        show_value_col = "total_value_dollars"
    else:
        value_label = "Holding value"
        show_value_col = "total_value"

    print(f"Top-{by_mgr.shape[0]} fund managers holding CUSIP {q_cusip} in quarter {quarter}:")
    for idx, row in by_mgr.reset_index(drop=True).iterrows():
        print(f"Rank {idx+1}: Manager = {row['manager']} | {value_label} = {row[show_value_col]:.2f}")


if __name__ == "__main__":
    args = get_args()
    topk_managers(args.cusip, args.quarter, args.topk, value_in_thousands=args.value_in_thousands)
