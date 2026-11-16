# Diagnosis Report: skillopt / jpg-ocr-stat

## 1. 诊断修复前轨迹
- baseline_result: `/Users/elsie/Desktop/SkillOpt-eva/experiments/opus47-15-skillopt-opus47-tatu-20261008/baseline/original-skill/jpg-ocr-stat/benchmark_result.json`
- baseline comparable/pass: `True` / `False`
- baseline error category: `None`
- rollout_dir: `/Users/elsie/Desktop/SkillOpt-eva/experiments/opus47-15-skillopt-opus47-tatu-20261008/jobs/baseline-original-skill/jpg-ocr-stat-opus47-original-skill-r003-infra-recovery`

## 2. 诊断定位的 skill，以及如何修复
- overall diagnosis: The task requires OCR extraction of date and total_amount from receipt images and writing results to a single-sheet XLSX. All three samples agree the baseline failed on 078.jpg because the Grand Total '92.80' could not be reliably extracted. The image-ocr skill is the primary gap: it lacks a documented multi-variant preprocessing + voting strategy (notably 3x LANCZOS upscale with --psm 4), keyword-priority total extraction with exclusion keywords and comma/thousand-separator handling, two-line fallback for split keyword/value layouts, and ISO date normalization. The xlsx skill is a minor secondary concern around preserving '92.80'/'47.70' as exact strings (not float-coerced) and writing true blank cells for nulls on a single 'results' sheet. A prior patch adding a detailed Receipt OCR recipe + voting + extractors was rejected under gate_no_improve, so the new repair should take a different angle: rather than re-adding the same large code recipe verbatim, provide a more concise decision-oriented guidance block emphasizing when to escalate to 3x+PSM4, how to validate extracted totals via cross-variant agreement, and when to emit null — plus a short, targeted xlsx note on strict output typing.
- diff: `/Users/elsie/Desktop/SkillOpt-eva/experiments/opus47-15-skillopt-opus47-tatu-20261008/methods/skillopt/jpg-ocr-stat/diff.patch`
- `image-ocr/SKILL.md` diagnosed=True confidence=high
  - diagnosis: The skill documents only basic pytesseract usage. It lacks: (1) decision guidance on when to escalate from default OCR to aggressive preprocessing (3x LANCZOS upscale + grayscale + autocontrast + --psm 4) specifically for faint/compressed receipt totals like 'Grand Total 92.80' that other variants miss; (2) a lightweight cross-variant agreement check to validate monetary extractions before accepting them (reduces false positives from a single noisy pass); (3) a prioritized keyword/exclusion list for receipt total extraction (GRAND TOTAL > TOTAL RM > TOTAL AMOUNT > TOTAL/AMOUNT/BALANCE DUE/NETT TOTAL; exclude SUBTOTAL, TAX, GST, SST, DISCOUNT, CHANGE, CASH TENDERED); (4) handling for two-line keyword/value layouts (amount on the next non-empty line); (5) numeric normalization — comma thousand separators, OCR confusions (O/0, l/1, S/5), stripping spaces inside numbers like '92 80'; (6) ISO date normalization across DD/MM/YYYY, DD-MM-YY, DD.MM.YYYY, DD MMM YYYY, YYYY-MM-DD. The previous round's large verbatim recipe patch did not improve results, so this round should favor concise decision guidance plus a compact, explicit escalation checklist rather than one monolithic code block.
  - repair: Rewrite the receipt-OCR guidance as a concise, decision-oriented checklist (not a single long code dump). Specifically: (a) Add an 'Escalation ladder' subsection listing OCR passes in strict order to try and clearly state that pass 4 (3x LANCZOS upscale on grayscale+autocontrast image with --psm 4) MUST be attempted before emitting null for a total — call out that this is the pass that recovers faint Grand Total lines such as '92.80' on 078.jpg-style receipts. The ladder: (1) default pytesseract, (2) grayscale+autocontrast PSM 6, (3) 2x LANCZOS upscale grayscale+autocontrast PSM 6, (4) 3x LANCZOS upscale grayscale+autocontrast PSM 4, (5) sharpened/unsharp-mask variant PSM 11. (b) Add a 'Cross-variant validation' note: run >=3 passes, collect candidate totals via the keyword parser, and prefer the value that appears in >=2 passes; only fall back to the pass-4 value alone if nothing else matched. (c) Provide ONE small, focused code snippet (<~30 lines) for the keyword-priority total parser with priority groups, exclusion keywords, a regex r'(?<![\d.])\d{1,3}(?:,\d{3})*\.\d{2}(?!\d)', two-line fallback (take last decimal number on the next non-empty line), comma stripping, and '{:.2f}' formatting. (d) Add a compact date-normalization helper covering the five common formats and returning ISO YYYY-MM-DD. (e) Explicitly state the null policy: emit None only when ALL five escalation passes yield no candidate from the keyword parser. (f) Avoid repeating the exact monolithic 'Robust Receipt / Low-Quality OCR Recipe' structure from the rejected patch; frame as guidance + minimal snippets so the agent internalizes the escalation decision rather than copy-pasting one large function.
  - change_summary: ['replace:applied_replace', 'insert_after:applied_insert_after']
  - diff_stats: {'added_lines': 0, 'removed_lines': 0}
- `openai-vision/SKILL.md` diagnosed=False confidence=n/a
  - diagnosis: 
  - repair: 
  - change_summary: []
  - diff_stats: {'added_lines': 0, 'removed_lines': 0}
- `pdf/SKILL.md` diagnosed=False confidence=n/a
  - diagnosis: 
  - repair: 
  - change_summary: []
  - diff_stats: {'added_lines': 0, 'removed_lines': 0}
- `video-frame-extraction/SKILL.md` diagnosed=False confidence=n/a
  - diagnosis: 
  - repair: 
  - change_summary: []
  - diff_stats: {'added_lines': 0, 'removed_lines': 0}
- `xlsx/SKILL.md` diagnosed=True confidence=low
  - diagnosis: The xlsx skill is used to emit the final workbook. Baseline structure (single 'results' sheet, header, 3 columns, filename ordering) was already correct, so this is secondary. However, the skill does not explicitly document how to preserve formatted monetary strings like '92.80' or '47.70' as exact text (openpyxl will otherwise coerce to float and drop trailing zeros), nor how to write true blank cells (None) rather than empty strings for missing extractions — both can matter for oracle comparisons.
  - repair: Add a short 'Strict single-sheet output' subsection with ~10 lines of openpyxl showing: create Workbook, rename default sheet to the exact required name (e.g., 'results'), append the header row, append data rows writing formatted decimals as Python str (e.g., '92.80') and missing values as Python None (not '' or 'None'), optionally set column number_format='@' to force text format, verify wb.sheetnames == ['results'] before saving so no extra sheets are present, and sort rows by the key column (filename) prior to writing.
  - change_summary: ['insert_after:applied_insert_after', 'insert_after:applied_insert_after', 'insert_after:applied_insert_after']
  - diff_stats: {'added_lines': 0, 'removed_lines': 0}

## 3. 是否修复成功及原因
- comparable/pass: `True` / `False`
- skill_exposure_verified: `True`
- outcome_category: `located_but_not_fixed`
- analysis: A skill was localized and rewritten, but the comparable method-skill run still failed; likely causes are insufficient repair content or downstream model execution limits.

## 4. 修复时间及成本开销
- optimizer total tokens: `14679`
- optimizer duration sec: `26.896`
- baseline evaluation: `{'wall_time_sec': 1436.7, 'cost_usd': None, 'provider_requests': 65, 'agent_iterations': 65, 'termination_reason': 'max_iterations'}`
- method evaluation: `{'wall_time_sec': 1436.7, 'cost_usd': None, 'provider_requests': 65, 'agent_iterations': 65, 'termination_reason': 'max_iterations'}`
- known_total_cost_usd: `0`
