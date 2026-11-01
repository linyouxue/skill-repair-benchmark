# GPT-5.2 SkillOpt 控制变量实验最终报告

## 结论

实验已于 2026-11-01 03:05:15 CST 完成。55/55 个预期执行单元均取得有效结果，无缺失、无重复有效结果。当前没有继续运行的 worker，也不需要继续消耗 API。

本实验的 22 个 SkillOpt 修复候选中：

| 指标 | 结果 |
|---|---:|
| 原生任务满分通过 | 11/22（50.0%） |
| 严格 Gold 语义完整修复 | 4/22（18.2%） |
| 语义部分修复 | 9/22（40.9%） |
| 语义未修复 | 9/22（40.9%） |
| 原生通过且语义完整修复 | 3/22（13.6%） |
| 留一实验中非目标 Gold 保持 | 12/12（100%） |

因此，11/22 不能解释为“SkillOpt 正确修好了 11 个”。其中 8 个虽然原生任务满分，但严格检查时目标修复语义仍不完整或错误；另有 1 个语义修对但原生任务失败。严格意义上，完整修对的是 4 个。

## 方法与隔离

- 实验目录：`gpt52-skillopt-controlled-location-single-r2l5-v2-20261027`
- 方法：`skillopt-controlled-oracle-hint-r2l5-v2`
- 修复模型：`openai/gpt-5.2`
- 原题执行：OpenHands + `ai360/openai/gpt-5.2`
- 配置：`R=2`、`L=5/file`、`N=3`、reasoning effort=`medium`
- 与旧版纯 SkillOpt GPT-5.2 以及 Opus 4.7 诊断目录、候选、轨迹和结果完全分离；只共享 benchmark/runner 基础运行代码。
- 隔离审计：通过；检查 22 个候选响应、573 个 repair trace JSON、83 个运行记录、82 个结果文件，0 条违规，0 个越界软链接。

## 三组 SkillOpt 修复结果

| 数据组 | 候选数 | 原生满分 | 完整语义修复 | 部分语义修复 |
|---|---:|---:|---:|---:|
| 给出修复位置 `location_hint` | 5 | 2（40%） | 0（0%） | 5 |
| 多故障一次修 `all_faults` | 5 | 0（0%） | 0（0%） | 3 |
| 单点留一修复 `leave_one_out` | 12 | 9（75%） | 4（33.3%） | 1 |

严格语义完整修复的 4 个候选是：

1. `single-manufacturing-equipment-maintenance-RI-001`：原生通过。
2. `single-video-silence-remover-RI-001`：原生通过。
3. `single-video-silence-remover-RI-002`：原生通过。
4. `single-sec-financial-report-RI-003`：语义修对，但原生失败。

这说明当前配置下，已知位置加 SkillOpt 仍然是 SkillOpt 的诊断—改写流程，但定位难度被控制掉了；结果显示单点留一明显比一次修多个故障更容易。不过这里只有单次执行，不能把 9/12 对 0/5 直接解释为稳定的因果提升。

## 四类控制组

| 控制条件 | 定义 | 满分通过 | 平均 reward |
|---|---|---:|---:|
| `full_gold` | 完整 Gold Skill 直接执行；用于确认当前模型、环境和检查器下 Gold 是否可通过 | 6/8 | 0.750 |
| `original` | 真正的原始 Skill，不含修复；用于检查历史缺陷是否仍出现 | 0/8 | 0.104 |
| `all_faults` | 所有标注修复点都撤回，但保留题目固定背景改动；是多故障修复的直接基线 | 1/5 | 0.200 |
| `condition_baseline` | 单点留一输入不做任何修复直接执行；是每个单点修复候选的配对基线 | 8/12 | 0.667 |

`original` 没有任何满分通过，但 `dialogue-parser` 得到 0.833 的部分分，所以 baseline 本身可以有部分 reward。`condition_baseline` 则有 8/12 满分，说明不少底层任务即使缺少目标修复仍会偶然或依靠执行模型通过；评估 Skill 修复时不能只看原生 pass。

`full_gold` 中 `data-to-d3` 和 `flink-query` 仍为 0。这表示在本次单次执行里，即使给执行模型完整 Gold Skill，底层 agent 仍没有通过检查器；它不是说 Gold Skill 文本错误，而是说明这两题的执行成功率受 agent 轨迹、环境或检查器约束影响，修复方法的结果必须结合 positive control 解读。

`all_faults` 控制只有 `manufacturing-equipment-maintenance` 通过。SkillOpt 的五个多故障修复候选反而是 0/5；这不是因为框架只允许两个 hint。当前配置允许每题提示多个 RI，失败来自模型没有同时恢复所有严格语义，例如 Flink 同时偏离 FINISH-only 与 qualifying-activity gate。

## 单点修复的配对变化

- SkillOpt 修复后：9/12 满分。
- 同一留一输入不修复：8/12 满分。
- 净满分数只增加 1 个，而且 9 个原生 pass 中只有 3 个同时满足完整 Gold 语义。
- 12/12 均保持了非目标 Gold 修复，说明隔离单点时没有在语义上破坏已经提供的其他修复点。

所以“单点修复”的含义是：输入已经包含其他 Gold 修复，只撤回一个 RI，让方法只补回这个点。它和之前完整 SkillOpt 的主要区别是控制了问题数量与定位难度，不再评价从原始 Skill 自主发现全部问题的能力。

## 运行稳定性与费用

- 55 个最终选中执行结果合计：26,727,222 prompt tokens、396,320 completion tokens。
- BenchFlow 记录的执行阶段费用合计约 52.3211 USD；这不含修复阶段未统一计价的调用，不能当成整个实验的完整账单。
- 运行中出现过 2 次 600 秒 API timeout/HTTP 500，均自动恢复，后续请求为 HTTP 200。
- 没有余额不足或 provider balance 错误。
- 审计保留了 28 个无效/未完成的历史尝试，但最终统计只选取 `bench_exit_code=0` 的 55 个有效结果。

## 结果文件

- `scorecard.csv`：22 个修复候选逐项原生 reward、语义判断与证据。
- `metrics-summary.json`：分组指标与四类控制组汇总。
- `semantic-review.json`：22 个候选的严格 Gold 语义人工核对。
- `result-audit.json`：55 个最终有效结果选择及无效尝试记录。
- `isolation-audit.json`：GPT-5.2/Opus 及目录隔离审计。
- `candidate-static-audit.json`：候选文件集合、目标文件范围和静态 Gold 片段审计。

