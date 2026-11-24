# Controlled55 WML Semantic Review

Review basis: organizer annotations and Gold repairs, the immutable WML candidate versus its exported input, and the native execution trajectory where useful.
Target verdict is not inferred from native pass/fail. The reviewer attribution is AI-assisted Codex review, not independent human sign-off.
For `target_semantically_repaired`, partial fixes are `false` unless the target mechanism is functionally repaired by an equivalent reusable rule. For `non_target_gold_preserved`, only leave-one-out trials are applicable; supplied non-target repairs are checked against the frozen input and candidate bundle. Gold atoms shared with the held-out target are not counted as independent preservation evidence.

## single-fix-build-google-auto-all

Task: `fix-build-google-auto`; condition: `all_faults`; target repairs: `RI-001, RI-002`.
Target semantic verdict: **false**.
Rationale: The target nested dependency repair is not localized: the candidate emphasizes a general/main-reactor workflow and does not prescribe or operationalize the coherent functional-Invoker dependency repair.
Official Gold target statement(s):
- 在任何项目修改前先读取 .travis.yml/workflow/wrapper/build POM，记录 java -version、javac -version、mvn -version，并切换到 CI 明确声明的 JDK；随后执行 CI 的原始完整命令（包括 -f build-pom.xml、verify、profile/flag）。错误 JDK 下出现的 tools.jar、模块系统、注解 API 等症状不得驱动迁移式修复。mvn test 或在错误 toolchain 下的绿色命令不能视为有效复现；只有目标 CI 环境中的剩余错误才进入根因分析。
- 当 maven-invoker-plugin 报告 */pom.xml 失败时，把该目录视为独立 Maven project：读取对应 nested POM 与 Invoker build.log，定位第一条具体 compiler/test error，并在同一目标 JDK 下检查其 dependency tree/effective dependency mediation；不要假设父 reactor 的依赖版本自动支配 Invoker POM。对 missing library API（本例 MoreObjects），先确认实际选中的库版本。对该 Google Auto 快照，应把 value/src/it/functional/pom.xml 的测试依赖作为一个同步单元修复：显式使用 Guava 19.0，并同步 guava-testlib 19.0、Truth 0.28、JUnit 4.12、jsr305 3.0.x；保持修改局限于 functional integration-test POM，最后重新执行 JDK 7 下完整 verify，包含所有 Invoker tests。
Candidate changed files: maven-build-lifecycle/SKILL.md.
Candidate manifest SHA256: `a873bcdd6fdf85a3a64574d48436f4fed5892f16f5f1dbc3d0ec1f1e193a274d`.
Native verifier outcome: `fail`, reward `0.0`; protocol audit `True`. Native result is corroborating evidence only, not the semantic verdict.
Other Gold preservation verdict: **not_applicable**. Not a leave-one-out condition.
