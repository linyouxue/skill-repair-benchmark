# Controlled55 WML Semantic Review

Review basis: organizer annotations and Gold repairs, the immutable WML candidate versus its exported input, and the native execution trajectory where useful.
Target verdict is not inferred from native pass/fail. The reviewer attribution is AI-assisted Codex review, not independent human sign-off.
For `target_semantically_repaired`, partial fixes are `false` unless the target mechanism is functionally repaired by an equivalent reusable rule. For `non_target_gold_preserved`, only leave-one-out trials are applicable; supplied non-target repairs are checked against the frozen input and candidate bundle. Gold atoms shared with the held-out target are not counted as independent preservation evidence.

## location-manufacturing-equipment-maintenance

Task: `manufacturing-equipment-maintenance`; condition: `location_hint`; target repairs: `RI-001, RI-002`.
Target semantic verdict: **false**.
Rationale: The output checklist addresses RI-001, but the same candidate leaves RI-002 open by making TAL sensor selection handbook-conditional and permitting extrema other than the required unconditional global minimum.
Official Gold target statement(s):
- 把任务交付物变成 blocking completion gate：开始执行后必须创建 /app/output/q01.json、q02.json、q03.json、q04.json、q05.json 五个文件；不得在只读取数据、检查 handbook、写计划、展示示例或只完成部分问题后结束。结束前必须重新列出 /app/output，验证五个精确文件名均存在，用 JSON parser 逐个成功解析，并明确计数为 5；任一文件缺失、不可解析或未完成时都必须继续执行而不是宣布完成。
- 对 Q02 明确规定 run-level TAL 的唯一归约规则：先对该 run 的每个有效 thermocouple 使用其 solder liquidus threshold 独立计算插值 TAL，然后在全部有效 TC 中选择全局最小 TAL；TAL 完全相同时按字典序最小 tc_id 破同值。该选择与 TAL 是低于、位于还是高于 handbook window 无关；即使所有 TC 都高于上限，也禁止改取最大 TAL或另选“最严重违规”TC。最后仅根据这个已选 minimum-TAL record 与 handbook TAL window 比较得到 status。
Candidate changed files: reflow-profile-compliance-toolkit/SKILL.md.
Candidate manifest SHA256: `b411eadc0e77bb38a2888fc4e0c798f78be2cdb660229cc7f93b5c6ae2912209`.
Native verifier outcome: `pass`, reward `1.0`; protocol audit `True`. Native result is corroborating evidence only, not the semantic verdict.
Other Gold preservation verdict: **not_applicable**. Not a leave-one-out condition.
