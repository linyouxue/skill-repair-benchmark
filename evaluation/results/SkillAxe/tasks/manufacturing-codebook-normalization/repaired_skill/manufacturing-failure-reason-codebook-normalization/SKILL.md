This skill should be considered when you need to normalize, standardize, or correct testing engineers' written failure reasons to match the requirements provided in the product codebooks. Common errors in engineer-written reasons include ambiguous descriptions, missing important words, improper personal writing habits, using wrong abbreviations, improper combining multiple reasons into one sentence without clear spacing or in wrong order, writing wrong station names or model, writing typos, improper combining Chinese and English characters, cross-project differences, and taking wrong products' codebook.

Some codes are defined for specific stations and cannot be used by other stations. If entry.stations is not None, the predicted code should only be considered valid when the record station matches one of the stations listed in entry.stations. Otherwise, the code should be rejected.

For each record segment, the system evaluates candidate codes defined in the corresponding product codebook and computes an internal matching score for each candidate. You should consider multiple evidence sources to calculate the score to measure how well a candidate code explains the segment, and normalize the score to a stable range [0.0, 1.0]. Evidence can include:
- **Text evidence from span_text vs codebook text** (highest priority): overlap or fuzzy similarity between span_text and the codebook’s *standard_label*, *keywords_examples*, and/or *categories*.
- Station compatibility (hard constraint if station-scoped).
- fail_code alignment, test_item alignment.
- Conflict cues such as mutually exclusive or contradictory signals.

After all candidate codes are scored, sort them in descending order. Let c1 be the top candidate with score s1 and c2 be the second candidate with score s2. When multiple candidates fall within a small margin of the best score, the system applies a deterministic tie-break based on record context (e.g., record_id, segment index, station, fail_code, test_item) to avoid always choosing the same code in near-tie cases while keeping outputs reproducible.

## REQUIRED semantic-support guard for non-UNKNOWN
When you output a **non-UNKNOWN** pred_code, it must have **some lexical support in span_text** from the codebook entry’s text fields.

Implement this explicitly as a post-ranking (or integrated scoring) check:
- Build a token set from **span_text** (after basic normalization such as lowercasing and stripping punctuation / mixed CN-EN separators).
- Build a token set from the candidate codebook entry text (union of tokens from **standard_label + keywords_examples + category_lv1/lv2**).
- Compute a simple overlap metric (e.g., Jaccard = |A∩B|/|A∪B|, or at least require |A∩B|>0).

**Rule:** If the best candidate’s lexical overlap is near-zero (e.g., empty intersection or an overlap metric below a small floor), then you should usually output **pred_code="UNKNOWN"** unless there is a *direct* string/component match that your tokenizer would otherwise miss (e.g., a component reference like "R152", "U202", nets like "RESET_N", or obvious bilingual variants that can be normalized).

This guard is intentionally independent from station/fail_code/test_item cues: context can refine choices among lexically-supported candidates, but should not be the primary basis for selecting a known code when the span itself provides no textual support.

## Token/normalization guidance (to increase lexical support without cheating)
Engineer notes often contain typos, abbreviations, and Chinese/English mixtures. To better match codebook tokens while keeping predictions faithful to span_text:
- Normalize case, remove/standardize separators (/, -, _, Chinese punctuation), and split into tokens.
- Recognize common bilingual equivalents during tokenization (e.g., "治具"↔"fixture", "探针"↔"pogo/probe", "接触不良"↔"contact", "短路"↔"short", "开路"↔"open", "烧录"↔"program/flash", "校验"↔"verify/checksum/CRC").
- Treat component IDs and nets as strong tokens (e.g., R152, C87, U202, RESET_N, VDD_5V, GND).

These steps should improve genuine overlap between span_text tokens and codebook tokens, which helps avoid selecting known codes with near-zero evidence.

## Rationale requirements (make lexical support explicit)
To provide convincing answers, include **both**:
1) context: station, fail_code, test_item (when available), and
2) **a short explicit overlap cue**: quote 1–3 matching tokens that appear in span_text and in the chosen codebook entry (e.g., "short/短路", "R152", "CRC", "fixture/治具").

Avoid rationales that justify a known code using only station/fail_code/test_item if the span_text itself does not contain matching tokens.

UNKNOWN handling: UNKNOWN should be decided based on the best match only (i.e., after ranking), not by marking multiple candidates. If the best-match score is low (weak evidence), output pred_code="UNKNOWN" and pred_label="" to give engineering an alert. **Also output UNKNOWN when the semantic-support guard above fails (near-zero lexical overlap for the best candidate),** because that indicates the mapping is not grounded in the written reason segment.

When strong positive cues exist (e.g., clear component references or explicit defect terms), UNKNOWN should be less frequent than in generic or noisy segments.

Confidence calibration: confidence ranges from 0.0 to 1.0 and reflects an engineering confidence level (not a probability). Calibrate confidence from match quality so that UNKNOWN predictions are generally less confident than non-UNKNOWN predictions, and confidence values are not nearly constant. Confidence should show distribution-level separation between UNKNOWN and non-UNKNOWN predictions (e.g., means, quantiles, and diversity), and should be weakly aligned with evidence strength; round confidence to 4 decimals.

Here is a pipeline reference
1) Load test_center_logs.csv into logs_rows and load each product codebook; build valid_code_set, station_scope_map, and CodebookEntry objects.
2) For each record, split raw_reason_text into 1–N segments; each segment uses segment_id=<record_id>-S<i> and keeps an exact substring as span_text.
3) For each segment, filter candidates by station scope, then compute match score from combined evidence (text evidence, station compatibility, context alignment, and conflict cues).
4) Rank candidates by score; if multiple are within a small margin of the best, choose deterministically using a context-dependent tie-break among near-best station-compatible candidates.
5) Apply UNKNOWN decision:
   - If best evidence is weak by score, output UNKNOWN/"".
   - If best evidence is **not lexically supported by span_text tokens vs codebook tokens**, output UNKNOWN/"".
6) Output exactly one pred_code/pred_label per segment from the product codebook (or UNKNOWN/"" when best evidence is weak) and compute confidence by calibrating match quality with sufficient diversity; round to 4 decimals.
