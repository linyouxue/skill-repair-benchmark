# Evidence index

- `repair/`：37 个诊断窗口、综合诊断与两轮修复的真实请求/响应。`model_calls/*/request.json.gz` 是无损压缩的实际请求；相邻 `request_audit.json` 与 `receipt.json` 记录图片块数量、媒体类型、模型、路由和 HTTP 状态。
- `final_runs/run_01/`：`jpg-ocr-stat-skilltta-opus47-aigw-v2-r012`，23/65，44/44，字段正确率 1.0。
- `final_runs/run_02/`：`jpg-ocr-stat-skilltta-opus47-aigw-v2-r022`，32/65，42/44，字段正确率 0.9545454545454546。`verifier/test-stdout-infra-failure.txt` 是首次评分器基础设施错误；`verifier/test-stdout.txt`、`accuracy.json`、`ctrf.json`、`reward.txt` 和 `retry_metadata.json` 是对同一原 Excel 的零模型调用评分重试。
- `final_runs/run_03/`：`jpg-ocr-stat-skilltta-opus47-aigw-v2-r023`，24/65，44/44，字段正确率 1.0。
- `attempts/`：早期基础设施失败与较早有效尝试，仅作完整过程披露，不计入三次最终执行。

每个最终运行目录均保留执行器原生 `executor_request.json`、`config.json`、`result.json`、`benchmark_result.json`、`trajectory/acp_trajectory.jsonl`、`trajectory/llm_trajectory.jsonl`、`artifacts/stat_ocr.xlsx` 与 verifier 文件。`result.json` 未为整理或评分重试而改写。

三次执行均记录相同冻结 bundle 哈希：`sha256:d477760d2d0c1da2196b027a473f0174194bae28803824eceed8f2bee394844f`，相同上游模型和 Tatumass Anthropic-compatible 路由。为修复 Docker Desktop 宿主代理不可达问题，后两次将必经 LiteLLM 轨迹代理部署在任务容器内；该变更不改变上游模型、任务输入、冻结 Skill、65 轮限制或评分逻辑。
