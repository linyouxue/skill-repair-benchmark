import argparse
from pathlib import Path

import pandas as pd
from rapidfuzz import fuzz, process

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
    parser = argparse.ArgumentParser(description="Fuzzy search fund by name")
    parser.add_argument(
        "--keywords",
        type=str,
        default="",
        required=False,
        help="The fund name or keywords to search for",
    )
    parser.add_argument(
        "--accession_number",
        type=str,
        default="",
        help="The accession number to search for",
    )
    parser.add_argument("--quarter", type=str, required=True, help="The quarter to search in (e.g., 2025-q3)")
    parser.add_argument(
        "--topk",
        type=int,
        default=10,
        help="The maximum number of results to return",
    )
    return parser.parse_args()


def pretty_print(matched_cover: pd.Series, idx: int, score: float, colmap: dict):
    def g(key: str, default: str = ""):
        col = colmap.get(key)
        if not col:
            return default
        v = matched_cover.get(col)
        return "" if pd.isna(v) else str(v)

    print(f"** Rank {idx+1} (score = {score:.3f}) **")
    print(f"  ACCESSION_NUMBER: {g('accession')}")
    print(f"  REPORTCALENDARORQUARTER: {g('report_date')}")
    print(f"  FILINGMANAGER_NAME: {g('manager_name')}")
    print(f"  FILINGMANAGER_STREET: {g('street')}")
    print(f"  FILINGMANAGER_CITY: {g('city')}")
    print(f"  FILINGMANAGER_STATEORCOUNTRY: {g('state')}")
    print(f"  FORM13FFILENUMBER: {g('form_file_no')}")
    print()


def _load_coverpage(quarter: str) -> pd.DataFrame:
    quarter_dir = DATA_ROOT / quarter
    coverpage_path = _find_one(quarter_dir, ["COVERPAGE.tsv", "COVERPAGE.csv", "COVERPAGE.parquet", "coverpage.parquet"])
    return _norm_cols(_read_table(coverpage_path))


def search_fund_by_name(keywords: str, quarter: str, topk: int = 5):
    coverpage = _load_coverpage(quarter)

    accession_col = _first_existing_col(coverpage, ["accession_number", "accessionnumber"])
    manager_col = _first_existing_col(
        coverpage,
        ["filingmanager_name", "manager_name", "nameofinstitution", "company_name"],
    )
    report_col = _first_existing_col(coverpage, ["reportcalendarorquarter", "report_date", "report_period"], optional=True)
    street_col = _first_existing_col(coverpage, ["filingmanager_street1", "street1", "street"], optional=True)
    city_col = _first_existing_col(coverpage, ["filingmanager_city", "city"], optional=True)
    state_col = _first_existing_col(coverpage, ["filingmanager_stateorcountry", "stateorcountry", "state"], optional=True)
    form_col = _first_existing_col(coverpage, ["form13ffilenumber", "form_file_number"], optional=True)

    is_amend_col = _first_existing_col(coverpage, ["isamendment"], optional=True)

    colmap = {
        "accession": accession_col,
        "manager_name": manager_col,
        "report_date": report_col,
        "street": street_col,
        "city": city_col,
        "state": state_col,
        "form_file_no": form_col,
        "is_amendment": is_amend_col,
    }

    # Build fuzzy choices
    choices = coverpage[manager_col].fillna("").astype(str).unique().tolist()
    matches = process.extract(keywords, choices, scorer=fuzz.WRatio, limit=topk)

    shown = 0
    for idx, (match_name, score, _) in enumerate(matches):
        matched_rows = coverpage[coverpage[manager_col].astype(str) == str(match_name)]
        if is_amend_col is not None:
            matched_rows = matched_rows[matched_rows[is_amend_col].astype(str).str.upper().isin(["N", "NO", "0", "FALSE", "F", ""]) | matched_rows[is_amend_col].isna()]
        if matched_rows.empty:
            continue
        pretty_print(matched_rows.iloc[0], shown, score, colmap)
        shown += 1


def search_fund_by_accession_number(accession_number: str, quarter: str):
    coverpage = _load_coverpage(quarter)

    accession_col = _first_existing_col(coverpage, ["accession_number", "accessionnumber"])
    manager_col = _first_existing_col(
        coverpage,
        ["filingmanager_name", "manager_name", "nameofinstitution", "company_name"],
    )

    report_col = _first_existing_col(coverpage, ["reportcalendarorquarter", "report_date", "report_period"], optional=True)
    street_col = _first_existing_col(coverpage, ["filingmanager_street1", "street1", "street"], optional=True)
    city_col = _first_existing_col(coverpage, ["filingmanager_city", "city"], optional=True)
    state_col = _first_existing_col(coverpage, ["filingmanager_stateorcountry", "stateorcountry", "state"], optional=True)
    form_col = _first_existing_col(coverpage, ["form13ffilenumber", "form_file_number"], optional=True)

    colmap = {
        "accession": accession_col,
        "manager_name": manager_col,
        "report_date": report_col,
        "street": street_col,
        "city": city_col,
        "state": state_col,
        "form_file_no": form_col,
        "is_amendment": _first_existing_col(coverpage, ["isamendment"], optional=True),
    }

    matched_cover = coverpage[coverpage[accession_col].astype(str) == str(accession_number)]
    if matched_cover.empty:
        print(f"No fund found with ACCESSION_NUMBER = {accession_number} in quarter {quarter}")
        return
    pretty_print(matched_cover.iloc[0], 0, 100.0, colmap)


if __name__ == "__main__":
    args = get_args()
    if args.accession_number:
        search_fund_by_accession_number(args.accession_number, args.quarter)
    else:
        search_fund_by_name(args.keywords, args.quarter, topk=args.topk)
