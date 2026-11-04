# 原题训练与诊断材料

使用原题和完整原Skill，沿用各方法现有adapter、诊断/修订/选版机制。本目录不增加材料分窗或专用读取API。修复阶段不读取evaluation、oracle和隐藏评分资源，不用泛化成绩回头挑选Skill。

| 材料 | 位置 |
|---|---|
| 原题 | [task.md](../task.md) |
| 原Skill与脚本 | [完整bundle](../environment/skills/)，含13f-analyzer和fuzzy-name-search |
| 全部ACP事件 | [acp_trajectory.jsonl](source_run/trajectory/acp_trajectory.jsonl) |
| 全部LLM请求与响应 | [llm_trajectory.jsonl](source_run/trajectory/llm_trajectory.jsonl) |
| 原生ATIF与运行记录 | [atif.json](source_run/trainer/atif.json)、[results.jsonl](source_run/results.jsonl)、[index.json](index.json) |
| 允许反馈 | [allowed_feedback.json](outputs/allowed_feedback.json)，含原版重放测试状态、当前逐项正确率及题目级对错 |
| 状态与实际可用输出 | [execution_metadata.json](outputs/execution_metadata.json)、[output_inventory.json](outputs/output_inventory.json)、[恢复的原answers.json](recovered_output/answers.json) |

来源为指定GPT-5.2 Original-Skill运行 `sec-financial-report-original-skill-server-r003`，固定提交和每份原生文件的Git blob见index。两份Skill正文被持续预载；显式Skill调用数0与30/30次响应包含Skill指令的证据分别记录，不把“未显式调用”解释为未使用正文。

历史原评分在uv下载时失败，原reward0及原生记录保留，不能直接当成有效评分。本次恢复的输出来自ACP第30行成功写入和第31行实际文件回读，并与LLM第28—30行交叉核对；没有修改答案。恢复文件的哈希是本次恢复物哈希，不冒称当年已有独立归档，详见[provenance.json](recovered_output/provenance.json)。

同一原输出重放原版测试得1通过/1失败；当前正确率为4/10（40%）：q1正确、q2错误、q3五个位置全错、q4三个位置全对。因此可作为**经重放确认的模型FAIL**，同时保留历史原评分环境故障的说明。反馈不含GT值或隐藏断言；重放CTRF及核查记录由组织者放在validation，不用于方法修复。

公开Skill的原股票类别筛选口径继续沿用。只有SKILL.md正文是本轮Skill修复的修改范围，其他原文件保持完整；不要为了匹配另一套金融统计定义而扩大股票类别。最终提交要求见[result说明](../result/README.md)。
