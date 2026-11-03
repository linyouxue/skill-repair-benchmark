import argparse
import csv
import os
import re
from difflib import SequenceMatcher
from typing import Iterable

# Filing data is expected under /root/<quarter>/
# Allow override for local testing / alternate layouts.
data_root = os.environ.get("SEC13F_DATA_ROOT", "/root")

# A pragmatic allow-list of common-equity TITLEOFCLASS values.
# Values are compared case-insensitively after stripping.
# NOTE: Keep in sync with /skills/13f-analyzer/scripts/one_fund_analysis.py
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
    parser = argparse.ArgumentParser(description="Fuzzy search stock CUSIP by issuer name")
    parser.add_argument(
        "--keywords",
        type=str,
        required=True,
        help="Issuer name / keywords to search for",
    )
    parser.add_argument(
        "--quarter",
        type=str,
        default="",
        required=False,
        help=(
            "Quarter to search in (e.g., 2025-q3). "
            "If omitted, the helper scans all available datasets under $SEC13F_DATA_ROOT (default /root)."
        ),
    )
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
    s = (s or "").strip().lower()
    s = _non_word_re.sub(" ", s)
    s = _whitespace_re.sub(" ", s).strip()
    return s


def _token_overlap_score(a: str, b: str) -> float:
    ta = {t for t in _normalize_text(a).split() if t}
    tb = {t for t in _normalize_text(b).split() if t}
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(len(ta), len(tb))


def _similarity_score(query: str, target: str) -> float:
    """Return a similarity score in [0, 100]."""

    q = _normalize_text(query)
    t = _normalize_text(target)
    if not q or not t:
        return 0.0
    if q == t:
        return 100.0

    seq = SequenceMatcher(None, q, t).ratio()
    sub = 0.0
    if q in t or t in q:
        sub = min(len(q), len(t)) / max(len(q), len(t))
    tok = _token_overlap_score(q, t)
    return 100.0 * max(seq, sub, tok)


def _is_common_equity_position(row: dict[str, str]) -> bool:
    title = (row.get("TITLEOFCLASS") or "").strip().lower()
    if title not in title_class_of_stocks:
        return False

    # Exclude options when PUTCALL is present and non-empty.
    putcall = (row.get("PUTCALL") or "").strip().upper()
    if putcall:
        return False

    return True


def _discover_quarters(root: str) -> list[str]:
    """Return a sorted list of quarter directory names under root."""

    quarter_re = re.compile(r"^\d{4}-q[1-4]$", re.IGNORECASE)
    quarters: list[str] = []
    try:
        for name in os.listdir(root):
            if not quarter_re.match(name):
                continue
            if os.path.isfile(os.path.join(root, name, "INFOTABLE.tsv")):
                quarters.append(name)
    except FileNotFoundError:
        return []
    except PermissionError:
        return []

    return sorted(quarters)


def _iter_quarters(requested_quarter: str) -> Iterable[str]:
    if requested_quarter:
        return [requested_quarter]
    return _discover_quarters(data_root)


def _tsv_rows(path: str) -> Iterable[dict[str, str]]:
    with open(path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            yield {k: (v if v is not None else "") for k, v in row.items()}


def _load_stock_universe(quarters: Iterable[str]) -> list[tuple[str, str]]:
    """Load a (CUSIP, issuer_name) universe from one or more quarters."""

    seen: set[tuple[str, str]] = set()
    out: list[tuple[str, str]] = []

    for q in quarters:
        path = os.path.join(data_root, q, "INFOTABLE.tsv")
        if not os.path.isfile(path):
            continue

        try:
            for row in _tsv_rows(path):
                if not _is_common_equity_position(row):
                    continue
                cusip = (row.get("CUSIP") or "").strip().upper()
                name = _normalize_text(row.get("NAMEOFISSUER") or "")
                if not cusip or not name:
                    continue
                key = (cusip, name)
                if key in seen:
                    continue
                seen.add(key)
                out.append(key)
        except FileNotFoundError:
            continue

    return out


def search_stock_by_name(keywords: str, topk: int = 10, quarter: str = ""):
    """Fuzzy-search a stock issuer name and print candidate common-equity CUSIPs."""

    quarters = list(_iter_quarters(quarter))
    if not quarters:
        raise SystemExit(
            "ERROR: No quarter datasets found under $SEC13F_DATA_ROOT (default /root). "
            "Expected <root>/<quarter>/INFOTABLE.tsv (e.g., /root/2025-q3/INFOTABLE.tsv)."
        )

    pairs = _load_stock_universe(quarters)
    if not pairs:
        raise SystemExit("ERROR: No common-equity rows found in the available INFOTABLE datasets.")

    issuer_to_cusips: dict[str, set[str]] = {}
    for cusip, issuer in pairs:
        issuer_to_cusips.setdefault(issuer, set()).add(cusip)

    choices = list(issuer_to_cusips.keys())
    query = _normalize_text(keywords)

    scored = [(name, _similarity_score(query, name)) for name in choices]
    scored.sort(key=lambda t: t[1], reverse=True)

    quarter_desc = quarter if quarter else ", ".join(quarters)
    print(f"Search Results (quarters scanned: {quarter_desc}):")

    rank = 0
    for name, score in scored:
        if rank >= topk:
            break
        cusips = sorted(issuer_to_cusips.get(name, set()))
        if not cusips:
            continue
        rank += 1
        print(f"** Rank {rank} (score = {score:.3f}) **")
        print(f"  Name: {name}")
        if len(cusips) == 1:
            print(f"  CUSIP: {cusips[0]}")
        else:
            print("  CUSIPs:")
            for c in cusips:
                print(f"    - {c}")
        print()


if __name__ == "__main__":
    args = get_args()
    search_stock_by_name(args.keywords, topk=args.topk, quarter=args.quarter)
