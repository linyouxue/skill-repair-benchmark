# Codebook-Grounded Failure Reason Normalization

## Purpose
Map engineer-written failure reason text to standardized codes from a product-specific codebook, producing one pred_code per segment that is grounded in codebook rows and station scope, not in narrative properties of the output.

## When to Use
Use when the task provides (a) a log file of test records with raw reason text and context fields (station, fail_code, test_item, product) and (b) one or more product codebooks defining valid codes with labels, keywords/examples, categories, and optional station scope, and asks you to emit normalized predictions per segment.

## Procedure
- Discover inputs: list the working directory and identify the log file and codebook files; load them and print column names. Verify required fields exist (raw reason text, station, product, and codebook fields for code, label, keywords/examples, and optional stations). Do not assume filenames.
- Build indices per product codebook: valid_code_set, station_scope_map (code -> allowed stations or None), and a keyword->code inverted index tokenized from standard_label, keywords_examples, and categories (lowercased, punctuation-stripped, both English and any non-English tokens kept verbatim).
- Segment each record: split raw reason text into 1..N segments on clear delimiters (semicolons, slashes, commas, line breaks, multiple spaces); assign segment_id = <record_id>-S<i> and keep the exact substring as span_text.
- Filter and score candidates per segment: drop any code whose station_scope is not None and does not include the record station (hard precondition). For remaining candidates compute score = w1*token_overlap(span_text, code_keywords) + w2*fail_code_match + w3*test_item_match - w4*conflict_penalty, normalized to [0,1]. Sort descending; break ties deterministically on (record_id, segment_index, code).
- Decide output: if top score >= T_match emit pred_code=top.code, pred_label=top.label; else emit pred_code="UNKNOWN", pred_label="". Set confidence = round(clip(top_score, 0, 1), 4); UNKNOWN rows must occupy a lower confidence band than matched rows (e.g., map UNKNOWN confidence through a separate lower sub-interval of the score).
- Post-write verification (execution anchor): reload the produced output file and assert, printing counts: (1) every pred_code is in valid_code_set or equals "UNKNOWN"; (2) for every non-UNKNOWN prediction, record station is allowed by station_scope_map; (3) confidence values have 4 decimals and are not all identical. If any assertion fails, fix and rewrite before declaring done.

## Constraints / Pitfalls
- Do not self-validate on confidence distribution shape alone; the verifier scores code-to-ground-truth mapping, so correctness of pred_code is primary.
- Do not hard-code filenames, column names, product names, or thresholds not present in the task; discover them from the environment and declare chosen weights/thresholds explicitly in a short config block in your run log.
- Station scope is a hard filter, not a soft signal: a code with incompatible station must never be emitted, even if textual overlap is high.
- Never invent codes: pred_code must be literally present in the product codebook row set or be "UNKNOWN".
- Keep rationale fields (if emitted) tied to concrete evidence (matched tokens, fail_code, test_item); do not fabricate component references to appear confident.
- If required input fields are missing or codebooks cannot be matched to a product, stop and report the gap rather than guessing a mapping.