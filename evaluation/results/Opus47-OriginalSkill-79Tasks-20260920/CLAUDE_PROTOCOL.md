# Claude protocol：claude-opus47-openhands-v1

这份协议用于本组 SkillsBench 的 Claude Opus 4.7 实验，与 GPT-5.2 实验共用统一 BenchmarkExecutor。机器配置为同目录 `claude_protocol.json`，本次 runner 实际读取该文件。

## 1. 官方依据与采用范围

已核查 SkillsBench v1.1 对应 commit `b63b7b2850226b6aa4fb5929a8c1ac7bc4d9a6af` 的 [with-skills Claude 配置](https://github.com/benchflow-ai/skillsbench/blob/b63b7b2850226b6aa4fb5929a8c1ac7bc4d9a6af/experiments/configs/withskills/claude-code.yaml) 和 [without-skills Claude 配置](https://github.com/benchflow-ai/skillsbench/blob/b63b7b2850226b6aa4fb5929a8c1ac7bc4d9a6af/experiments/configs/without/claude-code.yaml)。二者固定 Claude Code 2.1.19、Claude 4.5 系列，未显式指定 effort、temperature 或 thinking budget。

本组沿用“运行配置不额外覆盖 effort”的做法，模型按实验要求替换为 Opus 4.7，harness 保留 OpenHands。**本协议不是官方 Claude Code 配置的逐项复现，也不应命名为 SkillsBench 官方 Opus 4.7 protocol。** 官方 YAML 的 5 次尝试、64/128 并发未用于本次实验。

## 2. 固定模型与执行器

| 项目 | 值 |
|---|---|
| 组内协议名称 | `claude-opus47-openhands-v1` |
| BenchmarkExecutor `protocol` 参数 | `skillrepair-v1` |
| 模型路由 | `openrouter/anthropic/claude-opus-4.7` |
| API provider | OpenRouter；密钥由环境变量 `OPENROUTER_API_KEY` 提供 |
| Agent / sandbox | OpenHands / Docker Linux amd64 |
| CLI commit | `2df8a2835d3f1bd2f2eadf5a7a2e1ad0dfb0d271` |
| OpenHands SDK / tools | 均为 `1.28.1` |
| ACP reasoning_effort | Python `None` / JSON `null` |
| LLM effort 环境覆盖 | 不设置 `LLM_REASONING_EFFORT` |
| SDK 默认 effort | 固定 SDK 源码默认 `high`；请求层结果需从轨迹另行确认 |
| temperature / top_p | 本协议不额外覆盖，以固定 SDK 与实际请求为准 |
| 配置的输出 token 上限 | `LLM_MAX_OUTPUT_TOKENS=32768`；2026-09-20 用户授权调低，历史尝试为 128000，详见第 6 节 |

不要将组内协议名称传给 `BenchmarkExecutor(protocol=...)`；该参数仍是 `skillrepair-v1`。`reasoning_effort=None` 表示不通过 ACP 设置 effort，**不表示关闭 Claude 推理，也不表示 max**。此前传入 `max` 会在首个模型请求前被 ACP 拒绝。

最小调用示例（使用本组已交付的统一执行器环境）：

```python
import os
from benchmark_executor import BenchmarkExecutor

os.environ.pop("LLM_REASONING_EFFORT", None)
os.environ["LLM_MAX_OUTPUT_TOKENS"] = "32768"
executor = BenchmarkExecutor(
    tasks_root="/path/to/frozen/tasks",
    jobs_root="/path/to/results",
    model="openrouter/anthropic/claude-opus-4.7",
    reasoning_effort=None,
    protocol="skillrepair-v1",
    experimental_text_only_retry_limit=1,
)
result = executor.run(
    task_id="azure-bgp-oscillation-route-leak",
    method_id="opus47-original-skill",
    stage="original-skill-screening",
    rollout_id="azure-opus47-r001",
    condition="original-skill",
    skill_bundle=None,
)
```

代理、固定 runtime archive 和任务环境由组内 runner 配置。凭据不写入协议或交付包。跨机器必须保持上述版本和任务副本，不得仅凭模型名称相同就合并结果。

## 3. 任务和预算

- 79 题：原 87 题排除 `civ6-adjacency-optimizer`、`financial-modeling-qa`、`invoice-fraud-detection`、`manufacturing-codebook-normalization`、`quantum-numerical-simulation`、`setup-fuzzing-py`、`shock-analysis-demand`、`xlsx-recover-data`。
- 本批只跑 `original-skill`，使用题目附带的官方原始 Skill。此前人工修复 bundle 不注入。
- 每题 1 条有效 rollout；正常 FAIL 不重复抽样。基础设施异常最多补跑 1 次；经过证据复核的启动器零调用失败保留为 void 并恢复有效尝试槽位。
- 最大并发 3 题，每题独立进程和目录；Docker 启动加跨进程锁。原有大内存／多 CPU 独占和本机资源不足暂缓策略继续生效。
- 每个 Step 共 60 次 parent iterations，最多 1 次 text-only continuation，共享该预算，不另加 60 次。`jpg-ocr-stat` 按已确认例外使用 65 次，该覆盖由本批 worker 完成。
- 禁用 Agent 子代理。每次 LLM 请求 watchdog 为 3600 秒，空闲 watchdog 为 3600 秒，总墙钟 watchdog 为 21600 秒；这些用于终止挂起，parent iterations 是工作预算。
- 用户明确要求本批费用无上限，不执行费用核对门禁或费用待核对调度提示；费用以原始响应 `usage.cost` 作为结果数据记录，仍遵守本协议的有限尝试次数。磁盘空闲低于 10 GiB、服务商实际返回余额不足或连续 3 次基础设施失败仍会暂停。
- 2026-09-19 用户确认：24 GiB 的 `fix-druid-loophole-cve` 由用户在服务器自行执行，本机自动运行其余 78 题；合并报告时必须另收服务器结果，不能将本机完成视为全部 79 题完成。

以下任务差异已在本次独立任务副本中执行，具体 patch 随 `task_corrections.patch` 交付：enterprise-information-search 的 tokens 类型示例修正；simpo-code-reproduction 的 verifier fallback 新增 `rich==11.2.0`；organize-messy-files 的 verifier 只扫描任务输入文件名范围。其余继承的环境修改在 `manifest.json` 中列出。使用这些修正后的结果必须注明版本差异。

## 4. 计分与交付证据

每题保留原始模型／工具轨迹、输入 Skill 快照、`result.json`、`benchmark_result.json` 和 verifier 日志，汇总 `summary.json`。记录 PASS/FAIL、reward、实际模型身份、实际 effort 字段、token 用量、费用、工具调用次数、`n_skill_invocations`、终止原因及是否有产物导出缺口。

基础设施正常、模型与工具链正常且 verifier 正常执行时，采用 verifier 判决；正常执行但无判决按 FAIL 计分，原始 reward/task_passed 仍保留 null。基础设施／API／安装失败属于 invalid，不进入有效 PASS/FAIL 分母。有效通过率为 `PASS / (PASS + FAIL)`，同时报告目标 79 题中已完成的数量和未完成原因。轨迹完整性字段单独不足以推翻已有有效 PASS。

Skill 正文预加载与真实 `invoke_skill` 调用分别记录，不能把预加载算作一次工具调用。当前统一执行器采用持久上下文预加载完整 Skill，和官方 Claude Code 的原生发现方式有差异。

恢复成功必须检查真实 OpenHands prompt 已执行、至少一次模型请求成功及一次真实工具调用；原始 API 的单独 HTTP 200 或单独看到容器均不足以证明本次 effort 修复生效。

## 5. 本次恢复验证

北京时间 2026-09-19 17:17:53 的启动快照中，adaptive-cruise-control、azure-bgp-oscillation-route-leak、citation-check 已分别记录 7、2、3 次模型交换，已检查的响应均为 HTTP 200，三题均已出现真实工具调用。Azure 已完成读取输入 JSON 文件的 terminal 调用。完整脱敏回执为 `protocol_start_evidence.json`。

已检查的 `/v1/chat/completions` 轨迹请求体只有 `model/messages/input/tools/stream` 字段，模型记录为 `anthropic/claude-opus-4.7`；未记录显式 `reasoning_effort`、`reasoning`、temperature 或输出 token 上限。因此，可确认本次采用“不显式覆盖 effort”的配置并已执行成功；不能由 SDK 的默认 `high` 推断 provider 实际接收了 high，也不能声称 128000 已在线路层验证。后续若要求固定 provider effort 数值，应单独升级协议并验证传参，不与本版本结果混写。

## 6. 2026-09-20 输出上限变更

用户明确要求调低后继续运行。新尝试单次输出上限从 128000 降至 32768；不改变上下文窗口或整题迭代预算。历史 789 次已记录用量的响应平均输出 536.19、P99 为 5072、最大 15570 tokens。35 个有效任务平均累计输入 519500.06、输出 8043.43 tokens；输入含多轮重复上下文，缺失 usage 的响应不纳入统计。完整统计为 `token_usage_before_limit_change.json`。

此前 OpenRouter 402 明确证实旧请求额度为 128000；第 5 节描述的是更早的代理层观察限制。新旧尝试分别记录 `max_output_tokens`，旧协议和状态保存在 `recovery_snapshots/user-lowered-output-limit-20260920/`。已有有效 PASS/FAIL 不重跑；本批是混合输出上限的运行，合并报告必须注明这个变更。

## 7. 用户授权的基础设施恢复轮（2026-09-20）

用户要求：有完整真实产物的异常任务修复 verifier 后仅补验；中途失败或无可恢复产物则重跑。本轮清单见 `infrastructure_recovery_plan.json`，10 题的两次旧尝试均无导出产物文件，原容器已删除。因此各追加一次模型补跑，沿用32768输出上限及原技能、评分、模型和固定OpenHands版本；不会改写已有有效PASS/FAIL。后台 `recover_infra_after_batch.py` 等当前批次自然结束再接续，避免干扰正在运行的付费任务。

旧第二次尝试保留在 `historical_infrastructure_attempts`，全部原始目录不变，已知费用、部分费用和未知金额继续纳入账目；新尝试编号为3，使用现有调度器的重试槽位。全局默认尝试限制仍保留，本轮仅对明确清单追加一次，不能无限重试。

修复包括：Ubuntu20.04的GLIBC不能载入缓存里的cryptography二进制，改用PyPI官方同版本50.0.1的manylinux_2_28 wheel，原OpenHands archive及CLI/SDK/tools版本不变；JPG的65次预算同步到ACP校验模块；复用原先固定uv0.9.7验证器缓存。ADA的旧日志仅保留空错误而无完整异常栈，不能声称根因已完全确定；新运行在验证前保存真实输出，并只对验证准备阶段的TimeoutError重试一次。四题的真实输出在验证准备之前导出为 `artifacts/pre-verifier-inputs.tar.gz`，用于将来仅补验，不从轨迹文本重建或冒充原始文件。

已执行零模型验证：Ubuntu20.04导入固定OpenHands成功；JPG三处迭代常量均为65；迁移历史尝试后费用下界不变；真实容器内产物打包导出并校验内容成功。

## 8. 充值后续跑（2026-09-20）

用户确认充值并要求继续；只读确认余额约48.37美元。6题第三次尝试均因OpenRouter额度中断、无完整导出产物，逐题追加一次编号4的尝试，旧尝试保留在historical_infrastructure_attempts且费用下界不变。另3题继续其尚未执行的编号3尝试；69个已有有效结果不变。仍为最多3题并行、输出32768、固定本地OpenHands和原评分，不启用无限重试。具体清单及充值恢复证据见claude_protocol.json的credit_recovery_resumptions与recovery_snapshots。
