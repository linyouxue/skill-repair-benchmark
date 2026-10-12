# Round 6 conservative amount-verification override

This block is stricter than the earlier receipt-field gate. It exists to stop
regressions caused by broad parser rewrites. Preserve the task's literal money
semantics and verify the selected payable value locally instead of widening
normalization rules.

## 1. Do not broaden money normalization

- In this task, a comma in examples is a **thousands separator** (`1,234.56`).
  Do not reinterpret comma as a decimal separator just to rescue OCR text.
- Do not globally translate OCR letters such as `S/B/I/L/O` into digits.
  Character-confusion correction is allowed only inside a tight crop of the
  already-selected monetary value, and only when multiple crop variants support
  the same correction.
- Prefer source tokens that visibly preserve a decimal point and exactly two
  decimal digits. Do not accept a one-decimal token, append a zero, or invent a
  decimal position merely because the result looks plausible.

## 2. Semantic tier is primary and must not be escaped casually

Choose the final-payable **semantic field first**, then adjudicate the digits in
that field. Do not choose a lower semantic tier merely because it has more OCR
votes.

- Strong final-payable labels (`GRAND TOTAL`, `TOTAL RM`, `TOTAL AMOUNT`,
  `TOTAL DUE`, `AMOUNT DUE`, `BALANCE DUE`, `NETT TOTAL`, `NET TOTAL`) outrank
  generic `TOTAL` and all accounting-summary rows.
- A top-tier candidate with weak OCR support must trigger targeted OCR of that
  same row. It must **not** cause fallback to a lower-tier amount.
- Fallback to a lower tier is permitted only after the stronger candidate is
  explicitly rejected as a non-payable/header/intermediate field from its local
  context, not merely because OCR confidence is lower.
- GST/tax summary tables, `Total(RM)` column headers, item tables, `SUBTOTAL`,
  `DISCOUNT`, `CHANGE`, tendered cash, and tax amounts are never allowed to win.
- `Total Sales (Inclusive GST)` may be used only as a last semantic fallback
  when it is clearly the receipt's payable total and there is no stronger final
  payable field. This exception does not apply to GST summary rows.

## 3. Every selected non-null amount requires a second-stage local verifier

This is mandatory even when full-page OCR already has a multi-pass winner.

For the selected payable row:

1. retain the selected label/row bbox and the exact value-token bbox;
2. make a **tight crop around the value token itself** with a small margin;
3. make one wider crop containing the payable label and value together;
4. upscale the tight crop 3x or 4x and OCR materially different views
   (original/grayscale, autocontrast+sharpen, and thresholded) with single-line
   or single-word PSMs such as 7, 8, 10, or 13;
5. OCR the wider semantic crop with PSM 6 or 11;
6. record raw outputs before normalization.

Do not count several PSMs over the same rendering as independent evidence.
Require agreement across materially different image variants.

The selected amount is allowed into the workbook only when:

- the tight value crop has at least two materially different variants agreeing
  on the same exact two-decimal token; and
- the wider crop confirms that token belongs to the selected payable label.

If the local verifier disagrees with the full-page value, the field remains
unresolved and receives additional tight-crop variants. Never silently keep the
full-page majority.

## 4. Explicitly handle one-digit disagreements

Treat values that differ by one glyph as a hard dispute, for example `1/7`,
`6/8`, `7/1`, `0/8`, `3/8`, or adjacent cents digits. Do not use numerical
magnitude or "looks reasonable" as the tiebreaker.

For a one-digit dispute, compare only OCR from the **same value-token crop**.
The winner must be supported by at least two materially different crop variants
and must preserve the same decimal placement. If that condition is not met,
keep the field unresolved and continue targeted OCR rather than switching to a
different receipt line.

## 5. Conservative completion audit

Before writing the final workbook, assert for every non-null `total_amount`:

```python
assert semantic_payable_row_identified
assert tight_value_crop_variant_support >= 2
assert wider_label_value_crop_confirms_ownership
assert no_unresolved_one_digit_alternative
assert not_from_summary_or_item_table
```

Do not finish merely because all rows are non-null. A non-null amount without
this local verification is unresolved.

Avoid broad rewrites once the workbook is mostly correct. When only a small
number of values are disputed, freeze all verified rows and spend remaining
tool calls only on those value-token crops.
