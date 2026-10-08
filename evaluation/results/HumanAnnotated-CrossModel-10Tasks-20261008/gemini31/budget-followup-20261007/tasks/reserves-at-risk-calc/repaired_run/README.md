# reserves-at-risk-calc: FAIL 1/5

上限200 parent；实际200 parent / 201 provider；停止原因 `max_iterations`。

LLM原始请求/响应在 `trajectory/llm_trajectory.jsonl.gz`，完整训练行在 `results.jsonl.gz`；gzip解压恢复原始字节。ACP保持未压缩，见统一可读轨迹索引。

本目录顶层 `result.json`、`benchmark_result.json`、`execution_summary.json` 和 `results.jsonl.gz` 保留发布控制面超时的原始infra记录。有效评分以 [recovered-summary.json](verifier-recovery-20261007/recovered-summary.json) 和 [派生canonical](verifier-recovery-20261007/canonical) 为准：只用真实已归档产物运行冻结原verifier，未再调用模型。恢复receipt和原始infra审查分别保留。canonical中原轨迹/产物的重复符号链接以 `ALIASES.json` 索引，主副本仍在本运行目录。
