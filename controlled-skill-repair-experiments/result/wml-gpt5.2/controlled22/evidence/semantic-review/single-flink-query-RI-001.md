# Controlled55 WML Semantic Review

Review basis: organizer annotations and Gold repairs, the immutable WML candidate versus its exported input, and the native execution trajectory where useful.
Target verdict is not inferred from native pass/fail. The reviewer attribution is AI-assisted Codex review, not independent human sign-off.
For `target_semantically_repaired`, partial fixes are `false` unless the target mechanism is functionally repaired by an equivalent reusable rule. For `non_target_gold_preserved`, only leave-one-out trials are applicable; supplied non-target repairs are checked against the frozen input and candidate bundle. Gold atoms shared with the held-out target are not counted as independent preservation evidence.

## single-flink-query-RI-001

Task: `flink-query`; condition: `leave_one_out`; target repairs: `RI-001`.
Target semantic verdict: **false**.
Rationale: The candidate edit strengthens existing activity eligibility but does not fix the target completion predicate: FINISH remains broadened with FAIL/KILL examples and is not bound to the task-authorized exact event.
Official Gold target statement(s):
- 实现前分别声明 contributing-event predicate 与精确的 completion-event predicate；任务指定某一结束状态时，除非规范明确声明等价，否则不得把其他 terminal state 纳入完成条件。
Candidate changed files: senior-data-engineer/SKILL.md.
Candidate manifest SHA256: `09c92efa0c174d11e48b563350301d61454e669555d37e14b7ad51bee95a1ea4`.
Native verifier outcome: `fail`, reward `0.0`; protocol audit `True`. Native result is corroborating evidence only, not the semantic verdict.
Other Gold preservation verdict: **true**. The non-target RI-002 emission gate remains in the candidate Skill, including activity-only eligibility and null aggregate suppression.
