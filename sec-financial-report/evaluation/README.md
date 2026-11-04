# 冻结Skill后的三批同源评测

三批来自SEC同一Form 13F发布渠道，沿用原题的四问模板和原helper实际股票筛选口径。每批20个案例、200个答案项；同一批作为一次完整任务输入，不能把200项当作200次独立模型实验。

| 批次 | 基准期→当前期 | 案例 | 答案项 |
|---|---|---:|---:|
| group_01 | 2024-Q1→2024-Q2 | 20 | 200 |
| group_02 | 2024-Q3→2024-Q4 | 20 | 200 |
| group_03 | 2025-Q4→2026-Q1 | 20 | 200 |

各批的inputs/queries.json列出案例ID和目标经理/证券；inputs/data包含四张原始表选中行的gzip文件；metadata.json记录来源、筛选条件和行数；verifier/reference_answers.json仅在评分侧使用。详细策展规则、排除原题与批间目标重复、并列排除及已知局限见[任务根说明](../README.md)与[manifest](manifest.json)。

## 导出和执行

从仓库根运行，输出目录必须不存在，末级目录名保持task ID：

```bash
python sec-financial-report/evaluation/prepare_task.py --group group_01 --output /tmp/sec-group01/tasks/sec-financial-report
```

将现有BenchmarkExecutor的tasks_root指向 `/tmp/sec-group01/tasks`，仍调用 `run(task_id="sec-financial-report", condition="method-skill", skill_bundle=完整冻结bundle, ...)`。同样支持group_02/03，不改方法adapter和公共API。每次使用新的rollout_id和全新任务工作区。

导出保留原Skill，只部署选中批次的输入和参数化四问题面；不带diagnosis、oracle、其他批次或策展代码。verifier位于单独目录，Agent退出后才部署。实际输出为 `/root/answers.json`，顶层是20个case_id，各值保留原题四键结构。

评分保持每例10项：金额、持仓行数、五个有序CUSIP、三个有序经理名。缺失与错值记错，多余排名元素/未知case_id增加错误项；时耗不加权，原时限保留。严格全对另报，退出0只表示评分程序完成。单独复核真实输出：

```bash
python sec-financial-report/verifier/score_accuracy.py --actual /path/to/answers.json --reference sec-financial-report/evaluation/group_01/verifier/reference_answers.json --report /tmp/sec-group01-accuracy.json
```

修复仅用原任务和diagnosis，测试输入、参考、策展代码及分数均不回流修复/调参/选版。固定最终Skill、模型和执行预算后再测试；重复次数由正式实验协议确定。真实泛化结果按[提交说明](results/README.md)上传，任务包目前没有新增方法成绩。
