# Round 10 mandatory final-total adjudication gate

This addendum is deliberately narrow. It applies only to the **last decision for
`total_amount`**, after the existing Round 5 receipt-field workflow has already
collected and adjudicated its evidence. Do not broaden the general OCR search to
implement it.

## 1. Freeze the baseline winner before final-total adjudication

After the normal evidence-ledger selection has produced a `total_amount`, keep a
snapshot of that value and its supporting rows/passes as `baseline_winner`.

The final-total gate may replace `baseline_winner` only when the replacement is
proved to be a **later payable stage in the same local settlement block**. A
change in global cluster geometry, support count, confidence, page y-position,
or a semantic-rank mutation is not sufficient reason to replace a stable
winner.

Once a baseline value has strong same-region evidence, do not regress it merely
because a later recomputation groups OCR boxes differently.

## 2. Absolute non-payable exclusions at the final decision

Before comparing payable candidates, reject rows whose semantic ownership is
clearly not the amount owed, including:

- `CASH`, `CASH TENDERED`, tender/received amount;
- `CHANGE` / `CHANGE DUE`;
- `PAYMENT` / card payment rows;
- `SUBTOTAL` / `SUB TOTAL`;
- tax/GST/SST summary-table rows and tax-only rows;
- item-table amounts, quantities, unit prices, and column headers.

An earlier or later occurrence of one of these values cannot become
`total_amount` just because it appears in more OCR passes.

Do **not** reject a genuine payable row merely because its label says
`INCLUDING GST`, `INCLUSIVE GST`, `INCL GST`, or equivalent. For example,
`TOTAL RM INCLUDING GST` is a payable-total candidate, not a tax-summary row.

## 3. Decimal punctuation is required for a new monetary override

A digits-only OCR token such as `1000` does not prove `1000.00`, `100.00`, or
`10.00`. Such evidence may support digit shape, but it cannot create a new
normalized monetary value and cannot override a decimal-preserving payable
candidate.

For a replacement value, require at least one existing evidence row/crop that
preserves the decimal mark (dot or decimal comma) in the correct payable field.
Do not infer decimal placement from magnitude or from what would make the
receipt look plausible.

## 4. Validate only the local final-settlement block

Use the already-collected evidence ledger to identify an ordered local block:

```text
A = earlier payable total, e.g. TOTAL / TOTAL SALES / TOTAL RM INCLUDING GST
R = explicit rounding or adjustment row, if present
F = later explicit final payable row, e.g. GRAND TOTAL / TOTAL AFTER ROUNDING /
    TOTAL AFTER ADJ / TOTAL DUE / AMOUNT DUE / NET TOTAL / ROUNDED TOTAL
```

`F` may replace `baseline_winner` only through one of these validation routes:

1. **Direct final-row support:** the same normalized `F` value is supported by
   at least two materially different OCR passes in the same final row/region; or
2. **Arithmetic settlement proof:** `A`, `R`, and `F` belong to the same block,
   the signs are preserved, and `Decimal(A) + Decimal(R) == Decimal(F)` within
   one cent; or
3. **Same-value stage proof:** `A` has strong independent same-region support,
   at least one decimal-preserving read of the later explicit `F` row has the
   same normalized value, and there is no credible non-zero adjustment that
   contradicts `A == F`.

These are local settlement proofs. Do not combine unrelated rows from different
receipt regions to manufacture support.

## 5. A validated final value must not be erased by a row-local support gate

After route 2 or route 3 validates `F`, the final value is settled by the whole
local block. Do not set it to null merely because the exact `F` row itself has
only one surviving OCR-pass cluster after box quantization.

In particular, if independently supported `A` and a later decimal-preserving
`F` agree and the adjustment is zero (or `A + R -> F` is arithmetically valid),
the settlement block corroborates the final amount even when the promoted `F`
row has `support == 1` under the current cluster key.

Conversely, a single promoted `F` row with no route above must not outrank a
stable `baseline_winner` merely because its semantic rank was changed to zero.

## 6. One irreversible pre-write decision

Immediately before writing `stat_ocr.xlsx`, run this gate exactly once per
receipt and persist a compact audit entry containing:

```text
baseline_winner
final_winner
decision = freeze_baseline | direct_final_support |
           arithmetic_settlement | same_value_stage
supporting A/R/F evidence rows and pass ids
rejected final competitors with reasons
```

After this point, do not call the generic winner selector again for
`total_amount`. The workbook must be written from `final_winner`, and the
readback check must compare against that same frozen value.

## 7. Scope and non-expansion requirements

- Do not add full-page OCR variants, preprocessing modes, PSM sweeps, or generic
  candidate searches for this addendum.
- Do not loosen the global amount regex or global exclusion policy.
- Do not modify date extraction or date adjudication.
- Do not globally change the region-clustering function to solve a final-total
  dispute.
- Reuse the evidence already produced by the established Round 5 workflow and
  its bounded targeted retries.
- Never hard-code a filename or expected amount.

The intended change is only:

```text
existing evidence + baseline winner
    -> local final-total adjudication gate
    -> frozen final_winner
    -> workbook write/readback
```
