# Diagnosis Report: skillopt / jpg-ocr-stat

## 1. 诊断修复前轨迹
- baseline_result: `/Users/elsie/Desktop/SkillOpt-eva/experiments/gpt52-31-skillopt-evidencefix-v2-20261017/baseline/original-skill/jpg-ocr-stat/benchmark_result.json`
- baseline comparable/pass: `True` / `False`
- baseline error category: `None`
- rollout_dir: `/Users/elsie/Desktop/SkillOpt-eva/experiments/gpt52-31-skillopt-evidencefix-v2-20261017/jobs/baseline-original-skill/jpg-ocr-stat-original-skill-v11x-20260903-r001-recovery001`

## 2. 诊断定位的 skill，以及如何修复
- overall diagnosis: Across samples, two consistent failure modes appear: (1) the system sometimes fails to reliably produce the required XLSX artifact (likely due to long-running/stalled batch OCR without robust timeout/checkpoint/atomic-save patterns), and (2) when an XLSX is produced, many date/total fields are blank or wrong compared to the oracle, indicating insufficient receipt-specific OCR robustness and post-OCR parsing/validation heuristics (e.g., selecting subtotals/unit prices, missing split keyword/value across lines, weak date normalization). The most implicated skills are image-ocr (primary OCR quality + receipt parsing + runtime reliability) and xlsx (benchmark-safe, deterministic, strict-structure workbook writing and ensuring the output file exists). openai-vision is only an optional fallback and is lower priority.
- diff: `/Users/elsie/Desktop/SkillOpt-eva/experiments/gpt52-31-skillopt-evidencefix-v2-20261017/methods/skillopt/jpg-ocr-stat/diff.patch`
- `image-ocr/SKILL.md` diagnosed=True confidence=0.88
  - diagnosis: Guidance is too generic and JSON-oriented for a receipt-stat extraction task. It under-specifies receipt-oriented preprocessing (contrast/threshold/denoise/deskew), Tesseract configuration for receipts and numeric fields (PSM/OEM selection, digit/currency whitelists), multi-pass/ROI strategies (e.g., bottom-of-receipt totals), and—critically—deterministic field extraction logic for date and total with validation. It also lacks operational guidance for batch reliability (per-image timeout, progress logging/checkpointing) which correlates with the observed missing output artifact in baseline.
  - repair: Extend the skill with a focused 'Receipt OCR pipeline for (date, total_amount)' section: (1) lightweight preprocessing recipe (grayscale→autocontrast→optional upscale→adaptive threshold/denoise; optional rotation/deskew cues), (2) recommended Tesseract configs for receipts with examples (e.g., --oem 1 and psm {6,4,11}, preserve_interword_spaces; separate numeric-focused config with whitelist for digits/currency/.,-), (3) bounded multi-pass strategy (try 1–2 configs; optional ROI second pass on bottom 30–40% for totals) selecting best output via confidence (image_to_data mean/conf filtering), (4) robust parsing heuristics: keyword-tier search for totals with exclusion keywords (subtotal/tax/change/discount), same-line + next-line fallback, money regex supporting thousands separators, and plausibility rules (prefer largest plausible total near bottom; avoid unit prices), (5) date extraction supporting multiple formats + month names and normalization to ISO with year-range plausibility checks, (6) batch reliability: per-image timeouts, progress checkpoints, and guarantee final artifact creation even with partial failures (record warnings per file).
  - change_summary: ['insert_after:applied_insert_after', 'insert_after:applied_insert_after', 'replace:applied_replace', 'append:applied_append']
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
- `xlsx/SKILL.md` diagnosed=True confidence=0.7
  - diagnosis: Current Excel guidance is broad/modeling-focused and does not strongly emphasize benchmark-style strictness: exact single-sheet constraint, exact headers/columns, deterministic row ordering, correct null handling (empty cells rather than literal strings), and post-save verification/atomic write. This maps to both the 'file not found' failure mode and line-by-line oracle mismatches caused by structural/representation differences.
  - repair: Add a 'Benchmark/SkillsBench strict-output mode' subsection: (1) create exactly one worksheet with the required name; remove extras; (2) write the exact header row and column order only—no helper sheets/columns/formatting artifacts; (3) sort rows deterministically (e.g., by filename) before writing; (4) represent missing values as true empty cells (None) and never write 'null'/'N/A' unless explicitly required; (5) save to the exact required path and use atomic save (tmp then rename) to avoid partial/missing files; (6) immediately validate after save (file exists, can be reopened, sheetnames match, expected row count). Include a minimal openpyxl example implementing these checks.
  - change_summary: ['insert_after:applied_insert_after', 'insert_after:applied_insert_after', 'insert_after:applied_insert_after', 'insert_after:applied_insert_after']
  - diff_stats: {'added_lines': 0, 'removed_lines': 0}

## 3. 是否修复成功及原因
- comparable/pass: `True` / `False`
- skill_exposure_verified: `True`
- outcome_category: `located_but_not_fixed`
- analysis: A skill was localized and rewritten, but the comparable method-skill run still failed; likely causes are insufficient repair content or downstream model execution limits.

## 4. 修复时间及成本开销
- optimizer total tokens: `10257`
- optimizer duration sec: `11.692`
- baseline evaluation: `{'wall_time_sec': 2967.4, 'cost_usd': 0.9739317, 'provider_requests': 32, 'agent_iterations': 32, 'termination_reason': 'stuck'}`
- method evaluation: `{'wall_time_sec': 2967.4, 'cost_usd': 0.9739317, 'provider_requests': 32, 'agent_iterations': 32, 'termination_reason': 'stuck'}`
- known_total_cost_usd: `1.9478634`
