# Keyword-anchored field selection from noisy text

**When to read this chapter.** You have OCR'd (or otherwise noisily
extracted) text and must pick, per record, the one *line* that carries
the target field (grand total, invoice date, order id, etc.) using a
positive/negative keyword rule. Skip when the field is identified by
position (fixed column in a form) or by a single unambiguous regex
(e.g. an ISBN) — no line-selection ambiguity exists.

**Core problem.** The natural implementation — a priority list of
positive keywords ("TOTAL", "GRAND TOTAL", "AMOUNT DUE") plus a
blanket substring exclusion of negative keywords ("GST", "TAX",
"SUBTOTAL", "CHANGE") — silently discards the right answer whenever
the real target line *mentions* a negative keyword as a descriptor
(`Total Sales Incl GST`, `Total Including GST 6%`, `Nett Total ...
GST`, `Total (Inclusive of GST)`). The extractor then falls through
to a stray tax-summary row (returning the tax figure) or returns
`None` when every candidate was excluded. The exclusion list is
semantic (skip tax/change rows); implementing it as a substring
test over the whole line is the over-generalisation.

---

## 1. Primary-keyword classification (with OCR-noise aliases)

A line's identity is set by its **strongest-tier positive keyword**,
not by whether any negative substring appears anywhere on it. A
negative keyword appearing as a *descriptor* on a positive-primary
line does not disqualify the line.

Negative keywords get **OCR-noise aliases** so that corrupted tokens
(`GST → GBT`, `G8T`, `6ST`, `G5T`; `SUBTOTAL → SUB T0TAL`, `SUB-T07AL`;
`TAX → T4X`) still trigger the exclusion test. Without aliases the
whole-word regex of §2 under-matches on noisy scans and lets
tax-summary rows through as candidates.

```python
import re

POSITIVE_TIERS = [
    ("grand_total", [r"\bGRAND\s+TOTAL\b", r"\bAMOUNT\s+DUE\b",
                     r"\bNETT?\s+TOTAL\b", r"\bTOTAL\s+SALES\b",
                     r"\bTOTAL\s+INCL(?:USIVE)?\b"]),
    ("total",       [r"\bTOTAL\b"]),
]

# OCR-noise aliases: canonical → set of observed variants (length ≥ 3
# to avoid false positives on short tokens).
NEGATIVE_ALIASES = {
    "GST":      {"GST", "GBT", "G8T", "6ST", "G5T", "GS1", "G$T"},
    "SUBTOTAL": {"SUBTOTAL", "SUB TOTAL", "SUB-TOTAL",
                 "SUB T0TAL", "SUB-T07AL", "5UBTOTAL"},
    "TAX":      {"TAX", "T4X", "7AX"},
    "CHANGE":   {"CHANGE", "CHANG3", "CHAN6E"},
}
NEGATIVE_PRIMARY_PATTERNS = [
    r"\bSUB[\s\-]?TOTAL\b", r"\bGST\s+SUMMARY\b",
    r"\bTAX\s+SUMMARY\b", r"\bCHANGE\b",
    r"\bROUNDING\b", r"\bCASH\b", r"\bTENDERED\b",
]

def _alias_hit(up_line, canonical):
    """True if the line contains any OCR-noise alias of `canonical` as
    a whole token. Edit-distance ≤ 1 is an alternative to the explicit
    alias set, but only for tokens of length ≥ 3."""
    for variant in NEGATIVE_ALIASES.get(canonical, {canonical}):
        if re.search(rf"\b{re.escape(variant)}\b", up_line):
            return True
    return False

def classify_line(line):
    up = line.upper()
    pos_tier = None
    for tier_name, patterns in POSITIVE_TIERS:
        if any(re.search(p, up) for p in patterns):
            pos_tier = tier_name
            break
    if pos_tier is not None:
        return ("candidate", pos_tier)
    if any(re.search(p, up) for p in NEGATIVE_PRIMARY_PATTERNS):
        return ("excluded", None)
    # Secondary exclusion via OCR-noise aliases (catches "GST Summary"
    # rendered as "GBT Summary").
    if _alias_hit(up, "GST") and "SUMMARY" in up:
        return ("excluded", None)
    return ("ignore", None)
```

**Decision rule.** The strongest positive-tier keyword on the line
determines classification. "Incl GST", "Including GST", "Inclusive of
GST", "incl. of GST" on a `TOTAL`-primary line are descriptors — the
line stays a candidate. Negative-keyword hits (including OCR aliases)
only exclude when there is no positive-tier keyword on the line.

---

## 2. Whole-word / token-boundary matching for negatives

Match negative keywords with `\bWORD\b` regex, never with
`"WORD" in line`. Substring tests fail two ways on OCR text:

- They **over-match**: `"GST" in "Total Incl GST 17.70"` is `True`,
  so the valid total is excluded.
- They **under-match on OCR noise**: `"GST" in "Total (Excluding
  GS1): 21.30"` is `False` because Tesseract rendered `T` as `1`,
  so the subtotal-excluding-tax line slips in as a candidate — this
  is the gap §1's alias set closes.

```python
GST_RE  = re.compile(r"\bGST\b", re.IGNORECASE)
TAX_RE  = re.compile(r"\bTAX\b", re.IGNORECASE)

def mentions_tax(line):
    # Whole-word on canonical form; alias set from §1 catches noisy
    # variants (GBT, G8T, 6ST, GS1).
    up = line.upper()
    return (bool(GST_RE.search(line) or TAX_RE.search(line))
            or _alias_hit(up, "GST") or _alias_hit(up, "TAX"))
```

Runtime branch:
- **Match on primary-keyword position** (e.g. line starts with
  `GST Summary` or has no positive-tier word) → exclude.
- **Match on descriptor position only** (positive-tier word also
  present) → keep as candidate; the primary rule from §1 governs.

---

## 3. Candidate ranking — tie-breaker ladder within a tier

Candidates at the same tier are common on real receipts (e.g. a
`Total Amt Rounded 702.000` line sits next to a `Total incl. of GST
102.00` line, both at the TOTAL tier). First-match-wins by position
lets a corrupted line win when the clean one happens to appear later.

Apply this ladder, in order, to break ties within a tier:

1. **Wording preference.** Prefer wordings that are rarely
   digit-corrupted on scans:
   `GRAND TOTAL`, `TOTAL INCL`, `TOTAL INCLUSIVE`, `AMOUNT DUE`
   beat `TOTAL AMT ROUNDED`, `TOTAL AFTER ROUNDING`,
   `TOTAL AFTER ADJUSTMENT` (the "rounded"/"after" wordings carry
   extra digits and are more OCR-corruption-prone).
2. **Sibling reconciliation.** If `cash`/`change`/`tendered` are
   present on the same record, prefer the candidate whose amount
   satisfies `cash − change ≈ amount` within rounding tolerance
   (see §4 and the sibling cross-field check in
   `references/ocr-batch-extraction.md` §5).
3. **Cross-variant numeric frequency.** Prefer the numeric *value*
   that appears in the most OCR variants (not the variant whose
   tier won). See `references/ocr-batch-extraction.md` §3 for the
   cross-variant voting shape; feed its vote back here.
4. **Bottom-most line position** — final fallback only.

Do **not** short-circuit the ladder at step 4; silently returning the
first match within a tier is forbidden.

```python
PREFERRED_WORDINGS = [r"\bGRAND\s+TOTAL\b", r"\bTOTAL\s+INCL",
                      r"\bTOTAL\s+INCLUSIVE\b", r"\bAMOUNT\s+DUE\b"]
DEMOTED_WORDINGS   = [r"\bTOTAL\s+AMT\s+ROUND", r"\bTOTAL\s+AFTER\s+ROUND",
                      r"\bTOTAL\s+AFTER\s+ADJ"]

def _wording_rank(line):
    up = line.upper()
    if any(re.search(p, up) for p in PREFERRED_WORDINGS):
        return 0
    if any(re.search(p, up) for p in DEMOTED_WORDINGS):
        return 2
    return 1

def rank_candidates(cands, lines, sibling=None, variant_vote=None):
    """cands: list[(line, tier, amount)]. sibling: dict with
    optional 'cash'/'change'. variant_vote: dict[amount → count]."""
    def _reconciles(amt):
        if sibling is None: return False
        cash, change = sibling.get("cash"), sibling.get("change")
        if cash is None or change is None or amt is None: return False
        try:
            return abs(float(cash) - float(change) - float(amt)) <= 0.05
        except (TypeError, ValueError):
            return False
    def key(ct):
        line, tier, amt = ct
        return (
            TIER_ORDER[tier],                 # 1. tier (strongest first)
            _wording_rank(line),              # 2. wording preference
            0 if _reconciles(amt) else 1,     # 3. sibling reconciliation
            -(variant_vote or {}).get(amt, 0),# 4. cross-variant frequency
            -lines.index(line),               # 5. bottom-most fallback
        )
    return sorted(cands, key=key)

def select_target_line(lines, strict=True, sibling=None, variant_vote=None):
    classified = [(ln, classify_line(ln)) for ln in lines]
    cands = []
    for ln, (status, tier) in classified:
        if status == "candidate":
            m = AMOUNT_RE.search(ln)
            amt = m.group(0) if m else None
            cands.append((ln, tier, amt))
    if cands:
        ranked = rank_candidates(cands, lines, sibling, variant_vote)
        return ranked          # list — caller uses ranked[0], then
                               # ranked[1] on reconcile failure (§4)
    if strict:
        return select_target_line(lines, strict=False,
                                  sibling=sibling,
                                  variant_vote=variant_vote)
    return []
```

Runtime branch:
- **Multiple candidates at the top tier** → apply the ladder; return
  the full ranked list so §4 can walk it on reconciliation failure.
- **Candidate set empty after exclusion** → relax the rule by one
  step (drop the weakest negative, require negative-as-primary) and
  retry once; do not loop indefinitely.

**Verification check — what to do on mismatch.** After running the
full batch, count rows where this function returned an empty list. If
count > 0:
- **Next corrective action**: open 2–3 of the empty-rows' raw text
  and read what a human eye picks. If a human can pick an answer the
  rule rejected, the rule is wrong — refine the positive-tier
  patterns or the negative-alias list, then re-run. Do **not** accept
  the empty result as the final value until this check passes.

---

## 4. Cross-field reconciliation — switch candidates before re-OCR

Many documents carry sibling values that constrain the target field.
Receipts: `cash − change ≈ total` within rounding. Invoices:
`line_subtotal + tax = grand_total`. Run this check on every row. On
failure, **the fix is often already on the same record**: a
same-tier candidate the ladder in §3 ranked lower will reconcile. Try
that before paying for a re-OCR.

```python
def reconcile_total(chosen_total, cash, change, tol=0.05):
    if cash is None or change is None or chosen_total is None:
        return True
    try:
        return abs(float(cash) - float(change) - float(chosen_total)) <= tol
    except (TypeError, ValueError):
        return True

def resolve_with_siblings(ranked_candidates, sibling):
    """ranked_candidates: list[(line, tier, amount)] from §3.
    Walk the ranked list; return the first candidate that reconciles,
    else return the top-ranked candidate (and let §5-level verification
    decide whether to escalate to re-OCR)."""
    cash, change = sibling.get("cash"), sibling.get("change")
    for line, tier, amt in ranked_candidates:
        if reconcile_total(amt, cash, change):
            return (line, tier, amt, "reconciled")
    if ranked_candidates:
        return (*ranked_candidates[0], "unreconciled")
    return (None, None, None, "no_candidate")
```

Runtime branch — in strict priority order:
- **Reconciliation passes on the top-ranked candidate** → accept it.
- **Top-ranked fails but a lower-ranked same-record candidate
  reconciles** → switch to that candidate. Do **not** re-OCR yet; the
  fix is already on the receipt (e.g. a corrupted
  `Total Amt Rounded 702.000` sits next to a clean
  `Total incl. of GST 102.00`).
- **No candidate reconciles AND the chosen amount differs from
  `cash − change` by exactly a known digit swap** (`7↔1`, `6↔0`,
  `3↔8`) → apply the digit-confusion repair from
  `references/ocr-batch-extraction.md` §4 to the chosen amount, then
  re-check.
- **Still unreconciled** → escalate to re-OCR with augmented
  pipeline per `references/ocr-batch-extraction.md` §5.

**Verification check — what to do on mismatch.** After re-selection
and any repair, re-run `reconcile_total`. If it still fails:
- **Next corrective action**: dump the full OCR text for that row
  and the current candidate ranking to stderr; manually confirm
  which line a human reader would pick, then adjust either the
  tier patterns (§1), the wording preference list (§3), or the
  digit-swap table before re-running. Record the row as
  low-confidence rather than silently writing a value that fails
  reconciliation.

---

## 5. Worked example — receipt total extraction

Walk through the mechanism on realistic OCR text that mixes valid
total lines (with "GST" as a descriptor) and genuine GST-summary
rows, plus a digit-corruption trap.

```python
RAW = """\
AEON CO (M) BHD
...
Sub-total                   102.00
Total Amt Rounded           702.000    # OCR corruption: 1 → 7
Total incl. of GST          102.00
GST Summary
  S @ 6%   96.23   5.77
Cash                        103.00
Change                        1.00
"""

lines = [ln.strip() for ln in RAW.splitlines() if ln.strip()]
ranked = select_target_line(
    lines,
    sibling={"cash": 103.00, "change": 1.00},
    variant_vote={"102.00": 4, "702.000": 1},  # from §3 cross-variant
)
# ranked[0] → "Total incl. of GST 102.00"
#   - Sub-total → excluded (SUB-TOTAL primary)
#   - Total Amt Rounded 702.000 → candidate, TOTAL tier,
#       wording_rank = 2 (demoted), reconcile = False, vote = 1
#   - Total incl. of GST 102.00 → candidate, TOTAL tier,
#       wording_rank = 0 (preferred), reconcile = True (103-1=102),
#       vote = 4 → wins on wording + reconciliation + vote
#   - GST Summary row → excluded (GST SUMMARY primary)

chosen_line, tier, amount, status = resolve_with_siblings(
    ranked, sibling={"cash": 103.00, "change": 1.00})
assert amount == "102.00" and status == "reconciled"
```

Contrast with the broken implementation:
`if "GST" in line: continue` plus first-match-wins — drops both
`Total ... Incl GST` candidates, leaves `Total Amt Rounded 702.000`
as the only TOTAL match, and returns `702.00`.

---

## 6. Checklist before shipping a keyword-anchored extractor

- [ ] Negative-keyword tests use `\bWORD\b` regex **or** the OCR-noise
      alias set from §1; `"WORD" in line` is forbidden anywhere on
      the exclusion path.
- [ ] NEGATIVE_ALIASES covers at least `GST`, `SUBTOTAL`, `TAX`,
      `CHANGE` with observed OCR variants (`GBT`, `G8T`, `6ST`,
      `SUB T0TAL`, …). Short tokens (< 3 chars) are not aliased.
- [ ] Within a tier, the §3 tie-breaker ladder runs
      (wording → reconciliation → cross-variant frequency →
      bottom-most). **First-match-wins within a tier is forbidden.**
- [ ] At least one candidate line survives for every input in a
      hand-picked sample of 3–5 inputs. If any sample yields an
      empty candidate set, go back to §1 and refine before running
      the full batch.
- [ ] A positive-primary line with a negative descriptor is
      explicitly kept as a candidate in the test sample.
- [ ] On reconciliation failure, the production path tries the
      next-ranked same-record candidate (§4) **before** triggering
      a re-OCR — re-OCR is the fallback, not the first move.
- [ ] After the full-batch run, grep the output for `None` /
      empty cells **and** reconciliation-failing rows; apply the
      §3 / §4 verification checks (human-eye spot read of 2–3
      flagged rows) before declaring done.

```python
# Final tier-ordering map used by §3.
TIER_ORDER = {name: i for i, (name, _) in enumerate(POSITIVE_TIERS)}
```
