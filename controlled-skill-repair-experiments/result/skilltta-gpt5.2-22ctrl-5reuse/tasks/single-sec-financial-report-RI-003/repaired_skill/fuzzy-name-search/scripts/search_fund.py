import argparse

import pandas as pd
from rapidfuzz import fuzz, process


data_root = '/root'


def get_args():
    parser = argparse.ArgumentParser(description='Fuzzy search fund by name')
    parser.add_argument(
        '--keywords',
        type=str,
        default='',
        required=False,
        help='The fund name or keywords to search for',
    )
    parser.add_argument(
        '--accession_number',
        type=str,
        default='',
        help='The accession number to search for',
    )
    parser.add_argument('--quarter', type=str, required=True, help='The quarter to search in')
    parser.add_argument(
        '--topk',
        type=int,
        default=10,
        help='The maximum number of results to return',
    )
    return parser.parse_args()


def _safe_get(row: pd.Series, key: str, default: str = '') -> str:
    if key in row and pd.notna(row[key]):
        return str(row[key])
    return default


def pretty_print(matched_cover: pd.Series, idx: int, score: float):
    accession_number = _safe_get(matched_cover, 'ACCESSION_NUMBER')
    report_qtr = _safe_get(matched_cover, 'REPORTCALENDARORQUARTER')
    mgr_name = _safe_get(matched_cover, 'FILINGMANAGER_NAME')

    street = _safe_get(matched_cover, 'FILINGMANAGER_STREET1')
    if not street:
        street = _safe_get(matched_cover, 'FILINGMANAGER_STREET')

    city = _safe_get(matched_cover, 'FILINGMANAGER_CITY')
    state = _safe_get(matched_cover, 'FILINGMANAGER_STATEORCOUNTRY')
    file_no = _safe_get(matched_cover, 'FORM13FFILENUMBER')

    print(f'** Rank {idx + 1} (score = {score:.3f}) **')
    print(f'  ACCESSION_NUMBER: {accession_number}')
    if report_qtr:
        print(f'  REPORTCALENDARORQUARTER: {report_qtr}')
    if mgr_name:
        print(f'  FILINGMANAGER_NAME: {mgr_name}')
    if street:
        print(f'  FILINGMANAGER_STREET: {street}')
    if city:
        print(f'  FILINGMANAGER_CITY: {city}')
    if state:
        print(f'  FILINGMANAGER_STATEORCOUNTRY: {state}')
    if file_no:
        print(f'  FORM13FFILENUMBER: {file_no}')
    print()


def search_fund_by_name(keywords: str, quarter: str, topk: int = 5):
    """Fuzzy search fund information by manager name."""
    coverpage = pd.read_csv(f'{data_root}/{quarter}/COVERPAGE.tsv', sep='\t', dtype=str)
    if 'FILINGMANAGER_NAME' not in coverpage.columns:
        raise KeyError('COVERPAGE.tsv missing required column FILINGMANAGER_NAME')

    choices = coverpage['FILINGMANAGER_NAME'].dropna().unique().tolist()
    matches = process.extract(keywords, choices, scorer=fuzz.WRatio, limit=topk)

    has_amend = 'ISAMENDMENT' in coverpage.columns

    out_idx = 0
    for match_name, score, _ in matches:
        matched_cover = coverpage[coverpage['FILINGMANAGER_NAME'] == match_name]
        if has_amend:
            matched_cover = matched_cover[matched_cover['ISAMENDMENT'] == 'N']
        if matched_cover.empty:
            continue
        pretty_print(matched_cover.iloc[0], out_idx, score)
        out_idx += 1


def search_fund_by_accession_number(accession_number: str, quarter: str):
    """Exact search fund information by accession_number."""
    coverpage = pd.read_csv(f'{data_root}/{quarter}/COVERPAGE.tsv', sep='\t', dtype=str)
    if 'ACCESSION_NUMBER' not in coverpage.columns:
        raise KeyError('COVERPAGE.tsv missing required column ACCESSION_NUMBER')

    matched_cover = coverpage[coverpage['ACCESSION_NUMBER'].astype(str) == str(accession_number)]
    if matched_cover.empty:
        print(f'No fund found with ACCESSION_NUMBER = {accession_number} in quarter {quarter}')
        return
    pretty_print(matched_cover.iloc[0], 0, 100.0)


if __name__ == '__main__':
    args = get_args()
    if args.accession_number:
        search_fund_by_accession_number(args.accession_number, args.quarter)
    else:
        search_fund_by_name(args.keywords, args.quarter, topk=args.topk)
