# Controlled55 WML Semantic Review

Review basis: organizer annotations and Gold repairs, the immutable WML candidate versus its exported input, and the native execution trajectory where useful.
Target verdict is not inferred from native pass/fail. The reviewer attribution is AI-assisted Codex review, not independent human sign-off.
For `target_semantically_repaired`, partial fixes are `false` unless the target mechanism is functionally repaired by an equivalent reusable rule. For `non_target_gold_preserved`, only leave-one-out trials are applicable; supplied non-target repairs are checked against the frozen input and candidate bundle. Gold atoms shared with the held-out target are not counted as independent preservation evidence.

## single-fix-build-google-auto-RI-001

Task: `fix-build-google-auto`; condition: `leave_one_out`; target repairs: `RI-001`.
Target semantic verdict: **false**.
Rationale: The candidate adds generic toolchain notes but does not make exact JDK-7 CI reproduction a prerequisite before edits. Its changes also remove the supplied nested dependency prescription.
Official Gold target statement(s):
- 在任何项目修改前先读取 .travis.yml/workflow/wrapper/build POM，记录 java -version、javac -version、mvn -version，并切换到 CI 明确声明的 JDK；随后执行 CI 的原始完整命令（包括 -f build-pom.xml、verify、profile/flag）。错误 JDK 下出现的 tools.jar、模块系统、注解 API 等症状不得驱动迁移式修复。mvn test 或在错误 toolchain 下的绿色命令不能视为有效复现；只有目标 CI 环境中的剩余错误才进入根因分析。
Candidate changed files: maven-build-lifecycle/SKILL.md.
Candidate manifest SHA256: `f0e93827d9b3d8bc227a80d2b4f5cd16c73afacb90585e2aa61be57575fdeb01`.
Native verifier outcome: `fail`, reward `0.0`; protocol audit `True`. Native result is corroborating evidence only, not the semantic verdict.
Other Gold preservation verdict: **false**. The candidate edits the shared Maven Skill and removes the supplied RI-002 functional-POM dependency prescription; this non-target Gold repair is not retained.
