# SkillAxe JPG diagnosis

## 034.jpg/date

Date extraction likely chose the wrong date string on a dense, small-font receipt; this image contains multiple date-like tokens (e.g., header date/time vs other numeric strings), and the current skills provide no receipt-specific date disambiguation guidance.

Evidence: Field feedback: 034.jpg date_correct=false while amount_correct=true. Visual inspection: 034.jpg is a full-page invoice with many numbers; date appears in a header block (e.g., "Date: 09/03/2018"), but other numeric sequences (receipt no, GST id, etc.) can be misread as dates by OCR. The skill docs do not instruct how to prioritize date candidates (e.g., explicit 'Date' label, dd/mm/yyyy vs mm/dd/yyyy, proximity to 'Time', etc.).

## 074.jpg/total_amount

Total amount extraction likely selected a non-total figure (e.g., subtotal, cash, or another prominent number) or missed a decimal/rounding line; current skills lack robust, receipt-specific total selection heuristics beyond generic OCR.

Evidence: Field feedback: 074.jpg amount_correct=false while date_correct=true. Visual inspection: 074.jpg shows 'GRAND TOTAL'/'TOTAL' style lines and also 'CASH RECEIVED'/'CHANGE' style lines; naive 'last number' or 'largest number' heuristics can fail. The task hint requires skipping exclusion keywords and handling split keyword/amount across lines; skills do not encode these rules.

## 077.jpg/total_amount

Total amount extraction likely confused 'TOTAL' vs 'Total (Inclusive of GST)' vs 'Rounding Adj' and produced a rounded value mismatch (off by 0.01) or selected the wrong adjacent number; skills lack guidance to prefer the final payable amount and to handle rounding adjustments.

Evidence: Field feedback: 077.jpg amount_correct=false while date_correct=true. Visual inspection: 077.jpg shows both 'Total (Inclusive of GST)' and a bold 'TOTAL:' with a slightly different value due to rounding. Exact-match scoring means 23.26 vs 23.25 style errors fail. Skills do not instruct to prefer the final 'TOTAL' line after rounding over inclusive/exclusive totals.

## 078.jpg/total_amount

Total amount extraction failed formatting/selection: produced an empty string instead of null or a 2-decimal string; indicates pipeline did not enforce output normalization and null handling for missing/uncertain totals.

Evidence: Field feedback: 078.jpg amount_correct=false; predictions table shows total_amount as "" (empty string). Task requires null when extraction fails, and total_amount must be a string with exactly two decimals when present. Skills do not mention strict output post-processing (empty->null, enforce 2 decimals).

## 034.jpg/date

Date extraction likely mis-parsed a labeled dd/mm/yyyy date due to OCR noise and/or ambiguous numeric tokens; the receipt has an explicit 'Date:' field but OCR can corrupt separators or swap digits, and a robust extractor should prioritize labeled date lines and validate plausibility.

Evidence: Allowed feedback shows 034.jpg date_correct=false while amount_correct=true. The OCR snippet in the run shows a labeled line 'Salesperson: Data: 09/08/2018' (label misspelled as Data), and the image itself shows a clear 'Date: 09/03/2018' in the header block. This is a classic ambiguity: multiple date-like strings can appear (or OCR can mutate one), so selection must prioritize explicit labels and sanity-check formats.

## 074.jpg/total_amount

Total amount extraction likely selected the wrong numeric value because multiple 'Total' variants exist (subtotal, total incl GST, rounded total, payment), and OCR can misread 102.00 as 702.00; extraction should prefer 'Total Amt Rounded'/'Total Rounded' when present and apply plausibility checks against nearby totals.

Evidence: Allowed feedback shows 074.jpg amount_correct=false while date_correct=true. The OCR text contains 'Subtotal : 102.00', 'Total incl. of GST 702.00' (likely OCR error), and 'Total Amt Rounded ... 102.00'. The image shows totals around 102.00. A robust rule should prioritize the rounded total line and also reject outliers that contradict subtotal/rounded totals on the same receipt.

## 077.jpg/total_amount

Total amount extraction likely chose the 'Total (Inclusive of GST)' value instead of the final payable 'TOTAL:' after rounding adjustment; extractor should explicitly prefer the final bold TOTAL line when a rounding adjustment exists and the final total differs.

Evidence: Allowed feedback shows 077.jpg amount_correct=false while date_correct=true. The image shows 'Total (Inclusive of GST): 23.26' and then 'Rounding Adj: -0.01' followed by a bold 'TOTAL: 23.25'. The run prediction used 23.26, indicating the pipeline did not apply a 'final total after rounding' preference.

## 078.jpg/total_amount

Output normalization failure: total_amount was emitted as an empty string instead of null or a 2-decimal string; the task requires null on failure and exact two-decimal formatting on success.

Evidence: Allowed feedback shows 078.jpg amount_correct=false; predictions table shows total_amount as "" (empty string). Task spec: if extraction fails set to null; otherwise must be a string with exactly two decimal places. This indicates missing post-processing/validation at the field level.

## 034.jpg/date

Date disambiguation failure: the pipeline likely selected a secondary date-like token (or OCR-corrupted label line) instead of the primary header date. Receipts/invoices can contain multiple date-like strings (header date, print date, closed date, etc.), and naive “first regex match” can pick the wrong one.

Evidence: Allowed feedback: 034.jpg date_correct=false while amount_correct=true. The image shows a clear header date field (e.g., “Date: 09/03/2018”), but other date-like strings can appear elsewhere or be OCR-mutated (e.g., DATE→DATA). The current generic OCR skill does not emphasize label-tolerant date selection and top-of-receipt preference strongly enough to prevent this failure mode.

## 074.jpg/total_amount

Total selection failure due to OCR digit flip/outlier and competing ‘total’ variants: the model selected an implausible total-like number (e.g., 702.00) instead of the payable/rounded total (e.g., 102.00). This happens when OCR corrupts one line and the extractor lacks an outlier rejection / rounded-total preference.

Evidence: Allowed feedback: 074.jpg amount_correct=false while date_correct=true. The receipt contains multiple total-related lines (Total excl/incl GST, Total Amt Rounded, Payment, GST Summary). OCR can misread 102.00 as 702.00; without a plausibility check and explicit preference for “Total Amt Rounded/Total Rounded” over “Total incl GST” when inconsistent, the wrong value is chosen.

## 077.jpg/total_amount

Rounding-line precedence failure: the extractor chose ‘Total (Inclusive of GST)’ instead of the final payable ‘TOTAL:’ after a rounding adjustment, causing an exact-match miss (often by 0.01).

Evidence: Allowed feedback: 077.jpg amount_correct=false while date_correct=true. The image shows a rounding adjustment line (e.g., “Rounding Adj: -0.01”) followed by a bold final “TOTAL: 23.25”, while an earlier line shows “Total (Inclusive of GST): 23.26”. The skill guidance needs an explicit rule to prefer the final total after rounding when present.

## 078.jpg/total_amount

Output normalization failure: total_amount was emitted as an empty string instead of null (on failure) or a two-decimal string (on success). This violates the task’s strict schema and causes exact-match failure even if OCR found the number.

Evidence: Allowed feedback: 078.jpg amount_correct=false; predictions table shows total_amount="". Task spec requires null on extraction failure and exactly two decimals when present. The skill docs should explicitly forbid empty strings and require strict post-processing/validation.

## 074.jpg/total_amount

Total extraction is vulnerable to OCR corruption and to selecting the wrong ‘total-like’ line when multiple totals exist (incl/excl GST, rounded total, payment, item count). The historical run picked an implausible outlier (702.00) that contradicts other nearby totals (102.00). The skill should explicitly recommend (a) a small, receipt-friendly preprocessing+PSM baseline, and (b) a candidate scoring approach that prefers consistent totals (e.g., rounded total / payment) and rejects outliers.

Evidence: Allowed feedback: 074.jpg amount_correct=false. Timeline shows raw OCR without preprocessing produced “Total inel. of GBT 702.00” and “Toial Amt Rounded … yo2.00”, causing the extractor to select 702.00. The same timeline shows that grayscale+autocontrast with PSM 6 yields a clean “Total incl. of GST 102.00”, demonstrating that preprocessing/PSM choice is decisive. Current image-ocr skill mentions multi-pass but does not explicitly elevate a strong default baseline (grayscale+autocontrast + PSM 6) nor a concrete outlier-rejection rule tied to other total-like anchors (payment/subtotal/rounded).

## 077.jpg/total_amount

Rounding precedence failure: when a receipt shows an inclusive total plus a rounding adjustment and then a final bold TOTAL, the payable amount is the final total after rounding. The skill should make this precedence rule unambiguous and operational (prefer final TOTAL after rounding over inclusive total).

Evidence: Allowed feedback: 077.jpg amount_correct=false. Image shows “Total (Inclusive of GST): 23.26”, “Rounding Adj: -0.01”, and final “TOTAL: 23.25”. The historical prediction used 23.26. Current image-ocr skill mentions rounding handling, but this failure indicates the rule needs to be stated as a hard preference when a rounding adjustment line exists and a later TOTAL exists.

## 078.jpg/total_amount

Schema/normalization failure: total_amount was emitted as an empty string instead of null, violating the task’s strict output requirements. The skill should explicitly require a final validation step that converts empty/whitespace-only strings to null and enforces two-decimal formatting only when a numeric value is confidently extracted.

Evidence: Allowed feedback: 078.jpg amount_correct=false; predictions table shows total_amount="". Task spec requires null on failure and exactly two decimals on success. Current image-ocr skill warns “Never output an empty string,” but the historical run still produced one; the skill should add an explicit ‘final output validation’ checklist item and a tiny reference snippet to make this hard to miss in implementations.

## 034.jpg/date

Date disambiguation failure: receipts/invoices can contain multiple date-like strings and OCR can corrupt the DATE label (e.g., DATE→DATA). The skill should more strongly instruct label-tolerant matching and top-of-receipt preference, and recommend ranking labeled dates above unlabeled ones even if another date-like token appears elsewhere.

Evidence: Allowed feedback: 034.jpg date_correct=false while amount_correct=true. Prior method history notes OCR label corruption (“Data: 09/08/2018”) and the image shows a clear header “Date: 09/03/2018”. Current image-ocr skill includes label-tolerant guidance, but this miss suggests emphasizing: treat near-miss labels (DAIE/DATA) as DATE labels and prefer the header block date.

## 074.jpg/total_amount

Total selection is brittle when OCR produces a corrupted ‘TOTAL AMT ROUNDED’ line with a wrong digit (702.00) while other anchors (Subtotal/Payment/Total incl GST) consistently show 102.00. The current image-ocr skill mentions outlier rejection, but it doesn’t give an operational, anchor-driven rule that would reliably override a later ‘TOTAL’ candidate when it contradicts multiple independent anchors on the same receipt.

Evidence: Allowed feedback: 074.jpg amount_correct=false. OCR text in timeline shows: 'Subtotal : 102.00', 'Total incl. of GST 102.00', 'Payment : 102.00' but also 'Total Amt Rounded ——S«702.00' and an item line '... 17.00 702.00'. The extractor that prefers the last TOTAL-like line will pick 702.00. A robust receipt heuristic should explicitly: (a) treat Payment/Subtotal as strong anchors, (b) treat ‘Total Amt Rounded’ as final only if it is consistent with anchors, otherwise discard as OCR outlier.

## 077.jpg/total_amount

Rounding precedence ambiguity: receipts can show an inclusive total, a rounding adjustment, and then a final payable TOTAL. The skill states a rounding preference, but it should be made more mechanical: if a rounding adjustment line exists and a later TOTAL exists, always take the later TOTAL (even if earlier ‘Total (Inclusive of GST)’ exists).

Evidence: Allowed feedback: 077.jpg amount_correct=false. OCR text shows 'Total (Inclusive of GST): 23.26', 'Rounding Adj: -0.01', then 'TOTAL: 23.25'. The historical prediction used 23.26, indicating the pipeline did not enforce the hard precedence rule consistently.

## 078.jpg/total_amount

Schema/normalization failure mode: total_amount was emitted as an empty string instead of null. The skill warns against empty strings, but it lacks a concrete ‘final validation’ snippet that implementers can drop in to guarantee compliance (empty/whitespace → None; otherwise enforce two decimals).

Evidence: Allowed feedback: 078.jpg amount_correct=false; predictions table shows total_amount="". Task requires null on failure and exactly two decimals on success. This is a post-processing/validation gap rather than OCR itself.

## 034.jpg/date

Date disambiguation remains vulnerable to OCR label corruption and multiple plausible date-like strings. The skill includes label-tolerant matching, but it should explicitly instruct: when multiple plausible dates exist, prefer the one on a line that also contains other header fields (e.g., Receipt/Invoice No, Cashier, Time) and appears in the header block; treat ‘Salesperson: Date: …’ as a strong header cue even if the label is partially corrupted.

Evidence: Allowed feedback: 034.jpg date_correct=false while amount_correct=true. Timeline OCR shows a header-like line 'Salesperson: Date: 09/03/2018' and prior history indicates alternate OCR readings (e.g., DATE→DATA and different day/month). This is a classic multi-candidate selection problem that benefits from stronger header-context ranking guidance.

## 074.jpg/total_amount

Total selection is brittle under OCR corruption when multiple total-like lines exist; the historical run selected an outlier (702.00) even though other strong anchors on the same receipt (Subtotal/Payment/Total incl GST) agree on a different value. The current image-ocr skill mentions anchor-driven outlier rejection, but it does not explicitly elevate a *mechanical* anchor-consistency override for cases where a high-priority keyword line (e.g., “TOTAL AMT ROUNDED”) is itself OCR-corrupted.

Evidence: Allowed feedback: 074.jpg amount_correct=false. Timeline OCR shows conflicting candidates: Subtotal 102.00, Total incl GST 102.00, Payment 102.00, but also “Total Amt Rounded … 702.00” (OCR digit flip). The agent’s own debugging shows that a different OCR variant (2× upscale + autocontrast + PSM6) removes the corrupted rounded-total line and yields only 102.00 totals, indicating selection logic must (a) try an upscale variant and (b) reject totals that contradict multiple anchors.

## 077.jpg/total_amount

Rounding precedence failure mode: receipts can show an inclusive total, a rounding adjustment, and then a final payable TOTAL. The skill already states a rounding rule, but it should be made even more operational: if a rounding adjustment line exists and a later TOTAL exists, always take the later TOTAL (even if earlier ‘Total (Inclusive of GST)’ exists).

Evidence: Allowed feedback: 077.jpg amount_correct=false. Image shows “Total (Inclusive of GST): 23.26”, “Rounding Adj: -0.01”, then bold “TOTAL: 23.25”. The historical prediction used the inclusive total, indicating the pipeline did not enforce the hard precedence consistently.

## 078.jpg/total_amount

Schema/normalization failure: total_amount was emitted as an empty string instead of null. The skill warns against empty strings and includes a helper, but it should explicitly require a final ‘schema guard’ step (empty/whitespace → None) and also note that some OCR passes may surface nearby non-total anchors (e.g., Cash Received) that must remain excluded even when ‘Grand Total’ is present but numberless.

Evidence: Allowed feedback: 078.jpg amount_correct=false; predictions table shows total_amount="". Task requires null on failure and exactly two decimals on success. Timeline shows cases where ‘Grand Total’ appears without a number in some OCR variants, and nearby ‘Cash Received 100.00’ can be mistakenly selected if exclusions/validation are weak.

## 034.jpg/date

Date disambiguation failure: the pipeline likely selected a secondary date-like token (or OCR-corrupted label line) instead of the primary header date. The skill includes label-tolerant matching, but it should explicitly recommend preferring the *document header’s labeled Date field* over other header-adjacent date-like strings (e.g., salesperson/date-time lines) when multiple plausible dates exist.

Evidence: Allowed feedback: 034.jpg date_correct=false while amount_correct=true. The image shows a clear header ‘Date: 09/03/2018’, while OCR can also produce ‘Data: 09/08/2018’ (label corruption DATE→DATA) on another line. This is a classic multi-candidate selection problem requiring stronger header-label prioritization and plausibility checks.

## 074.jpg/total_amount

Total selection is vulnerable to OCR digit-flip outliers when multiple total-like lines exist; a corrupted high-priority line (e.g., “Total Amt Rounded”) can dominate even when other internal anchors (Subtotal/Payment/Total incl) agree on a different value. The skill should explicitly require an anchor-consistency override and warn against majority-vote across OCR variants without anchor checks.

Evidence: Allowed feedback: 074.jpg amount_correct=false while date_correct=true. Predictions show 074 total_amount="702.00". The run’s own debugging notes OCR variants can produce both 702.00 and 102.00; the receipt image shows totals around 102.00 and includes multiple confirming anchors (Subtotal/Payment/Total incl). This is a classic OCR digit-flip (1→7) where internal consistency beats keyword priority or variant-majority voting.

## 078.jpg/total_amount

Total extraction can fail when the ‘Grand Total’ label is OCR-corrupted (e.g., missing space) and/or the amount uses a non-dot decimal separator (e.g., 92:80). Without robust normalization and label-tolerant matching, the extractor may fall back to non-total payment lines (Cash Received) or emit empty/incorrect values. The skill should explicitly add (a) label-tolerant GRAND TOTAL matching, (b) decimal-separator normalization, and (c) stronger exclusions for cash received/tendered lines.

Evidence: Allowed feedback: 078.jpg amount_correct=false; predictions show total_amount as empty string "". Timeline OCR for 078 shows lines like "a Total — 92:80" and "GrandTota. = tS 92.80" plus "Cash Received 100.00". This demonstrates two failure modes: (1) keyword corruption (GrandTota.) and (2) punctuation corruption (92:80). The task requires null on failure and exact two-decimal formatting on success; empty string violates schema.

## 034.jpg/date

Date disambiguation can fail on invoices with multiple date-like strings and OCR-corrupted labels (DATE→DATA). The skill should more mechanically prioritize the primary header ‘Date:’ field over other header-adjacent date-like tokens and recommend top-of-receipt/header-block preference when multiple labeled candidates exist.

Evidence: Allowed feedback: 034.jpg date_correct=false while amount_correct=true. The provided image shows a clear header date field, while prior method history indicates OCR can produce alternate labeled lines (e.g., ‘Data: …’) that can be mistakenly selected by naive regex-first or majority voting.

## 078.jpg/total_amount

Total extraction can be derailed by (a) column-header lines containing the word “Amount” (e.g., “Description Qty Price Amount”) and (b) OCR punctuation corruption in the total value (e.g., `92:80` instead of `92.80`) and (c) OCR corruption of the keyword itself (e.g., `GrandTotal.` / `GrandTota.` without a space). Without explicit header-line exclusion + tolerant keyword matching + decimal-separator normalization, the extractor may fall back to the next line’s last number (often an item price) or emit empty/None incorrectly.

Evidence: Timeline shows variant 0 matched `AMOUNT` on the column header line and then used the split-line fallback to grab the first item amount (20.00). It also shows lines like `a Total — 92:80` (digits present but not parseable as a decimal) and `GrandTotal. = ... 92.80` (keyword missing space/punctuation). Later debugging shows that a stronger OCR variant (3× upscale + PSM 4) yields `Grand Total a 92.80`, confirming that both OCR configuration and tolerant parsing are needed. Field feedback: 078.jpg amount_correct=false; prediction emitted empty string in the original run.

## 074.jpg/total_amount

Total selection is vulnerable to OCR digit-flip outliers (e.g., `102.00`→`702.00`) when a high-priority keyword line is itself corrupted. A robust extractor must apply a mechanical anchor-consistency override: if Subtotal/Payment/other strong anchors agree, reject contradictory totals even if they appear on a higher-priority keyword line or later in the receipt.

Evidence: Allowed feedback: 074.jpg amount_correct=false; prediction was `702.00`. The receipt image shows multiple consistent anchors around `102.00` (Subtotal/Total incl/Payment), while OCR can produce a spurious `702.00` on a ‘Total Amt Rounded’ line. Prior method history repeatedly notes this exact digit-flip pattern and that preprocessing/PSM changes can remove the corrupted line, implying selection logic must not trust a single keyword line when it contradicts multiple anchors.

## 077.jpg/total_amount

Rounding precedence failure: when a receipt shows an inclusive total, a rounding adjustment, and then a final bold TOTAL, the payable amount is the final total after rounding. The extractor must treat this as an unconditional precedence rule to avoid exact-match misses (often by 0.01).

Evidence: Allowed feedback: 077.jpg amount_correct=false; prediction was `23.26`. The image clearly shows `Rounding Adj: -0.01` followed by a bold `TOTAL: 23.25`, while an earlier line shows `Total (Inclusive of GST): 23.26`. This indicates the pipeline selected the inclusive total rather than the final payable total.

## 034.jpg/date

Date disambiguation failure on invoices with multiple date-like strings and OCR-corrupted labels (DATE→DATA). The extractor should more mechanically prioritize the primary header ‘Date:’ field (top-of-receipt header block) over other header-adjacent date-like tokens (e.g., salesperson/date-time lines), even when both appear labeled due to OCR near-misses.

Evidence: Allowed feedback: 034.jpg date_correct=false while amount_correct=true. Prior method history notes the image contains a clear header `Date:` field and also an OCR-mutated `Data:` line elsewhere; naive regex-first or weak ranking can pick the wrong candidate.

## 074.jpg/total_amount

Total selection failure driven by OCR digit-flip outlier on a high-priority keyword line. The receipt contains multiple strong anchors (Subtotal / Total incl GST / Total Amt Rounded / Payment) that agree, but one OCR pass produced a spurious 702.00 and the pipeline selected it.

Evidence: Allowed feedback: 074.jpg amount_correct=false while date_correct=true; prediction total_amount="702.00". Visual inspection of 074.jpg shows Total incl. of GST 102.00, Total Amt Rounded 102.00, Payment 102.00, and an item line amount 102.00; 702.00 is not consistent with the receipt’s internal totals and is a classic OCR 1→7 digit flip. This indicates selection logic over-trusted a single OCR line/variant and lacked a strict anchor-consistency override.

## 077.jpg/total_amount

Rounding precedence failure: the extractor selected the pre-rounding inclusive total (23.26) instead of the final payable TOTAL after rounding adjustment (23.25).

Evidence: Allowed feedback: 077.jpg amount_correct=false while date_correct=true; prediction total_amount="23.26". Visual inspection of 077.jpg shows 'Total (Inclusive of GST): 23.26', 'Rounding Adj: -0.01', then a bold final 'TOTAL: 23.25'. Exact-match scoring makes this a hard failure unless the rule 'final total after rounding wins' is enforced mechanically.

## 078.jpg/total_amount

Schema/normalization + header-triggered fallback failure: total_amount was emitted as an empty string, and this receipt layout contains an 'Amount' column header that can incorrectly trigger split-line fallback to an item amount unless explicitly excluded. Also, the total can appear as 'Grand Total' with OCR punctuation variants and the amount may be mis-OCRed as 92:80.

Evidence: Allowed feedback: 078.jpg amount_correct=false; prediction total_amount="" (empty string) violates task requirement (must be null on failure). Visual inspection of 078.jpg shows a table header 'Description Qty Price Amount' and later summary lines 'Total: 92.80' and 'Grand Total: 92.80' plus 'Cash Received: 100.00' and 'Change: 7.20'. Without explicit exclusion of header lines containing AMOUNT and strict gating of split-line fallback, an extractor can grab an item amount. Additionally, OCR can render 92.80 as 92:80 and 'Grand Total' as 'GrandTota.'/'GrandTotal.'; normalization and tolerant keyword matching are required.

## 034.jpg/date

Date disambiguation failure on a dense invoice with multiple date-like strings: the pipeline selected a secondary date-like token (or an OCR-corrupted label line) instead of the primary header Date field.

Evidence: Allowed feedback: 034.jpg date_correct=false while amount_correct=true; prediction date="2018-08-09". Visual inspection of 034.jpg shows a clear header block with 'Date: 09/03/2018' and also other date-like tokens/fields (e.g., time, receipt metadata) that can be misread or swapped by OCR. This indicates the date selector needs stronger header-block + label-tolerant prioritization and should not rely on first regex match.

## 034.jpg/date

Date disambiguation failure: OCR text contains multiple plausible date-like strings, including an OCR-corrupted label line (“Salesperson: Data: 09/08/2018”) and the true header “Date: 09/03/2018”. A naive “first match” or “most confident-looking match” selector can pick the wrong one, especially when DATE→DATA corruption occurs.

Evidence: Allowed feedback: 034.jpg date_correct=false while amount_correct=true. In the historical OCR output (m0014), the extracted text includes “Salesperson: Data: 09/08/2018”. Visual inspection of 034.jpg shows a clear header block with “Date: 09/03/2018” near receipt metadata. This indicates the pipeline likely over-weighted the OCR-mutated label line or failed to prioritize the primary header Date field.

## 074.jpg/total_amount

Total selection failure due to OCR digit-flip outlier on a total-like line: the receipt’s internal anchors (Subtotal/Total incl/Payment) are consistent, but one OCR line produced an implausible 702.00 and the pipeline selected it.

Evidence: Allowed feedback: 074.jpg amount_correct=false while date_correct=true; prediction total_amount="702.00". The OCR output (m0017) shows “Subtotal : 102.00”, “Payment : 102.00”, but also “Total inel. of GBT 702.00” and “Toial Amt Rounded ... yo2.00”. The image itself shows totals around 102.00. This is a classic 1→7 digit flip where anchor-consistency should override keyword priority or ‘last total wins’.

## 077.jpg/total_amount

Rounding precedence failure: the extractor selected the pre-rounding inclusive total instead of the final payable TOTAL after a rounding adjustment, causing an exact-match miss (often by 0.01).

Evidence: Allowed feedback: 077.jpg amount_correct=false while date_correct=true; prediction total_amount="23.26". Visual inspection of 077.jpg shows “Total (Inclusive of GST): 23.26”, “Rounding Adj: -0.01”, then bold “TOTAL: 23.25”. The OCR output (m0017) includes the rounding line but the pipeline still chose the inclusive total, implying the rounding precedence rule was not enforced mechanically.

## 078.jpg/total_amount

Schema/normalization failure: total_amount was emitted as an empty string instead of null, violating the task’s strict output requirements. This is a post-processing guard failure independent of OCR quality.

Evidence: Allowed feedback: 078.jpg amount_correct=false; predictions table shows total_amount="" (empty string). Task spec requires null when extraction fails and exactly two decimals when it succeeds. The OCR output (m0017) actually contains total-like lines (“a Total — 92:80”, “GrandTota. ... 92.80”), so even if selection failed, the output should have been null rather than empty string.

## 034.jpg/date

Date disambiguation failure: invoice contains multiple date-like strings; the pipeline likely selected a secondary header-adjacent date/time token (or OCR-corrupted label line) instead of the primary header “Date:” field.

Evidence: Allowed feedback: 034.jpg date_correct=false while amount_correct=true. The image shows a clear header block with “Date: 09/03/2018” near receipt metadata, but the historical prediction is 2018-08-09, consistent with selecting a different dd/mm token elsewhere (or an OCR-mutated DATE→DATA line noted in prior history). This is a classic multi-candidate selection problem requiring label-tolerant matching + header-block preference.

## 074.jpg/total_amount

Total selection failure due to OCR digit-flip outlier and competing total-like lines (incl/excl GST, rounded total, payment). The pipeline selected an implausible outlier (702.00) instead of the internally consistent payable total.

Evidence: Allowed feedback: 074.jpg amount_correct=false while date_correct=true; prediction total_amount="702.00". Visual inspection of 074.jpg shows multiple anchors around 102.00 (Subtotal, Total incl. of GST, Total Amt Rounded, Payment), while 702.00 is a typical OCR 1→7 digit flip. This indicates selection logic over-trusted a single corrupted line/variant and lacked a strict anchor-consistency override.

## 077.jpg/total_amount

Rounding precedence failure: receipt shows an inclusive total, a rounding adjustment, then a final payable TOTAL; the pipeline selected the pre-rounding value (23.26) instead of the final total after rounding (23.25).

Evidence: Allowed feedback: 077.jpg amount_correct=false while date_correct=true; prediction total_amount="23.26". The image clearly shows “Rounding Adj: -0.01” followed by a bold “TOTAL: 23.25”, while an earlier line shows “Total (Inclusive of GST): 23.26”. Exact-match scoring requires a hard rule: final total after rounding wins.

## 078.jpg/total_amount

Schema/normalization failure: total_amount was emitted as an empty string instead of null; additionally, this receipt layout includes an “Amount” column header that can trigger split-line fallback to an item amount unless explicitly excluded, and OCR may corrupt the decimal separator (e.g., 92:80) and the GRAND TOTAL keyword (e.g., GrandTota./GrandTotal.).

Evidence: Allowed feedback: 078.jpg amount_correct=false; prediction total_amount="" violates task requirement (must be null on failure). Visual inspection of 078.jpg shows a table header “Description Qty Price Amount” plus summary lines “Total: 92.80” and “Grand Total: 92.80” and payment lines “Cash Received: 100.00”, “Change: 7.20”. Prior history indicates OCR variants like “a Total — 92:80” and “GrandTota.”, which require decimal-separator normalization and tolerant keyword matching; regardless, empty string must be converted to null.

## 034.jpg/date

Date disambiguation failure on a dense invoice: multiple date-like strings exist (header Date field vs other date/time tokens), and naive selection can pick the wrong one. The historical prediction chose a different dd/mm token than the primary header date.

Evidence: Allowed feedback: 034.jpg date_correct=false while amount_correct=true. Visual inspection of 034.jpg shows a clear header block with a labeled Date field near receipt metadata, while other date-like strings (e.g., time line, other header fields) can appear. Prior history indicates OCR label corruption (DATE→DATA) can create competing labeled candidates.

## 074.jpg/total_amount

Total selection failure driven by OCR digit-flip/outlier on a total-like line: one OCR pass produced an implausible 702.00 even though other internal anchors on the same receipt (Subtotal/Total incl/Payment) agree on 102.00. Selection logic over-trusted a single keyword match and/or split-line fallback.

Evidence: Allowed feedback: 074.jpg amount_correct=false while date_correct=true; prediction total_amount="702.00". The run’s own OCR debug (shown in the packet) demonstrates that grayscale+autocontrast + PSM6 yields a clean “Total incl. of GST 102.00”, while a different OCR output contains “Total ... 702.00” and “Total Amt Rounded ... 702.00”. This is a classic 1→7 digit flip where anchor-consistency should override keyword priority or ‘last total wins’.

## 077.jpg/total_amount

Rounding precedence failure: receipt shows an inclusive total, a rounding adjustment, then a final payable TOTAL; the pipeline selected the pre-rounding value instead of the final total after rounding, causing an exact-match miss (often by 0.01).

Evidence: Allowed feedback: 077.jpg amount_correct=false while date_correct=true; prediction total_amount="23.26". Visual inspection of 077.jpg shows “Rounding Adj: -0.01” followed by a bold final “TOTAL: 23.25”, while an earlier line shows “Total (Inclusive of GST): 23.26”. This requires a mechanical precedence rule: final total after rounding wins.

## 078.jpg/total_amount

Schema/normalization failure: total_amount was emitted as an empty string instead of null. Additionally, this receipt layout contains an “Amount” column header that can trigger split-line fallback to an item amount unless explicitly excluded; OCR may also corrupt the GRAND TOTAL keyword and decimal separator (e.g., 92:80).

Evidence: Allowed feedback: 078.jpg amount_correct=false; prediction total_amount="" violates task requirement (must be null on failure). Visual inspection of 078.jpg shows a table header “Description Qty Price Amount” and summary lines “Total: 92.80” / “Grand Total: 92.80” plus payment lines “Cash Received: 100.00”, “Change: 7.20”. Prior history shows OCR variants like “GrandTota.” and “92:80”, which require tolerant keyword matching + decimal-separator normalization; regardless, empty string must be converted to null.

## 074.jpg/total_amount

Total selection failure driven by OCR digit-flip outlier on a later ‘TOTAL…’ line: the pipeline chose 702.00 even though multiple internal anchors on the same receipt agree on 102.00. This is a classic case where ‘last TOTAL wins’ (or ‘highest-priority keyword wins’) is unsafe when OCR corrupts one line.

Evidence: Allowed feedback: 074.jpg amount_correct=false while date_correct=true; prediction total_amount="702.00". Visual inspection of 074.jpg shows multiple consistent anchors around 102.00 (Subtotal 102.00, Total incl. of GST 102.00, Total Amt Rounded 102.00, Payment 102.00). The historical OCR snippet (w0013/m0068) shows both “Total incl. of GST 102.00” and a corrupted “Total Amt Rounded ——S«702.00”, plus an item line “17.00 702.00” (another corruption). Selection logic that prefers the last TOTAL-like candidate will pick 702.00 unless an anchor-consistency override rejects it.

## 077.jpg/total_amount

Rounding precedence failure: the extractor selected the pre-rounding inclusive total instead of the final payable TOTAL after a rounding adjustment, causing an exact-match miss (often by 0.01).

Evidence: Allowed feedback: 077.jpg amount_correct=false while date_correct=true; prediction total_amount="23.26". Visual inspection of 077.jpg shows “Rounding Adj: -0.01” followed by a bold final “TOTAL: 23.25”, while an earlier line shows “Total (Inclusive of GST): 23.26”. The historical OCR snippet (w0013/m0068) contains both lines, so the miss is selection/precedence, not OCR absence.

## 078.jpg/total_amount

Schema/normalization failure: total_amount was emitted as an empty string instead of null. Additionally, this receipt layout contains an “Amount” column header that can trigger split-line fallback to an item amount unless explicitly excluded; OCR may also corrupt the GRAND TOTAL keyword and decimal separator (e.g., 92:80).

Evidence: Allowed feedback: 078.jpg amount_correct=false; prediction total_amount="" violates task requirement (must be null on failure). Visual inspection of 078.jpg shows a table header “Description Qty Price Amount” and summary lines “Total: 92.80” / “Grand Total: 92.80” plus payment lines “Cash Received: 100.00”, “Change: 7.20”. Historical OCR snippet (w0013/m0068) shows “Description Qty Price Amount” and “{ Grand Total —— ... 92 80” (keyword/spacing corruption) and “Cash Received — 100.00”. This combination can cause (a) header-triggered split-line fallback to an item amount, and (b) failure to parse 92.80 if OCR renders it as 92:80 or splits digits, leading to empty-string output if schema guard is missing.

## 034.jpg/date

Date disambiguation failure on a dense invoice with multiple date-like strings and OCR label corruption (DATE→DATA). The pipeline selected a different plausible dd/mm token than the primary header Date field.

Evidence: Allowed feedback: 034.jpg date_correct=false while amount_correct=true; prediction date="2018-08-09". Visual inspection of 034.jpg shows a clear header block with “Date: 09/03/2018” near receipt metadata. Historical OCR snippet (w0013/m0068) shows “Salesperson: Date: 09/03/2018” and other header fields; prior method history indicates alternate OCR readings like “Data: 09/08/2018”. This is a selection/ranking issue: multiple plausible dates exist and OCR can mutate the label, so the extractor must prioritize the primary header Date field and apply header-context ranking rather than first-match.

## 074.jpg/total_amount

Total amount selection failed under OCR digit-flip corruption: the pipeline chose an outlier total-like value (702.00) even though multiple internal anchors on the same receipt (Subtotal/Total incl/Payment/Total Amt Rounded) agree on ~102.00. This is a selection/robustness issue: trusting a single high-priority keyword line (or “last TOTAL wins”) without anchor-consistency override and without an upscale OCR pass that resolves the digit flip.

Evidence: Allowed feedback: 074.jpg amount_correct=false while date_correct=true; prediction total_amount="702.00". Source-run logs show OCR variants where “Total incl. of GST 102.00” is present but a corrupted “Total Amt Rounded … 702.00” appears later and dominates. The run’s own debugging demonstrates that 2× upscaling + autocontrast + PSM6 removes the corrupted rounded-total line and yields only 102.00 totals, indicating OCR configuration + anchor-consistency are decisive.

## 077.jpg/total_amount

Rounding precedence failure: the extractor selected the pre-rounding inclusive total instead of the final payable TOTAL after a rounding adjustment, causing an exact-match miss (often by 0.01).

Evidence: Allowed feedback: 077.jpg amount_correct=false while date_correct=true; prediction total_amount="23.26". The receipt image shows a rounding adjustment line (e.g., “Rounding Adj: -0.01”) followed by a bold final “TOTAL: 23.25”, while an earlier line shows “Total (Inclusive of GST): 23.26”. This indicates the pipeline did not enforce the ‘final total after rounding wins’ rule mechanically.

## 078.jpg/total_amount

Schema/normalization failure: total_amount was emitted as an empty string instead of null. Additionally, this receipt layout includes an “Amount” column header that can trigger split-line fallback to an item amount unless explicitly excluded; OCR may also corrupt the GRAND TOTAL keyword and decimal separator (e.g., 92:80).

Evidence: Allowed feedback: 078.jpg amount_correct=false; prediction total_amount="" violates task requirement (must be null on failure). Source-run OCR snippets show both (a) a table header line containing “Amount” and (b) total-like lines with punctuation corruption (“92:80”) and keyword corruption (“GrandTota.”/“GrandTotal.”). Without explicit header-line exclusion + tight split-line fallback gating + decimal-separator normalization + final schema guard, the pipeline can either pick the wrong number or emit an invalid empty string.

## 034.jpg/date

Date disambiguation failure: the pipeline selected a secondary date-like token (or an OCR-corrupted label line such as DATE→DATA) instead of the primary header Date field on a dense invoice with multiple date-like strings.

Evidence: Allowed feedback: 034.jpg date_correct=false while amount_correct=true; prediction date="2018-08-09". The image shows a clear header Date field (dd/mm/yyyy) and also other date-like strings; source-run logs include an OCR-mutated label line (“Salesperson: Data: …”) that can be mistakenly prioritized by naive regex-first selection. This is a ranking/selection issue requiring label-tolerant matching plus header-block preference.

## 074.jpg/total_amount

Total selection over-trusted a corrupted TOTAL-like line (OCR digit flip 102.00→702.00) and/or used cross-variant voting without an internal-anchor override. The receipt contains multiple strong anchors (Subtotal/Payment/Total incl/Total Amt Rounded) that agree, so a single conflicting candidate should be rejected even if it matches a higher-priority keyword.

Evidence: Allowed feedback: 074.jpg amount_correct=false; prediction total_amount="702.00". Source-run OCR debug shows conflicting candidates across variants: Variant 0/1 include “Subtotal : 102.00” and “Total incl. of GST 102.00” but also “Total ... 702.00” / “Total Amt Rounded ... 702.00”; Variant 2 yields only 102.00 totals. This is a classic OCR 1→7 digit flip where anchor-consistency must override keyword priority and variant-majority voting.

## 077.jpg/total_amount

Rounding precedence failure: the payable total is the final TOTAL after a rounding adjustment, but selection can incorrectly choose the earlier inclusive total if it simply prefers the first/most prominent TOTAL-like line.

Evidence: Allowed feedback: 077.jpg amount_correct=false; prediction total_amount="23.26". Image shows “Rounding Adj: -0.01” followed by bold “TOTAL: 23.25”, while an earlier line shows “Total (Inclusive of GST): 23.26”. Source-run OCR debug confirms both values appear; the miss is precedence/selection, not OCR absence.

## 078.jpg/total_amount

Two coupled failure modes: (1) schema/normalization bug emitted empty string instead of null; (2) total extraction is vulnerable to AMOUNT column-header lines triggering split-line fallback to item amounts and to OCR corruption of both keyword (GrandTota./GrandTotal.) and decimal separator (92:80).

Evidence: Allowed feedback: 078.jpg amount_correct=false; prediction total_amount="" (empty string) violates task requirement (must be null on failure). Source-run OCR debug shows “Description Qty Price Amount” header, “a Total — 92:80”, “GrandTota. ... 92.80”, plus “Cash Received 100.00” and “Change 7.20”. Other variants show “: Grand Total” without a number, which can cause fallback to nearby payment lines unless tightly gated and excluded.

## 034.jpg/date

Date disambiguation failure: multiple plausible date-like strings exist and OCR can corrupt the DATE label (DATE→DATA), causing selection of a secondary date-like token rather than the primary header Date field.

Evidence: Allowed feedback: 034.jpg date_correct=false; prediction date="2018-08-09". Visual inspection shows a clear header Date field (dd/mm/yyyy) and other header-adjacent date-like tokens; prior history and source-run notes include OCR-mutated label lines (e.g., “Data: ...”) that can be mistakenly prioritized by naive regex-first or weak ranking.

## 034.jpg/date

Date disambiguation failure: the predicted date likely came from a secondary date-like token (or OCR-corrupted label line) rather than the primary header Date field. Dense invoices can contain multiple dd/mm/yyyy strings (header date, print date/time, other metadata), and naive selection (first match / most frequent across OCR variants) can pick the wrong one.

Evidence: Allowed feedback shows 034.jpg date_correct=false while amount_correct=true. The provided 034.jpg image visibly contains a header block with a labeled Date field near the top (e.g., “Date: 09/03/2018”), while the historical prediction is 2018-08-09, consistent with selecting a different dd/mm token elsewhere or an OCR-mutated DATE→DATA line noted in the run history. This indicates a ranking/selection issue, not OCR absence.

## 074.jpg/total_amount

Total selection failure driven by OCR digit-flip outlier: the predicted total_amount (702.00) is inconsistent with multiple internal anchors on the receipt (Subtotal/Total incl/Payment/Total Amt Rounded) that agree on a different value. This happens when a single corrupted high-priority keyword line dominates selection or cross-variant voting without an anchor-consistency override.

Evidence: Allowed feedback shows 074.jpg amount_correct=false while date_correct=true; prediction total_amount="702.00". The 074.jpg image shows several summary lines around 102.00 (Subtotal, Total incl. of GST, Total Amt Rounded, Payment), while 702.00 is a classic OCR 1→7 digit flip. The run history also shows the agent’s fallback/voting logic over-trusted a corrupted line/variant. This is a selection robustness issue under OCR noise.

## 077.jpg/total_amount

Rounding precedence failure: the predicted total_amount likely selected the pre-rounding inclusive total instead of the final payable TOTAL after a rounding adjustment, causing an exact-match miss (often by 0.01).

Evidence: Allowed feedback shows 077.jpg amount_correct=false while date_correct=true; prediction total_amount="23.26". The 077.jpg image clearly shows “Total (Inclusive of GST): 23.26”, then “Rounding Adj: -0.01”, then a bold final “TOTAL: 23.25”. This indicates the pipeline did not enforce a hard precedence rule: final total after rounding wins.

## 078.jpg/total_amount

Schema/normalization failure: total_amount was emitted as an empty string instead of null. Additionally, this receipt layout includes an “Amount” column header that can trigger split-line fallback to an item amount unless explicitly excluded; OCR may also corrupt the GRAND TOTAL keyword and decimal separator (e.g., 92:80).

Evidence: Allowed feedback shows 078.jpg amount_correct=false; prediction total_amount="" violates the task requirement (must be null on failure). The 078.jpg image shows a table header “Description Qty Price Amount” and summary lines “Total: 92.80” / “Grand Total: 92.80” plus payment lines “Cash Received: 100.00”, “Change: 7.20”. The run history shows split-line fallback and keyword/decimal corruption (GrandTota./GrandTotal., 92:80), which can cause wrong selection; regardless, empty string must be converted to null.

## 034.jpg/date

Date disambiguation failure: the predicted date likely came from a secondary date-like token (or an OCR-corrupted label line) rather than the primary header Date field. Dense invoices can contain multiple dd/mm/yyyy strings (header date, print date/time, other metadata), and naive selection (first match / most frequent across OCR variants) can pick the wrong one.

Evidence: Allowed feedback shows 034.jpg date_correct=false while amount_correct=true; prediction date=2018-08-09. Visual inspection of 034.jpg shows a clear header block with a labeled Date field near the top (e.g., “Date: 09/03/2018”), while other date-like strings exist (e.g., time line). Prior history indicates OCR label corruption (DATE→DATA) can create competing labeled candidates. This points to missing/insufficiently enforced ranking: prefer the primary header ‘Date:’ field in the header block over other labeled/near-labeled date-like strings.

## 074.jpg/total_amount

Total selection failure driven by OCR digit-flip outlier: the predicted total_amount (702.00) is inconsistent with multiple internal anchors on the receipt (Subtotal/Total incl/Payment/Total Amt Rounded) that agree on a different value. This happens when a single corrupted high-priority keyword line dominates selection or cross-variant voting without an anchor-consistency override.

Evidence: Allowed feedback shows 074.jpg amount_correct=false while date_correct=true; prediction total_amount=702.00. Visual inspection of 074.jpg shows multiple summary lines around 102.00 (Subtotal, Total incl. of GST, Total Amt Rounded, Payment), while 702.00 is a classic OCR 1→7 digit flip. The historical trajectory also shows OCR variants producing both values; selection must reject candidates contradicting multiple anchors even if they appear on a higher-priority keyword line.

## 077.jpg/total_amount

Rounding precedence failure: the predicted total_amount selected the pre-rounding inclusive total instead of the final payable TOTAL after a rounding adjustment, causing an exact-match miss (often by 0.01).

Evidence: Allowed feedback shows 077.jpg amount_correct=false while date_correct=true; prediction total_amount=23.26. Visual inspection of 077.jpg shows “Total (Inclusive of GST): 23.26”, then “Rounding Adj: -0.01”, then a bold final “TOTAL: 23.25”. This indicates the pipeline did not enforce the hard precedence rule: if rounding adjustment exists and a later TOTAL exists, always take the later TOTAL.

## 078.jpg/total_amount

Coupled extraction + schema failure: total_amount was emitted as an empty string instead of null, violating the task’s strict output requirements. The receipt layout also includes an “Amount” column header that can trigger split-line fallback to an item amount unless explicitly excluded; OCR may corrupt the GRAND TOTAL keyword and decimal separator (e.g., 92:80).

Evidence: Allowed feedback shows 078.jpg amount_correct=false; prediction total_amount="" violates task requirement (must be null on failure). The source-run trace (window w0017) shows the extractor matched the column header line “Description Qty Price Amount” (contains AMOUNT, no digits) and then used split-line fallback to grab the next line’s last number (an item amount 20.00). Additional OCR variants show “GrandTotal.” / “GrandTota.” (missing space/punctuation) and “92:80” (colon as decimal separator), and a stronger OCR variant (3× upscale + PSM4) yields “Grand Total a 92.80”. This demonstrates the need for: (1) explicit exclusion of column-header lines containing AMOUNT, (2) tight gating of split-line fallback so it never triggers on headers, (3) tolerant GRAND TOTAL matching, (4) decimal-separator normalization, and (5) a final schema guard converting empty/whitespace to null.

## 034.jpg/date

Date disambiguation failure on a dense invoice: multiple plausible date-like strings exist (header Date field vs other date/time-like tokens), and the pipeline likely selected a secondary candidate rather than the primary header “Date:” field.

Evidence: Allowed feedback: 034.jpg date_correct=false while amount_correct=true; prediction date=2018-08-09. Visual inspection of 034.jpg shows a clear header block with a labeled Date field near the top (dd/mm/yyyy) and other header-adjacent fields that can contain date/time-like strings. Prior history indicates OCR label corruption (DATE→DATA) can create competing labeled candidates, making naive “first match” or weak ranking brittle.

## 074.jpg/total_amount

Total selection failure driven by OCR digit-flip outlier: the predicted total (702.00) contradicts multiple internal anchors on the receipt (Subtotal/Total incl/Payment/Total Amt Rounded) that agree on a different value; selection likely over-trusted a corrupted high-priority keyword line or ‘last TOTAL wins’.

Evidence: Allowed feedback: 074.jpg amount_correct=false while date_correct=true; prediction total_amount=702.00. Visual inspection of 074.jpg shows multiple summary lines around 102.00 (Subtotal, Total incl. of GST, Total Amt Rounded, Payment), while 702.00 is a classic OCR 1→7 digit flip. This indicates missing/insufficiently enforced anchor-consistency override and/or insufficient use of a stronger OCR variant (e.g., autocontrast/PSM6/upscale) that resolves the corruption.

## 077.jpg/total_amount

Rounding precedence failure: receipt shows an inclusive total, a rounding adjustment, then a final payable TOTAL; the pipeline selected the pre-rounding value (23.26) instead of the final total after rounding (23.25).

Evidence: Allowed feedback: 077.jpg amount_correct=false while date_correct=true; prediction total_amount=23.26. Visual inspection of 077.jpg shows “Total (Inclusive of GST): 23.26”, “Rounding Adj: -0.01”, then bold “TOTAL: 23.25”. This is a deterministic precedence rule failure (final total after rounding should win).

## 078.jpg/total_amount

Coupled extraction + schema failure: total_amount was emitted as an empty string instead of null, violating the task schema. This receipt also contains an “Amount” column header that can incorrectly trigger split-line fallback to an item amount unless explicitly excluded; OCR may corrupt both the GRAND TOTAL keyword and the decimal separator (e.g., 92:80).

Evidence: Allowed feedback: 078.jpg amount_correct=false; prediction total_amount="" (empty string). Visual inspection of 078.jpg shows a table header “Description Qty Price Amount” and summary lines “Total: 92.80” / “Grand Total: 92.80” plus payment lines “Cash Received: 100.00”, “Change: 7.20”. Prior history shows header-triggered split-line fallback and punctuation corruption (92:80) and keyword corruption (GrandTota./GrandTotal.), all of which require explicit header exclusion, tight fallback gating, decimal normalization, and a final schema guard (empty/whitespace → null).

## 034.jpg/date

Date disambiguation failure: the pipeline selected a secondary date-like token (likely from a different header line or OCR-corrupted label) instead of the primary header “Date:” field in the invoice header block.

Evidence: Allowed feedback: 034.jpg date_correct=false while amount_correct=true; prediction date=2018-08-09. Visual inspection of 034.jpg shows a clear header block with “Date: 09/03/2018” near the top, while other date-like strings can appear elsewhere (and prior history shows DATE→DATA corruption). This is a classic multi-candidate selection problem requiring label-tolerant matching plus explicit preference for the primary header Date field (top-of-receipt).

## 074.jpg/total_amount

Total selection failure due to OCR digit-flip outlier and competing total-like lines: the chosen total (702.00) contradicts multiple internal anchors on the same receipt (Subtotal/Total incl/Total Amt Rounded/Payment) that agree on 102.00.

Evidence: Allowed feedback: 074.jpg amount_correct=false while date_correct=true; prediction total_amount=702.00. Visual inspection of 074.jpg shows Subtotal 102.00, Total incl. of GST 102.00, Total Amt Rounded 102.00, Payment 102.00; 702.00 is a typical OCR 1→7 digit flip. The historical run also shows that OCR configuration changes (grayscale+autocontrast + PSM6 and/or upscaling) can remove the corrupted 702.00 line, so selection must apply an anchor-consistency override rather than trusting a single keyword line or “last TOTAL wins”.

## 077.jpg/total_amount

Rounding precedence failure: the extractor selected the pre-rounding inclusive total (23.26) instead of the final payable TOTAL after a rounding adjustment (23.25).

Evidence: Allowed feedback: 077.jpg amount_correct=false while date_correct=true; prediction total_amount=23.26. Visual inspection of 077.jpg shows “Total (Inclusive of GST): 23.26”, then “Rounding Adj: -0.01”, then a bold final “TOTAL: 23.25”. Exact-match scoring requires a mechanical precedence rule: if a rounding adjustment exists and a later TOTAL exists, always take the later TOTAL.

## 078.jpg/total_amount

Coupled extraction + schema failure: total_amount was emitted as an empty string instead of null; additionally, this receipt layout contains an “Amount” column header that can trigger split-line fallback to an item amount unless explicitly excluded, and OCR may corrupt both the GRAND TOTAL keyword and decimal separator (e.g., 92:80).

Evidence: Allowed feedback: 078.jpg amount_correct=false; prediction total_amount="" violates task requirement (must be null on failure). Visual inspection of 078.jpg shows a table header “Description Qty Price Amount” and summary lines “Total: 92.80” / “Grand Total: 92.80” plus payment lines “Cash Received: 100.00”, “Change: 7.20”. Prior history shows header-triggered split-line fallback and punctuation corruption (92:80) and keyword corruption (GrandTota./GrandTotal.), which require explicit header exclusion, tight fallback gating, decimal normalization, and a final schema guard (empty/whitespace → null).

## 034.jpg/date

Date disambiguation failure: the run selected a secondary date-like token (or an OCR-corrupted label line) instead of the primary header Date field on a dense invoice with multiple date-like strings.

Evidence: Allowed feedback: 034.jpg date_correct=false while amount_correct=true; prediction date=2018-08-09. Visual inspection of 034.jpg shows a clear header block with a labeled Date field near the top (dd/mm/yyyy) and other header-adjacent fields that can contain date/time-like strings. The historical trajectory also shows OCR label corruption (DATE→DATA) can create competing labeled candidates, making naive “first match” or weak ranking brittle.

## 074.jpg/total_amount

Total selection failure driven by OCR digit-flip outlier: the predicted total (702.00) contradicts multiple internal anchors on the receipt (Subtotal/Total incl/Payment/Total Amt Rounded) that agree on a different value; selection likely over-trusted a corrupted high-priority keyword line or “last TOTAL wins”.

Evidence: Allowed feedback: 074.jpg amount_correct=false while date_correct=true; prediction total_amount=702.00. Visual inspection of 074.jpg shows multiple summary lines around 102.00 (Subtotal, Total incl. of GST, Total Amt Rounded, Payment), while 702.00 is a classic OCR 1→7 digit flip. The source-run debugging (in the packet) shows OCR variants can produce both values; robust selection must reject candidates contradicting multiple anchors even if they appear on a higher-priority keyword line.

## 077.jpg/total_amount

Rounding precedence failure: receipt shows an inclusive total, a rounding adjustment, then a final payable TOTAL; the pipeline selected the pre-rounding value (23.26) instead of the final total after rounding (23.25).

Evidence: Allowed feedback: 077.jpg amount_correct=false while date_correct=true; prediction total_amount=23.26. Visual inspection of 077.jpg shows “Total (Inclusive of GST): 23.26”, “Rounding Adj: -0.01”, then bold “TOTAL: 23.25”. This is a deterministic precedence rule failure: if a rounding adjustment exists and a later TOTAL exists, always take the later TOTAL.

## 078.jpg/total_amount

Coupled extraction + schema failure: total_amount was emitted as an empty string instead of null, violating the task schema. This receipt also contains an “Amount” column header that can incorrectly trigger split-line fallback to an item amount unless explicitly excluded; OCR may corrupt both the GRAND TOTAL keyword and the decimal separator (e.g., 92:80).

Evidence: Allowed feedback: 078.jpg amount_correct=false; prediction total_amount="" (empty string). Visual inspection of 078.jpg shows a table header “Description Qty Price Amount” and summary lines “Total: 92.80” / “Grand Total: 92.80” plus payment lines “Cash Received: 100.00”, “Change: 7.20”. The packet’s historical trace shows header-triggered split-line fallback and punctuation corruption (92:80) and keyword corruption (GrandTota./GrandTotal.), which require explicit header exclusion, tight fallback gating, decimal normalization, and a final schema guard (empty/whitespace → null).

## 034.jpg/date

Date selection likely used a secondary date-like token (or OCR-corrupted label line) instead of the primary header Date field. This is a ranking/selection failure under multiple plausible dd/mm/yyyy strings.

Evidence: Allowed feedback: 034.jpg date_correct=false while amount_correct=true. The image shows a clear header block with a labeled Date field near the top, while the historical prediction is 2018-08-09 (consistent with selecting a different dd/mm token elsewhere or an OCR-mutated DATE→DATA line noted in the run history).

## 074.jpg/total_amount

Total selection failed due to OCR digit-flip outlier (102.00→702.00) on a total-like line. The pipeline over-trusted a corrupted high-priority keyword match or a 'last TOTAL wins' heuristic instead of enforcing internal anchor consistency (Subtotal/Payment/Total incl).

Evidence: Allowed feedback: 074.jpg amount_correct=false while date_correct=true; prediction total_amount=702.00. The receipt image contains multiple anchors around 102.00 (Subtotal, Total incl. of GST, Total Amt Rounded, Payment), while 702.00 is a classic OCR 1→7 digit flip. The source-run notes show OCR variants can produce both values, so selection must reject candidates contradicting multiple anchors.

## 077.jpg/total_amount

Rounding precedence failure: the extractor selected the pre-rounding inclusive total instead of the final payable TOTAL after a rounding adjustment, causing an exact-match miss (often by 0.01).

Evidence: Allowed feedback: 077.jpg amount_correct=false while date_correct=true; prediction total_amount=23.26. The receipt shows an inclusive total, a rounding adjustment line, then a final bold TOTAL with a slightly different value; selection must treat the final total after rounding as the payable amount.

## 078.jpg/total_amount

Schema/normalization failure: total_amount was emitted as an empty string instead of null. This receipt also has an AMOUNT column header that can trigger split-line fallback to an item amount unless explicitly excluded; OCR may corrupt both keyword (GrandTota./GrandTotal.) and decimal separator (92:80).

Evidence: Allowed feedback: 078.jpg amount_correct=false; prediction total_amount="" violates task requirement (must be null on failure). The receipt layout includes a table header containing “Amount” and summary lines for Total/Grand Total plus payment lines (Cash Received/Change). Historical trace indicates header-triggered split-line fallback and punctuation corruption (92:80), so strict header exclusion + decimal normalization + final schema guard are required.

## 034.jpg/date

Date disambiguation failure on a dense invoice: multiple plausible date-like strings exist in the header region, and the run selected a secondary date-like token rather than the primary header “Date:” field.

Evidence: Allowed feedback: 034.jpg date_correct=false while amount_correct=true; prediction date=2018-08-09. Visual inspection of 034.jpg shows a clear header block with “Date: 09/03/2018” near the top, while other date-like strings/metadata exist. Historical trace indicates OCR label corruption (DATE→DATA) can create competing labeled candidates, making naive first-match or weak ranking brittle.

## 074.jpg/total_amount

Total selection failure driven by OCR digit-flip outlier: the predicted total (702.00) contradicts multiple internal anchors on the receipt (Subtotal/Total incl/Payment/Total Amt Rounded) that agree on 102.00; selection likely over-trusted a corrupted high-priority keyword line or “last TOTAL wins”.

Evidence: Allowed feedback: 074.jpg amount_correct=false while date_correct=true; prediction total_amount=702.00. Visual inspection of 074.jpg shows multiple summary lines around 102.00 (Subtotal, Total incl. of GST, Total Amt Rounded, Payment), while 702.00 is a classic OCR 1→7 digit flip. Source-run notes show OCR variants can produce both values; robust selection must reject candidates contradicting multiple anchors even if they appear on a higher-priority keyword line.

## 077.jpg/total_amount

Rounding precedence failure: receipt shows an inclusive total, a rounding adjustment, then a final payable TOTAL; the pipeline selected the pre-rounding value (23.26) instead of the final total after rounding (23.25).

Evidence: Allowed feedback: 077.jpg amount_correct=false while date_correct=true; prediction total_amount=23.26. Visual inspection of 077.jpg shows “Total (Inclusive of GST): 23.26”, “Rounding Adj: -0.01”, then bold “TOTAL: 23.25”. This is a deterministic precedence rule failure: if a rounding adjustment exists and a later TOTAL exists, always take the later TOTAL.

## 078.jpg/total_amount

Coupled extraction + schema failure: total_amount was emitted as an empty string instead of null, violating the task schema. This receipt also contains an “Amount” column header that can incorrectly trigger split-line fallback to an item amount unless explicitly excluded; OCR may corrupt both the GRAND TOTAL keyword and the decimal separator (e.g., 92:80).

Evidence: Allowed feedback: 078.jpg amount_correct=false; prediction total_amount="" (empty string). Visual inspection of 078.jpg shows a table header “Description Qty Price Amount” and summary lines “Total: 92.80” / “Grand Total: 92.80” plus payment lines “Cash Received: 100.00”, “Change: 7.20”. Historical trace shows header-triggered split-line fallback and punctuation corruption (92:80) and keyword corruption (GrandTota./GrandTotal.), requiring explicit header exclusion, tight fallback gating, decimal normalization, and a final schema guard (empty/whitespace → null).

## 034.jpg/date

Date disambiguation failure: the run selected a secondary date-like token instead of the primary header Date field on a dense invoice with multiple date-like strings.

Evidence: Allowed feedback shows 034.jpg date_correct=false while amount_correct=true. The prediction is 2018-08-09. Visual inspection of 034.jpg shows a clear header block with a labeled Date field near the top (dd/mm/yyyy) and other header-adjacent date/time-like strings. Historical trace also shows OCR label corruption (DATE→DATA) can create competing labeled candidates, making naive first-match or weak ranking brittle.

## 074.jpg/total_amount

Total selection failure driven by OCR digit-flip outlier: the predicted total (702.00) contradicts multiple internal anchors on the receipt (Subtotal/Total incl/Payment/Total Amt Rounded) that agree on ~102.00; selection likely over-trusted a corrupted high-priority keyword line or “last TOTAL wins”.

Evidence: Allowed feedback shows 074.jpg amount_correct=false while date_correct=true; prediction total_amount=702.00. Visual inspection of 074.jpg shows multiple summary lines around 102.00 (Subtotal, Total incl. of GST, Total Amt Rounded, Payment), while 702.00 is a classic OCR 1→7 digit flip. The source-run debugging (in the packet) shows OCR variants can produce both values; robust selection must reject candidates contradicting multiple anchors even if they appear on a higher-priority keyword line.

## 077.jpg/total_amount

Rounding precedence failure: receipt shows an inclusive total, a rounding adjustment, then a final payable TOTAL; the pipeline selected the pre-rounding value (23.26) instead of the final total after rounding (23.25).

Evidence: Allowed feedback shows 077.jpg amount_correct=false while date_correct=true; prediction total_amount=23.26. Visual inspection of 077.jpg shows “Total (Inclusive of GST): 23.26”, “Rounding Adj: -0.01”, then bold “TOTAL: 23.25”. This is a deterministic precedence rule failure: if a rounding adjustment exists and a later TOTAL exists, always take the later TOTAL.

## 078.jpg/total_amount

Coupled extraction + schema failure: total_amount was emitted as an empty string instead of null, violating the task schema. This receipt also contains an “Amount” column header that can incorrectly trigger split-line fallback to an item amount unless explicitly excluded; OCR may corrupt both the GRAND TOTAL keyword and the decimal separator (e.g., 92:80).

Evidence: Allowed feedback shows 078.jpg amount_correct=false; prediction total_amount="" (empty string). Visual inspection of 078.jpg shows a table header “Description Qty Price Amount” and summary lines “Total: 92.80” / “Grand Total: 92.80” plus payment lines “Cash Received: 100.00”, “Change: 7.20”. Historical trace shows header-triggered split-line fallback and punctuation corruption (92:80) and keyword corruption (GrandTota./GrandTotal.), requiring explicit header exclusion, tight fallback gating, decimal normalization, and a final schema guard (empty/whitespace → null).

## 034.jpg/date

Date disambiguation failure: receipt/invoice contains multiple date-like strings; the run selected a secondary candidate (likely from a different header line or OCR-corrupted label) instead of the primary header Date field.

Evidence: Allowed feedback shows 034.jpg date_correct=false while amount_correct=true. The prediction is 2018-08-09. Visual inspection of 034.jpg shows a clear header block with “Date: 09/03/2018” near the top, while other date-like strings/metadata exist (and prior history shows DATE→DATA corruption can create competing labeled candidates). This is a ranking/selection issue under multiple plausible dd/mm/yyyy strings, not an OCR-absence issue.

## 074.jpg/total_amount

Total selection failure driven by OCR digit-flip outlier: the predicted total (702.00) contradicts multiple internal anchors on the receipt (Subtotal/Total incl/Payment/Total Amt Rounded) that agree on ~102.00; selection likely over-trusted a corrupted high-priority keyword line or “last TOTAL wins”.

Evidence: Allowed feedback shows 074.jpg amount_correct=false while date_correct=true; prediction total_amount=702.00. Visual inspection of 074.jpg shows multiple summary lines around 102.00 (Subtotal, Total incl. of GST, Total Amt Rounded, Payment), while 702.00 is a classic OCR 1→7 digit flip. The historical trace indicates OCR variants can produce both values; robust selection must reject candidates contradicting multiple anchors even if they appear on a higher-priority keyword line.

## 077.jpg/total_amount

Rounding precedence failure: receipt shows an inclusive total, a rounding adjustment, then a final payable TOTAL; the pipeline selected the pre-rounding value (23.26) instead of the final total after rounding (23.25).

Evidence: Allowed feedback shows 077.jpg amount_correct=false while date_correct=true; prediction total_amount=23.26. Visual inspection of 077.jpg shows “Total (Inclusive of GST): 23.26”, “Rounding Adj: -0.01”, then bold “TOTAL: 23.25”. This is a deterministic precedence rule failure: if a rounding adjustment exists and a later TOTAL exists, always take the later TOTAL.

## 078.jpg/total_amount

Coupled extraction + schema failure: total_amount was emitted as an empty string instead of null, violating the task schema. This receipt also contains an “Amount” column header that can incorrectly trigger split-line fallback to an item amount unless explicitly excluded; OCR may corrupt both the GRAND TOTAL keyword and the decimal separator (e.g., 92:80).

Evidence: Allowed feedback shows 078.jpg amount_correct=false; prediction total_amount="" (empty string). Visual inspection of 078.jpg shows a table header “Description Qty Price Amount” and summary lines “Total: 92.80” / “Grand Total: 92.80” plus payment lines “Cash Received: 100.00”, “Change: 7.20”. Historical trace shows header-triggered split-line fallback and punctuation corruption (92:80) and keyword corruption (GrandTota./GrandTotal.), requiring explicit header exclusion, tight fallback gating, decimal normalization, and a final schema guard (empty/whitespace → null).

## 074.jpg/total_amount

Total selection failed due to OCR digit-flip outlier on a later, high-priority keyword line (e.g., “Total Amt Rounded”), overriding multiple internal anchors (Subtotal/Payment/Total incl) that agree on a different value. This is a classic case where keyword-priority or “last TOTAL wins” must be subordinated to receipt-internal consistency.

Evidence: Allowed feedback: 074.jpg amount_correct=false while date_correct=true; prediction total_amount="702.00". Visual inspection of 074.jpg shows multiple summary anchors around 102.00 (Subtotal, Total incl. of GST, Total Amt Rounded, Payment). The packet’s trace shows OCR variants can produce both 702.00 and 102.00, indicating a 1→7 digit flip on one line. Selection logic must reject candidates contradicting multiple anchors even if they appear on a higher-priority keyword line.

## 077.jpg/total_amount

Rounding precedence failure: the extractor selected the pre-rounding inclusive total instead of the final payable TOTAL after a rounding adjustment, causing an exact-match miss (often by 0.01).

Evidence: Allowed feedback: 077.jpg amount_correct=false while date_correct=true; prediction total_amount="23.26". Visual inspection of 077.jpg shows “Total (Inclusive of GST): 23.26”, then “Rounding Adj: -0.01”, then bold “TOTAL: 23.25”. This indicates the pipeline did not enforce the hard precedence rule: if a rounding adjustment exists and a later TOTAL exists, always take the later TOTAL.

## 078.jpg/total_amount

Coupled extraction + schema failure: total_amount was emitted as an empty string instead of null, violating the task schema. This receipt also contains an “Amount” column header that can trigger split-line fallback to an item amount unless explicitly excluded; OCR may corrupt both the GRAND TOTAL keyword and the decimal separator (e.g., 92:80).

Evidence: Allowed feedback: 078.jpg amount_correct=false; prediction total_amount="" (empty string). Visual inspection of 078.jpg shows a table header “Description Qty Price Amount” and summary lines “Total: 92.80” / “Grand Total: 92.80” plus payment lines “Cash Received: 100.00”, “Change: 7.20”. The packet’s trace shows header-triggered split-line fallback and punctuation corruption (92:80) and keyword corruption (GrandTota./GrandTotal.), requiring explicit header exclusion, tight fallback gating, decimal normalization, and a final schema guard (empty/whitespace → null).

## 034.jpg/date

Date disambiguation failure: the run selected a secondary date-like token (or an OCR-corrupted label line such as DATE→DATA) instead of the primary header Date field on a dense invoice with multiple date-like strings.

Evidence: Allowed feedback: 034.jpg date_correct=false while amount_correct=true; prediction date=2018-08-09. Visual inspection of 034.jpg shows a clear header block with a labeled Date field near the top (dd/mm/yyyy) and other header-adjacent date/time-like strings. Prior history indicates OCR label corruption (DATE→DATA) can create competing labeled candidates, making naive first-match or weak ranking brittle.

## 034.jpg/date

Date disambiguation failure: the run selected a secondary date-like token instead of the primary header Date field on a dense invoice with multiple date-like strings.

Evidence: Allowed field feedback: 034.jpg date_correct=false while amount_correct=true. Prediction row shows date=2018-08-09. Visual inspection of 034.jpg shows a clear header block with a labeled Date field near the top (dd/mm/yyyy) and other header-adjacent date/time-like strings; prior history shows OCR label corruption (DATE→DATA) can create competing labeled candidates. This is a ranking/selection issue under multiple plausible dd/mm/yyyy strings, not an OCR-absence issue.

## 074.jpg/total_amount

Total selection failure driven by OCR digit-flip outlier: the predicted total (702.00) contradicts multiple internal anchors on the receipt (Subtotal/Total incl/Payment/Total Amt Rounded) that agree on ~102.00; selection likely over-trusted a corrupted high-priority keyword line or “last TOTAL wins”.

Evidence: Allowed field feedback: 074.jpg amount_correct=false while date_correct=true; prediction total_amount=702.00. Visual inspection of 074.jpg shows multiple summary lines around 102.00 (Subtotal, Total incl. of GST, Total Amt Rounded, Payment), while 702.00 is a classic OCR 1→7 digit flip. Source-run trace shows the agent used cross-variant majority voting and keyword-tier priority, which can be defeated by a single corrupted ‘Total Amt Rounded’ line unless anchor-consistency overrides it.

## 077.jpg/total_amount

Rounding precedence failure: the extractor selected the pre-rounding inclusive total instead of the final payable TOTAL after a rounding adjustment, causing an exact-match miss (often by 0.01).

Evidence: Allowed field feedback: 077.jpg amount_correct=false while date_correct=true; prediction total_amount=23.26. Visual inspection of 077.jpg shows “Total (Inclusive of GST): 23.26”, then “Rounding Adj: -0.01”, then a bold final “TOTAL: 23.25”. This indicates the pipeline did not enforce the hard precedence rule: if rounding adjustment exists and a later TOTAL exists, always take the later TOTAL.

## 078.jpg/total_amount

Coupled extraction + schema failure: total_amount was emitted as an empty string instead of null, violating the task schema. This receipt also contains an “Amount” column header that can incorrectly trigger split-line fallback to an item amount unless explicitly excluded; OCR may corrupt both the GRAND TOTAL keyword and the decimal separator (e.g., 92:80).

Evidence: Allowed field feedback: 078.jpg amount_correct=false; prediction total_amount="" (empty string). Visual inspection of 078.jpg shows a table header “Description Qty Price Amount” and summary lines “Total: 92.80” / “Grand Total: 92.80” plus payment lines “Cash Received: 100.00”, “Change: 7.20”. Source-run trace shows header-triggered split-line fallback and keyword/decimal corruption (GrandTota./GrandTotal., 92:80), and also a missing final schema guard (empty/whitespace → null).

## 034.jpg/date

Date disambiguation failure: the run selected a secondary date-like token (likely from a different header line or OCR-corrupted label) instead of the primary header Date field.

Evidence: Allowed feedback: 034.jpg date_correct=false while amount_correct=true; prediction date=2018-08-09. Visual inspection of 034.jpg shows a clear header block with a labeled Date field near the top (dd/mm/yyyy) and other header-adjacent date/time-like strings. Prior history shows OCR label corruption (DATE→DATA) can create competing labeled candidates, so naive first-match or weak ranking can pick the wrong one.

## 074.jpg/total_amount

Total selection failure driven by OCR digit-flip outlier: the predicted total (702.00) contradicts multiple internal anchors on the receipt (Subtotal/Total incl/Payment/Total Amt Rounded) that agree on ~102.00; selection likely over-trusted a corrupted high-priority keyword line or “last TOTAL wins”.

Evidence: Allowed feedback: 074.jpg amount_correct=false while date_correct=true; prediction total_amount=702.00. Visual inspection of 074.jpg shows multiple summary lines around 102.00 (Subtotal, Total incl. of GST, Total Amt Rounded, Payment), while 702.00 is a classic OCR 1→7 digit flip. The historical trace shows OCR variants can produce both values; robust selection must reject candidates contradicting multiple anchors even if they appear on a higher-priority keyword line.

## 077.jpg/total_amount

Rounding precedence failure: receipt shows an inclusive total, a rounding adjustment, then a final payable TOTAL; the pipeline selected the pre-rounding value (23.26) instead of the final total after rounding (23.25).

Evidence: Allowed feedback: 077.jpg amount_correct=false while date_correct=true; prediction total_amount=23.26. Visual inspection of 077.jpg shows “Total (Inclusive of GST): 23.26”, “Rounding Adj: -0.01”, then bold “TOTAL: 23.25”. This is a deterministic precedence rule failure: if a rounding adjustment exists and a later TOTAL exists, always take the later TOTAL.

## 078.jpg/total_amount

Coupled extraction + schema failure: total_amount was emitted as an empty string instead of null, violating the task schema. This receipt also contains an “Amount” column header that can incorrectly trigger split-line fallback to an item amount unless explicitly excluded; OCR may corrupt both the GRAND TOTAL keyword and the decimal separator (e.g., 92:80).

Evidence: Allowed feedback: 078.jpg amount_correct=false; prediction total_amount="" (empty string). Visual inspection of 078.jpg shows a table header “Description Qty Price Amount” and summary lines “Total: 92.80” / “Grand Total: 92.80” plus payment lines “Cash Received: 100.00”, “Change: 7.20”. Historical trace shows header-triggered split-line fallback and punctuation corruption (92:80) and keyword corruption (GrandTota./GrandTotal.), requiring explicit header exclusion, tight fallback gating, decimal normalization, and a final schema guard (empty/whitespace → null).

## 034.jpg/date

Date disambiguation failure on a dense invoice: the run selected a secondary date-like token (likely from a different header line or OCR-corrupted label) instead of the primary header Date field.

Evidence: Allowed feedback shows 034.jpg date_correct=false while amount_correct=true; prediction date=2018-08-09. Visual inspection of 034.jpg shows a clear header block with a labeled Date field near the top (dd/mm/yyyy) and other header-adjacent date/time-like strings. Prior history indicates OCR label corruption (DATE→DATA) can create competing labeled candidates, so naive first-match or weak ranking can pick the wrong one.

## 074.jpg/total_amount

Total selection failure driven by OCR digit-flip outlier: the predicted total (702.00) contradicts multiple internal anchors on the receipt (Subtotal/Total incl/Payment/Total Amt Rounded) that agree on ~102.00; selection likely over-trusted a corrupted high-priority keyword line or “last TOTAL wins”.

Evidence: Allowed feedback shows 074.jpg amount_correct=false while date_correct=true; prediction total_amount=702.00. Visual inspection of 074.jpg shows multiple summary lines around 102.00 (Subtotal, Total incl. of GST, Total Amt Rounded, Payment), while 702.00 is a classic OCR 1→7 digit flip. The packet’s trace shows OCR variants can produce both values; robust selection must reject candidates contradicting multiple anchors even if they appear on a higher-priority keyword line.

## 077.jpg/total_amount

Rounding precedence failure: receipt shows an inclusive total, a rounding adjustment, then a final payable TOTAL; the pipeline selected the pre-rounding value (23.26) instead of the final total after rounding (23.25).

Evidence: Allowed feedback shows 077.jpg amount_correct=false while date_correct=true; prediction total_amount=23.26. Visual inspection of 077.jpg shows “Total (Inclusive of GST): 23.26”, “Rounding Adj: -0.01”, then bold “TOTAL: 23.25”. This is a deterministic precedence rule failure: if a rounding adjustment exists and a later TOTAL exists, always take the later TOTAL.

## 078.jpg/total_amount

Coupled extraction + schema failure: total_amount was emitted as an empty string instead of null, violating the task schema. This receipt also contains an “Amount” column header that can incorrectly trigger split-line fallback to an item amount unless explicitly excluded; OCR may corrupt both the GRAND TOTAL keyword and the decimal separator (e.g., 92:80).

Evidence: Allowed feedback shows 078.jpg amount_correct=false; prediction total_amount="" (empty string). Visual inspection of 078.jpg shows a table header “Description Qty Price Amount” and summary lines “Total: 92.80” / “Grand Total: 92.80” plus payment lines “Cash Received: 100.00”, “Change: 7.20”. Historical trace shows header-triggered split-line fallback and punctuation corruption (92:80) and keyword corruption (GrandTota./GrandTotal.), requiring explicit header exclusion, tight fallback gating, decimal normalization, and a final schema guard (empty/whitespace → null).

## 034.jpg/date

Date disambiguation failure: the run selected a secondary date-like token instead of the primary header Date field on a dense invoice with multiple date-like strings.

Evidence: Allowed feedback shows 034.jpg date_correct=false while amount_correct=true; prediction date=2018-08-09. The image shows a clear header block with “Date: 09/03/2018” near the top, while other date-like strings/metadata exist. Prior history indicates OCR label corruption (DATE→DATA) can create competing labeled candidates, so naive first-match or weak ranking can pick the wrong one.

## 074.jpg/total_amount

Total selection failure driven by OCR digit-flip outlier: the predicted total (702.00) contradicts multiple internal anchors on the receipt (Subtotal/Total incl/Payment/Total Amt Rounded) that agree on ~102.00; selection likely over-trusted a corrupted high-priority keyword line or “last TOTAL wins”.

Evidence: Allowed feedback shows 074.jpg amount_correct=false while date_correct=true; prediction total_amount=702.00. The receipt image contains multiple anchors around 102.00 (Subtotal, Total incl. of GST, Total Amt Rounded, Payment), while 702.00 is a classic OCR 1→7 digit flip. The source-run trace shows OCR variants can produce both values; robust selection must reject candidates contradicting multiple anchors even if they appear on a higher-priority keyword line.

## 077.jpg/total_amount

Rounding precedence failure: receipt shows an inclusive total, a rounding adjustment, then a final payable TOTAL; the pipeline selected the pre-rounding value (23.26) instead of the final total after rounding (23.25).

Evidence: Allowed feedback shows 077.jpg amount_correct=false while date_correct=true; prediction total_amount=23.26. The image clearly shows “Rounding Adj: -0.01” followed by a bold final “TOTAL: 23.25”, while an earlier line shows “Total (Inclusive of GST): 23.26”. This is a deterministic precedence rule failure: if a rounding adjustment exists and a later TOTAL exists, always take the later TOTAL.

## 078.jpg/total_amount

Coupled extraction + schema failure: total_amount was emitted as an empty string instead of null, violating the task schema. This receipt also contains an “Amount” column header that can incorrectly trigger split-line fallback to an item amount unless explicitly excluded; OCR may corrupt both the GRAND TOTAL keyword and the decimal separator (e.g., 92:80).

Evidence: Allowed feedback shows 078.jpg amount_correct=false; prediction total_amount="" (empty string). The source-run trace shows the extractor matched the column header line “Description Qty Price Amount” and then used split-line fallback to grab an item amount; other OCR variants show “GrandTota.”/“GrandTotal.” and “92:80”, and a stronger OCR variant (3× upscale + PSM4) yields “Grand Total ... 92.80”. Regardless of extraction outcome, empty string must be converted to null.

## 034.jpg/date

Date disambiguation failure on a dense invoice: multiple plausible date-like strings exist (header Date field vs other date/time-like tokens), and the run selected a secondary candidate rather than the primary header “Date:” field.

Evidence: Allowed feedback shows 034.jpg date_correct=false while amount_correct=true; prediction date=2018-08-09. Visual inspection of 034.jpg shows a clear header block with a labeled Date field near the top (dd/mm/yyyy) and other header-adjacent fields (e.g., time). Prior history indicates OCR label corruption (DATE→DATA) can create competing labeled candidates, making naive first-match or weak ranking brittle.

## 074.jpg/total_amount

Total selection failure driven by OCR digit-flip outlier: the predicted total (702.00) contradicts multiple internal anchors on the receipt (Subtotal/Total incl/Payment/Total Amt Rounded) that agree on ~102.00; selection likely over-trusted a corrupted high-priority keyword line or “last TOTAL wins”.

Evidence: Allowed feedback shows 074.jpg amount_correct=false while date_correct=true; prediction total_amount=702.00. Visual inspection of 074.jpg shows multiple summary lines around 102.00 (Subtotal, Total incl. of GST, Total Amt Rounded, Payment), while 702.00 is a classic OCR 1→7 digit flip. The packet’s trace shows OCR variants can produce both values; robust selection must reject candidates contradicting multiple anchors even if they appear on a higher-priority keyword line.

## 077.jpg/total_amount

Rounding precedence failure: receipt shows an inclusive total, a rounding adjustment, then a final payable TOTAL; the pipeline selected the pre-rounding value (23.26) instead of the final total after rounding (23.25).

Evidence: Allowed feedback shows 077.jpg amount_correct=false while date_correct=true; prediction total_amount=23.26. Visual inspection of 077.jpg shows “Total (Inclusive of GST): 23.26”, “Rounding Adj: -0.01”, then bold “TOTAL: 23.25”. This is a deterministic precedence rule failure: if a rounding adjustment exists and a later TOTAL exists, always take the later TOTAL.

## 078.jpg/total_amount

Coupled extraction + schema failure: total_amount was emitted as an empty string instead of null, violating the task schema. This receipt also contains an “Amount” column header that can incorrectly trigger split-line fallback to an item amount unless explicitly excluded; OCR may corrupt both the GRAND TOTAL keyword and the decimal separator (e.g., 92:80).

Evidence: Allowed feedback shows 078.jpg amount_correct=false; prediction total_amount="" (empty string). Visual inspection of 078.jpg shows a table header “Description Qty Price Amount” and summary lines “Total: 92.80” / “Grand Total: 92.80” plus payment lines “Cash Received: 100.00”, “Change: 7.20”. Historical trace shows header-triggered split-line fallback and punctuation corruption (92:80) and keyword corruption (GrandTota./GrandTotal.), requiring explicit header exclusion, tight fallback gating, decimal normalization, and a final schema guard (empty/whitespace → null).

## 034.jpg/date

Date disambiguation failure: the run selected a secondary date-like token (likely from a different header line or an OCR-corrupted label) instead of the primary header Date field on a dense invoice.

Evidence: Allowed feedback shows 034.jpg date_correct=false while amount_correct=true; prediction date=2018-08-09. Visual inspection of 034.jpg shows a clear header block with a labeled Date field near the top (e.g., “Date: 09/03/2018”), while other date-like strings/metadata exist. Prior history indicates OCR label corruption (DATE→DATA) can create competing labeled candidates, so naive first-match or weak ranking can pick the wrong one.

## 074.jpg/total_amount

Total selection failure driven by OCR digit-flip outlier: the predicted total (702.00) contradicts multiple internal anchors on the receipt (Subtotal/Total incl/Payment/Total Amt Rounded) that agree on ~102.00; selection likely over-trusted a corrupted high-priority keyword line or “last TOTAL wins”.

Evidence: Allowed feedback shows 074.jpg amount_correct=false while date_correct=true; prediction total_amount=702.00. Visual inspection of 074.jpg shows multiple summary lines around 102.00 (Subtotal, Total incl. of GST, Total Amt Rounded, Payment), while 702.00 is a classic OCR 1→7 digit flip. The packet’s trace shows OCR variants can produce both values; robust selection must reject candidates contradicting multiple anchors even if they appear on a higher-priority keyword line.

## 077.jpg/total_amount

Rounding precedence failure: receipt shows an inclusive total, a rounding adjustment, then a final payable TOTAL; the pipeline selected the pre-rounding value (23.26) instead of the final total after rounding (23.25).

Evidence: Allowed feedback shows 077.jpg amount_correct=false while date_correct=true; prediction total_amount=23.26. Visual inspection of 077.jpg shows “Total (Inclusive of GST): 23.26”, “Rounding Adj: -0.01”, then bold “TOTAL: 23.25”. This is a deterministic precedence rule failure: if a rounding adjustment exists and a later TOTAL exists, always take the later TOTAL.

## 078.jpg/total_amount

Coupled extraction + schema failure: total_amount was emitted as an empty string instead of null, violating the task schema. This receipt also contains an “Amount” column header that can incorrectly trigger split-line fallback to an item amount unless explicitly excluded; OCR may corrupt both the GRAND TOTAL keyword and the decimal separator (e.g., 92:80).

Evidence: Allowed feedback shows 078.jpg amount_correct=false; prediction total_amount="" (empty string). Visual inspection of 078.jpg shows a table header “Description Qty Price Amount” and summary lines “Total: 92.80” / “Grand Total: 92.80” plus payment lines “Cash Received: 100.00”, “Change: 7.20”. Historical trace shows header-triggered split-line fallback and punctuation corruption (92:80) and keyword corruption (GrandTota./GrandTotal.), requiring explicit header exclusion, tight fallback gating, decimal normalization, and a final schema guard (empty/whitespace → null).

## 034.jpg/date

Date disambiguation failure: the run’s date extractor likely took the first plausible dd/mm(/yyyy) match it saw (or a mislabeled near-match like “Data:”), rather than prioritizing the primary header ‘Date:’ field in the top header block. This caused selecting a different date-like token than the true invoice date.

Evidence: In the source-run OCR output for 034.jpg, a header-adjacent line appears as “Salesperson: Data: 09/08/2018” (DATE→DATA OCR corruption), while the image itself shows a clear header field “Date: 09/03/2018” near other header metadata. The original extraction code (extract_date) scans lines sequentially and returns the first regex match without label/context ranking, making it vulnerable to this exact ambiguity. Field feedback confirms 034.jpg date_correct=false while amount_correct=true.

## 074.jpg/total_amount

Total amount selection failure due to OCR digit-flip outlier and over-trusting a single ‘TOTAL’-like line. The run picked 702.00 even though multiple internal anchors on the same receipt (Subtotal/Payment/Total incl/Total Amt Rounded) indicate ~102.00. This is a robustness issue: keyword priority or ‘last total wins’ must be subordinated to anchor consistency.

Evidence: The OCR output for 074.jpg contains both consistent anchors (“Subtotal : 102.00”, “Payment : 102.00”) and a corrupted line “Total inel. of GBT 702.00” (classic 1→7 digit flip). The receipt image shows totals around 102.00. Field feedback confirms 074.jpg amount_correct=false while date_correct=true, and the prediction table shows total_amount="702.00".

## 077.jpg/total_amount

Rounding precedence failure: the run selected the pre-rounding ‘Total (Inclusive of GST)’ instead of the final payable ‘TOTAL’ after a rounding adjustment, causing an exact-match miss (often by 0.01).

Evidence: The 077.jpg image shows “Total (Inclusive of GST): 23.26”, then “Rounding Adj: -0.01”, then a bold final “TOTAL: 23.25”. The prediction table shows total_amount="23.26" and field feedback confirms amount_correct=false while date_correct=true. This indicates selection logic did not enforce ‘final total after rounding wins’.

## 078.jpg/total_amount

Schema/normalization failure plus header-triggered fallback risk: the run emitted an empty string for total_amount (must be null on failure). This receipt also contains an ‘Amount’ column header that can incorrectly trigger split-line fallback to an item amount unless explicitly excluded, and OCR may corrupt decimal separators (e.g., 92:80) and ‘Grand Total’ keyword spacing/punctuation.

Evidence: Predictions table shows 078.jpg total_amount="" (empty string) and field feedback confirms amount_correct=false. The OCR output includes “Description Qty Price Amount” (a column header), “a Total — 92:80” (colon decimal corruption), and “GrandTota. ... 92.80” (keyword corruption). Without strict post-processing (empty→null) and header-line exclusion, extraction can fail or pick an item amount.

## 034.jpg/date

Date disambiguation failure: the original pipeline returns the first regex-matching date anywhere in the OCR text, so it can pick a secondary date-like token (or an OCR-corrupted label line like DATE→DATA) instead of the primary header Date field.

Evidence: Source code excerpt (atif_steps s0008) shows extract_date() iterates lines top-to-bottom and returns immediately on first match, with no label/context ranking. Prior history and OCR snippets indicate competing header-adjacent date-like strings (e.g., “Salesperson: Data: …”) exist on 034.jpg; allowed feedback shows date_correct=false while amount_correct=true.

## 074.jpg/total_amount

Total selection failure due to OCR digit-flip outlier and weak candidate selection: the original pipeline prefers the last matching TOTAL-like line and lacks anchor-consistency override, so a corrupted ‘Total incl… 702.00’ can dominate despite Subtotal/Payment anchors.

Evidence: OCR debug for 074.jpg shows both anchors (“Subtotal : 102.00”, “Payment : 102.00”) and an outlier “Total inel. of GBT 702.00” (atif_steps s0010 / m0032). The extraction logic in s0008 explicitly “Prefer the LAST candidate line” and then uses split-line fallback, with no anchor-consistency check. Allowed feedback: 074.jpg amount_correct=false; prediction total_amount=702.00.

## 077.jpg/total_amount

Rounding precedence failure: receipt contains both an inclusive total and a final payable TOTAL after a rounding adjustment; naive ‘TOTAL’ selection can pick the wrong one unless a hard rounding precedence rule is applied.

Evidence: 077.jpg image shows “Rounding Adj: -0.01” followed by bold “TOTAL: 23.25”, while an earlier line shows “Total (Inclusive of GST): 23.26”. Allowed feedback: 077.jpg amount_correct=false; prediction total_amount=23.26. This is consistent with selection not enforcing ‘final total after rounding wins’.

## 078.jpg/total_amount

Schema/normalization failure: total_amount was emitted as an empty string instead of null. Additionally, this receipt layout includes an AMOUNT column header that can trigger split-line fallback to an item amount unless explicitly excluded; OCR may also corrupt decimal separators (92:80) and GRAND TOTAL spacing/punctuation.

Evidence: Predictions table shows 078.jpg total_amount="" (empty string) while task requires null on failure. The source-run trace (prior history) shows matching on “Description Qty Price Amount” and split-line fallback to an item amount; OCR variants include “92:80” and “GrandTota.”. These are exactly the failure modes addressed by strict schema guard + header-line exclusion + decimal normalization.

## 034.jpg/date

Date disambiguation failure: the original pipeline likely selected the first regex-matching date-like token (or an OCR-corrupted near-label like “Data:”) rather than prioritizing the primary header Date field. Dense invoices can contain multiple plausible dd/mm(/yyyy) strings; without label/context ranking, the wrong one is chosen.

Evidence: Allowed feedback: 034.jpg date_correct=false while amount_correct=true. Source-run evidence shows competing header-adjacent date-like strings due to OCR label corruption (DATE→DATA) and multiple header fields. The atif_steps and related OCR snippets show that the extraction logic returned the first match without ranking, which is brittle on invoices like 034.jpg.

## 074.jpg/total_amount

Total selection failure due to OCR digit-flip outlier and over-trusting a single TOTAL-like line. The receipt contains multiple internal anchors (Subtotal/Payment/Total incl) consistent with one value, but OCR produced a conflicting outlier (e.g., 102.00→702.00) on a later TOTAL-like line; naive “last TOTAL wins” or keyword-tier priority without anchor override selects the outlier.

Evidence: Allowed feedback: 074.jpg amount_correct=false while date_correct=true; prediction total_amount=702.00. Source-run OCR snippets show both anchors (“Subtotal : 102.00”, “Payment : 102.00”, “Total incl. of GST 102.00”) and an outlier “Total ... 702.00” / “Total Amt Rounded ... 702.00”. This is a classic OCR 1→7 digit flip where internal consistency should override a single corrupted line.

## 077.jpg/total_amount

Rounding precedence failure: the receipt shows an inclusive total, a rounding adjustment, then a final payable TOTAL. The pipeline selected the pre-rounding inclusive total instead of the final total after rounding, causing an exact-match miss (often by 0.01).

Evidence: Allowed feedback: 077.jpg amount_correct=false while date_correct=true; prediction total_amount=23.26. The image shows “Rounding Adj: -0.01” followed by bold “TOTAL: 23.25”, while an earlier line shows “Total (Inclusive of GST): 23.26”. This requires an unconditional precedence rule: if rounding adjustment exists and a later TOTAL exists, take the later TOTAL.

## 078.jpg/total_amount

Schema/normalization failure plus header-triggered fallback risk: total_amount was emitted as an empty string instead of null. Additionally, this receipt contains an “Amount” column header that can trigger split-line fallback to an item amount unless explicitly excluded; OCR may also corrupt the GRAND TOTAL keyword and decimal separator (e.g., 92:80).

Evidence: Allowed feedback: 078.jpg amount_correct=false; prediction total_amount="" violates task requirement (must be null on failure). Source-run trace shows matching on “Description Qty Price Amount” and split-line fallback to an item amount; OCR variants include “GrandTota.” and “92:80”. Even if extraction fails, output must be null, never empty string.

## 034.jpg/date

Date disambiguation failure: the original run selected a secondary date-like token (likely from an OCR-corrupted label line such as DATE→DATA) instead of the primary header Date field. This is consistent with a first-match regex strategy without header/label ranking.

Evidence: Allowed feedback: 034.jpg date_correct=false while amount_correct=true; prediction date=2018-08-09. Source-run OCR snippets show a competing header-adjacent line like “Salesperson. Data: 09/08/2018”, while the image shows a clear header “Date: 09/03/2018”. The source implementation (per atif_steps references) used first-match date extraction without label/context ranking, making this failure mode likely.

## 074.jpg/total_amount

Total selection failure driven by OCR digit-flip outlier (102.00→702.00) on a TOTAL-like line and a selection rule that prefers the last TOTAL candidate. Without an anchor-consistency override (Subtotal/Payment agreement) and/or an upscale OCR pass, the outlier can dominate.

Evidence: Allowed feedback: 074.jpg amount_correct=false while date_correct=true; prediction total_amount=702.00. OCR snippets show anchors “Subtotal : 102.00” and “Payment : 102.00” but also a corrupted “Total ... 702.00”. The run’s own debugging shows that 2× upscaling + autocontrast + PSM6 yields clean “Total incl. of GST 102.00”, indicating OCR configuration plus anchor-consistency are decisive.

## 077.jpg/total_amount

Rounding precedence failure: the run selected the pre-rounding inclusive total instead of the final payable TOTAL after a rounding adjustment. This requires an unconditional precedence rule to avoid exact-match misses.

Evidence: Allowed feedback: 077.jpg amount_correct=false while date_correct=true; prediction total_amount=23.26. The image shows “Rounding Adj: -0.01” followed by bold “TOTAL: 23.25”, while an earlier line shows “Total (Inclusive of GST): 23.26”. The miss is selection/precedence, not OCR absence.

## 078.jpg/total_amount

Schema/normalization failure: total_amount was emitted as an empty string instead of null. Additionally, this receipt layout includes an AMOUNT column header that can trigger split-line fallback to an item amount unless explicitly excluded; OCR may also corrupt the GRAND TOTAL keyword and decimal separator (e.g., 92:80).

Evidence: Allowed feedback: 078.jpg amount_correct=false; prediction total_amount="" violates task requirement (must be null on failure). Source-run trace shows matching on “Description Qty Price Amount” and split-line fallback to an item amount; other OCR variants show “GrandTota.” and “92:80”. Even when extraction fails, output must be null, never empty string.

## 034.jpg/date

Date selection is vulnerable to first-match / weak-ranking behavior when multiple date-like strings exist and the DATE label is OCR-corrupted (e.g., DATE→DATA). The historical run picked a different dd/mm token than the primary header Date field.

Evidence: Allowed feedback: 034.jpg date_correct=false while amount_correct=true. Source-run evidence shows OCR text containing a competing header-adjacent line like “Salesperson: Data: 09/08/2018” while the image shows a clear header “Date: 09/03/2018”. The source implementation (atif_steps references) used first-match date extraction without label/context ranking, making this failure mode likely.

## 074.jpg/total_amount

Total selection is brittle under OCR digit-flip outliers (e.g., 102.00→702.00) when a corrupted TOTAL-like line appears later and the selector prefers “last TOTAL wins” or majority vote across OCR variants. Robust selection must use internal anchors (Subtotal/Payment/Total incl) to reject contradictory totals even if they appear on a higher-priority keyword line.

Evidence: Allowed feedback: 074.jpg amount_correct=false while date_correct=true; prediction total_amount=702.00. Source-run OCR snippets show anchors “Subtotal : 102.00”, “Total incl. of GST 102.00”, “Payment : 102.00” but also corrupted “Total ... 702.00” / “Total Amt Rounded ... 702.00”. This is a classic OCR 1→7 digit flip where anchor-consistency should override keyword priority and variant-majority voting.

## 077.jpg/total_amount

Rounding precedence failure: the payable total is the final TOTAL after a rounding adjustment, but selection can incorrectly choose the earlier inclusive total if it does not enforce a hard precedence rule.

Evidence: Allowed feedback: 077.jpg amount_correct=false while date_correct=true; prediction total_amount=23.26. The image shows “Total (Inclusive of GST): 23.26”, “Rounding Adj: -0.01”, then bold “TOTAL: 23.25”. This indicates selection/precedence logic did not enforce “final total after rounding wins”.

## 078.jpg/total_amount

Coupled extraction + schema failure: total_amount was emitted as an empty string instead of null. This receipt also contains an AMOUNT column header that can trigger split-line fallback to an item amount unless explicitly excluded, and OCR may corrupt both the GRAND TOTAL keyword and decimal separator (e.g., 92:80).

Evidence: Allowed feedback: 078.jpg amount_correct=false; prediction total_amount="" violates task requirement (must be null on failure). Source-run trace shows matching on “Description Qty Price Amount” and split-line fallback risk; OCR variants include “GrandTota.” and “92:80”. Even if extraction fails, output must be null, never empty string.

## 034.jpg/date

Date disambiguation failure: selection likely came from a secondary date-like token (or OCR-corrupted DATE label such as DATE→DATA) rather than the primary header Date field. Root cause is weak ranking/selection (e.g., first-match or frequency vote) when multiple plausible dates exist in header region.

Evidence: Allowed feedback: 034.jpg date_correct=false while amount_correct=true; prediction date=2018-08-09. The image shows a clear header block with a labeled Date field near the top (dd/mm/yyyy) and other header-adjacent metadata. Prior history and source-run OCR snippets show label corruption (e.g., “Salesperson: Data: …”) creating competing labeled candidates; first-match extraction is brittle in this scenario.

## 074.jpg/total_amount

Total selection failure driven by OCR digit-flip outlier (102.00→702.00) on a TOTAL-like line. The pipeline over-trusted a corrupted high-priority keyword match or a “last TOTAL wins” heuristic instead of enforcing receipt-internal anchor consistency (Subtotal/Payment/Total incl).

Evidence: Allowed feedback: 074.jpg amount_correct=false while date_correct=true; prediction total_amount=702.00. The receipt image contains multiple anchors around 102.00 (Subtotal, Total incl. of GST, Total Amt Rounded, Payment), while 702.00 is a classic OCR 1→7 digit flip. Source-run trace shows OCR variants can produce both values; robust selection must reject candidates contradicting multiple anchors even if they appear on a higher-priority keyword line.

## 077.jpg/total_amount

Rounding precedence failure: receipt shows an inclusive total, a rounding adjustment, then a final payable TOTAL; the pipeline selected the pre-rounding value instead of the final total after rounding, causing an exact-match miss (often by 0.01).

Evidence: Allowed feedback: 077.jpg amount_correct=false while date_correct=true; prediction total_amount=23.26. The image shows “Rounding Adj: -0.01” followed by bold “TOTAL: 23.25”, while an earlier line shows “Total (Inclusive of GST): 23.26”. This requires an unconditional precedence rule: if rounding adjustment exists and a later TOTAL exists, always take the later TOTAL.

## 078.jpg/total_amount

Coupled extraction + schema failure: total_amount was emitted as an empty string instead of null. This receipt also contains an “Amount” column header that can incorrectly trigger split-line fallback to an item amount unless explicitly excluded; OCR may corrupt both the GRAND TOTAL keyword and decimal separator (e.g., 92:80).

Evidence: Allowed feedback: 078.jpg amount_correct=false; prediction total_amount="" violates task requirement (must be null on failure). Source-run trace shows matching on the column header line “Description Qty Price Amount” and split-line fallback to an item amount; other OCR variants show “GrandTota.”/“GrandTotal.” and “92:80”, and a stronger OCR variant (3× upscale + PSM4) yields “Grand Total … 92.80”. Regardless of extraction outcome, empty string must be converted to null.
