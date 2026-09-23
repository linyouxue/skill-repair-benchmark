import argparse

from skills._shared.tsv_utils import iter_tsv, topk_fuzzy, normalize_text

data_root = "/root"
title_class_of_stocks = [
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


def get_args():
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
        default="2025-q2",
        help="Quarter folder under /root (default: 2025-q2)",
    )
    parser.add_argument(
        "--topk",
        type=int,
        default=10,
        help="The maximum number of results to return",
    )
    return parser.parse_args()


def search_stock_by_name(keywords: str, quarter: str = "2025-q2", topk: int = 5):
    """Fuzzy search stock CUSIP by issuer name.

    Reads /root/<quarter>/INFOTABLE.tsv.
    """
    info_path = f"{data_root}/{quarter}/INFOTABLE.tsv"

    # Build a CUSIP -> issuer name map (first-seen) restricted to common-stock-like rows.
    cusip_to_issuer = {}
    for row in iter_tsv(info_path):
        title = (row.get("TITLEOFCLASS") or "").lower().strip()
        if title not in title_class_of_stocks:
            continue
        cusip = (row.get("CUSIP") or "").upper().strip()
        issuer = (row.get("NAMEOFISSUER") or "").strip()
        if not cusip or not issuer:
            continue
        cusip_to_issuer.setdefault(cusip, issuer)

    choices = list(cusip_to_issuer.values())
    matches = topk_fuzzy(keywords, choices, k=topk)

    # Build reverse lookup for display: normalized issuer -> cusips (could be multiple)
    issuer_to_cusips = {}
    for cusip, issuer in cusip_to_issuer.items():
        issuer_to_cusips.setdefault(normalize_text(issuer), []).append(cusip)

    print("Search Results:")
    for idx, (match_name, score) in enumerate(matches):
        key = normalize_text(match_name)
        cusips = issuer_to_cusips.get(key, [])
        cusip = cusips[0] if cusips else ""
        print(f"** Rank {idx+1} (score = {score:.3f}) **")
        print(f"  Name: {match_name}")
        print(f"  CUSIP: {cusip}")
        print()


if __name__ == "__main__":
    args = get_args()
    search_stock_by_name(args.keywords, quarter=args.quarter, topk=args.topk)
