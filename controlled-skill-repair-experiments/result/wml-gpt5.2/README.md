# WML / GPT‑5.2 实验结果

本目录只整理 **WML**，不包含 SkillAxe、SkillTTA。三种方法合计 66 条的分工中，WML 对应 22 条受控修复；另有 5 题无提示原题修复对照。

| 目录 | 内容 |
|---|---|
| controlled22/ | 5 条位置提示、12 条单点待修、5 条多点待修；9 通过、13 失败，22 条执行评分有效 |
| unhinted5/ | 5 题无提示 WML 原题修复结果，4 条历史结果直接复用；对话解析另有授权的补充执行验证 |
| shared_controls33/ | 配套的 33 条直接执行共享对照；与 5 题“无提示 WML 修复”不是同一种对照 |
| trajectory_timelines/ | 根据本目录原始 JSONL 自动转换的 Markdown 与索引 |
| rerun4/ | 4 条问题结果的原始问题、历史轨迹和补跑对应清单；已包含在 22/33 内，不重复计数 |
| evidence/ | 原包摘要、环境验收、D3 verifier 兼容差异、审计和尝试对应记录 |
| tools/ | 原始脚本存档与适配本目录布局的轨迹导出器 |

## 受控修复

`controlled22/skills/<trial>/` 是实际使用的完整冻结修后 Skill；`inputs/<trial>/` 是本次条件输入；`evidence/repair/<trial>/` 保留 WML 诊断/修复响应及用量；`experiments/repair/<trial>/jobs/selected/<rollout>/` 保留执行、verifier 和模型轨迹。官方 22 行评分表在 `controlled22/reports/score_template.csv`。

语义评分是 **AI 辅助复核，不是独立人工签字**。目标修复成立 5/22，其他 Gold 保留 11/12；不能用任务 pass/fail 替代这两项评分。

## 无提示对照

5 题是 dialogue-parser、data-to-d3、flink-query、manufacturing-equipment-maintenance、pddl-airport-planning。`unhinted5/manifest.json` 给出各题应采用的结果、完整修后 Skill 和配置。

每题 `historical_zenmux/` 保存原记录。dialogue-parser 原历史记录虽得 1 分，但末尾有未执行的继续动作，仍标为异常；另在 `supplemental_tatumass/` 保存用户授权的冻结修后 Skill 补充执行，正常通过并实际保存产物。没有覆盖或美化原记录。4 条历史清洁结果与 1 条补充验证覆盖这 5 题。

历史无提示是 Zenmux GPT‑5.2，受控与补充验证是 Tatumass GPT‑5.2；分开标注，不能当作严格同端点的随机配对比较。

## 证据与归档说明

`summary.json` 是本目录摘要，三个子目录各有 manifest；`COPY_PROVENANCE.json` 记录原包到本目录的逐文件对应和哈希。原包 `../wml-gpt5.2-controlled55/` 保持不变。原始请求/结果 JSON 的历史绝对路径未人工改写，当前入口以本目录 manifest 中的相对路径为准。

部分历史任务产物未归档；没有从评分 JSON、模型文字或 Gold 重建文件。D3 的 SVG verifier 兼容修正经用户授权，原版本/分数和差异保留。所有原始尝试仍在原包记录的本机 work 归档目录中；本目录不是全部原始尝试的重复镜像。仅目录整理，没有发起新模型调用或上传 GitHub。

## 上传范围

请整体上传本目录 `wml-gpt5.2/`。其中 WML 受控修复 22 条、无提示修复对照 5 题、配套共享执行对照 33 条；`rerun4/` 是其中 4 条的专门审计入口，不是额外 4 个实验。三种方法合计 66 条不全属于 WML，本包不包含其他方法。目录完整性、哈希和上传前检查见 `UPLOAD_CHECK.json`。旧问题证据与重跑轨迹均保留。
