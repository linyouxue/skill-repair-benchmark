# Controlled55 WML Semantic Review

Review basis: organizer annotations and Gold repairs, the immutable WML candidate versus its exported input, and the native execution trajectory where useful.
Target verdict is not inferred from native pass/fail. The reviewer attribution is AI-assisted Codex review, not independent human sign-off.
For `target_semantically_repaired`, partial fixes are `false` unless the target mechanism is functionally repaired by an equivalent reusable rule. For `non_target_gold_preserved`, only leave-one-out trials are applicable; supplied non-target repairs are checked against the frozen input and candidate bundle. Gold atoms shared with the held-out target are not counted as independent preservation evidence.

## single-manufacturing-equipment-maintenance-RI-001

Task: `manufacturing-equipment-maintenance`; condition: `leave_one_out`; target repairs: `RI-001`.
Target semantic verdict: **true**.
Rationale: The candidate states the five exact output paths and schemas, requires all five deliverables, and adds a pre-finish validity checklist. This directly turns the previously optional scaffold into a required complete-output contract; Q02 is a separate non-target rule.
Official Gold target statement(s):
- 把任务交付物变成 blocking completion gate：开始执行后必须创建 /app/output/q01.json、q02.json、q03.json、q04.json、q05.json 五个文件；不得在只读取数据、检查 handbook、写计划、展示示例或只完成部分问题后结束。结束前必须重新列出 /app/output，验证五个精确文件名均存在，用 JSON parser 逐个成功解析，并明确计数为 5；任一文件缺失、不可解析或未完成时都必须继续执行而不是宣布完成。
Candidate changed files: reflow-profile-compliance-toolkit/SKILL.md.
Candidate manifest SHA256: `1b43002041862bf892945fed12d7bba987d00954a1d009869c24540d057fe34f`.
Native verifier outcome: `pass`, reward `1.0`; protocol audit `True`. Native result is corroborating evidence only, not the semantic verdict.
Other Gold preservation verdict: **true**. The non-target RI-002 global-minimum TAL invariant remains present in the candidate bundle.
