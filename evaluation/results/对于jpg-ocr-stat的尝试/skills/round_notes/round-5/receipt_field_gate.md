# Round 5 mandatory receipt-field adjudication gate

For receipt OCR tasks that require an exact `date` and `total_amount` per image,
this block overrides weaker or more permissive advice below. Treat it as an
execution contract. Do not finish merely because an Excel file exists or every
row is non-null.

## A. Run bounded full-page OCR once, then cache it

1. Enumerate all receipt images in deterministic filename order.
2. For every image run a small fixed set of materially different full-page OCR
   passes (for example original/grayscale, contrast or sharpened, and thresholded;
   use useful PSM variants). Persist each pass's text **and token boxes** once.
3. Parse all field candidates from that cache. Never rerun the entire image set
   just because one parser rule changes.
4. After the cached full-page passes, additional OCR is allowed only for images
   and fields whose evidence is unresolved or conflicting.

Use `pytesseract.image_to_data(..., output_type=Output.DICT)` or an equivalent
box-producing API in addition to plain text OCR. Whole-page mean confidence is
not a valid reason to discard all candidates from another pass.

## B. Keep a field-level evidence ledger

For every `(filename, field)` pair, where `field` is `date` or `total_amount`,
persist candidate evidence with at least:

```
filename, field, pass_id, raw_line, normalized_label, semantic_class,
bbox_or_row_region, raw_candidate, normalized_candidate, confidence,
eligible, rejection_reason
```

The final selection must be reproducible from this ledger. Never reduce the
evidence to only `value -> number_of_passes`.

Two passes support one another only when they read the **same semantic field in
the same source region**. The same number occurring elsewhere on the receipt is
not supporting evidence. Group candidates by page-local row/box geometry and
field meaning before counting cross-pass agreement.

## C. Amount semantics: enumerate before selecting

For `total_amount`, collect all plausible amount candidates from every cached
pass before choosing a winner. Apply these rules in this order:

1. Reject lines containing task exclusion concepts such as `SUBTOTAL`,
   `SUB TOTAL`, `TAX`, `GST`, `SST`, `DISCOUNT`, `CHANGE`, or `CASH TENDERED`.
2. Reject product/table headings such as `QTY ITEM TOTAL`, `ITEM ... TOTAL`, or
   another line where `TOTAL` is a column header rather than a payable field.
3. Prefer explicit final-payment semantics (`GRAND TOTAL`, `TOTAL RM`,
   `TOTAL AMOUNT`, `TOTAL DUE`, `AMOUNT DUE`, `BALANCE DUE`, `NETT TOTAL`,
   `NET TOTAL`) over a generic `TOTAL` occurrence.
4. Distinguish intermediate sales totals from a later adjustment/rounding/final
   payable stage. A `TOTAL SALES` or similar earlier accounting stage must not
   outrank a later clearly final/adjusted payable amount merely because it is
   easier to OCR or appears in more passes.
5. Never select `amounts[-1]`, the largest amount, the most frequent number, or
   the first legal match as a substitute for semantic adjudication.

### Safe next-line fallback

Use the task's next-line fallback only if the current line is a **standalone
payable-field label**. The next line must be locally adjacent, aligned with the
field's value region, and contain only a plausible currency/value token rather
than an item description, quantity, unit price, tendered amount, change, or a
new field label. Record the label/value boxes proving the pairing.

## D. Decimal placement is evidence, not formatting

Do not let numeric whitelists or normalization silently destroy monetary
punctuation. A digits-only pass that reads `1000` cannot by itself prove whether
the source is `1000`, `100.0`, or `10.00`. It may support the digit sequence,
but decimal placement must be confirmed by a pass/crop that preserves
punctuation or by clear same-region visual/OCR evidence.

Keep the raw candidate string. Remove thousands separators only after the
decimal mark is established. Use `Decimal` for normalization and format the
accepted final amount to exactly two decimal places only **after** the source
value is adjudicated. Never append/remove digits merely to make a plausible
currency value.

## E. Date parsing must preserve token order

Collect every date candidate across passes before selecting. Do not return the
first syntactically valid date and do not let a parser silently choose MDY/DMY
for an ambiguous slash date.

For each candidate keep the raw text and component order. Determine the date
convention from explicit labels/context and, where needed, unambiguous dates or
consistent formatting evidence. Once a convention is established for that
receipt/context, apply it explicitly. A disagreement in day, month, **or year**
between passes makes the field disputed and triggers targeted OCR.

## F. Every disagreement must trigger targeted OCR

A field is disputed if any of these holds:

- same-region passes produce different normalized values;
- only one usable pass supports a candidate;
- two different semantic candidates remain eligible;
- decimal placement differs or disappears between passes;
- a date component differs between passes;
- a next-line fallback lacks strong local pairing evidence;
- OCR confidence/fragmentation makes any digit uncertain.

For every disputed field, stop broad OCR and make targeted crops around the
field's label/value row. Use both:

- a **tight value crop** to improve digit recognition; and
- a **wider context crop** that retains the label and neighboring lines so the
  number's semantic ownership is visible.

Upscale the crops (2x minimum; 3x/4x when useful), try materially different
preprocessing, and use appropriate PSMs such as 6/7/11. A numeric whitelist is
an auxiliary pass, not authoritative evidence for punctuation. Add every
targeted result to the same ledger.

Printing a disagreement table is not resolution. Each disputed ledger row must
cause an actual targeted retry and finish with a winner or an explicit reject
reason for each competing candidate.

### Digit-shape ambiguity is itself a dispute

Do **not** accept a monetary candidate merely because multiple whole-page OCR
passes repeat the same string. Repeated full-page passes can share the same
systematic glyph error. In particular, leading currency digits such as
`1/7`, `1/4`, `3/8`, `5/6`, and `0/8` are high-risk when the glyph is blurred,
broken, shadowed, or touches a currency symbol/line.

Before freezing a final payable amount, inspect the value token itself. Treat
the field as disputed and force targeted value OCR when any of the following
holds:

- the decisive digit has low token confidence or differs across preprocessing
  variants, even if the normalized full amount currently has majority support;
- another OCR pass from the same payable row produces a visually plausible
  one-character alternative;
- the amount is obtained from a noisy/fragmented line where the label is clear
  but one leading digit is not;
- the candidate is semantically correct but its numeric token is the only
  remaining uncertainty.

For this case, crop **only the payable value token** with a small margin and run
several materially different recognition views (for example grayscale,
autocontrast/sharpen, adaptive or fixed threshold, and 3x/4x upscale) with
PSM 7/8/10/13 as appropriate for a single amount token. Also keep one wider
label+value crop with PSM 6/11 to prove ownership. Do not count several PSMs of
the same visually identical full-page rendering as independent confirmation of
the disputed digit.

Freeze the amount only after the **tight value crop** and the wider semantic
crop agree on the same two-decimal value, or after multiple independent tight
crop variants agree and all plausible one-digit alternatives are explicitly
rejected in the ledger. This rule overrides a whole-page majority vote.

## G. Blocking pre-write audit

Before creating `stat_ocr.xlsx`, build one compact final audit row per input
image containing:

```
filename | selected date | date evidence regions/passes |
selected total | total evidence regions/passes | rejected alternatives | status
```

Programmatically enforce at least:

```python
assert audit_filename_set == input_filename_set
assert unresolved_field_count == 0
assert single_pass_non_null_winner_count == 0
assert cross_region_consensus_count == 0
assert unresolved_competing_candidate_count == 0
assert unsafe_next_line_winner_count == 0
```

If one fails, continue **only** with the unresolved images/fields. Do not rerun
already-resolved images and do not write the final workbook yet.

## H. Exact artifact contract and readback

After the field audit passes:

1. create exactly one sheet named `results`;
2. write exactly the columns `filename`, `date`, `total_amount`;
3. sort data rows by filename and include exactly one row for every input image;
4. write dates as ISO `YYYY-MM-DD` strings (or null only when genuinely
   unresolved according to the task contract);
5. write accepted monetary values as strings with exactly two decimal places;
6. save to the exact required path `/app/workspace/stat_ocr.xlsx`;
7. reopen that saved workbook and read every cell back;
8. compare the readback programmatically to the adjudicated audit rows and the
   exact sheet/header/order constraints.

Only the reopened workbook matching the adjudicated evidence is completion.

## I. Completion-budget discipline

Once a `(filename, field)` has strong same-region evidence, freeze it. Spend
remaining OCR/tool calls only on disputed fields. The intended workflow is:

`bounded cached batch -> field ledger -> targeted retries -> audit -> one write -> readback`.

Do not regress to repeated whole-dataset OCR commands during parser iteration or
final workbook creation.

If all but one or a few fields are already stable, do not spend the remaining
agent budget redesigning the parser globally. Preserve the verified rows and
concentrate the remaining calls on the disputed receipt/value crop until the
blocking audit is satisfied.
