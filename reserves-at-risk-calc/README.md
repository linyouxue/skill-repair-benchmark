# 黄金储备风险评测

基于 SkillsBench 的 `reserves-at-risk-calc`。任务要求用 IMF 月度金价估算短期冲击，汇总各国黄金储备市值，再计算损失占总储备的比例。任务包包含一个训练集、三个受控测试集和独立的历史诊断材料。

| 目录 | 内容 |
|---|---|
| [task.md](task.md) 和 [environment](environment/) | A 组 2025 年训练题、两份冻结输入和完整原 Skill |
| [diagnosis](diagnosis/) | SkillsBench 原题、原输入、GPT‑5.2 完整失败轨迹、实际 Excel 和允许反馈 |
| [evaluation](evaluation/) | 三个测试集、隔离导出入口及接入说明 |
| [verifier](verifier/) | 连续正确率入口及训练集参考答案 |
| [result](result/) | 冻结 Skill 和执行证据的提交格式 |
| [source](source/) | IMF 冻结观测、来源说明和国家分组 |

## 训练与泛化测试

| 数据集 | 国家 | 年份 | 相对训练集的变化 |
|---|---|---:|---|
| train | A 组 9 国 | 2025 | 训练和选版 |
| group_01 | B 组 9 国 | 2025 | 只换国家 |
| group_02 | A 组 9 国 | 2023 | 只换年份 |
| group_03 | B 组 9 国 | 2023 | 国家和年份都换 |

同年份使用完全相同的 13 个月金价观测。同国家组使用完全相同的国家名单和字段可用性。各组都有 7 国同时提供黄金市值和总储备、1 国只有黄金市值、1 国只有黄金重量。另有 2 个市值已知国家同时提供重量，检验市值来源优先规则。

四组复用原题三步和工作簿的五个工作表。题面只换目标年份，并将在线下载改为读取本地冻结 IMF 工作簿。输出仍为 `/root/output/rar_result.xlsx`，`Answer` 表行列沿用原题。训练使用同一 IMF 口径的 A 组 2025 快照；历史原题和原始数据可从 diagnosis 读取。

## 同学接入

先用 [diagnosis](diagnosis/README.md) 和训练集进行诊断、修复及选版。冻结一份完整 Skill 后，由组织者独立导出每组测试。沿用现有方法 adapter 和 BenchmarkExecutor 接口，任务 ID 为 `reserves-at-risk-calc`。导出目录的父级作为 `tasks_root`。使用同一冻结 bundle 逐组运行，测试答案和评分反馈只供评测侧读取。

```bash
python reserves-at-risk-calc/evaluation/prepare_task.py --split group_01 --output /tmp/rar-g1/tasks/reserves-at-risk-calc
```

## 评分

评分器重算实际 Excel，按**正确项数 ÷ 43**写连续 reward 和逐项反馈。

| 答题区 | 计分内容 | 项数 |
|---|---|---:|
| Step 1 | 冲击系数和三项波动率统计 | 4 |
| Step 2 | 9 国黄金市值及风险敞口 | 18 |
| Step 3 | 7 国黄金市值、总储备和风险比例 | 21 |

国家按名称匹配，答题区内的国家列可换序。同一国家重复填列、缺项、错值或公式错误都按相关项记错。数值按重算后的单元格底层值比较，相对和绝对容差均为 `1e-6`。每项占约 2.33 个百分点，空输出计 0/43。Decimal 从冻结观测独立计算参考答案，Excel 公式从实际导出的两份输入重算并复核。参考值仅随 verifier 部署，评分反馈仅包含字段名和对错。
