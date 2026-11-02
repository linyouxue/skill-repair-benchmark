# WML Claude 4.7 受控数据集实验结果

本目录包含同一执行配置下的 55 个有效实验：22 个 WML 修复实验和 33 个对照实验。

## 汇总

- 修复实验：22/22 有效，12 pass，10 fail
- 对照实验：33/33 有效，19 pass，14 fail
- 合计：55/55 有效，31 pass，24 fail，0 invalid
- 修复模型：Claude-Opus-4.7
- 执行模型：`openai/Claude-Opus-4.7`
- 执行代理：OpenHands
- API：Paratera OpenAI-compatible endpoint

## 目录

```text
inputs/                  22 个 WML 单次修复输入
candidates/              22 个 WML 最终完整候选 Skill bundle
prepared/                22 个 WML method-skill 执行材料
eval-runs/               WML 修复实验运行、日志、result 和 trajectory
control-prepared/        33 个对照实验执行材料
control-runs/            对照实验全部 attempt、日志、result 和 trajectory
failed-attempts/         修复阶段失败尝试的保留记录
method/                  WML adapter、修复/执行/汇总脚本
protocol/                数据集说明、catalog、Gold annotation、repair groups 和官方评分模板
review/                  已填写的官方语义评分表及逐题复核证据
eval_summary.json        22 个最终 WML 结果
control_eval_summary.json 33 个最终对照结果
results-summary-20261029.json WML 官方 collect 输出
control-collected.json   对照实验官方 collect 输出
experiment-manifest-55.json 55 个最终实验及证据路径的统一清单
```

`experiment-manifest-55.json` 中每个条目都指向对应 prepared 目录、最终 attempt、result 和 ACP trajectory。基础设施失败 attempt 保留在运行目录中，但不计入有效结果。

本包不包含 API key、虚拟环境、Docker socket/软件源代理配置或本机调试配置。上传前的凭据扫描发现 `location-data-to-d3` 一次运行的 Agent 工具输出在若干派生轨迹中重复记录了同一 API key；这些日志仅将该密钥字符串替换为 `<REDACTED_API_KEY>`，其余轨迹内容不变。修复调用的实际用量保存在各 `candidates/<trial>/api_usage.json`；执行命令、模型、agent、时间和输入哈希保存在相应 attempt 的 `RUN_RECORD.json`。未在实验前显式固定的 seed 或统一预算不事后补写。

## 语义复核

- `review/semantic_review.csv`：按照官方 `organizer/score_template.csv` 的 23 个字段填写，共 22 个 WML 修复实验。
- `review/semantic_review_evidence.md`：逐项记录目标修复与非目标 Gold 保留性的判断依据。
- 严格的“所有 Gold 要求均满足”口径下，`target_semantically_repaired=true` 为 5/22；12 个留一实验的 `non_target_gold_preserved=true` 为 12/12。
- 该复核由 Codex 逐项阅读候选 Skill、Gold annotation/repair atoms 和运行记录完成，属于 AI 辅助人工式语义复核，不冒充独立人类审稿；如提交方要求独立人类签字，应在此表基础上进行二次复核并更新 `reviewer`。
