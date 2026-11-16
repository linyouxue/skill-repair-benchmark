# Diagnosis Report: skillopt / exoplanet-detection-period

## 1. 诊断修复前轨迹
- baseline_result: `/Users/elsie/Desktop/SkillOpt-eva/experiments/gpt52-4task-unhealthy-rerun-evidencefix-v3-20261018/baseline/original-skill/exoplanet-detection-period/benchmark_result.json`
- baseline comparable/pass: `True` / `False`
- baseline error category: `None`
- rollout_dir: `/Users/elsie/Desktop/SkillOpt-eva/experiments/gpt52-4task-unhealthy-rerun-evidencefix-v3-20261018/jobs/baseline-original-skill/exoplanet-detection-period-original-skill-r001`

## 2. 诊断定位的 skill，以及如何修复
- overall diagnosis: The agent detrended/cleaned the light curve and ran a transit search, but selected a strong short-period alias/harmonic (~1.398 d) instead of the true orbital period (~5.357 d). The main gap is insufficient candidate validation after BLS/TLS: not inspecting multiple top peaks, not checking integer harmonics/subharmonics, and not confirming the signal via phase-folded transit morphology (including odd/even checks and duration sanity checks). Residual stellar variability and/or inappropriate detrending/duration settings likely biased the periodogram toward the alias, and the overall workflow guidance did not enforce an iterative detrend→search→mask→re-detrend→re-search loop common in activity-dominated TESS light curves.
- diff: `/Users/elsie/Desktop/SkillOpt-eva/experiments/gpt52-4task-unhealthy-rerun-evidencefix-v3-20261018/methods/skillopt/exoplanet-detection-period/diff.patch`
- `box-least-squares/SKILL.md` diagnosed=True confidence=0.9
  - diagnosis: BLS usage latched onto the maximum-power peak without robust alias/harmonic rejection. The skill underemphasizes that the top BLS peak is often a harmonic/subharmonic (or cadence/window alias), especially with residual stellar variability, and lacks a concrete validation checklist (folded light curve, odd/even, duration realism, testing P, 2P, 3P and P/2, P/3). It also doesn’t clearly constrain realistic transit-duration grids, which can inflate spurious power if durations are too long.
  - repair: Add an explicit 'Validation & common failure modes' section: (1) always review top N peaks, not just max; (2) systematically test harmonics/subharmonics by evaluating P, 2P, 3P and P/2, P/3 with the same duration prior; (3) require phase-fold + binned visualization and model overlay to confirm a coherent box-shaped dip; (4) perform odd/even transit depth comparison and secondary-eclipse check; (5) add duration sanity guidance for TESS (hours-scale typical) and recommend tying duration bounds to period and stellar density (avoid overly long durations unless justified); (6) mention alias sources (data gaps, cadence, detrending leakage) and recommend SNR/FAP/bootstrapping where available; include an example where the highest BLS peak is not the true period.
  - change_summary: ['insert_after:applied_insert_after', 'insert_after:applied_insert_after', 'replace:applied_replace', 'insert_after:applied_insert_after']
  - diff_stats: {'added_lines': 81, 'removed_lines': 9}
- `exoplanet-workflows/SKILL.md` diagnosed=True confidence=0.85
  - diagnosis: Workflow guidance is too generic for activity-dominated transit searches and did not enforce iterative validation steps, allowing the agent to accept an alias period. It lacks a concrete troubleshooting path for when preprocessing leaves rotational power that can dominate BLS/TLS and produce misleading peaks.
  - repair: Add a step-by-step workflow for 'strong stellar variability' cases: (1) estimate rotation timescale (optionally via Lomb-Scargle) to inform detrend settings; (2) detrend with transit-preserving methods and document window heuristics; (3) run BLS/TLS; (4) validate candidates via folded morphology + harmonics/aliases + odd/even + transit count consistency; (5) iterate: mask detected transits, re-detrend, rerun search; (6) final refinement of period/epoch using folded fit. Explicitly warn: strongest peak may be non-physical; always check harmonics before reporting.
  - change_summary: ['insert_after:applied_insert_after', 'insert_after:applied_insert_after', 'replace:applied_replace', 'insert_after:applied_insert_after']
  - diff_stats: {'added_lines': 50, 'removed_lines': 1}
- `light-curve-preprocessing/SKILL.md` diagnosed=True confidence=0.7
  - diagnosis: Preprocessing likely left residual rotational variability or distorted transit signals (over/under-flattening), which can bias period searches toward short aliases. The skill lacks enough concrete guidance on choosing detrending windows relative to transit duration and on avoiding treating in-transit points as outliers.
  - repair: Expand with transit-preserving detrending guidance: choose detrend/flatten windows much longer than expected transit duration (e.g., 5–20×), avoid overfitting that removes dips; handle quality flags before clipping; do sigma-clipping on detrended residuals rather than raw flux; explicitly caution against removing in-transit points as outliers; recommend segment-wise normalization for gaps; require before/after plots and an iterative 'detrend → search → mask transits → re-detrend' pattern to reduce leakage of variability into the periodogram.
  - change_summary: ['insert_after:applied_insert_after', 'replace:applied_replace', 'insert_after:applied_insert_after', 'insert_after:applied_insert_after']
  - diff_stats: {'added_lines': 63, 'removed_lines': 18}
- `lomb-scargle-periodogram/SKILL.md` diagnosed=False confidence=n/a
  - diagnosis: 
  - repair: 
  - change_summary: []
  - diff_stats: {'added_lines': 0, 'removed_lines': 0}
- `transit-least-squares/SKILL.md` diagnosed=True confidence=0.6
  - diagnosis: TLS is often more robust for shallow transit-shaped signals, but guidance may not sufficiently stress using TLS for validation/cross-checking and using TLS diagnostics to reject aliases/harmonics when BLS and TLS disagree.
  - repair: Strengthen 'when to use TLS' and 'how to validate' sections: recommend TLS as primary or as cross-validation after BLS in transit searches; add instructions to constrain period/duration ranges, interpret TLS metrics (e.g., SNR/SDE, transit count, duration consistency), and explicitly check harmonics/subharmonics of the TLS best period. Provide a short recipe for resolving BLS vs TLS discrepancies by folding at P and harmonic alternatives and selecting the period with consistent, repeated transit morphology.
  - change_summary: ['insert_after:applied_insert_after', 'replace:applied_replace', 'replace:applied_replace', 'replace:applied_replace']
  - diff_stats: {'added_lines': 52, 'removed_lines': 7}

## 3. 是否修复成功及原因
- comparable/pass: `True` / `True`
- skill_exposure_verified: `True`
- outcome_category: `repair_success`
- analysis: The method-skill run is comparable and passed the task verifier.

## 4. 修复时间及成本开销
- optimizer total tokens: `6395`
- optimizer duration sec: `13.587`
- baseline evaluation: `{'wall_time_sec': 1447.2, 'cost_usd': 0.4048408, 'provider_requests': 18, 'agent_iterations': 18, 'termination_reason': 'end_turn'}`
- method evaluation: `{'wall_time_sec': 321.1, 'cost_usd': 0.7061355, 'provider_requests': 12, 'agent_iterations': 12, 'termination_reason': 'end_turn'}`
- known_total_cost_usd: `1.1109763`
