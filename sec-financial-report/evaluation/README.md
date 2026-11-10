# 冻结 Skill 后的三组同源评测

三组沿用训练任务的七问、输出结构和逐项评分规则。每组 10 个案例、100 个答案项。

| 批次 | 报告期 | 查询对象 | 输入 |
| --- | --- | --- | --- |
| group_01 | 2024 Q3 → Q4 | 训练组 A | [本组完整 ZIP](group_01/inputs/) |
| group_02 | 2024 Q1 → Q2 | 新对象 B | [训练组同两份完整 ZIP](../environment/) |
| group_03 | 2025 Q4 → 2026 Q1 | 同一组 B | [本组完整 ZIP](group_03/inputs/) |

从仓库根目录导出一组，输出目录须为新建目录。

```bash
python sec-financial-report/evaluation/prepare_task.py --group group_01 --output /tmp/sec-group01/tasks/sec-financial-report
python sec-financial-report/evaluation/score_results.py --group group_01 --actual /path/to/answers.json --report /tmp/sec-group01-accuracy.json
```

导出的 `environment/` 放完整季度 ZIP 和 Skill，评测参考留在 `verifier/`。用现有 adapter 和 `BenchmarkExecutor` 运行，`tasks_root` 为例子中的 `/tmp/sec-group01/tasks`，每次使用新运行 ID。群组与季度来源见[清单](manifest.json)，结果留证见[结果说明](results/README.md)。
