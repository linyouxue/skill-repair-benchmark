# 冻结Skill后的三批同源评测

三组使用同源的 SEC Form 13F 数据。每组沿用原题四问，仅替换报告期、机构和证券名称，每次作答共 10 个答案项。

| 批次 | 基准期→当前期 | 案例 | 答案项 |
|---|---|---:|---:|
| group_01 | 2024-Q1→2024-Q2 | 1 | 10 |
| group_02 | 2024-Q3→2024-Q4 | 1 | 10 |
| group_03 | 2025-Q4→2026-Q1 | 1 | 10 |

每组从已复核的冻结候选中选一个按名称可以唯一定位的案例。group_01、group_02 使用 `case_001`，group_03 使用 `case_002`。各组的 inputs/data 提供两期申报表，metadata.json 与 [manifest](manifest.json) 记录冻结候选池和原始行。

## 导出和执行

从仓库根运行，输出目录必须不存在，末级目录名保持task ID：

```bash
python sec-financial-report/evaluation/prepare_task.py --group group_01 --output /tmp/sec-group01/tasks/sec-financial-report
```

将现有BenchmarkExecutor的tasks_root指向 `/tmp/sec-group01/tasks`，仍调用 `run(task_id="sec-financial-report", condition="method-skill", skill_bundle=完整冻结bundle, ...)`。同样支持group_02/03，不改方法adapter和公共API。每次使用新的rollout_id和全新任务工作区。

导出保留原 Skill 和选中组的输入表。题面由原题替换季度、机构和证券名称得到。输出文件为 `/root/answers.json`，顶层直接包含 `q1_answer`、`q2_answer`、`q3_answer` 和 `q4_answer`。该案例的参考答案位于导出任务的 `verifier/expected_output.json`，Agent 退出后部署。

评分保持每例10项：金额、持仓行数、五个有序CUSIP、三个有序经理名。缺失与错值记错，多余排名元素增加错误项；时耗不加权，原时限保留。严格全对另报，退出0只表示评分程序完成。单独复核真实输出：

```bash
python sec-financial-report/verifier/score_accuracy.py --actual /path/to/answers.json --reference /tmp/sec-group01/tasks/sec-financial-report/verifier/expected_output.json --report /tmp/sec-group01-accuracy.json
```

修复仅用原任务和diagnosis，测试输入、参考、策展代码及分数均不回流修复/调参/选版。固定最终Skill、模型和执行预算后再测试；重复次数由正式实验协议确定。真实泛化结果按[提交说明](results/README.md)上传，任务包目前没有新增方法成绩。
