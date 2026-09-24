# SkillsBench 25 题统一评估流程 v1.1

冻结日期：2026-08-25  
任务集名称：`skillsbench-cf25-v1`  
适用范围：组内各 baseline、诊断方法和修复方法的初步对比

## 1. 固定任务集

以下 25 题按编号固定。运行失败、环境报错或得分过低都不能临时换题。

1. `software-dependency-audit`
2. `suricata-custom-exfil`
3. `fix-erlang-ssh-cve`
4. `xlsx-recover-data`
5. `invoice-fraud-detection`
6. `sec-financial-report`
7. `weighted-gdp-calc`
8. `manufacturing-codebook-normalization`
9. `3d-scan-calc`
10. `r2r-mpc-control`
11. `lean4-proof`
12. `pddl-tpp-planning`
13. `paratransit-routing`
14. `threejs-to-obj`
15. `mario-coin-counting`
16. `video-silence-remover`
17. `exoplanet-detection-period`
18. `crystallographic-wyckoff-position-analysis`
19. `glm-lake-mendota`
20. `court-form-filling`
21. `pptx-reference-formatting`
22. `sales-pivot-analysis`
23. `dialogue-parser`
24. `python-scala-translation`
25. `fix-visual-stability`

## 2. 冻结配置

| 项目 | 统一设置 |
| --- | --- |
| SkillsBench | commit `9a1f4dd5f7659f75707435da3ce854b6e48321d1` |
| BenchFlow | `0.6.3` |
| 模型 | OpenRouter 请求标识 `openai/gpt-5.2`；保存服务端返回的模型元数据 |
| 推理强度 | 使用模型默认值；请求中不发送额外 reasoning 参数，结果记录为 `null/default` |
| 服务商 | OpenRouter；主表禁止混入 OpenAI 直连结果 |
| Skills 条件 | `with_skills`，只部署任务自带 curated Skills |
| 任务提示 | 原始 `task.md`，不追加题目提示或人工诊断 |
| 环境 | 官方 Dockerfile，每条运行从干净容器开始；agent 命令以非 root `agent` 身份执行，官方 verifier 以 `root` 身份执行 |
| 外部资料 | 禁止网页搜索和额外资料检索；任务规定的网络访问除外 |
| 初始运行预算 | 最多 24 个 agent/tool 轮次，每次模型输出上限 2,048 token；墙钟使用任务官方上限 |
| 方法阶段预算 | 最多 24 次诊断或干预模型调用，单次输出上限 2,048 token；CausalFlow 对每个历史步骤最多提一个候选；任务级墙钟上限 14,400 秒 |
| verifier 查询 | 方法阶段最多 32 次；最终评测另计 1 次 |
| pilot 重复数 | 明早先交 R0；正式实验补 R1、R2 |

所有调用大模型的环节都使用同一个 GPT-5.2 配置，包括原始 agent、诊断、干预提议和修复候选生成。纯程序步骤不产生模型限制。模型不保证完全确定，R0、R1、R2称为独立重复。

正式启动前，全组先用 `dialogue-parser` 做一次不计分预检，核对模型返回名、工具调用、Skill 注入、Docker、token 计量和官方 verifier。只要一名同学无法调用固定快照，就应在查看 25 题结果前统一修改服务商和模型标识。修改后所有人使用完全相同的配置，已经产生的主表结果重新运行。禁止在主表中静默混用快照、浮动别名或自动回退模型。

## 3. 两条对比赛道

### 3.1 共享轨迹赛道，作为主比较

负责人统一生成并冻结每题的 R0 原始轨迹。每种方法接收相同的任务、Skills、轨迹、起始工作区、镜像和 baseline reward，再做诊断与修复。该赛道控制了初始 agent 随机性，能够比较算法本身的定位能力、修复能力和资源开销。

原始轨迹已经满分时，方法应输出 no-op。破坏成功轨迹计入回归率。严格重放不合格的轨迹先重新生成，不能交给方法比较。

### 3.2 端到端赛道，作为扩展比较

每种方法从干净容器自行生成轨迹，再完成诊断与修复。它反映完整系统效果，也会混入 agent 外壳、提示模板和工具封装差异。端到端结果单独成表，不能和共享轨迹赛道放在同一列排名。

## 4. 单题标准流程

1. 核对仓库 commit、BenchFlow、任务文件哈希、Skill 哈希和 Docker 镜像 digest。
2. 用固定 GPT-5.2 配置生成原始轨迹，保存全部消息、工具调用、返回码、文件读写和 token 用量。
3. 调用官方 verifier，记录 `baseline_reward`、分项计数和最终文件哈希。
4. 在全新容器完整重放原始命令。重放必须沿用原始身份边界，由非 root `agent` 执行轨迹命令，再由 `root` 单独运行官方 verifier。命令数、已记录返回码、reward、官方分项和产物哈希必须一致。无法复现时记为 `replay_invalid`，不进入算法得分。
5. 对有效失败轨迹运行待评方法。每个候选必须保留完整前缀和完整下游语义；局部图切片结果只能放在消融表。
6. 方法停止后，在全新 verifier 进程评估最终产物，记录 `final_reward`。
7. 保存诊断阶段与修复阶段各自的 token、费用、墙钟时间、模型调用数和 verifier 查询数。
8. 基础设施错误允许同配置重试一次。第二次仍失败则记为 invalid；模型超时、预算耗尽和错误答案计入方法失败。

诊断和修复模型不能查看 verifier 源码、标准答案、oracle 或隐藏断言。方法阶段只接收 scalar reward 和是否完全通过。编译器、求解器和程序自身公开产生的 stderr 可以作为过程反馈，但必须在 method card 中说明。

## 5. 必交结果字段

每条结果至少包含以下字段：

```json
{
  "method": "method-name",
  "track": "shared-trajectory",
  "task_set": "skillsbench-cf25-v1",
  "task_id": "dialogue-parser",
  "replicate": "R0",
  "model_requested": "openai/gpt-5.2",
  "model_returned": "openai/gpt-5.2",
  "provider": "openrouter",
  "baseline_reward": 0.0,
  "final_reward": 1.0,
  "pass": true,
  "diagnosis_input_tokens": 0,
  "diagnosis_output_tokens": 0,
  "diagnosis_cost_usd": 0.0,
  "diagnosis_wall_seconds": 0.0,
  "repair_input_tokens": 0,
  "repair_output_tokens": 0,
  "repair_cost_usd": 0.0,
  "repair_wall_seconds": 0.0,
  "verifier_queries": 0,
  "replay_ratio": 1.0,
  "agent_identity": "agent",
  "verifier_identity": "root",
  "identity_matches": true,
  "failure_type": null,
  "artifact_hashes": {}
}
```

同时提交完整轨迹、运行配置、最终产物和日志。token 必须分开记录普通输入、缓存输入、输出和 reasoning token；费用优先保存服务商实际返回值。

## 6. 统一指标

组会主表只报告以下指标：

1. 原始 `pass@1` 和最终 `pass@1`，满分定义为官方 `reward == 1`。
2. 平均 reward 与平均提升 `final_reward - baseline_reward`。
3. 基线失败条件下的修复成功率。
4. 基线成功条件下的回归率。
5. 每题 win / tie / loss。
6. 诊断和修复各自的 token、美元、墙钟时间与 verifier 查询数。
7. 严格重放比例和重放无效率。
8. 失败类型分布。

25 题只支持初步结论。展示比例时必须同时给原始计数，例如 `3/12`，避免只报告百分数。正式三次重复完成后再计算任务级配对 bootstrap 置信区间。

## 7. 统一失败类型

- `localization_error`：没有找到真正影响 reward 的步骤或依赖。
- `repair_semantic_error`：定位基本正确，修复内容在语义上错误。
- `artifact_missing_or_invalid`：必需文件缺失、格式错误或内容不完整。
- `global_optimization_failure`：局部操作有效，整体约束或目标仍未满足。
- `replay_invalid`：严格重放无法复现，不进入算法得分。
- `budget_or_timeout`：方法耗尽统一预算。
- `infrastructure_error`：镜像、网络、API 或 verifier 故障，不进入算法得分。
- `method_no_effect`：方法完成运行，reward 没有变化，且无法归入更具体类型。

## 8. 费用估算

GPT-5.2 当前公开价格为每百万 token 1.75 美元普通输入、0.175 美元缓存输入和 14 美元输出。费用公式如下。

```text
cost = (input - cached_input) × 1.75e-6
     + cached_input × 0.175e-6
     + output × 14e-6
```

当前 15 个通过严格门禁的 R0 基线合计约 2.25 美元，平均 0.150 美元/题。11 条有效失败轨迹的完整 CausalFlow CRS 合计约 3.45 美元，平均 0.314 美元/条。按当前成功率和实测均值外推，25 题一次“基线 + 失败侧 CRS”的模型费用约 10 美元；考虑网络重试、超时和超长轨迹，建议每种方法的 25 题 R0 准备 15–20 美元。正式三次重复建议准备 45–60 美元，并保存实际账单值。
