# Exact receipt fields

When OCR is used to produce exact structured receipt fields such as `date` and
`total_amount`, do not simply concatenate text from different OCR passes and
pick a value from the combined text.

1. Keep each OCR pass separate and preserve the source line/region for every
   candidate. Count agreement only when independent passes read the same field
   in the same receipt region. Do not resolve conflicting values by global
   frequency/majority vote; a non-null candidate is still unresolved when
   independent passes disagree.
2. For `total_amount`, apply the task's exclusion rules before ranking values.
   Prefer an explicit final-payable field such as `GRAND TOTAL`, `TOTAL DUE`,
   `AMOUNT DUE`, `NET TOTAL`, or a clearly rounded/after-adjustment total over
   an earlier subtotal, sales total, tax summary, cash/payment, or change row.
   Treat a generic `TOTAL`/`AMOUNT` as fallback only after those semantic rows
   are classified; a payable `TOTAL ... INCLUDING GST` row is still a total.
3. Preserve monetary punctuation. A digits-only OCR read cannot by itself
   establish decimal placement.
4. If passes disagree, even when both produced non-null values, or a required
   field is unresolved, retry OCR only on a crop around that field/row, keeping
   the wider label context. Do not redesign the global OCR strategy or unrelated
   field parsing to solve one conflict.
5. Once independent same-region evidence resolves a field, freeze that value;
   later retries for other unresolved fields must not overwrite it.
6. If a total remains unresolved, a clear decimal-preserving targeted read of
   an explicit final-payable row may resolve it when no competing eligible
   final-payable value remains and local receipt evidence corroborates it.
7. Write the artifact from the resolved/frozen field values and reopen it to
   verify the saved rows, schema, and ordering.
