# Controlled55 WML Semantic Review

Review basis: organizer annotations and Gold repairs, the immutable WML candidate versus its exported input, and the native execution trajectory where useful.
Target verdict is not inferred from native pass/fail. The reviewer attribution is AI-assisted Codex review, not independent human sign-off.
For `target_semantically_repaired`, partial fixes are `false` unless the target mechanism is functionally repaired by an equivalent reusable rule. For `non_target_gold_preserved`, only leave-one-out trials are applicable; supplied non-target repairs are checked against the frozen input and candidate bundle. Gold atoms shared with the held-out target are not counted as independent preservation evidence.

## single-sec-financial-report-RI-001

Task: `sec-financial-report`; condition: `leave_one_out`; target repairs: `RI-001`.
Target semantic verdict: **false**.
Rationale: The changed helper now reads a quarter-specific data path, but the target is correcting the two Skills to call helpers through their installed absolute /skills/.../scripts paths.
Official Gold target statement(s):
- 将两个 Skill 的 helper 路径改为稳定的 /skills/<skill>/scripts/...；helper 未找到时先检查 Skill 安装路径，不得因 cwd 不同而静默替换分析算法。
Candidate changed files: 13f-analyzer/scripts/holding_analysis.py.
Candidate manifest SHA256: `dee3672e47b315926b17b71bf572eb8e249a536dbf16c0374a48eae51c83d72f`.
Native verifier outcome: `pass`, reward `1.0`; protocol audit `True`. Native result is corroborating evidence only, not the semantic verdict.
Other Gold preservation verdict: **true**. RI-002 and RI-003 guidance is in distinct script/Skill files and remains byte-identical to the frozen input.
