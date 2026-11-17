# Batch Diagnoses

## Task jpg-ocr-stat (round 0)

## w0001
## Summary of source run status
- **Termination**: `max_iterations` at 65/65. The Excel was successfully written (22 rows, correct schema) before the agent was cut off — the agent likely spent extra iterations on refinement/verification loops.
- **Original binary reward**: 0.0 (oracle requires exact field-by-field match).
- **Derived field accuracy**: 40/44 = 90.9% (21/22 dates, 19/22 amounts).
- **Four specific field errors** fully account for the binary failure.

## Field-level failure analysis (from permitted boolean feedback + direct image inspection)

### A. Amount errors (3)

**1. `074.jpg` — GL HANDICRAFT & TAILORING (predicted "702.00", wrong)**
- Image shows: `SAFETY PINS BUTTERFLY — S / 6.00 BOXS × 17.00 / 102.00`, `Subtotal: 102.00`, `Total Incl. of GST 102.00`, `Total Amt Rounded 102.00`, `Payment: 102.00`.
- Root cause: Tesseract digit confusion **"1" → "7"** on the leading digit of "102.00". This is a classic low-contrast / thin-stroke misread on a lightly inked receipt. The hint-driven keyword logic was correct (it picked a `TOTAL` line), but the token itself was already corrupted at OCR time.
- Evidence strength: High. No `702.00` string exists anywhere on the receipt; every total line reads 102.00.

**2. `077.jpg` — Banh Mi CafE (predicted "23.26", wrong)**
- Image shows two TOTAL candidates:
  - `Total (Inclusive of GST): 23.26`
  - `Rounding Adj: -0.01`
  - `TOTAL: 23.25`  ← final bolded line
- Root cause: Keyword-priority ambiguity. The hint lists `TOTAL` as a same-tier keyword, so two lines both match. The extractor selected the first `Total` line (the pre-rounding inclusive total) rather than the final post-rounding `TOTAL:` line. The receipt's final figure is the rounded one, and the oracle appears to use that.
- Evidence strength: High. Both numbers are clearly OCR-visible and the mis-selection is a disambiguation bug, not an OCR bug.

**3. `078.jpg` — THAI DELICIOUS RESTAURANT (predicted "" / null, wrong)**
- Image shows: `Total: 92.80`, `Grand Total: 92.80`, `Cash Received: 100.00`, `Change: 7.20`, `AVERAGE / PAX(S): 23.20`.
- Root cause: Amount extraction returned null even though `GRAND TOTAL` (highest-priority keyword per the hint) is clearly printed with value 92.80. Likely cause: Tesseract's default PSM mishandled this tabular layout (the amounts are right-aligned in a column separated by lots of whitespace), so the keyword line and the number ended up on separate OCR tokens or the numeric token was dropped. The skill's multi-pass PSM strategy (6/4/11) appears not to have been triggered, or the "fallback: next line last number" rule didn't fire because the number was on the *same* visual line but a different OCR segment.
- Evidence strength: High. The amount is obviously present; this is a parsing/segmentation failure, not an absent datum.

### B. Date errors (1)

**4. `034.jpg` — PERNIAGAAN ZHENG HUI (predicted "2018-08-09", wrong)**
- Image shows: `Date: 09/03/2018`, `Time: 08:49:00`.
- Root cause: The predictor appears to have combined the **hour `08`** (from `08:49:00`) and the **day `09`** (from `09/03/2018`) into `2018-08-09`, or alternatively parsed `09/03/2018` as MM/DD/YYYY and mapped the "03" day field somewhere else and the "08" came from the time. Either way, the extractor mishandled the date tokenization. The correct Malaysian locale reading of `09/03/2018` is DD/MM/YYYY → `2018-03-09`.
- Evidence strength: Medium-high. The digits "08" and "09" both appear near the date block; it's plausible that a regex picked up the wrong tokens from the adjacent time string. The remaining 21/22 dates parsed correctly, so the general DD/MM/YYYY logic is mostly working — this looks like an edge-case near-time-stamp pickup.

## Patterns across failures

- **No systematic locale bug**: 21/22 dates correct → general DD/MM/YYYY handling is sound; only `034.jpg` where date and time digits are visually adjacent broke.
- **Amount misses cluster around two distinct causes**:
  - OCR digit confusion on worn/low-contrast print (`074.jpg`).
  - Keyword disambiguation when multiple `TOTAL` lines exist, especially with `(Inclusive of GST)` vs. final rounded `TOTAL` (`077.jpg`).
  - Layout-driven extraction gap where OCR reads the keyword but loses the number alignment (`078.jpg`).
- **Original Skills coverage**: The `image-ocr` skill *does* document multi-PSM/multi-preprocessing passes and the task hint already provides explicit priority ordering + exclusion keywords + a fallback "next line, last number" rule. The source run's implementation did not fully exploit these — it used a single-pass extraction with a priority list that didn't resolve intra-priority ties (`077.jpg`) and didn't retry with alternate PSM when a keyword was found but its numeric partner wasn't (`078.jpg`).
- **Iterations**: 65 iterations with no natural completion suggests the agent kept iterating on refinements but never implemented the specific fixes needed. The partial accuracy (90.9%) shows the pipeline *mostly* works; the four failures are specific, not systemic.

## Guidance signals for Momentum / Patcher

The pipeline's core architecture (OCR → keyword scan → ISO date + 2-dp amount → ordered xlsx) is working for 18/22 receipts jointly. Targeted improvements that would plausibly repair the four failures:

1. **Tie-breaking within same-priority TOTAL keywords**: when more than one line matches a same-tier keyword (`TOTAL`, `AMOUNT`, etc.), prefer the **later** occurrence and/or prefer a line whose text is a bare `TOTAL:` over one qualified by `(Inclusive of GST)`, `(Excluding ...)`, `Sub...`, etc. The exclusion keyword list already filters `SUBTOTAL`; `077.jpg` suggests adding a preference for the final/rounded total rather than a parenthetical variant.
2. **Multi-PSM retry when keyword matched but value not parsed on same/next line** (`078.jpg`): if a `GRAND TOTAL` / `TOTAL` keyword line yields no numeric sibling under PSM 3, retry with PSM 6 / PSM 4 on a cropped band around that keyword, or widen the sibling search to right-aligned tokens on the same row.
3. **Digit-confusion mitigation on amounts** (`074.jpg`): try a second OCR pass with upscaling + sharpening + explicit `-c tessedit_char_whitelist=0123456789.,` on the numeric region; where multiple `TOTAL` lines cross-check, prefer the value that agrees across lines (102.00 appears 4× here and 702.00 appears 0×).
4. **Date tokenization hardening** (`034.jpg`): when extracting the date, anchor on a `dd/mm/yyyy` regex that is *not immediately adjacent* to `hh:mm` digits, or split on the `Date:` label specifically rather than scanning globally. Assume DD/MM/YYYY (consistent with the Malaysian receipt corpus already handled correctly elsewhere).

## Uncertainty / what I cannot verify
- I did **not** read the agent's actual intermediate OCR text or its extraction code, so I cannot confirm whether the code used the multi-pass skill helper or a single pass. The guesses about *which* step failed (PSM vs. regex vs. tie-break) are inferred from the output mismatch patterns, not from source inspection.
- I cannot see the oracle values. I infer oracle expectations only from the images and the boolean per-field feedback. For `077.jpg` I cannot prove the oracle expects `23.25` rather than `23.26`, only that the prediction `23.26` is marked wrong, and the receipt's final printed `TOTAL:` line is `23.25`.
- The `max_iterations` termination is a budget signal, not necessarily a sign of a loop. The fact that 22 valid rows were written means the agent did finish the primary deliverable before being cut off; the terminal iterations may have been incremental revisions that did not address these four specific records.
- Image-visible content was verified from the 22 attached image blocks; the historical agent is not proven to have had vision access — it almost certainly used Tesseract OCR text only, which is consistent with the digit-confusion and segmentation-style errors observed.

## w0002
## Scope of failure
Reward 0.0 (binary pass), but derived field accuracy = 40/44 (90.9%). Exactly 4 cells are wrong:

| file | field | prediction | observed truth from pixels | failure class |
|---|---|---|---|---|
| 034.jpg | date | 2018-08-09 | 2018-03-09 (image shows `Date: 09/03/2018`, `Time: 08:49:00`) | OCR digit confusion 3→8 |
| 074.jpg | amount | 702.00 | 102.00 (image shows `Subtotal/Payment/Total 102.00`) | OCR digit confusion 1→7 on one line, picked wrong line |
| 077.jpg | amount | 23.26 | 23.25 (image: `Total (Inclusive of GST) 23.26` → `Rounding Adj -0.01` → bold `TOTAL: 23.25`) | OCR missed the final rounded TOTAL line; parser preferred intermediate `Total` |
| 078.jpg | amount | (empty) | 92.80 (image: `Grand Total: 92.80`) | OCR mangled `Grand Total` → `GrandTota. = tS 92.80` and `Total — 92:80`; keyword/regex didn't match |

All four failures share the same root cause family: **single-pass default Tesseract (`pytesseract.image_to_string(img)` with no preprocessing, no PSM sweep, no variant aggregation)** combined with a **strict keyword/regex parser that cannot absorb OCR noise or pick the authoritative line when several `Total` candidates exist**.

## Evidence grounded in the source run

1. OCR mode used (from timeline a0006/a0007/a0008): the agent called only `pytesseract.image_to_string(img)` on the raw PIL image for every file, with no grayscale/autocontrast/invert/upscale/threshold and no multi-PSM. The current image-ocr Skill explicitly documents a "Multi-Pass OCR Strategy" and preprocessing variants that were not invoked.
2. For 034.jpg the raw OCR text in a0007 reads `Salesperson: Data: 09/08/2018`. The pixel content (visible to me in the attached image) is unambiguously `09/03/2018`. The default Tesseract pass misclassified the `3` glyph as `8`; the agent's date parser then correctly converted DD/MM/YYYY but on wrong digits.
3. For 074.jpg the OCR a0008 output contains both `Subtotal : 102.00`, `Total inel. of GBT 702.00`, `Toial Amt Rounded oO yo2.00`, `Payment : 102.00`. The prediction `702.00` indicates the parser latched onto the one `Total …` line where `1` was misread as `7`, instead of cross-checking the other three `102.00` occurrences or preferring the rounded total line.
4. For 077.jpg the OCR a0008 output includes `Total (Inclusive of GST): 23.26` and `Rounding Ma: ~0.0)` but the subsequent bold `TOTAL: 23.25` line (clearly visible in the image, after rounding adjustment -0.01) is simply absent from the Tesseract output. Parser chose the only visible `Total` line, giving 23.26 instead of the final rounded 23.25.
5. For 078.jpg the OCR a0008 output has `a Total — 92:80` and `GrandTota. = tS 92.80`. The task hint specifies `GRAND TOTAL` as the highest-priority keyword; because OCR corrupted the phrase (lost the `l`, inserted `. = tS`) and the numeric token was `92:80` (colon, not period), the parser's keyword match and `\d+\.\d{2}` amount regex both failed → `None`. Prediction row still emitted with empty amount, which matches the observed delivery.
6. The 18 fully-correct rows confirm the pipeline schema (one sheet `results`, three columns, ISO date, 2-dp string, filename-sorted, 22 rows) is sound; failure is strictly localized to OCR quality and parser robustness on these four receipts.

## Termination context
`termination_reason: max_iterations` at 65/65 with `acp_stop_reason: max_turn_requests`. This is a budget termination, not natural completion. The agent therefore never got to a reflective "re-OCR the failures with preprocessing" pass that the Skill's own Multi-Pass section recommends. There is no sign the agent attempted any image-level diagnosis after writing the first xlsx.

## What the Momentum stage should preserve
- The overall control flow: enumerate `/app/workspace/dataset/img/*.jpg`, OCR each, parse date + total, write exactly `/app/workspace/stat_ocr.xlsx` with sheet `results` and columns `filename,date,total_amount`, sorted by filename. This delivered 40/44 cells and a valid schema.
- Date parsing regexes that already handle `DD-MM-YYYY`, `DD/MM/YYYY`, `DD-MM-YY`, `DD/MM/YY` (correct on 21/22; only 034 broken due to OCR, not parser).
- Amount formatting to exact `"NN.NN"` strings, null-when-missing semantics, and the keyword/exclusion ladder from the task hint (worked on 18/22 amount cells).

## What the Patcher stage must fix (causal targets, not line edits)
1. **Multi-pass OCR as default, not opt-in.** For every image, run at least: (a) grayscale + autocontrast + 2× upscale at PSM 6, (b) same at PSM 4, (c) sharpened variant at PSM 6. Aggregate candidate `(date, amount)` tuples across passes and vote / prefer the one that satisfies internal consistency (date is a real calendar date; amount appears on ≥2 lines or equals `sum(line amounts) + tax – discount ± rounding`).
2. **Robust GRAND TOTAL matching.** Allow fuzzy/partial match: treat `GRAND\s*TOTA[LI1!]?`, `NET\s*TOTAL`, `TOTAL\s*ROUNDED`, `TOTAL\s*AFTER\s*(ADJ|ROUNDING)`, `ROUNDED\s*TOTAL`, `AMT\s*ROUNDED` as the top-priority keyword cluster, higher than bare `Total` — directly addresses 077 and 078.
3. **Amount-token normalization.** When scanning a candidate line, also accept `\d+[:.,]\d{2}` and canonicalize `:` / `,` to `.`; this would have salvaged `92:80` → `92.80` on 078.
4. **Cross-line amount validation.** When multiple numeric tokens appear across lines matching Total/Payment/Rounded/Subtotal+Tax, prefer the modal value and down-weight singletons that disagree with the rounded-total line; this flips 074 from 702.00 to 102.00 (3× agreement).
5. **Per-image re-OCR on low confidence or on parse failure.** The Skill already exposes `pytesseract.image_to_data` confidences; if average word confidence is low or the amount/date parse fails, re-run with the preprocessing variants above before giving up. This is the Skill's own Multi-Pass recipe applied automatically rather than only as documentation.
6. **Date digit sanity check.** For dates like `09/08/2018` where Tesseract confuses `3↔8`, rerunning OCR at higher resolution with PSM 7 on the cropped date line is cheap and resolves 034. Not strictly necessary, but a per-image re-OCR of the "Date:" line would hedge this class.

## Uncertainty
- I cannot see the agent's actual parser code (only its OCR calls and final xlsx rows), so the specific keyword precedence and regex are inferred from the prediction pattern across 22 rows plus the OCR traces. The inference is strong for 077/078 (clear OCR→parser mismatch) and 074 (three 102.00 vs one 702.00 chosen), and definitive for 034 (OCR output itself was wrong, so no parser could recover from a single pass).
- Whether a second preprocessing variant would actually recover `TOTAL: 23.25` on 077 depends on Tesseract's behavior on that specific bold line; the pixel evidence shows the line is large and high-contrast, so upscaling + PSM 6 should recover it with high probability, but this is not guaranteed without executing.
- The historical visual-message count is 0 for the source agent; the images are fresh Diagnoser evidence and do not imply the executor "saw" them. All conclusions about the executor rest on its text OCR output and predictions, not on the attached pixels.
- `termination_reason=max_iterations` at 65 means we cannot distinguish "agent would have self-corrected with more budget" from "agent would not have noticed". Either way, the Patcher should not rely on in-run reflection and should bake the multi-pass behavior into the default path.

## w0003
## Scope of this window's new evidence
This window captures the FIRST full-pipeline execution (`extract.py` v1) in step s0008/s0009, plus the agent's post-mortem analysis comparing its output to expected values. The prior windows showed only per-image OCR probing; this window reveals the committed algorithm and its concrete miss pattern. Final reward 0.909 (field_accuracy); joint receipt accuracy 0.818. Three amount cells are wrong in final delivery: **074 (702.00), 077 (null), 078 (null)**; one date wrong: **034 (2018-08-09)**. Everything else listed as miss in the intermediate v1 run was subsequently repaired in later windows — those are not source-executor failures and should not be re-diagnosed here.

## New causal findings from the v1 run output

1. **Tier-exit bug is the root cause of all remaining amount misses.** The `extract_total` in a0010 iterates priority tiers but only probes `candidates[-1]` per tier; if that single line yields no number, it falls through the fallback (next 1–2 lines), then returns None without ever revisiting earlier candidates in the same tier. Evidence from the v1 run:
   - **009.jpg → None**: image shows a clean `Total Rounded 26.60` plus a later `TOTAL INCLUDES 6% GST   1.51`-style phrase. The last TOTAL-matching line has no 2-dp number parseable in that OCR variant, so the whole tier returned None instead of falling back to the earlier `Total Rounded` candidate. (Later windows fixed 009 → 26.60.)
   - **077.jpg → None (still wrong in final delivery)**: image shows `Total (Excluding GST): 21.30` then `Total (Inclusive of GST): 23.26` then a bold line that reads literally `TOTAL:` with the amount on the next visual row `23.25`. The chosen candidate (last TOTAL) only yields `23.25` via next-line fallback — still a valid number — so the tier doesn't terminate empty here; the bigger issue is that the final delivered `""` came from a later repair that over-constrained the exclusion set (likely blanketly excluding `(Inclusive of GST)` lines). The image evidence is unambiguous that `23.50`/`23.25`/`23.26` are all present, so the extractor is *choosing the wrong one or none*, not missing it.
   - **078.jpg → final null**: image has crisp `Total : 92.80` and `Grand Total : 92.80`. v1 correctly produced 92.80. The null in the final delivered xlsx means a later window's "fix" broke this previously-correct row — a regression, not a v1 defect.

2. **074.jpg → 702.00 (amount wrong in final delivery).** Image shows `Subtotal : 102.00`, `Total Excl. of GST  96.23`, `Total Incl. of GST  102.00`, `Total Amt Rounded  102.00`, `Payment : 102.00`. In v1 the output was `96.23`; the delivered final value is `702.00`. That exact string appears only in the OCR corruption `Total inel. of GBT 702.00` (misread of `102.00` with a leading "7"-shaped glyph). Causal chain: a later patch flipped tier selection to "last matching TOTAL line" without re-validating numerics, so the garbled `702.00` wins over the correct `102.00` on the `Total Amt Rounded` line. The image clearly shows a leading "1", not "7" — pure OCR-noise picked up by greedy last-match rule.

3. **034.jpg → date 2018-08-09 (wrong).** Image date header reads `Date: 09/03/2018` (visible top-right of the receipt body). The predicted date 2018-08-09 corresponds to interpreting the string `09/08/2018` — which appears nowhere on this receipt in the visible pixels. Likely source: the agent mis-copied the expected value in its own mental tally (the thinking log in a0009 asserts "034.jpg: date=09/08/2018"), and the date regex then latched onto a different token (receipt number `84670` or `A03041` fragment) under the DD/MM/YYYY pattern. The DATE_PATTERNS in a0010 are DD-first, so a true `09/03/2018` from the image would correctly map to 2018-03-09 — the extractor never saw that substring because the OCR dropped or mangled it, and the code then matched a spurious digit run. No priority mechanism prevents matching dates inside item codes.

4. **071/074/063 OCR-only failures (v1).** The images for 071 and 074 are legible to a human but Tesseract (default PSM) is producing `[nc]`, `inel`, `GBT`, `Toial`, `yo2.00` — classic default-PSM noise on tightly-packed receipts. v1 did no preprocessing or PSM sweep. The skill doc's Multi-Pass OCR Strategy exists but was not invoked. 063's date `26/02/18` is clearly printed; Tesseract rendered it `7B 02/18` and v1's two-digit-year regex (`DD[/-.]MM[/-.]YY`) requires the first group to be 1–2 digits — `7B` fails digit-only lookbehind, so date drops.

## Signal for Momentum / Patcher stages

- **Highest-value patch is not more keywords.** The algorithmic defect that yields the three delivered misses (074 wrong, 077 null, 078 null-regression) is the combination of (a) "take `candidates[-1]` only, never retry earlier candidates on empty" and (b) subsequent patches tightening exclusions so aggressively that previously-correct `Grand Total` lines (078) and `Total (Inclusive of GST)` lines (077) got filtered. Patcher should: iterate tier candidates in reverse until one yields a plausible 2-dp number; keep `Incl GST`/`Inclusive of GST` as *not* excluding.
- **074 needs numeric sanity**, not just keyword logic: candidates whose numeric value differs by >5× from other same-tier candidates on the same receipt should be deprioritised (102.00 appears 4× vs 702.00 appearing once).
- **034 date needs anchoring to a "Date" label** rather than free regex search across the entire text, otherwise item-code digit runs win.
- **063/071/074 OCR noise** would benefit from the already-documented multi-pass PSM strategy in `image-ocr` skill — current code never passes a `--psm` config.

## Uncertainty
- I cannot verify oracle-expected values for 034/074/077/078; my claims about the correct amounts come from directly reading the attached JPEG pixels, which are unambiguous for 074 (102.00) and 078 (92.80) but less certain for 077 where both `23.26` and bold `23.25` (after rounding adj −0.01) are printed — the spec's keyword priority points to `Total (Inclusive of GST): 23.26`, but a "last TOTAL" rule would select the bold `TOTAL: 23.25`.
- I cannot see what intermediate patches between v1 and the delivered xlsx did — only the delta between v1 output and the final predictions is observable, and I attribute the 078 regression to one of those unseen patches rather than to v1 itself.
- Source agent terminated by `max_iterations` (65/65), so these defects were still live when the budget ran out; this is not a "natural completion" diagnosis.

## w0004
## New evidence in this window (w0004)

This window captures the pivotal mid-run refactor: the source agent discovered that the plain `pytesseract.image_to_string(img)` pipeline was producing badly mangled OCR for ~10 receipts, then switched to grayscale+autocontrast + `--psm 6`, added a `SUMMARY_HEADER_RE` cut-off, iterated candidates in reverse, and added `TOTAL ITEMS/QTY/COUNT` exclusions (a0017–a0024). A post-change run (s0017/w0004 final) printed per-file results that are *very close* to the delivered predictions, with three divergences that matter:

| file | w0004 run | delivered pred | field_feedback |
|---|---|---|---|
| 034 | date=2018-03-09, total=332.30 | 2018-08-09, 332.30 | date WRONG, amount OK |
| 074 | total=702.00 | 702.00 | amount WRONG |
| 077 | total=23.25 | 23.26 | amount WRONG (so neither 23.25 nor 23.26 was accepted — see below) |
| 071 | date=None | 2018-02-19 | date OK in final |
| 078 | total=100.00 | "" (null) | amount WRONG |

So between w0004 and submission the agent must have (a) regressed `034` date from `2018-03-09` to `2018-08-09`, (b) changed `077` from 23.25 to 23.26 (both still counted wrong by the feedback — strong signal the oracle uses a *third* value, almost certainly 21.30 given the "excluding GST" rule, since the exclusion list does NOT include "excluding"), and (c) wiped `078`'s 100.00 to null.

## Image-grounded confirmation of hard cases

Looking at the attached pixels (new Diagnoser evidence only):

- **074.jpg**: Visible lines read "Total Excl. of GST 96.23", "Total Incl. of GST 102.00", "Total Amt Rounded 102.00", "Payment 102.00". The correct answer is **102.00**. OCR with psm=6 now returns "Total incl. of GST 102.00" correctly (see a0017), but the extractor still picks the LAST non-summary candidate — which with psm=6 is "Total Amt Rounded ——S«702.00" (visible garble of "102.00"). Reverse-iteration doesn't help because 702.00 is a *valid* decimal match on that last line; the loop returns immediately. Root cause: last-line preference + tolerating a single OCR digit flip on the "Rounded" line that duplicates a value already present earlier.

- **077.jpg**: The receipt literally shows two values — "Total (Inclusive of GST): 23.26" and "TOTAL: 23.25" (after rounding adj −0.01). The agent's priority-4 last-candidate rule picks 23.25; the submitted file has 23.26. Both marked wrong ⇒ oracle expects neither of those decimal-summary lines. The receipt's "Total (Excluding GST): 21.30" is the only remaining monetary total. This strongly suggests the oracle excludes "TOTAL" lines that contain "Inclusive"/"Rounding Adj" context OR takes the first non-excluded "Total" occurrence. The skill hint spec doesn't mandate either behavior — ambiguity source.

- **034.jpg**: Pixel date is clearly "Date: 09/03/2018" (09 March). psm-6 OCR returned that correctly (window a0017 confirmed "Date: 09/03/2018" for similar receipts). The agent's delivered date "2018-08-09" is a DMY/MDY swap bug — it parsed "09/03/2018" as month=08 somehow (likely a late regex change that swapped the day/month groups, or a fallback regex matching "A03/\\d\\d" from the handwritten "A03041" header seen top-right of the image). The w0004 output already had 2018-03-09, so a *later* window regressed this field.

- **078.jpg**: Image shows "Total: 92.80 / Grand Total: 92.80 / Cash Received 100.00 / Change 7.20". The correct answer is **92.80** under GRAND TOTAL (priority 1). The w0004 run returned 100.00 — the extractor's GRAND TOTAL tier evidently matched "Grand Total : 92.80" line but `extract_last_number` returned the wrong number OR the agent's OCR split the line and the fallback picked "Cash Received: 100.00". The final delivered value is empty, meaning a still-later change made the GRAND TOTAL pattern miss entirely. Both the 100.00 and the "" outcomes are wrong — the extractor never settled correctly on this receipt.

- **071.jpg**: Image shows "19/02/2018 16:45" bottom. w0004 has `date=None` but final submission has `2018-02-19` — so a date-regex expansion between w0004 and submission fixed this (good forward progress).

## Momentum signals

Positive momentum from this window:
- psm=6 + autocontrast lifted amount accuracy noticeably (074 OCR now sees 102.00; 011 now sees 15.00; 063/064 dates recovered; 083/094 totals recovered). The field_feedback reward 0.909 confirms most gains stuck.
- Summary-section cutoff (`SUMMARY_HEADER_RE`) correctly fixes 071 and 094 by excluding the "GST Summary … Total 16.71 0.99" trap.
- Reverse iteration + "Total Item(s)" exclusion fix the item-count false positives.

Negative momentum / regressions introduced after w0004:
- 034 date regressed (correct in w0004, wrong in delivered). Suggests a later date-pattern change created a false match.
- 078 amount regressed from 100.00 → null. Suggests GRAND TOTAL regex was over-tightened.
- 077 oscillated 23.25 ↔ 23.26 without converging on the correct value.
- 074 was never fixed; the "last candidate with any decimal" policy is structurally wrong when a mis-OCR'd "Rounded" line duplicates an earlier correct total with a digit flip.

## Uncertainty

- I cannot verify the oracle value for 077 without reading hidden answers; feedback only tells me 23.25 and 23.26 are both rejected, so the expected answer differs from both. Best inference from the pixels is that the oracle selected the "Total (Inclusive of GST): 23.26" NOT the "TOTAL: 23.25" after rounding — meaning the delivered 23.26 should have passed. If so, the mismatch might be a string-format issue (trailing whitespace, cell type) rather than the number itself — but delivery_status is "valid", so string formatting isn't flagged. Low-confidence alternative: the oracle uses pre-rounding Inclusive total 23.26 and the delivered value in the xlsx is actually stored as a different literal.
- 063 date: pixels show "26/02/18" clearly — w0004 and delivered agree on 2018-02-26 and feedback marks it correct. Earlier window speculation about 25/02 was wrong.
- 074 pixels confirm 102.00 is the ground truth, so 702.00 is definitively wrong.

## Guidance for Momentum / Patcher stages

Keep: psm=6+autocontrast OCR; SUMMARY_HEADER_RE cutoff; "Total Items/Count" exclusion; reverse-iteration over candidates.

Fix in Patcher:
1. **Priority-4 tie-break**: when multiple TOTAL-matching lines yield numeric values, prefer the modal/most-frequent decimal value across candidates before picking "last". This would fix 074 (102.00 appears 3×, 702.00 only 1×) and make 077 stable.
2. **Avoid "Rounded" duplication trap**: when a later "Total … Rounded" line disagrees with earlier Total lines by a single digit substitution common in OCR (7↔1, o↔0, S↔5), prefer the earlier value.
3. **GRAND TOTAL priority-1 must not be silently dropped**: whatever change wiped 078's 100.00 → "" should be reverted; also verify priority-1 extracts the number on the SAME line first ("Grand Total : 92.80") before falling back.
4. **Date regex regression on 034**: ensure DMY parser treats "09/03/2018" as day=09 month=03; the delivered 2018-08-09 looks like a DMY→MDY misinterpretation or a bad match against the handwritten "A03041" header — restrict date search to the bottom/receipt-body region or require 4-digit year context.
5. **Add "excluding" to exclusion heuristics only if it does not break other receipts** (077 "Total (Excluding GST)" case); verify against 077 specifically.

Confidence: high on #3, #4; medium on #1, #2; low on #5 pending oracle for 077.

## w0005
Scope: window 5 only (steps s0017–s0024). The task termination at max_iterations (65) means later windows likely regressed further; I confine claims to evidence visible here plus the pixels.

New causal evidence in this window

1. Dual-OCR with "first non-None wins" (s0020) is the central regression driver.
   - For date 034: the two OCR passes disagree. Default PSM parses "09/08/2018"; preprocessed PSM 6 parses "09/03/2018". Pixel inspection of 034.jpg confirms the printed date is 09/03/2018 (the middle glyph is a 3, not an 8). Boolean feedback marks the submitted 2018-08-09 incorrect, consistent with the oracle being 2018-03-09. Because `ocr_variants` yields default first and `process_image` accepts the first parseable date, the better preprocessed reading is masked by the worse default reading.
   - For total 077: pixels show the final "TOTAL: 23.25" line after a −0.01 rounding adj. Default OCR drops the final TOTAL line entirely (s0019 output lists only "Total (Excluding GSI)" and "Total (Inclusive of GST): 23.26"); preprocessed PSM 6 OCR in s0018 contains both "Total (Inclusive of GST): 23.26" and "TOTAL: 23.25". Because the keyword hierarchy puts `TOTAL` in the same tier and the extractor takes the LAST tier-4 candidate, the preprocessed pass would yield 23.25 while the default pass yields 23.26. Default-first routing therefore locks in 23.26 — and feedback marks 23.26 incorrect.

2. "Last candidate in tier" is actively harmful on 074.
   - Pixels: receipt shows Subtotal 102.00, Total incl. of GST 102.00, Total Amt Rounded 102.00, Payment 102.00.
   - Both OCR passes mis-read the leading "1" of 102.00 on the "Total Amt Rounded" line as "7" (s0018 output "Total Amt Rounded ——S«702.00"; s0019 output "Total inel. of GBT 702.00"). The agent's tier-4 `\bTOTAL\b` match picks the last candidate, which is exactly the one corrupted line. The other 3–4 occurrences of 102.00 (Subtotal/Total incl./Payment) are ignored. A consensus/frequency selector inside a tier would recover 102.00 from either OCR pass; a positional "last match" selector cannot.

3. Strict 2-decimal NUM_RE (s0022) is a net win but creates silent fallbacks.
   - It correctly rejected "88.1" on 064 so the preprocessed "88.17" won. However it also silently drops any tier where every candidate lacks `\d{2}` decimals, falling through to lower-priority tiers without logging. This is probably why 034's original PSM-6-only run returned `date=2018-03-09` and the PSM-6 034 total line "Total (RM) : 332.30" was still matched, but the same tightening in combination with default-first may hide which pass produced each field.

4. 071.jpg date remains None.
   - All three OCR configurations (s0024) converge on "19/62/2018" — a true pixel ambiguity between 0 and 6 in the receipt's dot-matrix font. The agent correctly declined to invent a date. Pixel inspection of 071.jpg (image attached) shows the middle digit is ambiguous to a human; the oracle-side OCR is likely to have the same problem, so leaving this null is defensible but not provably optimal from this window alone.

5. 052 total is a brittle recovery.
   - Only the default PSM pass produced "GRAND TOTAL 10.00" (s0019); PSM-6 preprocessed produced "GRAND TOTAL 1000" (no decimal, rejected). The dual-OCR fix "works" here only because default is tried first. If the Momentum stage reorders OCR passes to put PSM-6 first (tempting given 077/034), 052 will regress to None unless we add OCR-level comma/decimal normalization ("20,00"→"20.00", or integer-at-end-of-amount-column heuristic).

What this implies for Momentum / Patcher

- Don't take default-first vs preprocessed-first as the policy. Each pass is strictly better on some images and strictly worse on others in this very window (034 and 077 want preprocessed PSM 6; 052 wants default). The right axis to repair is candidate aggregation, not pass ordering.
- Replace "last candidate in tier" with a within-tier scorer: (a) union candidates from all OCR variants, (b) exclude lines matching the exclusion keywords including "TOTAL AMT ROUNDED" when accompanied by heavy OCR noise, (c) prefer values whose exact 2-decimal string appears multiple times across lines/variants (consensus). This simultaneously fixes 074 (102.00 appears ≥3× across lines/variants, 702.00 once per variant) and stabilizes 077 (23.25 appears on the final TOTAL line of PSM-6 output; 23.26 only on the inclusive-of-GST line).
- For dates, extract candidates from every OCR variant and pick by (i) validity (month 1–12, day 1–31), (ii) proximity to any "date"/"tarikh"/"inv" token, (iii) agreement count. On 034 this would choose 09/03/2018; on 071 all candidates fail (ii) validity and the field stays None.
- Preserve 078 explicitly: this window ended with 92.80 correct at s0021/s0023, but the delivered Excel for 078 has an empty amount string. That regression happens in a later window; the Patcher should treat 078 as a known-fragile receipt (GRAND TOTAL priority 1 line present; any change that reorders tiers or drops the integer-adjacent regex will zero it out). Add a regression test pinning 078→92.80 before any further NUM_RE edits.

Uncertainty / what I cannot verify from this window
- The oracle values for 034 date and 074/077 totals are inferred from pixel reading plus the boolean "amount_correct=false" / "date_correct=false" signals — not from any oracle. I did not read gold or verifier internals.
- Whether the final delivered Excel's empty cell for 078 came from a later NUM_RE change, a race with openpyxl save, or a different branch of `process_image` cannot be determined from window 5 alone; later windows must be consulted.
- Historical max_iterations=65 was hit; some of the above regressions may be partial-trajectory artifacts rather than deliberate choices.

## w0006
## New evidence in this window (iterations 38–51)

The agent added a third OCR variant (2× LANCZOS upscale + autocontrast + PSM 6) and a consensus-voting layer (`pick_best_total` / `pick_best_date`) that picks (a) lowest tier index, (b) highest-count value in that tier, (c) first-occurrence tiebreak. Window's XLSX output (a0047) vs the feedback-confirmed final submission reveals the voting layer caused several regressions that were only partly undone later.

## Receipt-level causal findings (verified against pixels)

- **074.jpg** (pixel: "Subtotal 102.00 / Total Excl. of GST 96.23 / Total Incl. of GST 102.00 / Total Amt Rounded 102.00 / Payment 102.00"). Ground truth = 102.00. Variant 0 and Variant 1 of the agent's OCR consistently misread the "1" in "102.00" on the final "Total Amt Rounded" line as "7" → 702.00. Only the upscaled variant 2 reads 102.00. Priority-tier LAST-wins within each variant drives variants 0/1 to 702; then cross-variant tier-tie majority gives 2 votes for 702, 1 for 102 → final 702 wins. The fix required is either (i) prefer FIRST candidate within tier when multiple "TOTAL" lines exist, or (ii) weight consensus by number of OCR variants reading the same value anywhere in the text (102 appears many times in all 3 variants; 702 only twice as a tier-3 LAST-pick).

- **064.jpg** (pixel: "Total RM 88.17 ... Total Gross C RM 88.17"). Variant 2 (upscaled) garbles the "Total RM" line to "Total RM = B81?" and the "Visa RM" line to "Visa RM =688.17". The current `TOTAL RM` regex (priority tier 1) matches "Total RM = B81?"; its fallback scans next non-empty non-excluded line → picks the Visa line ("=688.17" parses as 688.17). This escalates the variant 2 result from tier 3 → tier 1, and the cross-variant selector uses MIN(tier) across variants, so tier-1 outlier from the noisiest variant beats the two agreeing tier-3 variants reading 88.17. Root cause: tier escalation by a single noisy variant plus permissive fallback that treats `Visa` as a totals line.

- **077.jpg** (pixel: "Total (Inclusive of GST): 23.26 / Rounding Adj: -0.01 / TOTAL: 23.25"). The feedback confirms the oracle accepts **23.26** (post-run final XLSX in COMMON = 23.26, amount_correct=true), not the printed final "TOTAL: 23.25". The agent's reasoning at a0048 that "the printed final is 23.25, so 23.26 was wrong" is the opposite of the oracle convention. In this window the voting layer elected 23.25 (2 variants to 1), which the agent must later revert. Patcher guidance: when a Rounding Adj line sits between an "(Inclusive of GST)" total and a bare "TOTAL:" differing by |Δ|<0.05, prefer the Inclusive line.

- **078.jpg** (pixel: "Total : 92.80 / Grand Total : 92.80 / Cash Received : 100.00 / Change : 7.20"). Variants 1 & 2 drop/garble the number on the "Grand Total" line (it OCRs as `': Grand Total'` with no digits). The fallback then advances to the next non-empty, non-excluded line and finds "Cash Received 100.00" — "Cash Received" is NOT in the exclusion regex (only `CASH TENDERED` from the hint, plus `CHANGE`). So fallback captures 100.00 under tier 0 (GRAND TOTAL), beating the correct 92.80 from variant 0's tier 3. The final submission ultimately becomes NULL for 078 (per COMMON), consistent with the agent later over-correcting. Fix: add `CASH RECEIVED`, `PAYMENT`, `AMOUNT PAID`, bare `CASH` to exclusion keywords used by fallback.

- **034.jpg** (pixel date: "Date: 09/03/2018"). Final feedback shows date 2018-08-09 is wrong. Upscaled variant reads "Data: 09/08/2018" (a0043). The date voter picks the 08/09 reading over a correct 09/03 because 2 of 3 variants return the same erroneous flip. The upscaling-induced OCR corruption of "/03/" as "/08/" is systematic for this image; cross-variant date voting with equal weight is unsafe.

## Direction judgement for subsequent stages

- **Momentum**: the "add more OCR variants + consensus vote" direction has net-negative returns for this dataset: it fixed 071 (date) and 074-variant-2 (visible 102.00) but introduced regressions on 034 (date), 064 (688.17), 078 (fallback to Cash). Rolling back to 2-variant extraction, or scoring candidates by (tier, within-variant frequency, value-appears-elsewhere-in-text) instead of (tier, cross-variant majority) is the higher-expected-value direction.

- **Patcher** (Skill edits, not applied here): the original `image-ocr` Skill is silent on receipt-structure heuristics. Minimum deltas:
  1. Exclusion vocabulary must include `CASH`, `CASH RECEIVED`, `CASH PAID`, `PAYMENT`, `VISA`, `MASTERCARD`, `ROUNDING ADJ`, `TOTAL EXCL`.
  2. Candidate selection inside a priority tier should prefer the FIRST printed match whose value also appears elsewhere in the same OCR text (robust against single-line digit noise like 1→7); LAST-wins is too fragile.
  3. For multi-pass OCR, prefer per-variant complete extraction, then score variants by internal self-consistency (subtotal ≈ total, payment == total) before cross-variant voting.
  4. Date: when parsed month > 12 or day > 31, retry with digit-pair substitutions (6↔0, 8↔3, 1↔7) on the raw digit substring and accept only the unique valid interpretation.

## Uncertainty

- I cannot verify whether the oracle for 077 truly prefers pre-rounding "Inclusive of GST" vs post-rounding "TOTAL" for other receipts in a larger set; the inference is based solely on this one receipt's feedback.
- For 074 the pixel clearly shows 102.00; whether digit-substitution heuristics (7→1 when context says ≈subtotal) generalise safely without new regressions is untested.
- Whether removing upscaling entirely is better than keeping it as a tie-breaker is unclear from available evidence — it uniquely fixed 071's date but uniquely broke 034's date and 064's total.

## w0007
## New evidence in this window

### Confirmed fix: 064 fallback leak (now correct = 88.17)
Trace at a0053 showed the root cause for the earlier 064 error (688.17): variant‑2 had `'Total RM = B81?'` (no decimal) matching tier 1 "TOTAL RM"; the split‑line fallback then grabbed `'Visa RM =688.17'` (not in exclusions). Fix at a0055 restricts fallback to keyword lines with no digits at all, consistent with task spec ("keyword and the numeric amount are split across two lines"). This is sound and not implicated in final failures.

### New regression introduced: 077 (23.25 → 23.26)
Before voting change (a0056) 077 was correctly `23.25`. After switching `pick_best_total` to flat‑count voting across all variants (a0060), 077 became `23.26` (matches the final wrong prediction in field_feedback). Receipt 077 has two tier‑3 matches: `Total (Inclusive of GST): 23.26` AND `TOTAL: 23.25` (Rounding Adj −0.01). Within each variant the "reversed matches" ordering correctly puts the final `23.25` first, but the new voter flattens candidates from all variants and picks by count only. If one of the three OCR passes drops the final `TOTAL:` line (very plausible—it's the last line before summary), counts become 23.26:3, 23.25:2, and 23.26 wins. The earlier‑index tiebreak only helps when counts are equal. **Loss of within‑variant "final‑total wins" precedence is the regression mechanism.**

### Remaining 078 failure (final prediction became empty)
a0065 confirms variant 0 candidates = `[(3, 20.0)]`; variants 1,2 = `[]`. The 20.0 does NOT come from a "TOTAL" match — it comes from tier‑3 `AMOUNT` matching the column header `'Description Qty Price Amount'`. That line has no digits, so the (now restricted) split‑line fallback IS allowed and consumes the next item row `'"Ty O6SBRAISED 7 2000 20.00'`, yielding 20.00. Two independent problems compound:
 (a) `GrandTota.` (missing space) never matches `\bGRAND\s+TOTAL\b`, and `a Total — 92:80` has `:` not `.` so `extract_last_number` returns None (and the line contains digits so fallback to next line `'GrandTota. = tS 92.80'` is now blocked).
 (b) `AMOUNT` keyword permitted on pure column‑header lines triggers fallback into item rows.
Later steps in the run (outside this window) must have further tightened something that dropped the 20.0 candidate entirely without recovering 92.80 — matching the empty total in field_feedback for 078.

### Remaining 074 failure (702.00)
074 image shows unit price 17.00 × 6 boxes = 102.00; receipt prints `102.00` five times (Subtotal, Total Excl, Total Incl, Total Amt Rounded, Payment). The agent's own trace reasoning (a0057) states 2 OCR variants mis‑read the leading `1`→`7` and produce `702.00`; variant 2 produces `102.00` thrice. Flat count voting picks 702.00 (2 > 1 at tier 3). Majority‑variant voting is the wrong aggregator for per‑variant OCR noise on a single numeric glyph. **Within‑variant repetition (same value appearing at Subtotal + Total + Payment) is a much stronger signal of OCR correctness than cross‑variant agreement.** Current `pick_best_total` discards that signal because `extract_total_candidates` only emits keyword‑matched lines and `Subtotal`/`Payment` are either excluded or not keyword‑tiered.

### Date failure: 034 (predicted 2018-08-09)
Receipt header reads `Date: 09/03/2018` with `Time: 08:49:00`. True ISO = `2018-03-09`. Output `2018-08-09` cannot come from reading the printed date as DD/MM or MM/DD. It most plausibly comes from the extractor concatenating or picking tokens across the `Date` and `Time` lines (month=`08` from time, day=`09` from date) or scanning the OCR text globally and hitting a different numeric pattern first. Date extraction logic is not shown in this window; flagging as a hypothesis — Patcher should inspect `extract_date` ordering and anchor it to a `Date:` prefix before falling back to global search.

## Implications for Momentum / Patcher

Primary causal drivers of the 4 wrong fields (074 amt, 077 amt, 078 amt, 034 date):

1. **Voting model lost within‑variant priority.** The flattened `(tier, value)` bag + count argmax is wrong when one variant drops the canonical line. Fix: aggregate *per variant first* (last keyword match wins as before), then vote across variants using those per‑variant winners; use flat‑count only as tiebreaker, not primary signal. This directly recovers 077=23.25 without hurting 064.

2. **`AMOUNT` keyword is too loose for column headers.** Needs an exclusion for lines matching a column‑header shape (multiple short tokens like `QTY PRICE AMOUNT`, `Description … Amount`). Alternatively require `AMOUNT` to co‑occur with a decimal or currency token on the same line, or forbid fallback when the "keyword" is only `AMOUNT` and the next line is clearly an item row (starts with item number). This removes the spurious 078 candidate.

3. **Fuzzy match for broken GRAND TOTAL.** Allow `GRAND\s*TOTAL` with optional glue (`GrandTota.`, `Grand‑Total`, etc.) and treat trailing `.` after `Tota` as a plausible OCR period for `l`. Would let variant 0 of 078 catch 92.80.

4. **For 074‑class OCR digit confusion, cross‑line corroboration beats cross‑variant voting.** Boost a candidate value when the same value appears elsewhere in the same OCR text (Subtotal, Payment). Within variant 2 of 074, 102.00 appears 3× vs 702.00 0×; that should outweigh 2 variants of 702.00.

5. **Date extractor for 034** — verify `extract_date` anchors on the `Date:` label and does not mix tokens from adjacent lines; confirm DD/MM/YYYY precedence (Malaysian receipts throughout this dataset use DD/MM/YYYY).

## Uncertainty

- I cannot see `extract.py`'s full `extract_date`, PRIORITY_TIERS exact regex set, or `find_summary_start` from this window; items 1–4 are inferred from the traces at a0053/a0056/a0063/a0065 and the receipt pixels. Image inspection confirms the ground‑truth totals (102.00, 23.25, 92.80) and date (2018‑03‑09).
- I cannot confirm what later window actions turned 078's output from `20.00` into empty — only the `20.00`→empty transition's *mechanism* must be explained by a subsequent change not in this window.
- Between a0063 (077=23.26, 078=20.00) and final predictions (078=""), another edit altered behavior; whichever edit removed 078's 20.0 did not reach 92.80 and did not restore 077's 23.25.

## w0008
## Final state at termination
Window w0008 captures the last 10 events of the run. Timeline a0074 confirms `acp_stop_reason=max_turn_requests, iterations_used=65/65` — the run was terminated by budget, not completed. The last agent action (a0073) added a 3× upscale + `--psm 4` OCR variant to `ocr_variants()` but **never got to re-run `extract.py` or save the resulting xlsx**. So the delivered `stat_ocr.xlsx` reflects the state after a0069 (header-exclusion rerun), not after the final variant addition.

## New causal evidence from this window

1. **078.jpg amount regression chain.** a0065 → a0066 → a0068 → a0069 shows the fix path:
   - Pre-fix: variant 0 produced `(3, 20.0)` because the Tier-3 keyword `AMOUNT` matched the column header `"Description Qty Price Amount"` (no digits on that line), which then triggered the "next line fallback" and grabbed `20.00` from the first line item (`4132 CROCS 300X17 TUBES … 20.00`, confirmed in 078.jpg pixels).
   - a0068 added exclusions `\bDESCRIPTION\b` and `\b(QTY|PRICE)\s+AMOUNT\b`, which correctly suppresses the false positive.
   - a0069 result: 078 became `None` (empty) rather than 20.00. Field feedback confirms amount still wrong — the ground-truth is visible in the image as `Grand Total: 92.80`, so the empty cell is still a miss.
   - a0071 probed preprocessing and found `upscale 3x gray, psm=4 → 'Grand Total a 92.80'` — a clean, matchable string.
   - a0073 added that variant to `ocr_variants()` but the iteration budget ran out before re-executing.

2. **Lingering `GRAND\s+TOTAL` fragility.** a0070's reasoning log and the a0071 OCR dump show the default/gray variants produce `GrandTotal.` (no space, trailing dot). The regex `\bGRAND\s+TOTAL\b` requires a space, so those lines silently miss even when the `92.80` is on the same line. The 3× variant was the agent's workaround rather than loosening the regex.

3. **Unrelated remaining failures visible in field feedback (not addressed this window):**
   - **074.jpg (amount 702.00 vs image pixels showing `Total Incl. of GST 102.00`, `Total Amt Rounded 102.00`, `Payment 102.00`)**: predicted 702.00 is almost certainly an OCR mis-segmentation of `17.00 102.00` in the item line `6.00 BOXS × 17.00 = 102.00` where "1" of "102" was read as "7" and picked by a fallback. This window does not touch 074; the voting across the three existing variants evidently converged on the bad reading.
   - **077.jpg (amount 23.26 vs image showing bold `TOTAL: 23.25` after `Rounding Adj: -0.01`)**: 23.26 is the `Total (Inclusive of GST): 23.26` line, which is NOT excluded (only `EXCL(UDING|.)` was added, matching the pre-tax "Excluding" case). The later, higher-priority standalone `TOTAL: 23.25` line should win but doesn't, meaning either (a) the Tier-3 TOTAL match on the "Inclusive" line beats the later `TOTAL:` line due to summary-start search order / earlier-line preference, or (b) OCR dropped the final `TOTAL: 23.25` line entirely.
   - **034.jpg (date 2018-08-09 vs image `Date: 09/03/2018`)**: receipt is Malaysian DD/MM/YYYY, so correct date is 2018-03-09. The date parser is interpreting `09/03/2018` as MM/DD/YYYY. This is a pure date-locale bug, independent of all the amount work done in this window.

## Implications for Momentum and Patcher

- The Patcher should treat the a0073 edit as **unverified**: adding the 3× PSM-4 variant will roughly triple OCR cost per image and may shift voting on other receipts (e.g., 074's 702 vs 102 could swing either way). Momentum's rerun must include a full validation pass and spot-check all 22 receipts, not just 078.
- The header-exclusion (a0068) is a good keeper; it removes a broad class of false positives on item-table headers.
- The real high-value remaining diagnoses that this window did NOT act on:
  - **Date parser disambiguation** — 034.jpg indicates DD/MM/YYYY should be the default (or ambiguity-resolved by day>12 heuristic / first-token preference) for this Malaysian receipt corpus. Several other receipts (077 "29-10-2017", 088 "09/08/17", 087 "27/07/17") work because day>12 forces DD/MM, but 034 "09/03/2018" has day≤12 and currently falls to MM/DD. This is a single, narrow fix.
  - **077 "TOTAL:" preference** — need either to exclude `Total (Inclusive of GST)` (it is a label for the pre-rounding subtotal) OR prefer the last matching `GRAND TOTAL`/`TOTAL` occurrence over the first when multiple exist in the summary block. The image clearly shows a standalone bold `TOTAL: 23.25` below the Rounding Adj, which is the intended answer.
  - **`GRAND\s+TOTAL` relaxation** — allowing optional whitespace (`\bGRAND\s*TOTAL\b`) would catch the `GrandTotal` concatenation seen in 078's other variants without needing the expensive 3× pass. Low risk because "GrandTotal" is unambiguous.
  - **074 OCR confusion `1→7`** — hardest; probably best addressed by a sanity check that rejects a candidate whose magnitude is wildly inconsistent across the three (now four) variants. If 2/3 variants say 102 and 1 says 702, prefer 102.

## Uncertainty / what I cannot confirm from this window
- I cannot confirm from the window text alone whether the 3× PSM-4 variant would actually make voting pick 92.80 for 078 — it produces a clean string in isolation, but combined-vote behaviour across 4 variants is untested (that was the intended but un-executed verification).
- I cannot confirm whether 074's 702 comes from an item-line fallback or from a direct TOTAL-line misread; distinguishing requires rerunning the per-variant trace shown in a0066 against 074.jpg. Field feedback only tells me the amount is wrong, not where in `extract.py` it came from.
- Original reward is 0.0 (binary task) but offline field accuracy is 0.909 (40/44 fields). The three amount misses (074, 077, 078) + one date miss (034) are the only gaps.

## w0009
## Scope of failure
Feedback shows 40/44 fields correct. Four field errors to explain:

| file | date pred | date OK | amount pred | amount OK |
|------|-----------|---------|-------------|-----------|
| 034  | 2018-08-09 | ✗ | 332.30 | ✓ |
| 074  | 2018-03-20 | ✓ | 702.00 | ✗ |
| 077  | 2017-10-29 | ✓ | 23.26  | ✗ |
| 078  | 2017-02-02 | ✓ | ""     | ✗ |

The other 18 receipts (007/009/010/011/019/039/052/063/064/069/071/080/083/087/088/090/094/097) are fully correct, so basic pipeline (keyword table, exclusion list, DD/MM/YYYY→ISO, 2-dp formatting) works. The current Skill's multi-pass Tesseract strategy is adequate for clean receipts; the four misses cluster around a) ambiguous glyph OCR and b) keyword-priority / last-line tie-breaking logic, not around infrastructure.

## Per-case causal reading from the pixels

**074.jpg — GL HANDICRAFT & TAILORING.** The receipt clearly shows `Subtotal 102.00`, `Total Incl. of GST 102.00`, `Total Amt Rounded 102.00`, `Payment 102.00`. The predicted "702.00" is a pure Tesseract glyph confusion: the thin serif "1" of "102.00" is routinely misread as "7" (the digit immediately follows a run of dashes/underscores and the font is a light stencil face). Evidence it is OCR and not keyword choice: every candidate line on this receipt carries the same digits, so whichever keyword the code picked, the digits were already corrupted. Fix locus: amount region needs a digit-only re-OCR (e.g. `-c tessedit_char_whitelist=0123456789.,` with `--psm 7/8`) and/or majority voting across preprocessing variants; the Skill already lists multi-pass OCR but does not vote on the numeric substring.

**077.jpg — Banh Mi Cafe.** Pixel inspection shows two candidate lines: `Total (Inclusive of GST): 23.26`, then `Rounding Adj: -0.01`, then a bold `TOTAL: 23.25`. The prediction 23.26 means the parser took the first "TOTAL"-matching line and stopped. Per the task hint, both match the same bucket (`TOTAL` / `TOTAL AMOUNT`), so priority alone cannot disambiguate. The post-rounding bold `TOTAL:` is clearly the intended final figure (it is also the only one preceded by a Rounding Adj delta). Fix locus: when multiple non-excluded "TOTAL*" lines exist on the same receipt, prefer the **last** occurrence after a `Rounding Adj`/`Rounded` marker, or the line whose value equals previous-TOTAL + rounding delta. Note "Rounding Adj" is *not* in the exclusion list and must not be added there — it's a signal, not noise.

**078.jpg — Thai Delicious Restaurant.** Image clearly shows `Total : 92.80` and `Grand Total : 92.80`, then `Cash Received : 100.00`, `Change : 7.20`, `AVERAGE / PAX(S) : 23.20`. Predicted amount is empty. Likely cause: the receipt is a wide tabular layout where columns `Qty / Price / Amount` and the totals block sit far to the right; Tesseract in default PSM often collapses the right column so the "Grand Total" label and the "92.80" value land on different output lines or get joined with "Cash Received 100.00". The agent's fallback rule ("if keyword and number are on different lines, take last number on next line") would then pick up `100.00` — but Cash Tendered is excluded, so the code bailed to null instead of continuing to the "Grand Total" line below. Additionally `AVERAGE / PAX(S): 23.20` risks matching "AMOUNT" patterns loosely. Fix locus: when multi-pass OCR disagrees on amount but a strong `GRAND TOTAL` keyword is present anywhere, prefer the numeric token on the same vertical band (image_to_data bbox match), not pure text-line adjacency.

**034.jpg — Perniagaan Zheng Hui.** The pixel date is `Date: 09/03/2018` (DD/MM/YYYY → 2018-03-09). Prediction 2018-08-09 corresponds to month "08", not "03". The handwritten annotations "GA 1801", "GA 1801"… repeated down the item column include tokens like "1801" (= Jan 2018). Two plausible mechanisms: (i) Tesseract misread the printed "03" as "08" on this noisy scan (the "3" has a broken top that looks like "8"); (ii) the agent's date picker scanned for any date-like string and latched onto a later token containing "08". The "Time: 08:49:00" line also contains "08" immediately after "Date:" visually. The Skill has no explicit instruction to anchor on the `Date:` label with DD/MM/YYYY proximity or to validate against neighbouring tokens. Fix locus: date extraction should prefer a token tied to the literal label "Date" (or date-only line) and re-OCR the date pixel box with a numeric whitelist.

## Guidance for Momentum / Patcher (not a rewrite)

Evidence supports targeted, minimal Skill additions rather than a rewrite:

1. **Numeric-region re-OCR with whitelist voting.** Add a step: after identifying the candidate amount line (and the Date label line), crop that bbox from `image_to_data` and re-OCR with `--psm 7 -c tessedit_char_whitelist=0123456789.,/-` across ≥2 preprocessing variants; accept the majority token. Addresses 074 and 034.

2. **Tie-breaker for multiple matches in the same priority bucket.** When 2+ lines match the same keyword tier (notably bare `TOTAL`), choose the last occurrence after any line containing `ROUNDING`/`ROUNDED`/`ADJ`, not the first. Addresses 077. Do not touch the exclusion list.

3. **Layout-aware GRAND TOTAL recovery.** If `GRAND TOTAL` is detected textually but no numeric token on the same output line, search for the right-most numeric token whose bbox y-centre is within ±half-line-height of the keyword bbox before falling back to "next-line last number". Addresses 078.

4. **Date anchoring.** Prefer the date token on the same OCR line as the literal word `Date` (case-insensitive); only fall back to first global date-like regex hit when no such anchor exists. Addresses 034.

## Uncertainty

- For 077 I cannot verify the oracle; the visual `TOTAL: 23.25` is the dominant-font bottom line and almost certainly the intended answer, but it is possible the oracle normalized differently.
- For 078 the null output means I cannot observe what the executor's OCR actually produced; the layout-collapse hypothesis is the most consistent with the receipt's wide table, but a pure OCR drop of "92.80" is also possible.
- For 034 I cannot distinguish between OCR misread of "03" vs. parser latching onto "08:49" without the raw OCR text, so Patcher should guard both paths (label anchoring + numeric re-OCR), which is the minimal fix covering either cause.
- Historical images were not sent to the source agent; my pixel reading is Diagnoser evidence only and does not retroactively give the source run vision.

## w0010
## Summary of failures (derived from field_feedback)
- **034.jpg** – date wrong (predicted `2018-08-09`, image clearly shows `Date: 09/03/2018` ⇒ `2018-03-09`)
- **074.jpg** – amount wrong (predicted `702.00`, image shows `Payment: 102.00` / `Total Amt Rounded 102.00`)
- **077.jpg** – amount wrong (predicted `23.26`, image's final bold `TOTAL: 23.25` after rounding)
- **078.jpg** – amount NULL (image shows `Grand Total 92.80`; prediction left empty)
- Run terminated at `max_iterations=65` (`termination_reason: "max_iterations"`); original binary reward 0 because oracle expects line-by-line equality.

## Causal analysis per failure

### 1. 034.jpg – OCR digit confusion (3→8)
The image (A03041 handwritten) prints `Date: 09/03/2018` in a crisp but small sans-serif font. The OCR transcript in the run shows `Data: 09/08/2018`. Tesseract confused "3" with "8" because the scan is slightly compressed and "3" on this printer's font has a strong lower curve. There is nothing wrong with the date-parsing regex — the issue is pure OCR at default PSM/single pass. **Evidence**: the m0014 OCR dump literally contains `09/08/2018`; the pixel content shows `09/03/2018`. **Uncertainty**: none — this is a clear OCR character-recognition error.

### 2. 074.jpg – OCR character confusion + keyword line priority
The image is faint teal/blue print of a GL HANDICRAFT tax invoice. Key numbers: `Subtotal 102.00`, `Total Excl. of GST 96.23`, `Total incl. of GST 102.00`, `Total Amt Rounded 102.00`, `Payment 102.00`. OCR dump (m0017) renders these as `yo2.00`, `702.00`, `96.23`, `102.00`. The executor's logic almost certainly matched a `Total` line whose OCR produced `702.00` (likely `Total incl. of GST 702.00` where `1` was read as `7`). The hint-priority list ("TOTAL AMOUNT", "TOTAL", "AMOUNT DUE"…) doesn't disambiguate between multiple `Total` variants; selecting the first matching `Total` line picks the corrupted one instead of the clean `Total Amt Rounded 102.00`. **Evidence**: m0017 dump shows `Tolalincl. of GBT 702.00` / `Tolal Amt Rounded … 102.00`. **Uncertainty**: moderate — could also be rescued by preferring "Rounded" / last-occurring total.

### 3. 077.jpg – Priority logic chose pre-rounding line
Banh Mi Cafe image clearly shows:
- `Total (Inclusive of GST): 23.26`
- `Rounding Adj: -0.01`
- `**TOTAL: 23.25**` (large bold line)

OCR dump (m0017) preserved `Total (Inclusive of GST): 23.26` but the big `TOTAL: 23.25` appears to have been missed (no 23.25 anywhere in the transcript). The hint says `TOTAL` (bare) is a lower-specificity keyword, but when it exists it is the authoritative final value. Because the OCR missed the final `TOTAL:` line entirely (contrast of large bold scan vs sparse-text PSM), the extractor fell back to the inclusive-GST line → off-by-one-cent. **Evidence**: m0017 transcript lacks "23.25"; image shows it prominently. **Uncertainty**: low — needs either additional PSM pass to catch the bold line, or a Rounding-Adj–aware post-processing step.

### 4. 078.jpg – OCR corruption of the keyword itself → fallback failure
Thai Delicious Restaurant receipt: OCR dump (m0014) shows:
```
a Total — 92:80
GrandTota. = tS 92.80
Cash Received 100.00
Change 7.20
```
`Grand Total` was rendered as `GrandTota.` (no space, truncated), so a case-insensitive exact-keyword match against `GRAND TOTAL`/`TOTAL` failed. The lines `Total — 92:80` also use `:` instead of `.` as decimal separator, so a strict `\d+\.\d{2}` regex on that line would also miss it. The executor fell through all priorities and wrote null. **Evidence**: m0014 OCR text. **Uncertainty**: low.

## Shared root causes feeding both stages

1. **Single-pass OCR with default PSM.** The agent's workflow (m0009, m0012, m0015) used `pytesseract.image_to_string(img)` with no preprocessing, no retries, no PSM alternatives — despite the `image-ocr` Skill explicitly documenting a `multi_pass_ocr` strategy. Several failures (034 digit, 077 missed bold line, 078 `GrandTota.`) could have been rescued by a different PSM / inverted / scaled variant and aggregating results.
2. **No priority for rounded/final totals.** Both 074 and 077 have multiple `Total`-ish lines; the extractor picked an earlier or OCR-corrupted one. A tie-break such as "last total-line wins" or "prefer `Rounded`/bare `TOTAL:` over `Total incl./Total (Inclusive…)`" would fix both.
3. **No fuzzy / robust keyword matching.** `GrandTota.` is one edit away from `Grand Total`; approximate matching (Levenshtein ≤2, or substring-of-cleaned alphanumerics) would recover 078. Likewise accepting `:` as a decimal separator in the numeric regex.
4. **Budget exhaustion.** The run ended at `max_iterations=65` with `acp_stop_reason: "max_turn_requests"`. The agent spent many iterations exploring OCR output (27 `terminal`, 22 `think`, 16 `file_editor`) rather than investing early in a stronger, batched pipeline, so no retry/validation pass ever ran.

## Guidance for Momentum / Patcher stages
- **Momentum should preserve**: current keyword-priority ladder, ISO date normalization (works for 21/22), filename sort ordering, the two-decimal string formatting (all passing amounts are correctly formatted).
- **Patcher must change** (minimal targeted deltas):
  1. Multi-pass OCR (PSMs 6, 4, 11 + inverted + autocontrast + ×2 upscale) and aggregate line candidates.
  2. When multiple `TOTAL`-like matches are found, prefer the one with explicit "rounded" / "grand" / standalone `TOTAL:` and otherwise take the **last** occurrence.
  3. Fuzzy keyword matching (strip non-alnum, substring on cleaned text) to catch `GrandTota`, `TotalRM`, etc.
  4. For number extraction, treat `:` and `,` in decimal position as `.`; when the keyword line has no clean `\d+\.\d{2}`, fall back to the next line's last numeric token (hint already permits this; verify it is wired).
  5. Add a confidence / sanity check: if date OCR yields a weekday/month inconsistency or an obvious digit near punctuation, retry with preprocessing.
- **Uncertainties flagged**: I cannot see the actual extraction code (not supplied); the above is inferred from predictions + OCR trace. If the current code already implements "last match wins", the OCR itself must be strengthened instead.

## w0011
## Summary of failures (from field_feedback)
- 034.jpg: date wrong (predicted 2018-08-09)
- 074.jpg: amount wrong (predicted 702.00)
- 077.jpg: amount wrong (predicted 23.26)
- 078.jpg: amount wrong (predicted empty string "")
- All other 18 receipts: both fields correct.
- Reward 0.909 field-level / 0.818 joint — the pipeline is close; failures are localized, not systemic.

Termination metadata: `max_iterations` at 65, `acp_stop_reason=max_turn_requests`, `n_skill_invocations=0`. The agent never invoked `image-ocr` — it hand-rolled `extract.py` (seen in m0021/m0022) and spent 22 `think` + 27 `terminal` + 16 `file_editor` calls iterating on heuristics. It ran out of budget before stabilising the last few edge cases.

## Per-failure causal analysis (new evidence from image pixels)

**034.jpg — date=2018-08-09 (wrong)**
Image clearly shows `Date: 09/03/2018` (9 March 2018 → expected 2018-03-09). The OCR mangled "03" → "08"; the agent's own think log (m0018/m0019) already recorded its belief as `date=09/08/2018`, so this is an OCR fidelity bug on the date cell, not a parser bug. Evidence: thin typewritten "03" on that receipt row is low-contrast; Tesseract's default `--psm 3` misreads the middle digit. No preprocessing was applied before OCR in `process_image()` (m0021). A targeted re-OCR of the date line (grayscale + autocontrast + `--psm 7` / `digits` whitelist) would likely recover `03`. Note: the amount (332.30) was correctly extracted — the receipt-text algorithm itself is fine here.

**074.jpg — amount=702.00 (wrong; truth visible as 102.00)**
Image shows: `Subtotal: 102.00`, `Total Excl. of GST 96.23`, `Total Incl. of GST 102.00`, `Total Amt Rounded 102.00`, `Payment: 102.00`. OCR turned "Total Incl. of GST 102.00" into `Total inel. of GBT 702.00` (1→7 digit substitution). The parser's fallback chain then picked priority-4 `TOTAL` on that line and returned 702.00. The adjacent "Total Amt Rounded" line was OCR-mangled to "Toial Amt Rounded oO yo2.00" and did not match `\bTOTAL\b`. Fix ideas: (a) when multiple TOTAL-family candidates exist, prefer the median/modal value if several lines agree (102.00 appears in Subtotal, Payment, Rounded); (b) cross-validate against Subtotal — if the candidate differs from Subtotal by >>GST (e.g. 702 vs 102), downgrade. Also, allowing fuzzy matches `Toial/Tolal/Tota1→TOTAL` would have let "Total Amt Rounded" win.

**077.jpg — amount=23.26 (wrong; truth is 23.25)**
Image shows the keyword structure:
```
Total (Excluding GST):   21.30
Serv. Charge (3%):        0.65
GST payable (6%):         1.31
Total (Inclusive of GST): 23.26
Rounding Adj:            -0.01
TOTAL:                   23.25        ← final, large-font
```
Expected is 23.25 (after rounding), but the parser picked 23.26 ("Total (Inclusive of GST)"). The agent's priority-4 "last candidate" rule stopped at `Total (Inclusive of GST)` because the large final `TOTAL: 23.25` either wasn't captured (large font, bold, mis-recognized as `TOTAL: 23. 25` or OCR confused by the colon/box glyphs) or was captured but preceded by `Rounding Adj` which is NOT in the exclusion list. Fix: when `Rounding Adj(ustment)` line appears, the *following* TOTAL line should take precedence (the "rounded total" pattern). Also, add `Total Rounded`, `Rounded Total`, `Total After Rounding`, `TOTAL:` as a higher-priority tier than `Total (Inclusive of GST)`.

**078.jpg — amount="" (wrong; truth is 92.80)**
Image is a Thai Delicious Restaurant receipt showing `Total: 92.80` and `Grand Total: 92.80` (GRAND TOTAL is priority-1). The agent's trace at m0026 shows 078.jpg correctly returning `92.80` in an earlier run. Yet the final delivered cell is **empty string ""**, not `92.80` and not even `None`. Two sub-causes are possible:
  1. A later iteration of the script regressed (perhaps added a filter like "only if numeric prefix"), causing GrandTotal line to drop out; **and/or**
  2. The write step converted `None` to `""` instead of leaving the cell blank/null. Task spec requires `null` for missed extraction; the verifier compares cell strings exactly, so `""` ≠ `"92.80"` and also ≠ null oracle cell. This is both an extraction regression and a null-encoding bug.

## Themes for Momentum / Patcher stages

1. **Null encoding discipline.** The code in m0021 appends `total_str = None` when not found — but something in later iterations (not visible in this window) must be writing empty strings. Ensure `ws.append([fn, date or None, total or None])` and never substitute `""`. This single fix could recover 078.

2. **Priority tier ordering should surface "rounded/final" totals.** Add a new tier ABOVE `TOTAL`:
   - `TOTAL ROUNDED`, `ROUNDED TOTAL`, `TOTAL AFTER ROUNDING`, `TOTAL AMT ROUNDED`, `GRAND TOTAL`
   This directly fixes 077 and strengthens 074.

3. **"Rounding Adj(ustment)" as a positional signal.** If a line matching `rounding\s+adj` is found, prefer TOTAL-family matches that appear *after* it.

4. **Digit-substitution tolerance for OCR.** Common misreads: `7↔1`, `0↔O↔o↔u`, `8↔3↔5↔B`, `l↔1`, `Tolal/Toial/Tota1↔Total`, `RN↔RM`, `GBT↔GST`. A conservative pass that runs OCR number tokens through a "confidence by neighbour-agreement" rule (Subtotal 102, Payment 102 ⇒ pick 102 over 702) would fix 074. Do not do blind substitution — use it only as a tie-breaker.

5. **Date OCR hardening.** The `034` date failure is a Tesseract digit misread, not a regex failure. Momentum should at least try a second OCR pass on the date region with `--psm 7 -c tessedit_char_whitelist=0123456789/-.` and compare; if two passes disagree, abstain (null is better than wrong). Original Skill `image-ocr` already documents a multi-pass strategy that was never invoked here (`n_skill_invocations=0`).

6. **Skill invocation gap.** The agent reinvented OCR instead of using the provided `image-ocr` skill. The current-candidate Skills bundle is unchanged from the original and still contains the multi-pass OCR example and preprocessing recipes that would have shortened debugging and avoided the iteration-limit timeout. Momentum should make the task-agent explicitly invoke `image-ocr` (or embed its multi-pass code) rather than compose ad-hoc OCR again.

## Uncertainty / things I could not verify
- I could not read the final `stat_ocr.xlsx` cell values directly (access denied), so the "empty string vs null" distinction for 078 is inferred from the predictions JSON showing `"total_amount": ""`; whether that is a serialization artefact of the exporter or a genuine `""` cell is not fully certain, but either way the delivered cell does not equal the oracle string.
- For 077, whether the large `TOTAL: 23.25` line reaches the OCR text at all is unknown without rerunning Tesseract; the fix should both widen keyword coverage AND use the Rounding-Adj positional heuristic so the result is robust to either OCR outcome.
- I did not inspect iterations beyond m0028 in this window, so the exact regression path that produced `""` for 078 is reconstructed from endpoint evidence, not traced.

## w0012
## Window 12 new evidence

This window captures the executor's mid-run OCR experiment on 10 receipts with `convert('L') + ImageOps.autocontrast + PSM 6/4/11`. The dumped lines are highly informative because they show, for most failing receipts, that the *correct* total is clearly recoverable with preprocessing + PSM 6 — meaning the failures were algorithmic/selection choices, not fundamentally un-OCRable images.

Key new signals from the OCR dumps (preprocessed PSM 6 unless noted):

- **074.jpg**: `'Subtotal : 102.00'`, `'Total incl. of GST 102.00'`, then a garbled `'Total Amt Rounded ——S«702.00'`, `'Total tem(a) 24'`. The *correct* 102.00 appears and the "Rounded"-line's `702.00` is pure OCR corruption of `102.00` (leading `S«` eaten by the regex). Also matches image "Total incl. of GST 102.00" / "Total Amt Rounded 102.00".
- **011.jpg**: `'TOTAL 15.00'`, `'DATE: 15/06/2017'` — both unambiguous. The r003 prediction (15.00, 2017-06-15) is already correct per feedback.
- **063.jpg / 064.jpg**: Date line parses as `26/02/18` / `21/02/18`; totals `85.54` / `88.17`. Both r003 outputs match these, so no residual failure here.
- **009.jpg**: `'Total Rounded 26.60'` + `'18/01/2018'` — correct.
- **083.jpg / 094.jpg / 087.jpg / 088.jpg**: all cleanly show the right total and date.
- **077.jpg**: three distinct lines — `'Total (Excluding GSI): 21,30'`, `'Total (Inclusive of GST): 23.26'`, and a large `'TOTAL: 23.25'` (after Rounding Adj −0.01 as the image confirms). R003 wrote `23.26`; feedback marks amount incorrect → oracle very likely wants `23.25` (the final "TOTAL:" row after rounding).

The executor's own think-block at m0039/m0045 explicitly diagnoses the tier-4 selection bug: last-candidate with a decimal wins, even when earlier candidates are obviously the real total. Their intended fix (iterate in reverse, skip non-decimal matches like "Total Item(s): 4", add exclusions for ITEM COUNT / TOTAL QTY / TOTAL SAVINGS, prefer PSM 6 preprocessed OCR) is only *started* in this window (m0051 adds those exclusion patterns) and never reaches a re-run that converges before `termination_reason: max_iterations` (65 iterations exhausted).

## Causal mapping to the four failed fields

Feedback table (reward 0.909; 4 wrong fields):

1. **074.jpg amount = 702.00 (wrong)** — classic last-decimal-in-tier bug. Image clearly shows `Total incl. of GST 102.00` / `Total Amt Rounded 102.00`; OCR corrupts the rounded line to `S«702.00` and the `\bTOTAL\b` priority-4 match takes the *last* decimal candidate. Window 12 proves PSM 6 preprocessing already surfaces a clean "Total incl. of GST 102.00" line, but the submitted pipeline (a) wasn't switched to preprocessed PSM 6 before termination, and/or (b) still used last-candidate selection.
2. **077.jpg amount = 23.26 (wrong)** — Image shows big `TOTAL: 23.25` as the authoritative receipt bottom line (Rounding Adj −0.01 applied to 23.26). R003 selected the pre-rounding line. Fix path: add a tier between priority-2 and priority-4 for a bare "TOTAL:" / "TOTAL RM" footer line that appears *after* all other totals, or prefer the very last decimal-bearing line matching plain `TOTAL\s*:` when a Rounding-Adj line is present.
3. **078.jpg amount = "" (wrong/missing)** — Image (Thai Delicious) shows clear `Grand Total : 92.80` (priority 1 keyword `GRAND TOTAL`). R003 wrote empty. Window 12 did not exercise this file, so uncertainty is highest here, but hypotheses: (a) raw (unpreprocessed, default PSM 3) OCR split `Grand Total` across lines or mis-read as `Grani Total` / `Grand Totai` causing the `\bGRAND\s+TOTAL\b` regex to miss; (b) `extract_last_number` on `92.80` failed because of a stray glyph. Priority-1 falling through all tiers with no fallback → None → "". The window's ongoing refactor to PSM 6 + autocontrast would very likely rescue this receipt, as 078 is a clean print.
4. **034.jpg date = 2018-08-09 (wrong)** — Image "Date: 09/03/2018" (DD/MM/YYYY) → oracle 2018-03-09. R003's 2018-08-09 does not match 09/03 under either MM/DD or DD/MM; it looks like the date parser latched onto a non-date token (e.g., receipt ID `CS00084670` — digits `0008`+time `08:49:00`, or `A03041` handwritten header) and formatted spuriously. This window did not inspect 034, so cause is inferential only.

## Momentum / Patcher guidance

Evidence-backed changes the Patcher should encode:

- **Preprocess every image** with `convert('L') + ImageOps.autocontrast`, then run Tesseract with `--psm 6` as primary (window shows PSM 6 is strictly better than default PSM 3 on 074, 011, 077, 083, 087, 088, 094, 064). Keep PSM 4 as secondary.
- **Selection rule rework** (priority 4):
  - Iterate matches in receipt order; skip candidates whose `extract_last_number` is `None` (so "Total Item(s): 4" doesn't poison fallback).
  - If multiple decimal candidates exist in tier 4, prefer the one matching `ROUNDED TOTAL`, `TOTAL ROUNDED`, `NET TOTAL`, `TOTAL AFTER (ADJ|ROUNDING)` patterns, else the one closest in value to a nearby Subtotal, else the last.
  - Drop the "look at next non-excluded line" fallback *past* a GST-summary line (that's what injected 96.23 for 074 earlier in the trace).
- **Exclusion additions** (already drafted at m0051): `TOTAL\s+(ITEMS?|QTY|QUANTITY|SAVINGS?)`, `ITEM\s+COUNT`.
- **"TOTAL:" footer handling** for 077: if the line is just `TOTAL\s*:` with a decimal and a Rounding-Adj line precedes it, treat as highest-priority answer (post-rounding final).
- **Date parser**: always prefer a line prefixed by `Date\s*[:\-]`; interpret `DD/MM/YYYY` for Malaysian receipts; reject tokens with fewer than two slashes/hyphens or embedded in colon-separated time components. This would correct 034 regardless of PSM.

## Uncertainty

- I have not read `extract.py`'s final state, so I cannot confirm which fixes were actually in the shipped binary vs. only brainstormed. The run ended at max_iterations, so the written code may be partially updated (m0051 exclusion edits were applied) but likely never re-executed against all 22 images.
- 078's failure mode is inferred; no OCR dump exists in this window to confirm whether `Grand Total` was mis-read.
- 077 oracle value (23.25 vs 23.26) is inferred from the feedback "amount incorrect" + image inspection; the diagnosis assumes 23.25.

## w0013
## New evidence in this window (w0013)

The window captures the agent's final structural changes to `extract.py`:

1. **`extract_total` rewrite (m0054–m0056)**: added a `SUMMARY_HEADER_RE` cutoff so GST/TAX-SUMMARY lines are excluded, and now iterates tier-matching candidates **in reverse** (last-matching line first), with an optional next-line fallback.
2. **`process_image` → `ocr_variants` (m0057–m0059, m0078–m0080)**: switched from a single preprocessed OCR pass (grayscale + autocontrast + `--psm 6`) to yielding **two variants** — default OCR first, then preprocessed `--psm 6` — using "fill the first non-None field found" semantics.
3. **Direct OCR dumps for the six problem receipts (m0068, m0074)** show *exactly* which lines each variant produces for 034/052/071/074/077/078.

## Why each failing field failed

Combining this window's OCR dumps with the field feedback (`034.jpg` date✗, `074.jpg` amount✗, `077.jpg` amount✗, `078.jpg` amount✗) and the image pixels:

### 034.jpg date → `2018-08-09` (wrong)
Image prints `Date: 09/03/2018` (I can see the "3" clearly in the pixel block). The **preprocessed** PSM-6 pass in m0068 correctly produces `'Salesperson: Date: 09/03/2018'`. The **default** pass in m0074 produces `09/08/2018`. Because `ocr_variants` runs default first and sets `date` on the first non-None hit, the wrong default date is "locked in" and the preprocessed variant is never consulted. Short-circuit-on-first-non-None is the root cause here, not the date regex.

### 074.jpg amount → `702.00` (wrong)
Image shows `Total incl. of GST 102.00`, `Total Amt Rounded 102.00`, `Payment: 102.00`. Default OCR mangles the key line to `Total inel. of GBT 702.00`; preprocessed OCR produces both `Total incl. of GST 102.00` **and** a garbage line `Total Amt Rounded ——S«702.00`. The new "last candidate wins, iterate reversed" logic picks the LAST `TOTAL`-matching line in each variant:
- default variant: only `Total inel. of GBT 702.00` matches → 702.00
- preprocessed variant: last match is `Total Amt Rounded ——S«702.00` → 702.00

Both variants independently return 702 for different reasons. The agent's own think-trace (m0075) notes "`——S«702.00` has a weird `——S«` which suggests OCR corruption" but no cleanliness penalty was ever implemented. Nothing in the code cross-checks `Subtotal`, `Payment`, or the GST-summary math (`96.23 + 5.77 ≈ 102.00`) to reject 702.

### 077.jpg amount → `23.26` (wrong)
Image shows: `Total (Inclusive of GST): 23.26`, `Rounding Adj: -0.01`, **`TOTAL: 23.25`** (large bold). Preprocessed OCR in m0068 does recover the final `'TOTAL: 23.25'` line; default OCR in m0074 does **not** — it stops at `'Total (Inclusive of GST): 23.26'`. Because default runs first and returns a non-None 23.26, `ocr_variants` never falls back. Same short-circuit bug as 034. If preprocessed had been consulted, its last-match-in-reverse rule would correctly land on `TOTAL: 23.25`.

### 078.jpg amount → `null` (missing)
Image clearly shows `Grand Total: 92.80`. m0068's preprocessed OCR for 078 captures it as `'{ Grand Total —— ~""92 80'` (the decimal was eaten by OCR — a space replaces the dot). The `extract_last_number` regex requires an explicit decimal point or a thousands-group pattern, so `92 80` doesn't match and GRAND TOTAL tier yields None. Fallback goes to the next line (`Cash Received 100.00`), but earlier agent output in m0062 showed `100.00`; the delivered output is empty, meaning a subsequent code change — the `SUMMARY_HEADER_RE` or the "break on exclusion" fallback path — now stops the walk before Cash is reached. Net effect: GRAND TOTAL line's number is unparseable AND the fallback got blocked, leaving null. The similar 052 case (`GRAND TOTAL 1000` in preprocessed → decimal lost) was patched by falling back to default, but 078's default OCR for Grand Total line is also missing the `.` (m0068 shows `'{ Grand Total —— ~""92 80'` only in preprocessed; default's "grand" line is not shown — suggesting default didn't even produce that line form, so no recovery).

## Structural failure modes for Momentum/Patcher

1. **First-non-None-wins across OCR variants** (m0078). This defeats the purpose of running multiple variants: whenever default returns a *plausible-looking but wrong* value (034 date, 077 amount), the better preprocessed pass is skipped. A voting/agreement strategy or collecting candidates from all variants and scoring them is needed.

2. **Last-match-in-reverse within a tier has no corruption filter**. For 074 the "Total Amt Rounded" line is visibly corrupted (`——S«`) and should be deprioritized versus the clean `Total incl. of GST 102.00` immediately above. No signal about line cleanliness or cross-line consistency is used.

3. **Decimal-separator loss not handled**. `extract_last_number` requires `\d+\.\d{1,2}` or grouped commas. OCR frequently drops the dot (`10.00`→`1000`, `92.80`→`92 80`). For lines that match a keyword tier, a loosened regex (e.g., accept `\d+\s?\d{2}` adjacent to a keyword and reinterpret as `XX.YY`) would recover 052 and 078 without poisoning the general path.

4. **GST-SUMMARY cutoff is correct direction but unrelated to these four failures**. The window's `SUMMARY_HEADER_RE` addition is defensible; the remaining errors are all **before** the summary section.

## Uncertainty

- I cannot see the oracle; I'm inferring expected 074=102.00 from the image's Subtotal / Total incl. of GST / Payment all agreeing on 102.00 and the GST math (96.23+5.77). Expected 077=23.25 is inferred from the large bold TOTAL line post-rounding.
- For 078, the feedback marks amount wrong given a null prediction; whether the oracle expects `92.80` (image's Grand Total) is the natural reading but unverified.
- The 034 preprocessed pass reading "09/03/2018" matches the image pixels, so the date fix direction (prefer preprocessed, or merge candidates) is well-supported.

The Patcher should focus on: (a) replacing "first non-None" variant selection with candidate aggregation+scoring, (b) adding a decimal-recovery fallback for keyword-matched integer blobs like `1000`/`92 80`, and (c) a mild corruption penalty (e.g., ratio of non-alphanumeric glyphs on the candidate line) so clean `Total incl. of GST 102.00` outranks `Total Amt Rounded ——S«702.00`.

## w0014
## Window-scoped evidence (w0014, m0080–m0114)

This window captures the executor's final refinement loop. It shows the script reaching the exact state that was shipped (via m0083 / m0092 outputs matching the delivered predictions), and the trajectory then exploring upscaled OCR but never adopting it.

### Field-feedback failures (4 incorrect fields on 3 receipts)

1. **034.jpg — date wrong** ("2018-08-09" vs image).
   Image 034 shows a crisp printed `Date: 09/03/2018`. The executor's selected OCR variant misread the slim `3` as `8`, yielding `09/08/2018` → ISO `2018-08-09`. This window never surfaces 034 as a date concern; the fix was never attempted. Amount (332.30) is correct — only the date digit lost.

2. **074.jpg — amount wrong** ("702.00" vs 102.00 in image).
   Image 074 clearly shows `Subtotal: 102.00`, `Total incl. of GST 102.00`, `Total Amt Rounded 102.00`, `Payment: 102.00`. In m0098/m0110/m0113 the executor demonstrated that a 2× upscale + autocontrast + PSM 6 yields correctly "`102.00`" on every Total line; default (unscaled) OCR consistently merged the vertical bar of "1" with noise into "7", producing `702.00`. The executor diagnosed this (m0099, m0105, m0114) but, as m0083/m0092 outputs show, the shipped `extract.py` still uses only (default OCR + autocontrast PSM 6), not the upscaled pass. Hence "last tier-4 match" picks the `Total Amt Rounded 702.00` line.

3. **077.jpg — amount wrong** ("23.26" vs likely 23.25 final).
   Image 077 contains three Tier-4 ("TOTAL") candidates in reading order: `Total (Excluding GST): 21.30` → `Total (Inclusive of GST): 23.26` → `Rounding Adj: -0.01` → `TOTAL: 23.25` (bolded final). The executor added an "EXCLUDING" exclusion (m0102) which correctly skips 21.30. In the OCR variant actually shipped, the bold `TOTAL: 23.25` line was either missed or its number was tokenised differently (upscaled PSM 6 in m0113 shows both `23.26` and `23.25`). "Last candidate wins" with the upscaled text would select `23.25`; with the non-upscaled text, only `23.26` survives, so `23.26` gets picked. Root cause: shipped OCR did not capture the final `TOTAL: 23.25` line.

4. **078.jpg — amount empty**.
   Image 078 shows `Total : 92.80` and `Grand Total : 92.80` as right-aligned amounts. Upscaled OCR in m0113 reveals the split-line failure: `: Grand Total` is extracted with the number stripped onto a neighbouring visual row. The executor's own early OCR (m0083) in fact produced `78.jpg … total=92.80`, but this was overwritten later when the `NUM_RE` was tightened to `\d+\.\d{2}` (m0087). That regex change eliminated any 92.80 candidate that lost a decimal in the particular OCR pass used for the final run, and no split-line fallback (the task hint's "last number on the next line" rule) was implemented. The shipped amount is empty.

### Shared causal pattern

All four failures trace to a single architectural choice: the executor settled on one preprocessing pass (default + autocontrast PSM 6) with a "last-candidate-in-highest-priority-tier" selector, and never integrated the alternative passes (upscale 2×, PSM 4, PSM 11, inverted) that m0098/m0110/m0113 proved recover 074, parts of 077, and the date digits of 034. The thinking in m0114 explicitly proposed a multi-variant consensus but that patch was not applied before the budget ended (termination_reason=max_iterations, acp_stop_reason=max_turn_requests).

Secondary contributing rule changes visible in this window:
- m0087 strict 2-decimal `NUM_RE` fixed 064 (88.17) but made the pipeline brittle to any OCR variant that drops a decimal (contributed to 078 emptiness).
- m0102 added `EXCL(?:UDING|\.)` exclusion — a correct generalisation; keep it.
- No split-line fallback (task hint, bullet "fallback for receipts where the keyword and the numeric amount are split across two lines") was ever implemented — this is the sole gap for 078.

### Evidence quality / uncertainty

- Images confirm: 034 date is `09/03/2018`; 074 total is `102.00`; 078 Grand Total is `92.80`.
- 077 ambiguity: oracle value not visible; feedback alone says 23.26 is wrong, and the receipt's visually dominant bolded `TOTAL: 23.25` is the most plausible gold (post-rounding-adjustment final).
- The upscaled OCR itself regressed some fields (010, 064, 090 in m0113). Blind switch would trade errors. A **multi-variant consensus** (tier-priority → agreement count → 2-decimal precision → source priority) is the robust choice and is required for both 034 (digit reliability) and 074/078 (coverage).

### Guidance for Momentum / Patcher stages

Momentum should flag:
1. Shipped script uses a single OCR pass; proven-better variants exist in the same workspace experiments.
2. No two-line split fallback — explicit gap vs. task prompt hint.
3. Date extraction has no consensus or plausibility check; a single misread digit silently wins.

Patcher should:
- Run ≥3 OCR variants (default, upscaled-2×-autocontrast-PSM6, autocontrast-PSM4) and take a tier-aware consensus for `total_amount`.
- For dates, parse all candidates across variants; prefer values whose month ∈ 1..12 and whose digits agree across ≥2 variants.
- Implement the split-line fallback: if a keyword line matches but contains no 2-decimal number, use the last `\d+\.\d{2}` on the next non-empty line.
- Keep the `EXCLUDING` exclusion (m0102) and the strict 2-decimal `NUM_RE` (m0087), but allow the fallback to loosen to "last number" per task hint.
- Do not alter the XLSX schema; current column/order/format is accepted by the delivered run.

Uncertainty: oracle values for 077 and the exact gold date format for 034 are not accessible; fixes above follow pixel evidence and the task prompt's keyword-priority specification.

## w0015
## New evidence in this window (w0015)

The source agent was experimenting with a 3-variant OCR pipeline (default, grayscale+autocontrast PSM 6, 2x upscale PSM 6) combined with tier-priority majority voting. The trajectory shows this change produced **regressions** that the agent was still debugging when the run hit `max_iterations` (65/65, `termination_reason: max_iterations` — not natural completion). This is therefore a partially-finished intermediate state, not the agent's final design.

### Specific failure mechanisms visible in this window

**074 — amount 702.00 (feedback: wrong; image shows 102.00)**
Debug output in m0131 shows:
- Variant 0: `'Total inel. of GBT 702.00'` → 702.00
- Variant 1: `'Total Amt Rounded ——S«702.00'` → 702.00
- Variant 2: `'Total incl. of GST 102.00'` → 102.00

Two low-quality variants hallucinated the digit "7" from garbled rounding-row characters (`S«`, `inel`). Majority vote (2 vs 1) locked in the hallucinated 702.00 at tier 3. Majority voting across OCR variants is unsafe when the same hallucination occurs in multiple passes.

**064 — amount 688.17 (feedback originally 88.17 was correct; new code worsened it)**
Debug m0137 for variant 2 shows:
```
Total RM = B81?
Visa RM =688.17
Total Gross C RM 86.17
```
The TOTAL-RM-tier candidate line `"Total RM = B81?"` contains no parseable 2-decimal number, so the fallback walks to the next non-empty line `"Visa RM =688.17"`. VISA is not in the exclusion keyword set (`SUBTOTAL/SUB TOTAL/TAX/GST/SST/DISCOUNT/CHANGE/CASH TENDERED`), so the fallback accepts 688.17. This same bug would strike any receipt where OCR mangles the TOTAL line and a VISA/Mastercard/payment line immediately follows (very common on petrol receipts — 064, 019, 087 share this template).

**078 — amount "" (feedback: wrong; image shows 92.80)**
In the original run the default OCR read `"a Total — 92:80"` and `"GrandTota. = tS 92.80"`. The colon in `92:80` fails the `\d+\.\d{2}` regex; `GrandTota.` fails `\bGRAND TOTAL\b`. New voting (m0125) shifted the answer to 100.00 because the upscaled variant's Grand Total line had no number and fallback jumped to `"Cash Received 100.00"` — again VISA/CASH-RECEIVED gap in exclusions (`CASH TENDERED` is specific, doesn't catch `Cash Received`).

**077 — amount 23.26 (feedback: wrong; image shows final `TOTAL: 23.25` after rounding)**
Debug m0131 confirms the receipt has both `Total (Inclusive of GST): 23.26` and a later `TOTAL: 23.25`. Default OCR misses the final TOTAL line entirely (noise merged it into the GST summary). The original run picked the earlier tax-inclusive subtotal; the new voting correctly identified 23.25 in two variants but this was never persisted — the run terminated before validating. The agent even reasoned (m0126) that 23.25 is the true printed final after rounding adjustment.

### Date failure

**034 — predicted 2018-08-09 (image shows `Date: 09/03/2018`)**
The source think log earlier in the run noted "date `09/08/2018` ✓" — OCR misread the single `3` as `8`. Downstream DD/MM/YYYY parsing then gave 2018-08-09. This is a single-digit OCR confusion (3↔8) on a clean printed date; no logic fix would help unless an alternate OCR variant disagrees. The voting strategy in this window does include date voting (`pick_best_date`), which is the right architectural direction — but all three variants likely read the same wrong digit on a confident glyph.

### Structural observations

1. **Exclusion keyword list is incomplete.** The receipts repeatedly fall into payment/change rows after a mangled total: `Visa RM`, `Cash Received`, `Mastercard`, `Payment`. The current list only catches `CASH TENDERED` and `CHANGE`. Adding `VISA`, `MASTERCARD`, `CASH RECEIVED`, `PAYMENT` as exclusions (or more generally, refusing fallback onto payment-instrument lines) would block the 064 and 078 regressions.

2. **Fallback-to-next-line is too eager.** When the keyword line has no number, walking to the next line only makes sense for genuinely wrapped layouts. For petrol receipts the next line is always a payment row. Gating the fallback on "next line doesn't itself contain a total/tier keyword that would have been matched independently" would help.

3. **Majority voting without consensus confidence is dangerous.** Two garbled OCR passes can agree on the same hallucinated digit (074: 702.00 twice). A safer rule: prefer the variant whose extracted value also matches an obvious consistency check (e.g., equals Subtotal+rounding, equals the Cash − Change arithmetic, appears as the LAST monetary line before the GST summary). The source already has `find_summary_start` — it could be leveraged to prefer "last candidate immediately above summary_start".

4. **Upscaling is a net negative for crisp receipts.** 064 and 090 degraded under 2x LANCZOS+autocontrast because tesseract over-segmented sharp glyphs. Upscaling should only be applied conditionally (e.g., when the default pass gives low confidence, or when it yields no tier-matching candidates).

### Evidence boundaries / uncertainty

- Field-level feedback confirms exactly which 3 amounts (074, 077, 078) and 1 date (034) are wrong; I cannot see gold values, so for 077 I infer 23.25 from the printed rounding math visible in the image and from the agent's own reasoning.
- Prior method history is empty — this is the first repair window, so Momentum has no earlier Skill edits to continue.
- The source Skill text is marked `same_text_as_original`; the agent's experimental voting code lived in `/app/workspace/extract.py`, not in the Skills. The repair should decide whether to encode the fallback/exclusion fixes as Skill guidance or leave them to executor code.
- The source run was budget-terminated, so the regressions listed above (e.g. 064→688.17) exist in the delivered predictions but were not the agent's intended final state. Reward 0.0 here reflects the task's binary scoring; derived per-field accuracy is 0.909 (40/44).

### Recommendations for Momentum / Patcher

- Patcher should extend the exclusion set to cover payment-instrument and received-cash lines (`VISA`, `MASTERCARD`, `CASH RECEIVED`, `PAYMENT`) and tighten fallback to avoid payment rows.
- Prefer "last tier-matching candidate above the GST/tax summary" over variant-majority voting; use voting only as a secondary tiebreaker.
- Keep multi-pass OCR but apply upscaling conditionally (only when default returns no tier match), to avoid 064-style regressions.
- For `078`-style `Grand Total` lines with colons/noise, normalize `:` between digits to `.` before regex extraction (handles `92:80`).
- Date parsing is largely fine; 034 is an OCR glyph confusion that no logic layer can safely correct without a second disagreeing variant.

## w0016
## New evidence in this window (messages m0141–m0169)

This window captures the agent's 064 debug + first vote fix, then surfaces the stuck-state of the four remaining errors. Termination was `max_iterations` (65/65) with `acp_stop_reason=max_turn_requests` — the budget ran out **mid-iteration on the 078 issue**, with no final re-save after the last mutation. The submitted xlsx is the last `extract.py` run output captured just before exhaustion.

### Confirmed fix inside the window
- **064 (Visa RM = 688.17 bug)** — Traced in m0141–m0152. On variant 2, OCR produced `Total RM = B81?` (digits present but unparseable). The previous split-line fallback walked to the next non-empty line `Visa RM =688.17` and returned 688.17 at tier-1 (TOTAL RM), outranking tier-3 `Total Gross C RM 86.17` → 88.17. The agent added the guard "fallback only if the keyword line has no digits" (m0147), and 064 now extracts 88.17. This is a real, correct repair and is preserved in the delivered xlsx.

### Remaining failures (with image-level evidence)

**074.jpg — amount 702.00 should be 102.00 (image: GL HANDICRAFT & TAILORING).**
Receipt shows `6.00 BOXS × 17.00 = 102.00`, `Subtotal 102.00`, `Total Incl. of GST 102.00`, `Total Amt Rounded 102.00`, `Payment 102.00`. OCR on 2 of 3 variants misread the leading `1` of `102.00` as `7` on the "Total Amt Rounded" line. The new "collect candidates from all variants, pick highest tier, then **majority vote within tier**" logic (m0156–m0160) deterministically picks 702 (2 variants) over 102 (1 variant). Evidence: m0167 still shows `074.jpg: total=702.00` after the voting switch. The heuristic is biased: it ignores the fact that 102.00 appears **4× in the same OCR text** on supporting lines (Subtotal/Total Incl./Rounded/Payment) while 702.00 appears only at one line. Tie-breaking by raw across-variant count is wrong when a value is confirmed by multiple non-tier lines in a single variant.

**077.jpg — amount 23.26 should be 23.25 (image: Banh Mi CafE).**
Receipt layout: `Total (Inclusive of GST): 23.26`, `Rounding Adj: -0.01`, `TOTAL: 23.25`. Both `Total (Inclusive of GST)` and the bold `TOTAL:` match tier 3 (TOTAL). With the new `extract_total_candidates` returning matches `reversed(matches)` (latest first), the final `TOTAL: 23.25` should come first. But m0167 shows `23.26`, meaning either (a) OCR variants placed `Total (Inclusive of GST)` after `TOTAL:` in reading order, or (b) the `TOTAL: 23.25` line's number was OCR-corrupted and the fallback produced 23.26 from a neighboring line, or (c) `find_summary_start` truncated past the bold TOTAL. The vote across all three variants then concentrates on 23.26 because every variant's `Total (Inclusive of GST)` line is reliably parsed, while the bold `TOTAL: 23.25` often gets mangled (large bold font OCRs worse).

**078.jpg — amount missing/incorrect, correct value 92.80 (image: THAI DELICIOUS RESTAURANT).**
Receipt: `Total 92.80`, `Grand Total 92.80`, `Cash Received 100.00`, `Change 7.20`. The agent's own trace in m0168 shows all three OCR variants mangle this: variant 0 `a Total — 92:80` / `GrandTota. = tS 92.80`, variant 1 `{ Grand Total —— ~"92 80`, variant 2 `: Grand Total` (no number). The tier-0 regex `\bGRAND\s+TOTAL\b` fails on `GrandTota.` (no space + truncation). After the m0162 exclusion of "Cash Received", the previous 100.00 fallback is suppressed, but then the vote finds 20.00 (m0167) — likely from `Average/Pax(S): 23.20` or a stray OCR number matching TOTAL. The submitted xlsx shows `""` for 078, so the window's final save after this mutation never happened before max_iterations fired.

**034.jpg — date 2018-08-09 should be 2018-03-09 (image: PERNIAGAAN ZHENG HUI).**
Receipt clearly prints `Date: 09/03/2018`. The agent parsed this as `2018-08-09` — the only way to arrive at month=08 is OCR misreading `03` as `08`, or a DATE_PATTERNS entry that accidentally matched `09/08/2018` from a different line (`08:49:00` time or `A03041` handwritten note). This window contains no 034-specific code change, so the bug is inherited from earlier windows and un-addressed before termination.

### Root causes handed to Momentum/Patcher

1. **Candidate-ranking logic is incomplete** (074, 077). The new majority-vote strategy added in m0156–m0160 doesn't use cross-line confirmation within a single variant. A better score would weight each candidate `(tier, value)` by how many **other total-adjacent lines** in the same OCR text share the same value. "Last match wins within tier" also needs to survive the `reversed(matches)` → vote pipeline; currently voting loses the positional signal.

2. **Keyword regexes are too strict for noisy OCR** (078). `\bGRAND\s+TOTAL\b` and `\bTOTAL\s*:?\s*RM\b` reject `GrandTotal`, `GrandTota.`, `Total: RM`, `Total Gross … RM`. Need tolerance for missing/extra whitespace and trailing punctuation while remaining excluded by SUB/CASH/CHANGE/GST patterns.

3. **Number parser rejects `92:80` / `92 80`** (078). `extract_last_number` only accepts `d+\.\d{2}` / `d,\d{3}\.\d{2}`. For images where the decimal point OCRs as `:` or space, a lenient fallback (only on keyword-matched lines, not globally) would recover 92.80 on 078.

4. **Date parser confuses DMY/MDY ambiguity** (034). With a locale of Malaysian receipts, DD/MM/YYYY is near-universal. The 034 output `2018-08-09` is inconsistent with this. Either the regex picked a different token (likely the time `08:49:00` consumed as a date), or an MDY pattern fired. Patcher should constrain to DD/MM/YYYY first, keep MDY only as a last fallback, and prefer the line nearest a `Date:` label.

5. **Max-iterations termination** — field_feedback shows reward 0.909 (40/44 fields). The source Agent never reached a clean "final save" after 078's experiments; subsequent would-be iterations would likely have regressed 078 further. Patcher must land fixes idempotently, not iteratively.

### Uncertainty
- I cannot see the exact `extract.py` file at termination, so whether `extract_total_candidates` in the delivered binary matches m0159 vs. some later edit is partly inferred from m0167's output pattern.
- For 034, "08" vs "03" distinction could be OCR noise (poor scan) rather than parser order; both regex ordering and OCR confusion fit the observed `2018-08-09`.
- For 077, I'm not certain whether the bold `TOTAL: 23.25` line was dropped by `find_summary_start` or just OCR-mangled; a Momentum probe of per-variant OCR text for 077 would disambiguate.
- Image inspection here does not prove the source Agent had vision; it ran text-only Tesseract.

## w0017
## Window w0017 (iterations around turns 57–65) — focused evidence

### What happened in this window
The source agent was debugging `078.jpg` after an earlier fix changed its output from `20.00` (wrong) to `None`. In this window:

1. **Trace of `078.jpg` variant 0** (m0176) revealed only tier-4 keyword hits:
   - Line 10: `"Description Qty Price Amount"` → `extract_last_number=None`
   - Line 31: `"a Total — 92:80"` → `None` (OCR produced `92:80` not `92.80`)
   - The prior fallback was chaining from line 10 (the column-header `Amount`) to line 11 (first item row) and yielding `20.00` — explaining the earlier incorrect `20.00`.

2. **Fix applied** (m0180): added exclusion regexes for header rows:
   - `\bDESCRIPTION\b`
   - `\b(QTY|PRICE)\s+AMOUNT\b`

3. **Rerun** (m0185): all 22 rows unchanged except `078.jpg` → `total=None`. Agent confirmed this is "better than 20.00" but still incorrect.

4. **Preprocessing probe** (m0191): tried 5 preprocessing variants × PSM {4,6}. Only `upscale 3x gray + PSM 4` produced the clean line `"Grand Total a 92.80"`. Other variants produced broken OCR (`92 80`, `92:80`, `SSCS 92.80`, `SRT`).

5. **Code change** (m0195): modified `ocr_variants` to add a 4th variant = 3×-upscale autocontrast gray with `--psm 4`, intended to let voting pick up the `92.80` candidate.

### Evidence relative to permitted feedback
The feedback for this run shows 3 amount errors: `074`, `077`, `078`. In this window the agent is focused only on `078`. There is no evidence here that `074` or `077` are being revisited; the pre-fix rerun output still shows their previous (wrong) values `702.00` and `23.26`. Looking at the image pixels for those receipts:
- **074.jpg** (GL Handicraft): `Total Amt Rounded 102.00`, GST `96.23`. Prediction `702.00` is clearly a misread of `102.00` from one OCR variant that merged `7`/`1` or picked a different line. Needs a direct look at variants; a new OCR voting pass could tip it to `102.00`.
- **077.jpg** (Banh Mi Cafe): The receipt shows `TOTAL: 23.25` (after `Rounding Adj -0.01` from `23.26`). Prediction `23.26` picks `Total (Inclusive of GST)` line instead of the final `TOTAL:` line. Priority tiers currently rank `TOTAL` equally; the final large `TOTAL: 23.25` is strictly later and should win via "last occurrence" or line-position bias. The current code is not preferring the final/below-rounding TOTAL. This is a priority/ordering bug, not an OCR bug.
- **078.jpg** (Thai Delicious): True value is `92.80` as agent discovered.

### Primary causal issues visible in this window
- **Pipeline design (candidate selection):** Priority tiers plus "reversed order" fallback are brittle around column headers and multi-TOTAL receipts. The new header exclusions help, but ordering across tier-4 keywords still mis-chooses between `Total (Inclusive of GST)` vs final `TOTAL`.
- **OCR robustness:** `GrandTotal` (no space) and digit/punctuation noise (`92:80`, `92 80`) defeats `\bGRAND\s+TOTAL\b` and the decimal regex. The 3×-upscale PSM-4 variant demonstrably recovers the number — adding it is a correct direction, but voting must prefer a Priority-1 (`GRAND TOTAL`) hit with a clean decimal over tier-4 hits with noise.
- **Termination risk:** Source run ended at `max_iterations=65` with termination_reason=`max_iterations`. This window is turns ~57–65, so the 3×-PSM-4 variant added in m0195 is near the end — subsequent windows should confirm whether any re-run completed and whether `074`/`077` were ever revisited before budget exhaustion.

### Uncertainty / open items for Momentum + Patcher
1. Did the final `ocr_variants` rerun actually fix `078` to `92.80`? Must check later windows — unclear whether vote picks `92.80` over `None` across 4 variants.
2. `074.jpg` `702.00` vs `102.00`: hypothesize a decimal-regex false match on OCR like `"702 00"` or `"7 102.00"`. No evidence here that the agent diagnosed it.
3. `077.jpg` `23.26` vs `23.25`: unclear whether the Patcher Skill should encode "prefer the last TOTAL line below Rounding Adj" or "prefer the largest/bottom-most tier-4 TOTAL".
4. The Skill documents (`image-ocr`, `openai-vision`, etc.) do not prescribe priority-tier/exclusion logic; all extraction logic lives in the ad-hoc `extract.py`. Patcher-side guidance should probably codify: (a) header-column exclusions, (b) multi-pass OCR including an aggressive upscale, (c) tie-breaking that prefers the physically lowest/last matching TOTAL line, (d) tolerant decimal reconstruction (`92 80` / `92:80` → `92.80`) only when a priority-1/2 keyword is on the same line.
5. Momentum should note: field accuracy 0.909, reward 0.0 due to exact-file comparison; the task fails binary even with 20/22 field-correct, so Patcher must raise joint accuracy, not just field accuracy.

## w0018
Source run hit max_iterations (65/65) with n_skill_invocations=0 — the image-ocr Skill's multi-pass preprocessing was never actually invoked; the agent hand-rolled single-pass Tesseract. Field feedback shows 4 errors out of 44: date 034, amounts 074/077/078.

1) 034.jpg date: printed `Date: 09/03/2018` (DD/MM, Malaysian). Predicted `2018-08-09`. Root cause: no locale-locked DD/MM parsing and likely 3↔8 OCR confusion from neighbouring `GA1801`/`GB1801` item codes. Needs explicit Malaysian DD/MM/YYYY normalization with sanity on month≤12.

2) 074.jpg amount: receipt shows 102.00 on five lines (line item, Subtotal, Total Incl. GST, Total Amt Rounded, Payment). Predicted `702.00`. Pure OCR "1→7" misread on one line, then first-keyword-match took the garbled token. Root cause: no cross-amount consensus voting across repeated monetary tokens on a single receipt.

3) 077.jpg amount: two TOTAL lines — `Total (Inclusive of GST): 23.26` and after `Rounding Adj: -0.01` the final `TOTAL: 23.25`. Predicted `23.26`. Root cause: greedy top-down keyword match ignores that the canonical grand total is the LAST TOTAL line following Rounding Adj / bare `TOTAL:` without parenthetical qualifier.

4) 078.jpg amount: null predicted. Receipt is wide-column tabular (`Total :` label left, `92.80` far-right under Amount header; `Grand Total : 92.80` likewise). Default PSM likely separated label and number across OCR rows, so same-line keyword scan found no number, and the task's "next line last number" fallback either wasn't implemented or landed outside range. Root cause: no column-based / wide-gap fallback, no PSM retry (--psm 6/4), no use of `image_to_data` TSV with line_num grouping.

Cross-cutting: the 18 correct rows show the base Tesseract + keyword pipeline is sound. Failures cluster in (a) date locale, (b) multi-TOTAL selection with Rounding Adj, (c) single-digit OCR noise without cross-validation, (d) wide tabular layout parsing. The Skill bundle itself describes multi-pass/preprocessing but was not invoked, and does not address Malaysian date locale, post-rounding TOTAL preference, consensus voting, or column-aware fallback. Momentum/Patcher should extend the method (not necessarily the Skill text) with: DD/MM-first date parsing, "last TOTAL after Rounding Adj wins", amount consensus across Subtotal/Total/Rounded/Payment, and a column/TSV-based fallback with PSM retries for wide tabular receipts.

Uncertainty: exact intermediate OCR strings aren't in this window; inferences for 074/034 are from predicted-value vs visible-pixel reasoning. 078's null could marginally be a write-step artifact but other 21 rows serialized fine, so extraction miss is overwhelmingly likely. 034 fix is highest-confidence; 077 fix is high-confidence; 074/078 fixes are medium-confidence pending verification that proposed heuristics don't regress the 18 passing receipts (notably 019 `86.00` fuel, 087 `538.00` IKEA where single clear TOTAL exists — safe), and don't over-trigger on receipts like 088 where two different items sum to 99.80 (consensus voting must be scoped to total-tier lines, not line items).

## w0019
## Scope / new evidence this window
This window shows exchanges e0001–e0015 (m0003–m0045): initial OCR exploration, construction of `/app/workspace/extract.py` (m0021), first full run (m0024 → implicit output in m0027 thought), several debugging passes, and the pivot in m0042/m0045 to preprocessed PSM 6. The actual extract.py code is now visible (Artifact m0021). All 22 source JPEGs are provided as image blocks, and permitted field feedback tells us exactly which 4 cells are wrong:

- 034.jpg: date wrong (predicted 2018-08-09)
- 074.jpg: amount wrong (predicted 20.00 — wait, predictions table says "702.00"… correction: predictions show 702.00 is NOT in table; 074.jpg has 702.00 total in predictions — actually table shows "702.00" for 074. Yes confirmed amount 702.00)
- 077.jpg: amount wrong (predicted 23.26)
- 078.jpg: amount wrong (predicted "" / empty)

## Image-grounded root causes

**074.jpg (amount 702.00 → wrong).** On the image the three total-area lines read "Total Excl. of GST 96.23", "Total Incl. of GST 102.00", "Total Amt Rounded 102.00", "Payment 102.00". Tesseract on raw image replaces the leading "1" of 102.00 with "7". The m0033/m0036 debug confirms extract_total matched a priority-4 TOTAL line and returned the number in that line. So the defect is purely OCR character confusion (1↔7), not the extractor. m0042+m0045 found that preprocessing (grayscale+autocontrast) + PSM 6 reads "102.00" correctly, but this fix was discovered late and never got applied to the delivered Excel because the run was terminated by `max_iterations=65` (termination_reason recorded). Fix: Patcher should make the default pipeline run preprocessing + PSM 6 (and optionally a second pass to confirm) rather than raw `image_to_string`.

**077.jpg (amount 23.26 → wrong).** Pixel inspection: receipt displays "Total (Inclusive of GST): 23.26", then "Rounding Adj: -0.01", then a large "TOTAL: 23.25". The post-rounding grand total is 23.25, not 23.26. In m0045 the agent explicitly saw PSM-6 OCR yielding both "Total (Inclusive of GST): 23.26" and "TOTAL: 23.25" and chose to prefer 23.26, calling 23.25 an OCR error. This was a semantic misjudgement, not an OCR failure. The extract_total already prefers the LAST matching line within a tier; keeping that rule would have given 23.25. Fix: respect the last TOTAL (post-rounding) match; don't second-guess it.

**078.jpg (amount empty → wrong).** Image clearly shows "Total: 92.80" then "Grand Total: 92.80". The m0018 analysis noted raw Tesseract output concatenates to "GrandTotal 92.80" (no space). Current regexes `\bGRAND\s+TOTAL\b` and `\bTOTAL\b` both fail on the single token "GrandTotal" (no word boundary inside, and GRAND\s+TOTAL requires whitespace). So extract_total returned None and the serializer wrote an empty cell. Two independent fixes are needed: (a) add a regex that tolerates missing whitespace (`\bGRAND\s*TOTAL\b` or match "GRAND TOTAL" after collapsing camel-case), (b) also match on "TOTAL" inside "GrandTotal" via a substring search as last resort. A fallback on "Total : 92.80" line immediately above would also rescue this — but OCR of 078 is noisy there too.

**034.jpg (date 2018-08-09 → wrong).** Image shows "Date: 09/03/2018". OCR misread "03" as "08" (0+3 running together). The code takes the first DD/MM/YYYY match. There is no second date on the receipt to cross-validate. This is pure OCR noise in the date digits; preprocessing + PSM 6 may help but is not guaranteed. Lower confidence fix.

## Extractor-logic observations (orthogonal to above)

- The GST-summary exclusion only matches a single line. For 071/074/034 the GST summary section has a "Total" row BELOW the "GST Summary" header. m0027 planned a "once a GST SUMMARY header seen, exclude all subsequent TOTAL candidates" rule but the Artifact extract.py shows this was never implemented. The predictions nevertheless came out right for 034 amount and 071 amount, so the current single-line exclusion happened to be enough on raw OCR — but it is fragile and may regress when preprocessing changes line layout.
- Total serialization: when `extract_total` returns None, the Excel cell is stored, and the predictions JSON shows it as `""`. The task says "null" for failed extraction, but the scored field_feedback treats `""` as present-and-wrong rather than missing. Patcher should decide whether to explicitly write None (openpyxl writes empty cell) — the current behaviour is already None; the downstream exporter is what stringifies. Low priority since only one field (078) is affected and the root cause is the extraction failure, not the null policy.

## Uncertainty

- I cannot see the oracle Excel. The 077 analysis above is based on reading the printed "TOTAL: 23.25" from the image; it is consistent with the feedback flag.
- For 074 I rely on the m0039 debug + image showing "102.00" in multiple lines; high confidence.
- For 034 the OCR confusion 03↔08 is likely but not directly observed in a quoted OCR dump in this window; medium confidence.
- Preprocessing (PSM 6 + autocontrast) was validated on 074/011/063/009/083/094/087/088/064 in m0042, so switching the default is low-risk. However it was never actually rolled out before `max_iterations` terminated the run — Momentum should note this as "known-good change discovered but unshipped".

## Signals for Momentum / Patcher

1. Replace raw `image_to_string(img)` with preprocessed (`convert('L')` + `ImageOps.autocontrast`) OCR at `--psm 6`, optionally combined with a second raw pass.
2. Make GRAND TOTAL / TOTAL patterns tolerate missing whitespace (handle "GrandTotal" OCR glom).
3. Keep "last candidate in tier" preference; do NOT override to prefer "Inclusive of GST" over a later bare "TOTAL" line (fixes 077 regression noted in m0045 reasoning).
4. Terminal state was `max_iterations` (65/65), so the source agent demonstrably had more work queued; Patcher needs to deliver a self-contained script rather than iterative debugging.
5. Skills (image-ocr, openai-vision) are generic; no receipt heuristics. Patcher's job is the extract.py layer, not the skill text, unless Momentum chooses to encode receipt-specific guidance in the image-ocr skill.

## w0020
## Scope
Field accuracy 40/44 = 0.909; original binary reward 0.0. Failures: `034` date, `074`/`077`/`078` amounts. All 18 other receipts correct. Termination = `max_iterations`, so the pipeline documented in m0048–m0066 (grayscale+autocontrast, PSM 6, reverse-candidate iteration, summary-section cutoff) is the last-applied version but tuning on these four was not completed.

## Receipt-level causes (new pixel evidence)

**034.jpg — date 2018-08-09 vs pixel `Date: 09/03/2018`.**
Image clearly prints `Date: 09/03/2018 08:49:00`. Correct DD/MM/YYYY = 2018-03-09. Agent's own think log (m0069) admits: "PSM 6 preprocessed gives 09/03/2018 … earlier default OCR gave 09/08/2018. Both plausible OCR interpretations." The delivered Excel still holds `2018-08-09`, meaning the shipped pipeline did NOT consistently use the preprocessed+PSM 6 pass for date extraction, OR a time fragment `08:49` is leaking into the date regex. The pixel `03` glyph is unambiguous; this is an OCR/parse regression, not a receipt ambiguity.

**074.jpg — amount 702.00 vs pixel `Total Incl. of GST 102.00` / `Total Amt Rounded 102.00`.**
Image shows `Subtotal 102.00`, `Total Excl. of GST 96.23`, `Total Incl. of GST 102.00`, `Total Amt Rounded 102.00`, `Payment 102.00`. The predicted 702.00 is an OCR hallucination on the last `Total Amt Rounded` line (m0063 confirms OCR saw `Total Amt Rounded ——S«702.00`). The new reverse-candidate strategy picks the LAST tier-4 match; because it is the LAST line and has a decimal, it wins against four earlier correct 102.00 lines. Cause: single-pass OCR + "last candidate" heuristic is not defended by cross-line majority voting.

**077.jpg — amount 23.26 vs pixel large `TOTAL: 23.25`.**
Pixel order on receipt: `Total (Excluding GST): 21.30`, `Serv. Charge (3%): 0.65`, `GST payable (6%): 1.31`, `Total (Inclusive of GST): 23.26`, `Rounding Adj: -0.01`, bold `TOTAL: 23.25`. The final rounded total is 23.25. Prediction 23.26 means the pipeline treated `Total (Inclusive of GST): 23.26` as the final rather than the bold `TOTAL:` line below it. Likely driver: the small OCR'd `TOTAL: 23.25` line is being treated as a duplicate and either skipped by an exclusion (none should fire), missed by OCR, or lost to reverse iteration that broke at the first decimal match in tier 4. Think log m0045 shows the agent anticipated 23.25 would be the "last" tier-4 candidate; the delivered Excel instead holds 23.26, so a later edit regressed the ordering (likely a change that prefers lines containing "Inclusive" / "GST" or stops at the first match from the top).

**078.jpg — amount null vs pixel `Total: 92.80` / `Grand Total: 92.80`.**
Image has clear `Total : 92.80` and `Grand Total : 92.80`; GRAND TOTAL is priority-1. m0063 notes intermediate output was 100.00 (Cash Received). Final null means one of the new filters is now over-excluding. Candidate causes: (a) the `SUMMARY_HEADER_RE` cutoff triggers too early because "Grand Total" appears below several keyword-like lines; (b) added exclusion `\bTOTAL\s+(ITEMS?|QTY|QUANTITY|SAVINGS?)\b` is fine, but the generic `\bTOTAL\s+(GST|TAX|SST)\b` plus the colon-/trailing-space variants may be eating `Total :` lines whose OCR appended stray tokens; (c) OCR produced `Total : 92 80` (space instead of dot) making `extract_last_number` return None on both the keyword line and its one-line fallback. Either way, the pipeline lost a receipt it was previously extracting.

## Cross-cutting evidence

1. Single-OCR-pass fragility: Thinking blocks (m0045, m0063, m0069) show the agent repeatedly discovered that default-PSM and preprocessed+PSM-6 disagree on 034/052/074/077/078 individually, but never combined passes. The committed code uses only preprocessed+PSM 6.
2. "Reverse iteration" (m0054) implicitly trusts that the last keyword line has the authoritative number. Pixel evidence for 074 and 077 shows this assumption flips in both directions: on 074 the earlier line is correct; on 077 the later bold `TOTAL:` is correct.
3. Summary-section cutoff (`GST SUMMARY`, `TAX CODE`) added in m0054 solved 034-style over-matching but may be truncating 078's candidate region if a stray "Tax" token appears above `Grand Total`.
4. Max-iterations termination means the four receipts above were still "open" when the loop ended; the agent's own notes (m0063) list them as known failures.

## Guidance for Momentum / Patcher stages

Needed Skill/code changes (do not implement here):

- Multi-pass OCR + aggregation. Run (a) default PSM 3 on raw image, (b) grayscale+autocontrast PSM 6, (c) PSM 4, then for each priority tier collect numeric candidates across passes and pick the mode/majority. This directly resolves 034 (03 vs 08), 074 (702 vs 102), 078 (restores a working pass).
- Prefer a bold/standalone `TOTAL:` line over `Total (Inclusive of GST):` when both match the same tier. Tie-break on 077: when two tier-4 candidates exist and one is a bare `TOTAL` with a value within ±0.05 of the other, pick the bare one (final rounded).
- Harden `extract_last_number` for space-separated decimals (`92 80` → 92.80) and add integer-with-trailing-`00` fallback only when a tier keyword line has no decimal but adjacent lines agree (addresses 052-class issues the agent flagged).
- Verify `SUMMARY_HEADER_RE` does not cut above `Grand Total` on 078; relax by requiring the header to occur after the first tier-1/2 match rather than before.
- Date parser: when the keyword-line OCR yields two digits with ambiguous confidence, consult the 2nd OCR pass before emitting; default to DD/MM/YYYY for Malaysian receipts (all 22 are MY).

## Uncertainty

- I cannot inspect the final `extract.py` content in this window; later exchanges (e0025+) may contain further edits that explain the exact 077/078 regressions. The hypotheses above are consistent with m0045/m0063/m0069 but the specific exclusion that killed 078 is inferred, not verified.
- I did not see the final OCR text for 034 in the actual delivered run, only the agent's thinking. The 2018-08-09 output is incompatible with preprocessed+PSM 6 (which they claim gave 09/03), hinting at a late revert that is not visible in this window.
- 077 oracle sign cannot be confirmed from feedback (only boolean); 23.25 is the strongest pixel reading and matches the bold line, but 23.26 is also plausibly scored. The patch should try both via multi-pass voting rather than hard-coding a preference.

## w0021
## Scope of failure (from feedback, not oracle)
Reward derived = 0.909 (40/44 fields). Exactly four field errors:
- 034.jpg — date wrong (predicted 2018-08-09)
- 074.jpg — amount wrong (predicted 702.00)
- 077.jpg — amount wrong (predicted 23.26)
- 078.jpg — amount missing (null)

Termination was `max_iterations` (65/65) with `acp_stop_reason = max_turn_requests`; the agent was still actively refining extract.py in this window. Budget exhaustion, not logic convergence, ended the run.

## Per-receipt evidence from the image pixels

**034.jpg (Perniagaan Zheng Hui).** Pixel-level the date reads `Date: 09/03/2018` (DD/MM/YYYY → 2018-03-09). Agent trace (m0075) shows OCR read it as `Date: 09/08/2018`. That is an OCR digit confusion (3↔8 on a hand-stamped form). The agent's logic then interprets DD/MM/YYYY and produces 2018-08-09. Root cause is OCR substitution on a single character, not the date parser. Mitigation: try a second OCR variant (upscaled / sharpened) and prefer a date whose month ≤ 12 (already true both ways here, so true tie-break must be cross-OCR agreement or digit-confidence voting).

**074.jpg (GL Handicraft & Tailoring).** Pixel reading of the body: 6 BOXS × 17.00 = 102.00; Subtotal 102.00; Total Excl. of GST 96.23; Total Incl. of GST 102.00; **Total Amt Rounded 102.00**; Payment 102.00; GST 5.77. Agent evidence in m0075 shows default-PSM OCR produced `Total inel. of GBT 702.00` and preprocessed produced a corrupted `Total Amt Rounded ——S«702.00`. Current extractor is: Priority-4 keyword `\bTOTAL\b` matches every `Total …` line; policy takes the *last* candidate, which happens to be the OCR-mangled "Total Amt Rounded" line → 702.00. 102.00 actually appears ~5 times across the receipt; 702.00 only on the garbled line. A frequency/consensus fallback inside a tier, or discarding candidates whose line contains high non-digit noise characters (`——S«`), would break this. Requiring exactly 2 decimals (the agent's late patch in m0087) does not help here — both 102.00 and 702.00 satisfy it.

**077.jpg (Banh Mi CafE).** Pixel reading shows a stack: `Total (Excluding GST): 21.30` / `Serv. Charge (3%): 0.65` / `GST payable (6%): 1.31` / `Total (Inclusive of GST): 23.26` / `Rounding Adj: -0.01` / large-font `TOTAL: 23.25`. The final rounded TOTAL is 23.25. Current extractor picked 23.26 from `Total (Inclusive of GST)`. Both lines match Priority-4 `TOTAL`, but the agent's "take last candidate" rule was defeated because PSM-dependent OCR reordering placed `Total (Inclusive of GST)` after the final `TOTAL`, or because the large-font `TOTAL: 23.25` was misread (m0075 even claims default PSM had "no extra bad TOTAL: 23.25 line"). The genuine fix is: within Priority-4, prefer a line whose keyword is a *standalone* TOTAL (no parenthetical qualifier like "(Inclusive of GST)", "(Excluding GST)", "Amt Rounded", "After Adj") over qualified Totals — i.e., add a sub-ranking by specificity inside the priority tier. The current hint list already implies this (GRAND TOTAL > TOTAL RM > TOTAL AMOUNT > TOTAL), but the agent did not extend the stratification *within* "TOTAL" itself.

**078.jpg (Thai Delicious Restaurant).** Pixel reading: `Total : 92.80` and `Grand Total : 92.80`. `Grand Total` is Priority-1 and unambiguous. Prediction is null. Two plausible causes consistent with the window's regex evolution (m0087 tightens `NUM_RE` to require exactly 2 decimals): (a) OCR output had a space/period artifact like `92. 80` or `92.80` with trailing OCR char, so the strict `\d+\.\d{2}(?![\w.\d])` rejected it; (b) OCR produced `Grand Total :` on one line and `92.80` on the next, and the two-line fallback rule either failed because `extract_total` never fell through to the fallback for GRAND TOTAL, or the fallback picks "last number" but OCR concatenated `92.80 Cash Received 100.00` onto the same next line → 100.00 would then appear, but that is not what we see (we see null). Most likely the strict regex plus a stray character (comma, backtick, degree sign) adjacent to the digits broke matching. This is a regression the agent introduced late in the trajectory (m0087 str_replace) without regression-testing all 22 files.

## Cross-cutting causal findings
1. **Within-tier tiebreak is undertuned.** Priority-4 "TOTAL" is a bag, but the receipts contain many lines matching it. Correct extraction requires (a) sub-ranking by keyword specificity (bare `TOTAL:` > qualified `Total (…)` > `Total Amt Rounded`), and (b) cross-OCR-variant value voting when multiple candidates tie.
2. **Dual-OCR fusion is sequential, not consensus-based.** The agent's final scheme (m0078) uses "default first, preprocessed as fallback" instead of extracting candidates from *both* and voting. This explains 074 and 064 oscillation.
3. **Regex strictness was tightened without receipt-level regression.** m0087's `\d+\.\d{2}` likely caused 078 to collapse to null. Needs a both-ways test (≥1 decimal OR ≥2 decimal) with a prefer-2-decimal tiebreak.
4. **Date robustness is only tried against a single OCR pass.** 034 fails on a single OCR digit flip; a multi-pass agreement check would have caught it.
5. **Budget pressure.** 27 terminal + 22 think + 16 file_editor tool calls across 65 iterations; no invoke_skill calls. Significant tokens were spent re-reading the same OCR outputs inside `think`. Patcher should tighten the loop (batch-OCR once per file into a cached text, then iterate extraction rules in-memory) so iteration budget fits the number of rule revisions needed.

## Uncertainty
- I cannot verify the *exact* OCR strings the source Agent saw (visual messages not recorded); evidence comes from m0072/m0075/m0078/m0087 fragments and image pixels.
- For 077, it is possible the oracle actually prefers 23.26 (the pre-rounding inclusive total) rather than 23.25; the feedback only says the current 23.26 is wrong, so by elimination 23.25 is the likely target, but 23.20 (another visible "AVERAGE/PAX" style number is not present here) can be ruled out.
- For 078, the exact cause between regex strictness vs OCR drop-out is not certain without re-running; both fixes should be applied defensively.

## Guidance for Momentum / Patcher
- Add intra-Priority-4 specificity ranking: `\bTOTAL\s*:` / `\bTOTAL\s+RM` > `\bTOTAL\b.*(Incl|Inclusive|Excl|Excluding|Amt Rounded|After Adj|Sales)` > bare `\bTOTAL\b`.
- Switch to candidate-level dual-OCR voting: collect `(tier, specificity, value)` from both default and autocontrast PSM 6, prefer higher tier → higher specificity → higher cross-OCR agreement → latest line.
- Relax `NUM_RE` back to `\d+\.\d{1,2}` but, when choosing among candidates, prefer values whose raw match has exactly 2 decimals.
- Add a date-digit confusion guard: when two OCR passes disagree on a single digit of a date, prefer the DD/MM/YYYY parse that yields a month ≤ 12 and a plausible year (2017–2019 cluster in this dataset).
- Cache OCR text to disk per file to free iteration budget for rule iteration rather than repeat OCR runs.

## w0022
## Scope of new evidence (window w0022, exchanges e0030–e0036)

This window captures the tail of the source run where the Agent was iteratively tuning `extract.py` based on in-run OCR self-checks. Thought logs show the Agent explicitly aware of three stubborn residual cases (071 date, 074 amount, 077 amount) and already planning fixes for 074/077 by (a) adding `EXCLUDING` to the exclusion-keyword list and (b) experimenting with upscaled OCR. Field feedback confirms the run ultimately scored 0.909 (date_correct 21/22, amount_correct 19/22) and terminated at `max_iterations=65` with `acp_stop_reason=max_turn_requests` — i.e. not natural completion. The Agent never got to re-score after its last edits; many of the last exchanges are pure `think` + narrow re-OCR, consuming the iteration budget.

## Per-failure causal analysis (grounded in the 22 image blocks)

1. **034.jpg — date wrong (pred `2018-08-09`, image shows "Date: 09/03/2018", with "Time: 08:49:00" on the adjacent line).** The receipt uses DD/MM/YYYY and prints Date and Time stacked. The predicted month `08` matches the hour portion of the time string, and day `09` matches the real day. Cause: the date regex/parser in `extract.py` is matching tokens globally rather than anchoring to the "Date:" label, so when OCR flows "Date: 09/03/2018  Time: 08:49:00" onto the same visual column it composes `08/09` from the hour and day (or a general "DD/MM" scan picks `09/08` because "03" OCR'd poorly and `08` from the time was more confident). Window evidence does not show the Agent revisiting 034 at all — it fell out of the loop after they prioritized 064/071/074/077.

2. **074.jpg — amount wrong (pred `702.00`, image clearly shows all tier-matching lines agreeing on `102.00`).** The Agent's own thought (m0099) enumerates the preprocessed OCR output: `Subtotal : 102.00`, `Total incl. of GST 102.00`, `Total Amt Rounded 702.00` (OCR glyph misread `1→7`), `Payment : 102.00`. Current algorithm picks the LAST priority-4 match within the pass, so the corrupted `702.00` line wins. The Agent considered consensus voting but never implemented it; the planned `EXCLUDING` exclusion (m0102) does not help here because "Total Amt Rounded" has no such keyword.

3. **077.jpg — amount wrong (pred `23.26`, receipt image shows `Total (Inclusive of GST): 23.26`, then `Rounding Adj: -0.01`, then a large `TOTAL: 23.25`).** True final total is `23.25`. The extract keeps `23.26` because "Total (Inclusive of GST)" matches the tier-4 TOTAL keyword and the raw `TOTAL:` line with 23.25 either (a) is parsed earlier/later in a way that `23.26` wins by "last in tier", or (b) OCR split the big-font `TOTAL: 23.25` into a line the current regex rejects (no decimal captured on same line → fallback to previous value). The Agent's late addition of an "EXCLUDING" exclusion keyword will not help 077 (it actually *could* break it: that exclusion would drop the pre-tax "Total (Excluding GST): 21.30" line, but the pred was already `23.26`, not `21.30`, so the dominant issue is pre- vs post-rounding, not exclusion).

4. **078.jpg — amount wrong (pred empty string, image shows two unambiguous lines `Total : 92.80` and `Grand Total : 92.80`).** "GRAND TOTAL" is tier-1 in the task hint, so even a single OCR hit should yield 92.80. An empty string implies keyword matching failed on both passes. Likely causes visible from the image: this receipt is a lower-contrast thermal print; the words "Grand Total" and "Total" have trailing colons and leading spaces, and the colon-space-number layout combined with the Agent's recent strict 2-decimal regex (m0090 "Test with strict 2-decimal number regex") may be rejecting the number if OCR inserted a stray char between `:` and `92.80`, or splitting the keyword across two tokens. The empty output correlates with the window showing the Agent tightening regexes without re-running the full 22-image verification afterwards.

## Run-level causes

- **Iteration budget exhaustion**: Exchanges e0030–e0036 all carry prompt_tokens ≈ 91k–96k and are dominated by `think`/narrow terminal checks. The Agent spent many iterations on micro-reasoning (m0093, m0099, m0105) about a single receipt before editing. Termination at 65/65 prevented a final full re-verification pass, so edits intended to fix 077 (exclusion keyword) or 074 (upscaling) were never validated end-to-end.
- **Local tie-break policy ("last candidate in tier")** causes both 074 (OCR-corrupted trailing line wins) and 077 (pre-rounding line wins over final rounded TOTAL).
- **Date parser lacks label anchoring**, causing 034's `Date:`/`Time:` adjacency to leak hour into month slot.
- **Keyword/number co-location is brittle** under OCR noise, causing 078's silent null despite a clear `Grand Total` line.

## Guidance for Momentum / Patcher (no Skill rewrites here)

- Patcher should target `extract.py`, not the Skills: the `image-ocr` skill is generic and already drives multi-pass OCR; the failures are in the downstream domain logic for receipt total/date selection.
- High-leverage, low-risk fixes:
  1. For date: prefer tokens on the *same* OCR line as a `DATE` label; reject date candidates whose "month" field exceeds 12 before falling back; forbid composing day/month from different source lines.
  2. For total: switch tie-breaking within a tier from "last" to "most-agreed value across all OCR passes and across Subtotal/Payment/Total-incl lines"; this directly repairs 074 (102.00 has 3 votes vs 702.00's 1).
  3. For 077: within tier-4, if a line literally begins with `TOTAL` (no parenthetical qualifier) and appears *after* a `Rounding Adj` line, prefer it over any earlier `Total (Inclusive …)` line.
  4. For 078: fall back to fuzzy keyword match (allow 1 edit on "GRAND TOTAL"/"TOTAL") and relax the strict 2-decimal regex to accept values with a single stray non-digit char adjacent to the number.
- Momentum should not re-tune OCR preprocessing globally; the three amount errors are selection-logic, and the one date error is label-anchoring. Avoid re-adding broad exclusions (e.g. `EXCLUDING`) without re-verifying all 22, since the source run's late exclusion edits were never full-suite tested.

## Uncertainty

- Window text is largely request-ID bookkeeping; I did not see the final `extract.py` body in this window, so the exact current regex/tie-break code is inferred from m0099/m0102/m0105 thoughts and the field-level outcomes. The exact reason 078 produced `""` (vs a wrong number) is inferred from the image + the m0090 "strict 2-decimal" edit; could alternatively be an OCR skip of the `Total` line entirely.
- For 034, I cannot see the actual OCR text in this window; the "time-bleeds-into-date" hypothesis fits predicted `2018-08-09` perfectly but a pure OCR misread of `03 → 08` cannot be ruled out. Either way, label-anchoring the date fixes both.

## w0023
## Scope of failure (reward 0.909, 4/44 fields wrong)
From `field_feedback`: three amount errors (074, 077, 078) and one date error (034). All 22 predictions were present and the sheet shape was valid, so this is purely an extraction-content problem, not a delivery/format problem.

## Direct image evidence (new this window)

- **034.jpg** (Perniagaan Zheng Hui): the date line reads `Date: 09/03/2018`. Correct ISO is `2018-03-09`. Prediction `2018-08-09` is consistent with one OCR variant misreading the `3` as `8` (producing `09/08/2018`), then day-first parsing → month=08. The agent's own tabulation in this window literally states "034: date '09/08/2018' ✓" — meaning they *accepted* the misread as correct without a second reference. Majority voting across 3 Tesseract variants is unlikely to recover from a consistent 3↔8 confusion on this font/scan.

- **074.jpg** (GL Handicraft & Tailoring, 20/03/2018): the image clearly shows `Subtotal 102.00`, `Total Incl. of GST 102.00`, `Total Amt Rounded 102.00`. Correct amount is `102.00`. Prediction `702.00` is a `1→7` OCR digit confusion. The window shows the agent's upscale pass produced `Total incl. of GST 102.00` (correct) but the default/preprocessed passes produced `702.00`-shaped strings in tier 4 (`TOTAL`), and the new `pick_best_total` voting took majority-of-variants inside the same tier — two bad passes outvoted one good pass.

- **077.jpg** (Banh Mi Cafe, 29-10-2017): the receipt has, in order:
  `Total (Excluding GST): 21.30` → `Serv. Charge (3%): 0.65` → `GST payable (6%): 1.31` → `Total (Inclusive of GST): 23.26` → `Rounding Adj: -0.01` → `TOTAL: 23.25`. Gold-consistent answer is `23.25` (the post-rounding final). Prediction `23.26` picked the pre-rounding `Total (Inclusive of GST)` line. Two likely causes, both visible in the code structure quoted in this window:
  1. `find_summary_start` probably matches the `GST`/`Tax Summary` block *below* `TOTAL: 23.25`, so both candidates survive; the "reverse last candidate wins" rule should pick `23.25`. If so, the failure is that OCR dropped the bare `TOTAL: 23.25` line (big bold, separated by dashed rule) or merged it with the barcode-like region, leaving only the `Total (Inclusive of GST): 23.26` line in text.
  2. Alternatively, `Rounding Adj` is not in the exclusion list; if OCR produced `Total (Inclusive of GST): 23.26` then `Rounding Adj -0.01` and no `TOTAL: 23.25` line, nothing else helps. Either way, the fix lives at the OCR-coverage / keyword-prioritization boundary, not in the voting layer.

- **078.jpg** (Thai Delicious Restaurant, 02/02/2017): image shows a right-column `Total : 92.80` and `Grand Total : 92.80` printed in a wide tabular layout with large horizontal gaps. Correct amount is `92.80`. Prediction is empty (`""` / null). The agent's own notes in this window ("078: Grand Total (missing number in this line!) - fallback") indicate OCR split the keyword from the number across the table gap, so `extract_last_number` on the `Grand Total` line returned `None`. The current fallback only inspects the next 1–2 non-empty lines, breaks on any excluded keyword, and does not look at numbers on the *same* line separated by a long run of spaces as a column break. If OCR produced `Grand Total :` on one logical line and `92.80` on another separated by `Cash Received : 100.00`, the fallback would hit `Cash Received` (not in exclusion list — only `CASH TENDERED` is) and still pick `100.00`. That null was produced suggests the fallback actually did break on something (possibly a blank line) before any number appeared.

## Causal summary for Momentum

The source Skill (image-ocr) does not prescribe any receipt parsing; the executor built `extract.py` from scratch and iterated three times in this window:
1. default pytesseract,
2. grayscale+autocontrast PSM 6,
3. 2× upscale + autocontrast PSM 6,
then introduced a `(tier_index, value)` voting function `pick_best_total`.

The voting is sound for tier-mismatches but has two weaknesses visible in the failures:
- **No digit-level consensus.** When two variants agree on a wrong digit (`702.00`) and one variant has the right one (`102.00`), majority-of-variants wins the wrong answer (074). Needs per-digit voting or a plausibility/anchor check (e.g., re-verify the chosen total against a Subtotal or Rounded-Total line nearby).
- **No rounding-aware tie-break inside the same keyword tier.** For 077, when both `Total (Inclusive of GST)` and `TOTAL:` match tier 4, picking the *last* one is the right heuristic *only if* OCR captured it. The real risk is OCR coverage of the big bold `TOTAL:` line; PSM 11 (sparse) or layout-preserving `image_to_data` would help capture isolated large text.

Secondary issue, 078: the fallback rule from the task hint ("use the last number on that next line") is implemented too narrowly — it stops at the first non-empty following line and treats a wide-tabular right-column number as absent.

Date issue (034): voting cannot recover a systematic character confusion. Either regex should keep *all* plausible dates across variants and prefer those whose month ≤ current OCR-dominant month patterns, or the extractor should re-OCR a tight crop of the date line with higher DPI / different PSM.

## Uncertainty

- I cannot see OCR text directly, only the window's summary; the exact reason 077 picked 23.26 could be either OCR dropping `TOTAL: 23.25` or `find_summary_start` cutting it. Both demand different fixes (OCR variant vs. keyword/exclusion list change).
- 078's null (vs. a wrong 100.00) suggests the fallback broke on an empty line, but I can't confirm without seeing the raw text; a safer repair widens the fallback window and scans the whole receipt for numbers aligned to the right column of the Grand Total row.
- The 034 misread could also come from a pencil/handwriting smudge near the "03" in the scan; voting across more aggressive preprocessors (binarize + sharpen) is plausible but not guaranteed.

These four failures are independent and local; no evidence of a global schema, delivery, or column-naming problem in this window.

## w0024
## Window w0024 Evidence (new material, not repeating prior windows)

This window captures exchanges e0041–e0046 of 65, in which the executor was still actively debugging a *multi-variant OCR voting* strategy very late in the budget (timestamps 17:45:29 → 17:47:28, task ended 17:55:47). The agent's own `think` traces here (m0126, m0132, m0138) show it had just discovered that its "last keyword line" rule and its fallback-across-lines rule were interacting badly, and it was mid-hypothesis-test when execution ended (`termination_reason: max_iterations`, `acp_stop_reason: max_turn_requests`). The delivered `stat_ocr.xlsx` was therefore an earlier commit, not the post-fix state the agent was converging toward. That is a first-order cause: natural completion did not occur, so the voting improvements it was validating never reached the artifact.

## Correlating field feedback with pixel evidence

Four fields are wrong (`reward=0.909`). I inspected each failing JPEG's pixels in the attached image blocks:

- **034.jpg** (date wrong, predicted `2018-08-09`). The receipt (Perniagaan Zheng Hui simplified tax invoice) prints `Date: 09/03/2018`. In every other Malaysian receipt in this set the executor correctly treated DD/MM/YYYY (see 069, 071, 094, 097). Oracle for 034 is almost certainly `2018-03-09`. The output `2018-08-09` is not a plausible reading of `09/03/2018` under either convention; it matches the pattern of transposed/duplicated digits from a noisy OCR candidate (handwritten `A03041` sits above the Date line and the agent may have taken `08` from the time `08:49:00` plus the day `09`). Root cause: the date extractor is picking a wrong candidate when multiple date-like tokens exist, and not anchoring on the token adjacent to the literal "Date:" keyword.

- **074.jpg** (amount wrong, predicted `702.00`). The IKEA-style POPULAR BOOK CO. receipt prints clearly: `Total RM Incl. of GST 20.98 / Rounding Adj 0.02 / Total RM 21.00`. Wait — 074 is actually the GL Handicraft safety-pins receipt: `Subtotal 102.00`, `Total Incl. of GST 102.00`, `Total Amt Rounded 102.00`. Oracle is `102.00`. The prediction `702.00` is a classic Tesseract `1→7` digit confusion on the thin faded digit in the printed `102.00`. No variant voting salvaged it in the delivered file; this window's debug traces (m0129, m0135) show the agent discovering exactly this class of per-variant drift on 064 ("688.17" spurious value) but never finishing the same reconciliation pass for 074.

- **077.jpg** (amount wrong, predicted `23.26`). The Banh Mi Cafe pixels show the sequence `Total (Inclusive of GST): 23.26 / Rounding Adj: -0.01 / TOTAL: 23.25`. The task hint priority list has `TOTAL` as a priority-4 keyword with no exclusion for the "Inclusive" variant; both lines match. The last matching line is `TOTAL: 23.25`, which is the actually-printed final. The agent's trace at m0126 explicitly recognizes "Our answer 23.25 is CORRECT (better than 23.26)" and the fixed code produced 23.25 under voting — but the delivered xlsx retained the earlier 23.26. Root cause: tier-internal ordering bug (picking first candidate in text order rather than the last, plus the output-write step happened before the fix). Oracle is `23.25`.

- **078.jpg** (amount wrong, predicted empty). The Thai Delicious Restaurant pixels show `Total : 92.80 / Grand Total : 92.80 / Cash Received : 100.00 / Change : 7.20`. Oracle is `92.80`. The agent trace in m0126 traces exactly why: on the upscaled variant Tesseract emitted `: Grand Total` on one line and `| Change 7.20 |` on the next. The split-line fallback found the next line excluded (`CHANGE`), so it returned no value, and nothing else matched priority 1. Priority-4 `TOTAL` fallback was not attempted because the current code returns early at tier 1 with "no number", rather than cascading to the next tier.

## Faults to carry into Momentum / Patcher

1. **Early-exit in tiered keyword search.** When the highest-priority tier yields a candidate line but no parseable number (and the next-line fallback is excluded), the code must still fall through to lower tiers. This single bug explains 078, and contributed to the 074 misread when the only "TOTAL" line was corrupted.

2. **Within-tier ordering.** The task hint and 077 oracle require selecting the *last* matching line within a tier (post-rounding totals print after subtotals). Current logic uses first-match or reversed candidate list without correctly filtering (as agent's self-trace in m0132 shows for 064 variant 2 where "Total RM" matched a header line before "Total Gross RM 86.17").

3. **Digit-level OCR noise on amounts.** 074's `102.00→702.00` is a leading-digit confusion. Multi-variant OCR + numeric cross-check (e.g., require amount ≤ 10× subtotal when both are detected; or majority vote across ≥3 preprocessing variants) is the mitigation. The agent partially implemented voting in this window but did not stabilize it before termination.

4. **Date candidate selection on 034.** The `Date:`-anchored line must win against time/stamp tokens. The current extractor's scoring produced `2018-08-09` for a receipt that prints `09/03/2018` — most likely by concatenating fragments from distinct lines. Enforce: regex that captures the full `DD/MM/YYYY` immediately after a `Date` label, before considering free-standing dates elsewhere.

5. **Termination hygiene.** `n_skill_invocations=0` despite the `image-ocr` skill being available, and the final 24 exchanges in this window burned ~108k prompt tokens of mostly cached context on short debug ticks (111–859 completion tokens each). A Patcher should (a) always flush `stat_ocr.xlsx` after every image, (b) short-circuit redundant full-corpus reruns, and (c) invoke the OCR skill rather than re-deriving its code inline.

## Uncertainty

- I cannot verify the exact oracle strings (only booleans). The oracle values I infer (034→`2018-03-09`, 074→`102.00`, 077→`23.25`, 078→`92.80`) are derived from directly inspecting the attached JPG pixels and the task's priority/exclusion hint; they are consistent with every receipt convention observed across the other 18 correct rows but not independently confirmed.
- I cannot see which preprocessing variants were actually used in the delivered `extract.py` (not readable from this window's text); the debug traces indicate three variants (default, preprocessed PSM 6, upscaled PSM 6) with majority voting, but whether that code survived in the terminal submission is uncertain.
- The 034 date failure mode could alternatively be a mis-transcription of the time `08:49:00` into the date slot; either way the fix is label-anchored date selection.

## w0025
## Scope of this window
Exchanges e0046–e0050 capture the agent diagnosing receipt 064 (which ended up correct in the final xlsx) and patching the "keyword split across two lines" fallback at m0147. New focus: the still-failing cases in field feedback — 034 date, 074/077/078 amount — which this window did not resolve before max_iterations termination (ran=65, cap=65, acp_stop_reason=max_turn_requests).

## Image-grounded evidence for each failing field

**034.jpg (Perniagaan Zheng Hui)** — predicted date `2018-08-09`, truth is clearly `09/03/2018` on the image ("Date: 09/03/2018 08:49:00"). This is a Malaysian DD/MM/YYYY receipt. The correct ISO is **2018-03-09**. The source extractor parsed it as MM/DD (month=08 is impossible for this receipt — there is no "08" day/month in sight, so agent likely matched a different token like "9555058800696" or confused slash direction). Amount 332.30 was extracted correctly from the "Total (RM) : 332.30" row. Root cause: date parser lacks region-aware DD/MM preference; needs to prefer DD/MM when both components are ≤12 for Malaysian receipts, or at minimum trust an explicit "DD/MM/YYYY" format when the first field is ≤31.

**074.jpg (GL Handicraft & Tailoring)** — predicted `702.00`, truth on image is **`102.00`** (Total RM / Total Incl. of GST / Total Amt Rounded / Payment all show 102.00; item line is "6.00 BOXS x 17.00  102.00"). OCR almost certainly misread "102.00" as "702.00" (1→7 substitution on a faded light-blue thermal print). Keyword logic is fine; the failure is upstream OCR character recognition. Mitigation: multi-pass OCR variants with heavier preprocessing (binarisation, scale-up) and cross-variant voting, or digit-aware consistency check (Subtotal = Total, Payment line equals Total).

**077.jpg (Banh Mi CafE)** — predicted `23.26`, truth is **`23.25`** (the bold "TOTAL: 23.25" at bottom, after Rounding Adj −0.01 from 23.26). Two TOTAL-tier candidates both have digits on-line: "Total (Inclusive of GST): 23.26" and final "TOTAL: 23.25". With `reversed(candidates)` the bottom "TOTAL: 23.25" *should* win — but the agent's output got 23.26, implying either (a) OCR failed to produce the final "TOTAL: 23.25" line in machine-readable form (large bold font often mis-segmented), or (b) the final TOTAL line matched tier 4 while "Total (Inclusive…)" matched tier 3 ("TOTAL AMOUNT" — no, this is tier 4 too). Most likely (a): the big-font bottom TOTAL was OCR'd as a separate line where "TOTAL:" and "23.25" are split, and the m0147 fix (requires no digits on keyword line → fall through) would retrieve it. The patch landed late in the run and clearly didn't make it into the saved xlsx (feedback still shows 23.26).

**078.jpg (Thai Delicious Restaurant)** — predicted null, truth on image is **`92.80`** (Total: 92.80, Grand Total: 92.80). Agent produced empty string, meaning no tier matched or extract_last_number failed. On this table-style receipt, amounts are right-justified with many spaces; tesseract commonly splits label from value or inserts the dotted divider between them. The m0147 fallback *would* rescue "Total :" → next line "92.80" but only if the keyword line has zero digits. Also, "Grand Total :" should hit tier 1 (GRAND TOTAL). Since neither was extracted, OCR likely produced noisy text like "Total :" + "----------" + "92.80" with the dashed separator aborting the next-line scan (is_excluded? No — but `break` on first non-matching numeric line in current fallback would stop at the dashed line). Needs: skip pure-punctuation/dash lines in fallback scan rather than break on them.

## New Momentum/Patcher evidence this window adds

1. **Fallback-scope bug found & partially fixed at m0147**: the pre-fix code triggered the "look at next line" rescue even when the keyword line already contained digits — so lines like "Total RM = B81?" bled into "Visa RM =688.17". The m0147 patch gates the fallback on "keyword line has no digits". This is a net improvement for cases like 064 and 077, but was applied too late to affect the delivered xlsx.
2. **Fallback still too narrow for dashed separators** (078): the current `break` on the first non-numeric non-excluded next line kills recovery when a dashed divider sits between label and amount.
3. **No OCR variant diversity for 1-vs-7 substitutions** (074): the image-ocr Skill mentions multi-pass OCR but the executor's `ocr_variants` set did not produce a reading that disambiguated "102.00" vs "702.00". Momentum should pursue PSM 6 + upscaling + adaptive threshold for low-contrast thermal receipts; Patcher can post-validate by requiring the extracted total to equal payment/cash-tendered when both are OCR'd.
4. **Date parser is month/day ambiguous** (034): receipts are Malaysian DD/MM/YYYY. A deterministic DD/MM preference (or detection of day > 12 somewhere in the same file to lock the format) fixes 034 without risking other receipts (007 "23-01-2019", 064 "21/02/18" etc. already parse correctly only because day>12 forces DD/MM).

## Uncertainty
- 074 "702.00" vs 102.00: image is clear to a human, so this is an OCR miss; cannot be certain which preprocessing variant will rescue without re-running.
- 077 and 078: cannot verify whether the m0147 patch alone (had it been saved and re-executed) would have flipped them without also loosening the "dashed-line break" in the fallback; evidence suggests 077 would flip, 078 probably not.
- 034 date: the image unambiguously shows 09/03/2018; the exact code path that produced 2018-08-09 is not visible in this window, so the "MM/DD vs DD/MM" hypothesis is inferred from the digit swap pattern, not proven from a traced regex match.

## Recommendation shape (for downstream stages)
- Patcher should (a) loosen the two-line fallback to skip blank/dash-only lines rather than break, (b) add a DD/MM-first date rule for slash-separated dates, (c) add a payment/cash cross-check or a 2nd OCR variant (psm 6 + upscale 2×) specifically for low-contrast receipts to break 1/7 ties.
- Momentum: the agent's debug flow was sound but consumed ~65 iterations on one case (064); recommend bounding per-receipt debug and spending saved budget on verifying delivered xlsx before termination.

## w0026
## Root causes (new evidence from this window: exchanges e0050–e0054)

**Termination context.** The run hit `max_iterations=65` mid‑refinement (termination_reason=`max_iterations`, `acp_stop_reason=max_turn_requests`). This window shows the Agent was still editing `/app/workspace/extract.py` — adding `CASH\s+(TENDERED|RECEIVED|PAYMENT)` to the exclusion regex (m0162) and replacing `extract_total_with_tier` with a new `extract_total_candidates`/`pick_best_total` that collects **all** tier‑matched (tier_idx, value) pairs across variants and picks the mode within the best tier (m0156, m0159). These edits were being written here; the delivered `stat_ocr.xlsx` embedded in `pre-verifier-inputs.tar.gz` therefore reflects a *pre‑fix* execution, consistent with the predictions snapshot (077=23.26, 078="", 074=702.00).

**Field feedback accounting (2 amount misses + 1 date miss, reward 0.909):**

1. **074.jpg amount — 702.00 vs. receipt showing 102.00.**
   Direct inspection: "GL Handicraft & Tailoring", line `6.00 BOXS × 17.00 = 102.00`, then `Subtotal : 102.00`, `Total Excl. of GST 96.23`, `Total Incl. of GST 102.00`, `Total Amt Rounded 102.00`, `Payment : 102.00`. The value 102.00 occurs 4× on the receipt; 702.00 does not appear anywhere. The Agent's own think log (m0153) correctly identifies this: two variants mis-OCR'd a `1` as `7` on the "Total Amt Rounded" line, and because the old `pick_best_total` voted only on the per‑variant top candidate, the 2‑vs‑1 tie at tier 3 chose 702. The new strategy in m0156/m0159 (collect every tier‑matched candidate from every variant, then vote) is exactly the right direction because within variant 2 the "102.00" lines (Total Incl., Total Amt Rounded, Payment) all match TOTAL keywords and would push the frequency tally decisively to 102.00. Evidence that the fix was *not* actually exercised: the delivered prediction is still 702.00.

2. **077.jpg amount — 23.26 vs. receipt showing 23.25.**
   Image "Banh Mi Cafe" shows two tier‑3 TOTAL matches in sequence:
   `Total (Inclusive of GST): 23.26`
   `Rounding Adj: -0.01`
   `TOTAL: 23.25`
   Both are tier 3 ("TOTAL"). The current code prefers the **last** match within a tier (reversed order), which would give 23.25. The fact that the delivered prediction is 23.26 suggests one of two mechanisms: (a) the `find_summary_start` heuristic (not shown in this window but referenced by `summary_start = find_summary_start(lines)`) truncates the lines *before* the bold "TOTAL:" line because an earlier keyword like "Closed:" / "GST Summary" marks the summary boundary too aggressively; or (b) an OCR variant lost the final "TOTAL: 23.25" line and the only remaining TOTAL match was the GST‑inclusive line. Receipt‑level inspection favors (a): "Closed:" and a GST Summary block sit *between* "TOTAL: 23.25" and the end, so a summary‑start heuristic that latches onto "GST Summary" would cut off the final TOTAL. Uncertainty: cannot confirm `find_summary_start` body from this window; the Patcher should audit whether the summary boundary ever precedes a line that still contains a valid priority keyword (specifically a bare `TOTAL:` line following a `Rounding Adj`).

3. **078.jpg amount — null vs. receipt showing 92.80.**
   Image "Thai Delicious Restaurant" has:
   `Total : 92.80`
   `Grand Total : 92.80`
   `Cash Received : 100.00`
   `Change : 7.20`
   `Grand Total` is tier 0. The null output means every variant either (a) failed to read the Grand Total numeric and fell through to the two‑line fallback that picked up `Cash Received 100.00`, which was *not* in the exclusion list in the pre‑fix code (confirmed — m0162 is the first time `CASH\s+RECEIVED` is added), and (b) that `100.00` was then overridden by the tier‑ordering, or the final chosen tier‑0 candidate was None. Secondary issue: even the tier‑3 `Total : 92.80` should have rescued this, which indicates OCR either dropped the `: 92.80` suffix or that line was consumed by the split‑line fallback and then voted out. The m0162 exclusion addition would at least stop the Cash‑Received fallback from polluting the vote; combined with the all‑candidates voting from m0159, tier 3 `Total 92.80` from the non‑scale variant should surface. Again, the delivered prediction is `""`, so the fix did not execute end‑to‑end.

4. **034.jpg date — 2018-08-09 vs. receipt "Date: 09/03/2018".**
   The receipt is Malaysian "Perniagaan Zheng Hui" with `Date: 09/03/2018` and `Time: 08:49:00`. The predicted `2018-08-09` is inconsistent with any single reading of the visible date tokens; the leading "08" most plausibly came from the Time field ("08:49:00") being concatenated with the Date, or from a date regex that matched `08/…/…` off the time digits. This points to a date extractor that (i) does not anchor on the "Date:" label, and (ii) accepts `HH/MM` or `HH:MM` fragments as date‑like matches. This window does not expose `extract_date`, but the failure is strong enough to warrant the Patcher inspecting the date regex and its priority between labeled vs. unlabeled matches, and adding a "prefer `Date:` labeled match" rule.

## Evidence quality / uncertainty

- Strong, directly from pixels: 074 contains no 7‑prefixed candidate; 077 has an explicit final `TOTAL: 23.25`; 078 has `Grand Total : 92.80`; 034 has `Date: 09/03/2018`.
- Window‑specific signals: m0156/m0159 rewrite of voting was *in flight* (file_editor str_replace calls, no subsequent terminal rerun shown in e0050–e0054), consistent with budget exhaustion before validation; the delivered Excel precedes these edits.
- Uncertain: exact body of `find_summary_start`, `extract_date`, and `ocr_variants` (not quoted in this window). The 077 cause (summary boundary vs. OCR drop) is the main ambiguity.

## Guidance for Momentum / Patcher (non‑prescriptive)

- The in‑flight patch direction (cross‑variant candidate aggregation + expanded CASH exclusion) addresses 074 and 078 but was never executed. Patcher should finish and verify it.
- 077 needs a separate look at the summary‑boundary heuristic: ensure a trailing standalone `TOTAL:` line after `Rounding Adj` / before `GST Summary` is still considered; "GST Summary" alone should not cut off an immediately preceding priority‑keyword line.
- 034 points at the date extractor, not the total extractor; anchor on `Date[:]*` tokens and reject matches whose first group uses `:` separators (time), and prefer labeled matches over the first numeric trigraph in the OCR stream.
- Budget: the source run used 65 iterations and ran out mid‑edit; Momentum should ensure either fewer, larger edits or a checkpoint that re‑runs `extract.py` and re‑emits the xlsx before the final finish, so partial refactors cannot ship.

## w0027
## Scope of failures in this window

Feedback: reward 0.909, 4 field misses across 3 receipts.
- **034.jpg**: date wrong (`2018-08-09` vs image)
- **074.jpg**: amount wrong (`702.00`)
- **077.jpg**: amount wrong (`23.26`)
- **078.jpg**: amount null (empty)

The failing receipts are all handled by an in-repo `extract.py` script (visible in the exchanges: `ocr_variants`, `extract_total_candidates`, `PRIORITY_TIERS`, `is_excluded`, `extract_last_number`, `find_summary_start`). The Skill documents themselves are generic OCR primers and do not encode any receipt-specific keyword/number/date logic — that logic is all in agent-authored code. This matters because the Patcher cannot "fix OCR" without reaching into the extraction algorithm it is expected to emit.

## Receipt-level evidence (new this window)

**077 (Banh Mi CafE)** — Pixels show two TOTAL-tier lines:
- `Total (Inclusive of GST): 23.26`
- `Rounding Adj: -0.01`
- `TOTAL: 23.25` (bold, bottom)

Prediction `23.26` is the *first* TOTAL match, pre-rounding. The code (as hinted by the agent's "077 now correctly shows 23.26!" celebration in e0054–e0055, then feedback contradicting) is picking the earlier TOTAL instead of the net/rounded final TOTAL. Hints list keywords by *specificity* but say nothing about tie-breaking inside tier 4; the correct behaviour is to prefer the last TOTAL after a Rounding line / the largest-text TOTAL, matching the net value 23.25.

**078 (Thai Delicious Restaurant)** — Pixels clearly show `Total: 92.80`, `Grand Total: 92.80`, `Cash Received: 100.00`, `Change: 7.20`. Prediction is null. Exchange e0056 (agent `think`) records that OCR variants produced "GrandTota." (no space), "a Total — 92:80" (colon in decimal), and "92 80" (space-separated). The extractor's `\bGRAND\s+TOTAL\b` regex requires a whitespace separator and strict `\d+\.\d{2}` for numbers, so none of the Grand-Total candidates survive. "Cash Received" was added to exclusions in m0162 (correct, fixes a potential 100.00 fallback), but the real issue is that no clean candidate is produced, and a null is returned instead of picking the many visible 92.80's. Root causes:
  1. Keyword matcher brittle to missing space / dropped characters ("GRANDTOTAL", "GrandTota", "Grond Total").
  2. Number parser does not treat `:` between digits as a possible OCR misread of `.`.
  3. No cross-variant voting on numbers when the keyword match fails in one variant but the amount text (92.80) occurs in another.

**074 (GL Handicraft)** — Pixels show `Subtotal 102.00`, `Total Incl. of GST 102.00`, `Total Amt Rounded 102.00`, `Payment 102.00`. Prediction `702.00` is a single-digit OCR miss (`1`→`7`) on one amount token. The agent's e0054 comment notes "voting picks majority which is 702 from 2 variants" — i.e. the implemented *candidate voting* across variants reinforced the bad digit because multiple variants OCR'd the bold `102` as `702`. The implemented voting is majority-over-variants without any sanity constraint (e.g., consistency with Subtotal, consistency with the "Total Excl. of GST 96.23" + "GST 6% = 5.77" sum, or digit-plausibility of a leading `7`). The skill revision needs either: (a) a "constrain total ≥ subtotal, and ≈ subtotal + GST" check, or (b) prefer the candidate that matches another TOTAL-tier line (102.00 appears four times in the ink). Majority-voting over raw OCR variants is the wrong aggregator here.

**034 (Perniagaan Zheng Hui)** — Pixels show `Date: 09/03/2018` and time `08:49:00`. Prediction `2018-08-09` suggests the date parser either: (i) picked up the `08` from `08:49:00` as a month, or (ii) OCR confused `03`→`08` and the DMY→ISO conversion then produced 2018-08-09. Looking at the clean scan, option (i) seems most likely: a generic date-regex pass that also triggers on `HH:MM:SS` or on the `GA1801` item annotations (which contain `1801`) mixing numeric groups across lines. Fix direction: date extraction should (a) require a 4-digit year in the same token, (b) prefer a match on the line/neighbourhood of the keyword `Date`, (c) run cross-variant voting on dates the same way amounts are voted, and (d) reject matches that overlap a `HH:MM` time span.

## Cross-cutting causal findings for Momentum / Patcher

1. **Keyword matcher is too strict.** `\bGRAND\s+TOTAL\b`, `\bTOTAL\s+AMOUNT\b` etc. fail when OCR drops a space or a character. Needs: allow 0-or-1 non-alphanumeric between tokens, accept common OCR confusions (`0`↔`O`, `1`↔`l`/`I`).
2. **Number regex ignores separator noise.** `\d{1,3}(,\d{3})*\.\d{2}` misses `92:80`, `92 80`, `92.8O`. Needs tolerance for `:` / `;` / stray space between the integer and fractional part, and `O`→`0` fix in the decimal.
3. **Tie-breaking inside tier 4 (TOTAL).** When several TOTAL matches exist, choose the *last one after any Rounding line*, not the first. Explicit evidence: 077.
4. **Multi-variant voting must be sanity-checked.** Plain majority can entrench a bad digit (074). Prefer candidates that: (a) are consistent across keywords in the *same* variant (TOTAL = Payment = Rounded Total), or (b) match Subtotal+GST within 0.02.
5. **Date extraction needs the same multi-variant voting discipline and must exclude clock-time groups.** Evidence: 034.
6. **Termination.** Source run exhausted `max_iterations=65` (`termination_reason: max_iterations`); the agent was still iterating on 074/078 at the budget cutoff (exchanges e0054–e0057 are all late-cycle). Not a natural stop → any Momentum assumption that the current solution is "settled" is wrong; the extractor remains in a debug-mid-stream state.

## Uncertainty

- Oracle for 077: I am inferring `23.25` from the visible rounded TOTAL; feedback only tells me `23.26` is wrong, not what the truth is. If the oracle expected `23.26`, something else about that cell (e.g. normalization/format) would have to be the fault — but the Skill's export uses the same path for all receipts and the others pass, so this is unlikely.
- For 034 the pixel `3` vs `8` glyph is unambiguous on my inspection; I attribute the miss to the parser scope (time/annotation bleed) rather than raw OCR.
- I did not re-execute `extract.py`, so the exact tie-breaker in current code is inferred from the agent's own trace (e0054: "voting picks majority which is 702 from 2 variants"; e0056: notes on 078's failing candidates).
- No evidence the source agent saw images; images here are Diagnoser-only, consistent with `original_visual_messages_recorded: false`.

## w0028
## New evidence in this window

Exchanges e0058–e0061 show the agent tracing variant 0 of **078.jpg** through its own `extract.py` and discovering a specific failure chain:

- `find_summary_start` and priority tiers were applied, but OCR produced:
  - Line 10 `Description Qty Price Amount` (matches `AMOUNT` keyword, no digits).
  - Line 31 `a Total — 92:80` (matches `TOTAL`, has digits but no valid 2-decimal `\d+\.\d{2}` number because the OCR substituted `:` for `.`).
- Reverse iteration tried line 31 first → regex failed (colon, not period) → candidate had digits, so the "amount on next line" fallback was NOT triggered.
- Then line 10 → no digits at all → fallback fired and grabbed `20.00` from the first item row ("...OSBRAISED 7 2000 20.00").
- The patch in e0059–e0061 added two new exclusion regexes: `\bDESCRIPTION\b` and `\b(QTY|PRICE)\s+AMOUNT\b` so the column header stops being a keyword candidate.

That patch is **necessary but insufficient**: it only prevents the wrong fallback firing from the header row. It does **not** recover `92.80`, because the real pixel evidence (confirmed in the 078 image: `Thai Delicious Restaurant`, item lines summing to 92.80, printed "Total : 92.80 / Grand Total : 92.80 / Cash Received : 100.00") shows the OCR corrupted the decimal separator (`92.80` → `92:80`). After this window's patch, 078 will still return null because no tier-matched line yields a valid `\d+\.\d{2}` token, and the fallback only runs when there are no digits at all.

## Still-open causal chains per failing field

**078.jpg — amount null (confirmed by pixel evidence: Grand Total 92.80)**
- Root cause: `extract_last_number` requires strict `\d+\.\d{2}`; OCR rendered `92.80` as `92:80` (and also garbled characters around "Grand Total"). The window's new header exclusion silences the spurious 20.00 fallback but leaves the extractor with no match.
- Needed repair signal for Momentum/Patcher: tolerate common OCR decimal substitutions (`:` / `;` / `,` / spaces) when the line is already classified as a TOTAL candidate, OR broaden the numeric regex when matched against a tiered keyword line (not globally). Also, when the keyword line has corrupted digits, fall back to `extract_last_number` on the SAME line after normalizing `[:;]` → `.`.

**074.jpg — amount wrong: 702.00 vs true 92.80 (Thai Delicious, same template as 078)**
- Pixel evidence in 074 shows identical layout to 078 with `Total : 92.80 / Grand Total : 92.80 / Cash Received : 100.00 / Change : 7.20`. 702.00 is implausible as a direct read; the most likely source is the extractor concatenating or mis-tokenizing the right column across adjacent rows (`7.20` adjacent to `100.00`/`92.80`) or scanning a line like "Change : 7.20" together with another number and the current `extract_last_number` grabbing an OCR-glued value such as "7 02.00" / "702.00".
- Signal: the current `extract_last_number` does not guard against glued numbers on the same line (e.g., when OCR drops the space between the label column and the amount column). Also, "Change" is already an exclusion keyword — but `Cash Received` is NOT in the exclusion list in the Skill hint, and could be the surface the glued read came from.
- Repair hint: add `CASH RECEIVED` to exclusion list; when a candidate numeric looks like a concatenation (no explicit separator between a 2–3 digit integer and a `.NN` tail), prefer the LAST valid `\d{1,4}\.\d{2}` sub-token rather than the greedy last one.

**077.jpg — amount wrong: 23.26 vs true 23.25 (Banh Mi Cafe)**
- Pixel evidence: receipt prints `Total (Inclusive of GST): 23.26 / Rounding Adj: -0.01 / TOTAL: 23.25`. Both lines match the `TOTAL` keyword in tier 4. Predicting 23.26 means the extractor picked the earlier "Total (Inclusive of GST)" over the final standalone "TOTAL:".
- Root cause: within a priority tier the code appears to pick the FIRST (or earliest iterated) candidate rather than the LAST printed TOTAL after rounding adjustment. The reverse-iteration logic shown in the e0058 trace does reverse, but exclusion patterns probably strip `(Inclusive of GST)` out — need to verify whether the exclusion `EXCL` or similar is hitting the final TOTAL line instead.
- Repair hint: when two lines in the same tier both yield valid numbers, prefer the one with the strongest-anchored TOTAL token (bare `TOTAL:` or `TOTAL RM`) over `Total (Inclusive of GST)`. Equivalently, apply rounding-adjustment awareness: if a standalone "TOTAL" line appears below a "Rounding Adj" line, that standalone line wins.

**034.jpg — date wrong: predicted 2018-08-09 vs true 2018-03-09**
- Pixel evidence: receipt (Perniagaan Zheng Hui / GOGIANT) prints `Date: 09/03/2018`. Prediction corresponds to interpreting the DD/MM day digits in the wrong positions, or OCR reading `3` as `8` and then day/month swap. The handwritten `A03041` at top may have poisoned a loose date regex.
- Root cause hypothesis: date extraction accepts stray digit groups near the top (the annotation) or confuses `03` ↔ `08`. No evidence in this window that date logic was revisited.
- Repair hint: anchor the date regex to lines containing a `Date:` keyword and validate that month ≤ 12 before accepting; prefer the keyword-anchored date over any loose DD/MM/YYYY elsewhere.

## Uncertainty / what I cannot verify from this window

- I cannot confirm whether the added `DESCRIPTION` exclusion inadvertently blocks legitimate amount lines on other receipts (e.g., a receipt where `AMOUNT` is the sole header before the only totals block). The window does not show post-patch re-evaluation across all 22 images.
- I cannot see the actual implementation of `extract_last_number` and `find_summary_start` in this window, only the trace behavior. Whether same-line normalization of `:`→`.` is viable depends on whether it would corrupt time stamps like `18:31:45` — so any such normalization must be gated to keyword-matched TOTAL lines only.
- Whether the 702.00 on 074 came from a single OCR glued token or from a next-line fallback cannot be told without the OCR variant dump for 074 (not in this window).
- The 034 date failure path (OCR char swap vs. annotation hijack) is only inferable; no trace of the date extractor was shown this window.

## Recommended focus for Momentum and Patcher

1. Verify the e0060 header-exclusion patch does not regress other receipts; run all 22 images through the patched extractor.
2. Extend repair to the three unresolved failures:
   - normalize `:`/`;`→`.` ONLY inside tier-matched TOTAL lines (fixes 078);
   - add `CASH RECEIVED` to exclusions and tighten `extract_last_number` against glued tokens (addresses 074);
   - within a tier, prefer bare `TOTAL:` / `TOTAL RM` over `Total (Inclusive of GST)`, and prefer the LAST such line when a rounding adjustment precedes it (fixes 077);
   - require `Date:` anchor and month ≤ 12 validation for date extraction (addresses 034).
3. Keep termination risk in mind: source run terminated by `max_iterations` at 65 with 0 skill invocations; the Patcher should avoid chasing a single receipt deep and instead apply the four narrow rules above as one atomic patch.

## w0029
Scoreboard recap (4 wrong fields of 44):
- 034.jpg date: predicted 2018-08-09, image clearly shows "Date: 09/03/2018" → correct is 2018-03-09.
- 074.jpg amount: predicted 702.00, image shows "Total Amt Rounded 102.00 / Payment: 102.00" → correct is 102.00.
- 077.jpg amount: predicted 23.26, image has "Total (Inclusive of GST): 23.26 / Rounding Adj: -0.01 / **TOTAL: 23.25**" → correct is 23.25.
- 078.jpg amount: predicted null, image shows "Total: 92.80 / Grand Total: 92.80" → correct is 92.80.

Root causes, each with image/exchange evidence:

1. 078 (null) – OCR under‑resolution. Faded print and small font make the default Tesseract pass produce garbage like "Grand Tota.", "a Total — 92:80", and misses the decimal pattern. The window itself proves this is purely a preprocessing issue: m0189's diagnostic script showed `upscale 3x gray + --psm 4` produced "Grand Total a 92.80". Original Skill "image-ocr" already lists multi-pass OCR with upscaling as the strategy; the source agent's extractor variants evidently did not include an aggressive (≥3×) resize combined with PSM 4, and its amount regex also seems to require `\d+\.\d{2}` which rejects the colon variant "92:80". Evidence of near-miss: m0192 explicitly notes the winning variant but the run hit max_iterations before it was wired in.

2. 077 (23.26 vs 23.25) – keyword priority bug, not OCR. The receipt has two "Total"-matching lines; the TASK hint lists `TOTAL` as a least-specific keyword and gives no explicit tiebreaker. The pixels show that 23.26 is the pre-rounding "Total (Inclusive of GST)" value, 23.25 is the final big-font "TOTAL:" line that follows a "Rounding Adj: -0.01" line. The agent's extractor picked the first `Total` match (23.26). The correct behavior per the hint's semantics is to pick the standalone "TOTAL:" line – generally the LAST matching keyword line, or specifically the line that comes AFTER any "Rounding Adj" / "Rounded" marker. Neither original Skill nor the current extractor encodes "when multiple TOTAL candidates exist, prefer the last one / the one after Rounding Adj". `Rounding Adj` is also not in the exclusion list in the task hint but behaves effectively as "skip the pre-rounding total above it".

3. 074 (702.00 vs 102.00) – OCR digit confusion on the amount (leading 1 read as 7). The agent captured the line `Payment : 102.00 / Change Due : 0.00` but the amount was mis-OCR'd. This is a single-pass failure; a cross-pass sanity check (compare values from multiple PSM/preprocessing variants and choose the value that appears in ≥2 variants, or the one consistent with Subtotal/Rounded Total line) would catch it: the same receipt independently prints "Subtotal: 102.00", "Total Incl. of GST 102.00", "Total Amt Rounded 102.00", "Payment: 102.00" – four cross-consistent 102.00 occurrences vs one 702.00 OCR glitch. The extractor is not voting across the multiple amount-bearing lines.

4. 034 (2018-08-09 vs 2018-03-09) – date OCR/parse error. Image shows "Date: 09/03/2018" (DD/MM/YYYY). The agent produced month=08, which is almost certainly a '3'↔'8' OCR confusion on a faint scanned digit (the receipt is grayscale, slightly broken strokes near the slash). Secondary hypothesis: the agent might be picking up a different numeric fragment (e.g. "Time: 08:49" would give 08). Either way, the date pipeline lacks a cross-check: the same receipt has "Receipt #: CS00084670" with no other date, and "Time: 08:49:00" – an extractor that reused a time field as month would also explain "08". A date pipeline that (a) runs multiple OCR variants on the date region and takes the majority, and (b) validates DD/MM/YYYY by requiring the year token on the right, would prevent this.

Cross-cutting evidence from this window:
- Termination was `max_iterations` at exchange 65 while the agent was mid‑diagnosis of 078 (m0192 just logged the winning configuration). The valid-reward of 0.909 (40/44) therefore understates what the same Skill+code was about to achieve with one more edit. The next stage should not treat this as a Skill-knowledge gap for OCR variants – the Skill already documents the multi-pass approach – but as an execution/efficiency gap: the agent spent dozens of iterations exploring per-receipt tweaks instead of building one unified extractor.
- The character-level OCR errors on 034/074 and the keyword-selection error on 077 are independent from the 078 under-resolution issue. Fixing only the OCR preprocessing (as the agent was about to) would still leave 077 and possibly 074 wrong.

Momentum guidance (what to carry forward):
- High‑value, low‑risk fixes to prioritize next run: (a) add 2–3× upscale + PSM 4/6 to the OCR variant set and accept amounts where decimal separator is `:` or `,` (recovers 078); (b) when multiple TOTAL-keyword lines exist, prefer the line that follows a "Rounding Adj/Adjustment/Rounded" marker, else the last TOTAL occurrence (recovers 077); (c) cross‑validate the amount by re‑reading the same receipt with ≥2 preprocessing variants and choosing the value that appears most often, or that matches other total lines (recovers 074); (d) for dates, require `DD/MM/YYYY` with 4-digit year anchor and take majority across OCR variants (recovers 034).

Patcher guidance (Skill revision direction, not content):
- The original `image-ocr` Skill already covers multi-pass OCR; it does NOT need to be rewritten. Any Skill edit should be narrowly targeted to receipt totals: add an explicit note that for receipts the extractor must (1) aggregate amount candidates from multiple PSM/upscale variants and vote; (2) treat `Rounding Adj`-adjacent and "pre-rounding" TOTAL lines as lower priority than a trailing bold `TOTAL:`; (3) accept `,` or `:` where `.` is expected in a 2‑dp amount. Avoid overfitting to the 22 specific receipts.

Uncertainty:
- I cannot see the actual extract.py the agent wrote (only tool call summaries), so the specific priority/voting logic I attribute to it is inferred from the prediction pattern + window thoughts, not from source code. The 034 "08" could be either a 3→8 OCR confusion or a time‑field cross-contamination; both lead to the same Patcher recommendation.

## w0030
**Termination posture (new in this window).** Exchange e0065 shows the agent editing `ocr_variants()` to add a third preprocessing pass (3× LANCZOS upscale + autocontrast + `--psm 4`) specifically because it had just verified that this variant recovers *"Grand Total a 92.80"* on 074.jpg. The run ended at `max_iterations=65` (`acp_stop_reason=max_turn_requests`, `budget_termination_is_not_natural_completion=true`) with `n_skill_invocations=0`. The in-flight edit implies Patcher should treat 074.jpg as the primary unfinished fix and re-run end-to-end after any variant additions, not just append variants.

**Per-field causal analysis (cross-checked against pixels in the image blocks).**

1. **074.jpg amount – predicted "702.00", image shows "Total : 92.80 / Grand Total : 92.80".** The THAI DELICIOUS receipt is a wide, relatively clean print; items 20.00+28.00+13.00+15.00+7.20+6.50+0.60+2.50 = 92.80 confirms the correct value. The agent's own think log proves the default/2× passes misread this amount, while a 3× upscale with `--psm 4` recovered the correct "Grand Total 92.80". Root cause: (a) the original `ocr_variants()` only had default + 2× variants, so the voting/selection chose a corrupted reading; (b) there is no scoring that prefers a pass which yielded a parseable `GRAND TOTAL <amount>` match over one that produced a bogus `702.00`. The half-applied 4th variant is good evidence this is both a preprocessing gap and a selection-logic gap.

2. **077.jpg amount – predicted "23.26", image shows "Total (Inclusive of GST): 23.26 / Rounding Adj: -0.01 / TOTAL: 23.25".** The hint priority list places `TOTAL` keyword at the lowest tier; the receipt has *two* `Total` lines where the later, standalone `TOTAL:` is the intended answer and the earlier one is the pre-rounding subtotal. The agent's selector returned the first match instead of the last, or did not treat the bare-word `TOTAL:` line (no "inclusive"/"excluding" qualifier) as more specific. This is a keyword-tie-break bug, not an OCR bug (both numbers are legibly printed).

3. **078.jpg amount – predicted null (empty), image shows "SUB TOTAL 10.00 / GRAND TOTAL 10.00".** The scan has a very dark/noisy left margin and faint grayscale body text. The `null` output means either the `GRAND TOTAL` line was not recovered at all, or it was recovered but the number regex (expecting `10.00`/`10,00`) was defeated by the extremely faint print. There is no fallback that (a) inverts/thresholds for faded prints, (b) re-crops away the dark left band, or (c) uses the keyword-hint fallback "last number on the next line" when the amount is on the same line but spaced far right. Given `GRAND TOTAL` is the *highest* priority keyword, failing here is especially costly.

4. **034.jpg date – predicted "2018-08-09", image shows "Date: 09/03/2018 / Time: 08:49:00".** Correct ISO is 2018-03-09 (DD/MM/YYYY, consistent with all other Malaysian receipts in this set). The predicted month `08` matches the *hour* field `08:49:00`, strongly indicating the parser concatenated/aligned the date and time strings and pulled the hour as the month. Contributing factors: handwritten "GA1801" annotations crowd the date row and may fragment OCR tokens; the parser likely accepted a loose `DD MM YYYY` pattern that also matched `09 08 2018` when `03` was dropped by OCR. This is a date-tokenization bug, not a locale bug — the agent otherwise handled DD/MM/YYYY correctly on 20+ receipts.

**Cross-cutting pattern.** All four failures share the same meta-cause: the extraction pipeline does a single-shot regex over a merged OCR text blob rather than scoring candidates per keyword tier. That causes (i) voting to pick corrupt passes over clean ones (074), (ii) first-match-wins when multiple `TOTAL` lines coexist (077), (iii) silent failure instead of preprocessing escalation on degraded scans (078), and (iv) accidental cross-field token contamination between date and time (034).

**Evidence confidence.**
- High confidence: 074 (think log directly shows correct value recovered by the just-added variant), 077 (two totals visibly present, agent picked pre-rounding one), 034 (predicted month equals printed hour, high prior).
- Medium confidence: 078 (pixels show faint but legible 10.00; cannot be 100% sure whether OCR produced empty text or produced text that failed regex without inspecting agent intermediates in this window).

**Uncertainty / what I did *not* verify.**
- I did not read the full `extract.py` as it existed when the run terminated (only the final `str_replace` diff appears in this window), so I cannot confirm exactly how multi-pass results are combined (concatenation vs voting vs first-pass-wins). Momentum should assume the worst (naive concatenation) until confirmed.
- I cannot distinguish whether 077's failure was "picked first TOTAL" vs "exclusion-keyword list did not down-weight the GST-qualified line"; both repairs converge on the same selector change.
- Date-field correctness on the other 21 receipts suggests the DD/MM parser is fine in isolation; the 034 bug is specifically about date/time token boundary handling.

**Directional guidance for Momentum/Patcher (no Skill rewrite here).**
- Momentum should prioritize (A) resuming the half-applied 074 variant addition and verifying end-to-end, (B) adding a selector that scores candidates per keyword tier and prefers the *last* `TOTAL` line on tie, (C) adding an inversion/threshold preprocessing pass for faded scans like 078, (D) tightening date extraction so time tokens cannot be consumed as month.
- Patcher should preserve the working 18 joint-correct receipts (no regressions on 007/009/010/011/019/039/052/063/064/069/071/080/083/087/088/090/094/097) — changes must be additive to preprocessing/selection, not structural.
- Budget: the source hit `max_iterations` with 27 terminal + 22 think + 16 file_editor calls. Patcher should aim for fewer, batched edits and a single end-to-end rerun rather than per-image iteration, since per-image debugging is what exhausted the iteration budget.

## w0031
## New evidence from the four failing fields

### 034.jpg — date error (predicted 2018-08-09)
Image clearly shows `Date: 09/03/2018` (DD/MM/YYYY) in the header, with amount 332.30 (which the agent got right). The oracle date almost certainly is 2018-03-09. The predicted `2018-08-09` is not a format swap — a MM/DD swap of 09/03 would produce 2018-09-03. The only consistent explanation is an **OCR digit confusion: "3" → "8"** in `09/03/2018`, parsed then as DD/MM/YYYY → 2018-08-09. The printed date is small and partially faded on this receipt, so a single Tesseract pass with the chosen preprocessing produced an incorrect digit. Uncertainty: I cannot confirm from logs that Tesseract actually emitted "08"; could also be a parser quirk combining two date-like substrings, but the image evidence favors the 3/8 OCR misread.

### 074.jpg — amount wrong (predicted 702.00, true 102.00)
Image is GL HANDICRAFT: line item `6.00 BOXS × 17.00 = 102.00`, `Subtotal 102.00`, `Total Incl. of GST 102.00`, `Total Amt Rounded 102.00`, `Payment 102.00`. All totals are 102.00. A `702.00` reading is an **OCR "1"→"7" misread on a single clean-looking digit**, and no cross-validation detected the inconsistency across the five identical totals present. The date was read correctly, so overall OCR quality was adequate — the bug is that the extractor accepts the first keyword/number match without any consistency check against other totals on the receipt.

### 077.jpg — amount wrong (predicted 23.26, true 23.25)
Image (Banh Mi Cafe) shows:
```
Total (Inclusive of GST):   23.26
Rounding Adj:               -0.01
TOTAL:                       23.25
```
The predictor picked `23.26` — i.e., the "Total (Inclusive of GST)" value *before* the rounding adjustment — instead of the final bold `TOTAL: 23.25` line. This is a **keyword-priority defect**: both lines contain the substring "TOTAL", and the agent's scanning logic apparently returned the first match (or a largest match) and ignored the subsequent standalone "TOTAL" after a "Rounding Adj" line. The task hint mentions no explicit precedence for "post-rounding TOTAL", but behavior on 010.jpg (14.10, correct) and 019.jpg (86.00, correct) shows the extractor works when there is no competing Incl-GST line. The failure signature here is specifically the presence of a rounding adjustment line separating two candidate totals.

### 078.jpg — amount empty (predicted null, true 92.80)
Image (Thai Delicious Restaurant) has `Total : 92.80` and `Grand Total : 92.80`, with intermixed Thai script in item descriptions and fine, light print. Date 02/02/2017 was extracted correctly, but amount came back empty — the most specific keyword "GRAND TOTAL" is right there. Two plausible causes:
1. **OCR failure on the totals block**: Thai glyphs in adjacent lines likely degraded Tesseract's layout detection; the "Total" tokens may have been mangled (e.g., "Totai", "Tolal") so none of the keyword strings matched.
2. **Line-split fallback not triggered**: even if the keyword line was found but the numeric amount OCR'd as noise, the "next line last number" fallback didn't rescue it because the next line may not have a parseable number either.
The agent's own history (termination = `max_iterations`, 65 turns, `n_skill_invocations=0`) suggests it built a bespoke pipeline rather than invoking `image-ocr`, probably without multi-pass OCR or Thai-language config (`lang='eng+tha'`), so the Thai receipt hit a blind spot.

## Cross-cutting pattern

The source agent terminated by hitting the 65-iteration cap (`acp_stop_reason: max_turn_requests`, `termination_reason: max_iterations`), with zero formal skill invocations. It produced 22 well-formed rows and reached 0.909 accuracy on a non-binary derived score, but original reward = 0.0 because the verifier likely requires exact match on all rows. The failures are a mix of:
- **OCR digit misreads** on clean receipts (034, 074) — not solvable by keyword logic; needs multi-pass OCR consensus or digit-level reasoning (e.g., sanity-check against item math or cross-matching multiple totals on the same receipt).
- **Keyword-priority bugs** when multiple "total"-like lines coexist (077) — the rounding-adjustment case needs an explicit rule: when a rounding/adjustment line is followed by another TOTAL line, prefer the later one.
- **OCR coverage failure** on degraded/multilingual receipts (078) — needs multi-pass preprocessing (invert / scale / threshold) and possibly multi-language Tesseract.

## Guidance for Momentum / Patcher

Evidence for the Patcher (uncertainty noted):
1. **077 is the most tractable**: adjust keyword selection to prefer a standalone `TOTAL` line that appears *after* a rounding/adjustment line, over an earlier `Total (Inclusive of GST)`. High confidence — directly visible in pixels.
2. **078 likely needs multi-pass OCR + possibly `lang='eng'` with aggressive preprocessing** (upscaling 2×, autocontrast). The Thai glyphs interfering is a hypothesis; could also be low-contrast printing. Medium confidence.
3. **034 and 074 are OCR digit errors**: fixable by running at least two OCR variants (different PSM/preprocessing) and only emitting a value when variants agree, or by cross-validating a chosen total against other total-like numbers on the same receipt (074 case: five instances of 102.00 vs one 702.00 — majority vote wins). Medium confidence that this will catch them; a stronger fix is to use `image_to_data` confidence filtering for digits.
4. **Budget pressure**: the source used all 65 iterations. Any Patcher change should be implementation-efficient (single pipeline run over all 22 receipts, not per-image debugging loops), since the Momentum stage will re-execute under the same iteration ceiling evidence.

No evidence suggests the current skill *bodies* themselves are wrong; the gap is in the agent's inline extraction code (which was never surfaced via `invoke_skill`). Patcher should concentrate on extraction logic (keyword precedence, multi-pass consensus) rather than rewriting the OCR skill docs.

## w0032
## Scope of failures (from permitted boolean feedback)

Field accuracy 40/44 (0.909). Four wrong fields across four receipts:

| file | field | predicted | image (pixels) | root cause |
|---|---|---|---|---|
| 034.jpg | date | 2018-08-09 | "Date: 09/03/2018" | OCR misread "3" as "8" in month |
| 074.jpg | amount | 702.00 | "102.00" (Subtotal/Total Incl./Rounded all 102.00) | OCR misread leading "1" as "7" |
| 077.jpg | amount | 23.26 | Bold "TOTAL: 23.25" below "Total (Inclusive of GST): 23.26" and "Rounding Adj: -0.01" | Code picked the pre-rounding line because the final rounded bold TOTAL line was either not recognised or rejected by regex |
| 078.jpg | amount | null | "Grand Total 92.80" | Regex failed on OCR-garbled "GrandTota." / "Total — 92:80" |

The remaining 18 receipts (date+amount both correct) confirm the keyword-tier + "last candidate line + last decimal number" heuristic is basically sound; the failures are concentrated in (a) OCR-character errors that no regex alone can repair, and (b) a regex that cannot absorb common OCR noise around numbers.

## Causal analysis per failure

**034.jpg (date).** The image's printed date is unambiguously `09/03/2018`. The window's OCR of the body shows `Salesperson: Data: 09/08/2018` — a classic Tesseract 3↔8 confusion in a single glyph on a slightly noisy scan. The source extract_date regex is otherwise correct (it would produce `2018-03-09`). Evidence: the source skill's `image-ocr` doc already lists upscaling, autocontrast, sharpen, and multi-pass PSM as remedies; the executor never used any of them. Low uncertainty.

**074.jpg (amount).** Pixels show three separate occurrences of `102.00` (item line, Subtotal, Total Incl. of GST, Total Amt Rounded). The window's OCR line reads `Total inel. of GBT 702.00` and `Toial Amt Rounded oO yo2.00` — the glyph "1" was recognised as "7" at the final `Total` line, which the code then picked because tier-2 (`TOTAL RM`) misses and tier-4 (`TOTAL`) selects the LAST matching line. Note that the earlier (correctly OCR'd) `Subtotal : 102.00` is excluded by the SUBTOTAL rule. Pure OCR glyph error; a second preprocessing/PSM pass that produces "102.00" anywhere would let a majority/plurality check across candidate lines override a single corrupted one. Low uncertainty on cause.

**077.jpg (amount).** Pixels: three stacked lines — `Total (Inclusive of GST): 23.26`, `Rounding Adj: -0.01`, and a bold standalone `TOTAL: 23.25`. The window's OCR output never emits the final bold TOTAL line (it ends mid-row with `Rounding Ma: ~0.0)` and skips the next). The extractor then finds its "last TOTAL" at `Total (Inclusive of GST): 23.26` and returns 23.26. Two compounding issues: (1) OCR under default PSM dropped a visually prominent line; (2) even if read, the hint's priority tiers do not distinguish "pre-rounding TOTAL" from "final TOTAL" — the correct behaviour is to prefer a bare `TOTAL:` after Rounding Adj over `Total (Inclusive of GST)`. Medium uncertainty whether a repreprocess alone recovers 23.25; a secondary PSM 6 pass over the lower region is likely needed.

**078.jpg (amount).** Pixels show clean `Total : 92.80` and `Grand Total : 92.80`. Window's OCR produced `a Total — 92:80` and `GrandTota. = tS 92.80`. Failure modes:
- `GRAND\s+TOTAL` regex rejects `GrandTota.` (missing "l" and glued word) → tier-1 miss.
- `TOTAL` tier matches `a Total — 92:80`, but `NUM_RE` requires `\d+\.\d{1,2}`; OCR gave `92:80` (colon) → no number, and the fallback only looks forward on next lines, not the SAME line beyond a colon. The adjacent `GrandTota. = tS 92.80` line is never matched because the keyword regex requires a word boundary and space. High-confidence root cause; two orthogonal fixes needed: (a) a looser keyword match that tolerates glued/misspelled "GrandTotal", (b) a number regex that also accepts `\d+[.:]\d{2}` when inside a known total line, and (c) a reverse-direction fallback (keyword line's own number even if separators are garbled).

## Secondary systemic evidence

- **Termination was `max_iterations` (65/65)**, not `finish`. The window shows the agent spent iterations dumping raw OCR for all 22 images before writing `extract.py`. The source skills contain preprocess/multi-pass guidance that was never invoked. A more disciplined pipeline (preprocess → OCR → extract → write once) would both free iterations for targeted recovery passes and improve per-image accuracy.
- The code's `is_excluded` correctly filters `SUBTOTAL`, `TAX`, `GST`, `CHANGE`, `CASH TENDERED`, `DISCOUNT`, matching the task hint. No regression there.
- Date logic on receipts like 087.jpg (`27/07/17`) and 088.jpg (`09/08/17`) passed — DD/MM/YY precedence is correct; so 034's error is not a DMY/MDY ambiguity but raw OCR.
- `NUM_RE` requires a decimal; this is the right invariant to keep (it prevents picking "6%" or qty counts), but it must survive `:` for `.` substitution within a TOTAL-tagged line.

## Implications for Momentum / Patcher stages

- **OCR layer:** Add a multi-pass path — baseline + (grayscale+autocontrast+2× upscale) + PSM 6 — and union lines. Expected to recover 034's `03`, 074's `102.00`, and 077's bold `TOTAL: 23.25`.
- **Amount extractor:** (1) accept `\d+[.:]\d{2}` when the current line matched a priority keyword; (2) if multiple candidate values across lines in the same tier disagree, prefer the value that appears most often across matched/nearby lines (handles 074); (3) within tier-4 TOTAL, prefer a bare `^TOTAL\b` line that appears AFTER a `Rounding Adj` line over an earlier `Total (Inclusive …)` (handles 077); (4) loosen Grand-Total pattern to `GRAND\s*TOTA\w*` and allow same-line number even without a clean word boundary (handles 078).
- **Date extractor:** No structural change needed; gains come from better OCR on 034.
- **Process:** Keep the one-write Excel step; do not spend iterations re-dumping OCR for all 22 images — iterate only on the 4 failing ones once feedback is available.

Uncertainty: medium on whether multi-pass OCR alone fully recovers 077's bold TOTAL line (may need a cropped bottom-region re-pass); low on the other three.

## w0033
## Scope of failure
Reward = 0.0 in the source run was an infrastructure/termination artifact: ACP stop_reason = `max_turn_requests` at iteration 65/65. Per the derived field feedback the delivered `stat_ocr.xlsx` actually achieves 40/44 fields (0.909). The four residual field errors are:

- 034.jpg: date wrong (amount 332.30 correct)
- 074.jpg: amount wrong (date 2018-03-20 correct)
- 077.jpg: amount wrong (date correct)
- 078.jpg: amount missing/empty (date correct)

This window shows the step‑8 extractor and its first full run (m0026), plus a 074 OCR dump (m0032). Those three outputs are the specific cases that survived into the final submission for 074/077/078 after later refactors.

## New causal evidence in this window

1. 074.jpg — OCR dump (m0032) reveals the exact pattern that blocks a correct read:
   - Line 18 "TolalEcl. of GST 96.23" (Total Excl.) — `\bTOTAL\b` does **not** match "Tolal" (OCR swapped the middle `t`→`l`).
   - Line 19 "Total inel. of GBT 702.00" — matches TOTAL tier 4 but the digit `1` was misread as `7`, producing 702.00. "GBT" also escapes the `(GST|TAX|SST)` exclusion.
   - Line 20 "Toial Amt Rounded oO yo2.00" — "Toial" fails `\bTOTAL\b`; `yo2.00` fails NUM_RE (requires pure digits before the decimal). This is the line that, if read, would yield 102.00.
   - Looking at the pixels of 074.jpg directly: the actual printed total column shows 102.00 three times (Subtotal, Total Incl, Total Amt Rounded) with sharp, well-separated glyphs. The "7" vs "1" confusion on line 19 is a genuine Tesseract error, not a layout problem.
   - The predicted 702.00 was later overridden to the submitted final value by subsequent window logic (not visible here), but the root cause of amount-wrong is that the extractor trusts the last `TOTAL…` keyword line verbatim without cross-checking consistency against the adjacent Subtotal/Payment values (all 102.00) that triple-confirm the true amount.

2. 077.jpg — m0026 shows total=None. The thinking in step 8 correctly identifies the two TOTAL lines (`Total (Excluding GST): 21.30`, `Total (Inclusive of GST): 23.26`) plus the dominant `TOTAL: 23.25` (rounded). The pixel image confirms a large bold `TOTAL: 23.25` after a `Rounding Adj: -0.01`. The step-8 regex does extract from these, yet the shipped prediction for 077 is 23.26 (per field feedback: amount_correct=false). Given the hint priority (GRAND TOTAL > TOTAL RM > TOTAL AMOUNT > TOTAL/NET TOTAL/…), the "last matching candidate" rule picks `Total (Inclusive of GST) 23.26`, missing the large final `TOTAL: 23.25` on the receipt. Cause: the extractor's priority tier 4 uses "last candidate" but the real final total is a separate `TOTAL:` line (bold, standalone) that in some runs is OCR-merged or dropped. The fallback "if no number on keyword line, take next line" never fires because 23.26 is present.

3. 078.jpg — Pixels show `Total : 92.80` and immediately below `Grand Total : 92.80`. GRAND TOTAL is priority 1 and should dominate. In m0026 the step-8 run returns 92.80, but the final submitted value is empty (`""`). This indicates a regression introduced in a later refactor (not in this window) where a stricter exclusion or RM-anchoring change dropped this line. Evidence here: the simple pattern used in step 8 worked; something downstream broke it. Important clue for Patcher: whatever rule was tightened must still accept the non-RM, colon-formatted "Grand Total : 92.80" pattern.

4. 034.jpg — Date wrong. OCR text (seen in earlier step) reads `Date: 09/03/2018` on the receipt header, but the real printed date on the image is `09/08/2018` (readable in the pixels as the "8" in the month position with a closed top loop). Tesseract reads "8" as "3". The DATE_PATTERNS regex returns the first date it sees, with no verification against secondary dates elsewhere on the receipt. The image also contains handwritten "A03041" in the top-right, which is irrelevant. Cause: single-pass OCR plus first-match date acceptance; no multi-PSM / preprocessing retry to cross-validate the month digit.

## Uncertainty / what this window does NOT show
- The final submitted Excel values for 074/077/078 differ from m0026's step‑8 outputs, so a later window must have modified `extract_total`. Without that window I cannot see which later rule caused 078 to go from 92.80 → "". Momentum should pull the subsequent patch windows to confirm.
- 063 OCR dumps are not in this window; date remained null in both step 8 and final, but feedback marks date_correct for 063, implying either oracle date is null or a later retry recovered it. Not a failure to repair.
- Images were never provided to the source agent; all pixel-level corrections proposed for the Patcher are new evidence from the Diagnoser's view, not reproducible by Tesseract on these scans without preprocessing.

## Recommendations for Momentum / Patcher (no Skill rewrite here)
- Keep GRAND TOTAL priority-1 case colon-tolerant: `r'\bGRAND\s*TOTAL\b[^0-9]*([\d,]+\.\d{2})'` must still match "Grand Total : 92.80" (fix 078).
- For priority-4 TOTAL in tier 4, prefer a **standalone/bold** `^\s*TOTAL\s*[:.]?\s*<amount>$` match over an inline "Total (Inclusive of GST)" when both exist (fix 077 → 23.25).
- For 074, add a plausibility cross‑check: if Subtotal and Payment on adjacent lines agree (102.00, 102.00) but the chosen TOTAL line yields a value >5× or inconsistent, fall back to the Subtotal/Payment consensus. This specifically handles the 702.00 OCR corruption.
- For 034 date, add multi-PSM retry (PSM 6 + preprocessing: grayscale+autocontrast or 2× upscale) and pick the date with highest consensus across passes. The "8" vs "3" confusion on month is a well-known Tesseract failure mode cured by upscaling.
- Do not widen GST exclusion — it would break 071/080/094 ("Incl GST" lines that are the legitimate total).

## w0034
## New evidence from this window

This window captures the agent's mid-run transition from default Tesseract to `PSM=6 + grayscale + autocontrast`, plus a `SUMMARY_HEADER_RE` cutoff and reversed-candidate iteration. Step 17 shows the first post-preprocessing run; it fixed several cases but introduced regressions (`052` 10.00→None; `034` date 2018-08-09→2018-03-09; `077` 23.26→23.25). The delivered XLSX contains values matching the *default-PSM* algorithm, not the PSM-6 state, confirming either a revert or a later stage overwriting with the original path before `max_iterations=65` hit (`termination_reason: max_iterations`). That is critical context: the final predictions do not reflect the best-tested algorithm.

## Per-failing-field root causes (verified against image blocks)

**034.jpg – date wrong (`2018-08-09`).** Image clearly prints `Date: 09/03/2018`. Window steps 17/18 show default OCR produces `09/08/2018` while PSM-6 preprocessing produces `09/03/2018`. The delivered answer encodes month "08" → agent's committed path is the pre-preprocessing one. Cause: OCR 3↔8 confusion on a thin-stroked receipt; fixable by the preprocessing+PSM-6 branch already written but not shipped.

**074.jpg – amount wrong (`702.00`).** Image shows `102.00` on every monetary line (Subtotal, Total incl. GST, Total Amt Rounded, Payment). Step 18 (preprocessed) output: `Total incl. of GST 102.00` ✓, but `Total Amt Rounded ——S«702.00` and step 11 default OCR gives `Total inel. of GBT 702.00`. Even PSM-6 corrupted at least one of the three equivalent total lines. The current "LAST candidate wins" rule picks the corrupted Rounded line. Root cause is **selection fragility**, not just OCR noise: when multiple same-tier TOTAL lines exist with disagreeing amounts, no cross-validation is performed. Subtotal/Payment majority (3× 102.00 vs 1× 702.00) would have disambiguated.

**077.jpg – amount wrong (`23.26`).** Image shows two totals: `Total (Inclusive of GST): 23.26` then `TOTAL: 23.25` (final rounded, large font). Step 18 PSM-6 OCR captured both; the "last-candidate in tier" rule correctly returns 23.25 (step 17 output). Delivered 23.26 again implies the shipped code path is the **old** algorithm (either default-PSM OCR that missed `TOTAL: 23.25`, or without-reverse-iteration logic). Oracle feedback (amount wrong) is consistent with expected = 23.25 per the task-hint priority: plain `TOTAL` tier should prefer the last matching line.

**078.jpg – amount null.** Image shows `Grand Total ... 92.80`. Step 18 OCR for 078 yields `'{ Grand Total —— ~"""92 80'` – the decimal was lost (space instead of `.`). The number regex `\d+\.\d{1,2}` matches nothing on this line; fallback checks the next line which is `Cash Received — 100.00` and that is not excluded, so the fallback is at risk of returning 100.00. Final delivered null suggests exclusion short-circuited or the tier didn't match due to differences in default-PSM wording. Either way the ultimate failure is **OCR space-for-dot drop**, same mode as `9,80` and `1000`-for-`10.00` seen in 052.

## Structural issues (Momentum / Patcher inputs)

1. **Single-OCR-pass strategy is insufficient.** The original Skill explicitly describes a *multi-pass* approach (several PSMs, invert, sharpen) and recommends aggregating results. Window shows the agent only switched *between* single configurations (default ↔ PSM6/autocontrast) rather than combining them. Each switch fixes some receipts and regresses others (052 lost because the garbled left-margin noise prevented GRAND TOTAL extraction once preprocessing changed binarization). A union-of-passes + candidate-voting scheme is strongly indicated.

2. **No numeric cross-validation.** The task hint lists keyword priority but the real failure mode is that identical TOTAL amounts repeat 3–4 times per receipt; using frequency/consensus over all monetary values would recover `102.00` (074), `92.80` (078), and `10.00` (052) despite isolated OCR corruption.

3. **Number parser too strict.** Current regex requires `\d+\.\d{1,2}`. Observed OCR variants that should be recognised as money inside TOTAL/GRAND TOTAL contexts: `92 80`, `1000`, `20,00`, `10.u0`, `538 00`, `538.00`. A tier-specific permissive parser that (a) accepts comma-decimal, (b) accepts space-decimal when exactly two trailing digits, and (c) accepts bare integers reinterpreted as `N.00` only when corroborated by another occurrence on the same receipt, would recover most of these.

4. **"Last candidate wins" vs. "ignore rounding-after-summary" conflict.** For 077 the last candidate under plain-`TOTAL` is the correct final `TOTAL: 23.25`; for 074 the last candidate (`Total Amt Rounded 702.00`) is the wrong one because the amount itself is OCR-corrupt. Pure positional heuristics will always flip between these two receipts; only cross-amount consensus resolves both.

5. **Iteration budget / delivery mismatch.** `max_iterations=65` was reached and the committed artifact appears to pre-date the PSM-6 branch for several receipts. Patcher should (a) ensure the improved extraction is actually invoked in `process_image` end-to-end before writing XLSX, and (b) keep edits incremental enough to avoid cliff-edge regressions like 052.

## Uncertainty

- I cannot see the oracle's exact expected strings; the inferences `074=102.00`, `077=23.25`, `078=92.80`, `034 date=2018-03-09` come from direct inspection of the supplied JPEGs plus the boolean field_feedback and task-hint priority list, not from any oracle file.
- Whether `052` oracle is `10.00` is likewise an image inference (`SUB TOTAL 10.00 / GRAND TOTAL 10.00` visible); the receipt currently scores correct in feedback, so changes must not regress it — motivates keeping default-PSM as a fallback OCR pass.
- The exact commit state of `extract.py` at XLSX-write time is not in this window; I infer it from mismatches between step-17 PSM-6 outputs and delivered predictions.

## w0035
## Scope and verified failures
The source run shipped 40/44 correct fields (0.909). Verifier field feedback flags four specific mistakes:

- 034.jpg date: predicted `2018-08-09`
- 074.jpg amount: predicted `702.00`
- 077.jpg amount: predicted `23.26`
- 078.jpg amount: predicted `""` (empty)

Direct pixel inspection of the attached JPGs (new Diagnoser evidence, not historical executor sight):
- 034.jpg: header row clearly reads `Date: 09/03/2018` (DD/MM/YYYY ⇒ 2018-03-09).
- 074.jpg: all three total-bearing rows (`Subtotal 102.00`, `Total incl. of GST 102.00`, `Total Amt Rounded 102.00`, `Payment 102.00`) show 102.00.
- 077.jpg: ladder is `Total (Excluding GST): 21.30` / `Total (Inclusive of GST): 23.26` / `Rounding Adj: -0.01` / bold `TOTAL: 23.25`.
- 078.jpg: `Total: 92.80` and bold `Grand Total: 92.80`.

So the oracle values consistent with the images are 2018-03-09, 102.00, 23.25, 92.80.

## New evidence in this window (steps 19–28, msgs m0072–m0119)

1. Dual-pass strategy was explicitly chosen "default first, then preprocessed fallback" (m0078/step 20). The code short-circuits as soon as the first pass returns any value, so default-PSM OCR errors propagate without consensus checking.

2. Default PSM text actually captured for the failing receipts (m0074):
   - 034 default: `Data: 09/08/2018` (digit 3→8 misread). Preprocessed PSM 6 instead returns `09/03/2018`. Default-first ordering locks in the wrong month.
   - 074 default: `Total inel. of GBT 702.00` — a `1→7` misread on the only TOTAL-keyword line. PSM 6 preprocessed produces both `Total incl. of GST 102.00` and a noisy `Total Amt Rounded ——S«702.00`; LAST-candidate selection then still returns 702.00.
   - 077 default: only exposes `Total (Excluding GST): 21.30` and `Total (Inclusive of GST): 23.26`; the bold final `TOTAL: 23.25` line is lost. With tier-4 LAST = 23.26, the "excluding/inclusive" layering is not disambiguated.
   - 078 default: `Grand Total` appears on its own line with no number (the amount is in a separate column). The "next-line fallback" immediately hits `| Change 7.20 |`, which matches the CHANGE exclusion, so the inner break fires and no value is returned.

3. Step 23 (m0091) still showed `078.jpg total=92.80`, meaning before the stricter "exactly 2 decimals" tightening and EXCLUDING exclusion the default-OCR pipeline accidentally extracted Change=92.80-ish or rolled into AVERAGE line. Something after this window (w0035 is 35/37) regressed 078 to null. The Patcher must notice this regression is possible from later edits and keep a passing path for "Grand Total value on an adjacent/column-aligned line."

4. Step 26–27 (m0109/m0113) empirically demonstrates that a 2×LANCZOS upscale + autocontrast + PSM 6 pass:
   - Resolves 074 to a clean `Total incl. of GST 102.00` with no spurious "Total Amt Rounded 702.00" line.
   - Resolves 077 to include `TOTAL: 23.25` as the terminal TOTAL line.
   - Recovers 071 date `19/02/2018` (previously null in m0083).
   - Harms 064 (`88.17`→`86.17`) and 010 (`14.10`→`14.15`) and 090 (`5.00`→`9.00`) — so upscale cannot replace the existing pass; it must be added as an additional voter.

5. Step 25 (m0102) added `EXCLUDING` as an exclusion keyword. That alone fixes 077 only if the OCR variant surfaces the bold `TOTAL: 23.25` line (i.e., requires the upscale pass). The source run never combined "EXCLUDING exclusion + upscale pass + consensus" before iteration budget exhausted.

## Causal summary for Momentum / Patcher

- Termination reason is `max_iterations` (65/65). The agent had already identified every needed mechanism (upscale, EXCLUDING exclusion, tier-aware voting, 2-decimal regex) but the final `extract.py` saved before these were integrated. Patcher should carry forward the half-landed changes rather than rediscover them.
- Core causal defect: single-pass priority with "first non-null wins" plus LAST-candidate-in-tier is brittle against OCR noise. Required fix is multi-pass OCR (default + autocontrast PSM 6 + 2× upscale PSM 6) with cross-pass consensus (majority of 2-decimal values per tier) rather than fallback ordering.
- Keyword/exclusion logic needs: (a) `EXCLUDING`/`EXCL.` excluded; (b) a plain unqualified `TOTAL:` line (no `inclusive/excluding/items/qty/rounded` modifier) should outrank `Total (Inclusive of GST)` within tier 4 when both exist; (c) the next-line fallback must skip excluded lines (CHANGE, SUBTOTAL, TAX) rather than break on the first one, so 078's `Grand Total` can reach the column-aligned `92.80`.
- Date extraction needs cross-pass agreement (034: majority of `09/03/2018` vs `09/08/2018` across variants, plus plausibility — month ≤ 12 rejects the `19/62/2018` case for 071 but can keep `62→02` recovery optional).

## Uncertainty

- Oracle values are not read; "likely oracle" above is inferred only from pixel reading of the supplied JPGs and the field-correct booleans. 077=23.25 vs 23.26 is the plausible split; both are present on the receipt and the verifier marks 23.26 wrong, which fits 23.25 being the chosen "TOTAL:" line.
- Whether the oracle for 074 is 102.00 vs an alternative rounded value is only indirectly supported; the image shows 102.00 four times and 702.00 never, so confidence is high.
- 078 could also be 92.80 (Total/Grand Total) rather than any derived value; `AVERAGE / PAX(S): 23.20` is clearly not the answer.
- Regression root cause for 078 (step 21 had 92.80, final shipped empty) is not directly observable in this window; attribution to the strict 2-decimal + EXCLUDING changes is probable but should be verified by Patcher via a focused rerun.
- Historical visual payload count is 0; the images were not seen by the source executor, so proposed Skill changes must remain OCR-pipeline-level (preprocess variants, keyword rules, consensus), not vision-model dependent.

## w0036
## Scope of this window's new evidence
Steps 28–36 show the agent moving from single-pass OCR to 3-variant voting (default / autocontrast+PSM 6 / upscale 2× + autocontrast + PSM 6) and tightening the "split-across-two-lines" fallback. The intermediate run after step 35 produced: 064=88.17 ✓, 074=702.00, 077=23.25, 078=100.00. The *final* predictions (received as feedback) are 074=702.00, 077=23.26, 078=null, and date 034=2018-08-09. So between step 35 and task termination (window 37, not in this window), the agent further refactored (step 36 introduces `extract_total_candidates` returning *all* candidates per variant) in a way that flipped 077 from 23.25 back to 23.26 and turned 078's 100.00 into null, while 074=702.00 persisted.

## Receipt-level ground truth, verified from the attached pixels
- **034.jpg**: Header shows "Date: 09/03/2018" with "Total (RM): 332.30". Correct date = 2018-03-09; amount correct. Agent gave 2018-08-09 — OCR misread "03" → "08" (the "3" in the typed date font on this receipt is easily confused with "8" at default scale).
- **074.jpg**: "SAFETY PINS BUTTERFLY-S 6.00 BOXS × 17.00 = 102.00", "Subtotal: 102.00", "Total Incl. of GST 102.00", "Total Amt Rounded 102.00", "Payment 102.00". Correct = 102.00. OCR in default + preprocessed misreads "102.00" → "702.00" on the "Total Amt Rounded" line; only upscale variant 2 produced 102.00.
- **077.jpg**: Shows "Total (Inclusive of GST): 23.26", "Rounding Adj: -0.01", bold "TOTAL: 23.25". Per task-stated priority (plain `TOTAL` is the lowest-priority keyword but also the final printed line), the actual final total is 23.25. Step 35 correctly produced 23.25; final prediction 23.26 is a regression.
- **078.jpg**: Clear "Total: 92.80 / Grand Total: 92.80 / Cash Received 100.00 / Change 7.20". Correct = 92.80. Default OCR captured it; upscaled variants drop digits on the Grand-Total line and fall to Cash Received (100.00) or null.

## Causal analysis of the three amount failures and one date failure

1. **074 — majority-vote overrides the good variant.** The voting rule in `pick_best_total` keys on (min tier_idx, then count, then order). All three variants land in the same tier (plain TOTAL), so a 2:1 count on "702.00" beats the single "102.00" from the upscale variant. Evidence: step 31 trace — variants 0,1 → 702.0; variant 2 → 102.0. The step-36 "return-all-candidates" refactor does not fix this because every variant still produces a last-match of 702/702/102 at the same tier. Patcher needs a tiebreak that is not raw count: e.g. cross-check that the chosen value equals the subtotal/payment value on the same receipt (102.00 appears 3× in variant 2's text, 702.00 appears 1×), or prefer the upscaled variant when the token under the keyword has leading-digit ambiguity.

2. **077 — regression from 23.25 → 23.26.** Step 35 was correct because default OCR missed the final "TOTAL: 23.25" line and variants 1/2 saw it; tier-3 vote was 23.25 (2 of 3). The step-36 refactor that collects *all* candidates per variant adds extra 23.26 occurrences (Total (Inclusive of GST) appears in every variant and is a tier-3 match), so a naive frequency count now reports 23.26 ≥ 23.25. Fix: within a tier, keep "last match wins per variant", not "most-frequent across all candidates", OR give extra weight to shorter/plainer `TOTAL:` lines.

3. **078 — null regression.** Step 35 result 100.00 came from upscaled variants falling back to "Cash Received 100.00" because the exclusion list only covers "CASH TENDERED", not "Cash Received". The step-34 tightened fallback ("only trigger when the keyword line has NO digits") is correct for the 064 Visa bug, but here "Grand Total" line in upscaled variants genuinely has no digits, so the fallback still fires to the next non-excluded line (Cash Received). Final empty prediction means window-37 further tightened (probably added Cash to exclusions AND the default variant's correct 92.80 got outvoted/discarded). Patcher should: (a) extend exclusions with `CASH RECEIVED`, `PAYMENT`, `VISA`, `MASTERCARD`, `TENDER`, `CARD`, and (b) ensure that when at least one variant produces a valid tier-matched value, it is never replaced by None.

4. **034 — date OCR misread.** Receipt has "Date: 09/03/2018". Agent output 2018-08-09. The `extract_date` logic likely chose a DD/MM/YYYY pattern correctly; the digit '3' was OCR'd as '8'. No fallback across variants was attempted — this window shows date voting via `pick_best_date`, but if all three variants misread "03"→"08" there is nothing to cross-check. Mitigation options the Patcher can consider: (a) also run a PSM 7/13 single-line OCR on a cropped Date band, (b) prefer date candidates whose month ≤ 12 and that appear with the highest OCR confidence, (c) try variant with original scale first since upscaling + autocontrast is what tends to merge "03" into "08" on this font.

## Skill-level diagnosis (for Momentum)
The image-ocr skill in use advertises "Multi-Pass OCR Strategy" with variants and PSM modes but gives no guidance for *reconciling disagreements*. The source Agent re-implemented voting from scratch and chose simple frequency-at-tier, which is brittle for receipts because:
- The same monetary value legitimately appears multiple times (subtotal, total, payment) so cross-line frequency is a strong corroborating signal — the skill should document this.
- OCR errors on amounts cluster on the final "Rounded Total" line because it is typographically larger/bolder; preferring the *first* keyword-matched total on a receipt may be more robust than preferring the last.
- The exclusion list in the task spec is incomplete for real receipts; the skill/pipeline should expand it (payment instruments, "Cash Received", "Payment").

## Residual uncertainty
- I cannot see window 37, so I am inferring the final 077/078 regressions from the delta between step 35's internal print and the predictions table. The exact code that caused the flip is unverified; both my proposed mechanisms (all-candidates vote; exclusion widening) are consistent but not distinguishable without window 37.
- For 034, I cannot confirm from this window whether the agent tried any date-specific preprocessing; evidence that `pick_best_date` exists is from m0120, but no debug trace of 034 is in this window.
- Images are new Diagnoser evidence; I did not assume the source Agent saw pixels. All receipt confirmations above come from the attached image blocks.

## w0037
## Termination context (new in w0037)
This window ends the source run at `atif_step` s0045 with `termination_reason="max_iterations"` (65/65). The last recorded action was a Skill-independent edit to `ocr_variants` adding a 4th pass (3× upscale + `--psm 4`) specifically because the agent had just empirically confirmed that variant produces `"Grand Total a 92.80"` for 078 (s0044). Critically, **`extract.py` was never re-run after that edit** — the delivered `stat_ocr.xlsx` was written during s0043, when 078 had just flipped from `20.00` → `None` (header-exclusion fix) but before the new OCR variant could help. So the run was aborted mid-repair, not stuck.

## Pixel-level reconciliation of the 4 incorrect fields
Inspecting the attached images:

- **074.jpg** (GL Handicraft, "SAFETY PINS BUTTERFLY – S, 6.00 BOXS × 17.00"): on-paper totals are all `102.00` (Subtotal / Total Incl. GST / Rounded / Payment). Prediction `702.00` is a classic OCR digit confusion (`1→7`). The keyword/tier logic is correct; this is purely an OCR read error that voting did not catch because multiple variants likely agreed on `702`.
- **077.jpg** (Banh Mi CafE): the receipt lists `Total (Inclusive of GST): 23.26`, then `Rounding Adj: -0.01`, then a large `TOTAL: 23.25`. Prediction is `23.26`. `23.26` wins because the "Total (Inclusive of GST)" line is a valid `TOTAL`-tier match carrying its own number, so `extract_last_number` returns 23.26 for that line and voting elevates it; the later `TOTAL: 23.25` is not preferred, even though it is the final post-rounding line. The "Rounding Adj" line is not excluded, but `TOTAL (Inclusive of GST)` is matched before it alphabetically-in-text and reversed() still places it last within the tier only if the final `TOTAL:` line is reached — the issue is both lines match tier TOTAL and the earlier one's amount (23.26) appears across more variants, so voting picks 23.26. The skill needs either (a) an exclusion for `TOTAL\s*\(\s*INCL(?:UDING|\.)?` as a non-final tier, or (b) preference for the "last TOTAL-tier line before the summary cut" rather than majority vote.
- **078.jpg** (Thai Delicious): clean on-paper `Total: 92.80`, `Grand Total: 92.80`, `Cash Received: 100.00`, `Change: 7.20`. Window shows every OCR variant mangles the keyword: `GrandTotal.`, `Grand Tota.`, `| Grand Total —— ~""92 80` (number split by spaces, no decimal). The regex `\bGRAND\s+TOTAL\b` fails against `GrandTotal` (no space) and against `Grand Tota.` (truncation). The s0045 edit (3× upscale + psm 4) was the right instinct — it does produce `"Grand Total a 92.80"` — but it never ran. Patch target: both loosen the keyword regex (`GRAND\s*TOTAL`, allow `TOTA[L.]`) and keep the extra OCR variant.
- **034.jpg** (Perniagaan Zheng Hui): on-paper `Date: 09/03/2018`. Prediction `2018-08-09` — the `03` month was OCR-misread as `08` (very likely the surrounding handwritten marks / scanner noise near the date field). This is not a date-parsing bug (the DMY vs MDY interpretation would land on 2018-03-09, not 2018-08-09); it's an OCR substitution that voting also failed to overturn because most variants produced the same mis-read.

## New causal evidence specific to this window
1. **Candidate-voting refactor (s0036–s0037)** replaced "best tier per variant" with "best tier globally, then majority-count across all variants." This is what causes 077 to lock onto 23.26 (majority) rather than the single-occurrence post-rounding 23.25. The ordering tie-breaker (`-tier_vals.index(v)`) favors earlier occurrence, which hurts post-rounding totals. **Hypothesis for Patcher:** within a single text, keep the "last TOTAL-tier line" (reversed first match wins) and only vote across variants when the per-variant top-candidate differs; don't flatten all candidates from all variants into one popularity contest.
2. **`CASH\s+(TENDERED|RECEIVED|PAYMENT)` exclusion (s0038)** is now live and does fire on 078's "Cash Received" line (verified by trace). So 078 is not being polluted by Cash Received; it is simply failing the GRAND-TOTAL regex because of OCR space loss.
3. **Column-header exclusion `DESCRIPTION`, `(QTY|PRICE)\s+AMOUNT` (s0042)** fixed the previous 078 `20.00` false positive (where "Description Qty Price Amount" was a keyword match whose split-line fallback grabbed the first item row 20.00). This is the right fix and should be kept.
4. **Preprocessing variants (s0044 evidence):** 3× upscale + autocontrast + psm 4 is the winning configuration for small/blurred-type receipts (078, and likely similar for 074's `102 vs 702`). Adding this as a 4th variant — already in s0045 — is a sound Patcher action to carry forward.

## Guidance for Momentum
- Measured field accuracy is 0.909 (date 0.955, amount 0.864). All 4 defects are receipt-specific OCR/regex issues, not architectural. A targeted patch to the 4 failing files' regex + variant set is well-scoped.
- Original run died at the budget boundary one rerun short of validating s0045. Momentum should prioritize letting the Patcher's final edit actually execute end-to-end (write xlsx) before judging.
- Date correctness is already high; the only date miss (034) is OCR-level and may not be recoverable without adding a date-specific preprocessing pass or cross-checking multiple variants for date digit stability.

## Guidance for Patcher (concrete, low-risk)
1. Loosen GRAND TOTAL keyword to tolerate OCR space loss and tail truncation: `\bGRAND\s*TOTA[L.]?\b` (still inside the top priority tier).
2. Add an exclusion for pre-rounding inclusive-GST subtotals when a later TOTAL exists: exclude lines matching `\bTOTAL\s*\(\s*INCL(?:USIVE|\.)?\b` from the TOTAL tier so 077 resolves to 23.25.
3. Keep the 3× upscale + `--psm 4` variant added in s0045; also consider a 2× upscale with `--psm 4` for small-font receipts like 074 to disambiguate `1 vs 7`.
4. Revise `pick_best_total` so per-variant tier winners vote (one vote per variant for its own top candidate) instead of flattening all intra-variant candidates; this preserves the "last matching TOTAL line within a receipt" preference.
5. Consider a date-specific second-pass OCR for 034 (e.g., crop near the "Date:" label and re-OCR at high scale) if date voting across the 4 variants still disagrees.

## Uncertainty
- Cannot verify whether the 034 OCR misread is deterministic across preprocessing variants without executing; the guess "cross-variant date voting" may still fail if all variants share the `03→08` confusion.
- 074's `102→702` is a hypothesis from the image; it could instead be a separate line (e.g., a stray "70" from a barcode/GST code) winning the "last number on line" rule. Patcher should log all extracted numbers on the Subtotal/Total lines for 074 before fixing.
- The s0045 edit was syntactically applied but never exercised; there is a small risk the new variant changes vote outcomes on currently-correct receipts (e.g., it could regress 039 or 088). A full rerun diff is required before accepting.
