# Controlled55 WML Semantic Review

Review basis: organizer annotations and Gold repairs, the immutable WML candidate versus its exported input, and the native execution trajectory where useful.
Target verdict is not inferred from native pass/fail. The reviewer attribution is AI-assisted Codex review, not independent human sign-off.
For `target_semantically_repaired`, partial fixes are `false` unless the target mechanism is functionally repaired by an equivalent reusable rule. For `non_target_gold_preserved`, only leave-one-out trials are applicable; supplied non-target repairs are checked against the frozen input and candidate bundle. Gold atoms shared with the held-out target are not counted as independent preservation evidence.

## location-pddl-airport-planning

Task: `pddl-airport-planning`; condition: `location_hint`; target repairs: `RI-001`.
Target semantic verdict: **false**.
Rationale: The candidate changes the problem input and save-plan schema, but does not establish PDDLWriter(problem) serialization or exact-file parse/validate round-trip. Its examples use hyphenated Python identifiers, which are invalid syntax.
Official Gold target statement(s):
- 把保存契约统一为 save-plan(problem_object, plan_object, output_path)，并让结构化 save_plan.skill 显式声明 problem 输入。要求始终使用 PDDLWriter(problem).write_plan(plan, filename=output_path)，禁止用 str(ActionInstance) 或手写 move(a, b) 风格序列化；sequential plan 必须一行一个 (action-name arg1 ... argN)。保存后必须对 exact output file 执行 PDDLReader.parse_plan(problem, output_path)，再用 PlanValidator 验证 parsed plan；只有 round-trip VALID 才允许结束。
Candidate changed files: pddl-skills/SKILL.md, pddl-skills/load_problem.skill, pddl-skills/save_plan.skill.
Candidate manifest SHA256: `e18e4deda8a798383e5976d0efc9354e8d05b9d01ec62b69eff9c86067abb02d`.
Native verifier outcome: `fail`, reward `0.0`; protocol audit `True`. Native result is corroborating evidence only, not the semantic verdict.
Other Gold preservation verdict: **not_applicable**. Not a leave-one-out condition.
