# SkillHone · Claude Opus 4.7 · Gold15

11 月 19 日在服务器启动，11 月 20 日完成。15 个独立 worker 处理与 CausalFlow Opus 4.7 Gold15 相同的题目。首轮使用固定 commit 的 Original-Skill 归档轨迹。修复和 OpenHands 执行均使用 Paratera 的 Claude Opus 4.7，沿用已固定的 OpenHands CLI 和 SDK。每题最多修复 5 轮，满分即结束，取消 SkillHone 外层 20 分钟限制。基线使用 OpenRouter 的 Claude Opus 4.7。[Gold15 清单](../CausalFlow-Skill-Opus47-Gold15-20260922/gold.subset.json) · [固定的基线归档](https://github.com/linyouxue/skill-repair-benchmark/tree/745816c178cb1bb5c0f0e9900baaf9b698b36c49/evaluation/results/Opus47-OriginalSkill-79Tasks-20260920)

15 题全部取得有效最终评分。6 题满分，9 题完成第 5 轮后得 0 分。56 轮有效评分中，50 轮为原生 `end_turn`，6 轮达到预设步数上限。56 轮均校验了 Skill 预载，实际记录 1 次原生 Skill 调用。[逐轮评分](scores.json)

首批 21 轮的执行请求记录为 verifier 代理关闭，余下 35 轮使用显式代理。18 轮在原 verifier 故障后，复用导出的同一工作区和两份模型轨迹补评，补评产生零模型请求。逐轮清单记录原始代理模式及补评来源。6 次修复触及输出上限后在原会话内从 16,384 提升至 32,768 tokens。视频静音移除第 5 轮复用已完成的 Skills 修改，剔除了模型额外生成的 `.gitignore`。

| Artifact | Contents |
| --- | --- |
| [`submission.json`](submission.json) | 15 题及最终完整 Skill 路径 |
| [`scores.json`](scores.json) | 15 份最终分、56 轮评分及恢复来源 |
| [`tasks/`](tasks/) | 每题原始与最终执行的 ACP 轨迹、评分元数据及最终完整 Skill |
| [`trajectory_timelines/`](trajectory_timelines/) | 仓库脚本生成的 15 条 before、15 条 after 时间线及索引 |

服务器侧的 56 轮均通过仓库的 BenchFlow 产物校验，含 ACP、LLM 请求响应轨迹与 rollout 级 `results.jsonl`。本目录沿用既有 SkillHone 提交范围，保存初始与最终的 ACP 轨迹和评分元数据。原始供应商轨迹、训练行和中间轮工作区保留在服务器。

## Final scores

| Task | Baseline | Final | Rounds | Final verifier |
| --- | ---: | ---: | ---: | --- |
| [azure-bgp-oscillation-route-leak](tasks/azure-bgp-oscillation-route-leak/) | 0 | 0 | 5 | initial verifier |
| [data-to-d3](tasks/data-to-d3/) | 0 | 1 | 1 | same-workspace replay |
| [dynamic-object-aware-egomotion](tasks/dynamic-object-aware-egomotion/) | 0 | 0 | 5 | initial verifier |
| [enterprise-information-search](tasks/enterprise-information-search/) | 0 | 0 | 5 | initial verifier |
| [fix-build-agentops](tasks/fix-build-agentops/) | 0 | 0 | 5 | initial verifier |
| [flink-query](tasks/flink-query/) | 0 | 1 | 1 | same-workspace replay |
| [jpg-ocr-stat](tasks/jpg-ocr-stat/) | 0 | 1 | 1 | same-workspace replay |
| [manufacturing-equipment-maintenance](tasks/manufacturing-equipment-maintenance/) | 0 | 1 | 3 | initial verifier |
| [paper-anonymizer](tasks/paper-anonymizer/) | 0 | 0 | 5 | initial verifier |
| [pddl-airport-planning](tasks/pddl-airport-planning/) | 0 | 1 | 4 | initial verifier |
| [python-scala-translation](tasks/python-scala-translation/) | 0 | 0 | 5 | initial verifier |
| [reserves-at-risk-calc](tasks/reserves-at-risk-calc/) | 0 | 0 | 5 | initial verifier |
| [seismic-phase-picking](tasks/seismic-phase-picking/) | 0 | 1 | 1 | same-workspace replay |
| [shock-analysis-supply](tasks/shock-analysis-supply/) | 0 | 0 | 5 | initial verifier |
| [video-silence-remover](tasks/video-silence-remover/) | 0 | 0 | 5 | initial verifier |
