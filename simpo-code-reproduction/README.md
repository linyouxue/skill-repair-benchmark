# SimPO 损失函数复现与泛化评测

修复阶段使用 SkillsBench 原题、两份原 Skill、原张量和 GPT-5.2 原始失败轨迹。选定并冻结完整 Skill 后，再用三批新张量进行泛化评测。

| 材料 | 位置 |
|---|---|
| 原题及执行配置 | [task.md](task.md) |
| 原环境、代码、论文、测试脚本和输入 | [environment/](environment/) |
| 原 Skill | [完整 bundle](environment/skills/) |
| 完整失败轨迹 | [ACP](https://github.com/linyouxue/skill-repair-benchmark/blob/bee9b0df5b04a300735e5009f5238f5d5c8aaf61/evaluation/results/GPT52-AllTasks-RepresentativeRuns-20260916/tasks/simpo-code-reproduction/selected_run/trajectory/acp_trajectory.jsonl)、[LLM 请求和响应](https://github.com/linyouxue/skill-repair-benchmark/blob/bee9b0df5b04a300735e5009f5238f5d5c8aaf61/evaluation/results/GPT52-AllTasks-RepresentativeRuns-20260916/tasks/simpo-code-reproduction/selected_run/trajectory/llm_trajectory.jsonl)、[ATIF](https://github.com/linyouxue/skill-repair-benchmark/blob/bee9b0df5b04a300735e5009f5238f5d5c8aaf61/evaluation/results/GPT52-AllTasks-RepresentativeRuns-20260916/tasks/simpo-code-reproduction/selected_run/trainer/atif.json) |
| 反馈和产物状态 | [允许反馈](diagnosis/outputs/allowed_feedback.json)、[产物清单](diagnosis/outputs/output_inventory.json)、[来源索引](diagnosis/index.json) |

指定历史运行得到官方 reward 0。它记录的 Python 是 3.12.3，官方评分要求 3.10，运行在数值比较前就失败了。原产物未归档，历史逐项正确率为空。

## 接入和评分

修复侧与 Flink 使用同一方法 adapter，读取原 Task、完整 Skill、完整轨迹和允许反馈。执行侧使用现有 `BenchmarkExecutor.run(task_id="simpo-code-reproduction", ...)`。将 `tasks_root` 指向包含本任务目录的父目录。每次运行使用新的 `rollout_id`。

```bash
python simpo-code-reproduction/evaluation/prepare_task.py --group group_01 --output /tmp/simpo-g01/tasks/simpo-code-reproduction
python simpo-code-reproduction/evaluation/score_results.py --group group_01 --actual /path/to/loss.npz --report /tmp/simpo-g01-accuracy.json
```

导出只替换 Agent 环境里的两个 `.pt` 输入文件。参考答案随评分包在 Agent 退出后部署。`verifier/verifier.md` 使用统一执行器的脚本策略，从 `/verifier` 启动原 `test.sh`。原脚本因此可以分别读取评分侧的 `/verifier/loss.npz` 和 Agent 的 `/root/loss.npz`。

逐项正确率单独计算。读取实际输出中形状为 `(100,)` 的 `losses` 向量，按原 verifier 的浮点容差逐位置比较。每项 1 个百分点。缺失、不可读或结构错误的输出计 0 分，NaN 或无穷值所在位置计错。`--group original` 可按同一规则评估原任务。

## 数据与复核

三组各有 100 对 float32 的 chosen/rejected 平均对数概率。根据原张量的均值和标准差固定采样参数，用三个独立种子产生新张量，记录见 [manifest](evaluation/manifest.json)。这是同任务契约下构造的张量测试集。

参考答案用 NumPy 计算，再用 Python Decimal 的 50 位精度逐项复核。复核命令需要 NumPy 和 PyTorch。

```bash
python simpo-code-reproduction/tools/build_groups.py
```

原题固定 SkillsBench `b63b7b2850226b6aa4fb5929a8c1ac7bc4d9a6af`。原题、原输入、测试脚本、原 verifier 源码和原 GT 均沿用该版本。原 oracle 和各组 GT 只供组织者复核与评分。
