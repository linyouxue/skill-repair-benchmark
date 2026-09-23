# CausalFlow × SkillsBench

这个目录保存 CausalFlow 在 SkillsBench 上的执行、重放、因果归因、局部修复和人工 Skill 缺陷实验。当前研究主线只关注 SkillsBench。早期 MBPP、GSM8K、LiveCodeBench、DPO 和独立建图消融已经停止并从工作区移除。

## 当前结论

CausalFlow 能对 agent 轨迹中的命令进行干预，并在干净容器中重放完整下游流程。它对动作链附近的错误有一定定位能力。当前干预对象仍以命令为主，无法直接修改 Skill 文档或 Skill 脚本中的具体代码行。

人工缺陷试验目前构造了 10 个候选。`3d-scan-calc` 的体积放大错误通过完整门槛。原始 Skill 三次全部成功，缺陷 Skill 三次全部失败，恢复一行代码后重放两次全部成功。CausalFlow 测试六个完整下游分支后没有定位到缺陷代码行，也没有生成修复后的 Skill。

其余候选显示出三类常见情况。强模型会绕过错误路径或根据常识纠正文档错误；agent 自身波动可能形成 clean 通过、defect 失败的假象；复杂任务的单次运行成本差异很大。正式样本必须同时通过 clean 稳定性、分数下降、失败机制匹配和参考修复恢复四项检查。

## 目录结构

| 路径 | 内容 | 建议 |
| --- | --- | --- |
| `causal_flow.py`、`causal_attribution.py`、`counterfactual_repair.py` | CausalFlow 核心流程 | 修改算法时阅读 |
| `causal_graph.py`、`trace_logger.py`、`schemas.py` | 轨迹和因果图的数据结构 | 理解 CRS 输入时阅读 |
| `skillsbench_replay/` | SkillsBench 轨迹解析、文件快照和重放计划 | 当前主线核心代码 |
| `replay_graph/` | 保守依赖图和资源节点 | 当前重放基础设施 |
| `repro_wrappers/` | SkillsBench 执行、审计、人工缺陷和结果汇总入口 | 运行实验时使用 |
| `repro_wrappers/defective_skills/` | 缺陷清单、运行计划和失败机制复核 | 查看实验设计 |
| `repro_wrappers/defective_skill_bundles/` | 模型可见缺陷包和隐藏真值 | 不要手工修改 |
| `repro_wrappers/results/` | 机器可读结果 | 先看目录 README |
| `skill-repair-benchmark/` | 课题组共享执行器的本地固定版本 | 保留为独立 Git 仓库 |
| `external_baselines/` | MASA、SkillRL、AUSO 官方代码 | 用于方法适配研究；SkillTTA 位于同级目录 `../SkillTTA/` |
| `docs/` | 当前报告、技术说明、方法导读和项目历史 | 回顾项目从这里开始 |
| `tests/` | CausalFlow 与 SkillsBench 本地测试 | 修改代码后运行 |

## 推荐阅读顺序

1. [`docs/README.md`](docs/README.md) 说明每份文档的用途。
2. [`docs/current/DEFECTIVE_SKILL_REPORT.md`](docs/current/DEFECTIVE_SKILL_REPORT.md) 给出最新实验和 CausalFlow 表现。
3. [`docs/current/DEFECTIVE_SKILL_PROTOCOL.md`](docs/current/DEFECTIVE_SKILL_PROTOCOL.md) 说明样本构造、运行门槛和评分方式。
4. [`docs/current/SUBSET25_TASK_GUIDE.md`](docs/current/SUBSET25_TASK_GUIDE.md) 逐题解释统一子集中的任务和 Skills。
5. [`docs/current/SUBSET25_RESULTS.md`](docs/current/SUBSET25_RESULTS.md) 总结 25 题阶段的主要结果。
6. [`docs/technical/SKILLSBENCH_INTEGRATION.md`](docs/technical/SKILLSBENCH_INTEGRATION.md) 解释执行器、轨迹和重放如何连接。
7. [`docs/history/PROJECT_HISTORY.md`](docs/history/PROJECT_HISTORY.md) 回顾关键决定和被淘汰的实验方向。

## 环境

主要依赖包括 Python、Docker、OpenRouter 和本地 SkillsBench 仓库。默认路径为相邻目录 `../skillsbench`。共享执行器使用自己的虚拟环境。

```bash
uv venv --python 3.13 .venv
uv pip sync --python .venv/bin/python requirements.txt
uv pip install --python .venv/bin/python -e ./skill-repair-benchmark

cd skill-repair-benchmark
uv sync --extra dev --locked
cd ..
```

根目录环境用于 CausalFlow 和实验入口。共享执行器环境用于其自身测试。macOS 云盘可能把虚拟环境中的源码变成云端占位文件；若 Python 导入长期无响应，请重建环境，不要单独删除虚拟环境中的 `__pycache__`。

`.env` 中保存本地密钥，不能提交或复制到报告。当前任务模型固定为 `openrouter/openai/gpt-5.2`，最终评分使用 SkillsBench 官方 verifier。

## 常用命令

检查 OpenRouter 账户状态，不发送模型请求。

```bash
.venv/bin/python repro_wrappers/diagnose_openrouter.py --skip-chat
```

检查预注册缺陷包。

```bash
.venv/bin/python repro_wrappers/defects/construct_defective_skill_bundles.py \
  --manifest repro_wrappers/defective_skills/manifest_round2.json \
  --check
```

生成运行计划。去掉 `--execute` 时不会调用模型。

```bash
.venv/bin/python repro_wrappers/defects/run_defective_skill_matrix.py \
  --manifest repro_wrappers/defective_skills/manifest_round2.json \
  --jobs-root repro_wrappers/runs/<new-run-name> \
  --trials 1 \
  --variant mesh-logic-volume-inflation-v2
```

正式执行时增加 `--execute`，并使用新的 `--jobs-root`。程序会拒绝覆盖已有运行。

汇总 clean 与 defect 结果。

```bash
.venv/bin/python repro_wrappers/defects/summarize_defective_skill_matrix.py \
  --plan <run-plan.json> \
  --jobs-root <jobs-root> \
  --failure-review repro_wrappers/defective_skills/failure_mode_reviews_20260905.json \
  --output <summary.json>
```

运行本地测试。

```bash
.venv/bin/python -m unittest -v \
  tests.test_defective_skill_evaluation \
  tests.test_skillsbench_repair_targeting \
  tests.test_skillsbench_replay

skill-repair-benchmark/.venv/bin/pytest -q \
  skill-repair-benchmark/tests/agents/test_openhands_benchmark_adapter.py
```

## 对接课题组诊断与修复评估

`repro_wrappers/export_skill_evaluation_submission.py` 将逐任务 CausalFlow 结果和最终完整 Skill bundle 汇总为林同学评估器要求的 `submission.json`。复制 [`evaluation_submission_plan.template.json`](repro_wrappers/evaluation_submission_plan.template.json) 并填写各任务路径；任务集合必须与所选评估模板完全一致。计划中的一行如下：

```json
{
  "method_id": "causalflow-original-crs",
  "benchmark_version": "core25-gold-defects-20260909-v1",
  "tasks": [
    {
      "task_id": "dialogue-parser",
      "diagnosis_result": "path/to/causalflow-result.json",
      "final_bundle": "path/to/final-complete-skills",
      "executor_run_id": "dialogue-parser-final-r0"
    }
  ]
}
```

上例只展示一行；正式计划需填写模板中的全部 7 个任务。计划内相对路径从计划文件所在目录解析。`diagnosis_result` 可包含 `predictions`、`diagnoses` 或原版 CausalFlow 的完整结果；`final_bundle` 必须是方法最终提交的完整 Skill 目录，不能只给补丁文件。脚本把它复制到输出目录，生成相对路径。若原始 Skill 已通过，只能显式填写 `original_pass: true` 和 `original_run_id`，评估器仍会核验执行证据。

```bash
.venv/bin/python repro_wrappers/export_skill_evaluation_submission.py \
  --plan <method-plan.json> \
  --template skill-repair-benchmark-publish/evaluation/data/core25/submission.template.json \
  --output <new-submission-dir> \
  --evaluator-script skill-repair-benchmark-publish/evaluation/scripts/evaluate_skill_diagnosis_repair.py
```

默认只调用评估器的离线 `--dry-run`，在输出目录生成 `submission.json`、`conversion_report.json` 和 `evaluation-output/summary.json`，不产生分数或模型费用。正式评分时使用新的 `--output` 目录，并增加 `--evaluation-mode execute --judge-model openai/gpt-5.5 --omit-temperature --reasoning-effort medium`，同时按评估说明配置裁判密钥；有最终执行证据时再加 `--executor-runs-dir <method-jobs-dir>` 计算 Verified Fix Rate。也可直接把已生成的 `submission.json` 交给评估器手动执行，避免重复导出。使用 `original_pass` 跳过时，必须提供可核验的 Original rollout 目录。

原版 CausalFlow 的 CRS 只修改轨迹中的动作，不能把动作级因果步骤自动记作 Skill 文件级诊断或修复。此时导出 `diagnoses: []` 和未改动的最终 Skill，并在 `conversion_report.json` 中标出限制。当前公开 Gold 只覆盖 Core-25 的 7 个任务、14 个缺陷；`3d-scan-calc` 等错误注入案例不属于这个 Gold，不能混用评分。最新版评估脚本报告 Diagnosis/Repair P/R/F1、Location Accuracy、Regression 和实际运行的 Verified Fix Rate；Repair 使用逐缺陷正确性判定，没有文本相似度指标。

## 实验规则

- 固定 SkillsBench commit、共享执行器版本、模型、任务 Skill 和官方 verifier。
- 在运行前登记缺陷位置、替换内容、预期失败方式和最小参考修复。
- clean 失败时停止该候选，不继续消耗 defect 预算。
- 分数下降后检查轨迹和官方失败项。失败机制不匹配的候选进入拒绝台账。
- 正式结果保存完整轨迹、Skill 快照、token、费用、实际用时和 verifier 输出。
- 原始 CausalFlow 与扩展方法分开命名，避免把新增能力计入原版 CRS。

## 当前版本锚点

- SkillsBench commit `9a1f4dd5f7659f75707435da3ce854b6e48321d1`
- 共享执行器基础 commit `b88b4b9482d08ad91d01058ecade523d753c086f`
- 本地 OpenHands 适配器 SHA-256 `e8b4b1663e2055bafa294e23c5e08ba2cc6fc6913ec012f07e9ec693df961ed3`
- 任务模型 `openrouter/openai/gpt-5.2`
- 协议 `skillrepair-v1`

清理和文件来源记录见 [`docs/technical/CODE_PROVENANCE.md`](docs/technical/CODE_PROVENANCE.md)。
