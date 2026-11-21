# 三组受控泛化测试

每组 `inputs/` 放该组原始 PDF，`verifier/expected_output.json` 放对应的逐区域标注。三组共用根目录题面、原 Skill 和评分代码。各组的论文数、页数和应遮字段数见[分组表](../README.md#训练与泛化测试)。

```bash
python paper-anonymizer/evaluation/prepare_task.py --split group_01 --output /tmp/paper-g1/tasks/paper-anonymizer
```

训练组可直接使用任务包根目录，或用 `--split train` 导出。冻结 Skill 后分别导出三个测试组，每组使用独立目录与 rollout ID。将导出的 `tasks/` 设为 BenchmarkExecutor 的 `tasks_root`。作答容器读取 `/root/paper*.pdf`，保存同名文件至 `/root/redacted/`。verifier 独立读取只读源文件和提交，运行 `bash /verifier/test.sh` 后在 `/logs/verifier/` 产生 `reward.txt`、`accuracy.json` 和逐项 `ctrf.json`。

本机复算可用 Python、PyMuPDF 1.27.2.2 和 NumPy 2.1.3，在导出目录下执行以下命令。

```bash
python verifier/score_accuracy.py --source-dir environment --actual /path/to/redacted --log-dir /tmp/paper-score
```
