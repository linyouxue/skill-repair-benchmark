# OCR batch extraction → structured workbook

**When to read this chapter.** The input to the workbook is a batch of
images or scanned PDFs that must be OCR'd into typed fields (dates,
amounts, ids, keyword-anchored totals). Skip when the inputs are already
text (CSV, HTML, JSON, text PDFs with extractable text layers) — plain
parsing is sufficient there.

**Core problem.** A narrow OCR variant sweep plus majority voting cements
shared misreads: if 5 of 6 variants render a `0` as `6`, the "majority"
answer is wrong. The fix is **validity-aware** variant scoring plus a
**wider sweep** plus **targeted repair** of fields that fail validation,
plus a **mandatory all-rows verification pass** before the final save.

---

## 1. Sweep width — PSM modes × preprocessing

Use the full cross product below as the default. Narrower sweeps are only
justified by measured runtime pressure.

```python
import pytesseract
from PIL import Image, ImageOps, ImageFilter

PSM_MODES = [3, 4, 6, 11, 12]   # include 11 (sparse) and 3 (auto)

def preprocess_variants(img):
    gray = ImageOps.grayscale(img)
    sharp = gray.filter(ImageFilter.SHARPEN)
    # Upscale is 2× MINIMUM. 1.5× / 1.75× is insufficient — see below.
    up2 = gray.resize((gray.width * 2, gray.height * 2))
    up3 = gray.resize((gray.width * 3, gray.height * 3))
    return {"plain": img, "gray": gray, "sharp": sharp,
            "up2": up2, "up3": up3}

def ocr_all_variants(img):
    out = {}
    for pname, pimg in preprocess_variants(img).items():
        for psm in PSM_MODES:
            cfg = f"--psm {psm}"
            out[(pname, psm)] = pytesseract.image_to_string(pimg, config=cfg)
    return out   # 5 preprocessing × 5 PSM = 25 variants
```

**Why PSM 11 matters.** Block-mode PSMs (4, 6) read receipts as paragraphs
and share systematic misreads on narrow digits. PSM 11 (sparse text)
treats each glyph more independently and frequently rescues dates/amounts
that all block-mode variants miss. If your sweep omits PSM 11, you are
one blind spot away from a majority-wrong consensus.

**Upscale factor — 2× minimum, 3× recommended on receipt JPGs.**
1.5× and 1.75× are **insufficient** for the digit confusions that
dominate receipt-OCR failures (observed: `102.00` read as `702.000`
persists at 1.5× but resolves at 2×/3×). Treat sub-2× upscale as an
anti-pattern — include at least `up2` and `up3` in the preprocessing
axis. Low-resolution JPGs (shorter edge < 800 px) warrant 3× as the
default rather than 2×.

---

## 2. Field validators

Validators are per-field-type predicates. They are the primary scoring
signal; frequency is only a tie-breaker.

```python
import re

DATE_RE = re.compile(r"(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{2,4})")
AMOUNT_RE = re.compile(r"\d+\.\d{2}")
# Loosened amount regex — ONLY for the sliding-window fallback in §4b.
# Do NOT use on the primary extraction path; false positives return.
AMOUNT_RE_LOOSE = re.compile(r"\d+[.,]\d{2}|\d{3,}")

def valid_date(s):
    m = DATE_RE.search(s or "")
    if not m: return False
    d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if not (1 <= mo <= 12): return False
    if not (1 <= d <= 31): return False
    if y < 100: y += 2000
    return 1990 <= y <= 2099     # tune per task plausibility window

def valid_amount(s):
    return bool(AMOUNT_RE.fullmatch((s or "").strip()))
```

Add validators for every typed field in the schema. A validator that
returns `True` on anything is worse than no validator — the whole
mechanism depends on validators actually rejecting malformed outputs.

---

## 3. Validity-aware variant scoring (plus cross-variant numeric voting)

Replace raw-frequency majority voting with a two-key sort: **validity
count desc, frequency desc**. A single valid variant beats a many-way
invalid consensus.

```python
from collections import Counter

def pick_field(candidates, validator):
    """candidates: list[str] extracted from each variant for this field."""
    freq = Counter(c for c in candidates if c is not None)
    ranked = sorted(
        freq.items(),
        key=lambda kv: (validator(kv[0]), kv[1]),
        reverse=True,
    )
    return ranked[0][0] if ranked else None
```

### 3b. Cross-variant numeric consistency for keyword-anchored amounts

`pick_field` votes on the raw string extracted per variant. For
keyword-anchored amounts (where each variant selects a *line* first
and then an amount from it), picking the "best variant by tier" and
then taking its amount is **arbitrary** when two variants both hit the
top tier with different numeric values (`702.000` vs `102.00`). The
choice collapses to dict/order dependence and OCR hallucinations
propagate.

Fix: after per-variant extraction of `(tier, amount)` pairs, bucket
by the **numeric value** across variants that reached the top tier,
and feed the vote back into the keyword-anchored ranker (see
`references/keyword-anchored-field-selection.md` §3 step 3).

```python
def cross_variant_vote(per_variant_pairs):
    """per_variant_pairs: list[(tier, amount)]. Returns dict[amount→count]
    scoped to the strongest tier any variant reached."""
    valid = [(t, a) for (t, a) in per_variant_pairs if t is not None and a]
    if not valid:
        return {}
    top_tier = min(TIER_ORDER[t] for t, _ in valid)
    top = [a for t, a in valid if TIER_ORDER[t] == top_tier]
    return dict(Counter(top))
```

Runtime branch:
- **All candidates invalid** → proceed to digit-confusion repair (§4).
- **At least one valid candidate** → return the most frequent valid one;
  for keyword-anchored amounts, pass `cross_variant_vote(...)` to the
  keyword chapter's ranker rather than returning here.
- **No candidates at all (all None)** → mark the row for re-OCR with
  augmented pipeline (§5).

---

## 4. Digit-confusion repair for fields that fail validation

Common Tesseract digit confusions on receipt-resolution scans:
`0 ↔ 6`, `3 ↔ 8`, `0 ↔ O`, `2 ↔ Z`, `1 ↔ 7`. Apply targeted
substitutions only on positions that are failing validation, then
re-validate. Do not apply blindly across the whole string — that
introduces new errors.

```python
DIGIT_SWAPS = {
    "0": "6", "6": "0",
    "3": "8", "8": "3",
    "1": "7", "7": "1",
    "2": "1",
}

def repair_date(raw):
    m = DATE_RE.search(raw or "")
    if not m: return None
    d, mo, y = m.group(1), m.group(2), m.group(3)
    if not (1 <= int(mo) <= 12):
        for i, ch in enumerate(mo):
            if ch in DIGIT_SWAPS:
                cand = f"{d}/{mo[:i] + DIGIT_SWAPS[ch] + mo[i+1:]}/{y}"
                if valid_date(cand):
                    return cand
    if not (1 <= int(d) <= 31):
        for i, ch in enumerate(d):
            if ch in DIGIT_SWAPS:
                cand = f"{d[:i] + DIGIT_SWAPS[ch] + d[i+1:]}/{mo}/{y}"
                if valid_date(cand):
                    return cand
    return None

def repair_amount(raw):
    s = (raw or "").strip()
    if re.fullmatch(r"\d{3,}", s):
        cand = s[:-2] + "." + s[-2:]
        if valid_amount(cand):
            return cand
    return None
```

Runtime branch:
- **Repair yields a valid candidate** → use it; record that the field
  was repaired (useful for the verification report).
- **Repair fails** → leave the field as `None` and let §5 flag the row.

---

## 4b. Line-splitting handling (sliding 2-line window)

PSM 11 (and some sharpened variants) frequently split a keyword from
its amount across adjacent lines — e.g. `Grand Total` on line N and
`92.80` on line N+1. The strict `\d+\.\d{2}` on the keyword line
returns no match and the extractor falls back to a brittle variant
chain. Also observed: sharpened/PSM-4 produces garbled amount strings
(`9280`, `SSCS 92.80`) that the strict regex misses.

Fix: slide a 2-line window across the OCR text so a keyword on line N
can match an amount on line N+1 (and N+2 for very sparse PSMs).
**Loosen the amount regex ONLY on this fallback path** (use
`AMOUNT_RE_LOOSE` from §2 and run decimal-insertion repair via §4);
loosening on the primary path re-introduces false positives.

```python
def extract_amount_near_keyword(lines, keyword_rx, window=2):
    """Primary path uses AMOUNT_RE on the keyword line; fallback walks
    the window below it with AMOUNT_RE_LOOSE + decimal repair."""
    for i, line in enumerate(lines):
        if not keyword_rx.search(line):
            continue
        m = AMOUNT_RE.search(line)
        if m:
            return m.group(0), "primary"
        # Fallback: look ahead up to `window` lines, loosened regex.
        for j in range(1, window + 1):
            if i + j >= len(lines):
                break
            m2 = AMOUNT_RE_LOOSE.search(lines[i + j])
            if m2:
                token = m2.group(0).replace(",", ".")
                if valid_amount(token):
                    return token, "window_strict"
                repaired = repair_amount(token)
                if repaired:
                    return repaired, "window_repaired"
    return None, "no_match"
```

Runtime branch:
- **Primary path returns a valid amount** → use it.
- **Primary empty, window finds a strict `\d+\.\d{2}`** → use it,
  flag the row as `window_strict` (sibling reconciliation in §5
  still applies).
- **Primary empty, window finds only `\d{3,}` or `\d+,\d{2}`** →
  apply decimal-insertion repair via `repair_amount`; use the
  repaired value only if it passes `valid_amount`.
- **Nothing found anywhere** → return `None`; §5 flags the row.

---

## 5. Mandatory all-rows verification pass (incl. cross-field sanity)

After the first full run saves the workbook, iterate over **every** row
(not a spot-check) and flag rows meeting any of these conditions:

1. A field is `None`.
2. The chosen candidate had `validator == False`.
3. The top-two variants disagreed.
4. **Cross-field sanity fails** — the chosen value is syntactically
   valid but inconsistent with sibling fields on the same input
   (receipts: `cash − change ≈ total` within rounding; invoices:
   `subtotal + tax = grand_total`). Catches both wrong-line
   selection and syntactically-valid OCR digit corruption (`702.00`
   where cash/change imply ~`102.00`).

On flagged rows, in **strict priority order**:

1. **First try switching to the next-ranked keyword candidate on the
   same record** — call the keyword-anchored chapter §3/§4 ranker
   with the full ranked list and walk it until one reconciles. The
   fix is often already on the receipt (e.g. 074's
   `Total incl. of GST 102.00` sits right next to the corrupted
   `Total Amt Rounded 702.000`). Re-OCR is **not** the first move.
2. **If no same-record candidate reconciles**, apply the §4
   digit-confusion repair to the chosen amount — including swap
   candidates that would bring the value into reconciliation (if
   the chosen total differs from `cash − change` by exactly a
   known swap like `7↔1`, try that swap first).
3. **If still unreconciled**, re-OCR with an augmented pipeline:
   additional PSMs you didn't try, additional preprocessing
   (binarization, contrast stretch, 3×/4× upscale), then re-run the
   keyword-anchored line selector.

Then re-save.

```python
from openpyxl import load_workbook

def reconcile(row, tol=0.05):
    total, cash, change = row.get("total"), row.get("cash"), row.get("change")
    if cash is None or change is None or total is None:
        return True
    try:
        return abs(float(cash) - float(change) - float(total)) <= tol
    except (TypeError, ValueError):
        return True

def verify_and_repair(xlsx_path, raw_inputs, extract_augmented,
                     rerank_same_record):
    wb = load_workbook(xlsx_path)
    ws = wb.active
    headers = [c.value for c in ws[1]]
    flagged = []
    for row in ws.iter_rows(min_row=2, values_only=False):
        values = {h: c.value for h, c in zip(headers, row)}
        if any(v is None for v in values.values()) or not reconcile(values):
            flagged.append(row[0].row)
    for r in flagged:
        row_id = ws.cell(row=r, column=1).value
        # Step 1: cheap — try the next-ranked same-record candidate.
        fixed = rerank_same_record(raw_inputs[row_id])
        if fixed is None or not reconcile(fixed):
            # Step 2+3: expensive — digit-confusion repair + re-OCR.
            fixed = extract_augmented(raw_inputs[row_id])
        for col_idx, h in enumerate(headers, start=1):
            if h in (fixed or {}) and fixed[h] is not None:
                ws.cell(row=r, column=col_idx).value = fixed[h]
    wb.save(xlsx_path)
    return flagged
```

**Verification check — what to do on mismatch.**
- Reopen the saved workbook with `openpyxl.load_workbook(path)` and
  count rows where any field is still `None` **or** where `reconcile`
  returns `False`. If count > 0:
  **next corrective action** → widen the augmented pipeline further
  (add PSM 13 raw-line, add adaptive-threshold binarization, 4× upscale,
  and for reconciliation-failing rows also re-run the keyword-anchored
  line selector from `references/keyword-anchored-field-selection.md`
  with the next-ranked candidate), then re-run `verify_and_repair`.
- If a row still fails after two augmented re-OCR passes, accept the
  current best candidate (do not loop indefinitely) and record it; the
  baseline-deliverable rule from the main workflow applies — a saved
  imperfect workbook beats budget exhaustion. **However** — a row the
  reasoning trace has explicitly identified as wrong (e.g. notes say
  "074 still fails") must get at least one targeted re-extraction
  attempt before silently shipping; see the L2 "degenerate /
  known-wrong row" checklist bullet.

---

## 6. End-to-end skeleton tying §1–§5 together

```python
from pathlib import Path
from openpyxl import Workbook

def extract_one(img):
    variants = ocr_all_variants(img)
    # Per-variant tier+amount extraction via keyword-anchored chapter.
    pairs = [find_total_pair(t) for t in variants.values()]
    vote  = cross_variant_vote(pairs)
    date_cands = [find_date(t)   for t in variants.values()]
    amt_cands  = [a for (_, a) in pairs if a]
    date = pick_field(date_cands, valid_date) or repair_date(
        max(set(date_cands), key=date_cands.count, default="") or "")
    # Keyword-anchored amount: use ranker + cross-variant vote.
    amt  = select_total_amount(variants, vote=vote)
    return {"date": date, "amount": amt}

out = Path("/app/workspace/output.xlsx")
wb = Workbook(); ws = wb.active
ws.append(["id", "date", "amount"])
rows = {item.id: extract_one(item.image) for item in load_all_items()}
for rid, fields in rows.items():
    ws.append([rid, fields["date"], fields["amount"]])
wb.save(out)
assert out.exists()

flagged = verify_and_repair(out,
                            {i.id: i.image for i in load_all_items()},
                            extract_augmented=extract_one,
                            rerank_same_record=rerank_total_only)
print(f"re-processed rows: {flagged}")
```
