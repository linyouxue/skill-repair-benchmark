# 位置提示与无提示结果对照（描述性）

历史无提示来自 Zenmux GPT‑5.2；本轮受控来自 Tatumass GPT‑5.2，保留配置差异，不能把差值解释为仅由提示导致。

| 任务 | 位置提示奖励 | 历史无提示奖励 | 历史无提示审计 |
|---|---:|---:|---|
| dialogue-parser | 0.833 | 1.0 | invalid |
| data-to-d3 | 1.0 | 1.0 | valid_pass |
| flink-query | 0.0 | 0.0 | valid_fail |
| manufacturing-equipment-maintenance | 1.0 | 1.0 | valid_pass |
| pddl-airport-planning | 0.0 | 1.0 | valid_pass |

dialogue-parser 历史轨迹末尾有未执行的预览命令；原分数保留，当前已获准补充 Tatumass 执行验证，结果将单列。