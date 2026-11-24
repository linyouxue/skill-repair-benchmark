# Controlled55 WML Semantic Review

Review basis: organizer annotations and Gold repairs, the immutable WML candidate versus its exported input, and the native execution trajectory where useful.
Target verdict is not inferred from native pass/fail. The reviewer attribution is AI-assisted Codex review, not independent human sign-off.
For `target_semantically_repaired`, partial fixes are `false` unless the target mechanism is functionally repaired by an equivalent reusable rule. For `non_target_gold_preserved`, only leave-one-out trials are applicable; supplied non-target repairs are checked against the frozen input and candidate bundle. Gold atoms shared with the held-out target are not counted as independent preservation evidence.

## single-flink-query-all

Task: `flink-query`; condition: `all_faults`; target repairs: `RI-001, RI-002`.
Target semantic verdict: **false**.
Rationale: Some key-set guidance was added, but exact completion, eligibility dominance for every emit path, and suppression of null/empty aggregates are not all enforced.
Official Gold target statement(s):
- 实现前分别声明 contributing-event predicate 与精确的 completion-event predicate；任务指定某一结束状态时，除非规范明确声明等价，否则不得把其他 terminal state 纳入完成条件。
- 只允许 contributing event 建立 output eligibility；每条 collect、emit 或 sink 路径都必须先检查该资格或等价的非空 aggregate 证据；null aggregate 必须表示无活动并且不输出；提交前用 lifecycle-only 负例和 unexpected-extra-key 检查验证该约束。
Candidate changed files: senior-data-engineer/SKILL.md.
Candidate manifest SHA256: `59ef33a15e0e26696432b13aa91139eee3daa94785d92080002f9aebb57def1c`.
Native verifier outcome: `fail`, reward `0.0`; protocol audit `True`. Native result is corroborating evidence only, not the semantic verdict.
Other Gold preservation verdict: **not_applicable**. Not a leave-one-out condition.
