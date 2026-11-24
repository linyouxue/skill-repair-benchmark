# Controlled55 WML Semantic Review

Review basis: organizer annotations and Gold repairs, the immutable WML candidate versus its exported input, and the native execution trajectory where useful.
Target verdict is not inferred from native pass/fail. The reviewer attribution is AI-assisted Codex review, not independent human sign-off.
For `target_semantically_repaired`, partial fixes are `false` unless the target mechanism is functionally repaired by an equivalent reusable rule. For `non_target_gold_preserved`, only leave-one-out trials are applicable; supplied non-target repairs are checked against the frozen input and candidate bundle. Gold atoms shared with the held-out target are not counted as independent preservation evidence.

## location-dialogue-parser

Task: `dialogue-parser`; condition: `location_hint`; target repairs: `RI-001`.
Target semantic verdict: **false**.
Rationale: Reachability guidance was added, but the target defect is the implicit End contract. The candidate still permits constructing/serializing a synthetic End content node and does not align JSON export, validation, and visualization.
Official Gold target statement(s):
- 明确 End 默认仅为终止 edge target；没有显式且含内容的 [End] section 时，不得建立或序列化 Node(id="End")；非终止 edge target 必须存在；reachability 仅覆盖 content nodes，并在遇到 End 时终止该路径；DOT 中的 End marker 不等于 JSON node。
Candidate changed files: dialogue-graph/scripts/dialogue_graph.py.
Candidate manifest SHA256: `931503621c3bc7536150ab6bcdebef4933ae403c2f6d358cc1abec7ca5360ef2`.
Native verifier outcome: `fail`, reward `0.833`; protocol audit `True`. Native result is corroborating evidence only, not the semantic verdict.
Other Gold preservation verdict: **not_applicable**. Not a leave-one-out condition.
