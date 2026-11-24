# Controlled55 WML Semantic Review

Review basis: organizer annotations and Gold repairs, the immutable WML candidate versus its exported input, and the native execution trajectory where useful.
Target verdict is not inferred from native pass/fail. The reviewer attribution is AI-assisted Codex review, not independent human sign-off.
For `target_semantically_repaired`, partial fixes are `false` unless the target mechanism is functionally repaired by an equivalent reusable rule. For `non_target_gold_preserved`, only leave-one-out trials are applicable; supplied non-target repairs are checked against the frozen input and candidate bundle. Gold atoms shared with the held-out target are not counted as independent preservation evidence.

## single-fix-build-google-auto-RI-002

Task: `fix-build-google-auto`; condition: `leave_one_out`; target repairs: `RI-002`.
Target semantic verdict: **true**.
Rationale: The candidate adds a reusable nested-Invoker diagnostic and repair workflow: identify the nested POM/log, inspect effective POM and dependency tree there, reconcile coupled versions in the local POM, and rerun the failing goal. This is an equivalent reusable mechanism to the benchmark-specific version example.
Official Gold target statement(s):
- 当 maven-invoker-plugin 报告 */pom.xml 失败时，把该目录视为独立 Maven project：读取对应 nested POM 与 Invoker build.log，定位第一条具体 compiler/test error，并在同一目标 JDK 下检查其 dependency tree/effective dependency mediation；不要假设父 reactor 的依赖版本自动支配 Invoker POM。对 missing library API（本例 MoreObjects），先确认实际选中的库版本。对该 Google Auto 快照，应把 value/src/it/functional/pom.xml 的测试依赖作为一个同步单元修复：显式使用 Guava 19.0，并同步 guava-testlib 19.0、Truth 0.28、JUnit 4.12、jsr305 3.0.x；保持修改局限于 functional integration-test POM，最后重新执行 JDK 7 下完整 verify，包含所有 Invoker tests。
Candidate changed files: maven-build-lifecycle/SKILL.md.
Candidate manifest SHA256: `720a2b001afb5f879a76eea52967a10c6fa714afd2c9ea0629f43fed6b839a3d`.
Native verifier outcome: `fail`, reward `0.0`; protocol audit `True`. Native result is corroborating evidence only, not the semantic verdict.
Other Gold preservation verdict: **true**. The RI-001 JDK-7 and exact-CI gate remains in the opening Core rule and minimal diagnostic workflow.
