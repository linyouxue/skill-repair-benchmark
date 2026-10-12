from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable, Optional

import pytesseract
from pytesseract import Output
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
from openpyxl import Workbook


IMG_DIR = Path("/app/workspace/dataset/img")
OUT_XLSX = Path("/app/workspace/stat_ocr.xlsx")


@dataclass(frozen=True)
class Line:
    text: str
    left: int
    top: int
    right: int
    bottom: int

    @property
    def cy(self) -> float:
        return (self.top + self.bottom) / 2


@dataclass
class Candidate:
    value: str
    score: float


_DIGIT_FIX = str.maketrans(
    {
        "O": "0",
        "o": "0",
        "I": "1",
        "l": "1",
        "|": "1",
        "S": "5",
    }
)


def iter_images(img_dir: Path) -> list[Path]:
    exts = {".jpg", ".jpeg", ".png", ".webp"}
    return sorted([p for p in img_dir.iterdir() if p.is_file() and p.suffix.lower() in exts], key=lambda p: p.name)


def preprocess_variants(img: Image.Image) -> list[tuple[str, Image.Image]]:
    base = img.convert("RGB")
    gray = ImageOps.grayscale(base)
    gray_ac = ImageOps.autocontrast(gray)

    sharp = gray_ac.filter(ImageFilter.SHARPEN)

    # Mild thresholding; receipts vary a lot, so keep it gentle
    thr = gray_ac.point(lambda p: 255 if p > 170 else 0)

    # Upscale can help tiny text
    scale = 2
    up = gray_ac.resize((gray_ac.width * scale, gray_ac.height * scale), Image.Resampling.LANCZOS)

    # Slight contrast boost
    enh = ImageEnhance.Contrast(gray_ac).enhance(1.4)

    return [
        ("gray_ac", gray_ac),
        ("sharp", sharp),
        ("contrast", enh),
        ("thr", thr),
        ("up", up),
    ]


def ocr_lines(img: Image.Image, psm: int) -> list[Line]:
    data = pytesseract.image_to_data(img, output_type=Output.DICT, config=f"--oem 3 --psm {psm}")

    buckets: dict[tuple[int, int, int], list[int]] = {}
    n = len(data["text"])
    for i in range(n):
        txt = (data["text"][i] or "").strip()
        if not txt:
            continue
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        buckets.setdefault(key, []).append(i)

    lines: list[Line] = []
    for idxs in buckets.values():
        words = [data["text"][i].strip() for i in idxs if (data["text"][i] or "").strip()]
        if not words:
            continue
        lefts = [data["left"][i] for i in idxs]
        tops = [data["top"][i] for i in idxs]
        rights = [data["left"][i] + data["width"][i] for i in idxs]
        bottoms = [data["top"][i] + data["height"][i] for i in idxs]
        lines.append(Line(" ".join(words).strip(), min(lefts), min(tops), max(rights), max(bottoms)))

    lines.sort(key=lambda l: (l.top, l.left))
    return lines


def norm(s: str) -> str:
    s = s.upper()
    s = s.replace("$", "S")
    s = re.sub(r"\s+", " ", s).strip()
    s = s.replace("TOTAI", "TOTAL")
    s = s.replace("T0TAL", "TOTAL")
    return s


_MONEY_RE = re.compile(r"(?:(?:RM|MYR|USD|SGD|\$)\s*)?([0-9OIl|S]{1,3}(?:,[0-9OIl|S]{3})*|[0-9OIl|S]+)(?:\.([0-9OIl|S]{1,3}))")


def extract_money_tokens(text: str) -> list[str]:
    out: list[str] = []
    for m in _MONEY_RE.finditer(text):
        whole = (m.group(1) or "").translate(_DIGIT_FIX)
        frac = (m.group(2) or "").translate(_DIGIT_FIX)
        if not whole or not frac:
            continue
        whole = whole.replace(",", "")
        if not whole.isdigit() or not frac.isdigit():
            continue
        out.append(f"{whole}.{frac}")
    return out


def parse_money_to_2dp(token: str) -> Optional[str]:
    token = token.replace(",", "")
    try:
        d = Decimal(token)
    except InvalidOperation:
        return None

    # Heuristic: if OCR gave 3 decimals, try a stricter re-read; here we reject
    tup = d.as_tuple()
    decimals = -tup.exponent if tup.exponent < 0 else 0
    if decimals == 2:
        return f"{d:.2f}"
    if decimals == 1:
        return f"{d.quantize(Decimal('0.00')):.2f}"
    if decimals == 0:
        return f"{d.quantize(Decimal('0.00')):.2f}"
    return None


def crop_with_padding(img: Image.Image, box: tuple[int, int, int, int], pad: int = 15) -> Image.Image:
    l, t, r, b = box
    l = max(0, l - pad)
    t = max(0, t - pad)
    r = min(img.width, r + pad)
    b = min(img.height, b + pad)
    return img.crop((l, t, r, b))


def _most_common(values: Iterable[str]) -> Optional[str]:
    counts: dict[str, int] = {}
    for v in values:
        counts[v] = counts.get(v, 0) + 1
    if not counts:
        return None
    return max(counts.items(), key=lambda kv: (kv[1], kv[0]))[0]


def refine_date_from_crop(crop: Image.Image) -> Optional[str]:
    counts: dict[str, int] = {}
    for _, v in preprocess_variants(crop):
        txt = pytesseract.image_to_string(v, config="--oem 3 --psm 7")
        for d in parse_dates_from_text(norm(txt)):
            counts[d] = counts.get(d, 0) + 1

    if not counts:
        return None

    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    best_date, best_n = ranked[0]
    second_n = ranked[1][1] if len(ranked) > 1 else 0

    if best_n >= 2 and best_n > second_n:
        return best_date
    return None


def refine_money_from_crop(crop: Image.Image) -> Optional[str]:
    found: list[str] = []
    for _, v in preprocess_variants(crop):
        txt = pytesseract.image_to_string(v, config="--oem 3 --psm 7")
        tokens = extract_money_tokens(norm(txt))
        for tok in tokens:
            p = parse_money_to_2dp(tok)
            if p is not None:
                found.append(p)
    return _most_common(found)



def best_total_candidate(lines: list[Line], img: Image.Image) -> Optional[Candidate]:
    pos_patterns: list[tuple[int, list[str]]] = [
        (100, ["GRAND TOTAL"]),
        (90, ["TOTAL RM", "TOTAL: RM"]),
        (80, ["TOTAL AMOUNT"]),
        (70, ["TOTAL DUE", "AMOUNT DUE", "BALANCE DUE", "NETT TOTAL", "NET TOTAL"]),
        (60, ["TOTAL", "AMOUNT"]),
        (50, ["TOTAL"]),
        (40, ["AMOUNT"]),
    ]

    neg = ["SUBTOTAL", "SUB TOTAL", "TAX", "GST", "SST", "DISCOUNT", "CHANGE", "CASH TENDERED"]

    best: Optional[Candidate] = None
    for i, ln in enumerate(lines):
        n = norm(ln.text)
        base = None
        for score, keys in pos_patterns:
            if all(k in n for k in keys):
                base = score
                break
        if base is None:
            continue

        penalty = 0
        for k in neg:
            if k in n:
                penalty += 20

        tokens = extract_money_tokens(n)
        box = (ln.left, ln.top, ln.right, ln.bottom)

        used_next = False
        if not tokens and i + 1 < len(lines):
            nxt = lines[i + 1]
            if abs(nxt.cy - ln.cy) < max(30, (ln.bottom - ln.top) * 2):
                nt = norm(nxt.text)
                if not any(x in nt for x in ["TOTAL", "SUB", "TAX", "GST", "SST", "CHANGE", "CASH"]):
                    tokens = extract_money_tokens(nt)
                    if tokens:
                        box = (
                            min(ln.left, nxt.left),
                            min(ln.top, nxt.top),
                            max(ln.right, nxt.right),
                            max(ln.bottom, nxt.bottom),
                        )
                        used_next = True

        if not tokens:
            continue

        # Prefer last token on the line (often right-aligned amount)
        parsed = None
        for tok in reversed(tokens):
            parsed = parse_money_to_2dp(tok)
            if parsed is not None:
                break
        if parsed is None:
            crop = crop_with_padding(img, box)
            parsed = refine_money_from_crop(crop)
        if parsed is None:
            continue

        y_frac = ln.cy / max(1, img.height)
        score = float(base - penalty + y_frac * 10)
        if used_next:
            score -= 1.0

        if best is None or score > best.score:
            best = Candidate(parsed, score)

    return best


_DATE_YMD = re.compile(r"\b(20\d{2}|19\d{2})[\-/\.](\d{1,2})[\-/\.](\d{1,2})\b")
_DATE_DMY = re.compile(r"\b(\d{1,2})[\-/\.](\d{1,2})[\-/\.](\d{2,4})\b")


def parse_dates_from_text(text: str) -> list[str]:
    t = text.translate(_DIGIT_FIX)
    out: list[str] = []

    for y, m, d in _DATE_YMD.findall(t):
        try:
            dt = datetime(int(y), int(m), int(d))
        except ValueError:
            continue
        out.append(dt.strftime("%Y-%m-%d"))

    for d, m, y in _DATE_DMY.findall(t):
        yy = int(y)
        if yy < 100:
            yy = 2000 + yy
        try:
            dt = datetime(yy, int(m), int(d))
        except ValueError:
            continue
        out.append(dt.strftime("%Y-%m-%d"))

    return out


def best_date_candidate(lines: list[Line], img: Image.Image) -> Optional[Candidate]:
    best: Optional[Candidate] = None

    for ln in lines:
        n = norm(ln.text)
        dates = parse_dates_from_text(n)
        if not dates:
            continue

        base = 10
        if "DATE" in n:
            base = 80
        elif "ORD" in n and "#" in n:
            base = 40
        elif "INVOICE" in n:
            base = 30

        crop = crop_with_padding(img, (ln.left, ln.top, ln.right, ln.bottom))
        refined = refine_date_from_crop(crop)
        chosen = refined if refined is not None else dates[0]

        y_frac = ln.cy / max(1, img.height)
        score = float(base - y_frac * 2 + (0.5 if refined is not None else 0.0))

        if best is None or score > best.score:
            best = Candidate(chosen, score)

    return best


def extract_fields(img_path: Path) -> tuple[Optional[str], Optional[str]]:
    img = Image.open(img_path)
    best_date: Optional[Candidate] = None
    best_total: Optional[Candidate] = None

    for _, variant in preprocess_variants(img):
        for psm in (6, 4):
            lines = ocr_lines(variant, psm)
            if not lines:
                continue

            d = best_date_candidate(lines, variant)
            if d is not None and (best_date is None or d.score > best_date.score + 5):
                best_date = d

            t = best_total_candidate(lines, variant)
            if t is not None and (best_total is None or t.score > best_total.score):
                best_total = t

            if best_date is not None and best_total is not None and best_date.score >= 70 and best_total.score >= 70:
                break

    return (best_date.value if best_date else None, best_total.value if best_total else None)


def write_xlsx(rows: list[tuple[str, Optional[str], Optional[str]]], out_path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "results"

    ws.append(["filename", "date", "total_amount"])
    for fn, dt, tot in rows:
        ws.append([fn, dt, tot])

    # Ensure only one sheet exists
    for name in list(wb.sheetnames):
        if name != "results":
            del wb[name]

    wb.save(out_path)


def main() -> None:
    rows: list[tuple[str, Optional[str], Optional[str]]] = []
    for p in iter_images(IMG_DIR):
        date, total = extract_fields(p)
        rows.append((p.name, date, total))

    write_xlsx(rows, OUT_XLSX)


if __name__ == "__main__":
    main()
