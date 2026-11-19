#!/usr/bin/env python3
"""Write a strict, autograded-friendly XLSX.

Many benchmark tasks compare produced XLSX files *exactly* (sheet names, rows,
columns). This helper creates a workbook with exactly one sheet and writes
header + rows as literal values.

Key properties
- Exactly one worksheet (named by --sheet)
- No formulas, charts, tables, pivots, or named ranges
- Deterministic ordering: input rows are written in provided order

Usage:
  python3 write_strict_xlsx.py --output out.xlsx --sheet results \
      --header filename,date,total_amount \
      --row 000.jpg,2020-01-01,12.34 --row 001.jpg,,

Notes
- Empty strings are written as empty cells (None).
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

from openpyxl import Workbook


def write_strict_xlsx(
    out_path: Path,
    sheet_name: str,
    header: list[str],
    rows: list[list[object]],
) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_name

    ws.append(header)
    for row in rows:
        ws.append([None if v == "" else v for v in row])

    # Ensure no extra default sheet exists.
    for name in list(wb.sheetnames):
        if name != sheet_name:
            del wb[name]

    wb.save(out_path)


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Write a strict single-sheet XLSX")
    ap.add_argument("--output", required=True)
    ap.add_argument("--sheet", required=True)
    ap.add_argument("--header", required=True, help="Comma-separated header fields")
    ap.add_argument(
        "--row",
        action="append",
        default=[],
        help="Comma-separated row values; can be supplied multiple times",
    )

    args = ap.parse_args(argv)

    header = [h.strip() for h in args.header.split(",")]
    rows: list[list[object]] = []
    for r in args.row:
        rows.append([c for c in r.split(",")])

    write_strict_xlsx(Path(args.output), args.sheet, header, rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
