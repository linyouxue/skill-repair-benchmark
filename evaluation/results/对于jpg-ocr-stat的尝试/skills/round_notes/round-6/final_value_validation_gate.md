# Round 6 mandatory final-value validation gate

This block strengthens the receipt OCR contract for one remaining failure
archetype: a wrong monetary digit can be reproduced consistently by several
whole-page OCR passes. Therefore **whole-page agreement alone is not sufficient
evidence for the final payable amount**.

The rules below override weaker advice later in the Skill.

## 1. Mandatory local verification for every selected payable total

After semantic adjudication selects a candidate `total_amount`, do not freeze it
yet merely because two or more full-page passes agree.

For the selected payable-total row, always run a compact local verification
step using the already-known row/value box:

- one wider crop that retains the payable label plus the value;
- one tighter value crop centered on the monetary glyphs;
- upscale at least 3x;
- use at least two materially different image variants;
- include a line-oriented OCR mode such as PSM 7 plus one context-capable mode
  such as PSM 6 or 11.

The local verification results must be added to the same evidence ledger with
distinct `pass_id`s. Do not perform another whole-page OCR sweep.

## 2. A selected total needs local digit agreement

A non-null `total_amount` is final only when its significant digits and decimal
placement are supported by local evidence from the selected payable region.

Accept either of these patterns:

1. at least two materially different **targeted/local** passes agree with the
   selected normalized value; or
2. one strong targeted value pass agrees with multiple same-region full-page
   passes and there is no targeted pass supporting a different digit string.

If targeted passes disagree with the whole-page consensus on any significant
digit, the field becomes disputed again. Resolve the disagreement with tighter
or differently preprocessed crops before writing the workbook.

Do not use confidence alone to choose between two different digit strings.

## 3. Leading-digit confusions require explicit scrutiny

Receipt fonts and blur can make leading glyphs such as `1`, `7`, `0`, `8`, `3`,
and `5` systematically confusable across several OCR passes. A stable but wrong
leading digit is therefore a known risk pattern.

When the selected payable amount contains a leading digit whose glyph is weak,
fragmented, touching a currency mark, or read differently by any local pass:

- crop the value more tightly while preserving the full glyph height;
- try grayscale/autocontrast and thresholded variants separately;
- preserve punctuation rather than using a digits-only whitelist as authority;
- compare the raw local OCR strings before normalization;
- require explicit targeted agreement before accepting that leading digit.

Never infer a digit from what amount seems economically plausible, and never
hard-code values for individual filenames.

## 4. Do not confuse repeated OCR configuration with independent support

Support is only materially different when the observation differs in image
conditioning or segmentation. Repeating nearly identical whole-page OCR calls
does not make a glyph correct by majority vote.

For the final amount audit, record at least:

```
filename
selected_payable_label
selected_total
source_bbox
full_page_support_passes
targeted_context_raw_values
targeted_value_raw_values
targeted_normalized_values
final_status
```

`final_status` must not be `resolved` until the local verification rule above
passes.

## 5. Blocking final audit

Extend the pre-write audit with these invariants:

```python
assert payable_total_without_targeted_validation_count == 0
assert targeted_vs_fullpage_digit_conflict_count == 0
assert unresolved_leading_digit_conflict_count == 0
```

If an invariant fails, work only on those specific receipt/value crops. Do not
restart OCR for already-resolved images.

## 6. Iteration-budget discipline

Implement the evidence rules in one deterministic script early. Prefer one
batched run plus one focused repair run over repeated manual inspection commands.

Do not spend tool turns printing every worksheet or every OCR variant after each
minor parser edit. Once all audit invariants pass, write the workbook once,
reopen it, verify sheet/header/order/value strings, and finish the task.

