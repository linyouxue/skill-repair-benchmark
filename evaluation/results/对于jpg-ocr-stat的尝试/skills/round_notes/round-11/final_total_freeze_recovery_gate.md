# Round 11 mandatory total freeze-and-recovery gate

This addendum is deliberately narrow. It changes only the **last adjudication
of `total_amount`** on top of the established Round 5 workflow. It must not be
used as permission to redesign OCR acquisition, date parsing, clustering, or
the general candidate parser.

## 1. Acquisition is frozen

For full-page OCR, keep the established bounded Round 5 acquisition only:

- the existing original / contrast-or-sharpened / thresholded variants;
- full-page PSM 6 and 11 only;
- targeted OCR, when genuinely unresolved, may use the already-established
  crop PSMs 6 / 7 / 11.

Do **not** add PSM 4 or any other full-page PSM. Do not add another
preprocessing variant, threshold sweep, scale sweep, generic OCR retry, looser
money regex, new date heuristic, or new global region/cluster definition.

This is a blocking implementation invariant. If the implementation changes the
full-page acquisition set or date adjudication in order to solve a total
dispute, revert that change before continuing.

## 2. Freeze a resolved baseline before any targeted total retry

After the bounded full-page evidence has been collected, run the ordinary
Round 5 semantic selection once and snapshot:

```text
baseline_winner
baseline_support_rows
baseline_support_pass_ids
```

If `baseline_winner` is non-null and has the normal independent same-region
support required by Round 5, it is **frozen**.

For that receipt:

- do not run targeted OCR for `total_amount` merely to seek a different value;
- do not recompute it under a new cluster key;
- do not let later confidence/support counts or a semantic-rank mutation
  replace it;
- do not call a generic total winner selector again after final adjudication.

Targeted total OCR is allowed only when the bounded full-page baseline is
actually unresolved (`baseline_winner is None`). Date handling is independent
and must not be changed by this addendum.

## 3. Absolute non-payable exclusions remain in force

Never select `CASH`, cash tendered/received, `CHANGE`, payment/card rows,
`SUBTOTAL` / `SUB TOTAL`, tax-only/GST/SST summary rows, item amounts,
quantities, unit prices, or table headers as the final payable amount.

However, an excluded earlier accounting row may be used only as **local
corroborating evidence** for the digits of a later explicit final-payable row;
it does not itself become the selected total.

Do not reject genuine payable labels such as `TOTAL RM INCLUDING GST` merely
because the phrase contains GST.

## 4. Decimal punctuation is mandatory for a selected value

A digits-only OCR token such as `1000` cannot establish whether the source is
`1000`, `100.0`, or `10.00`. It may corroborate the digit sequence of an
already decimal-preserving read from the **same row/region**, but it cannot
create a monetary value or determine decimal placement.

Any selected or replacement total therefore needs at least one existing OCR
observation of the correct payable row that preserves a decimal mark (dot or
decimal comma).

## 5. Null-baseline recovery from an explicit final row

If and only if `baseline_winner is None`, the final gate may recover a value
from evidence already collected by the bounded workflow.

Let `F` be an explicit final-payable row such as `GRAND TOTAL`, `TOTAL DUE`,
`AMOUNT DUE`, `BALANCE DUE`, `TOTAL AFTER ROUNDING`, `ROUNDED TOTAL`,
`NET TOTAL`, or equivalent. A single decimal-preserving read of `F` may be
accepted even when row-local clustering leaves it with support 1, but only when
**all** of the following hold:

1. there is no different decimal-preserving eligible final-payable competitor
   in the same settlement block;
2. the value of `F` is corroborated locally by at least one independent
   observation, for example:
   - the same normalized value on an earlier payable/accounting row in the
     same settlement block; or
   - a digits-only read of the same `F` row/region whose digit sequence matches
     `F` after punctuation is removed; or
   - an explicit local adjustment equation leading to `F`;
3. no credible non-zero adjustment or later payable row contradicts `F`.

This rule is specifically a **null recovery rule**. It must not be used to
replace an already stable non-null baseline.

## 6. Local settlement replacement rules

For a frozen non-null baseline `A`, a different later final value `F` may
replace it only if one of these proofs exists in the same local settlement
block:

1. `F` itself has at least two materially different decimal-preserving OCR
   passes in the same final row/region; or
2. there is an explicit signed adjustment `R` and
   `Decimal(A) + Decimal(R) == Decimal(F)` within one cent.

A single promoted final row, later page position, larger support count,
confidence change, or semantic-rank change is not sufficient.

## 7. One-cent mutation veto

If a proposed later value differs from a stable `baseline_winner` by exactly
`0.01`, treat that as a disputed OCR digit, not an automatic rounding event.

Keep the baseline unless the same local settlement block contains either:

- an explicit non-zero rounding/adjustment row whose arithmetic explains that
  exact one-cent change; or
- at least two materially different decimal-preserving reads of the later
  final row agreeing on the changed value.

Without one of those proofs, the one-cent mutation is vetoed and the baseline
remains final.

## 8. Irreversible pre-write audit

Immediately before writing `stat_ocr.xlsx`, persist for every receipt:

```text
baseline_winner
final_winner
decision = freeze_baseline | recover_explicit_final |
           direct_final_support | arithmetic_settlement | cent_mutation_veto
supporting local evidence rows/pass ids
rejected competing final values and reasons
```

After this audit decision, `final_winner` is immutable. Write the workbook from
that value and compare workbook readback against the same frozen audit value.
Do not run another generic selector afterward.

## 9. Scope guard

The intended implementation change is only:

```text
unchanged Round 5 bounded evidence
    -> freeze resolved baseline
    -> if null, recover only from explicit local final evidence
    -> if replacement proposed, require settlement proof and apply cent veto
    -> immutable final_winner
    -> workbook write/readback
```

Never hard-code a filename, expected date, or expected amount.
