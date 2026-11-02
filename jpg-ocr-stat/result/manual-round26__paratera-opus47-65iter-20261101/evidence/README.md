# 证据入口

- `repair/`：真实保留的人工修复记录、已公开历史材料链接，以及本次生成的原版到Round26差异；修复对话缺失与材料接触边界明确披露。
- `final_runs/run_01`至`run_03`：三条独立原题执行的原始配置/result/benchmark_result、完整ACP、无损XZ完整LLM与trainer记录、实际原Excel、原评分和评分前工作区归档。`xz -dc trajectory/llm_trajectory.jsonl.xz`可恢复原JSONL；没有删历史、图像或响应。
- `final_runs/summary.json`：已有验收投影、运行身份、44字段成绩、同冻结版本核对、Excel字节一致性及压缩往返SHA。
- `execution/`：当时三个独立原题请求。真实65上限同时见各run的`config.json`、`result.json`与ACP；不修改全仓库默认执行器。

run_01的根`result.json`和`benchmark_result.json`保留首次评分环境错误。模型57步自然完成、工作簿与评分前tar已经产生；第一次仅评分补验又遇Ubuntu索引同步错误，其标识/原因/零新增模型调用见`discarded-verifier-attempts.json`。有效评分在`run_01/verifier-only-02/`，原生补验result、benchmark_result、provenance和verifier均保留。该补验无新模型调用，不是新的独立执行。首次错误元数据不改写成成功，废弃补验原件不重复上传。

run_02/03均正常达到65步上限，保留`max_iterations`和全部成绩，未为追求自然结束或满分重跑。run_03为43/44，正常错误计入均值。原Excel从各自`artifacts/pre-verifier-workspace.tar.gz`的`./workspace/stat_ocr.xlsx`按字节导出，并与已有本地交付一致，没有人工补齐。

评分前tar原样保留，里面的原图/OCR工作文件只是原生证据归档，不作为新增修复材料；不另复制已发布的原图。只提交本批原22票结果；group2结果按独立泛化目录处理。此次发布新增模型调用0、verifier调用0，历史实际费用未知。
