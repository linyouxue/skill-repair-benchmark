# Round 9 mandatory final-settlement sequence gate

This addendum is intentionally narrow. Preserve the established receipt OCR/date
workflow and all already-stable field-selection behavior. It overrides only the
choice between several payable-total rows that belong to the same final
settlement block.

## 1. Model the final settlement block as an ordered sequence

When a receipt contains multiple amount rows near the bottom, retain their page
order and semantic ownership. In particular, recognize sequences such as:

```text
Total Sales / Total incl. tax / Total Inclusive GST   A
Rounding / Rounding Adj / Adjustment                  R
TOTAL / TOTAL DUE / AMOUNT DUE / final payable        F
```

Do not rank these rows only by keyword specificity or number of OCR passes.
`A` can be an intermediate pre-adjustment payable amount. A later explicit final
`TOTAL`, `TOTAL DUE`, `AMOUNT DUE`, or equivalent row after a rounding/adjustment
line is the final settlement candidate.

## 2. Arithmetic consistency validates the stage transition

Parse `A`, `R`, and `F` with `Decimal`, preserving signs. If the receipt exposes
all three, require the final-stage relationship

```text
quantize(A + R, 0.01) == F
```

within one cent of OCR tolerance. When this holds, choose `F` even if `A` has
more full-page OCR support or appears under an earlier `Total Inclusive ...`
label.

Examples of valid *patterns*, not task-specific values:

- inclusive total + `-0.01` rounding -> later `TOTAL` one cent lower;
- inclusive total + `+0.02` adjustment -> later final payable two cents higher.

Never hard-code a filename or expected amount.

## 3. A purported rounded total must stay numerically plausible

Conversely, if OCR labels a later row `Total Amt Rounded`, `Rounded Total`, or
similar but the value differs from the preceding payable total by more than
`1.00`, changes order of magnitude, or cannot be reconciled with any explicit
rounding/adjustment row, treat that later value as disputed OCR rather than an
automatic winner.

For such a dispute:

1. OCR a tight crop around the later value token;
2. OCR a wider crop retaining the preceding payable row, rounding/adjustment
   row, and later final-total row;
3. use materially different preprocessing/PSM settings;
4. preserve raw values and signs in the evidence ledger;
5. accept the later value only if local evidence and settlement arithmetic make
   it coherent; otherwise fall back to the stable preceding payable total.

## 4. Final-stage precedence inside one semantic tier

Within otherwise comparable payable-total candidates, use this stage order:

1. later explicit final `TOTAL` / `TOTAL DUE` / `AMOUNT DUE` that follows an
   adjustment or rounding row and is arithmetically consistent;
2. explicit `TOTAL AFTER ADJ` / `TOTAL AFTER ADJUSTMENT`;
3. coherent `ROUNDED TOTAL` / `TOTAL AMT ROUNDED`;
4. earlier `TOTAL SALES`, `TOTAL INCLUSIVE GST`, or similar pre-adjustment total;
5. tax/GST summary-table totals remain excluded from payable selection.

This ordering applies only to rows belonging to the same local settlement block.
Do not compare unrelated totals from different regions of the receipt.

## 5. Do not regress stable fields

- Do not change date parsing because of this addendum.
- Do not globally loosen amount regexes or exclusion rules.
- Do not reinterpret item-table or tax-summary rows.
- Do not replace a stable amount merely because a different OCR pass exists.
- Target only settlement-stage conflicts; freeze already-resolved fields.

Before writing the workbook, record for every settlement-stage override the
ordered evidence rows and, when available, the `A + R -> F` arithmetic check.
