import argparse
import csv
import os
import re
from difflib import SequenceMatcher
from typing import Sequence, Tuple

_WHITESPACE_RE = re.compile(r"\s+")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")

# The dataset is expected to live under DATA_ROOT/<quarter>/, e.g. /root/2025-q3/INFOTABLE.tsv
DATA_ROOT_DEFAULT = os.environ.get("SEC13F_DATA_ROOT", "/root")

# Keep this list explicit and consistent with other helpers.
TITLE_CLASS_OF_STOCKS = {
    "com",
    "com new",
    "common stock",
    "common",
    "stock",
    "class a",
    "class a com",
    "cl a",
    "cl a com",
    "cl a new",
    "cl b",
    "cl b new",
    "cap stk cl a",
    "cap stk cl c",
    "com cl a",
    "com shs",
    "comm stk",
    "cmn",
    "ord shs",
    "shs cl a",
    "foreign stock",
    "sponsored adr",
    "sponsored ads",
    "adr",
    "equity",
}

_QUARTER_RE = re.compile(r"^(?P<year>\d{4})-q(?P<q>[1-4])$", re.IGNORECASE)


def get_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fuzzy search stock CUSIP by its name")
    parser.add_argument(
        "--keywords",
        type=str,
        required=True,
        help="The stock name or keywords to search for",
    )
    parser.add_argument(
        "--quarter",
        type=str,
        default=None,
        required=False,
        help="Quarter to search within (e.g. 2025-q3). If omitted, auto-detect the latest available quarter under data_root.",
    )
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
        help="Root directory that contains <quarter>/INFOTABLE.tsv (default: /root)",
    )
    return parser.parse_args()


def _require_columns(fieldnames: Sequence[str] | None, required: Sequence[str], source: str) -> None:
    if not fieldnames:
        raise ValueError(f"No header found in {source}")
    missing = [c for c in required if c not in fieldnames]
    if missing:
        raise KeyError(f"Missing required columns {missing} in {source}")


def _normalize_text(text: str) -> str:
    text = (text or "").lower().strip()
    text = _NON_ALNUM_RE.sub(" ", text)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    return text


def _fuzzy_score(query: str, choice: str) -> float:
    """Return a fuzzy score in [0, 100] using stdlib only.

    Uses a token-aware normalization (strip punctuation, collapse whitespace) and
    SequenceMatcher ratio for a lightweight approximation.
    """

    q = _normalize_text(query)
    c = _normalize_text(choice)
    if not q or not c:
        return 0.0

    return SequenceMatcher(None, q, c).ratio() * 100.0


def _available_quarters(data_root: str) -> list[Tuple[int, int, str]]:
    """Return available quarters as (year, q, name) tuples."""

    quarters: list[Tuple[int, int, str]] = []

    try:
        entries = os.listdir(data_root)
    except FileNotFoundError:
        return quarters

    for name in entries:
        m = _QUARTER_RE.match(name)
        if not m:
            continue
        path = os.path.join(data_root, name, "INFOTABLE.tsv")
        if not os.path.exists(path):
            continue
        quarters.append((int(m.group("year")), int(m.group("q")), name))

    return quarters


def _default_quarter(data_root: str) -> str:
    """Pick the latest available quarter if not provided."""

    candidates = _available_quarters(data_root)
    if not candidates:
        raise ValueError(
            f"Could not auto-detect a quarter under data_root={data_root!r}. "
            "Pass --quarter explicitly (e.g. 2025-q3) and ensure <quarter>/INFOTABLE.tsv exists."
        )
    candidates.sort(key=lambda t: (t[0], t[1]), reverse=True)
    return candidates[0][2]


def search_stock_by_name(keywords: str, quarter: str, topk: int, data_root: str) -> None:
    """Fuzzy search stock CUSIP by issuer name within a quarter's INFOTABLE.

    Notes:
    - Restricts to common-equity-like positions using TITLEOFCLASS.
    - Prints one result per unique CUSIP.
    """

    path = f"{data_root}/{quarter}/INFOTABLE.tsv"

    choices: list[tuple[str, str]] = []  # (CUSIP, NAMEOFISSUER)

    with open(path, "r", encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        _require_columns(reader.fieldnames, ["CUSIP", "NAMEOFISSUER", "TITLEOFCLASS"], source=path)

        for row in reader:
            title_norm = (row.get("TITLEOFCLASS") or "").lower().strip()
            if title_norm not in TITLE_CLASS_OF_STOCKS:
                continue

            cusip = (row.get("CUSIP") or "").upper().strip()
            name = (row.get("NAMEOFISSUER") or "").strip()
            if not cusip or not name:
                continue

            choices.append((cusip, name))

    # Keep one representative name per CUSIP (first occurrence).
    by_cusip: dict[str, str] = {}
    for cusip, name in choices:
        if cusip not in by_cusip:
            by_cusip[cusip] = name

    scored: list[tuple[str, str, float]] = [
        (cusip, name, _fuzzy_score(keywords, name)) for cusip, name in by_cusip.items()
    ]
    scored.sort(key=lambda t: (-t[2], t[0]))

    print(f"Search Results (quarter={quarter}):")
    for idx, (cusip, name, score) in enumerate(scored[: max(0, int(topk))], start=1):
        print(f"** Rank {idx} (score = {score:.3f}) **")
        print(f"  Name: {name}")
        print(f"  CUSIP: {cusip}")
        print()


if __name__ == "__main__":
    args = get_args()
    quarter = args.quarter or _default_quarter(args.data_root)
    search_stock_by_name(args.keywords, quarter=quarter, topk=args.topk, data_root=args.data_root)
