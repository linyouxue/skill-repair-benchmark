# Evidence index

本目录保存 SkillTTA 的真实修复过程，以及同一冻结 Skill 在原 22 张小票任务上的三次独立最终执行证据。

## 目录入口

- `repair/`：37 个多模态 diagnosis、synthesis、两轮 repair 的请求审计、响应与收据；`adapter_audit.json` 汇总实际图片内容块、模型交付、HTTP 状态及凭据检查。
- `diagnosis_package/`：本轮允许使用的诊断包 README、索引、图片映射和 allowed feedback。
- `implementation/`：本轮实际使用的 SkillTTA runner、最终 rollout runner、adapter、provider 和 65 父迭代执行器实现快照。
- `final_runs/run_01/`、`run_02/`、`run_03/`：每次独立运行的原始执行元数据、真实 `artifacts/stat_ocr.xlsx`、评分文件、ACP 轨迹和完整 LLM 轨迹。

每次最终运行的主要文件：

- `executor_request.json`、`config.json`：模型、冻结 Skill 清单、65 父迭代上限及运行配置。
- `result.json`、`benchmark_result.json`：实际迭代、终止原因、Skill 挂载/调用核验与执行结果。
- `trajectory/acp_trajectory.jsonl`：完整 ACP 轨迹；`agent/acp_trajectory.jsonl` 为执行器原生副本。
- `trajectory/llm_trajectory.jsonl.gz` 或其无损分卷：完整 LLM 请求/响应轨迹。
- `artifacts/stat_ocr.xlsx`：该次运行实际生成的原 Excel。
- `verifier/accuracy.json`、`verifier/ctrf.json`、`verifier/reward.txt`：固定 44 字段的实际评分记录。
- `trainer/`、`results.jsonl`、`rewards.jsonl`、`timing.json` 等：执行器原生辅助记录。

## 大轨迹无损分卷

Run 01 的 LLM 轨迹直接保留为 `run_01/trajectory/llm_trajectory.jsonl.gz`。Run 02 和 Run 03 的 gzip 文件超过 GitHub 单文件 100 MB 限制，因此仅做无损字节分卷，内容未删减或转写。

在对应 `trajectory/` 目录执行：

```bash
cat llm_trajectory.jsonl.gz.part-* > llm_trajectory.jsonl.gz
shasum -a 256 llm_trajectory.jsonl.gz
gzip -t llm_trajectory.jsonl.gz
```

- Run 02 重组后 SHA-256：`55f6d2649106156e72603fee3ee7e5859e18cf2033240a983d639e30fd51ccda`（`part-00` 至 `part-04`）。
- Run 03 重组后 SHA-256：`a0882310dafd0f2b9231ff493a64f086357073abb7fa4b49de7832241d24f623`。为提高 GitHub 上传可靠性，`part-02` 与 `part-03` 又按连续字节细分为带字母后缀的小片段；仍按上述 `part-*` 通配符的字典序拼接即可。

## 修复过程中的重试说明

- 第 31 个诊断窗口曾发生连接重置；使用同一输出目录只重试该失败窗口，最终 37/37 个诊断窗口均成功并保留各自记录。
- Repair round 2 首次响应的 `finish_reason=length`，原请求、截断响应和收据保留在 `repair/model_calls/repair-r2/`；随后使用紧凑请求重试，成功记录位于 `repair/model_calls/repair-r2-retry/` 和 `repair/repair_round_2_retry.json`。
- API key 与认证头未写入请求记录；提交前凭据扫描结果同时记录于 `repair/adapter_audit.json`。

## 边界声明

修复仅使用原 22 图、原 Task、原 Skill 和诊断包允许反馈；未读取 oracle/reference 答案或 verifier 断言，未使用 group2 做修复或选版。三次最终执行均使用相同执行器挂载哈希，且 `skill_bundle_mounted=true`、预加载 Skill 数为 0、`skill_exposure_verified=true`。Run 02 达到 65 轮并以 `max_iterations` 结束，作为普通 FAIL 原样计分和保留。
