# SkillTTA / Claude Opus 4.7 AIGW (Tatumass) — group_02

- Skill 版本：沿用 `jpg-ocr-stat/result/skilltta-claude4.7/skills/` 的冻结版本；bundle SHA-256 为 `sha256:d477760d2d0c1da2196b027a473f0174194bae28803824eceed8f2bee394844f`，未根据泛化成绩修改或重新选择。
- 数据版本：`group_02`，20 张小票、每次固定 40 个日期/金额字段；evaluation commit `bee9b0df5b04a300735e5009f5238f5d5c8aaf61`。
- 执行配置：Tatumass Anthropic-compatible `tatumass/claude-opus-4-7@AIGW-default`；OpenHands CLI/SDK/Tools 1.28.1；每次最多 65 次 parent iteration，completion guard 共用剩余额度。
- 三次运行均从任务初始状态独立执行；原 Excel 位于各次 `artifacts/stat_ocr.xlsx`，并在 run 根目录保留一份同字节副本 `stat_ocr.xlsx`。完整 ACP/LLM 轨迹、verifier 原始输出和执行器元数据均在相应 run 目录。
- 机器可核验汇总：`PACKAGE_AUDIT.json`。

- `run_01`：`jpg-group02-skilltta-opus47-aigw-d477-clean6-r001`，40/65 次父迭代，终止原因为 `end_turn`，Excel SHA-256 `4a3a307d607e107df667a26377f452baf174224061a80616f36bf1ed329bf895`，verifier 同时报告普通交付结构问题：`missing_or_unexpected_filenames`, `wrong_row_count`；仍按固定 40 字段分母如实计分。
- `run_02`：`jpg-group02-skilltta-opus47-aigw-d477-clean6-r002`，36/65 次父迭代，终止原因为 `end_turn`，Excel SHA-256 `cd188050dac6966467859e2ac4943269f1c3b1eb48086e4355a9695d42a69ec4`，verifier 同时报告普通交付结构问题：`missing_or_unexpected_filenames`, `wrong_row_count`；仍按固定 40 字段分母如实计分。
- `run_03`：`jpg-group02-skilltta-opus47-aigw-d477-clean6-r003`，56/65 次父迭代，终止原因为 `end_turn`，Excel SHA-256 `a52d48222b29ff972e7e4f78a5cacf31fba425fe673d35d4523ac0668450f872`，verifier 同时报告普通交付结构问题：`missing_or_unexpected_filenames`, `wrong_row_count`；仍按固定 40 字段分母如实计分。

| 组别 | 第1次 | 第2次 | 第3次 | 均值 |
|---|---:|---:|---:|---:|
| group_02 | 0.900000（36/40） | 0.875000（35/40） | 0.900000（36/40） | 0.891667（107/120） |
