# Controlled55 严格审计报告

审计时间（UTC）：2026-11-23T14:50:56.420151+00:00

本报告由 AI 辅助逐项核查生成，不是独立人工语义复核。冻结的原始实验目录未改写。55 组结果/ACP/模型轨迹/CTRF 共 220 份核心记录的 SHA-256 均与冻结包清单一致；恢复出的 675 份运行时/方法/候选 Skill 文件也全部一致。

**结论：不能声明 55 项全部满足本次严格要求。** 运行有效性、verifier 健康、任务通过以及产物归档可复核性分别判断。有效结果不等于通过，基础设施无效不能计为模型失败。

## 当前汇总

55 项逐项审计与 14/14 项确认性补跑已完成。执行/评分证据可采用 51 项：26 通过、25 失败；另 1 项 verifier 兼容性问题及 3 项补跑后无有效结果均未计作模型有效失败。

未解决条目：`location-data-to-d3`（SVG legend 检查异常，另有独立 tooltip 内容失败）；`flink-query__all_faults`（确认运行的模型原始响应有 API 500/all_endpoints_unavailable）；`single-manufacturing-equipment-maintenance-RI-001__condition_baseline` 与 `single-manufacturing-equipment-maintenance-RI-002`（确认运行再次以工具 JSON 普通文本提前结束）。详见 UNRESOLVED_FINDINGS.json。

本轮最终采用结果中，24 项找到了至少部分可直接读取的真实产物，27 项仍无可直接复查的产物归档。**不能把执行/评分有效等同于全部严格审计条款已满足。**

```json
{
  "audit_time_utc": "2026-11-23T14:50:56.420151+00:00",
  "total_experiment_entries": 55,
  "repair_entries": 22,
  "control_entries": 33,
  "fresh_environment_references_passed": 8,
  "fresh_environment_references_failed": 0,
  "historical_selected_passes": 24,
  "historical_selected_failures": 31,
  "historical_premature_endings": 5,
  "confirmation_premature_endings": 2,
  "historical_missing_key_output_entries": 7,
  "historical_empty_flink_output_entries": 2,
  "historical_max_iteration_endings": 5,
  "valid_execution_results": 51,
  "valid_passes": 26,
  "valid_failures": 25,
  "selected_entries_with_verifier_compatibility_invalidity": 1,
  "no_valid_result_after_confirmation": 3,
  "unresolved_original_abnormal_endings": 0,
  "historical_failed_entries_with_tool_DNS_errors": 8,
  "historical_passed_entries_with_recovered_network_errors": 6,
  "infrastructure_influenced_unconfirmed_entries": 0,
  "entries_without_any_valid_execution_result": 4,
  "outer_confirmations_planned": 14,
  "outer_confirmations_launched": 14,
  "outer_confirmations_finished": 14,
  "confirmation_entries_running": 0,
  "internal_confirmation_rollout_results": 17,
  "invalid_internal_confirmation_rollouts": 4,
  "historical_nonselected_infrastructure_attempts": 12,
  "historical_attempt_directories": 60,
  "historical_result_files": 67,
  "historical_empty_artifacts_directories": 55,
  "historical_entries_with_retained_outputs": 15,
  "historical_entries_without_retained_outputs": 40,
  "audit_execution_review_complete": true,
  "selected_results_with_some_actual_outputs_opened": 24,
  "selected_results_without_direct_output_archive": 27,
  "all_required_artifact_files_reopened": false,
  "overall_strict_audit_satisfies_all_user_requirements": false,
  "limits": [
    "Some historical outputs are retained under verifier/; 40 entries have no identified output archive, so full post-hoc file/provenance checks remain incomplete.",
    "One D3 legend check has an SVG/HTML API compatibility exception; independent tooltip assertion also fails, so no pass is fabricated.",
    "AI-assisted evidence audit, not independent human semantic review."
  ],
  "group_counts": {
    "repairs": {
      "total": 22,
      "valid_execution_results": 20,
      "valid_passes": 7,
      "valid_failures": 13,
      "unresolved_or_verifier_invalid": 2
    },
    "controls": {
      "total": 33,
      "valid_execution_results": 31,
      "valid_passes": 19,
      "valid_failures": 12,
      "unresolved_or_verifier_invalid": 2
    }
  },
  "final_entries_excluded_for_provider_error": 1,
  "final_entries_excluded_for_abnormal_ending": 2
}
```

55 项历史正式结果的 reward.txt、CTRF 测试计数和官方评分公式已重新核算，全部与 result.json 奖励一致（reward_reproduction.json）。这只能证明评分可复算，不能替代环境、异常终止和产物有效性判断。

## 环境与 verifier

8 个基础任务均使用冻结记录对应的镜像 ID，重新运行参考解法并完成 verifier；8 项奖励均为 1。验收命令、退出码、完整日志及 SHA-256 在 reference/。dependency_probes.json 记录架构、解释器和依赖；verifier_dependency_pin_checks.json 对照官方脚本的明确 pytest/CTRF pin。Google 的 agent 非 root JDK 切换另有日志。D3 与 Google 参考解法只改用已缓存的官方依赖/官方 diff 作为离线传输，源代码差异与哈希在 reference_oracle_transport_changes.json；这些参考答案未提供给模型。

官方 test_outputs.py 均未更改。已验收运行与官方安装入口之间原有的 9 处依赖传输差异（8 个 test.sh、Google run_passed.sh）保存在 verifier-source-diffs/，包括预装依赖、固定解释器、停用历史 apt 更新和 DNS 重写；不得称为源文件逐字相同。本轮保持与冻结尝试完全一致，未修改这些入口或评分。

`location-data-to-d3`：`test_legend_completeness` 对 SVG legend 调用 `inner_text()`，触发 `Node is not an HTMLElement`。同时 `test_tooltips_non_etf_and_etf` 独立失败（non-ETF hover 后无可见 tooltip）。评分脚本按 pytest 整体成功给 1，否则给 0；即使忽略 legend 异常，独立 tooltip 失败仍会导致原规则奖励 0。本报告不修改 verifier，也不补写新分数；该项保留为带验证器缺陷的结果，不列入严格有效结果。

## 轨迹与重跑

55 条历史入选轨迹均核对 ACP、模型请求/响应、工具调用 ID、HTTP 状态、Skill 输入快照、预加载哈希和 verifier 原始测试报告。55 项的 RUN_RECORD 源 Skill 文件清单/哈希也均与实际 inputs/skills 快照一致（skill_condition_source_checks.json）。5 条提前结束有 confirmed_premature_endings.json 的逐条事件证据。另 2 条 Flink 正常结束但 verifier 明确记录 out.txt 缺失，安排一次确认性补跑。5 条历史 max_iterations=60 是预定预算终止，不单独算 ACP 异常或为了涨分重跑。

另有 14 条历史轨迹包含依赖下载 DNS 错误，其中 8 条最终失败，排除为基础设施影响待确认；6 条最终通过，记录已恢复故障。8 条失败中，single-flink-query-RI-002 已由缺产物确认性运行覆盖，因此另补 7 项。当前同镜像非 root 下载 pypdf/pandas/numpy 验收通过，之后才启动追加补跑。详见 historical_network_failures.json、agent_network_qualification.json。

每项只新建一个外层确认 attempt；冻结 CLI 原有的基础设施内部重试（最多 2 次）仍保留，每个内部 rollout 的结果也单独列出。不能把内部错误的 result.json 当成最终模型失败。AUDIT_POLICY.json 说明实际 CLI 重试策略；本次没有增加有效失败的重复测量。

## 产物核验的实际边界

历史 55 条的 artifacts/ 均为空，但 15 条在 verifier/ 中留存了 32 份真实产物（9 组视频及 JSON 报告、6 组 Google 分析和补丁），可直接读取，详见 historical_artifact_audits.json。其余 40 条未找到独立保存的任务产物；运行时 verifier/工具证据不能替代全部文件重新读取，不能用模型文字、评分 JSON 或 Gold 重建产物。

新 attempt 尽量从实际容器复制产物，并进行 JSON、源码、JAR/ZIP、文本格式及视频 ffprobe 读取。最早的 dialogue 与 location-flink 确认运行容器在评分后被执行器 prune，未能保留文件：存在性/解析证据仅来自工具轨迹与官方 verifier。后续加入评分后、停止前的原文件复制及本审计进程禁用 prune 的观测钩子；不生成或改写任何任务产物。

Flink 的测试会编译程序并生成 out.txt。源代码属于模型交付物；verifier 后生成的 JAR/输出有独立来源，不能错误声称所有文件在模型 end_turn 前已写出。

本报告的 valid_execution_results 是有足够轨迹/评分证据且未发现运行故障的执行结果数，并非所有用户严格条款均已满足的数量。缺少原产物归档或独立历史退出码时，完整可复核性仍有明确限制；不会把这些限制隐藏在通过率里。

## 逐项清单

| 实验 | 历史状态 | 本轮采用状态 | 奖励 | 采用 attempt | 失败类别 / 限制 |
|---|---|---|---:|---|---|
| data-to-d3__full_gold | valid_pass | valid_pass | 1.0 | data-to-d3__full_gold-attempt-001 | official_verifier_pass；runtime verifier/tool evidence; historical direct re-opening unavailable |
| data-to-d3__original | valid_pass | valid_pass | 1.0 | data-to-d3__original-attempt-002 | official_verifier_pass；runtime verifier/tool evidence; historical direct re-opening unavailable |
| dialogue-parser__full_gold | valid_pass | valid_pass | 1.0 | dialogue-parser__full_gold-attempt-002 | official_verifier_pass；runtime verifier/tool evidence; historical direct re-opening unavailable |
| dialogue-parser__original | abnormal_end_invalid | valid_fail | 0.833 | dialogue-parser__original-attempt-002 | graph_semantics_failure；runtime verifier/tool evidence only; export gap |
| fix-build-google-auto__all_faults | abnormal_end_invalid | valid_fail | 0.0 | fix-build-google-auto__all_faults-attempt-003 | model_patch_build_failure；direct exported artifact inspection and verifier |
| fix-build-google-auto__full_gold | valid_pass | valid_pass | 1.0 | fix-build-google-auto__full_gold-attempt-001 | official_verifier_pass；direct archived output inspection plus verifier; see historical_artifact_audits.json |
| fix-build-google-auto__original | valid_fail | valid_fail | 0.0 | fix-build-google-auto__original-attempt-001 | model_patch_build_failure；direct archived output inspection plus verifier; see historical_artifact_audits.json |
| flink-query__all_faults | infrastructure_influenced_unconfirmed | no_valid_result_after_confirmation | None | None | output_content_or_query_semantics_failure；runtime verifier/tool evidence; historical direct re-opening unavailable |
| flink-query__full_gold | valid_fail | valid_fail | 0.0 | flink-query__full_gold-attempt-001 | output_content_or_query_semantics_failure；runtime verifier/tool evidence; historical direct re-opening unavailable |
| flink-query__original | valid_fail | valid_fail | 0.0 | flink-query__original-attempt-001 | output_content_or_query_semantics_failure；runtime verifier/tool evidence; historical direct re-opening unavailable |
| location-data-to-d3 | verifier_check_invalid_with_independent_failure | verifier_check_invalid_with_independent_failure | None | None | independent_tooltip_assertion_failure_and_verifier_SVG_exception；runtime verifier/tool evidence; historical direct re-opening unavailable |
| location-dialogue-parser | valid_fail | valid_fail | 0.833 | location-dialogue-parser-attempt-001 | graph_semantics_failure；runtime verifier/tool evidence; historical direct re-opening unavailable |
| location-flink-query | valid_fail | valid_fail | 0.0 | location-flink-query-attempt-002 | output_content_or_query_semantics_failure；runtime verifier/tool evidence only; export gap |
| location-manufacturing-equipment-maintenance | valid_pass | valid_pass | 1.0 | location-manufacturing-equipment-maintenance-attempt-001 | official_verifier_pass；runtime verifier/tool evidence; historical direct re-opening unavailable |
| location-pddl-airport-planning | valid_fail | valid_fail | 0.0 | location-pddl-airport-planning-attempt-001 | plan_numerical_correctness_failure；runtime verifier/tool evidence; historical direct re-opening unavailable |
| manufacturing-equipment-maintenance__all_faults | valid_pass | valid_pass | 1.0 | manufacturing-equipment-maintenance__all_faults-attempt-001 | official_verifier_pass；runtime verifier/tool evidence; historical direct re-opening unavailable |
| manufacturing-equipment-maintenance__full_gold | valid_pass | valid_pass | 1.0 | manufacturing-equipment-maintenance__full_gold-attempt-001 | official_verifier_pass；runtime verifier/tool evidence; historical direct re-opening unavailable |
| manufacturing-equipment-maintenance__original | valid_pass | valid_pass | 1.0 | manufacturing-equipment-maintenance__original-attempt-001 | official_verifier_pass；runtime verifier/tool evidence; historical direct re-opening unavailable |
| pddl-airport-planning__full_gold | valid_pass | valid_pass | 1.0 | pddl-airport-planning__full_gold-attempt-001 | official_verifier_pass；runtime verifier/tool evidence; historical direct re-opening unavailable |
| pddl-airport-planning__original | valid_pass | valid_pass | 1.0 | pddl-airport-planning__original-attempt-001 | official_verifier_pass；runtime verifier/tool evidence; historical direct re-opening unavailable |
| sec-financial-report__all_faults | valid_fail | valid_fail | 0.0 | sec-financial-report__all_faults-attempt-001 | answer_content_failure；runtime verifier/tool evidence; historical direct re-opening unavailable |
| sec-financial-report__full_gold | valid_pass | valid_pass | 1.0 | sec-financial-report__full_gold-attempt-001 | official_verifier_pass；runtime verifier/tool evidence; historical direct re-opening unavailable |
| sec-financial-report__original | valid_fail | valid_fail | 0.0 | sec-financial-report__original-attempt-001 | answer_content_failure；runtime verifier/tool evidence; historical direct re-opening unavailable |
| single-fix-build-google-auto-RI-001 | valid_fail | valid_fail | 0.0 | single-fix-build-google-auto-RI-001-attempt-002 | model_patch_build_failure；direct archived output inspection plus verifier; see historical_artifact_audits.json |
| single-fix-build-google-auto-RI-001__condition_baseline | valid_pass | valid_pass | 1.0 | single-fix-build-google-auto-RI-001__condition_baseline-attempt-001 | official_verifier_pass；direct archived output inspection plus verifier; see historical_artifact_audits.json |
| single-fix-build-google-auto-RI-002 | abnormal_end_invalid | valid_pass | 1.0 | single-fix-build-google-auto-RI-002-attempt-003 | official_verifier_pass；direct exported artifact inspection and verifier |
| single-fix-build-google-auto-RI-002__condition_baseline | valid_pass | valid_pass | 1.0 | single-fix-build-google-auto-RI-002__condition_baseline-attempt-001 | official_verifier_pass；direct archived output inspection plus verifier; see historical_artifact_audits.json |
| single-fix-build-google-auto-all | valid_fail | valid_fail | 0.0 | single-fix-build-google-auto-all-attempt-001 | model_patch_build_failure；direct archived output inspection plus verifier; see historical_artifact_audits.json |
| single-flink-query-RI-001 | infrastructure_influenced_unconfirmed | valid_fail | 0.0 | single-flink-query-RI-001-attempt-002 | output_content_or_query_semantics_failure；direct exported artifact inspection and verifier |
| single-flink-query-RI-001__condition_baseline | infrastructure_influenced_unconfirmed | valid_fail | 0.0 | single-flink-query-RI-001__condition_baseline-attempt-002 | output_content_or_query_semantics_failure；direct exported artifact inspection and verifier |
| single-flink-query-RI-002 | infrastructure_influenced_unconfirmed | valid_fail | 0.0 | single-flink-query-RI-002-attempt-002 | output_content_or_query_semantics_failure；direct exported artifact inspection and verifier |
| single-flink-query-RI-002__condition_baseline | infrastructure_influenced_unconfirmed | valid_fail | 0.0 | single-flink-query-RI-002__condition_baseline-attempt-002 | model_code_execution_failure；direct exported artifact inspection and verifier |
| single-flink-query-all | valid_fail | valid_fail | 0.0 | single-flink-query-all-attempt-001 | output_content_or_query_semantics_failure；runtime verifier/tool evidence; historical direct re-opening unavailable |
| single-manufacturing-equipment-maintenance-RI-001 | valid_pass | valid_pass | 1.0 | single-manufacturing-equipment-maintenance-RI-001-attempt-001 | official_verifier_pass；runtime verifier/tool evidence; historical direct re-opening unavailable |
| single-manufacturing-equipment-maintenance-RI-001__condition_baseline | infrastructure_influenced_unconfirmed | no_valid_result_after_confirmation | None | None | output_content_or_domain_semantics_failure；runtime verifier/tool evidence; historical direct re-opening unavailable |
| single-manufacturing-equipment-maintenance-RI-002 | infrastructure_influenced_unconfirmed | no_valid_result_after_confirmation | None | None | output_content_or_domain_semantics_failure；runtime verifier/tool evidence; historical direct re-opening unavailable |
| single-manufacturing-equipment-maintenance-RI-002__condition_baseline | infrastructure_influenced_unconfirmed | valid_pass | 1.0 | single-manufacturing-equipment-maintenance-RI-002__condition_baseline-attempt-002 | official_verifier_pass；direct exported artifact inspection and verifier |
| single-manufacturing-equipment-maintenance-all | abnormal_end_invalid | valid_fail | 0.0 | single-manufacturing-equipment-maintenance-all-attempt-002 | output_content_or_domain_semantics_failure；direct exported artifact inspection and verifier |
| single-sec-financial-report-RI-001 | valid_pass | valid_pass | 1.0 | single-sec-financial-report-RI-001-attempt-001 | official_verifier_pass；runtime verifier/tool evidence; historical direct re-opening unavailable |
| single-sec-financial-report-RI-001__condition_baseline | valid_pass | valid_pass | 1.0 | single-sec-financial-report-RI-001__condition_baseline-attempt-001 | official_verifier_pass；runtime verifier/tool evidence; historical direct re-opening unavailable |
| single-sec-financial-report-RI-002 | valid_fail | valid_fail | 0.0 | single-sec-financial-report-RI-002-attempt-001 | answer_content_failure；runtime verifier/tool evidence; historical direct re-opening unavailable |
| single-sec-financial-report-RI-002__condition_baseline | valid_pass | valid_pass | 1.0 | single-sec-financial-report-RI-002__condition_baseline-attempt-001 | official_verifier_pass；runtime verifier/tool evidence; historical direct re-opening unavailable |
| single-sec-financial-report-RI-003 | valid_pass | valid_pass | 1.0 | single-sec-financial-report-RI-003-attempt-001 | official_verifier_pass；runtime verifier/tool evidence; historical direct re-opening unavailable |
| single-sec-financial-report-RI-003__condition_baseline | valid_pass | valid_pass | 1.0 | single-sec-financial-report-RI-003__condition_baseline-attempt-001 | official_verifier_pass；runtime verifier/tool evidence; historical direct re-opening unavailable |
| single-sec-financial-report-all | valid_fail | valid_fail | 0.0 | single-sec-financial-report-all-attempt-001 | answer_content_failure；runtime verifier/tool evidence; historical direct re-opening unavailable |
| single-video-silence-remover-RI-001 | valid_fail | valid_fail | 0.0 | single-video-silence-remover-RI-001-attempt-001 | segment_or_video_content_failure；direct archived output inspection plus verifier; see historical_artifact_audits.json |
| single-video-silence-remover-RI-001__condition_baseline | valid_fail | valid_fail | 0.0 | single-video-silence-remover-RI-001__condition_baseline-attempt-001 | segment_or_video_content_failure；direct archived output inspection plus verifier; see historical_artifact_audits.json |
| single-video-silence-remover-RI-002 | valid_pass | valid_pass | 1.0 | single-video-silence-remover-RI-002-attempt-001 | official_verifier_pass；direct archived output inspection plus verifier; see historical_artifact_audits.json |
| single-video-silence-remover-RI-002__condition_baseline | valid_pass | valid_pass | 1.0 | single-video-silence-remover-RI-002__condition_baseline-attempt-001 | official_verifier_pass；direct archived output inspection plus verifier; see historical_artifact_audits.json |
| single-video-silence-remover-RI-003 | valid_pass | valid_pass | 1.0 | single-video-silence-remover-RI-003-attempt-001 | official_verifier_pass；direct archived output inspection plus verifier; see historical_artifact_audits.json |
| single-video-silence-remover-RI-003__condition_baseline | valid_pass | valid_pass | 1.0 | single-video-silence-remover-RI-003__condition_baseline-attempt-001 | official_verifier_pass；direct archived output inspection plus verifier; see historical_artifact_audits.json |
| single-video-silence-remover-all | abnormal_end_invalid | valid_fail | 0.0 | single-video-silence-remover-all-attempt-002 | segment_or_video_content_failure；direct exported artifact inspection and verifier |
| video-silence-remover__all_faults | valid_fail | valid_fail | 0.0 | video-silence-remover__all_faults-attempt-001 | segment_or_video_content_failure；direct archived output inspection plus verifier; see historical_artifact_audits.json |
| video-silence-remover__full_gold | valid_pass | valid_pass | 1.0 | video-silence-remover__full_gold-attempt-001 | official_verifier_pass；direct archived output inspection plus verifier; see historical_artifact_audits.json |
| video-silence-remover__original | valid_fail | valid_fail | 0.0 | video-silence-remover__original-attempt-001 | segment_or_video_content_failure；direct archived output inspection plus verifier; see historical_artifact_audits.json |

历史 verifier 的独立进程退出码没有单独序列化。完整 CTRF、reward、stdout 和无 verifier_error 的正式结果支持执行完成，但不能声称直接保存了每次历史进程返回码。新参考验收的退出码已实际捕获；后续补跑加入只读的返回码观测文件。

## 可复核文件

- AUDIT_RUNS.csv / AUDIT_RUNS.json：55 项的配置、镜像、采用结果、轨迹和 verifier 路径。
- historical_details.json：逐项 Skill 文件清单/哈希、所有失败断言及 trace、请求/工具对应关系、日志哈希。
- CONFIRMATION_AUDITS.json / reruns/*/STRICT_AUDIT.json：旧新 attempt 对应、内部失败、配置差异和实物解析。
- attempt_inventory.json / nonselected_attempt_audit.json：原始未入选尝试；不计入有效模型失败。
- reference/：8 项全新参考验收和 agent 权限验证。
- AUDIT_POLICY.json / artifact_retention_limitations.json：重跑规则和证据边界。
- historical_core_evidence_integrity.json：220 份原始核心证据哈希与冻结包逐一比对。
- skill_condition_source_checks.json / reward_reproduction.json：加载条件和评分复算。
