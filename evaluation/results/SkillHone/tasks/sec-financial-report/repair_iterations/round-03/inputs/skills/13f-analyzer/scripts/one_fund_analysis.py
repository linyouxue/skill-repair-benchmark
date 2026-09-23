import argparse

from skills._shared.tsv_utils import iter_tsv, safe_float


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
    parser = argparse.ArgumentParser(description="Analyze grouped fund holdings information")
    parser.add_argument(
        "--accession_number",
        type=str,
        required=True,
        help="The accession number of the fund to analyze",
    )
    parser.add_argument("--quarter", type=str, required=True, help="The quarter of the fund to analyze")

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
    return parser.parse_args()


def _aggregate_by_cusip(accession_number: str, quarter: str):
    """Return (stats, cusip->value, cusip->issuer) for stock-like rows."""
    info_path = f"{data_root}/{quarter}/INFOTABLE.tsv"

    total_rows = 0
    total_value = 0.0

    stock_rows = 0
    stock_total_value = 0.0
    cusip_value = {}
    cusip_issuer = {}

    for row in iter_tsv(info_path):
        if row.get("ACCESSION_NUMBER") != accession_number:
            continue
        total_rows += 1
        v = safe_float(row.get("VALUE", ""), 0.0)
        total_value += v

        title = (row.get("TITLEOFCLASS") or "").lower().strip()
        if title not in title_class_of_stocks:
            continue
        cusip = (row.get("CUSIP") or "").upper().strip()
        if not cusip:
            continue
        stock_rows += 1
        stock_total_value += v
        cusip_value[cusip] = cusip_value.get(cusip, 0.0) + v
        if cusip not in cusip_issuer and (row.get("NAMEOFISSUER") or "").strip():
            cusip_issuer[cusip] = row.get("NAMEOFISSUER").strip()

    stats = {
        "total_holdings_rows": total_rows,
        "total_value": total_value,
        "stock_holdings_rows": stock_rows,
        "unique_stock_cusips": len(cusip_value),
        "stock_total_value": stock_total_value,
    }
    return stats, cusip_value, cusip_issuer


def read_one_quarter_data(accession_number, quarter):
    stats, cusip_value, cusip_issuer = _aggregate_by_cusip(accession_number, quarter)

    print(f"Summary stats for quarter: {quarter}, accession_number: {accession_number}")
    print(f"- Total number of holdings: {stats['total_holdings_rows']}")
    print(f"- Total AUM: {stats['total_value']:.2f}")
    print(f"- Number of stock holdings (rows): {stats['stock_holdings_rows']}")
    print(f"- Number of stocks held (unique CUSIPs): {stats['unique_stock_cusips']}")
    print(f"- Total stock AUM: {stats['stock_total_value']:.2f}")

    if stats["stock_holdings_rows"] == 0:
        print(f"ERROR: No data found for ACCESSION_NUMBER = {accession_number} in quarter {quarter}")
        raise SystemExit(1)

    return cusip_value, cusip_issuer


def one_fund_analysis(accession_number, quarter, baseline_accession_number, baseline_quarter):
    cusip_value, cusip_issuer = read_one_quarter_data(accession_number, quarter)
    if baseline_accession_number is None or baseline_quarter is None:
        return

    print(f"Performing comparative analysis using baseline quarter {baseline_quarter}")
    base_cusip_value, base_cusip_issuer = read_one_quarter_data(baseline_accession_number, baseline_quarter)

    all_cusips = set(cusip_value) | set(base_cusip_value)
    merged = []
    for cusip in all_cusips:
        v = cusip_value.get(cusip, 0.0)
        vb = base_cusip_value.get(cusip, 0.0)
        abs_change = v - vb
        pct_change = abs_change / (vb if vb != 0 else 1.0)
        issuer = cusip_issuer.get(cusip) or base_cusip_issuer.get(cusip) or ""
        merged.append((cusip, issuer, v, vb, abs_change, pct_change))

    merged.sort(key=lambda t: t[4], reverse=True)

    print(f"Top 10 Buys from {baseline_quarter} to {quarter}:")
    buys = [t for t in merged if t[4] > 0][:10]
    for idx, (cusip, issuer, _v, _vb, abs_change, pct_change) in enumerate(buys):
        print(
            f"[{idx+1}] CUSIP: {cusip}, Name: {issuer} | Abs change: {abs_change:.2f} | pct change: {pct_change:.2%}"
        )

    print(f"\nTop 10 Sells from {baseline_quarter} to {quarter}:")
    sells = [t for t in merged if t[4] < 0][-10:]
    sells.sort(key=lambda t: t[4])  # most negative first
    for idx, (cusip, issuer, _v, _vb, abs_change, pct_change) in enumerate(sells):
        print(
            f"[{idx+1}] CUSIP: {cusip}, Name: {issuer} | Abs change: {abs_change:.2f} | pct change: {pct_change:.2%}"
        )


if __name__ == "__main__":
    args = get_args()
    one_fund_analysis(args.accession_number, args.quarter, args.baseline_accession_number, args.baseline_quarter)
