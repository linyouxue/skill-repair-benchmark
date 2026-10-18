# Diagnosis Report: skillopt / seismic-phase-picking

## 1. 诊断修复前轨迹
- baseline_result: `/Users/elsie/Desktop/SkillOpt-eva/experiments/gpt52-31-skillopt-evidencefix-v2-20261017/baseline/original-skill/seismic-phase-picking/benchmark_result.json`
- baseline comparable/pass: `True` / `False`
- baseline error category: `None`
- rollout_dir: `/Users/elsie/Desktop/SkillOpt-eva/experiments/gpt52-31-skillopt-evidencefix-v2-20261017/jobs/baseline-original-skill/seismic-phase-picking-original-skill-v11x-20260903-r001-recovery001`

## 2. 诊断定位的 skill，以及如何修复
- overall diagnosis: The dominant failure mode was weak operational guidance for seismic phase picking with SeisBench rather than data-access or infrastructure issues. Across runs, the agent used PhaseNet but either misused evolving SeisBench classify outputs (`classify_output.picks` vs older interfaces) or applied naive/default pick extraction strategies that produced poor precision-recall balance under strict ±0.1 s F1 evaluation. The missing guidance consistently involved end-to-end phase-picking workflows: preparing ObsPy streams from NPZ arrays, preprocessing and channel handling, extracting picks from probability traces, threshold tuning, multi-pick suppression, and enforcing physical phase constraints such as S-after-P. Method-selection guidance was also too high-level to support benchmark-oriented tuning and model choice.
- diff: `/Users/elsie/Desktop/SkillOpt-eva/experiments/gpt52-31-skillopt-evidencefix-v2-20261017/methods/skillopt/seismic-phase-picking/diff.patch`
- `obspy-data-api/SKILL.md` diagnosed=False confidence=n/a
  - diagnosis: 
  - repair: 
  - change_summary: []
  - diff_stats: {'added_lines': 0, 'removed_lines': 0}
- `obspy-datacenter-client/SKILL.md` diagnosed=False confidence=n/a
  - diagnosis: 
  - repair: 
  - change_summary: []
  - diff_stats: {'added_lines': 0, 'removed_lines': 0}
- `seisbench-model-api/SKILL.md` diagnosed=True confidence=0.94
  - diagnosis: The skill is the primary gap across all samples. It documents annotate/classify conceptually but lacks current API details and task-oriented workflows for high-accuracy phase picking. Evidence included runtime/API confusion around outdated classify outputs, naive global-max pick selection, reliance on default thresholds, and insufficient guidance on converting NPZ waveform arrays into correctly configured ObsPy Streams. The skill does not adequately cover probability-trace postprocessing, threshold calibration, multi-pick handling, temporal constraints, or practical preprocessing needed to maximize F1.
  - repair: Expand the skill into a complete seismic phase-picking workflow guide centered on PhaseNet/EQTransformer. Document current SeisBench inference APIs explicitly, including `out = model.classify(stream)` and `out.picks`, pick object fields, and differences between `annotate()` probability traces and `classify()` outputs. Add robust examples for converting raw NumPy/NPZ arrays into ObsPy Streams with correct `sampling_rate`, `delta`, `starttime`, and channel metadata. Include preprocessing defaults (demean/detrend, tapering, optional bandpass filtering, normalization, resampling, channel ordering) and detailed pick extraction recipes using probability peaks, threshold tuning, non-maximum suppression, minimum separation, top-k candidate handling, abstention logic, and enforcing S-after-P constraints. Add practical parameter guidance for 100 Hz data and strict ±0.1 s evaluation tolerances.
  - change_summary: ['insert_after:applied_insert_after', 'insert_after:applied_insert_after', 'insert_after:applied_insert_after', 'append:applied_append']
  - diff_stats: {'added_lines': 0, 'removed_lines': 0}
- `seismic-picker-selection/SKILL.md` diagnosed=True confidence=0.82
  - diagnosis: The selection guide is too high-level for benchmark-style automatic phase-picking tasks. It explains broad tradeoffs between STA/LTA, template matching, and deep learning, but does not operationalize how to maximize F1 with pretrained ML pickers. The agent lacked actionable guidance on choosing between PhaseNet and EQTransformer, calibrating thresholds, handling duplicate peaks, using abstention, or combining seismic constraints with ML outputs.
  - repair: Add an operational playbook for benchmark-oriented phase picking. Include concrete recommendations for pretrained deep-learning pickers available through SeisBench, criteria for selecting models under different noise/event conditions, and practical tuning strategies for balancing recall and precision. Cover probability-threshold calibration, peak finding, duplicate suppression, top-k candidate policies, abstention for low-confidence traces, and physical constraints such as P-before-S and plausible P-S separation windows. Include compact recommended parameter ranges for 100 Hz local-event data and explain when emitting multiple candidate picks helps or hurts F1.
  - change_summary: ['insert_after:applied_insert_after', 'insert_after:applied_insert_after', 'insert_after:applied_insert_after', 'insert_after:applied_insert_after']
  - diff_stats: {'added_lines': 0, 'removed_lines': 0}

## 3. 是否修复成功及原因
- comparable/pass: `True` / `False`
- skill_exposure_verified: `True`
- outcome_category: `located_but_not_fixed`
- analysis: A skill was localized and rewritten, but the comparable method-skill run still failed; likely causes are insufficient repair content or downstream model execution limits.

## 4. 修复时间及成本开销
- optimizer total tokens: `10654`
- optimizer duration sec: `11.015`
- baseline evaluation: `{'wall_time_sec': 1791.8, 'cost_usd': 0.54833975, 'provider_requests': 32, 'agent_iterations': 32, 'termination_reason': 'end_turn'}`
- method evaluation: `{'wall_time_sec': 1791.8, 'cost_usd': 0.54833975, 'provider_requests': 32, 'agent_iterations': 32, 'termination_reason': 'end_turn'}`
- known_total_cost_usd: `1.0966795`
