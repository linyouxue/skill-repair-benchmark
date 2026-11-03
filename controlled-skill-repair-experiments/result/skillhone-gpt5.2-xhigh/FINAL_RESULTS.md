# SkillHone 统一执行器重跑：最终结果

完成日期：2026-11-03（北京时间）。本报告只汇总 `controlled-skillhone-unified-20261102` 新批次；旧错误批次不计入结果，也未作为恢复来源。

22 条独立冻结输入均已结束，共 79 个有效修复／执行轮次。10 条满分停止，12 条达到 5 轮停止，总满分率 45.45%。所有轮次都有真实官方评分及对应工作区归档。最终只读审计未发现新增、足以作废评分的基础设施阻塞；正常低分全部保留。12 个原生续跑轮次的 ACP 仍明确标为部分轨迹，不作为完整 ACP／SFT 训练数据。

## 分组与逐轮结果

分组按 `plan.json` 的 dataset 定义。`single` 组包含 5 条 `all_faults` 和 12 条 `leave_one_out`，不能将这 17 条统称为单一故障条件。两个组的任务构成不同，下面的比例是本批协议结果，不是控制变量后的组间因果比较。

| 分组 | 冻结输入 | 有效轮次 | 满分停止 | 5 轮停止 | 满分率 |
|---|---:|---:|---:|---:|---:|
| location：定位提示组 | 5 | 14 | 3 | 2 | 60.00% |
| single：单点导出组，含 all 条件 | 17 | 65 | 7 | 10 | 41.18% |
| 合计 | 22 | 79 | 10 | 12 | 45.45% |

表中为 canonical 官方 reward；`—` 表示满分后没有执行该轮，不是 0 分。正常 FAIL／0 分均计轮；最终分数采用首次满分，否则采用最后一轮。

### location 组

完整 trial_id 为 `location-` 加表中名称。

| 输入 | R1 | R2 | R3 | R4 | R5 | 最终分数 | 停止原因 |
|---|---:|---:|---:|---:|---:|---:|---|
| dialogue-parser | 0.833 | 1 | — | — | — | 1 | R2 满分 |
| data-to-d3 | 0 | 0 | 0 | 0 | 0 | 0 | 5 轮上限 |
| flink-query | 0 | 0 | 0 | 0 | 0 | 0 | 5 轮上限 |
| manufacturing-equipment-maintenance | 1 | — | — | — | — | 1 | R1 满分 |
| pddl-airport-planning | 1 | — | — | — | — | 1 | R1 满分 |

### single 组

完整 trial_id 为 `single-` 加表中名称。`all` 对应 `all_faults`，RI 编号对应 plan 中的 `leave_one_out`。

| 输入 | R1 | R2 | R3 | R4 | R5 | 最终分数 | 停止原因 |
|---|---:|---:|---:|---:|---:|---:|---|
| flink-query-all | 0 | 0 | 0 | 0 | 0 | 0 | 5 轮上限 |
| flink-query-RI-001 | 0 | 0 | 0 | 0 | 0 | 0 | 5 轮上限 |
| flink-query-RI-002 | 0 | 0 | 0 | 0 | 0 | 0 | 5 轮上限 |
| manufacturing-equipment-maintenance-all | 0 | 0 | 0 | 0 | 0 | 0 | 5 轮上限 |
| manufacturing-equipment-maintenance-RI-001 | 1 | — | — | — | — | 1 | R1 满分 |
| manufacturing-equipment-maintenance-RI-002 | 0 | 0 | 0 | 0 | 1 | 1 | R5 满分 |
| video-silence-remover-all | 0 | 0 | 0 | 0 | 0 | 0 | 5 轮上限 |
| video-silence-remover-RI-001 | 0 | 1 | — | — | — | 1 | R2 满分 |
| video-silence-remover-RI-002 | 0 | 1 | — | — | — | 1 | R2 满分 |
| video-silence-remover-RI-003 | 1 | — | — | — | — | 1 | R1 满分 |
| sec-financial-report-all | 0 | 0 | 0 | 0 | 0 | 0 | 5 轮上限 |
| sec-financial-report-RI-001 | 0 | 1 | — | — | — | 1 | R2 满分 |
| sec-financial-report-RI-002 | 0 | 0 | 0 | 0 | 0 | 0 | 5 轮上限 |
| sec-financial-report-RI-003 | 0 | 0 | 0 | 0 | 0 | 0 | 5 轮上限 |
| fix-build-google-auto-all | 0 | 0 | 0 | 0 | 0 | 0 | 5 轮上限 |
| fix-build-google-auto-RI-001 | 0 | 0 | 0 | 0 | 0 | 0 | 5 轮上限 |
| fix-build-google-auto-RI-002 | 0 | 1 | — | — | — | 1 | R2 满分 |

`single` 内部为 all 条件 0/5 满分、leave-one-out 条件 7/12 满分。它们仍按各自冻结输入独立计数；79 个执行轮次不是 79 条独立输入。

## 协议与来源

实际运行使用原生 SkillHone／DSH 修复，再由现有共享 `BenchmarkExecutor.run(condition=method-skill)` 执行原题，并传入完整候选 bundle。没有复制第二份执行器，也没有使用旧 PyPI 0.6.5 私有 bench 入口。统一入口为本批 `start.py`，3 路独立 worker 滚动补位，修复和原会话恢复共同占用容量。

修复与执行均为 Tatu GPT-5.2、xhigh，每请求输出上限 16384。每轮一次原生修复、一次候选执行，满分立即停止，最多 5 轮。保留原题、输入、评分和每轮 1200 秒修复预算；正常 max-tokens 和明确外层预算停止按当时真实候选评测。每 Step 最多 60 个根 Agent iteration，最多一次 text-only guard 续跑，共享这 60 步。

执行器源码为 `C:/Users/linyuanjing/Desktop/skill论文/skill-repair-benchmark/src`，WSL editable 环境为 `/home/linyuanjing/.venvs/skill-repair-benchmark-a16/bin/python`。plan 记录的执行器 Git HEAD 为 `603c7db26a43e351213626bcac5052bc01d2be57`；既有工作区改动及授权的基础设施修复被保留，不能据此声称源码完全等于该提交。SkillHone 基线提交为 `7e0ce7ce6e8239cb870822d3db5ff66c5ef644d1`。

固定 OpenHands CLI commit 为 `2df8a2835d3f1bd2f2eadf5a7a2e1ad0dfb0d271`，SDK/tools 为 1.28.1。79 轮的运行版本元数据、候选与实际 inputs 快照逐字节一致性均已核对；2148 个成功执行响应的 xhigh／16384 参数回显已核对，30 个失败响应的回显未知。Gold 资格验证复用已有结果，没有新增 33 条对照。

`preflight/verification.json`、`preflight/prebuilt-verification.json`、镜像复用验证，以及 native-resume 的 host／empty／metadata-finalization 验证收据均已通过并复用。最终巡检没有为重复验证再调用模型或评分器；先前已完成的免费测试不计为新实验轮次。

79 轮各有唯一的原生修复 session／Run／Issue，79 份候选与对应原生 Git commit 一致，22 份最终 bundle 与各自最终轮 commit 一致。原生成功工具读取结果可核对全部 79 轮的原始 request、prompt 和 hint 全文。47 轮候选树有变化，32 轮不变；文件树变化本身不等于语义修复有效，也可能包含实际原生生成的字节码文件。

修复停止类型为：32 次原生完成、13 次正常 max-tokens、34 次明确 dsh ETIMEDOUT 外层预算停止。location-flink-query R3 沿原 session／Run／Issue／branch 继续，未新增轮次：首段时间上界 233771ms，加实际续段 965579.423ms，上界合计 1199350.423ms，小于原 1200000ms，未重新分配 20 分钟。

## Skill 正文与恢复证据

所有 79 轮的 `n_skill_invocations` 都为 0，实际 `invoke_skill` 工具调用也为 0。本批正文使用证据来自完整 Skill 预载进入 persistent AgentContext，以及真实供应商响应中的 instructions 回显；不能将这些结果描述成模型主动调用了 Skill 工具。

59 轮在全部成功响应中保留了完整原字节正文匹配。另 20 轮 Flink 的示例口令被日志脱敏，仓库真实 `redact_trajectory_text` 可逐项复现全部记录差异；其中 8 轮还保留独立、未脱敏的原生 persistent context，12 轮没有这份独立原文副本。这是正文观测限制，不能说 79 轮都有日志原字节匹配，也不能据脱敏差异认定模型缺少输入。本批涉及 212 份逐轮 Skill 正文，成功响应中共核对 5853 次正文包含记录。

原生 API 中断恢复始终沿原会话、原容器和检查点继续，没有重发题面、重建工作区或重置 60 步／guard 预算。12 个有效原生续跑轮次的前缀与续段 SDK／供应商响应 ID 集合、累计根步及调用记录已合并核验，没有丢弃中间段。上游故障本身未记作模型 0 分，最终分数来自恢复后的真实工作区。

79 轮累计 2162 个根 Agent iteration，单轮最多 60；70 轮 guard 使用一次，9 轮未使用。SDK 固定空响应纠错与 text-only guard 分开核算，不依据 user 消息数量推算 guard。12 轮保留 `partial_trajectory`、`derived_from` 和 SDK 格式说明，`training_ready=false`；有效官方评分不因此被抹去，也不伪造完整 ACP 或训练就绪。

评分汇总可以交付；完整 ACP／SFT 数据不能将这 12 轮混入。其余轮次的格式、轨迹及训练字段按已有验收和本次逐轮核查记录保留，不将分数有效笼统等同于整批均可发布为训练集。

## 成功归因与失败解释

10 条最终满分不能全部归因于“该轮新修复有效”：

- location-dialogue-parser R2 与 R1 候选相同，记录为同一候选第二次执行通过；两个修复轮的 `candidate_changed` 均为 false。
- single-video-silence-remover-RI-002 R2 与 R1 同 commit、候选逐字节相同；R1 有原生改动，R2 没有新增候选改动。
- single-sec-financial-report-RI-001 R1/R2 均无候选变化；6 文件 bundle 与冻结导出起始输入逐字节相同，是未改候选第二次执行通过。

其余 7 条成功轮可见真实原生候选变化，但本批没有额外对照来分离修复、执行随机性和其他因素，不能将 45.45% 解释为已证明的修复因果增益。

执行行为审计扫描了 79 轮、2100 次真实工具调用，未观察到读取隐藏 verifier／Gold／答案、复制其他 trial 或修改隐藏测试来取分。该结论限于已保留的配置、原生会话和工具记录；没有历史文件系统 syscall 写入者证明或全部已退役容器的挂载 inspect 收据。普通结果中的 `sandbox_id=null` 也不能单独证明各历史容器身份。

低分模式包括 D3 图形／交互错误或未交付应用、Flink Java 实现不完整及输出计数错误、制造任务的测量／合规或最佳方案选择错误、视频片段检测或交付错误、财报语义不满足，以及 Google 构建诊断／补丁／修复不完整。其中 15 个 Flink 轮次实际构建、运行成功但结果对照失败。14 个低分轮在早期探索后以文本提前停止；60 是上限，一次 guard 不强制模型使用完 60 步。模式可能重叠，不作为互斥原因计数。

环境和文档摩擦照实保留：部分 Flink 轮缺少 pdftotext／pypdf／pip 或 apt 权限，但 RI-002 R4 实际通过 Maven/PDFBox 读取了同一公开 PDF；制造任务也在轨迹内安装包后成功读取手册。尚无必要公开数据绝对不可读的证据。三条视频成功轨迹均先尝试旧 `/root/.claude/skills` 路径，再自行定位 `/skills` 并运行配套脚本，不能据满分声称文档路径完全正确。SEC 通用质量失败无法由允许查看的评分投影确定具体隐藏答案，未据此补造原因。

Google RI-002 R2 修改公开集成测试项目的 POM 依赖／编码配置，实际 note、diff 和修改后 POM 均归档；未观察到改 Java 断言或设置跳过测试。这里的 `build/failed/failed_reasons.txt` 是公开题目要求模型生成的交付，不是隐藏 verifier 答案。因此可以说明未见改断言／跳过测试，不能笼统声称“没有改测试相关文件”。视频 RI-001 成功候选中的两个原生 pyc 属于已评冻结 bundle，未为清理而擅改候选。

## 请求、用量和费用

以下请求数按真实发出 fetch／供应商执行记录计；不是已确认账单调用数。修复的 79 个标题辅助请求意图因 4096 配置在 fetch 前被本地拦截，不计入已发送请求，也不凭此推断供应商实际账单。

| 阶段 | 已发送请求尝试 | HTTP 200 | 失败／传输错误 | 有完整 usage 的响应 | 已记录 total tokens |
|---|---:|---:|---:|---:|---:|
| 原生修复 | 1778 | 1721 | 57 | 1720 | 38,865,525 |
| 原题执行 | 2178 | 2148 | 30 | 2148 | 94,651,450 |
| 初始连通探针，不计实验样本 | 1 | 1 | 0 | 1 | 34 |
| 合计 | 3957 | 3870 | 87 | 3869 | 133,517,009 |

修复原生 usage 字段为：inputTokens 10,423,104，cacheReadTokens 24,686,592，outputTokens 3,755,829；DSH 的 totalTokens 已包括这三部分，不能再将缓存输入重复加到总量。57 个传输错误和 1 个 HTTP 200 但没有完整原生 assistant usage 的修复响应，用量未知。后者为 single-sec-financial-report-RI-002 R2，外层预算停止时 34 次 HTTP 200 对应 33 份完整原生响应。执行的 30 个 HTTP 500 用量也未知。合计 88 个请求缺少完整 usage，未补成 0；133,517,009 是已记录量，不是完整账单量。

| 执行分组 | 请求 | 根步 | 已记录 tokens | canonical 执行费用估算（美元） |
|---|---:|---:|---:|---:|
| location | 298 | 294 | 11,727,972 | 8.0583874 |
| single | 1880 | 1868 | 82,923,478 | 44.2074885 |
| 执行合计 | 2178 | 2162 | 94,651,450 | 52.2658759 |

52.2658759 美元仅为 canonical 执行结果中的估算投影，部分原生续跑使用 SDK 累计估算；它不是供应商实际账单，也不含未知修复费用，因此不是整批总价。供应商执行回显只提供 total tokens，输入／输出拆分未知。所有阶段实际账单、错误请求是否计费及缺失用量仍未知。宿主聊天／审计的 Codex 用量不计入这批 Tatu 实验调用。

## 真实产物、清理和证据位置

79 个 canonical 执行目录各保留真实 `pre-verifier-workspace.tar.gz`。最终逐份读取整个压缩文件计算 SHA-256，并流式解析完整 tar；全部非空、可解析，总计 13,144,476,938 字节。满分交付的真实 CSV／JSON／MP4、财报 answers.json、规划文件及 Google note／diff／POM 已按各轮证据核对。归档存在不代表每个低分轮都完成了题目交付，没有事后生成产物冒充原件。

控制器及 22 条 status 均已结束，canonical 有效目录恰为 79 个。旧异常执行包及已合并的旧续段按简记精确删除，专属停止容器／网络已清理；最后实际 Docker 清单没有本批 `csu-*` 容器。已核对 9 个零容器引用的对应镜像 ID／单一 tag 后，使用非强制 `docker image rm --no-prune` 删除，并逐个验证 tag 和 ID 均不存在：8 个已完成任务镜像及 `controlled-skillhone-repair:20261102`。没有全局 prune，没有删卷，没有删除无关容器或基础镜像。

全部有效候选、正常低分、正式归档、原生修复来源、费用简记及固定 OpenHands 共享缓存保留。删除简记中的首个失败 setup 曾使用 location-dialogue-parser/round-1 路径；该路径后来承载有效原生 R1，未按过期路径误删。停止镜像清理收据不会使旧 environment-ready 记录变成当前镜像仍存在的证明。

主证据目录为 `/home/linyuanjing/controlled-skillhone-unified-20261102`，Windows 可通过 `\\wsl.localhost\Ubuntu\home\linyuanjing\controlled-skillhone-unified-20261102` 访问。

| 文件／目录 | 内容 |
|---|---|
| plan.json | 本批冻结协议与 22 条输入 |
| final-audit/summary.json | 紧凑汇总、逐轮结果索引及限制 |
| final-audit/matrix.json | 22 条输入、79 个 canonical 轮次、分数／根步／请求／费用投影 |
| final-audit/exposure.json | 版本、正文预载、60 步／guard、续跑事件及格式核验 |
| final-audit/repair.json | 79 个原生修复来源、候选／commit、实际全文读取、预算与调用用量 |
| final-audit/behavior.json | 正常低分、公开材料、工具行为及隔离边界核查 |
| final-audit/artifacts.json | 79 个真实归档的路径、大小、SHA-256 和完整 tar 解析结果 |
| final-audit/cleanup.json | 9 个镜像的精确 ID、删除结果和不存在验证 |
| acceptance/ | 后续新增满分的独立验收简记；先前满分沿用原证据并纳入本次逐轮核查 |
| evaluations/、candidates/、final/ | 唯一有效执行结果、逐轮候选和最终候选 |
| native-resume-history.jsonl、discarded-attempts.jsonl、resource-cleanup.jsonl | 已清除异常资源的短记录；不是额外实验轮次 |

本报告不包含凭据、隐藏评分答案或其他 trial 的输入正文。本批结果没有自动推送 GitHub。实验、真实产物和候选验收已完成；巡检 `skillhone-22-30` 已由自动化工具删除，并确认其本地 automation.toml 不存在，聊天保持开放。


发布注记：本文记录验收结束时的事实。随后用户明确授权用本批结果替换 GitHub 原目录；公开副本见 results-summary.json，原始全量工作区和完整轨迹仍仅在本地保留。
