# Diagnosis Report: skillopt / pddl-airport-planning

## 1. 诊断修复前轨迹
- baseline_result: `/Users/elsie/Desktop/SkillOpt-eva/experiments/gpt52-31-skillopt-evidencefix-v2-20261017/baseline/original-skill/pddl-airport-planning/benchmark_result.json`
- baseline comparable/pass: `False` / `False`
- baseline error category: `None`
- rollout_dir: `/Users/elsie/Desktop/SkillOpt-eva/experiments/gpt52-31-skillopt-evidencefix-v2-20261017/jobs/baseline-original-skill/pddl-airport-planning-original-skill-v11x-20260908-guarddiag-infra-r003`

## 2. 诊断定位的 skill，以及如何修复
- overall diagnosis: Plans are being saved in a non–PDDL-compliant text format (function-call style like action(arg1,arg2) or action(args...) as a single token) instead of the canonical parenthesized, whitespace-separated PDDL plan syntax required by unified_planning.io.PDDLReader.parse_plan (e.g., "(action-name arg1 arg2 ...)"). This output-format mismatch causes parse failures before any semantic validation, indicating pddl-skills guidance is underspecified/ambiguous about plan serialization requirements and lacks a recommended re-parse validation step.
- diff: `/Users/elsie/Desktop/SkillOpt-eva/experiments/gpt52-31-skillopt-evidencefix-v2-20261017/methods/skillopt/pddl-airport-planning/diff.patch`
- `pddl-skills/SKILL.md` diagnosed=True confidence=0.86
  - diagnosis: The skill’s plan saving/output requirements are not explicit enough about the exact textual grammar that unified_planning’s PDDLReader.parse_plan (and downstream verifiers) accepts. This likely led to emitting planner/operator strings in function-call syntax (e.g., name(args...)) instead of one-action-per-line s-expressions '(name arg1 ... argN)', causing UPException during plan parsing.
  - repair: Update SKILL.md to add/strengthen a dedicated 'Plan Saving / Serialization' section that (1) explicitly requires sequential plans to be written one action per line in canonical PDDL plan syntax: '(action-name param1 ... paramN)' with whitespace-separated args inside parentheses; (2) explicitly forbids 'action(param,...)' or 'action(params...)' function-call formatting; (3) notes any casing/normalization expectations (e.g., lowercase) to match parser behavior; (4) optionally documents the temporal/timed line format only if relevant. Include a canonical formatter snippet that converts a unified_planning SequentialPlan into these lines, and require a post-save syntactic check by re-parsing the saved plan with unified_planning.io.PDDLReader.parse_plan before returning/accepting the output.
  - change_summary: ['insert_after:applied_insert_after', 'replace:applied_replace']
  - diff_stats: {'added_lines': 43, 'removed_lines': 2}

## 3. 是否修复成功及原因
- comparable/pass: `True` / `True`
- skill_exposure_verified: `True`
- outcome_category: `repair_success`
- analysis: The method-skill run is comparable and passed the task verifier.

## 4. 修复时间及成本开销
- optimizer total tokens: `2154`
- optimizer duration sec: `6.12`
- baseline evaluation: `{'wall_time_sec': 374.7, 'cost_usd': 0.18712995, 'provider_requests': 21, 'agent_iterations': 21, 'termination_reason': 'end_turn'}`
- method evaluation: `{'wall_time_sec': 466.3, 'cost_usd': 0.19132925, 'provider_requests': 6, 'agent_iterations': 6, 'termination_reason': 'end_turn'}`
- known_total_cost_usd: `0.3784592`
