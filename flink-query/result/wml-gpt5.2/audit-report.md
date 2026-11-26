# WML + GPT‑5.2 Flink 运行审计

## 环境与评分器

Flink 1 项任务、4 组数据的官方 R2 参考程序均通过。使用发布归档的 Java 源码，保留各组原始 POM、数据及 verifier，在 Docker 中断网执行 `bash /verifier/test.sh`。四组退出码均为 0，CTRF 全通过，连续准确率均为 1.0。镜像架构为 Linux amd64，限制为 2 vCPU 和 4 GiB。四组的 root 与 agent 也分别通过断网 Maven 编译和 Flink 运行。证据见 `reference-{repair,scale,stages-r03,combined}/` 中的 `container.txt`、`image.txt`、`verifier.log`、`exit`、`SHA256SUMS`、评分和实际输出。首次 stages 对照误用了未完成的 R2 前序工作区，日志保存在 `reference-stages-unfinished-source/`。正式验收使用发布索引登记的完成态 R2 工作区。

历史容器经过清理。历史镜像 ID 前缀来自构建日志，当前参考镜像完整 ID 来自 Docker inspect。历史完整镜像 ID 及层清单无法逐条追溯。同一基础镜像和各组任务导出重建后通过验收。补跑使用同一参考验收镜像完整 ID。官方 Python verifier 读取 Maven/Flink 生成的输出，无 pytest 或浏览器步骤。未观察到 verifier 代码自身崩溃或兼容性错误。模型容器的 `pdftotext`、`pypdf` 缺失曾影响诊断命令，属于辅助工具缺失，相关尝试也有可读取的 CSV。必需的 Maven、Java、Flink 通过独立验收。CTRF 额外记录一行 delivery_contract，官方连续准确率仍按正确决策数除以评分分母计算。

## 采用结果

| Attempt | 官方评分 | 主要错误 | 实际输出 |
|---|---:|---|---|
| scale-04 | 1917/2648 = 72.39% | 输出 727 个应排除作业，另有 4 个正例计数错 | 30635 字节，2015 行合法 tuple |
| stages-07 | 958/1324 = 72.36% | 输出 362 个应排除作业，另有 4 个正例计数错 | 15292 字节，1006 行合法 tuple |
| combined-04 | 2536/2648 = 95.77% | 输出 108 个应排除作业，另有 4 个正例计数错 | 20952 字节，1396 行合法 tuple |

泛化三组等权平均 80.173716%。严格通过 0 组。有效运行可以在正常完成和得到可复核评分的同时判失败。基础设施错误产生的零分不参与模型失败统计。

三条采用运行使用 OpenHands、GPT‑5.2 指定路由与端点、60 次迭代上限、相同的冻结 Skill。冻结 bundle 共 26 文件。运行快照逐文件符合原候选，ACP 第 2 行启动提示和执行器元数据均记录了两项 Skill 和相同预载哈希。自动目录提取器误识别为 Claude Code，人工逐项查看的动作由 AI 辅助完成。三条轨迹请求 HTTP 状态均为 200，实际迭代数按 scale、stages、combined 分别为 32、23、26。正常结束由最后的结构化 finish、ACP 最终消息和 end_turn 共同证明。finish 属于终止工具，与需要单独返回执行结果的工具调用不同。

scale ACP 第 42–43 行成功重跑并读取了本地输出。stages 第 26 行本地命令返回 1，第 29–32 行修改并重新编译、读取源码和核对两种类型，最终只声明编译成功。随后官方 verifier 成功执行并生成可读取输出。combined 第 34–35 行早期尝试失败或软超时，第 36–40 行重新生成样本、运行并读取输出。三组评分所用的正式 `verifier/actual-flink.txt` 是 agent 结束后由官方 verifier 执行其提交代码生成。原始 Java/JAR 没有作为独立产物导出，产物存在证据限于真实工具回执、编译日志及 verifier 的输出，无法另外下载原始源文件复验。分数已用同一官方评分器重算。

## 历史 attempt 与重跑关系

| Attempt | 判定 | verifier 和奖励 | 后续取舍 |
|---|---|---|---|
| repair-01 | 环境配置无效，OpenHands 不接受 xhigh ACP 配置 | 未评分 | repair-02 移除不兼容的显式参数 |
| repair-02 | Docker 本地镜像标签不存在 | 未评分 | repair-03 恢复镜像 |
| repair-03 | 两次 HTTP 500，加上 3600 秒空闲超时 | 未完成的程序被 verifier 记录为 0，不采纳 | repair-04 重跑 |
| repair-04 | 异常结束。11:15:25 最后一条模型响应以文本模拟工具请求，ACP 第 8 行承诺继续查 schema，第 9 行直接 end_turn | Maven 报缺 JobEvent 和 TaskEvent，未生成正式输出，记录为 0，不采纳 | repair-08 和后续确认性重跑 |
| stages-04 | HTTP 500 与空闲超时 | 未完成的程序被 verifier 记录为 0，不采纳 | stages-05、06、07 |
| stages-05、06 | Compose 清理镜像标签后重试找不到本地镜像 | 未评分 | 重建同配方镜像并采用 stages-07 |
| repair-08 | 三次 HTTP 500 和空闲超时 | 编译失败并记录 0，不采纳 | repair-08-retry02 |
| repair-08-retry02 | HTTP 500、空闲超时及末尾未完成的执行调用 | Flink 程序无可执行拓扑，记录 0，不采纳 | repair-09 |
| repair-09 | 最后一条确认性重跑，状态以 audit-summary.json 为准 | 保留原始记录 | 使用同一已验收镜像、模型、端点、预算和 Skill |

`repair-08-retry03` 是一次镜像启动前预检失败。Docker 清理移除了原 tag，已从留存的同一镜像 ID 恢复 tag，再以 repair-09 启动。该预检保留日志，未生成模型 attempt。历史修复中的 xhigh 到默认路由、镜像恢复及重建均有配置差异记录，无法宣称相对于所有早期尝试零差异。以 repair-04 为确认性补跑的有效配置基线。没有修改任务内容、输入数据、Gold、评分代码或模型产物。

逐项的绝对结果及轨迹路径、哈希、分数、镜像证据、工具调用计数和 HTTP 状态见 `attempts.json` 和 `audit-summary.json`。在实验根目录可运行 `python3 audit/audit_runs.py` 和 `python3 audit/finalize.py` 重建审计汇总。官方快检只核对证据结构，不能识别提前结束的文本伪工具请求，也不能代替非 200 和空闲超时的专项判定。

## 审计结论

4 个评测条目，3 个有效结果，0 个严格通过，3 个有效失败，1 个无有效结果。共 13 次已结束的模型 attempt，9 次基础设施无效，1 次额外的异常结束，6 次有评分记录但未生成正式输出。审计新增 3 次补跑，另保留一次启动前预检失败。

repair-09 已结束。Agent idle for 3600s with no new tool call, message, or thought (last activity 3600s ago, 14 tool calls so far)。轨迹 HTTP 状态 {'200': 7, '500': 1}。三次审计补跑均已结束，repair 标为无有效结果。泛化平均仅使用三组各一条通过审计的成绩。

异常轨迹共 6 次，其中空闲超时的尝试同时计入基础设施无效。全实验共 9 次模型重跑，其中本次审计新增 3 次。未产出评分的启动失败未计入 6 次有评分但缺输出。

## 配置核对补充

历史任务导出的运行配置将上游模板的 4 vCPU 调整为云机可用的 2 vCPU，并添加各 split 的本地镜像标签。内存上限 4096 MiB。此次审计和确认性重跑沿用该配置。早期模型 attempt 的 reasoning effort 配置存在从 xhigh 到默认值的差异。用于最终泛化统计的三次 attempt 均使用模型路由 `vllm/gpt-5.2@AZUREOPENAI-default`、原指定中转地址、OpenHands 固定提交 `2df8a2835d3f1bd2f2eadf5a7a2e1ad0dfb0d271` 和 60 次迭代上限。审计补跑的基线是 repair-04。其原镜像已清除，同配方重建后使用参考验收通过的完整镜像 ID。该差异在重跑映射中保留。

复现参考验收请在实验根目录执行 `bash -x audit/reproduce-reference-check.sh repair scale stages combined`。该脚本使用另建的参考输出目录。中转接口冒烟请求及后续 HTTP 500 的响应时间分别记录在 `provider-preflight.json` 和相应 LLM JSONL。全部复核由程序和 AI 辅助完成。
