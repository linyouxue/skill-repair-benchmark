# SkillsBench 实验入口

这个目录只保留当前 SkillsBench 主线所需的执行、重放、归因、修复、审计和人工缺陷工具。文件按使用阶段阅读。

## 1. 任务执行

| 文件 | 作用 |
| --- | --- |
| `run_unified_skillsbench_task.py` | 调用课题组共享执行器，固定 GPT-5.2、完整 Skill、超时和官方 verifier |
| `prebuild_skillsbench_task.py` | 预构建原始任务镜像，减少重复安装造成的网络波动 |
| `diagnose_openrouter.py` | 安全检查 OpenRouter 密钥、余额和最小请求，不打印密钥 |
| `skillsbench_deployed_skills.py` | 从运行快照解析模型实际看到的 Skill bundle |

`run_skillsbench_openrouter_task.py` 和 `run_skillsbench_openrouter_smoke.py` 属于早期轻量执行适配。部分重放辅助代码仍使用其中的代理和资源记录函数。新正式任务优先使用统一执行器。

## 2. 人工 Skill 缺陷

| 文件 | 作用 |
| --- | --- |
| `defects/construct_defective_skill_bundles.py` | 按 manifest 构造缺陷包，并检查变更范围和文件哈希 |
| `defects/run_defective_skill_matrix.py` | 生成固定顺序的 clean/defect 计划，按要求执行 |
| `defects/summarize_defective_skill_matrix.py` | 汇总 reward、token、费用和失败机制复核状态 |
| `defects/build_skill_repair_cases.py` | 把通过门槛的失败轨迹打包成不泄露真值的公共 case，并单独生成私有评分索引 |
| `defects/merge_skill_repair_case_sets.py` | 校验并合并多个独立轮次的公共 case 与私有索引 |
| `defects/evaluate_skill_repair_submission.py` | 预检方法输出，使用统一执行器复跑完整修复 bundle，并自动计算定位与恢复指标 |
| `defects/score_defective_skill_evaluation.py` | 计算 Skill、文件、行号、类型和修复恢复指标 |
| `defects/validate_reference_skill_repair.py` | 只恢复预登记位置，然后重放同一轨迹 |
| `defects/run_direct_skill_review_baseline.py` | 一次性 verifier-blind GPT Skill 审查对照 |
| `defects/export_direct_skill_review_diagnosis.py` | 把一次性审查结果转换成统一 diagnosis contract |

实验数据目录包括 `defective_skills/`、`defective_skill_bundles/` 和以 `defective_skill_jobs_` 开头的运行目录。详细说明见 [`defective_skills/README.md`](defective_skills/README.md)。

当前通过完整门槛、可直接交给方法侧的合并盲测集合位于 [`skill_repair_suite_v1/registry.json`](skill_repair_suite_v1/registry.json)，包含 2 个 opaque case。私有评分映射位于 `defective_skills/skill_repair_suite_v1.private.json`，不得复制到方法输入目录。

## 3. CausalFlow 与重放

| 文件 | 作用 |
| --- | --- |
| `audit_shared_executor_replay.py` | 在新容器中严格重放共享执行器轨迹，核对 reward、返回码和文件内容 |
| `run_skillsbench_full_causalflow.py` | 执行完整轨迹 CRS、候选修复和官方评分 |
| `run_skillsbench_causalflow_repair.py` | 提供单条命令替换和 Docker 分支执行底层函数 |
| `export_skill_evaluation_submission.py` | 汇总诊断和完整 Final Skill，输出林同学评估器兼容的 `submission.json`，可直接调用其脚本 |

## 4. 阶段性工具

- `subset25/` 保存固定 25 题阶段的统计、审计和报告复核程序。
- `archive/` 保存一次性诊断与早期对照脚本。它们不进入当前正式实验。
- `run_skillsbench_openrouter_task.py` 和 `run_skillsbench_openrouter_smoke.py` 仍留在顶层，因为当前重放代码还会导入其中的代理、网络和资源辅助函数。后续若抽离这些公共函数，再将两个旧入口整体归档。

## 5. 当前最短工作流

```bash
# 1. 检查缺陷包
.venv/bin/python repro_wrappers/defects/construct_defective_skill_bundles.py \
  --manifest repro_wrappers/defective_skills/manifest_round2.json \
  --check

# 2. 生成计划
.venv/bin/python repro_wrappers/defects/run_defective_skill_matrix.py \
  --manifest repro_wrappers/defective_skills/manifest_round2.json \
  --jobs-root repro_wrappers/runs/<new-name> \
  --trials 1 \
  --variant mesh-logic-volume-inflation-v2

# 3. 人工核对计划后，使用同一命令并增加 --execute

# 4. 汇总结果
.venv/bin/python repro_wrappers/defects/summarize_defective_skill_matrix.py \
  --plan <plan.json> \
  --jobs-root <jobs-root> \
  --failure-review repro_wrappers/defective_skills/failure_mode_reviews_20260905.json \
  --output <summary.json>

# 5. 只把 status=effective 的样本导出给各方法；private registry 必须放在公共目录外
skill-repair-benchmark/.venv/bin/python \
  repro_wrappers/defects/build_skill_repair_cases.py \
  --manifest <manifest.json> \
  --plan <plan.json> \
  --summary <summary.json> \
  --jobs-root <clean-and-defect-jobs-root> \
  --public-root <public-cases-dir> \
  --private-registry <private-scoring-dir>/registry.json

# 6. 方法提交 diagnosis.json 和完整 repaired bundle；默认命令只做免费预检
skill-repair-benchmark/.venv/bin/python \
  repro_wrappers/defects/evaluate_skill_repair_submission.py \
  --case <public-cases-dir>/cases/<case-id> \
  --private-registry <private-scoring-dir>/registry.json \
  --diagnosis <method-output>/diagnosis.json \
  --repaired-bundle <method-output>/full-skills \
  --method-id <method-name>

# 人工核对预检结果后增加以下参数，才会产生付费 repair rollout
# --execute --tasks-root /path/to/skillsbench/tasks --jobs-root <repair-jobs-root>

# repaired bundle 必须是方法输出的独立目录；即使内容恰好恢复为原始字节，
# 也不能直接把路径指向 <skillsbench>/tasks/<task>/environment/skills。
```

完整实验规则见 [`../docs/current/DEFECTIVE_SKILL_PROTOCOL.md`](../docs/current/DEFECTIVE_SKILL_PROTOCOL.md)。机器结果导航见 [`results/README.md`](results/README.md)。
