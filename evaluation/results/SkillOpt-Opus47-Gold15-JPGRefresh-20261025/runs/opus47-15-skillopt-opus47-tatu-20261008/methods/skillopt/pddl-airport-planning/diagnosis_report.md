# Diagnosis Report: skillopt / pddl-airport-planning

## 1. 诊断修复前轨迹
- baseline_result: `/Users/elsie/Desktop/SkillOpt-eva/experiments/opus47-15-skillopt-opus47-tatu-20261008/baseline/original-skill/pddl-airport-planning/benchmark_result.json`
- baseline comparable/pass: `True` / `False`
- baseline error category: `None`
- rollout_dir: `/Users/elsie/Desktop/SkillOpt-eva/experiments/opus47-15-skillopt-opus47-tatu-20261008/jobs/baseline-original-skill/pddl-airport-planning-opus47-original-skill-r001`

## 2. 诊断定位的 skill，以及如何修复
- overall diagnosis: Across all three samples, the baseline agent correctly generated plans but wrote them in the task.md example format `action_name(arg1, arg2, ...)` with commas and function-call-style parentheses. The verifier uses `unified_planning.io.PDDLReader.parse_plan`, which requires standard Lisp-style PDDL plan syntax: `(action-name arg1 arg2 ... argN)` per line — parentheses wrapping the whole action, space-separated arguments, no commas. The pddl-skills SKILL.md's save-plan section does not explicitly specify this required format, so the agent followed the misleading task.md example and produced output that fails parsing. The earlier patch attempt only deleted content without adding the needed format specification; this round must ADD explicit format guidance with a concrete code snippet.
- diff: `/Users/elsie/Desktop/SkillOpt-eva/experiments/opus47-15-skillopt-opus47-tatu-20261008/methods/skillopt/pddl-airport-planning/diff.patch`
- `pddl-skills/SKILL.md` diagnosed=True confidence=high
  - diagnosis: The skill's plan-saving guidance does not specify the exact textual output format required by `unified_planning.io.PDDLReader.parse_plan`. The verifier requires standard PDDL plan syntax `(action-name arg1 arg2 ... argN)` per line, but the task.md example shows a misleading `action_name(arg1, arg2)` comma-separated function-call format. The baseline followed the task.md example and failed parsing with `UPException: Cannot interpret ...`. Prior patch attempts that only deleted text without adding explicit new format rules did not help; this round must ADD a clear 'Plan Output Format' section with a concrete code snippet.
  - repair: Rewrite SKILL.md to ADD (not just delete) a new prominent 'Plan Output Format' section near the save-plan documentation. The section must state: (1) Saved plans MUST be parseable by `unified_planning.io.PDDLReader.parse_plan`. (2) Each action occupies one line formatted as `(action-name arg1 arg2 ... argN)` — opening paren, action name, space-separated arguments, closing paren. NO commas. NO function-call style like `action(a, b)`. (3) Include a concrete worked example:
```
(move seg_rw_0_400 seg_rww_0_50 south south medium airplane_cfbeg)
(park seg_pp_0_60 south airplane_cfbeg)
```
(4) Include a recommended code snippet:
```python
with open(output_path, 'w') as f:
    for a in plan.actions:
        params = ' '.join(str(p) for p in a.actual_parameters)
        f.write(f'({a.action.name} {params})\n')
```
(5) Explicitly warn: 'If a task description shows an example like `action(a, b, c)` with commas, DO NOT use that format — it will fail `PDDLReader.parse_plan`. Always use the parenthesized space-separated Lisp-style form.' (6) Note that PDDLReader lowercases lines, so action and object names should match the domain/problem (lowercase is safe). (7) Ensure the file ends with a trailing newline.
  - change_summary: ['replace:applied_replace']
  - diff_stats: {'added_lines': 33, 'removed_lines': 1}

## 3. 是否修复成功及原因
- comparable/pass: `True` / `True`
- skill_exposure_verified: `True`
- outcome_category: `repair_success`
- analysis: The method-skill run is comparable and passed the task verifier.

## 4. 修复时间及成本开销
- optimizer total tokens: `5609`
- optimizer duration sec: `11.614`
- baseline evaluation: `{'wall_time_sec': 287.7, 'cost_usd': None, 'provider_requests': 14, 'agent_iterations': 14, 'termination_reason': 'end_turn'}`
- method evaluation: `{'wall_time_sec': 214.3, 'cost_usd': 0.27320125, 'provider_requests': 10, 'agent_iterations': 10, 'termination_reason': 'end_turn'}`
- known_total_cost_usd: `0.27320125`
