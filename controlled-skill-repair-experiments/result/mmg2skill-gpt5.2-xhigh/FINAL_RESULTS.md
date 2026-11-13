# MMG2Skill 控制变量实验结果

## 发布内容

- [results-summary.json](results-summary.json) 汇总 22 条输入的 R0、69 个有效轮次、末轮得分和产物路径。
- `candidates/<输入>/round-N/skills/` 保留逐轮完整 Skill。 `final/<输入>/skills/` 保留所选末轮的完整 Skill。
- `evidence/runs/` 包含官方分数、测试名及状态、步数、guard、正文预载和调用估算。 `artifacts/` 收录末轮真实归档中的任务交付文件，以及报告列出的 Flink 工作区文件。
- [EXPERIMENT_CONFIG.json](EXPERIMENT_CONFIG.json) 记录运行协议与 RI-002 第 5 轮的 guard3 例外。完整工作区归档、模型轨迹和修复会话保存在实验机器上，下文的原始 Linux 路径供溯源。

北京时间 2026-11-13 01:34:26 完成。

北京时间 2026-11-13 补做 Google Auto 三条 R5 的同候选重评。全量组和 RI-001 的 R5 已替换为 60 步的重跑结果。RI-001 更早的两次 R5 执行已从本地删除，调用与费用仍计入账目。RI-002 第一次重跑及其零模型调用补评分均在 900 秒评分上限处超时，简记见 `early-stop-rerun/discarded-ri002-verifier-timeout.json`。第二次重跑在 4/60 步以承诺式文本提前结束，官方 0 分（0/3）。第三次重跑单独将纯文本续跑上限改为 3，原候选和 60 根步预算沿用，官方 0 分（2/3），已作为当前 R5。前两份有分数的旧结果归入本地历史。

RI-002 的 guard3 重跑在两次上游 HTTP 500 后从原容器和原会话继续，三段累计 17+28+15=60 根步，实际使用 1 次纯文本续跑。执行期间共终止 5 个确认卡住的交互式 `sudo update-java-alternatives` 子进程，工作区由原会话保留。评分通过说明与补丁检查，构建检查失败。已归档真实工作区和合并的供应商调用记录。ACP 保留原前缀，续段以原生 SDK 事件保存。单次重评含执行随机性与上述恢复干预。

- **22/22 条完成，12 条满分（54.5%），10 条第 5 轮官方 0 分。** 共 69 次有效修复候选评测，满分即停。
- R0 满分 4/22。最终分数较 R0 提高 8 条、持平 14 条、下降 0 条。R0 复用 4 条同输入 SkillHone 轨迹与 3 条 GitHub 历史轨迹，其余 15 条本批新执行。
- 12 条满分中，8 条满分轮实际改动 Skill 正文，4 条以与 R0 字节相同的候选通过。结果包含单次执行的随机性及历史 R0 来源差异。
- 同一组 22 个冻结输入的 SkillHone 主实验有 10 条满分。逐条对照最终分数，MMG2Skill 有 5 条更高、14 条相同、3 条更低。该对照保留各实验实际使用的反馈和候选选择过程。

## 逐条评分

费用列仅含修复候选评测的执行侧估算。末轮 Skill 改动列为该轮变更的正文文件数。

| 冻结输入 | R0（来源） | 修复候选逐轮官方分数 | 末轮测试 | 末轮 Skill 改动 | 执行估算 USD |
| --- | --- | --- | --- | --- | --- |
| location-dialogue-parser | 0.833（SkillHone） | 1 | 6/6 | 1 | 0.24 |
| location-data-to-d3 | 0（GitHub） | 0 → 0 → 1 | 15/15 | 1 | 1.79 |
| location-flink-query | 0（GitHub） | 0 → 0 → 0 → 0 → 0 | 0/3 | 1 | 5.78 |
| single-flink-query-all | 0（本批） | 0 → 0 → 0 → 0 → 0 | 0/3 | 0 | 9.36 |
| single-flink-query-RI-001 | 0（本批） | 0 → 0 → 0 → 0 → 0 | 0/3 | 1 | 11.73 |
| single-flink-query-RI-002 | 0（本批） | 0 → 0 → 0 → 0 → 0 | 0/3 | 1 | 10.27 |
| location-manufacturing-equipment-maintenance | 0（本批） | 0 → 0 → 0 → 1 | 7/7 | 2 | 2.72 |
| single-manufacturing-equipment-maintenance-all | 1（本批） | 0 → 1 | 7/7 | 0 | 0.61 |
| single-manufacturing-equipment-maintenance-RI-001 | 0（本批） | 1 | 7/7 | 0 | 1.38 |
| single-manufacturing-equipment-maintenance-RI-002 | 0（本批） | 0 → 0 → 0 → 0 → 0 | 5/7 | 2 | 1.84 |
| location-pddl-airport-planning | 0（GitHub） | 1 | 2/2 | 0 | 0.15 |
| single-video-silence-remover-all | 0（SkillHone） | 0 → 0 → 0 → 0 → 0 | 7/9 | 0 | 1.11 |
| single-video-silence-remover-RI-001 | 0（SkillHone） | 0 → 0 → 0 → 0 → 0 | 7/9 | 0 | 0.56 |
| single-video-silence-remover-RI-002 | 1（本批） | 1 | 9/9 | 7 | 0.15 |
| single-video-silence-remover-RI-003 | 0（本批） | 0 → 1 | 9/9 | 4 | 0.49 |
| single-sec-financial-report-all | 0（本批） | 1 | 2/2 | 0 | 0.24 |
| single-sec-financial-report-RI-001 | 0（SkillHone） | 1 | 2/2 | 2 | 0.20 |
| single-sec-financial-report-RI-002 | 1（本批） | 1 | 2/2 | 2 | 0.21 |
| single-sec-financial-report-RI-003 | 1（本批） | 1 | 2/2 | 2 | 0.12 |
| single-fix-build-google-auto-all | 0（本批） | 0 → 0 → 0 → 0 → 0（R5 重跑） | 2/3 | 2 | 5.16 |
| single-fix-build-google-auto-RI-001 | 0（本批） | 0 → 0 → 0 → 0 → 0（R5 重跑） | 1/3 | 2 | 2.08 |
| single-fix-build-google-auto-RI-002 | 0（本批） | 0 → 0 → 0 → 0 → 0（R5 guard3 重跑） | 2/3 | 3 | 1.14 |

## 实际产物与正文

逐轮核对了官方评分、CTRF、真实工作区归档、输入快照、候选附件字节及实际上下文预载。成功生成的候选用保存的 Refiner 原始响应离线复核。下表列末轮归档和公开产物。归档路径相对于 Linux 实验根目录。回显列统计首条带供应商 instructions 的成功记录中，逐字匹配的完整正文份数。

| 冻结输入 | 归档文件数、公开产物及位置 | 预载／回显逐字匹配／命名调用 | 根步／guard |
| --- | --- | --- | --- |
| location-dialogue-parser | 4 件，dialogue.json, dialogue.dot, solution.py（evaluations/mmg2skill-location-dialogue-parser/round-1-attempt-01/artifacts/pre-verifier-workspace.tar.gz） | 1／1／0 | 17／1 |
| location-data-to-d3 | 108 件，output/index.html, output/js/visualization.js（evaluations/mmg2skill-location-data-to-d3/round-3-attempt-01-native-continuation-01/artifacts/pre-verifier-workspace.tar.gz） | 1／1／0 | 16／0 |
| location-flink-query | 10 件，pom.xml, src/main/java/clusterdata/utils/AppBase.java, src/main/java/clusterdata/query/LongestSessionPerJob.java, src/main/java/clusterdata/datatypes/TaskEvent.java, src/main/java/clusterdata/datatypes/JobEvent.java（evaluations/mmg2skill-location-flink-query/round-5-attempt-01-native-continuation-01/artifacts/pre-verifier-workspace.tar.gz） | 2／0／0 | 32／1 |
| single-flink-query-all | 10 件，pom.xml, src/main/java/clusterdata/utils/AppBase.java, src/main/java/clusterdata/query/LongestSessionPerJob.java, src/main/java/clusterdata/datatypes/TaskEvent.java, src/main/java/clusterdata/datatypes/JobEvent.java（evaluations/mmg2skill-single-flink-query-all/round-5-attempt-01/artifacts/pre-verifier-workspace.tar.gz） | 2／0／0 | 38／1 |
| single-flink-query-RI-001 | 10 件，pom.xml, src/main/java/clusterdata/utils/AppBase.java, src/main/java/clusterdata/query/LongestSessionPerJob.java, src/main/java/clusterdata/datatypes/TaskEvent.java, src/main/java/clusterdata/datatypes/JobEvent.java（evaluations/mmg2skill-single-flink-query-RI-001/round-5-attempt-01-native-continuation-01/artifacts/pre-verifier-workspace.tar.gz） | 2／0／0 | 57／1 |
| single-flink-query-RI-002 | 10 件，pom.xml, src/main/java/clusterdata/utils/AppBase.java, src/main/java/clusterdata/query/LongestSessionPerJob.java, src/main/java/clusterdata/datatypes/TaskEvent.java, src/main/java/clusterdata/datatypes/JobEvent.java（evaluations/mmg2skill-single-flink-query-RI-002/round-5-attempt-01/artifacts/pre-verifier-workspace.tar.gz） | 2／0／0 | 37／1 |
| location-manufacturing-equipment-maintenance | 10 件，output/q01.json, output/q02.json, output/q03.json, output/q04.json, output/q05.json（evaluations/mmg2skill-location-manufacturing-equipment-maintenance/round-4-attempt-01-native-continuation-01/artifacts/pre-verifier-workspace.tar.gz） | 2／2／0 | 46／1 |
| single-manufacturing-equipment-maintenance-all | 10 件，output/q01.json, output/q02.json, output/q03.json, output/q04.json, output/q05.json（evaluations/mmg2skill-single-manufacturing-equipment-maintenance-all/round-2-attempt-01/artifacts/pre-verifier-workspace.tar.gz） | 2／2／0 | 25／0 |
| single-manufacturing-equipment-maintenance-RI-001 | 1929 件，output/q01.json, output/q02.json, output/q03.json, output/q04.json, output/q05.json（evaluations/mmg2skill-single-manufacturing-equipment-maintenance-RI-001/round-1-attempt-01/artifacts/pre-verifier-workspace.tar.gz） | 2／2／0 | 53／0 |
| single-manufacturing-equipment-maintenance-RI-002 | 11 件，output/q01.json, output/q02.json, output/q03.json, output/q04.json, output/q05.json（evaluations/mmg2skill-single-manufacturing-equipment-maintenance-RI-002/round-5-attempt-01-native-continuation-02/artifacts/pre-verifier-workspace.tar.gz） | 2／2／0 | 33／1 |
| location-pddl-airport-planning | 63 件，task01.txt（evaluations/mmg2skill-location-pddl-airport-planning/round-1-attempt-01/artifacts/pre-verifier-workspace.tar.gz） | 1／1／0 | 20／1 |
| single-video-silence-remover-all | 14 件，compressed_video.mp4, compression_report.json, compressed_video_report.json（evaluations/mmg2skill-single-video-silence-remover-all/round-5-attempt-01/artifacts/pre-verifier-workspace.tar.gz） | 7／7／0 | 35／0 |
| single-video-silence-remover-RI-001 | 12 件，compressed_video.mp4, compression_report.json, compressed_video_report.json（evaluations/mmg2skill-single-video-silence-remover-RI-001/round-5-attempt-01/artifacts/pre-verifier-workspace.tar.gz） | 7／7／0 | 13／1 |
| single-video-silence-remover-RI-002 | 13 件，compressed_video.mp4, compression_report.json, compressed_video_report.json（evaluations/mmg2skill-single-video-silence-remover-RI-002/round-1-attempt-01/artifacts/pre-verifier-workspace.tar.gz） | 7／7／0 | 15／1 |
| single-video-silence-remover-RI-003 | 12 件，compressed_video.mp4, compression_report.json, compressed_video_report.json（evaluations/mmg2skill-single-video-silence-remover-RI-003/round-2-attempt-01-native-continuation-03/artifacts/pre-verifier-workspace.tar.gz） | 7／7／0 | 19／1 |
| single-sec-financial-report-all | 23 件，answers.json（evaluations/mmg2skill-single-sec-financial-report-all/round-1-attempt-02-native-continuation-01/artifacts/pre-verifier-workspace.tar.gz） | 2／2／0 | 25／0 |
| single-sec-financial-report-RI-001 | 23 件，answers.json（evaluations/mmg2skill-single-sec-financial-report-RI-001/round-1-attempt-01/artifacts/pre-verifier-workspace.tar.gz） | 2／2／0 | 22／1 |
| single-sec-financial-report-RI-002 | 23 件，answers.json（evaluations/mmg2skill-single-sec-financial-report-RI-002/round-1-attempt-01/artifacts/pre-verifier-workspace.tar.gz） | 2／2／0 | 18／1 |
| single-sec-financial-report-RI-003 | 23 件，answers.json（evaluations/mmg2skill-single-sec-financial-report-RI-003/round-1-attempt-01/artifacts/pre-verifier-workspace.tar.gz） | 2／2／0 | 14／1 |
| single-fix-build-google-auto-all | 11104 件，build/failed/failed_reasons.txt, build/failed/google/auto/patch_1.diff（evaluations/mmg2skill-single-fix-build-google-auto-all/round-5-attempt-02/artifacts/pre-verifier-workspace.tar.gz） | 3／3／0 | 60／0 |
| single-fix-build-google-auto-RI-001 | 11100 件，build/failed/failed_reasons.txt（evaluations/mmg2skill-single-fix-build-google-auto-RI-001/round-5-attempt-03/artifacts/pre-verifier-workspace.tar.gz） | 3／3／0 | 60／1 |
| single-fix-build-google-auto-RI-002 | 11101 件，build/failed/failed_reasons.txt, build/failed/google/auto/patch_1.diff（evaluations/mmg2skill-single-fix-build-google-auto-RI-002/round-5-attempt-04-native-continuation-02/artifacts/pre-verifier-workspace.tar.gz） | 3／3／0 | 60／1 |

Flink 归档中的 POM 与源码是当时工作区证据，四条 Flink 最终官方评分均为 0。回显受脱敏或序列化影响，匹配数低于预载数时，仍有执行器的实际上下文观测和冻结候选清单。SDK 续跑另核对原 persistent AgentContext。

## 用量与费用

- 原批执行 84 次（69 次候选及 15 次新 R0），供应商记录 HTTP 200 × 2236、HTTP 500 × 43。43 条无总 token 回报，已回报总 token 99,708,508。六次补跑另有 HTTP 200 × 246、HTTP 500 × 2，已回报总 token 14,800,175。RI-002 补评分的模型调用为 0。
- 原批执行费用估算 72.92 美元，候选 54.01 美元，新 R0 18.90 美元。六次补跑新增估算 4.91 美元，其中 RI-002 guard3 重跑的 SDK 估算为 0.94 美元。金额各自四舍五入，供应商实际账单未知。原批有 29 轮保留部分 ACP 和原生 SDK 续跑事件。
- 修复侧记录 239 次派发，227 次有响应、7 次明确 HTTP 错误、5 次无终态回执。已回报总 token 6,049,627，其中已报告输入 3,703,440、输出 2,346,187。0 次有响应但无总 token。修复侧美元费用未知。
- 限长响应包括 16,384 档 13 次与 32,768 档 9 次。原轮候选状态为 analyzer_max_tokens_retained_bundle 1、max_tokens_retained_bundle 16、outer_budget_retained_bundle 5、refined 47。已派发的旧限长请求和传输重试均纳入用量。
- 启动鉴权探针另计 1 次（HTTP 200，36 token）。4 次 Docker 启动废弃尝试均为 0 次模型调用。7 条历史基线费用属于原实验。

## 协议与证据

- 原生 MMG2Skill 源码版本 c12d8b1e8998ed76bad2ab85425959f44ca085b8。首轮使用同一冻结 Skill 的 R0 轨迹，后续使用本方法上一轮轨迹与官方反馈。每轮独立调用共享 BenchmarkExecutor，修复 20 分钟，执行 60 根步共享最多 1 次纯文本续跑。
- Linux 根目录为 /home/linyuanjing/controlled-mmg2skill-20261112。逐轮评分和候选索引见 feedback/，模型回执见 repairs/，官方评分和真实归档见 evaluations/。
- 八个任务镜像使用就绪收据中的实际镜像。镜像与历史环境的差异见 environment-ready/。原批专属容器、网络和八个闲置镜像已确认清理，见 resource-cleanup.json。补跑重建了 Google Auto 镜像，运行 manifest 和配置与原批一致，见 early-stop-rerun/image-verification.json。补跑资源清理见 early-stop-rerun/resource-cleanup.json。
- RI-002 guard3 重跑的验收、镜像一致性及资源清理分别见 `early-stop-rerun/ri002-guard3-acceptance.json`、`early-stop-rerun/ri002-guard3-image-verification.json` 和 `early-stop-rerun/ri002-guard3-resource-cleanup.json`。
