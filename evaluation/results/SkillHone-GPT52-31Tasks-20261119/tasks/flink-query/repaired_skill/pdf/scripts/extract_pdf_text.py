#!/usr/bin/env python3
"""Extract text from a PDF with graceful fallbacks.

Why this exists
--------------
Many sandboxes used for evaluation environments do *not* include:
- Poppler tools (e.g., `pdftotext`, `pdftoppm`)
- Common Python PDF libraries (`pypdf`, `pdfplumber`, `pypdfium2`, etc.)

This helper tries several options in a safe order and prints actionable
instructions when none are available.

Important: This script is meant as a *utility* for skills usage. It does not
attempt OCR.

Usage
-----
  python scripts/extract_pdf_text.py input.pdf > output.txt
  python scripts/extract_pdf_text.py input.pdf --pages 1-2

Exit codes
----------
0: success
2: dependency missing / unsupported environment
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Tuple


@dataclass(frozen=True)
class PageRange:
    start: int
    end: int


def _parse_pages(pages: Optional[str]) -> Optional[PageRange]:
    if not pages:
        return None
    m = re.fullmatch(r"(\d+)(?:-(\d+))?", pages.strip())
    if not m:
        raise ValueError("--pages must be like '3' or '1-5'")
    start = int(m.group(1))
    end = int(m.group(2) or m.group(1))
    if start <= 0 or end <= 0 or end < start:
        raise ValueError("Invalid page range")
    return PageRange(start=start, end=end)


def _try_pdftotext(pdf_path: Path, pages: Optional[PageRange]) -> Optional[str]:
    # pdftotext is the fastest/most reliable when present.
    try:
        # `command -v` isn't available cross-platform; just try executing.
        cmd = ["pdftotext", "-layout"]
        if pages:
            cmd += ["-f", str(pages.start), "-l", str(pages.end)]
        cmd += [str(pdf_path), "-"]
        proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout
        # If it ran but produced nothing, still fall through to python parsing.
    except FileNotFoundError:
        return None
    except Exception:
        return None
    return None


def _try_pypdf(pdf_path: Path, pages: Optional[PageRange]) -> Optional[str]:
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception:
        return None

    try:
        reader = PdfReader(str(pdf_path))
        out: List[str] = []
        start_idx = 0
        end_idx = len(reader.pages) - 1
        if pages:
            start_idx = pages.start - 1
            end_idx = pages.end - 1

        for i in range(start_idx, min(end_idx + 1, len(reader.pages))):
            page = reader.pages[i]
            txt = page.extract_text() or ""
            if txt:
                out.append(txt)
        text = "\n".join(out)
        return text if text.strip() else None
    except Exception:
        return None


def extract_text(pdf_path: Path, pages: Optional[PageRange]) -> Tuple[int, str]:
    """Return (exit_code, text_or_error_message)."""

    # 1) Try CLI tools first.
    txt = _try_pdftotext(pdf_path, pages)
    if txt is not None:
        return 0, txt

    # 2) Try pure-python parsing.
    txt = _try_pypdf(pdf_path, pages)
    if txt is not None:
        return 0, txt

    # 3) If nothing works, provide actionable guidance.
    guidance = (
        "ERROR: No PDF text extraction backend is available in this environment.\n\n"
        "Tried:\n"
        "- `pdftotext` (Poppler)\n"
        "- Python package `pypdf`\n\n"
        "Next steps:\n"
        "- If you can install system packages: install Poppler and retry (`pdftotext`).\n"
        "- If you can install Python packages: `pip install pypdf` and retry.\n"
        "- Otherwise: treat the PDF as an opaque binary and use any provided companion\n"
        "  text/markdown schema docs instead.\n"
    )
    return 2, guidance


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract text from a PDF with fallbacks")
    parser.add_argument("pdf", help="Path to input PDF")
    parser.add_argument(
        "--pages",
        help="Optional page range like '3' or '1-5' (1-based, inclusive)",
    )

    args = parser.parse_args()
    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print(f"ERROR: file not found: {pdf_path}", file=sys.stderr)
        return 2

    try:
        page_range = _parse_pages(args.pages)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    code, out = extract_text(pdf_path, page_range)
    if code == 0:
        sys.stdout.write(out)
    else:
        print(out, file=sys.stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
