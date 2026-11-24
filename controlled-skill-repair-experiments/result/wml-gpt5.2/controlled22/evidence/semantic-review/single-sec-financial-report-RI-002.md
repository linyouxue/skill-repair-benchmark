# Controlled55 WML Semantic Review

Review basis: organizer annotations and Gold repairs, the immutable WML candidate versus its exported input, and the native execution trajectory where useful.
Target verdict is not inferred from native pass/fail. The reviewer attribution is AI-assisted Codex review, not independent human sign-off.
For `target_semantically_repaired`, partial fixes are `false` unless the target mechanism is functionally repaired by an equivalent reusable rule. For `non_target_gold_preserved`, only leave-one-out trials are applicable; supplied non-target repairs are checked against the frozen input and candidate bundle. Gold atoms shared with the held-out target are not counted as independent preservation evidence.

## single-sec-financial-report-RI-002

Task: `sec-financial-report`; condition: `leave_one_out`; target repairs: `RI-002`.
Target semantic verdict: **false**.
Rationale: The candidate fixes adjacent-string concatenation in the stock-class list but does not distinguish Number of stock holdings from total holding rows when answering how many stocks.
Official Gold target statement(s):
- 明确 Total AUM、Total number of holdings 与 Number of stock holdings 的语义差异；问题询问“多少只股票”时使用 helper 的 stock holdings 字段。
Candidate changed files: 13f-analyzer/scripts/one_fund_analysis.py.
Candidate manifest SHA256: `768354a4b4cef25e856000bb3091bb32e25dafd5edd91ab3c903ab72a439293e`.
Native verifier outcome: `fail`, reward `0.0`; protocol audit `True`. Native result is corroborating evidence only, not the semantic verdict.
Other Gold preservation verdict: **true**. RI-001 helper-path and RI-003 ranking guidance remain byte-identical to the frozen input.
