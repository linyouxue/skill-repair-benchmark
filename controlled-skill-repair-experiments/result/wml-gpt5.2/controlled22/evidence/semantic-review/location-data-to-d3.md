# Controlled55 WML Semantic Review

Review basis: organizer annotations and Gold repairs, the immutable WML candidate versus its exported input, and the native execution trajectory where useful.
Target verdict is not inferred from native pass/fail. The reviewer attribution is AI-assisted Codex review, not independent human sign-off.
For `target_semantically_repaired`, partial fixes are `false` unless the target mechanism is functionally repaired by an equivalent reusable rule. For `non_target_gold_preserved`, only leave-one-out trials are applicable; supplied non-target repairs are checked against the frozen input and candidate bundle. Gold atoms shared with the held-out target are not counted as independent preservation evidence.

## location-data-to-d3

Task: `data-to-d3`; condition: `location_hint`; target repairs: `RI-001`.
Target semantic verdict: **true**.
Rationale: The repaired guidance makes overlaid SVG labels non-interactive and routes click/hover handling through the mark group; it directly addresses pointer interception and retains both chart-table selection directions. Native interactive_linking also passed. Tooltip and legend failures are separate verifier issues.
Official Gold target statement(s):
- 对覆盖交互 mark 的纯视觉 SVG text、label、icon 和 annotation 统一设置 pointer-events:none；交付前从代表性 mark 的可见中心执行真实浏览器点击，双向核对图表与表格联动，遇到 intercepted-pointer 或 click timeout 时必须修复后再结束。
Candidate changed files: d3-visualization/SKILL.md.
Candidate manifest SHA256: `36c1df102b35f10ab4dda7f85e3a519a022236939740dbe1e71ae76636e25416`.
Native verifier outcome: `fail`, reward `0.0`; protocol audit `True`. Native result is corroborating evidence only, not the semantic verdict.
Other Gold preservation verdict: **not_applicable**. Not a leave-one-out condition.
