# 测试导航

当前测试分为三组。

- `test_defective_skill_evaluation.py` 检查缺陷构造、运行矩阵、费用恢复和统一评分。
- `test_skillsbench_replay.py`、`test_replay_graph.py` 检查轨迹解析、文件依赖和重放计划。
- `test_skillsbench_repair_targeting.py`、`test_causal_attribution_sampling.py` 检查 CRS 分支和修复目标。

其余测试覆盖模型调用限制、文本解析、轨迹完整性和结果审计。共享执行器的适配测试位于 `skill-repair-benchmark/tests/agents/`。

```bash
python3 -m unittest discover -s tests -v
skill-repair-benchmark/.venv/bin/pytest -q \
  skill-repair-benchmark/tests/agents/test_openhands_benchmark_adapter.py
```
