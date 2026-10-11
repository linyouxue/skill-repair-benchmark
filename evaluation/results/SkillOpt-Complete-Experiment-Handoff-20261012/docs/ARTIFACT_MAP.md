# Artifact map

下列路径均相对于本实验包根目录。

| 需要的数据 | 路径 | 说明 |
|---|---|---|
| 原始失败轨迹 | `runs/<run>/jobs/baseline-original-skill/<rollout>/` | 包含 trajectory、agent、trainer、verifier、result、config 和 request。 |
| 优化器本轮证据 | `runs/<run>/methods/skillopt/<task>/workspace/round_<n>/evidence_bundle.json` | 记录本轮累计的 baseline/前序失败 gate 输入来源。 |
| 独立诊断样本 | `.../round_<n>/diagnosis_samples/sample_*.json` | 仅在已启用逐样本留存的 54 个轮次存在，共 162 份。 |
| 合并诊断 | `.../round_<n>/diagnosis.json` | SkillOpt 用于 rewrite 的合并诊断。 |
| 诊断原始响应摘要 | `.../round_<n>/diagnosis_raw.json` | 模型输出前缀、usage、duration、解析状态和 shared 来源。 |
| 增删改提案及应用结果 | `.../round_<n>/rewrite_raw/*.json` 与 `optimization_manifest.json` | 包含 proposed edits、update mode、edit reports、applied count、change summary 与 usage。 |
| 被验证的候选 Skill 包 | `runs/<run>/jobs/skillopt/<rollout>/inputs/skills/` | 是该 gate rollout 实际挂载的完整候选包。 |
| 候选执行 | `runs/<run>/jobs/skillopt/<rollout>/` | 包含完整执行轨迹、请求、配置、计时、usage 和输出。 |
| 验证结果 | `.../round_<n>/gate_result.json` 及对应 `jobs/.../verifier/` | 记录 comparable、pass、reward、错误类型和 verifier 输出。 |
| 接受/拒绝理由 | `.../workspace/repair_loop.json` | `rounds[].decision`、reason、rejected buffer 和 failure evidence size。 |
| 被拒提案详情 | `repair_loop.json` 的 `rejected_buffer` | 保存拒绝原因、提案、edit reports 和摘要。 |
| 跨轮反馈 | `repair_loop.json` 的 `failure_evidence`、`rejected_buffer` | 下一轮同时读取前序失败和被拒提案，避免重复。 |
| 初始/当前/最终 Skill | `before_skill/`、`after_skill/`、`best_skill/` | `best_skill` 是 gate 选择后的最终版本；`diff.patch` 是最终差异。 |
| 最终选择映射 | `method_result.json`、`rollout_pointer.json` | 指向最终被选 rollout；若所有候选被 revert，可能回退到 baseline。 |
| 标准 submission | `submissions/outputs/<track>/submission.json` | 两个 benchmark version 必须分开评分。 |
| 健康状态 | `submissions/outputs/<track>/run_status.json` | evaluator schema 外的严格健康、可比性、错误和 bundle 来源。 |
| 运行命令 | `runs/<run>/commands/` | 真实 worker、rerun 和环境配置脚本。 |
| 终端和无效尝试 | `runs/<run>/logs/` | 包括重跑、超时、Docker/依赖错误；已删除临时目录只剩这些日志。 |
| 自动映射索引 | `metadata/TASK_ROUND_INDEX.json` | 推荐分析入口，可将每个候选与执行、验证和选择对应起来。 |

`TASK_ROUND_INDEX.json` 中每一轮的 `candidate_skill_bundle`、`candidate_job`、
`gate_result`、`decision` 和 `rejected_proposals` 构成一条可机器读取的对应链。

