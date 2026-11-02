import argparse
import csv
import os
import re
from difflib import SequenceMatcher
from typing import Iterable, Sequence

# The dataset is expected to live under DATA_ROOT/<quarter>/, e.g. /root/2025-q3/COVERPAGE.tsv
DATA_ROOT_DEFAULT = os.environ.get("SEC13F_DATA_ROOT", "/root")

_WHITESPACE_RE = re.compile(r"\s+")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def get_args() -> argparse.Namespace:
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
    parser.add_argument("--quarter", type=str, required=True, help="The quarter to search in (e.g. 2025-q3)")
    parser.add_argument(
        "--topk",
        type=int,
        default=10,
        help="The maximum number of results to return",
    )
    parser.add_argument(
        "--data_root",
        type=str,
        default=DATA_ROOT_DEFAULT,
        help="Root directory that contains <quarter>/COVERPAGE.tsv (default: /root)",
    )

    return parser.parse_args()


def _require_columns(fieldnames: Sequence[str] | None, required: Sequence[str], source: str) -> None:
    if not fieldnames:
        raise ValueError(f"No header found in {source}")
    missing = [c for c in required if c not in fieldnames]
    if missing:
        raise KeyError(f"Missing required columns {missing} in {source}")


def _read_tsv_dicts(path: str) -> Iterable[dict[str, str]]:
    with open(path, "r", encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            # csv.DictReader can return None for missing values; normalize to empty strings.
            yield {k: (v if v is not None else "") for k, v in row.items()}


def _normalize_text(text: str) -> str:
    text = text.lower().strip()
    text = _NON_ALNUM_RE.sub(" ", text)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    return text


def _token_set_ratio(a: str, b: str) -> float:
    """A lightweight fuzzy score inspired by fuzzywuzzy's token_set_ratio.

    Returns a percentage score in [0, 100].
    """

    a_tokens = set(_normalize_text(a).split())
    b_tokens = set(_normalize_text(b).split())
    if not a_tokens or not b_tokens:
        return 0.0

    common = a_tokens & b_tokens
    a_all = " ".join(sorted(common | (a_tokens - common)))
    b_all = " ".join(sorted(common | (b_tokens - common)))
    common_s = " ".join(sorted(common))

    # Use max of a few SequenceMatcher ratios.
    ratios = [
        SequenceMatcher(None, a_all, b_all).ratio(),
        SequenceMatcher(None, common_s, a_all).ratio(),
        SequenceMatcher(None, common_s, b_all).ratio(),
    ]
    return max(ratios) * 100.0


def _fuzzy_score(query: str, choice: str) -> float:
    q = _normalize_text(query)
    c = _normalize_text(choice)
    if not q or not c:
        return 0.0
    # Combine plain ratio and token-set ratio for robustness.
    ratio = SequenceMatcher(None, q, c).ratio() * 100.0
    token_ratio = _token_set_ratio(q, c)
    return max(ratio, token_ratio)


def pretty_print(matched_cover: dict[str, str], idx: int, score: float) -> None:
    print(f"** Rank {idx+1} (score = {score:.3f}) **")
    print(f"  ACCESSION_NUMBER: {matched_cover.get('ACCESSION_NUMBER', '')}")
    print(f"  REPORTCALENDARORQUARTER: {matched_cover.get('REPORTCALENDARORQUARTER', '')}")
    print(f"  FILINGMANAGER_NAME: {matched_cover.get('FILINGMANAGER_NAME', '')}")
    print(f"  FILINGMANAGER_STREET: {matched_cover.get('FILINGMANAGER_STREET1', '')}")
    print(f"  FILINGMANAGER_CITY: {matched_cover.get('FILINGMANAGER_CITY', '')}")
    print(f"  FILINGMANAGER_STATEORCOUNTRY: {matched_cover.get('FILINGMANAGER_STATEORCOUNTRY', '')}")
    print(f"  FORM13FFILENUMBER: {matched_cover.get('FORM13FFILENUMBER', '')}")
    print()


def _coverpage_path(quarter: str, data_root: str) -> str:
    return f"{data_root}/{quarter}/COVERPAGE.tsv"


def search_fund_by_name(keywords: str, quarter: str, topk: int, data_root: str) -> None:
    """Fuzzy search fund information by name."""

    path = _coverpage_path(quarter, data_root=data_root)
    with open(path, "r", encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        _require_columns(
            reader.fieldnames,
            [
                "ACCESSION_NUMBER",
                "FILINGMANAGER_NAME",
                "ISAMENDMENT",
                "REPORTCALENDARORQUARTER",
                "FILINGMANAGER_STREET1",
                "FILINGMANAGER_CITY",
                "FILINGMANAGER_STATEORCOUNTRY",
                "FORM13FFILENUMBER",
            ],
            source=path,
        )
        rows = [{k: (v if v is not None else "") for k, v in row.items()} for row in reader]

    # Prefer non-amendment rows for ranking & printing.
    non_amend = [r for r in rows if r.get("ISAMENDMENT", "").strip() == "N"]

    # Keep one representative row per manager name (first occurrence among non-amendments).
    by_name: dict[str, dict[str, str]] = {}
    for r in non_amend:
        name = r.get("FILINGMANAGER_NAME", "")
        if name and name not in by_name:
            by_name[name] = r

    scored = [
        (name, _fuzzy_score(keywords, name), by_name[name])
        for name in by_name.keys()
    ]
    scored.sort(key=lambda t: (-t[1], _normalize_text(t[0])))

    for idx, (_name, score, row) in enumerate(scored[:topk]):
        pretty_print(row, idx, score)


def search_fund_by_accession_number(accession_number: str, quarter: str, data_root: str) -> None:
    """Exact search fund information by accession_number."""

    path = _coverpage_path(quarter, data_root=data_root)
    for row in _read_tsv_dicts(path):
        if row.get("ACCESSION_NUMBER", "").strip() == accession_number.strip():
            pretty_print(row, 0, 100.0)
            return

    print(f"No fund found with ACCESSION_NUMBER = {accession_number} in quarter {quarter}")


if __name__ == "__main__":
    args = get_args()
    if args.accession_number:
        search_fund_by_accession_number(args.accession_number, args.quarter, data_root=args.data_root)
    else:
        search_fund_by_name(args.keywords, args.quarter, topk=args.topk, data_root=args.data_root)
