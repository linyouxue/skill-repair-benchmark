# Replay-safe dependency graph：第一版实现与实验

> 更新：2026-08-10  
> 当前范围：GSM8K 确定性 calculator 重放，以及 SkillsBench 的文件流与技能决策图。

## 1. 解决什么问题

CausalFlow 修改一个步骤后，通常沿顺序链重新执行全部后续步骤。这里新增的 `replay_graph/` 将步骤输出表示成带生产者身份的资源版本，并用依赖图选择需要重放的计算步骤。

第一版遵守两个安全原则：

1. 两个步骤即使都输出 `8`，也对应不同资源，不能仅因数值相同而合并。
2. 如果旧轨迹无法判断某个 `8` 来自哪个步骤，重放器返回 `fallback-required`，不猜“最近来源”。

## 2. 代码结构

| 文件 | 用途 |
| --- | --- |
| `replay_graph/schema.py` | 定义 step/decision/resource/verifier 节点、版本化资源、must/may 边、绑定和重放结果。 |
| `replay_graph/builder.py` | 构建保守依赖图；保留所有同值候选生产者。 |
| `replay_graph/oracle.py` | 从干预点开始执行全部后续 calculator call，作为固定计划下的 full-tail oracle。 |
| `replay_graph/scheduler.py` | 按图后代局部重放，支持 change pruning、完整重放校准和不一致回退。 |
| `tests/test_replay_graph.py` | 重复值、歧义回退、完整/局部一致、change pruning 和安全函数测试。 |
| `repro_wrappers/replay_graph_benchmark.py` | 对 MongoDB 中已有 GSM8K 成功轨迹注入 `+13` 错误并比较两种重放。 |

`trace_logger.Step` 新增 `resource_reads` 和 `resource_writes`。新记录的 tool response 会自动获得类似下面的资源标识：

```text
resource:step:5:tool_output:v1
```

GSM8K 的结构化解答现在还要求每个计算步骤返回 `depends_on_steps`，并用 `final_answer_from_step` 指明最终答案来源。新采集轨迹会把这些引用转换成 `resource_reads`；旧 MongoDB 轨迹没有这些字段，因此仍只能使用推断绑定。

## 3. 当前重放语义

图中用于调度的主要路径是：

```text
tool_call → tool_response → ResourceVersion → downstream tool_call/final_answer
```

- tool call 与 response、response 与资源之间是 observed/must 边；
- 明确记录的 `resource_reads` 是 must 边；
- 旧轨迹中通过相同数值推测出的来源是 inferred/may 边；
- 多个候选生产者都输出相同数值时，不提前消歧；
- 下游计算结果未变化时，change pruning 停止传播；
- 局部结果与完整结果不同则返回完整结果，并记录 fallback 原因。

当前 oracle 固定原有计算计划，只重新执行确定性 calculator；它还不是“重新调用 LLM 继续决策”的通用 agent oracle。

SkillsBench 的第二阶段原型补充了另一类路径：

```text
skill 文件 → LLM decision → 生成命令 → 文件版本 → verifier
```

其中 skill 到 decision 是软语义边，可由双模型一致判断提出，或由技能消融提供干预证据；decision 到命令是轨迹中已发生的生成关系。当前执行器尚不能恢复 LLM decision，因此切片遇到这类节点会安全回退，不能把结构缩减误报成实际加速。实现见 `skillsbench_replay/semantic.py`，TicToc 结果见 `repro_wrappers/results/tictoc_hybrid_graph_with_intervention.json`。

## 4. 测试和运行

```bash
python -m unittest -v tests.test_replay_graph
python repro_wrappers/replay_graph_benchmark.py --max-traces 40
```

实验结果保存到：

```text
repro_wrappers/results/replay_graph_gsm8k_result.json
```

## 5. 2026-08-05 小规模结果

数据来自本地最新 GSM8K 成功运行；对可直接求值的 calculator call 注入 `+13`。

| 指标 | 结果 |
| --- | ---: |
| 涉及轨迹 | 33 |
| 干预次数 | 124 |
| full oracle 可完成 | 104 / 124 = 83.9% |
| 局部/完整可比次数 | 104 |
| 局部与完整一致 | 104 / 104 = 100% |
| 原始不一致 | 0 |
| 平均减少 calculator 重放 | 10.1% |
| 因歧义要求安全回退 | 20 |

20 次回退来自旧轨迹没有保存显式生产者身份。104 次可比实验也仍使用了推断绑定，因此这组结果是工程基线，不能直接作为论文主实验。

随后使用 `google/gemini-2.5-flash-lite` 采集了 1 条新格式冒烟轨迹：答案正确，记录到 2 个 observed 资源绑定；对首个计算步骤注入 `+13` 后，局部与完整重放均完成且结果一致。产物为 `repro_wrappers/results/replay_graph_explicit_trace_smoke.json`。

## 6. 当前结论与下一步

第一版已经证明：资源身份、歧义拒绝、完整重放、局部调度和 change pruning 可以形成一条可运行管线，且没有再出现同值跨分支污染。

但平均调用缩减只有 10.1%，低于计划中的 30% 目标。下一步应提高依赖识别精度，并保留安全回退：

1. 用已加入 GSM8K agent 的 `depends_on_steps → resource_reads` 记录重新采集轨迹；其他 agent 仍需在 tool wrapper 层补同类记录；
2. 将 20 个歧义样本作为优先回归集，验证显式身份能否消除回退；
3. 在不降低 100% 一致率的前提下重新测量调用、时间和 token；
4. 再接 MBPP 的文件、测试和副作用资源。
