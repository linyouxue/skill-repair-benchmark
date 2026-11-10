# 三组受控泛化测试

冻结 Skill 后分别导出 `group_01`、`group_02` 和 `group_03`。三组分别只换国家、只换年份、同时换国家和年份。每个导出任务包含当组题面、两份 Excel 输入、原 Skill 和隔离的评分侧参考值。

```bash
python reserves-at-risk-calc/evaluation/prepare_task.py --split group_01 --output /tmp/rar-g1/tasks/reserves-at-risk-calc
```

执行侧将 `tasks_root` 设为该次导出的 `tasks` 目录，继续使用相同的任务 ID、方法 adapter 和 BenchmarkExecutor API。每组使用独立的工作目录和 rollout ID。输出路径为 `/root/output/rar_result.xlsx`。

训练可以直接使用任务包根目录，也可以用 `--split train` 隔离导出。四组均使用同一个 43 项 scorer。需要免费重放评分时，把真实 Excel 放到容器输出路径，评分端运行 `bash /verifier/test.sh`，读取 `/logs/verifier/accuracy.json`、`ctrf.json` 和 `reward.txt`。
