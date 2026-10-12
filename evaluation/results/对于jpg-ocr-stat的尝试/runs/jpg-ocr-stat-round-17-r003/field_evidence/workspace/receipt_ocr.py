import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pytesseract
from PIL import Image, ImageFilter, ImageOps
from openpyxl import Workbook

IMG_DIR = Path("/app/workspace/dataset/img")
OUT_XLSX = Path("/app/workspace/stat_ocr.xlsx")
EVIDENCE_JSON = Path("/app/workspace/ocr_evidence.json")

MONEY_RE = re.compile(r"(?<!\d)(\d{1,3}(?:,\d{3})*(?:\.\d{2})|\d+(?:\.\d{2}))(?!\d)")

NON_PAYABLE_CUES = {
    "SUBTOTAL",
    "SUB TOTAL",
    "TAX",
    "GST",
    "SST",
    "DISCOUNT",
    "CHANGE",
    "CASH TENDERED",
}

KEYWORD_GROUPS = [
    ["GRAND TOTAL"],
    ["TOTAL RM", "TOTAL: RM"],
    ["TOTAL AMOUNT"],
    [
        "TOTAL DUE",
        "AMOUNT DUE",
        "BALANCE DUE",
        "NETT TOTAL",
        "NET TOTAL",
        "TOTAL",
        "AMOUNT",
    ],
]

MONTHS = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "SEPT": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}


@dataclass(frozen=True)
class OCRLine:
    text: str
    bbox: tuple[int, int, int, int]  # left, top, right, bottom
    conf: float
    source: str  # variant/psm


def _preprocess_variants(img: Image.Image) -> list[tuple[str, Image.Image]]:
    base = img.convert("L")
    variants: list[tuple[str, Image.Image]] = []

    ac = ImageOps.autocontrast(base)
    variants.append(("gray_autocontrast", ac))

    sharp = ac.filter(ImageFilter.SHARPEN)
    variants.append(("gray_autocontrast_sharpen", sharp))

    inv = ImageOps.invert(ac)
    variants.append(("gray_autocontrast_invert", inv))

    # Mild thresholding (kept conservative)
    thr = ac.point(lambda p: 255 if p > 160 else 0)
    variants.append(("gray_autocontrast_thresh160", thr))

    # Upscale if very small
    if img.width < 1200:
        scale = 2
        up = ac.resize((img.width * scale, img.height * scale))
        variants.append(("gray_autocontrast_up2x", up))

    return variants


def _ocr_lines(img: Image.Image, source: str, psm: int) -> list[OCRLine]:
    cfg = f"--psm {psm}"
    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT, config=cfg)

    # Group words by (block, par, line)
    groups: dict[tuple[int, int, int], list[int]] = {}
    n = len(data.get("text", []))
    for i in range(n):
        txt = (data["text"][i] or "").strip()
        if not txt:
            continue
        key = (int(data["block_num"][i]), int(data["par_num"][i]), int(data["line_num"][i]))
        groups.setdefault(key, []).append(i)

    lines: list[OCRLine] = []
    for _, idxs in groups.items():
        words = [data["text"][i].strip() for i in idxs if (data["text"][i] or "").strip()]
        if not words:
            continue
        confs = []
        lefts, tops, rights, bottoms = [], [], [], []
        for i in idxs:
            try:
                c = float(data["conf"][i])
            except Exception:
                c = -1.0
            if c >= 0:
                confs.append(c)
            l = int(data["left"][i])
            t = int(data["top"][i])
            w = int(data["width"][i])
            h = int(data["height"][i])
            lefts.append(l)
            tops.append(t)
            rights.append(l + w)
            bottoms.append(t + h)

        line_text = " ".join(words)
        conf = sum(confs) / len(confs) if confs else -1.0
        bbox = (min(lefts), min(tops), max(rights), max(bottoms))
        lines.append(OCRLine(text=line_text, bbox=bbox, conf=conf, source=f"{source}/psm{psm}"))

    # Sort top-to-bottom then left-to-right
    lines.sort(key=lambda ln: (ln.bbox[1], ln.bbox[0]))
    return lines


def _normalize(s: str) -> str:
    s = s.upper()
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _parse_money_token(tok: str) -> str | None:
    t = tok.replace(",", "")
    if not re.fullmatch(r"\d+\.\d{2}", t):
        return None
    # Return exactly two decimals
    return f"{float(t):.2f}"


def _find_total_amount(lines: list[OCRLine]) -> tuple[str | None, dict]:
    norm_lines = [(_normalize(ln.text), ln) for ln in lines]

    candidates: list[tuple[tuple[int, int, float], str, dict]] = []
    # score tuple: (keyword_priority, same_line_bonus, -conf) smaller is better

    for pri, keywords in enumerate(KEYWORD_GROUPS):
        for i, (ntxt, ln) in enumerate(norm_lines):
            if any(k in ntxt for k in keywords):
                if any(cue in ntxt for cue in NON_PAYABLE_CUES):
                    continue

                # Same-line amount (prefer last amount after keyword)
                amounts = [(m.start(), m.group(1)) for m in MONEY_RE.finditer(ntxt)]
                chosen = None
                if amounts:
                    # prefer last amount
                    chosen = amounts[-1][1]
                    parsed = _parse_money_token(chosen)
                    if parsed is not None:
                        ev = {
                            "field": "total_amount",
                            "chosen_value": parsed,
                            "keyword_group": keywords,
                            "match_type": "same_line",
                            "raw_line": ln.text,
                            "normalized_line": ntxt,
                            "bbox": ln.bbox,
                            "conf": ln.conf,
                            "source": ln.source,
                            "reason": "keyword present and amount found on same line; excluded non-payable cues",
                        }
                        candidates.append(((pri, 0, -ln.conf), parsed, ev))

                # Next-line fallback if no same-line amount
                if not amounts and i + 1 < len(norm_lines):
                    n2, ln2 = norm_lines[i + 1]
                    if any(cue in n2 for cue in NON_PAYABLE_CUES):
                        continue
                    amounts2 = [m.group(1) for m in MONEY_RE.finditer(n2)]
                    if len(amounts2) == 1:
                        parsed2 = _parse_money_token(amounts2[0])
                        if parsed2 is not None:
                            ev = {
                                "field": "total_amount",
                                "chosen_value": parsed2,
                                "keyword_group": keywords,
                                "match_type": "next_line",
                                "raw_line": ln.text,
                                "normalized_line": ntxt,
                                "raw_next_line": ln2.text,
                                "normalized_next_line": n2,
                                "bbox_label": ln.bbox,
                                "bbox_value": ln2.bbox,
                                "conf_label": ln.conf,
                                "conf_value": ln2.conf,
                                "source_label": ln.source,
                                "source_value": ln2.source,
                                "reason": "keyword line had no amount; immediate next line contained exactly one amount token and no intervening cues",
                            }
                            candidates.append(((pri, 1, -(ln.conf + ln2.conf) / 2.0), parsed2, ev))

    if not candidates:
        return None, {
            "field": "total_amount",
            "chosen_value": None,
            "reason": "no eligible total keyword/amount candidates found",
        }

    candidates.sort(key=lambda x: x[0])
    _, value, evidence = candidates[0]
    return value, evidence


DATE_YMD_RE = re.compile(r"\b(20\d{2})[\-/\.](0?[1-9]|1[0-2])[\-/\.](0?[1-9]|[12]\d|3[01])\b")
DATE_DMY_RE = re.compile(r"\b(0?[1-9]|[12]\d|3[01])[\-/\.](0?[1-9]|1[0-2])[\-/\.](\d{2}|20\d{2})\b")
DATE_MDY_RE = re.compile(r"\b(0?[1-9]|1[0-2])[\-/\.](0?[1-9]|[12]\d|3[01])[\-/\.](\d{2}|20\d{2})\b")
DATE_MON_RE = re.compile(
    r"\b(0?[1-9]|[12]\d|3[01])\s*[-/\.]?\s*(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|SEPT|OCT|NOV|DEC)\s*[-/\.]?\s*(20\d{2}|\d{2})\b",
    re.IGNORECASE,
)


def _to_iso(y: int, m: int, d: int) -> str | None:
    try:
        return date(y, m, d).isoformat()
    except Exception:
        return None


def _parse_year(y: str) -> int | None:
    if len(y) == 2:
        yy = int(y)
        # conservative pivot: 00-79 => 2000-2079, else 1980-1999
        return 2000 + yy if yy <= 79 else 1900 + yy
    if len(y) == 4:
        return int(y)
    return None


def _find_date(lines: list[OCRLine]) -> tuple[str | None, dict]:
    # Prefer lines with DATE label
    labeled_idxs = []
    for i, ln in enumerate(lines):
        nt = _normalize(ln.text)
        if "DATE" in nt or "DTE" in nt:
            labeled_idxs.append(i)

    search_order = labeled_idxs + [i for i in range(len(lines)) if i not in set(labeled_idxs)]

    candidates: list[tuple[tuple[int, float], str, dict]] = []
    # score (label_bonus, -conf)

    for idx in search_order:
        ln = lines[idx]
        txt = ln.text
        ntxt = _normalize(txt)
        label_bonus = 0 if idx in labeled_idxs else 1

        m = DATE_YMD_RE.search(ntxt)
        if m:
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            iso = _to_iso(y, mo, d)
            if iso:
                ev = {
                    "field": "date",
                    "chosen_value": iso,
                    "match_type": "YMD_numeric",
                    "raw_line": txt,
                    "normalized_line": ntxt,
                    "bbox": ln.bbox,
                    "conf": ln.conf,
                    "source": ln.source,
                    "reason": "recognized unambiguous YYYY-MM-DD style numeric date",
                }
                candidates.append(((label_bonus, -ln.conf), iso, ev))
                continue

        m = DATE_MON_RE.search(txt)
        if m:
            d = int(m.group(1))
            mon = m.group(2).upper()[:4]
            mon = "SEPT" if mon.startswith("SEPT") else mon[:3]
            mo = MONTHS.get(mon[:3])
            y = _parse_year(m.group(3))
            if mo and y:
                iso = _to_iso(y, mo, d)
                if iso:
                    ev = {
                        "field": "date",
                        "chosen_value": iso,
                        "match_type": "D_MON_Y",
                        "raw_line": txt,
                        "normalized_line": ntxt,
                        "bbox": ln.bbox,
                        "conf": ln.conf,
                        "source": ln.source,
                        "reason": "recognized month-name date (unambiguous month)",
                    }
                    candidates.append(((label_bonus, -ln.conf), iso, ev))
                    continue

        # DMY / MDY ambiguity handling
        m = DATE_DMY_RE.search(ntxt)
        if m:
            a, b, yraw = int(m.group(1)), int(m.group(2)), m.group(3)
            y = _parse_year(yraw)
            if y is not None:
                # if a>12 => day-first; if b>12 => month-first; else default day-first
                if a > 12:
                    d, mo = a, b
                    reason = "numeric date with first part >12 implies DMY"
                elif b > 12:
                    # this regex is DMY-shaped, but b>12 invalid for month; skip
                    d, mo = None, None
                    reason = None
                else:
                    d, mo = a, b
                    reason = "ambiguous numeric date; defaulted to day-first (DMY)"

                if d and mo:
                    iso = _to_iso(y, mo, d)
                    if iso:
                        ev = {
                            "field": "date",
                            "chosen_value": iso,
                            "match_type": "DMY_numeric",
                            "raw_line": txt,
                            "normalized_line": ntxt,
                            "bbox": ln.bbox,
                            "conf": ln.conf,
                            "source": ln.source,
                            "reason": reason,
                        }
                        candidates.append(((label_bonus, -ln.conf), iso, ev))

        else:
            m2 = DATE_MDY_RE.search(ntxt)
            if m2:
                a, b, yraw = int(m2.group(1)), int(m2.group(2)), m2.group(3)
                y = _parse_year(yraw)
                if y is not None:
                    # if b>12 => day must be b? Actually MDY means a=month, b=day.
                    if b > 12 and a <= 12:
                        # invalid day, skip
                        continue
                    iso = _to_iso(y, a, b)
                    if iso:
                        ev = {
                            "field": "date",
                            "chosen_value": iso,
                            "match_type": "MDY_numeric",
                            "raw_line": txt,
                            "normalized_line": ntxt,
                            "bbox": ln.bbox,
                            "conf": ln.conf,
                            "source": ln.source,
                            "reason": "recognized numeric date in MDY pattern",
                        }
                        candidates.append(((label_bonus + 1, -ln.conf), iso, ev))

    if not candidates:
        return None, {
            "field": "date",
            "chosen_value": None,
            "reason": "no plausible date patterns found",
        }

    candidates.sort(key=lambda x: x[0])
    _, value, evidence = candidates[0]
    return value, evidence


def extract_for_image(img_path: Path) -> tuple[dict, dict]:
    img = Image.open(img_path)

    all_lines: list[OCRLine] = []
    variants = _preprocess_variants(img)
    for vname, vimg in variants:
        for psm in (6, 4, 11):
            try:
                all_lines.extend(_ocr_lines(vimg, vname, psm))
            except Exception:
                continue

    # Deduplicate near-identical lines (same normalized text)
    seen = set()
    deduped: list[OCRLine] = []
    for ln in all_lines:
        nt = _normalize(ln.text)
        key = (nt, ln.bbox[0] // 20, ln.bbox[1] // 20)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(ln)

    deduped.sort(key=lambda ln: (ln.bbox[1], ln.bbox[0]))

    total, total_ev = _find_total_amount(deduped)
    dt, date_ev = _find_date(deduped)

    row = {
        "filename": img_path.name,
        "date": dt,
        "total_amount": total,
    }
    evidence = {
        "filename": img_path.name,
        "date": date_ev,
        "total_amount": total_ev,
    }
    return row, evidence


def write_excel(rows: list[dict]) -> None:
    wb = Workbook()

    # Remove default sheet and create required one
    default = wb.active
    wb.remove(default)
    ws = wb.create_sheet("results")

    ws.append(["filename", "date", "total_amount"])
    for r in rows:
        ws.append([r.get("filename"), r.get("date"), r.get("total_amount")])

    wb.save(OUT_XLSX)


def main() -> None:
    img_files = sorted(
        [
            p
            for p in IMG_DIR.iterdir()
            if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
        ],
        key=lambda p: p.name,
    )

    rows: list[dict] = []
    evidence: list[dict] = []

    for p in img_files:
        row, ev = extract_for_image(p)
        rows.append(row)
        evidence.append(ev)

    write_excel(rows)
    EVIDENCE_JSON.write_text(json.dumps(evidence, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
