# Controlled55 WML Semantic Review

Review basis: organizer annotations and Gold repairs, the immutable WML candidate versus its exported input, and the native execution trajectory where useful.
Target verdict is not inferred from native pass/fail. The reviewer attribution is AI-assisted Codex review, not independent human sign-off.
For `target_semantically_repaired`, partial fixes are `false` unless the target mechanism is functionally repaired by an equivalent reusable rule. For `non_target_gold_preserved`, only leave-one-out trials are applicable; supplied non-target repairs are checked against the frozen input and candidate bundle. Gold atoms shared with the held-out target are not counted as independent preservation evidence.

## single-flink-query-RI-002

Task: `flink-query`; condition: `leave_one_out`; target repairs: `RI-002`.
Target semantic verdict: **false**.
Rationale: The candidate strengthens exact completion labeling, but does not add the target contributing-activity eligibility invariant; completion-only keys can still emit empty/zero aggregates.
Official Gold target statement(s):
- 只允许 contributing event 建立 output eligibility；每条 collect、emit 或 sink 路径都必须先检查该资格或等价的非空 aggregate 证据；null aggregate 必须表示无活动并且不输出；提交前用 lifecycle-only 负例和 unexpected-extra-key 检查验证该约束。
Candidate changed files: senior-data-engineer/SKILL.md.
Candidate manifest SHA256: `5616d1366d8be47d40d8b35655201ea39b8f3e709c5eb162cb312cf29298f80a`.
Native verifier outcome: `fail`, reward `0.0`; protocol audit `True`. Native result is corroborating evidence only, not the semantic verdict.
Other Gold preservation verdict: **true**. The non-target RI-001 exact completion-event rule remains in the candidate Skill and still forbids broadening FINISH to other terminal labels.
