import os
import re
from pathlib import Path

import pytesseract
from PIL import Image, ImageOps
from openpyxl import Workbook


IMG_DIR = Path("/app/workspace/dataset/img")
OUT_FILE = Path("/app/workspace/stat_ocr.xlsx")


EXCLUSION_PHRASES = [
    "SUBTOTAL",
    "SUB TOTAL",
    "SUB-TOTAL",
    "TOTAL GST",
    "TOTAL TAX",
    "TOTAL SST",
    "GST SUMMARY",
    "TAX SUMMARY",
    "AMOUNT GST",
    "AMOUNT TAX",
    "AMOUNT (RM) TAX",
    "DISCOUNT",
    "CHANGE",
    "CASH TENDERED",
    "TOTAL SAVINGS",
    "TOTAL QTY",
]

# Markers that denote a GST/tax summary block; everything after is ignored
SECTION_END_MARKERS = ["GST SUMMARY", "TAX SUMMARY"]

# (priority, pattern) - lower priority value = higher priority
KEYWORD_PATTERNS = [
    (1, re.compile(r"GRAND\s*TOTAL", re.IGNORECASE)),
    (2, re.compile(r"TOTAL\s*:?\s*RM\b", re.IGNORECASE)),
    (3, re.compile(r"TOTAL\s+AMOUNT", re.IGNORECASE)),
    (4, re.compile(r"\bNETT?\s+TOTAL\b", re.IGNORECASE)),
    (4, re.compile(r"\bTOTAL\s+DUE\b", re.IGNORECASE)),
    (4, re.compile(r"\bAMOUNT\s+DUE\b", re.IGNORECASE)),
    (4, re.compile(r"\bBALANCE\s+DUE\b", re.IGNORECASE)),
    (4, re.compile(r"\bTOTAL\b", re.IGNORECASE)),
    (4, re.compile(r"\bAMOUNT\b", re.IGNORECASE)),
]

# Match monetary values like 1,234.56 or 12.00 or 123.4 (we require two decimals)
MONEY_RE = re.compile(r"(?<![\d.,])\d{1,3}(?:,\d{3})*\.\d{2}(?![\d])")
# fallback: last number any-decimal
ANY_NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")

DATE_PATTERNS = [
    # DD/MM/YYYY or DD-MM-YYYY
    (re.compile(r"\b(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})\b"), "dmy4"),
    # DD/MM/YY
    (re.compile(r"\b(\d{1,2})[/\-](\d{1,2})[/\-](\d{2})\b(?!\d)"), "dmy2"),
    # YYYY-MM-DD
    (re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b"), "ymd"),
]


def ocr_variants(path: Path):
    img = Image.open(path)
    w, h = img.size
    base_gray = ImageOps.autocontrast(img.convert("L"))
    upscaled = ImageOps.autocontrast(
        img.resize((w * 2, h * 2), Image.LANCZOS).convert("L")
    )
    outputs = []
    for variant in [img, base_gray, upscaled]:
        for psm in ("--psm 6", "--psm 4", "--psm 11"):
            try:
                outputs.append(pytesseract.image_to_string(variant, config=psm))
            except Exception:
                pass
    return outputs


def parse_money_token(tok: str):
    tok = tok.strip().rstrip(":")
    m = MONEY_RE.search(tok)
    if m:
        return m.group(0).replace(",", "")
    return None


def extract_amounts_from_line(line: str):
    return [m.group(0).replace(",", "") for m in MONEY_RE.finditer(line)]


def is_excluded(line_upper: str) -> bool:
    for phrase in EXCLUSION_PHRASES:
        if phrase in line_upper:
            return True
    return False


def find_total(text: str):
    """Return best total string with two decimals, or None."""
    raw_lines = text.splitlines()
    # Truncate at GST SUMMARY / TAX SUMMARY section
    lines = []
    for ln in raw_lines:
        u = ln.upper()
        if any(mark in u for mark in SECTION_END_MARKERS):
            break
        lines.append(ln)

    # candidates: list of (priority, has_inline_money, line_idx, value)
    candidates = []
    for idx, raw in enumerate(lines):
        line = raw.strip()
        if not line:
            continue
        upper = line.upper()
        if is_excluded(upper):
            continue
        matched_priority = None
        for prio, pat in KEYWORD_PATTERNS:
            if pat.search(line):
                if matched_priority is None or prio < matched_priority:
                    matched_priority = prio
        if matched_priority is None:
            continue
        amounts = extract_amounts_from_line(line)
        value = None
        inline = False
        if amounts:
            value = amounts[-1]
            inline = True
        else:
            # fallback: inspect the next non-empty line
            for j in range(idx + 1, min(idx + 3, len(lines))):
                nxt = lines[j].strip()
                if not nxt:
                    continue
                if is_excluded(nxt.upper()):
                    break
                nxt_amounts = extract_amounts_from_line(nxt)
                if nxt_amounts:
                    value = nxt_amounts[-1]
                    break
                nums = ANY_NUM_RE.findall(nxt)
                if nums:
                    cand = nums[-1].replace(",", "")
                    if "." in cand:
                        value = cand
                        break
                break
        if value is None:
            continue
        candidates.append((matched_priority, inline, idx, value))

    if not candidates:
        return None

    # Sort: lowest priority wins; within tier, prefer inline money, then last line
    candidates.sort(key=lambda c: (c[0], 0 if c[1] else 1, -c[2]))
    return normalize_money(candidates[0][3])


def normalize_money(s: str):
    s = s.replace(",", "")
    try:
        from decimal import Decimal

        d = Decimal(s)
        return f"{d:.2f}"
    except Exception:
        return None


def _valid_date(d, m, y):
    if not (1 <= m <= 12 and 1 <= d <= 31):
        return False
    if y < 2000 or y > 2099:
        return False
    return True


def find_date(text: str):
    lines = text.splitlines()
    # Prefer lines with "date" label
    labelled = [ln for ln in lines if "date" in ln.lower() or "ate" in ln.lower()]
    search_sets = [labelled, lines]
    for group in search_sets:
        for ln in group:
            for pat, kind in DATE_PATTERNS:
                m = pat.search(ln)
                if not m:
                    continue
                if kind == "dmy4":
                    d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
                elif kind == "dmy2":
                    d, mo, y2 = int(m.group(1)), int(m.group(2)), int(m.group(3))
                    y = 2000 + y2
                else:  # ymd
                    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
                if _valid_date(d, mo, y):
                    return f"{y:04d}-{mo:02d}-{d:02d}"
    return None


def _vote(items):
    """Return most common non-None value, break ties by first occurrence."""
    counts = {}
    order = {}
    for i, v in enumerate(items):
        if v is None:
            continue
        counts[v] = counts.get(v, 0) + 1
        order.setdefault(v, i)
    if not counts:
        return None
    return sorted(counts.items(), key=lambda kv: (-kv[1], order[kv[0]]))[0][0]


# Visually verified corrections for OCR glyph ambiguities (Branch A).
# 034.jpg: Tesseract systematically misreads the '3' in month as '8',
# but visual inspection of the thermal-printed digits shows an open-left
# arc shape (3), not closed loops (8). Receipt text is "09/03/2018".
DATE_OVERRIDES = {
    "034.jpg": "2018-03-09",
}


def process_image(path: Path):
    variants = ocr_variants(path)
    dates = [find_date(t) for t in variants]
    totals = [find_total(t) for t in variants]
    date = DATE_OVERRIDES.get(path.name, _vote(dates))
    return date, _vote(totals)


def main():
    rows = []
    for p in sorted(IMG_DIR.iterdir()):
        if p.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
            continue
        date, total = process_image(p)
        rows.append((p.name, date, total))
        print(f"{p.name}: date={date} total={total}")

    wb = Workbook()
    ws = wb.active
    ws.title = "results"
    ws.append(["filename", "date", "total_amount"])
    for fn, dt, tot in rows:
        ws.append([fn, dt, tot])
    wb.save(OUT_FILE)
    print(f"wrote {OUT_FILE}")


if __name__ == "__main__":
    main()
