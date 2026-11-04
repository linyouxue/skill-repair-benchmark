# WML / Claude Opus 4.7 — group_02 泛化评测

本目录提交同一冻结 Skill 在 JPG OCR `group_02` 上的三次独立运行。每次均保留实际生成的 Excel、完整 ACP/LLM 轨迹、原始 verifier 输出、trainer 记录和执行器元数据。

## 版本与配置

- 方法：Workflow Localized Mechanism Learning（WML）。
- Skill：`jpg-ocr-stat/result/wml__claude-opus-4-7-aigw/skills/`。
- 冻结 Skill SHA-256：`1fba2a8d283bd98117591bbf6528d2fafd44423dd1e435f0577bf04c6dd51282`。
- Skill 仓库 commit：本地结果尚未提交；提交本目录时应将最终 Git commit 补录于此。冻结身份以以上 SHA-256 为准，三次运行期间未修改 Skill。
- 数据版本：`skill-repair-benchmark` main commit `bee9b0df5b04a300735e5009f5238f5d5c8aaf61`，仅运行 `group_02`（20 张图片、40 个日期/金额字段）。
- Harness：BenchFlow `v0.6.7`，base commit `aadad44acf27f193df98f438443116d514f51fb8`；OpenHands CLI commit `2df8a2835d3f1bd2f2eadf5a7a2e1ad0dfb0d271`。
- 执行模型：Claude Opus 4.7；每次最多 65 次 parent iteration，guard 共用该额度。
- 评分：固定 40 个字段为分母，缺失值不缩分母；三次 `delivery_status` 均为 `valid`。

## 运行与成绩

| 组别 | 第1次 | 第2次 | 第3次 | 均值 |
|---|---:|---:|---:|---:|
| group_02 | 38/40（0.950） | 39/40（0.975） | 38/40（0.950） | 115/120（0.958333） |

| 目录 | Run ID | 实际模型路由 | Endpoint | 实际迭代 | 终止原因 | 有效性 |
|---|---|---|---|---:|---|---|
| `run_01` | `jpg-group02-r012` | `tatumass/claude-opus-4-7@AIGW-default` | `https://maas.tatucloud.com` | 33/65 | `end_turn` | 有效 |
| `run_02` | `jpg-group02-r013` | `tatumass/claude-opus-4-7@AIGW-default` | `https://maas.tatucloud.com` | 37/65 | `end_turn` | 有效 |
| `run_03` | `jpg-group02-r016` | `paratera/Claude-Opus-4.7` | `https://llmapi.paratera.com` | 36/65 | `end_turn` | 有效 |

前两次通过 Tatumass Anthropic Messages API 执行；第三次因 Tatumass 当时不可用，按实验继续要求切换到 Paratera OpenAI-compatible endpoint。三次使用相同冻结 Skill、Claude Opus 4.7 模型族、数据、harness 和 65 轮预算，但 endpoint/provider protocol 并不完全相同，因此不得将其描述为三次完全同配置运行。

`benchmark_result.json` 中 `task_passed=false` 表示未达到 40/40 的全字段满分阈值，不是基础设施失败。三次均满足 `execution_ok=true`、`trajectory_complete=true`、`protocol_evidence_valid=true` 和 `skill_exposure_verified=true`，且 verifier 均声明 `delivery_status=valid`。

## 文件说明

每次运行目录均包含：

- `stat_ocr.xlsx` 与 `pre-verifier-inputs.tar.gz`
- `executor_request.json`、`config.json`、`result.json`、`benchmark_result.json`
- `timing.json`、`rewards.jsonl`、`results.jsonl`、`prompts.json`
- `trajectory/acp_trajectory.jsonl` 与完整 LLM 请求响应轨迹
- `verifier/` 原始评分输出
- `trainer/` WML trainer 记录

`run_01`、`run_02` 的 LLM 轨迹使用 gzip 无损压缩；`run_03` 使用 xz 无损压缩，以确保单文件小于 GitHub 100 MB 限制。解压后均为原始 `llm_trajectory.jsonl`。
