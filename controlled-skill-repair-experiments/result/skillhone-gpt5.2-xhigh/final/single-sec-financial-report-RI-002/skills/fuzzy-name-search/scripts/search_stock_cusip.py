import argparse
import csv
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

DATA_ROOT = "/root"

# Keep this list aligned with 13f-analyzer/one_fund_analysis.py.
# It defines the conservative common-equity TITLEOFCLASS universe.
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


def get_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fuzzy search a stock CUSIP by issuer name")
    parser.add_argument(
        "--keywords",
        type=str,
        required=True,
        help="Stock/issuer name or keywords to search for",
    )
    parser.add_argument(
        "--topk",
        type=int,
        default=10,
        help="The maximum number of results to return",
    )
    parser.add_argument(
        "--quarter",
        type=str,
        default=None,
        help=(
            "Optional quarter to search in (e.g., 2025-q3). If omitted, the helper searches across all "
            "available /root/<quarter>/INFOTABLE.tsv files."
        ),
    )
    parser.add_argument(
        "--include_options",
        action="store_true",
        help=(
            "Include option rows (PUT/CALL) if present. By default the helper excludes rows where PUTCALL is set, "
            "so the returned CUSIPs reflect common-equity positions."
        ),
    )
    return parser.parse_args()


_WORD_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)


def _normalize_text(text: str) -> str:
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
        start = max(0, block[1] - block[0])
        end = start + len(a_n)
        substring = b_n[start:end]
        best = max(best, _ratio(a_n, substring))
    return best


def fuzzy_score(query: str, choice: str) -> float:
    scores = [
        _ratio(_normalize_text(query), _normalize_text(choice)),
        _token_sort_ratio(query, choice),
        _partial_ratio(query, choice),
    ]
    return max(scores)


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    return str(value).strip() == ""


def _discover_quarters(data_root: str) -> list[str]:
    root = Path(data_root)
    if not root.exists():
        return []

    quarters: list[str] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        infotable = child / "INFOTABLE.tsv"
        if infotable.exists():
            quarters.append(child.name)
    return quarters


@dataclass(frozen=True)
class StockRow:
    name: str
    cusip: str
    quarter: str


def _iter_stock_rows(quarters: list[str], include_options: bool) -> list[StockRow]:
    rows: list[StockRow] = []
    seen_cusip: set[str] = set()

    for quarter in quarters:
        path = Path(DATA_ROOT) / quarter / "INFOTABLE.tsv"
        if not path.exists():
            continue

        with path.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                title = str(row.get("TITLEOFCLASS", "") or "").strip().lower()
                if title not in TITLE_CLASS_OF_STOCKS:
                    continue

                if not include_options and "PUTCALL" in row and not _is_blank(row.get("PUTCALL")):
                    continue

                cusip = str(row.get("CUSIP", "") or "").strip().upper()
                if cusip == "" or cusip in seen_cusip:
                    continue

                name = str(row.get("NAMEOFISSUER", "") or "").strip().lower()
                if name == "":
                    continue

                rows.append(StockRow(name=name, cusip=cusip, quarter=quarter))
                seen_cusip.add(cusip)

    return rows


def search_stock_by_name(keywords: str, topk: int = 10, quarter: str | None = None, include_options: bool = False) -> None:
    keywords = (keywords or "").strip()
    if keywords == "":
        raise SystemExit("ERROR: --keywords must be non-empty")

    if quarter:
        quarters = [quarter]
    else:
        quarters = _discover_quarters(DATA_ROOT)

    if not quarters:
        raise SystemExit(
            "ERROR: Could not discover any quarters under /root. Provide --quarter explicitly (e.g., --quarter 2025-q3)."
        )

    stocks = _iter_stock_rows(quarters, include_options=include_options)
    if not stocks:
        raise SystemExit("ERROR: No candidate stock rows found in the selected quarter(s)")

    scored = [(fuzzy_score(keywords, s.name), s) for s in stocks]
    scored.sort(key=lambda t: (-t[0], t[1].name, t[1].cusip))

    print("Search Results:")
    for rank, (score, stock) in enumerate(scored[: max(topk, 0)], start=1):
        print(f"** Rank {rank} (score = {score:.3f}) **")
        print(f"  Name: {stock.name}")
        print(f"  CUSIP: {stock.cusip}")
        if quarter is None:
            print(f"  Quarter (sampled from): {stock.quarter}")
        print()


if __name__ == "__main__":
    args = get_args()
    search_stock_by_name(args.keywords, topk=args.topk, quarter=args.quarter, include_options=args.include_options)
