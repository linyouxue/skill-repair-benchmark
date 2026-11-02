# Diagnosis Report: skillopt / jpg-ocr-stat

## 1. 诊断修复前轨迹
- baseline_result: `None`
- baseline comparable/pass: `None` / `None`
- baseline error category: `None`
- rollout_dir: `None`

## 2. 诊断定位的 skill，以及如何修复
- overall diagnosis: The agent's OCR pipeline passed 43/44 checks (reward 0.977). The sole failure is receipt 039.jpg (test_receipt_06_date): date extraction returned an incorrect/missing ISO date despite the amount being correct. Image 039.jpg (shown as the 7th image, the Perniagaan Zheng Hui receipt) has the date 'Date: 09/03/2018' near 'Receipt #' and 'Cashier: USER'. The pipeline's date voting across OCR variants likely picked up a different date-like token (e.g., GA1801 handwritten annotations or misread of the slash) or failed to parse the format reliably on this slightly noisy scan. The image-ocr skill (which drives OCR extraction and date parsing heuristics) is the relevant skill to repair; other skills (xlsx output format, openai-vision, pdf, video) are not implicated.
- diff: `/Users/elsie/Desktop/SkillOpt-eva/experiments/opus47-gold15-jpg-refresh-v3-20261025/methods/skillopt/jpg-ocr-stat/diff.patch`
- `image-ocr/SKILL.md` diagnosed=True confidence=0.85
  - diagnosis: Date extraction heuristic fails on 039.jpg (Perniagaan Zheng Hui receipt). The receipt clearly shows 'Date: 09/03/2018' adjacent to 'Receipt #: CS00084670' and 'Cashier: USER', with handwritten 'GA1801'/'GB1801' annotations next to each line item that can mislead date voting. The skill likely either (a) picks a non-date numeric token biased by handwritten '1801' tokens, (b) fails to anchor to the 'Date:' label when it appears on the same line as a time, or (c) relies on majority voting across OCR variants where the degraded scan produces inconsistent reads of the slash separator.
  - repair: Strengthen date extraction in image-ocr/SKILL.md: (1) Give strong priority to tokens on lines that explicitly contain 'Date', 'Tarikh', 'Dated', or 'Receipt' labels, over any voting from unlabeled numeric tokens. (2) Explicitly ignore handwritten-style short alphanumeric tokens like 'GA1801', 'GB1801', 'A03041' when scanning for dates (reject tokens with mixed leading letters). (3) When a label line contains both a date and a time (e.g., 'Date: 09/03/2018  Time: 08:49:00'), split on whitespace and parse the date substring independently. (4) Add a fallback: if the primary date vote has low confidence, re-run OCR on just the top-right header region (where 'Date:' typically appears on tax-invoice receipts) at higher DPI with PSM 6. (5) Add a sanity check that the extracted year is plausible (2015–2019 range for this dataset) to reject spurious matches like '1801'.
  - change_summary: ['replace:applied_replace', 'replace:applied_replace', 'insert_after:applied_insert_after']
  - diff_stats: {'added_lines': 268, 'removed_lines': 0}
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
- `xlsx/SKILL.md` diagnosed=False confidence=n/a
  - diagnosis: 
  - repair: 
  - change_summary: []
  - diff_stats: {'added_lines': 58, 'removed_lines': 0}

## 3. 是否修复成功及原因
- comparable/pass: `True` / `False`
- skill_exposure_verified: `True`
- outcome_category: `located_but_not_fixed`
- analysis: A skill was localized and rewritten, but the comparable method-skill run still failed; likely causes are insufficient repair content or downstream model execution limits.

## 4. 修复时间及成本开销
- optimizer total tokens: `60388`
- optimizer duration sec: `68.429`
- baseline evaluation: `{'wall_time_sec': None, 'cost_usd': None, 'provider_requests': None, 'agent_iterations': None, 'termination_reason': None}`
- method evaluation: `{'wall_time_sec': 1270.6, 'cost_usd': 9.9332625, 'provider_requests': 31, 'agent_iterations': 31, 'termination_reason': 'end_turn'}`
- known_total_cost_usd: `9.9332625`
