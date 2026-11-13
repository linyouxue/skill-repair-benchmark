# Per-task overlay — iter_0

Context: every entry below is a window-view of the same failed task
`jpg-ocr-stat` (22-receipt Malaysian-receipt OCR → xlsx; reward 0.0 binary /
0.909 field; `termination_reason: max_iterations`, 65/65). The four
field-level errors are invariant across windows: 034 date `2018-08-09`,
074 amount `702.00`, 077 amount `23.26`, 078 amount empty. Each window
emphasises a different mechanism and therefore maps to a different primary
pattern; secondary patterns are mentioned in `gap` where relevant.

### [w0001] amount digit confusion, TOTAL-tier tie-break, layout-collapse amount, date tokenisation near time field
- signal: failure
- pattern: amount-candidate-selection-within-total-tier
- anchor: receipt-total-selection
- gap: w0001 is the first full enumeration of all four failures from pixels. For 074 `702.00`, the hint-driven keyword logic was correct but OCR already corrupted the token (`1→7` on thin-stroke 102.00) — no cross-line consensus check across the 4+ occurrences of 102.00. For 077 `23.26`, keyword-priority ambiguity between `Total (Inclusive of GST): 23.26` and the final bold `TOTAL: 23.25`; both match the same tier with no sub-ranking. For 078 null, OCR split keyword from number across a wide tabular layout and the "next line last number" fallback never fired. For 034, DD/MM/YYYY parse is correct but the date extractor isn't anchored to the `Date:` label.
- proposed_change: patcher should fan-out across two existing SKILL.md sections — (a) extend the `Multi-Pass OCR Strategy` section to explicitly describe candidate aggregation (not just `"\n".join`), and (b) add a new `receipt-total-selection` reference chapter covering within-tier specificity ranking, within-text frequency consensus, and the Rounding-Adj positional rule. Both anchor slugs stay (none yet) until the patcher creates content.

### [w0002] multi-pass OCR documented but not invoked; strict keyword/regex parser
- signal: failure
- pattern: single-pass-ocr-default
- anchor: multi-pass-ocr-strategy
- gap: w0002 confirms from timeline a0006/a0007/a0008 that every OCR call was `pytesseract.image_to_string(img)` on raw PIL — no grayscale, autocontrast, invert, upscale, threshold, no multi-PSM. The current SKILL.md body has a `multi_pass_ocr` function example but presents it as optional ("for challenging images") rather than default for receipt-grade tasks, and its aggregation strategy (`"\n".join(all_text)`) does not prescribe how to reconcile disagreements between passes. Also calls out `92:80`/`92 80` decimal-loss on 078 that a strict `\d+\.\d{2}` regex rejects.
- proposed_change: in SKILL.md body, elevate `multi_pass_ocr` from optional guidance to a mandatory step for low-contrast receipt/scanned-document OCR. Replace the `"\n".join(all_text)` aggregation with a candidate-collection pattern (per-pass line list + voting in the downstream extractor). Add a one-liner noting that the strict 2-decimal regex must be paired with same-line normalisation of `:`/`;` → `.` when matched against a known-amount keyword line.

### [w0003] tier-exit bug + "last candidate only" within tier; also 034 date anchor
- signal: failure
- pattern: amount-candidate-selection-within-total-tier
- anchor: receipt-total-selection
- gap: Source shows `extract_total` iterating tiers but only probing `candidates[-1]` per tier; if that single line yields no number, fallback runs then the tier returns None without revisiting earlier candidates. This structurally prevents recovery when the LAST tier-matched line is OCR-corrupted (074) or layout-wrapped (078). Window also flags 034 date needs anchoring to a `Date:` label vs free regex search across the entire text.
- proposed_change: the receipt-total-selection reference chapter must describe tier iteration in REVERSE across all candidates (not just the last), with a cleanliness/corruption penalty and within-text frequency corroboration. Separately, patcher should add a receipt-date-extraction section covering label anchoring.

### [w0004] psm=6+autocontrast proved better on 10 receipts but delivered xlsx didn't ship with it on 078; 034 regression
- signal: failure
- pattern: iteration-budget-and-pipeline-order
- anchor: pipeline-order-and-budget
- gap: Agent proved mid-run that psm=6+autocontrast recovers 074's clean `102.00` and 078's `92.80` in isolation, then subsequent patches regressed 078 (92.80→null) and 034 (correct→wrong). The shipped artifact predates the best-known algorithm because the pipeline rewrote xlsx after every change but validated only one receipt at a time, so later edits silently regressed earlier wins.
- proposed_change: patcher should add an explicit workflow note (either in image-ocr SKILL.md body or in a new L3 chapter `pipeline-order-and-budget`) mandating: cache multi-variant OCR once, iterate on extractor logic in-memory, re-run full 22-image end-to-end on EVERY extractor edit, write xlsx only after full-corpus validation.

### [w0005] default-first vs preprocessed-first ordering oscillation
- signal: failure
- pattern: single-pass-ocr-default
- anchor: multi-pass-ocr-strategy
- gap: "First non-None wins" across OCR variants defeats the purpose of running multiple variants: whenever default returns a plausible-but-wrong value (034 date, 077 amount), the better preprocessed pass is skipped; whenever preprocessed loses a decimal (052 `10.00`→`1000`), default rescues it. There is no ordering that strictly dominates; the fix axis is candidate aggregation, not pass ordering.
- proposed_change: in the multi-pass-ocr-strategy anchor, explicitly contrast "first-non-None-wins" (wrong) vs "collect candidates from all passes, score and vote" (right), and require the latter for receipt tasks.

### [w0006] 3-variant voting + consensus layer causes new regressions on 034/064/078 while fixing 071/074 variant 2
- signal: failure
- pattern: amount-candidate-selection-within-total-tier
- anchor: receipt-total-selection
- gap: Adding upscaled variant 2 + `pick_best_total` majority voting at (tier, count, order) regressed 034 (2/3 variants share the 3→8 misread, so majority vote entrenches the wrong digit), 064 (noisy variant escalates tier via next-line fallback onto Visa RM), 078 (Cash Received leak). Raw across-variant majority is wrong when a value is confirmed by multiple non-tier lines in a single variant.
- proposed_change: receipt-total-selection reference must explicitly prefer within-text frequency (same value appearing on Subtotal/Payment/Rounded in one variant) OVER cross-variant majority as the primary selector; cross-variant majority is only a final tiebreaker.

### [w0007] 064 fallback leak fixed; 077 regressed via flat count voting; 078 column-header `AMOUNT` leak into item row; 074 cross-line vs cross-variant
- signal: failure
- pattern: amount-candidate-selection-within-total-tier
- anchor: receipt-total-selection
- gap: Flat `(tier, value)` count voting loses the per-variant "last keyword match wins" positional signal — on 077, if one of three variants drops the final `TOTAL: 23.25` line, counts become 23.26:3, 23.25:2 and 23.26 wins. Also confirms `AMOUNT` keyword matches the column header `Description Qty Price Amount`, triggering fallback into item rows on 078.
- proposed_change: within-variant selection must be done FIRST (reversed, specificity-ranked); cross-variant voting is a second-stage tiebreaker only. Add column-header exclusion (`DESCRIPTION`, `QTY PRICE AMOUNT`) as a documented rule in exclusion-and-fallback reference.

### [w0008] final-window: 3× PSM-4 variant added at a0073, run never re-executed before max_iterations
- signal: failure
- pattern: iteration-budget-and-pipeline-order
- anchor: pipeline-order-and-budget
- gap: Last action added a demonstrably-recovering OCR variant (`upscale 3x gray, psm=4 → 'Grand Total a 92.80'`) but iteration budget ran out before re-executing `extract.py`. The shipped xlsx reflects the state after a0069, not a0073. Four known fixes (relax `GRAND\s*TOTAL` to tolerate missing whitespace, DD/MM default on day≤12, cross-line corroboration for 074, final-TOTAL preference on 077) were not pursued.
- proposed_change: pipeline-order-and-budget reference must mandate atomic re-run after any extractor edit; patcher should also widen `GRAND\s+TOTAL` regex to `GRAND\s*TOTA[LI1!]?\.?` as a specific rule under receipt-exclusion-and-fallback.

### [w0009] full enumeration — numeric-region re-OCR, tie-breaker for TOTAL, layout-aware GRAND TOTAL, date anchoring
- signal: failure
- pattern: amount-candidate-selection-within-total-tier
- anchor: receipt-total-selection
- gap: w0009 is a strong cross-receipt summary — same four causes across four receipts. Adds a concrete mechanism (image_to_data bbox to find right-aligned numeric token on the same vertical band as a `GRAND TOTAL` keyword) that prior windows didn't propose. Confirms "No systematic locale bug" (21/22 dates correct), so date fix should be narrow.
- proposed_change: in receipt-total-selection, add layout-aware fallback using `pytesseract.image_to_data` bbox proximity for cases where OCR text-line adjacency fails (078). Keep the date fix minimal (label anchoring only).

### [w0010] pure OCR character errors on 034/074, decimal-separator OCR corruption on 078, fuzzy keyword for `GrandTota.`
- signal: failure
- pattern: single-pass-ocr-default
- anchor: multi-pass-ocr-strategy
- gap: Confirms OCR dump shows `Data: 09/08/2018` (3→8 confusion) and `Toial Amt Rounded oO yo2.00` (digit garble). Strict `\d+\.\d{2}` + strict `\bGRAND\s+TOTAL\b` combine to block 078 completely because OCR delivered `GrandTota. = tS 92.80` (no word boundary between `Grand` and `Tota`). Noted `n_skill_invocations=0` — Skill's own multi-pass example not used.
- proposed_change: multi-pass-ocr-strategy anchor must note that fuzzy keyword matching (allow 0–1 non-alphanumeric between words, strip trailing `.`) is required when OCR concatenates tokens. Add a `GrandTota` / `GRANDTOTAL` / `GrandTotai` tolerance example.

### [w0011] null-encoding bug for 078; priority-tier ordering should surface "rounded/final" totals
- signal: failure
- pattern: exclusion-and-fallback-keyword-gaps
- anchor: receipt-exclusion-and-fallback
- gap: Two concrete gaps: (a) 078's delivered cell is `""` instead of null — xlsx write step converts missing to empty string; (b) new tier ABOVE `TOTAL` should match `TOTAL ROUNDED`/`ROUNDED TOTAL`/`TOTAL AFTER ROUNDING`/`TOTAL AMT ROUNDED`/`GRAND TOTAL`. Also proposes `Rounding Adj(ustment)` as a POSITIONAL signal (prefer TOTAL after it) without excluding it.
- proposed_change: in receipt-exclusion-and-fallback, add explicit rules: (i) write `None` not `""` for unknown totals; (ii) add rounded-total keyword cluster as top priority; (iii) treat `Rounding Adj` as a positional anchor, not an exclusion.

### [w0012] PSM 6 preprocessed OCR dumps show clean totals for 10 receipts; m0039/m0045 diagnoses tier-4 "last wins" selection bug
- signal: failure
- pattern: single-pass-ocr-default
- anchor: multi-pass-ocr-strategy
- gap: PSM 6 preprocessed OCR yields clean `Subtotal 102.00`, `Total incl. of GST 102.00` for 074, clean `Total Rounded 26.60` for 009, clean large `TOTAL: 23.25` for 077. Switch to PSM 6 preprocessed strictly dominates default on 8/10 sampled receipts. Agent started the fix in m0051 (exclusion additions) but never reached a re-run before termination.
- proposed_change: multi-pass-ocr-strategy anchor must recommend preprocessed+PSM 6 as the PRIMARY pass (not fallback) for receipt OCR, with default PSM 3 kept as a secondary variant for voting.

### [w0013] first-non-None-wins routing, last-match-in-reverse corruption penalty, decimal-separator loss
- signal: failure
- pattern: single-pass-ocr-default
- anchor: multi-pass-ocr-strategy
- gap: Three interacting failures: (a) `ocr_variants` short-circuits on first non-None field, so 034 default-wrong wins over 034 preprocessed-right; (b) "last match in reverse" within a tier has no corruption filter — 074's `Total Amt Rounded ——S«702.00` line's non-alphanumeric glyph density signals noise but isn't penalised; (c) `extract_last_number` rejects `92 80` / `92:80` so 078's keyword line yields None and fallback walks into Cash Received.
- proposed_change: multi-pass-ocr-strategy must describe candidate aggregation across ALL variants (not first-wins); receipt-total-selection must add a cleanliness heuristic (ratio of non-alphanumeric chars on candidate line) and decimal-recovery for keyword-matched lines.

### [w0014] single-pass shipped, upscaled proven, never integrated
- signal: failure
- pattern: single-pass-ocr-default
- anchor: multi-pass-ocr-strategy
- gap: Agent demonstrated in m0098/m0110/m0113 that 2× upscale + autocontrast + PSM 6 correctly reads 102.00 on every total line of 074 and uniquely captured the final `TOTAL: 23.25` for 077, but shipped `extract.py` uses only default OCR + autocontrast PSM 6. Hint's "split-line fallback" ("use last number on the next line") was never implemented. Also m0087 tightened `NUM_RE` to `\d+\.\d{2}` which removed 078's recoverable `92 80` candidate.
- proposed_change: multi-pass-ocr-strategy must require ≥3 variants (default, preprocessed PSM 6, upscaled 2× PSM 6) with consensus; split-line fallback must be documented as mandatory for receipt amount extraction.

### [w0015] default-first vs preprocessed-first sequencing, 078 fragile, 052 brittle recovery
- signal: failure
- pattern: amount-candidate-selection-within-total-tier
- anchor: receipt-total-selection
- gap: Each OCR pass is strictly better on some images and strictly worse on others in the same window — 034/077 want preprocessed PSM 6, 052 wants default (preprocessed reads `GRAND TOTAL 1000` losing the decimal). Pass ordering alone cannot win; aggregation must be at the candidate level with consensus.
- proposed_change: receipt-total-selection anchor must prescribe candidate-level aggregation (union candidates from all variants, prefer values whose exact 2-decimal string appears multiple times across lines/variants), with an explicit note that 078 must be pinned via regression test before further NUM_RE edits.

### [w0016] 064 Visa-RM leak fix; new majority-voting regressions on 074/077/078
- signal: failure
- pattern: exclusion-and-fallback-keyword-gaps
- anchor: receipt-exclusion-and-fallback
- gap: Mid-run "fallback only if keyword line has no digits" (m0147) correctly fixes 064's Visa RM leak. But the new `extract_total_candidates` + majority voting then produces: 074=702 (2 bad variants beat 1 good), 077=23.26 (bare `TOTAL:` line OCR-mangled on bold font), 078=20.00 then null (`AMOUNT` matches `Description Qty Price Amount` header, falls into item row; later patch nulls it). Core defect: majority voting without within-text cross-line corroboration.
- proposed_change: in receipt-exclusion-and-fallback, keep the "fallback requires zero digits on keyword line" rule; add header-column exclusions (`DESCRIPTION`, `QTY PRICE AMOUNT`); in receipt-total-selection, mandate within-text frequency check before any cross-variant vote.

### [w0017] 078 trace: `AMOUNT` matches column header; 3× upscale PSM 4 recovers `Grand Total a 92.80`
- signal: failure
- pattern: exclusion-and-fallback-keyword-gaps
- anchor: receipt-exclusion-and-fallback
- gap: m0176 trace shows variant 0 of 078 has tier-4 `AMOUNT` matching `Description Qty Price Amount` (no digits → fallback chains to item row 20.00) and `Total — 92:80` (colon-decimal → no number parsed). m0180 fix adds `\bDESCRIPTION\b` and `\b(QTY|PRICE)\s+AMOUNT\b` exclusions — correct direction. m0191 proves 3× upscale + PSM 4 recovers clean `Grand Total a 92.80`; m0195 adds it as a 4th variant but never re-runs.
- proposed_change: receipt-exclusion-and-fallback must include column-header exclusions and the colon→period same-line normalisation for keyword-matched lines; multi-pass-ocr-strategy must add 3× upscale + PSM 4 as a required variant.

### [w0018] highest-level summary of all four causes
- signal: failure
- pattern: amount-candidate-selection-within-total-tier
- anchor: receipt-total-selection
- gap: Clean cross-cutting enumeration: (a) 034 date needs Malaysian DD/MM/YYYY lock + label anchor + sanity month≤12; (b) 074 needs cross-amount consensus across Subtotal/Total/Rounded/Payment; (c) 077 needs "last TOTAL after Rounding Adj wins"; (d) 078 needs column/TSV-based fallback with PSM retries. Notes that the Skill bundle describes multi-pass/preprocessing but was not invoked and does not cover Malaysian date locale, post-rounding TOTAL preference, consensus voting, or column-aware fallback.
- proposed_change: patcher should fan out across both L2 (image-ocr SKILL.md body) and new L3 chapters covering receipt-total-selection, receipt-exclusion-and-fallback, and receipt-date-extraction.

### [w0019] visible `extract.py` + m0045 misjudgement that 23.26 is correct
- signal: failure
- pattern: amount-candidate-selection-within-total-tier
- anchor: receipt-total-selection
- gap: m0045 shows the agent's semantic misjudgement: "the printed final is 23.25, so 23.26 was wrong" — the opposite of the oracle convention (final rounded TOTAL below Rounding Adj is authoritative). This is a prompt/Skill gap: no documented rule tells the executor that the post-rounding bold `TOTAL:` is always authoritative over the pre-rounding `Total (Inclusive of GST)`.
- proposed_change: receipt-total-selection L3 chapter must contain an explicit rule: "When a bare `TOTAL:` line appears below a `Rounding Adj` / `ROUNDED` line, that line is authoritative and outranks any preceding `Total (Inclusive of GST)` / `Total (Excluding GST)` in the same keyword tier."

### [w0020] single-OCR-pass fragility; reverse-iteration trusts last line; summary cutoff risks 078
- signal: failure
- pattern: single-pass-ocr-default
- anchor: multi-pass-ocr-strategy
- gap: Agent's own thinking (m0045, m0063, m0069) shows repeated discovery that default-PSM and preprocessed+PSM-6 disagree, but passes never combined. Reverse-iteration implicitly trusts the last line, yet 074 needs earlier line, 077 needs later line. Summary-section cutoff (`GST SUMMARY`, `TAX CODE`) may truncate 078's `Grand Total` region.
- proposed_change: multi-pass-ocr-strategy must require pass combination; receipt-total-selection must distinguish "last line in tier" from "last line BEFORE summary" and guard against summary cutoff above a priority-1 `Grand Total`.

### [w0021] within-tier specificity ranking; cross-variant voting without specificity check
- signal: failure
- pattern: amount-candidate-selection-within-total-tier
- anchor: receipt-total-selection
- gap: Formal proposal: within priority-4 `TOTAL`, sub-rank by specificity — `\bTOTAL\s*:` / `\bTOTAL\s+RM` > `\bTOTAL\b.*(Incl|Inclusive|Excl|Excluding|Amt Rounded|After Adj|Sales)` > bare `\bTOTAL\b`. Switch from sequential dual-OCR to candidate-level dual-OCR voting over `(tier, specificity, value)`. Also notes `NUM_RE` tightening to exactly 2 decimals caused 078 regression — relax to `\d+\.\d{1,2}` but prefer exact-2-decimal in tiebreak.
- proposed_change: receipt-total-selection reference must codify the within-tier specificity ladder as explicit regex priority classes; multi-pass-ocr-strategy must describe `\d+\.\d{1,2}` with 2-decimal preference as the number regex.

### [w0022] tail-of-run budget exhaustion with known-but-unshipped fixes
- signal: failure
- pattern: iteration-budget-and-pipeline-order
- anchor: pipeline-order-and-budget
- gap: Exchanges e0030–e0036 all at 91k–96k prompt tokens dominated by narrow `think` + terminal checks on single receipts. Agent had enumerated all needed fixes but never validated end-to-end. 034 was not revisited in this window at all.
- proposed_change: pipeline-order-and-budget anchor must mandate a per-edit full-corpus re-run before xlsx save, and discourage per-receipt debug iterations beyond a bounded count.

### [w0023] no digit-level consensus; no rounding-aware tie-break; fallback too narrow for dashed separators
- signal: failure
- pattern: amount-candidate-selection-within-total-tier
- anchor: receipt-total-selection
- gap: Two concrete failures of the voting design: (a) 074 — when two variants agree on a wrong digit (`702.00`) and one variant has `102.00`, majority-of-variants wins the wrong answer; needs per-digit voting or anchor check against Subtotal/Rounded Total; (b) 077 — tier-4 ties resolved by "last wins" only if OCR captured the line; PSM 11 (sparse) or layout-preserving `image_to_data` captures isolated large text better.
- proposed_change: receipt-total-selection must describe per-digit verification by cross-check against Subtotal/Payment/Rounded lines; multi-pass-ocr-strategy should include PSM 11 as an additional variant for large/isolated bold text.

### [w0024] 074 1→7, 077 last-TOTAL, 078 early-exit at tier 1, 034 label anchoring
- signal: failure
- pattern: exclusion-and-fallback-keyword-gaps
- anchor: receipt-exclusion-and-fallback
- gap: Specific defect: "when highest-priority tier yields a candidate line but no parseable number, and the next-line fallback is excluded, the code must still fall through to lower tiers." 078 shows tier 1 `GRAND TOTAL` finds the keyword but excludes the next line (`CHANGE`), then returns None rather than cascading to tier 3 `TOTAL`. Also 034 date must prefer `Date:`-anchored match over free-standing dates (receipt ID `CS00084670` / handwritten `A03041`).
- proposed_change: receipt-exclusion-and-fallback reference must document "cascade to next tier on failed-fallback" as a required rule; receipt-date-extraction must require label anchoring.

### [w0025] 064 Visa-RM fallback leak fixed; 078 dashed separator still breaks fallback; DD/MM lock-in needed for 034
- signal: failure
- pattern: exclusion-and-fallback-keyword-gaps
- anchor: receipt-exclusion-and-fallback
- gap: Pre-m0147 code triggered next-line rescue even when keyword line had digits ("Total RM = B81?" bled into "Visa RM =688.17"). Post-m0147 fix gates fallback on zero-digit keyword line. Remaining gap: fallback `break`s on first non-numeric non-excluded next line (killed by dashed divider on 078). 034 needs deterministic DD/MM preference for Malaysian receipts.
- proposed_change: receipt-exclusion-and-fallback must specify that fallback skips blank/punctuation-only lines rather than breaking; receipt-date-extraction must default to DD/MM/YYYY for Malaysian corpus.

### [w0026] mid-refactor voting change at termination; 077/078 pre-fix execution shipped
- signal: failure
- pattern: iteration-budget-and-pipeline-order
- anchor: pipeline-order-and-budget
- gap: m0156/m0159 rewrote voting to collect all tier-matched candidates from all variants and pick the mode within the best tier — correct direction for 074 (102.00 appears 4× in-variant vs 702.00 1×). m0162 added `CASH\s+(TENDERED|RECEIVED|PAYMENT)` exclusion — correct for 078. Neither was executed end-to-end; shipped xlsx reflects pre-fix state.
- proposed_change: pipeline-order-and-budget anchor must require a verification rerun after any `pick_best_total` edit; receipt-exclusion-and-fallback keeps the extended CASH-family exclusion.

### [w0027] keyword matcher too strict; number regex ignores separator noise; multi-variant voting without sanity check
- signal: failure
- pattern: exclusion-and-fallback-keyword-gaps
- anchor: receipt-exclusion-and-fallback
- gap: `\bGRAND\s+TOTAL\b`, `\bTOTAL\s+AMOUNT\b` fail when OCR drops a space (`GrandTotal`) or a character (`GrandTota.`); needs 0-or-1 non-alphanumeric between tokens and common OCR confusions (`0`↔`O`, `1`↔`l`/`I`). `NUM_RE` misses `92:80`, `92 80`, `92.8O`. Majority voting can entrench a bad digit on 074.
- proposed_change: receipt-exclusion-and-fallback must document fuzzy keyword matching and tolerant number parsing; receipt-total-selection must document consistency check against Subtotal+GST.

### [w0028] in-flight exclusion patch for `DESCRIPTION` + `(QTY|PRICE)\s+AMOUNT`; still insufficient
- signal: failure
- pattern: exclusion-and-fallback-keyword-gaps
- anchor: receipt-exclusion-and-fallback
- gap: m0059/m0061 patch correctly suppresses the 078 column-header fallback but leaves the receipt returning null because no tier-matched line yields a valid `\d+\.\d{2}` once `92.80`→`92:80` corruption persists. Patch is necessary but not sufficient; must be paired with `:`/`;`→`.` normalisation on keyword-matched lines.
- proposed_change: receipt-exclusion-and-fallback must bundle the header-exclusion rule with the colon-normalisation rule as a single mechanism.

### [w0029] near-miss termination with PSM-4 upscale winner identified
- signal: failure
- pattern: single-pass-ocr-default
- anchor: multi-pass-ocr-strategy
- gap: m0189 diagnostic showed `upscale 3x gray + --psm 4` produces `Grand Total a 92.80` for 078; m0192 captured the winning configuration; run hit max_iterations before wiring it in. Agent's extractor ran default + PSM 6, missing the aggressive upscale that recovers the sub-decimal glyph.
- proposed_change: multi-pass-ocr-strategy anchor must include 3× LANCZOS + autocontrast + PSM 4 as a required variant alongside default and PSM 6.

### [w0030] half-applied s0045 edit; selector flattens all candidates
- signal: failure
- pattern: iteration-budget-and-pipeline-order
- anchor: pipeline-order-and-budget
- gap: Last action added 4th OCR variant specifically because it empirically recovers `Grand Total a 92.80`; `extract.py` was never re-run. Delivered xlsx = s0043 state. Also notes selector (tier → majority count → tiebreak) does not score candidates per-keyword-tier.
- proposed_change: pipeline-order-and-budget anchor must require the next patcher to resume the half-applied variant addition AND switch selection to per-tier scoring.

### [w0031] OCR digit misreads + Thai-script 078 interference hypothesis
- signal: failure
- pattern: single-pass-ocr-default
- anchor: multi-pass-ocr-strategy
- gap: 078 has Thai glyphs in adjacent lines possibly degrading Tesseract layout detection; `n_skill_invocations=0` and agent rolled bespoke pipeline without `lang='eng+tha'` or aggressive preprocessing. Proposes variant voting + confidence filtering via `image_to_data`.
- proposed_change: multi-pass-ocr-strategy may note language configuration (`lang='eng'` baseline, consider `+tha`/`+msa` when Asian glyphs are present) and `image_to_data` confidence filtering for digit tokens.

### [w0032] regex must absorb OCR noise around numbers; 102 appears 4× on 074
- signal: failure
- pattern: amount-candidate-selection-within-total-tier
- anchor: receipt-total-selection
- gap: Reinforces: 074's 102.00 vs 702.00 is resolved by 3× within-text frequency; 077's final bold TOTAL may need PSM 6 preprocessing to surface; 078's `GrandTota.` + `92:80` needs looser keyword + looser number parser on keyword-matched lines. Also flags iteration budget spent dumping OCR for all 22 images rather than one-pass then iterate.
- proposed_change: receipt-total-selection must mandate within-text frequency scoring; multi-pass-ocr-strategy must require preprocess+PSM 6 as primary.

### [w0033] step-8 extractor + first run; 074 OCR dump shows "Tolal"/"inel"/"GBT" noise
- signal: failure
- pattern: single-pass-ocr-default
- anchor: multi-pass-ocr-strategy
- gap: OCR dump shows Tesseract routinely swaps letters (`Tolal`, `Tolal`, `inel`, `GBT`, `Toial`, `yo2.00`) under default PSM. `\bTOTAL\b` does not match "Tolal"; `GBT` escapes `(GST|TAX|SST)` exclusion; `yo2.00` fails `NUM_RE`. Also notes 078 shipped as `""` is a later regression — step 8 originally produced 92.80.
- proposed_change: multi-pass-ocr-strategy must require preprocessed PSM 6 to recover from character-swap noise; receipt-exclusion-and-fallback must widen keyword matcher to tolerate single-char substitutions (`Tolal`→`Total`, `GBT`→`GST`).

### [w0034] PSM-6 switch; regressions on 052 and 077; delivered xlsx = default-PSM path
- signal: failure
- pattern: single-pass-ocr-default
- anchor: multi-pass-ocr-strategy
- gap: Single pass insufficient — PSM 6 fixes 034, 074, 077 but regresses 052 (10.00→None) and may regress others. Step 17 vs step 18 outputs diverge; the shipped xlsx corresponds to default-PSM path not the PSM-6 branch that was iterated on later. Needs multi-pass UNION + voting, not swap.
- proposed_change: multi-pass-ocr-strategy must describe union-of-passes + consensus voting explicitly, not sequential fallback.

### [w0035] dual-pass "default first, fallback preprocessed" documented as wrong; EXCLUDING added
- signal: failure
- pattern: single-pass-ocr-default
- anchor: multi-pass-ocr-strategy
- gap: m0078 shows "default first" short-circuit: 034 default returns `09/08/2018` and PSM-6's `09/03/2018` is never consulted; same for 077. m0102 adds `EXCLUDING` keyword — correct and must be preserved. m0113 proves 2× upscale PSM 6 recovers 074 and 077 but harms 064/010/090 — hence voting rather than swap.
- proposed_change: multi-pass-ocr-strategy must explicitly forbid sequential fallback across variants; must describe collecting all candidates and using tier → consensus → source priority.

### [w0036] 3-variant voting shipped; 074 majority-votes wrong digit; 077 regressed 23.25→23.26; 078 100.00→null
- signal: failure
- pattern: amount-candidate-selection-within-total-tier
- anchor: receipt-total-selection
- gap: Voting by (min tier_idx, then count, then order) ties all three variants in the same tier for 074, so 2 (702.00) beats 1 (102.00). Step 36 "return-all-candidates" refactor adds extra 23.26 occurrences from every variant, so naive frequency reports 23.26 ≥ 23.25 on 077. CASH/VISA/MASTERCARD/PAYMENT must be added to exclusions to prevent 078 Cash-Received leak.
- proposed_change: receipt-total-selection must mandate "last match wins per variant" within-variant selection first; receipt-exclusion-and-fallback must extend exclusion list with payment-instrument family.

### [w0037] final-state termination; `GRAND\s*TOTA[L.]?` loosening and `(Inclusive of GST)` exclusion identified
- signal: failure
- pattern: iteration-budget-and-pipeline-order
- anchor: pipeline-order-and-budget
- gap: s0045 added 3× upscale PSM 4 variant but never re-ran `extract.py`. Delivered xlsx = s0043 state. Patcher-ready low-risk fixes identified: (1) loosen GRAND TOTAL to `\bGRAND\s*TOTA[L.]?\b`; (2) exclude `TOTAL\s*\(\s*INCL` from TOTAL tier so 077 resolves to 23.25; (3) keep 3× upscale PSM 4 variant; (4) revise `pick_best_total` so per-variant tier winners vote (not flattened all-candidate count); (5) date-specific second-pass OCR for 034 cropped near `Date:`.
- proposed_change: pipeline-order-and-budget anchor must require full-corpus re-run before xlsx save; receipt-exclusion-and-fallback must add `TOTAL (Inclusive/Excluding GST)` sub-exclusion when a bare later `TOTAL:` exists; receipt-total-selection must mandate per-variant tier-winner voting rather than flat candidate counting.

## WORKFLOW-THEMES

- (none this iteration)
