# Controlled55 WML Semantic Review

Review basis: organizer annotations and Gold repairs, the immutable WML candidate versus its exported input, and the native execution trajectory where useful.
Target verdict is not inferred from native pass/fail. The reviewer attribution is AI-assisted Codex review, not independent human sign-off.
For `target_semantically_repaired`, partial fixes are `false` unless the target mechanism is functionally repaired by an equivalent reusable rule. For `non_target_gold_preserved`, only leave-one-out trials are applicable; supplied non-target repairs are checked against the frozen input and candidate bundle. Gold atoms shared with the held-out target are not counted as independent preservation evidence.

## single-sec-financial-report-RI-003

Task: `sec-financial-report`; condition: `leave_one_out`; target repairs: `RI-003`.
Target semantic verdict: **true**.
Rationale: The candidate tells the agent to use the existing helper Top Buys output, rank by Abs change, retain positive increases, and take top N unique CUSIPs. The supplied helper already performs the target stock filtering, CUSIP aggregation, outer join and zero fill, so this guidance selects the correct output path.
Official Gold target statement(s):
- 每季度分别使用对应 accession；应用与 helper 相同的股票过滤；按 CUSIP 聚合 VALUE；outer join 后补 0；计算 current-baseline；仅保留正值并降序排序；输出请求数量的唯一 CUSIP。
Candidate changed files: 13f-analyzer/SKILL.md.
Candidate manifest SHA256: `687bc9ff9372a5331f661469be63e353a9c14bb7b7454ae157e919ce3368ccf9`.
Native verifier outcome: `pass`, reward `1.0`; protocol audit `True`. Native result is corroborating evidence only, not the semantic verdict.
Other Gold preservation verdict: **true**. RI-001 helper-path rules and RI-002 stock-count semantics remain byte-identical to the frozen input.
