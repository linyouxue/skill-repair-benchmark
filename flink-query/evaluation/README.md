# 三组受控泛化测试

冻结 Skill 后分别导出 `scale`、`stages`、`combined`。三组依次增加作业规模、增加双阶段作业、同时改变两项。各组目录提供独立冻结输入和评分侧数据。题面、Java 骨架、原 Skill、Docker 环境和评分程序复用修复组。

```bash
python flink-query/evaluation/prepare_task.py --split scale --output /tmp/flink-scale/tasks/flink-query
```

在仓库根目录执行。导出路径须是新目录，将其父目录传给 BenchmarkExecutor 的 `tasks_root`。用 `--split repair` 同样可导出修复组。任务 ID 为 `flink-query`，四组均使用题面约定的输入和输出路径。评分端执行 `bash /verifier/test.sh`，从 `/logs/verifier/` 读取 `reward.txt`、`accuracy.json` 和 `stage_feedback.json`。

[各方法成绩和逐次索引](results/README.md)
