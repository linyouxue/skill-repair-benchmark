import argparse

from skills._shared.tsv_utils import iter_tsv, topk_fuzzy

data_root = "/root"


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


def pretty_print(matched_cover, idx, score):
    ACCESSION_NUMBER = matched_cover.get("ACCESSION_NUMBER", "")
    REPORTCALENDARORQUARTER = matched_cover.get("REPORTCALENDARORQUARTER", "")
    FILINGMANAGER_NAME = matched_cover.get("FILINGMANAGER_NAME", "")
    FILINGMANAGER_STREET1 = matched_cover.get("FILINGMANAGER_STREET1", "")
    FILINGMANAGER_CITY = matched_cover.get("FILINGMANAGER_CITY", "")
    FILINGMANAGER_STATEORCOUNTRY = matched_cover.get("FILINGMANAGER_STATEORCOUNTRY", "")
    FORM13FFILENUMBER = matched_cover.get("FORM13FFILENUMBER", "")
    print(f"** Rank {idx+1} (score = {score:.3f}) **")
    print(f"  ACCESSION_NUMBER: {ACCESSION_NUMBER}")
    print(f"  REPORTCALENDARORQUARTER: {REPORTCALENDARORQUARTER}")
    print(f"  FILINGMANAGER_NAME: {FILINGMANAGER_NAME}")
    print(f"  FILINGMANAGER_STREET: {FILINGMANAGER_STREET1}")
    print(f"  FILINGMANAGER_CITY: {FILINGMANAGER_CITY}")
    print(f"  FILINGMANAGER_STATEORCOUNTRY: {FILINGMANAGER_STATEORCOUNTRY}")
    print(f"  FORM13FFILENUMBER: {FORM13FFILENUMBER}")
    print()


def search_fund_by_name(keywords: str, quarter: str, topk: int = 5):
    """Fuzzy search fund information by manager name.

    Reads /root/<quarter>/COVERPAGE.tsv.
    """
    cover_path = f"{data_root}/{quarter}/COVERPAGE.tsv"
    rows = list(iter_tsv(cover_path))

    # Unique manager names
    choices = sorted({r.get("FILINGMANAGER_NAME", "") for r in rows if r.get("FILINGMANAGER_NAME")})
    matches = topk_fuzzy(keywords, choices, k=topk)

    for idx, (match_name, score) in enumerate(matches):
        # Prefer non-amendment rows if the column exists; otherwise accept any.
        candidates = [r for r in rows if r.get("FILINGMANAGER_NAME") == match_name]
        if not candidates:
            continue
        if any("ISAMENDMENT" in r for r in candidates):
            non_amend = [r for r in candidates if (r.get("ISAMENDMENT") or "N") == "N"]
            if non_amend:
                candidates = non_amend
        pretty_print(candidates[0], idx, score)


def search_fund_by_accession_number(accession_number: str, quarter: str):
    """Exact search fund information by accession_number."""
    cover_path = f"{data_root}/{quarter}/COVERPAGE.tsv"
    for row in iter_tsv(cover_path):
        if row.get("ACCESSION_NUMBER") == accession_number:
            pretty_print(row, 0, 100.0)
            return
    print(f"No fund found with ACCESSION_NUMBER = {accession_number} in quarter {quarter}")


if __name__ == "__main__":
    args = get_args()
    if args.accession_number:
        search_fund_by_accession_number(args.accession_number, args.quarter)
    else:
        search_fund_by_name(args.keywords, args.quarter, topk=args.topk)
