# Round 8 narrow override: rounded-total arithmetic consistency

This addendum is intentionally narrow. Preserve the existing receipt OCR/date
pipeline and the base Skill's semantic ranking for all fields unless the exact
condition below is met. In particular, do **not** broaden amount regexes, do not
change date convention logic, and do not replace an already-supported amount
with another generic TOTAL merely because it has more OCR votes.

## The defect being fixed

Full-page OCR can repeatedly misread one leading digit while still preserving
the label, decimal point, and remaining digits. This is especially dangerous
for labels such as `TOTAL AMT ROUNDED`, `TOTAL AMOUNT ROUNDED`, or an equivalent
final rounded-total line: semantic priority alone can make a wrong OCR token
outrank a nearby correctly read payable total.

Therefore, a multi-pass agreement on the same full-page OCR token is not enough
when the selected final amount is a **rounded-total** candidate whose value is
arithmetically inconsistent with the nearest preceding payable-total stage.

## Rounded-total invariant

When the selected amount comes from a line whose normalized label contains
`ROUND`, `ROUNDED`, or `ROUNDING` together with `TOTAL`/`AMOUNT`:

1. Locate the nearest preceding same-receipt payable-total candidate in the
   same local block. Legitimate examples include `TOTAL INCL. OF GST`,
   `TOTAL INCLUSIVE GST`, `TOTAL`, `TOTAL AMOUNT`, `TOTAL RM`, or another
   clearly final/pre-rounding payable total. A line that explicitly says
   `TOTAL ... INCL/INCLUSIVE ... GST` is a payable total and must **not** be
   rejected merely because it contains the token `GST`.
2. Compare the numeric values using `Decimal`.
3. Ordinary rounding is a small adjustment. If the rounded candidate differs
   from the preceding payable total by more than `1.00`, or differs in a
   leading digit / order of magnitude, mark the rounded value **disputed**.
   Do not accept it from full-page OCR consensus alone.
4. A larger difference may be accepted only if an explicit intervening
   discount, surcharge, tax, service charge, or other adjustment on the receipt
   numerically accounts for that difference. Never invent such an adjustment.

This rule is semantic/arithmetic, not filename-specific and not value-specific.

## Mandatory local adjudication for a disputed rounded total

For the disputed rounded-total field only:

- crop the exact numeric token tightly, retaining the decimal point;
- also crop a wider row/block that contains the rounded-total label and the
  preceding payable-total line;
- upscale the tight crop 3x-4x;
- run at least one original/non-binarized pass and two materially different
  image variants (for example autocontrast and threshold/sharpen), using a
  single-line PSM such as 7 for the tight token and PSM 6/11 for context;
- record each targeted read separately in the evidence ledger.

The rounded value is confirmed only if independent tight-token reads support it
and the wider crop confirms ownership by the rounded-total label. Repeated
full-page reads from transformations of the same source are supporting context,
not independent confirmation of a disputed leading digit.

If the targeted rounded-token OCR remains inconsistent but the immediately
preceding payable-total line is stable across independent OCR views and there
is no explicit intervening adjustment that changes the amount materially, use
the stable preceding payable amount as the final payable total rather than the
arithmetically impossible rounded OCR token.

## Regression guard

Do not apply this override to unrelated receipts/fields. Specifically:

- leave dates on the base pipeline;
- leave amounts whose selected label is not a rounded-total semantic on the
  base pipeline;
- do not introduce a blanket `amount >= threshold` re-OCR policy;
- do not loosen exclusions or semantic tiers globally;
- do not turn uncertainty elsewhere into null merely because this one rounded
  field needed extra adjudication.

After resolving the disputed field, perform the existing exact workbook
readback and completion checks.
