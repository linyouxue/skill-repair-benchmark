# Diagnosis Report: skillopt / dynamic-object-aware-egomotion

## 1. 诊断修复前轨迹
- baseline_result: `/Users/elsie/Desktop/SkillOpt-eva/experiments/gpt52-31-skillopt-evidencefix-v2-20261017/baseline/original-skill/dynamic-object-aware-egomotion/benchmark_result.json`
- baseline comparable/pass: `True` / `False`
- baseline error category: `None`
- rollout_dir: `/Users/elsie/Desktop/SkillOpt-eva/experiments/gpt52-31-skillopt-evidencefix-v2-20261017/jobs/baseline-original-skill/dynamic-object-aware-egomotion-original-skill-v11x-20260903-r001`

## 2. 诊断定位的 skill，以及如何修复
- overall diagnosis: The dominant failure modes are unstable dynamic-object masks and inconsistent fps-based sampling/index alignment. Multiple runs narrowly failed mask IoU while showing extremely poor boundary IoU and high temporal flicker, indicating the current masking workflow is too fragile under imperfect egomotion compensation, illumination variation, and sparse 5fps sampling. A later run additionally produced 19 masks instead of the expected 18, pointing to ambiguity in how fps-derived sample indices and final-frame inclusion are handled. Egomotion labels themselves were mostly correct, so transform classification is not the main bottleneck; the highest-value repairs are strengthening mask robustness, clarifying deterministic sampling/index policy, and improving validation to catch off-by-one sampling and unstable masks before submission.
- diff: `/Users/elsie/Desktop/SkillOpt-eva/experiments/gpt52-31-skillopt-evidencefix-v2-20261017/methods/skillopt/dynamic-object-aware-egomotion/diff.patch`
- `dyn-object-masks/SKILL.md` diagnosed=True confidence=0.92
  - diagnosis: The current mask-generation recipe (single-frame aligned differencing plus simple morphology) is not robust enough for this benchmark. Observed metrics showed low mean IoU, extremely low boundary IoU, and high flicker, consistent with residual alignment errors, illumination sensitivity, unstable thresholds, and insufficient temporal consistency. Guidance also under-specifies transform quality checks, border suppression, parameter scaling for 5fps sampling, and techniques for reducing false positives from parallax or warp residuals.
  - repair: Expand the workflow with stronger alignment-aware masking guidance: validate affine/homography quality using RANSAC inlier checks and fallback behavior; erode warped valid regions to suppress border artifacts; optionally normalize illumination (blur/CLAHE/normalized differencing) before differencing; define thresholds using robust MAD plus percentile/floor constraints tied to fps and resolution; add explicit temporal stabilization such as EMA or 2-of-3 majority voting to reduce flicker; strengthen morphology/component filtering with area scaling and border-touch rejection; and add self-check heuristics for mask fill ratio, flicker, and boundary quality. Include concrete default parameter ranges for 720p/5fps pipelines and debugging advice for tuning IoU versus false positives.
  - change_summary: ['insert_after:applied_insert_after', 'replace:applied_replace', 'replace:applied_replace']
  - diff_stats: {'added_lines': 0, 'removed_lines': 0}
- `egomotion-estimation/SKILL.md` diagnosed=False confidence=n/a
  - diagnosis: 
  - repair: 
  - change_summary: []
  - diff_stats: {'added_lines': 0, 'removed_lines': 0}
- `output-validation/SKILL.md` diagnosed=True confidence=0.68
  - diagnosis: Existing validation focuses on structural correctness but would not catch the observed off-by-one sampling mismatch or severe mask instability. The 19-vs-18 frame-count error and high-flicker masks likely passed local checks because there are no explicit validations for fps-derived sample counts, temporal consistency, or noisy mask behavior.
  - repair: Strengthen validation guidance with explicit cross-checks between computed sample_ids, JSON interval coverage, and NPZ frame count so fps-based off-by-one errors are detected before submission. Add lightweight non-GT diagnostics for mask quality, including foreground coverage ratio, adjacent-frame XOR flicker, border activation, and excessive tiny connected components. Include sanity thresholds and troubleshooting guidance when masks are unstable or overly dense.
  - change_summary: ['insert_after:applied_insert_after', 'insert_after:applied_insert_after', 'insert_after:applied_insert_after', 'append:applied_append']
  - diff_stats: {'added_lines': 0, 'removed_lines': 0}
- `sampling-and-indexing/SKILL.md` diagnosed=True confidence=0.88
  - diagnosis: The sampling policy is ambiguous for fps-based extraction and likely caused the off-by-one failure where 19 masks were generated instead of the expected 18. The current guidance suggests optionally appending the last frame, which conflicts with evaluator expectations when using fixed-rate sampling. The skill also lacks a deterministic mapping from timestamps to frame indices and does not clearly constrain downstream outputs to exactly match sampled-frame count.
  - repair: Clarify fps-based sampling as a deterministic time-grid process: generate sample timestamps at the target rate (e.g. 5fps), map them to source frame indices using a documented rounding/floor rule, and only include the final frame if it lies on the sampling grid rather than appending it unconditionally. Add explicit examples showing exact sample counts and indices for common source fps/frame-count combinations. Emphasize that JSON intervals, NPZ masks, and all downstream artifacts must align exactly with the computed sample_ids and contain no extra frames.
  - change_summary: ['replace:applied_replace', 'replace:applied_replace', 'insert_after:applied_insert_after', 'insert_after:applied_insert_after']
  - diff_stats: {'added_lines': 0, 'removed_lines': 0}

## 3. 是否修复成功及原因
- comparable/pass: `True` / `False`
- skill_exposure_verified: `True`
- outcome_category: `located_but_not_fixed`
- analysis: A skill was localized and rewritten, but the comparable method-skill run still failed; likely causes are insufficient repair content or downstream model execution limits.

## 4. 修复时间及成本开销
- optimizer total tokens: `12345`
- optimizer duration sec: `12.886`
- baseline evaluation: `{'wall_time_sec': 2177.8, 'cost_usd': 0.13558265, 'provider_requests': 3, 'agent_iterations': 3, 'termination_reason': 'end_turn'}`
- method evaluation: `{'wall_time_sec': 2177.8, 'cost_usd': 0.13558265, 'provider_requests': 3, 'agent_iterations': 3, 'termination_reason': 'end_turn'}`
- known_total_cost_usd: `0.2711653`
