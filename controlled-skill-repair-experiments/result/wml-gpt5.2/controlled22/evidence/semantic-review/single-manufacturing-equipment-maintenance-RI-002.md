# Controlled55 WML Semantic Review

Review basis: organizer annotations and Gold repairs, the immutable WML candidate versus its exported input, and the native execution trajectory where useful.
Target verdict is not inferred from native pass/fail. The reviewer attribution is AI-assisted Codex review, not independent human sign-off.
For `target_semantically_repaired`, partial fixes are `false` unless the target mechanism is functionally repaired by an equivalent reusable rule. For `non_target_gold_preserved`, only leave-one-out trials are applicable; supplied non-target repairs are checked against the frozen input and candidate bundle. Gold atoms shared with the held-out target are not counted as independent preservation evidence.

## single-manufacturing-equipment-maintenance-RI-002

Task: `manufacturing-equipment-maintenance`; condition: `leave_one_out`; target repairs: `RI-002`.
Target semantic verdict: **false**.
Rationale: The candidate permits handbook-conditional maximum or other representative thermocouples; the target Q02 rule requires minimum TAL across all valid thermocouples regardless of compliance-window position.
Official Gold target statement(s):
- 对 Q02 明确规定 run-level TAL 的唯一归约规则：先对该 run 的每个有效 thermocouple 使用其 solder liquidus threshold 独立计算插值 TAL，然后在全部有效 TC 中选择全局最小 TAL；TAL 完全相同时按字典序最小 tc_id 破同值。该选择与 TAL 是低于、位于还是高于 handbook window 无关；即使所有 TC 都高于上限，也禁止改取最大 TAL或另选“最严重违规”TC。最后仅根据这个已选 minimum-TAL record 与 handbook TAL window 比较得到 status。
Candidate changed files: reflow-profile-compliance-toolkit/SKILL.md.
Candidate manifest SHA256: `35682e3571521285b498fdf74fb55a5f7752af9b7808e83c6461f5cf38f7be9d`.
Native verifier outcome: `fail`, reward `0.0`; protocol audit `True`. Native result is corroborating evidence only, not the semantic verdict.
Other Gold preservation verdict: **true**. The non-target RI-001 five-output completion contract remains in the candidate bundle.
