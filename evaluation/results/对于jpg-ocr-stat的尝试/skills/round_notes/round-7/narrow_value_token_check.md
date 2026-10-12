# Round 7 narrow value-token verification addendum

Use the existing receipt OCR workflow as-is. Do **not** redesign the amount
parser, broaden regexes, reinterpret comma decimals, change semantic ranking,
or replace already-working extraction logic globally.

This addendum adds only one conservative verification step for selected payable
amounts whose digit shape is unusually risky.

## Trigger only high-risk selected amount tokens

After the normal workflow selects a semantically valid final payable amount,
run an extra local verification only when at least one of these holds:

- the selected amount is 100.00 or greater;
- the selected value token has low/fragmented OCR confidence;
- different preprocessing passes disagree by one digit while referring to the
  same payable row;
- the leading glyph could plausibly be confused among shapes such as `1/7`,
  `6/8`, `0/8`, `3/8`, or `5/6`.

Do not touch rows that do not meet a trigger once their normal evidence is
resolved.

## Verify the same value token, not another receipt line

For a triggered amount:

1. keep the original payable label/row fixed;
2. obtain the bbox of the selected numeric token itself;
3. make a tight token crop with a small margin and a wider label+value crop;
4. upscale the tight crop 3x/4x;
5. OCR materially different image variants (original or grayscale,
   autocontrast+sharpen, and thresholded) using suitable single-line/word PSMs;
6. preserve raw OCR outputs and decimal punctuation.

The local verifier must never switch to a different `TOTAL`, GST-summary,
subtotal, item-table, cash, or change row. Its only job is to adjudicate the
digits of the already-selected payable value token.

## Conservative correction rule

Keep the normal selected value unless a competing value from the **same token
crop** is supported by at least two materially different crop variants and the
wider label+value crop confirms the same payable-field ownership.

When that stronger local evidence exists, replace the full-page OCR value with
the locally verified value. Otherwise keep the normal selected value; do not
turn it into null and do not fall back to another semantic tier.

Do not use magnitude, arithmetic plausibility, oracle-like expectations, or a
hard-coded filename/value mapping as a tiebreaker.

## Budget discipline

This is a narrow post-selection check. Once the normal workbook is mostly
resolved, do not rerun broad OCR or rewrite the parser because of one ambiguous
digit. Spend the remaining calls only on the triggered value-token crop(s),
then perform the usual workbook readback/schema/order checks.
