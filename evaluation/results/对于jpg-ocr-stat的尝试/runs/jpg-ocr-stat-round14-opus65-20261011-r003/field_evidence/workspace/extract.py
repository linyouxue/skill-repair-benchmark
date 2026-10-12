import os
import re
from pathlib import Path
import pytesseract
from PIL import Image, ImageOps
import openpyxl

IMG_DIR = Path("/app/workspace/dataset/img")
OUT_XLSX = Path("/app/workspace/stat_ocr.xlsx")

# Tier keywords; lower tier index = higher priority
TIER_KEYWORDS = [
    ["GRAND TOTAL", "GRANDTOTAL"],
    ["TOTAL RM", "TOTAL: RM"],
    ["TOTAL AMOUNT"],
    ["NETT TOTAL", "NET TOTAL", "TOTAL DUE", "AMOUNT DUE",
     "BALANCE DUE", "TOTAL", "AMOUNT"],
]

EXCLUDE_IN_LINE = ["SUBTOTAL", "SUB TOTAL", "SUB-TOTAL",
                   "DISCOUNT", "CHANGE", "CASH TENDERED"]
SECTION_CUTOFFS = ["GST SUMMARY", "TAX SUMMARY", "TAX TOTALS",
                   "GST BREAKDOWN", "TAX BREAKDOWN"]

MONEY_RE = re.compile(
    r"(?<![A-Za-z0-9])(\d{1,3}(?:,\d{3})+\.\d{1,2}|\d+\.\s?\d{1,2}|\d+:\d{2}|\d+\s\d{2}(?!\d))(?![A-Za-z0-9])"
)
INT_RE = re.compile(r"(?<![A-Za-z0-9.])\d+(?![A-Za-z0-9.])")


def preprocess_variants(img):
    """Return list of (name, pil_image) variants for OCR."""
    g = img.convert("L")
    g = ImageOps.autocontrast(g)
    w, h = g.size
    if max(w, h) < 1500:
        upscaled = g.resize((w * 2, h * 2), Image.LANCZOS)
    else:
        upscaled = g
    # Preprocessed first so its results are preferred on ties
    return [("gray_up", upscaled), ("orig", img)]


OCR_CONFIGS = ["", "--psm 6", "--psm 4", "--psm 11"]


def ocr(img, config=""):
    return pytesseract.image_to_string(img, config=config)


def normalize_up(line):
    return re.sub(r"\s+", " ", line.strip()).upper()


def squash(s):
    return re.sub(r"[^A-Z0-9]", "", s.upper())


def parse_money(s):
    s = s.replace(",", "").replace(":", ".")
    if "." not in s:
        m = re.fullmatch(r"(\d+)\s(\d{2})", s)
        if m:
            s = m.group(1) + "." + m.group(2)
    s = s.replace(" ", "")
    try:
        return float(s)
    except Exception:
        return None


def last_money_in_line(line):
    """Prefer money-like numbers (with decimal) over bare integers."""
    monies = MONEY_RE.findall(line)
    for m in reversed(monies):
        v = parse_money(m)
        if v is not None:
            return v
    return None


def keyword_matches(line_up, line_squashed, kw):
    kw_sq = squash(kw)
    if kw == "TOTAL":
        if not re.search(r"\bTOTAL\b", line_up):
            return False
        if re.search(r"SUB[\s-]?TOTAL", line_up):
            return False
        return True
    if kw == "AMOUNT":
        return bool(re.search(r"\bAMOUNT\b", line_up))
    if " " in kw:
        return kw in line_up or kw_sq in line_squashed
    return kw in line_up or kw_sq in line_squashed


def line_excluded(line_up):
    if any(e in line_up for e in EXCLUDE_IN_LINE):
        return True
    if re.match(r"^\s*(GST|TAX|SST|6ST)\b", line_up):
        return True
    if re.match(r"^\s*TOTAL\s+(GST|TAX|SST|6ST)\b", line_up):
        return True
    return False


def find_total_in_text(text):
    """Return (tier_idx, amount) or (None, None)."""
    raw_lines = text.splitlines()
    cutoff = len(raw_lines)
    for i, raw in enumerate(raw_lines):
        up = normalize_up(raw)
        if any(ch in up for ch in SECTION_CUTOFFS):
            cutoff = min(cutoff, i)

    lines = []
    for i, raw in enumerate(raw_lines):
        up = normalize_up(raw)
        lines.append((i, raw, up, squash(up)))

    for tier_idx, kws in enumerate(TIER_KEYWORDS):
        for kw in kws:
            matches = []
            for i, raw, up, sq in lines:
                if i >= cutoff:
                    break
                if not up:
                    continue
                if not keyword_matches(up, sq, kw):
                    continue
                if line_excluded(up):
                    continue
                matches.append((i, raw, up))
            if not matches:
                continue
            # Last match preferred
            for idx in range(len(matches) - 1, -1, -1):
                i, raw, up = matches[idx]
                v = last_money_in_line(raw)
                if v is not None:
                    return tier_idx, v
                # Fallback: next non-empty line last money
                for j in range(i + 1, min(i + 3, len(raw_lines))):
                    if not raw_lines[j].strip():
                        continue
                    v = last_money_in_line(raw_lines[j])
                    if v is not None:
                        return tier_idx, v
                    break
    return None, None


DATE_RE_LONG = re.compile(r"\b(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})\b")
DATE_RE_SHORT = re.compile(r"\b(\d{1,2})[/\-](\d{1,2})[/\-](\d{2})\b")


def validate(d, m, y):
    return 1 <= d <= 31 and 1 <= m <= 12 and 1990 <= y <= 2099


def find_date_in_text(text):
    for m_ in DATE_RE_LONG.finditer(text):
        d, mo, y = int(m_.group(1)), int(m_.group(2)), int(m_.group(3))
        if validate(d, mo, y):
            return f"{y:04d}-{mo:02d}-{d:02d}"
    for m_ in DATE_RE_SHORT.finditer(text):
        d, mo, y = int(m_.group(1)), int(m_.group(2)), int(m_.group(3))
        y = 2000 + y if y < 70 else 1900 + y
        if validate(d, mo, y):
            return f"{y:04d}-{mo:02d}-{d:02d}"
    return None


def format_amount(v):
    return None if v is None else f"{v:.2f}"


def process(path):
    img = Image.open(path)
    variants = preprocess_variants(img)

    texts = []
    for vname, vimg in variants:
        for cfg in OCR_CONFIGS:
            try:
                t = ocr(vimg, config=cfg)
            except Exception:
                t = ""
            texts.append(t)

    date = None
    for t in texts:
        d = find_date_in_text(t)
        if d is not None:
            date = d
            break

    results = []
    for t in texts:
        tier, amt = find_total_in_text(t)
        if amt is not None:
            results.append((tier, amt))

    total = None
    if results:
        best_tier = min(r[0] for r in results)
        amts = [r[1] for r in results if r[0] == best_tier]
        counts = {}
        order = []
        for a in amts:
            if a not in counts:
                counts[a] = 0
                order.append(a)
            counts[a] += 1
        # Pick highest count, ties broken by first occurrence
        total = max(order, key=lambda a: (counts[a], -order.index(a)))

    return date, format_amount(total)


def main():
    files = sorted(f for f in os.listdir(IMG_DIR)
                   if f.lower().endswith((".jpg", ".jpeg", ".png")))

    results = []
    for f in files:
        p = IMG_DIR / f
        try:
            date, total = process(p)
        except Exception as e:
            print(f"ERROR {f}: {e}")
            date, total = None, None
        print(f"{f}: date={date} total={total}")
        results.append((f, date, total))

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "results"
    ws.append(["filename", "date", "total_amount"])
    for f, d, t in results:
        ws.append([f, d, t])
    wb.save(OUT_XLSX)
    print(f"Saved to {OUT_XLSX}")


if __name__ == "__main__":
    main()
