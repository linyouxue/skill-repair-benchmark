"""Extract date and total_amount from receipt images."""
import os
import re
import json
from pathlib import Path
from decimal import Decimal

import pytesseract
from PIL import Image, ImageOps, ImageFilter
from openpyxl import Workbook


IMG_DIR = Path("/app/workspace/dataset/img")
OUT_XLSX = Path("/app/workspace/stat_ocr.xlsx")


# Keyword tiers (priority: lower index = higher priority).
TIER_KEYWORDS = [
    [r"GRAND\s*TOTAL"],
    [r"TOTAL\s*:?\s*RM"],
    [r"TOTAL\s*AMOUNT"],
    [r"BALANCE\s*DUE", r"AMOUNT\s*DUE", r"TOTAL\s*DUE",
     r"NETT?\s*TOTAL", r"\bTOTAL\b", r"\bAMOUNT\b"],
]

# Always-exclude keywords.
STRICT_EXCLUDE = [
    r"SUB[-\s]*TOTAL",
    r"DISCOUNT", r"\bCHANGE\b", r"CASH\s*TENDERED",
]
# Tax-related exclusions: skip the line unless it also mentions "incl"/
# "inclusive"/"including" (meaning the amount already contains tax).
TAX_EXCLUDE = [r"\bTAX\b", r"\bGST\b", r"\bSST\b"]
INCL_RE = re.compile(r"INCL(?:USIVE|UDING|\.)?\b|\bINCL\b", re.I)
SUMMARY_RE = re.compile(r"\bSUMMARY\b", re.I)

MONEY_RE = re.compile(r"(?<![\d.])(?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2}(?![\d])")


def ocr_variants(path: Path):
    img = Image.open(path)
    gray = ImageOps.grayscale(img)
    w, h = img.size
    upscaled = ImageOps.autocontrast(img.resize((w * 3, h * 3), Image.LANCZOS).convert("L"))
    variants = [
        ("gray", gray),
        ("auto", ImageOps.autocontrast(gray)),
        ("sharp", gray.filter(ImageFilter.SHARPEN)),
        ("3x", upscaled),
    ]
    results = []  # list of (name, psm, text)
    for name, v in variants:
        for psm in ("--psm 6", "--psm 4", "--psm 11"):
            try:
                text = pytesseract.image_to_string(v, config=psm)
                results.append((name, psm, text))
            except Exception:
                pass
    return results


def _line_excluded(line_upper: str) -> bool:
    if any(re.search(p, line_upper) for p in STRICT_EXCLUDE):
        return True
    if any(re.search(p, line_upper) for p in TAX_EXCLUDE):
        # A tax-related line stays only when it explicitly says the amount
        # includes tax (e.g., "Total Incl. GST 10.40").
        if not INCL_RE.search(line_upper):
            return True
    return False


def _extract_from_variant(text):
    """Return (tier_idx, value) or (None, None)."""
    lines = text.splitlines()
    # Mark lines that come after a "SUMMARY" header (GST/Tax summary blocks
    # typically repeat label words like "Total" with per-column amounts).
    summary_from = None
    for i, line in enumerate(lines):
        if SUMMARY_RE.search(line):
            summary_from = i + 1
            break

    for tier_idx, patterns in enumerate(TIER_KEYWORDS):
        matches = []  # (line_index, line, next_line)
        for i, line in enumerate(lines):
            if summary_from is not None and i >= summary_from:
                continue
            upper = line.upper()
            if _line_excluded(upper):
                continue
            if not any(re.search(p, upper) for p in patterns):
                continue
            matches.append((i, line, lines[i + 1] if i + 1 < len(lines) else ""))
        if not matches:
            continue
        # Prefer the LAST matching line - final/net totals appear last.
        for _, line, nxt in reversed(matches):
            nums = MONEY_RE.findall(line)
            if nums:
                return tier_idx, nums[-1]
            nxt_nums = MONEY_RE.findall(nxt)
            if nxt_nums:
                return tier_idx, nxt_nums[-1]
    return None, None


def extract_total(all_texts):
    """Return monetary string with 2 decimals, or None."""
    # Each variant votes. Prefer the tier that occurs; within same tier, majority.
    candidates = []  # list of (tier_idx, value)
    for text in all_texts:
        tier, val = _extract_from_variant(text)
        if val is not None:
            candidates.append((tier, val))
    if not candidates:
        return None
    # Prefer the lowest tier index observed
    best_tier = min(c[0] for c in candidates)
    tier_vals = [c[1] for c in candidates if c[0] == best_tier]
    counts = {}
    for v in tier_vals:
        counts[v] = counts.get(v, 0) + 1
    best = max(counts.items(), key=lambda x: (x[1], x[0]))[0]
    try:
        d = Decimal(best.replace(",", ""))
        return f"{d:.2f}"
    except Exception:
        return None


DATE_PATTERNS = [
    # D(D)/M(M)/YY(YY) with / or - or .
    re.compile(r"(?<!\d)(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})(?!\d)"),
    # YYYY-MM-DD
    re.compile(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)"),
    # Merged 8-digit DDMMYYYY from OCR (e.g., 2032018 missing digit) - handled separately
]


def _normalize_year(y: str) -> int:
    y = int(y)
    if y < 100:
        y = 2000 + y
    return y


def _try_date(d: int, m: int, y: int):
    if 1 <= d <= 31 and 1 <= m <= 12 and 2000 <= y <= 2099:
        try:
            import datetime
            return datetime.date(y, m, d).isoformat()
        except ValueError:
            return None
    return None


DATE_TOKEN_RE = re.compile(r"\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}")


def _collect_date_boxes(img):
    """Return list of (l,t,r,b) boxes for date-like regions.

    Looks for both direct date tokens and the full line to the right of a
    "Date" label (helps when OCR mangles the date value itself).
    """
    boxes = []
    try:
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    except Exception:
        return boxes
    n = len(data["text"])
    for i in range(n):
        word = (data["text"][i] or "").strip()
        if not word:
            continue
        if DATE_TOKEN_RE.search(word):
            x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
            boxes.append((x, y, x + w, y + h))
    # Fallback: anchor on "Date" labels and crop the rest of the line.
    img_w, img_h = img.size
    for i in range(n):
        word = (data["text"][i] or "").strip().lower().rstrip(":")
        if word not in ("date", "dato", "data", "tarikh"):
            continue
        x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
        boxes.append((x + w, y, min(img_w, x + w + max(w * 6, 300)), y + h))
    return boxes


def focused_date_ocr(img):
    """Try to locate the date value and re-OCR it with a digit whitelist.
    Returns a list of candidate date tokens.
    """
    boxes = _collect_date_boxes(img)
    # If none found at native resolution, try an upscaled copy.
    if not boxes:
        w, h = img.size
        up = img.resize((w * 2, h * 2), Image.LANCZOS)
        upscaled_boxes = _collect_date_boxes(up)
        boxes = [(l // 2, t // 2, r // 2, b // 2) for (l, t, r, b) in upscaled_boxes]
    results = []
    for (l, t, r, b) in boxes:
        pad_x = max(10, (r - l) // 4)
        pad_y = max(4, (b - t) // 2)
        crop = img.crop((max(0, l - pad_x), max(0, t - pad_y), r + pad_x, b + pad_y))
        # Use multiple small scales and nearest-neighbor to preserve glyph
        # strokes (bicubic/lanczos tends to close open "3" into "8").
        for scale, interp in ((2, Image.LANCZOS), (3, Image.LANCZOS),
                               (3, Image.NEAREST), (4, Image.NEAREST)):
            up = crop.resize((crop.width * scale, crop.height * scale), interp)
            gray = ImageOps.grayscale(up)
            for v in (gray, ImageOps.autocontrast(gray)):
                for psm in ("--psm 7", "--psm 6", "--psm 11"):
                    cfg = psm + " -c tessedit_char_whitelist=0123456789/-."
                    try:
                        txt = pytesseract.image_to_string(v, config=cfg).strip()
                    except Exception:
                        continue
                    for m in DATE_TOKEN_RE.finditer(txt):
                        results.append(m.group(0))
    return results


def _candidates_from_token(tok, counts):
    # Try D[-/.]M[-/.]Y
    m = re.fullmatch(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})", tok)
    if m:
        d, mo, y = m.group(1), m.group(2), m.group(3)
        try:
            iso = _try_date(int(d), int(mo), _normalize_year(y))
            if iso:
                counts[iso] = counts.get(iso, 0) + 1
        except Exception:
            pass


def extract_date(all_texts, img=None):
    """Return date string YYYY-MM-DD or None."""
    cand_counts = {}
    # Focused OCR votes count more (weight 3) since digit-whitelist is
    # more accurate for date glyphs than full-page OCR.
    if img is not None:
        for tok in focused_date_ocr(img):
            m = re.fullmatch(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})", tok)
            if not m:
                continue
            d_s, mo_s, y_s = m.group(1), m.group(2), m.group(3)
            iso = _try_date(int(d_s), int(mo_s), _normalize_year(y_s))
            if not iso:
                continue
            # Weight tokens whose day/month are zero-padded (DD/MM) higher
            # than loose 1-digit readings, which tend to be OCR noise.
            weight = 10 if len(d_s) == 2 and len(mo_s) == 2 else 2
            cand_counts[iso] = cand_counts.get(iso, 0) + weight

    for text in all_texts:
        # First look at lines containing "DATE" to anchor
        lines = text.splitlines()
        for line in lines:
            # standard patterns
            for m in DATE_PATTERNS[0].finditer(line):
                d, mo, y = m.group(1), m.group(2), m.group(3)
                try:
                    iso = _try_date(int(d), int(mo), _normalize_year(y))
                    if iso:
                        cand_counts[iso] = cand_counts.get(iso, 0) + 1
                except Exception:
                    pass
            for m in DATE_PATTERNS[1].finditer(line):
                y, mo, d = m.group(1), m.group(2), m.group(3)
                iso = _try_date(int(d), int(mo), int(y))
                if iso:
                    cand_counts[iso] = cand_counts.get(iso, 0) + 1

        # Also look for merged 7-8 digit date near "Date" label
        for i, line in enumerate(lines):
            if re.search(r"\bDATE\b", line, re.I):
                # try line and next line
                search_text = line + " " + (lines[i + 1] if i + 1 < len(lines) else "")
                # try 7 or 8 digit sequences
                for m in re.finditer(r"(?<!\d)(\d{7,8})(?!\d)", search_text):
                    s = m.group(1)
                    if len(s) == 8:
                        # DDMMYYYY
                        for d_, mo_, y_ in [(s[0:2], s[2:4], s[4:8])]:
                            iso = _try_date(int(d_), int(mo_), int(y_))
                            if iso:
                                cand_counts[iso] = cand_counts.get(iso, 0) + 1
                    elif len(s) == 7:
                        # try DMMYYYY
                        d_, mo_, y_ = s[0:1], s[1:3], s[3:7]
                        iso = _try_date(int(d_), int(mo_), int(y_))
                        if iso:
                            cand_counts[iso] = cand_counts.get(iso, 0) + 1

    if not cand_counts:
        return None
    return max(cand_counts.items(), key=lambda x: (x[1], x[0]))[0]


def process_file(path: Path):
    img = Image.open(path)
    variants = ocr_variants(path)
    texts = [t for _, _, t in variants]
    date = extract_date(texts, img=img)
    total = extract_total(texts)
    return date, total


def main():
    rows = []
    for fname in sorted(os.listdir(IMG_DIR)):
        if not fname.lower().endswith((".jpg", ".jpeg", ".png")):
            continue
        path = IMG_DIR / fname
        date, total = process_file(path)
        print(f"{fname}: date={date} total={total}")
        rows.append((fname, date, total))

    wb = Workbook()
    ws = wb.active
    ws.title = "results"
    ws.append(["filename", "date", "total_amount"])
    for fname, date, total in rows:
        ws.append([fname, date, total])
    wb.save(OUT_XLSX)
    print(f"Saved to {OUT_XLSX}")


if __name__ == "__main__":
    main()
