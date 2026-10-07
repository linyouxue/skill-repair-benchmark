# flink-query: FAIL 2/3

上限100 parent；实际68 parent / 70 provider；停止原因 `end_turn`。

LLM原始请求/响应在 `trajectory/llm_trajectory.jsonl.gz`，完整训练行在 `results.jsonl.gz`；gzip解压恢复原始字节。ACP保持未压缩，见统一可读轨迹索引。

评分见 [execution_summary.json](execution_summary.json)；真实预verifier输出位于 `artifacts/pre-verifier-inputs.tar.gz`，停止容器补齐的诊断另在 `artifacts/post-verifier-diagnostics`。
