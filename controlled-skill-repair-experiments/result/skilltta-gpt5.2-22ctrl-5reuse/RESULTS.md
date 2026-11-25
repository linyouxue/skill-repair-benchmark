# 结果与审计状态

22条控制条件，5条无提示历史复用。模型队列已结束；逐项复核待办：0。严格有效通过0，严格有效失败12，其余10条为无有效结果、证据不足或verifier争议。有效结果不等于通过；未获证条目不进入模型有效失败数。

|实验ID|状态|采用attempt|采用奖励|原历史奖励（未直接采用）|
|---|---|---|---:|---:|
|location-data-to-d3|valid_failure|attempt-005/task__449fa769|0.0|1.0|
|location-dialogue-parser|verifier_semantics_disputed|—|—|0.0|
|location-flink-query|retry_cap_no_valid_result|—|—|0.0|
|location-manufacturing-equipment-maintenance|historical_resource_evidence_insufficient|—|—|0.0|
|location-pddl-airport-planning|historical_resource_evidence_insufficient|—|—|0.0|
|single-fix-build-google-auto-RI-001|retry_cap_no_valid_result|—|—|0.0|
|single-fix-build-google-auto-RI-002|retry_cap_no_valid_result|—|—|0.0|
|single-fix-build-google-auto-all|retry_cap_no_valid_result|—|—|0.0|
|single-flink-query-RI-001|valid_failure|attempt-009/task__8628a96d|0.0|0.0|
|single-flink-query-RI-002|retry_cap_no_valid_result|—|—|0.0|
|single-flink-query-all|valid_failure|attempt-003/task__29f2ca0d|0.0|0.0|
|single-manufacturing-equipment-maintenance-RI-001|valid_failure|attempt-004/task__56471cbf|0.0|0.0|
|single-manufacturing-equipment-maintenance-RI-002|valid_failure|attempt-004/task__fbede960|0.0|0.0|
|single-manufacturing-equipment-maintenance-all|valid_failure|attempt-004/task__6afc21bc|0.0|0.0|
|single-sec-financial-report-RI-001|valid_failure|attempt-004/task__2b76a86c|0.0|0.0|
|single-sec-financial-report-RI-002|retry_cap_no_valid_result|—|—|0.0|
|single-sec-financial-report-RI-003|valid_failure|attempt-005/task__9ee8e6b3|0.0|0.0|
|single-sec-financial-report-all|valid_failure|attempt-004/task__6efbc686|0.0|0.0|
|single-video-silence-remover-RI-001|retry_cap_no_valid_result|—|—|0.0|
|single-video-silence-remover-RI-002|valid_failure|attempt-002/task__76e4f148|0.0|0.0|
|single-video-silence-remover-RI-003|valid_failure|attempt-002/task__909a75c6|0.0|0.0|
|single-video-silence-remover-all|valid_failure|attempt-005/task__927b8d7d|0.0|0.0|

无提示5题来源、原分和配置差异见 no_hint_controls/audit.json。历史5题原分为1通过4未通过；缺完整历史工作区及镜像证据，不能把它们升级为本轮严格有效结果。

所有原始尝试均保留在 attempts、historical_excluded 和审计来源记录中；8个不可读旧iCloud来源文件在COPY_PROVENANCE明确列出，未伪造恢复。部分中断尝试实际文件从保留容器只读取得，另见audit/interrupted_attempt_original_container。

D3确认006官方9/10检查通过，tooltip仅因缺.visible类名被判失败；只读实际verifier解释器/默认viewport探针确认opacity=1且ticker/name/sector可见，ETF隐藏，单列verifier选择器争议，未改分且未替换首次005的JS格式失败。

诊断/修复成功阶段88个请求响应的哈希已核验；其中2个条件的较早失败HTTP响应未完整保存，方法完整失败调用历史不能补造。

任务输入、Gold、verifier测试及评分未因本次补跑/整理而修改；已有环境安装入口修订另见audit/installer_diffs.json。

轨迹由原export_trajectory.py导出，index未手改；原始运行缺展示条件元数据时会归入unknown，真实条件以tasks/<trial>/audit.json和RUN_RECORD为准，未编造executor_request。
