import argparse
import csv
import os
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Iterable

# Filing data is expected under /root/<quarter>/
# Allow override for local testing / alternate layouts.
data_root = os.environ.get("SEC13F_DATA_ROOT", "/root")


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
    parser.add_argument("--quarter", type=str, required=True, help="The quarter to search in")
    parser.add_argument(
        "--topk",
        type=int,
        default=10,
        help="The maximum number of results to return",
    )
    return parser.parse_args()


_whitespace_re = re.compile(r"\s+")
_non_word_re = re.compile(r"[^a-z0-9\s]", re.IGNORECASE)


def _normalize_text(s: str) -> str:
    """Normalize text for fuzzy matching."""

    s = (s or "").strip().lower()
    s = _non_word_re.sub(" ", s)
    s = _whitespace_re.sub(" ", s).strip()
    return s


def _token_overlap_score(a: str, b: str) -> float:
    """Return an overlap-based similarity score in [0, 1]."""

    ta = {t for t in _normalize_text(a).split() if t}
    tb = {t for t in _normalize_text(b).split() if t}
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(len(ta), len(tb))


def _similarity_score(query: str, target: str) -> float:
    """Return a similarity score in [0, 100].

    Uses a lightweight heuristic (SequenceMatcher + token overlap) to avoid
    third-party dependencies.
    """

    q = _normalize_text(query)
    t = _normalize_text(target)
    if not q or not t:
        return 0.0
    if q == t:
        return 100.0

    # Sequence similarity.
    seq = SequenceMatcher(None, q, t).ratio()

    # Substring bonus: if query is contained in target (or vice versa), treat as strong match.
    sub = 0.0
    if q in t or t in q:
        sub = min(len(q), len(t)) / max(len(q), len(t))

    tok = _token_overlap_score(q, t)

    return 100.0 * max(seq, sub, tok)


def _tsv_rows(path: str) -> Iterable[dict[str, str]]:
    with open(path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            # DictReader returns OrderedDict[str, str|None]; coerce None -> "" for safety.
            yield {k: (v if v is not None else "") for k, v in row.items()}


def _get_any(row: dict[str, str], keys: list[str], default: str = "") -> str:
    for k in keys:
        if k in row and row[k] not in (None, ""):
            return row[k]
    return default


def pretty_print(matched_cover: dict[str, str], idx: int, score: float):
    accession_number = _get_any(matched_cover, ["ACCESSION_NUMBER"], "")
    report_calendar = _get_any(matched_cover, ["REPORTCALENDARORQUARTER"], "")
    manager_name = _get_any(matched_cover, ["FILINGMANAGER_NAME"], "")
    street = _get_any(matched_cover, ["FILINGMANAGER_STREET1", "FILINGMANAGER_STREET", "FILINGMANAGER_STREET_1"], "")
    city = _get_any(matched_cover, ["FILINGMANAGER_CITY"], "")
    state = _get_any(matched_cover, ["FILINGMANAGER_STATEORCOUNTRY"], "")
    file_no = _get_any(matched_cover, ["FORM13FFILENUMBER"], "")

    print(f"** Rank {idx + 1} (score = {score:.3f}) **")
    print(f"  ACCESSION_NUMBER: {accession_number}")
    print(f"  REPORTCALENDARORQUARTER: {report_calendar}")
    print(f"  FILINGMANAGER_NAME: {manager_name}")
    print(f"  FILINGMANAGER_STREET: {street}")
    print(f"  FILINGMANAGER_CITY: {city}")
    print(f"  FILINGMANAGER_STATEORCOUNTRY: {state}")
    print(f"  FORM13FFILENUMBER: {file_no}")
    print()


@dataclass(frozen=True)
class _Match:
    score: float
    row: dict[str, str]


def _is_amendment_row(row: dict[str, str]) -> bool:
    v = (row.get("ISAMENDMENT") or "").strip().upper()
    return v == "Y" or v == "YES" or v == "TRUE" or v == "1"


def search_fund_by_name(keywords: str, quarter: str, topk: int = 5):
    """Fuzzy search fund information by name."""

    cover_path = os.path.join(data_root, quarter, "COVERPAGE.tsv")
    if not os.path.isfile(cover_path):
        raise SystemExit(
            f"ERROR: Missing COVERPAGE.tsv at {cover_path}. Expected dataset under {data_root}/<quarter>/COVERPAGE.tsv"
        )

    rows = list(_tsv_rows(cover_path))
    if not rows:
        raise SystemExit(f"ERROR: COVERPAGE.tsv is empty for quarter {quarter}")

    # Prefer non-amendment rows when available.
    candidates = [r for r in rows if not _is_amendment_row(r)]
    if not candidates:
        candidates = rows

    matches: list[_Match] = []
    for r in candidates:
        name = r.get("FILINGMANAGER_NAME", "")
        score = _similarity_score(keywords, name)
        if score <= 0:
            continue
        matches.append(_Match(score=score, row=r))

    matches.sort(key=lambda m: m.score, reverse=True)

    for idx, m in enumerate(matches[:topk]):
        pretty_print(m.row, idx, m.score)


def search_fund_by_accession_number(accession_number: str, quarter: str):
    """Exact search fund information by accession_number."""

    cover_path = os.path.join(data_root, quarter, "COVERPAGE.tsv")
    if not os.path.isfile(cover_path):
        raise SystemExit(
            f"ERROR: Missing COVERPAGE.tsv at {cover_path}. Expected dataset under {data_root}/<quarter>/COVERPAGE.tsv"
        )

    accession_number = accession_number.strip()
    for row in _tsv_rows(cover_path):
        if (row.get("ACCESSION_NUMBER") or "").strip() == accession_number:
            pretty_print(row, 0, 100.0)
            return

    print(f"No fund found with ACCESSION_NUMBER = {accession_number} in quarter {quarter}")


if __name__ == "__main__":
    args = get_args()
    if args.accession_number:
        search_fund_by_accession_number(args.accession_number, args.quarter)
    else:
        search_fund_by_name(args.keywords, args.quarter, topk=args.topk)
