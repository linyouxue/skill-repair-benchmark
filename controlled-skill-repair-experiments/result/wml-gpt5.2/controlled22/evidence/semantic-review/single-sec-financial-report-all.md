# Controlled55 WML Semantic Review

Review basis: organizer annotations and Gold repairs, the immutable WML candidate versus its exported input, and the native execution trajectory where useful.
Target verdict is not inferred from native pass/fail. The reviewer attribution is AI-assisted Codex review, not independent human sign-off.
For `target_semantically_repaired`, partial fixes are `false` unless the target mechanism is functionally repaired by an equivalent reusable rule. For `non_target_gold_preserved`, only leave-one-out trials are applicable; supplied non-target repairs are checked against the frozen input and candidate bundle. Gold atoms shared with the held-out target are not counted as independent preservation evidence.

## single-sec-financial-report-all

Task: `sec-financial-report`; condition: `all_faults`; target repairs: `RI-001, RI-002, RI-003`.
Target semantic verdict: **false**.
Rationale: The candidate changes holding-analysis file loading and a variable name, but does not repair the annotated helper paths, stock-count semantics, and quarter-difference ranking workflow.
Official Gold target statement(s):
- 将两个 Skill 的 helper 路径改为稳定的 /skills/<skill>/scripts/...；helper 未找到时先检查 Skill 安装路径，不得因 cwd 不同而静默替换分析算法。
- 明确 Total AUM、Total number of holdings 与 Number of stock holdings 的语义差异；问题询问“多少只股票”时使用 helper 的 stock holdings 字段。
- 每季度分别使用对应 accession；应用与 helper 相同的股票过滤；按 CUSIP 聚合 VALUE；outer join 后补 0；计算 current-baseline；仅保留正值并降序排序；输出请求数量的唯一 CUSIP。
Candidate changed files: 13f-analyzer/scripts/holding_analysis.py.
Candidate manifest SHA256: `f75452380f1dfd52caa62b527dcf7c22212237f0b22f3d3800ad3701bf70c082`.
Native verifier outcome: `fail`, reward `0.0`; protocol audit `True`. Native result is corroborating evidence only, not the semantic verdict.
Other Gold preservation verdict: **not_applicable**. Not a leave-one-out condition.
