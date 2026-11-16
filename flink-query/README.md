# Flink 规模与阶段泛化数据 v2

四组沿用[固定版本 SkillsBench Flink](https://github.com/benchflow-ai/skillsbench/tree/b63b7b2850226b6aa4fb5929a8c1ac7bc4d9a6af/tasks/flink-query) 的题面、Java 骨架、原 Skill、依赖和输入路径。每组独立放在 `tasks/<组名>/`，由框架隔离部署 verifier。四组共 7,944 个作业，作业 ID 彼此独立，也与 SkillsBench 原输入无重叠。原始来源为 John Wilkes 与 Charles Reiss 发布的 Google ClusterData2011_2 分片 00002–00025。数据包含有记录的事件删减、时间戳处理和按原题事件模板生成的样例。[Google 数据来源](https://github.com/google/cluster-data/blob/master/ClusterData2011_2.md) · [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)

| 组 | 应输出 / 应排除 | Job 事件行 | Task 事件行 | 有 FINISH 无 task SUBMIT | 仅 Task 表可见 | 双阶段 | 边界样例 |
|---|---:|---:|---:|---:|---:|---:|---:|
| `repair` | 644 / 680 | 3,130 | 84,250 | 54 | 178 | 32 | 10 |
| `scale` | 1,288 / 1,360 | 6,268 | 168,481 | 108 | 356 | 64 | 20 |
| `stages` | 644 / 680 | 3,130 | 84,232 | 54 | 178 | 64 | 10 |
| `combined` | 1,288 / 1,360 | 6,260 | 168,387 | 108 | 356 | 128 | 20 |

基准规模采用原题的负例构成。有提交且 KILL、无 FINISH 的作业 229 个。有提交、无 FINISH/KILL 的作业 361 个，其中 174 个仅在 Task 表里出现。有 FINISH、无提交的作业 54 个，合计含 96 行非 SUBMIT 的 Task 事件。另有 30 个 KILL 无提交和 6 个其他无提交作业。双倍规模组按各类配额翻倍。正例多次提交为 80 / 160 个，含重提交的正例为 16 / 32 个。各类的每作业 Task 事件数与 SUBMIT 次数联合分箱匹配。

每个基准规模组含 67 个按原题真实事件模板生成的新作业，双倍规模组含 134 个。新作业使用独立 ID，整体平移时间戳并保留其余字段。另一部分作业删减 Job 表记录，复现原题中只有 Task 表记录等可观察情形。边界作业的两个 SUBMIT 间隔取 599 秒、599.999999 秒、600 秒、600.000001 秒、601 秒。每档在基准规模组有 2 个作业，双倍规模组有 4 个。前三档合并为一阶段，后两档切为两阶段。边界样例计入表内原有配额。

每次运行输出一个最终正确率。分子为正确输出与正确排除的作业数之和。分母为输入作业总数，加上每个未知 ID 和每条非法行各一个额外错误项。已知作业等权。正例恰好输出一次且数值正确才算对，负例出现即算错。空、缺失、不可读或没有合法 tuple 的输出得 0。阶段与边界汇总通过 `stage_feedback.json` 提供诊断，`reward.txt` 只有这个连续正确率。

四组参考输出由 Python 和 SQLite 从实际日志复算并逐项对照。空文件得 0%，阈值 590 秒得 99.55%，恰好 600 秒就切分得 99.85%。完全漏切或使用 610 秒阈值，在 `repair`、`scale` 得 97.58%，在 `stages`、`combined` 得 95.17%。这是等权作业口径下按实际错题数扣分。另有 12 个保留原始时间戳的天然两阶段作业放在 `audit/natural_two_stage/` 中，用于单独的离线语义检查。

组织者可用 `audit/*-lineage.json` 重放每组的改动。完整重建另需组织者的本地构建脚本、上版输入与原始分片。当前验收覆盖数据、离线答案、评分规则与 verifier 写出。真实 Docker 执行和新修复集基线采证有各自的运行验收。现有 SkillHone 的旧反馈导出只选标量。运行新修复基线时需核对阶段汇总是否进入该方法实际收到的允许反馈。

[作业配额、错误对照与分箱统计](audit/summary.json) · [落盘日志与导出复核](audit/export-verification.json)

## 运行方式

选择 `tasks/repair`、`tasks/scale`、`tasks/stages` 或 `tasks/combined` 中的一组，复制为临时任务根目录下的 `flink-query/`，将该根目录交给[统一执行器](../DELIVERY_GUIDE.md#5-入口-b修复算法自动调用)，并使用 `task_id="flink-query"`。每组独立执行；`verifier/` 仅供评分侧，`audit/` 仅供组织者审计。冻结修复后的 Skill 再运行泛化组，避免用泛化结果反向选版。

旧版的原题、GPT-5.2 诊断材料和三批评测结果可从[替换前的 Git 提交](https://github.com/linyouxue/skill-repair-benchmark/tree/b53bf2f7d10a5c576cccfe05ddbaafdc2d32d155/flink-query)查看。
