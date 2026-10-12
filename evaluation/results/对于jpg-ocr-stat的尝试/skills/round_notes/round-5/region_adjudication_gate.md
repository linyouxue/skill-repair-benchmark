# Round 5 mandatory region-adjudication gate

For structured handwritten-form extraction, this block overrides any weaker or
more permissive OCR advice below. Treat it as an execution contract, not as a
quality suggestion. The task is unfinished until every required output field
has passed this gate.

## 1. Enumerate the destination fields before OCR

Open the provided spreadsheet/template first and build a checklist of every
cell that the task requires you to populate. Key each checklist row by the
sheet cell plus the human-visible form/line label (and repeated-row identity
when applicable). Keep dates and dollar amounts as different semantic types.

Do **not** start by dumping OCR text and then opportunistically filling cells.
The field checklist is the control structure for the extraction.

## 2. OCR evidence is valid only when it is tied to one semantic region

For each required field maintain an evidence ledger with at least:

```
field_id, source_image, section_anchor, row_anchor, expected_relation,
crop_bbox, pass_id, raw_text, normalized_candidate, confidence, decision
```

Use `pytesseract.image_to_data(..., output_type=Output.DICT)` (or an equivalent
token/box API), not only `image_to_string`, so that every candidate retains its
coordinates. Locate the printed section/row anchor first, then search only the
local row/box where the handwritten value belonging to that anchor can occur.

**Never count the same numeric string found elsewhere on the page as support
for a field.** Two OCR passes agree only when they read the same semantic field
from overlapping/near-identical source coordinates. A useful grouping key is:

```
(source_image, section_anchor, row_anchor, expected_relation, bbox_cluster)
```

Cluster rectangles by substantial overlap or close centers. Global
"same-value across passes" consensus is invalid.

## 3. Use a local geometry extractor before any value adjudication

For forms with printed labels/check boxes and handwritten values, implement the
following order:

1. OCR the whole page with boxes to find stable printed anchors and row bands.
2. Derive a tight row crop around each required anchor and a wider context crop
   that includes both the anchor and its handwritten value.
3. OCR each crop at enlarged scale (at least 2x; use 3x/4x when handwriting is
   small) using materially different preprocessing variants such as grayscale,
   autocontrast, adaptive/OTSU threshold, and a sharpened variant.
4. For short numeric crops, try segmentation modes appropriate for one line or
   sparse text (for example PSM 6/7/11) and a numeric whitelist when useful.
5. Store every plausible candidate; do not overwrite earlier disagreement.

The wider context crop establishes ownership of the number; the tight crop
improves digit recognition. Both are required for a disputed field.

## 4. Mandatory disagreement trigger

A field is **disputed** if any of the following is true:

- independent same-region passes produce different digits;
- only one usable pass produced a candidate;
- OCR confidence is low or characters are fragmented;
- comma/decimal placement differs across passes;
- the chosen value requires silently changing a digit or punctuation mark;
- two nearby numbers could plausibly belong to the same printed label.

For every disputed field, immediately stop broad full-page OCR and perform
targeted OCR on that field only. Use at least one tight crop and one wider
anchor-preserving crop, with multiple preprocessing/PSM combinations. Continue
until the candidate is supported by independent **same-region** evidence and
the wider crop confirms the semantic pairing.

Merely printing a low-confidence/disagreement table does not satisfy this
requirement. Every row in that table must trigger an actual targeted retry and
end with a recorded accept/reject reason.

## 5. Numeric normalization must not invent cents or digits

Keep a raw candidate string alongside the parsed number. Normalize only
unambiguous presentation characters (for example surrounding whitespace and
thousands separators). Do not convert a questionable mark into a decimal point,
do not append cents because the spreadsheet cell uses a currency format, and
do not repair ambiguous OCR digits by plausibility alone.

Common confusions such as `1/7`, `0/6`, `3/8`, `4/9`, `2/7`, a comma versus a
decimal point, or a faint terminal digit are hypotheses that require a new
same-region crop. They are never automatic substitutions.

When an amount visually/OCR-wise has no decimal fraction, preserve it as that
integer value; Excel formatting may display currency later. When the source
does contain cents, require evidence for both fractional digits.

## 6. Two-pass final adjudication before writing

Build one compact final table containing exactly one row per destination field:

```
field_id | source | anchor | winning raw text | normalized value |
supporting passes/regions | rejected alternatives | status
```

Perform two explicit reviews:

- **Structure pass:** verify source page, section, row label, repeated-row
  identity, and date-vs-dollar type.
- **Digit pass:** ignore semantics temporarily and compare every digit and
  decimal mark in the winner against the supporting tight/context crops and
  competing candidates.

The following assertions are blocking:

```python
assert unresolved_field_count == 0
assert single_pass_winner_count == 0
assert cross_region_consensus_count == 0
assert unresolved_competing_candidate_count == 0
```

If one fails, spend the next actions only on the unresolved/disputed fields.
Do not create the final workbook yet.

## 7. Reopen-and-readback gate

Only after the adjudication table passes may you write the workbook. Save to
the exact required path, reopen the saved workbook with the spreadsheet
library, and read every destination cell plus every required year-checkbox
cell back into a second table. Compare this readback programmatically with the
adjudicated winners and required fill state.

Do not finish on `file exists`, `workbook opens`, non-null counts, or a visual
spot-check. Finish only when every required destination cell equals the
adjudicated value and every required checkbox/fill is correct.

## 8. Scope discipline for this repair

Prefer targeted evidence acquisition over more full-page variants. Once a
field is known to be correct, freeze it and do not keep re-reading it. Spend
additional OCR effort only on fields with disagreement, weak evidence, or
ambiguous local ownership. This makes the procedure both more accurate and
more likely to complete within the execution budget.
