# WML / Claude Opus 4.7 AIGW

> **状态：完成。** 同一冻结 Skill 已在原 22 张小票任务上独立执行 3 次，
> 三次均保留原始 Excel、完整 ACP/LLM 轨迹和评分证据。

- 最终 Skill 版本：`sha256:1fba2a8d283bd98117591bbf6528d2fafd44423dd1e435f0577bf04c6dd51282`，已冻结。
- 方法：Workflow Localized Mechanism Learning（WML）；修复过程包含 37 个诊断窗口和 5 轮迭代更新。
- 方法与执行器版本：BenchFlow `v0.6.7`，base commit `aadad44acf27f193df98f438443116d514f51fb8`，OpenHands CLI commit `2df8a2835d3f1bd2f2eadf5a7a2e1ad0dfb0d271`；JPG 最终执行启用 65 parent-iteration 补丁及 Tatumass provider 路由。
- 修复模型：`claude-opus-4-7@AIGW-default`，Tatumass Anthropic Messages API，`https://maas.tatucloud.com/v1`。
- 最终执行模型：`tatumass/claude-opus-4-7@AIGW-default`，OpenHands/BenchFlow `skillrepair-v1` protocol v2，最多 65 次 parent iteration。
- 修复材料：JPG OCR 原 22 张小票、任务 Skill 和仓库提供的 diagnosis 材料；未使用 group2 进行修复或最终原任务选版。
- 图片接入：`evidence/repair/adapter-preflight.json` 证明每个诊断请求实际包含 22 个 Anthropic 原生图片内容块，解码字节与源 JPG 一致。
- 方法内部新增执行：诊断请求、响应、候选应用及选版记录位于 `evidence/repair/diagnoses/` 和 `evidence/repair/round-01/` 至 `round-05/`。
- 人工参与：人工只负责配置模型、处理基础设施和整理证据；最终 Skill 内容来自 WML 迭代，没有在冻结后人工改写。
- 样本专用内容：最终 Skill 含基于原 22 张诊断样本归纳的 OCR 规则；作用与变更可由各轮 `applied.json` 和最终 `SKILL.md` 核对。
- 运行任务披露：最终执行任务来自仓库 `main` 的原 22 张小票运行文件；`verifier/test.sh` 仅增加评分前按字节复制 `stat_ocr.xlsx` 到 `/logs/artifacts` 并生成归档的证据保存步骤，未修改预测、oracle、字段比较或 reward 计算。
- 旧运行披露：`jpg-original22-r015` 得分为 43/44（0.9772727273），53/65 iterations，评分和迭代证据有效，但执行器未在容器销毁前导出原始 `stat_ocr.xlsx`，因此仅放在 `evidence/incomplete_runs/`，不计入三次最终运行。
- 三次最终执行：`jpg-original22-r016`（24/65，`end_turn`）、`jpg-original22-r017`（12/65，`end_turn`）、`jpg-original22-r018`（18/65，`end_turn`）。三次均通过协议、轨迹、迭代计数与 Skill 暴露一致性检查。
- 原 Excel 与评分证据：分别位于 `evidence/final_runs/run_01/`、`run_02/`、`run_03/` 下的 `artifacts/stat_ocr.xlsx` 与 `verifier/`；对应完整轨迹位于各自 `trajectory/`。
- 证据入口：修复过程见 `evidence/repair/`，三次最终执行见 `evidence/final_runs/`。

| 评测集合 | 第1次字段正确率 | 第2次 | 第3次 | 三次均值 |
|---|---:|---:|---:|---:|
| 原22张小票（每次44字段） | 44/44（1.000000） | 43/44（0.977273） | 44/44（1.000000） | 131/132（0.992424） |
