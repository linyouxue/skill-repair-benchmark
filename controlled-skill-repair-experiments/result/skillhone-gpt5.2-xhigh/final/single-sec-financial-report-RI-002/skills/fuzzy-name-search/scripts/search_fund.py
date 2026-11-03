import argparse
import csv
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable

DATA_ROOT = "/root"


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
    parser.add_argument("--quarter", type=str, required=True, help="The quarter to search in")
    parser.add_argument(
        "--topk",
        type=int,
        default=10,
        help="The maximum number of results to return",
    )
    return parser.parse_args()


def _get_first(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        if key in row:
            val = row.get(key)
            if val is None:
                continue
            val = str(val)
            if val.strip() != "":
                return val
    return ""


def pretty_print(matched_cover: dict[str, Any], idx: int, score: float) -> None:
    accession_number = _get_first(matched_cover, "ACCESSION_NUMBER")
    report_quarter = _get_first(matched_cover, "REPORTCALENDARORQUARTER")
    manager_name = _get_first(matched_cover, "FILINGMANAGER_NAME")
    street = _get_first(
        matched_cover,
        "FILINGMANAGER_STREET1",
        "FILINGMANAGER_STREET",
        "FILINGMANAGER_STREET2",
    )
    city = _get_first(matched_cover, "FILINGMANAGER_CITY")
    state = _get_first(matched_cover, "FILINGMANAGER_STATEORCOUNTRY")
    file_number = _get_first(matched_cover, "FORM13FFILENUMBER")

    print(f"** Rank {idx + 1} (score = {score:.3f}) **")
    print(f"  ACCESSION_NUMBER: {accession_number}")
    print(f"  REPORTCALENDARORQUARTER: {report_quarter}")
    print(f"  FILINGMANAGER_NAME: {manager_name}")
    print(f"  FILINGMANAGER_STREET: {street}")
    print(f"  FILINGMANAGER_CITY: {city}")
    print(f"  FILINGMANAGER_STATEORCOUNTRY: {state}")
    print(f"  FORM13FFILENUMBER: {file_number}")
    print()


_WORD_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)


def _normalize_text(text: str) -> str:
    # Normalize for fuzzy matching: lowercase, keep alphanumerics, collapse spaces.
    tokens = _WORD_RE.findall((text or "").lower())
    return " ".join(tokens)


def _ratio(a: str, b: str) -> float:
    if not a and not b:
        return 100.0
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio() * 100.0


def _token_sort_ratio(a: str, b: str) -> float:
    a_tokens = sorted(_normalize_text(a).split())
    b_tokens = sorted(_normalize_text(b).split())
    return _ratio(" ".join(a_tokens), " ".join(b_tokens))


def _partial_ratio(a: str, b: str) -> float:
    # Best-effort approximation of a partial (substring) ratio.
    a_n = _normalize_text(a)
    b_n = _normalize_text(b)
    if not a_n or not b_n:
        return 0.0
    if len(a_n) > len(b_n):
        a_n, b_n = b_n, a_n

    if a_n in b_n:
        return 100.0

    matcher = SequenceMatcher(None, a_n, b_n)
    best = 0.0
    for block in matcher.get_matching_blocks():
        # Align the block so that the matching section lines up.
        start = max(0, block[1] - block[0])
        end = start + len(a_n)
        substring = b_n[start:end]
        best = max(best, _ratio(a_n, substring))
    return best


def fuzzy_score(query: str, choice: str) -> float:
    """Return a 0-100 similarity score.

    We do not rely on external fuzzy-matching libraries in the runtime.
    """
    query = query or ""
    choice = choice or ""

    # Combine a few cheap similarity heuristics.
    scores = [
        _ratio(_normalize_text(query), _normalize_text(choice)),
        _token_sort_ratio(query, choice),
        _partial_ratio(query, choice),
    ]
    return max(scores)


@dataclass(frozen=True)
class CoverpageRow:
    score: float
    manager_name: str
    accession_number: str
    row: dict[str, Any]


def _read_coverpage_rows(quarter: str) -> list[dict[str, Any]]:
    coverpage_path = Path(DATA_ROOT) / quarter / "COVERPAGE.tsv"
    if not coverpage_path.exists():
        raise SystemExit(f"ERROR: COVERPAGE.tsv not found at {coverpage_path}")

    with coverpage_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        return list(reader)


def _prefer_non_amendments(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return rows
    if "ISAMENDMENT" not in rows[0]:
        return rows

    non_amend = [r for r in rows if str(r.get("ISAMENDMENT", "")).strip().upper() == "N"]
    return non_amend if non_amend else rows


def search_fund_by_name(keywords: str, quarter: str, topk: int = 5) -> None:
    """Fuzzy search fund information by manager name."""
    keywords = (keywords or "").strip()
    if keywords == "":
        raise SystemExit("ERROR: --keywords must be non-empty when --accession_number is not provided")

    coverpage = _read_coverpage_rows(quarter)
    coverpage = _prefer_non_amendments(coverpage)

    candidates: list[CoverpageRow] = []
    seen_accessions: set[str] = set()

    for row in coverpage:
        accession = _get_first(row, "ACCESSION_NUMBER").strip()
        if accession == "" or accession in seen_accessions:
            continue

        manager_name = _get_first(row, "FILINGMANAGER_NAME")
        score = fuzzy_score(keywords, manager_name)
        candidates.append(CoverpageRow(score=score, manager_name=manager_name, accession_number=accession, row=row))
        seen_accessions.add(accession)

    if not candidates:
        raise SystemExit(f"ERROR: No candidates found in COVERPAGE.tsv for quarter {quarter}")

    # Sort by score desc, then name asc, then accession number asc.
    candidates.sort(key=lambda c: (-c.score, _normalize_text(c.manager_name), c.accession_number))

    for idx, cand in enumerate(candidates[: max(topk, 0)]):
        pretty_print(cand.row, idx, cand.score)


def search_fund_by_accession_number(accession_number: str, quarter: str) -> None:
    """Exact search fund information by accession number."""
    accession_number = (accession_number or "").strip()
    if accession_number == "":
        raise SystemExit("ERROR: --accession_number must be non-empty")

    coverpage = _read_coverpage_rows(quarter)
    matched = [r for r in coverpage if _get_first(r, "ACCESSION_NUMBER").strip() == accession_number]

    if not matched:
        print(f"No fund found with ACCESSION_NUMBER = {accession_number} in quarter {quarter}")
        return

    # Prefer non-amendment filing when multiple rows exist.
    matched = _prefer_non_amendments(matched)
    pretty_print(matched[0], 0, 100.0)


if __name__ == "__main__":
    args = get_args()
    if args.accession_number:
        search_fund_by_accession_number(args.accession_number, args.quarter)
    else:
        search_fund_by_name(args.keywords, args.quarter, topk=args.topk)
