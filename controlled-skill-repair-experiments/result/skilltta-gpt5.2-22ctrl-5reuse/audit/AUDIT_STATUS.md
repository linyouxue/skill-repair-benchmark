# Controlled55 严格审计：中间报告，尚未完成

数据更新时间（UTC）：2026-11-25T05:21:04.488573+00:00。本报告不是最终通过率报告，也不是独立人工复核。此前‘55/55有效’的结论已撤回。

## 当前状态

总条件55（22修复+33对照）。本轮含原33条件及新增补证的队列已有43个走完当前补跑流程；已新建73个外层attempt、关闭72个。执行器内部自动重试另按rollout登记，不能用外层目录数冒充实际执行次数。

已核验正常任务执行12次：官方满分0次，正常失败12次；PDDL确认性补跑已以超时结束并保留，第一次格式失败的资源证据仍不足。另有2个修复条件的早期修复HTTP失败响应未完整保留，不能把‘rollout有效’称为完整方法历史已合规。

55条件当前分组：{"historical_evidence_insufficient": 12, "historical_resource_evidence_insufficient": 2, "rerun_or_adjudication_pending": 9, "retry_cap_no_valid_result": 19, "valid_failure": 12, "verifier_semantics_disputed": 1}。分类互斥；异常/API/缺产物候选集合有重叠。

**有效结果不等于通过。无有效结果、证据不足、verifier争议不能记成模型有效失败。正常内容/数值失败不会为提高分数重跑。**

## 环境与官方参考验收

8任务、11实际运行环境组均完成相同CPU/内存/swap上限、相同初始运行镜像、官方env和挂载、正式verifier时间预算下的参考验收；全部满分通过。先前未设CPU/内存上限的验收和审计员接线失败记录均保留，现有结论以这次资源一致的验收为准。

|任务/环境组|架构|CPU|内存字节|verifier耗时/预算秒|奖励|原始命令/退出码/哈希|
|---|---|---:|---:|---:|---:|---|
|data-to-d3--full_gold|arm64|2|4294967296|14.70/240.0|1.0|[ACCEPTANCE.json](</Users/king/Library/Application Support/SkillTTA/controlled-gpt52/audits/controlled55-strict-20261124/resource-matched-reference/data-to-d3__1fb0c3efa0fb/ACCEPTANCE.json>)|
|dialogue-parser--full_gold|arm64|1|4294967296|0.44/900.0|1.0|[ACCEPTANCE.json](</Users/king/Library/Application Support/SkillTTA/controlled-gpt52/audits/controlled55-strict-20261124/resource-matched-reference/dialogue-parser__3f5b33df9999/ACCEPTANCE.json>)|
|fix-build-google-auto--full_gold|amd64|4|4294967296|805.30/900.0|1.0|[ACCEPTANCE.json](</Users/king/Library/Application Support/SkillTTA/controlled-gpt52/audits/controlled55-strict-20261124/resource-matched-reference/fix-build-google-auto__c6f1fefa5dcf/ACCEPTANCE.json>)|
|flink-query--full_gold|arm64|4|4294967296|518.17/600.0|1.0|[ACCEPTANCE.json](</Users/king/Library/Application Support/SkillTTA/controlled-gpt52/audits/controlled55-strict-20261124/resource-matched-reference/flink-query__2cc71f7d2333/ACCEPTANCE.json>)|
|manufacturing-equipment-maintenance--full_gold|arm64|2|4294967296|4.29/300.0|1.0|[ACCEPTANCE.json](</Users/king/Library/Application Support/SkillTTA/controlled-gpt52/audits/controlled55-strict-20261124/resource-matched-reference/manufacturing-equipment-maintenance__9c8a72f6a0ad/ACCEPTANCE.json>)|
|pddl-airport-planning--full_gold|arm64|1|2147483648|3.07/600.0|1.0|[ACCEPTANCE.json](</Users/king/Library/Application Support/SkillTTA/controlled-gpt52/audits/controlled55-strict-20261124/resource-matched-reference/pddl-airport-planning__28a71a6e0d4e/ACCEPTANCE.json>)|
|sec-financial-report--full_gold|arm64|1|4294967296|0.44/900.0|1.0|[ACCEPTANCE.json](</Users/king/Library/Application Support/SkillTTA/controlled-gpt52/audits/controlled55-strict-20261124/resource-matched-reference/sec-financial-report__381cc2592984/ACCEPTANCE.json>)|
|video-silence-remover--full_gold|arm64|1|4294967296|6.99/240.0|1.0|[ACCEPTANCE.json](</Users/king/Library/Application Support/SkillTTA/controlled-gpt52/audits/controlled55-strict-20261124/resource-matched-reference/video-silence-remover__f2304e9d0a5f/ACCEPTANCE.json>)|
|location-dialogue-parser|arm64|1|4294967296|11.57/900.0|1.0|[ACCEPTANCE.json](</Users/king/Library/Application Support/SkillTTA/controlled-gpt52/audits/controlled55-strict-20261124/resource-matched-reference/dialogue-parser__5764814a00aa/ACCEPTANCE.json>)|
|location-manufacturing-equipment-maintenance|arm64|2|4294967296|177.88/300.0|1.0|[ACCEPTANCE.json](</Users/king/Library/Application Support/SkillTTA/controlled-gpt52/audits/controlled55-strict-20261124/resource-matched-reference/manufacturing-equipment-maintenance__ded0d1bf3564/ACCEPTANCE.json>)|
|single-fix-build-google-auto-RI-001|amd64|4|4294967296|880.87/900.0|1.0|[ACCEPTANCE.json](</Users/king/Library/Application Support/SkillTTA/controlled-gpt52/audits/controlled55-strict-20261124/resource-matched-reference/fix-build-google-auto__21c65522514f/ACCEPTANCE.json>)|

初始镜像的RootFS与关键配置比对见[runtime_image_identity_review.json](</Users/king/Library/Application Support/SkillTTA/controlled-gpt52/audits/controlled55-strict-20261124/audit-evidence/runtime_image_identity_review.json>)。这不等于容器启动后所有可写层、联网安装依赖和历史已删除镜像均已获证。实际资源配置、部署路径、依赖版本和运行中Skill/verifier哈希另存；未核验内容不宣称通过。

## 明确发现

- 原始55主结果有28条实质性异常结尾、另1条通过的D3结尾是可选后备建议，未自动判无效。8条将工具参数写成普通文本；6条记录到API/上游错误回调。
- 最初29个缺产物文本候选中，排除只在回溯中展示的断言源码后，27条有实际缺产物报错，均已列入补跑。未导出文件不等于任务当时没有生成。
- 原始55外层组实际包含59个rollout，4个较早的ACP/空闲/verifier超时失败不能在汇总中隐藏。另1个回流焊内部失败有4个真正的terminal函数调用没有ACP执行结果；与普通文本伪调用分别报告。
- 6处native finish与ACP最终消息对应，属于控制结束动作，不能当作丢失的终端工具响应。
- 对话解析End检查：实际图205节点321边，正常BFS全部可达；测试跳过End后又将其计入不可达集合，唯一失败为End。保留原0.833，暂不归为模型有效失败。该attempt还缺完整初始镜像/原快照元数据证据。
- D3的SVG inner_text兼容性风险已最小复现，但原始D3正式日志未出现该错误；不能凭探针改任何正式分数。后续若出现，逐检查列出对奖励影响及其它独立失败。
- 原test.sh的依赖安装/解释器变更在审计前已存在；测试主体/预期数据与官方55项一致，不宣称完整入口字节一致。审计未更改任务、输入、Gold、测试和评分或模型输出。
- llm_trajectory由LiteLLM回调重建，成功回调写200，部分请求选项未保留，reasoning high可能由环境补记。不能称为原始HTTP抓包，也不能独立证明代理上游实际模型身份；指定路由/配置和可见原始请求按实核对。
- 22个SkillTTA候选共88个最终成功修复阶段请求/响应已核对哈希、模型、高推理及32768输出预算、stop终止和候选清单；3个调用曾重试且较早响应可能覆盖，涉及2个修复条件，明示历史缺口。

## 已核验的正常失败

|条件|新attempt/rollout|官方原分|失败层面|主要依据|
|---|---|---:|---|---|
|single-flink-query-RI-001|attempt-009/task__8628a96d|0.0|model_program_output_semantics|61 completed tool calls. Required query/datatype sources retained; last write event61 followed by successful Maven compile event62. Final accurately describes delivered code. Official verifier compilation and Flink runtime pass, output comparison fails: 698 actual tuple lines, 54 extra (job,0), no expected rows missing. Actual pom.xml hash unchanged at final and verifier stages. Runtime out.txt generated by submitted job and physically copied, UTF-8 with698/698 tuple lines. No required future action unperformed. API/native-call/config/artifact checks still need formal script gates; final resource acceptance pending.|
|single-flink-query-all|attempt-003/task__29f2ca0d|0.0|model_program_output_semantics|47 completed tools, last code changes followed by successful Maven compile event48. Query and datatype Java sources+JAR retained; actual pom unchanged at final and verifier stages. Official Maven and Flink run pass; actual987/987 tuple lines parsed, expected644 rows all present plus343 extras. Code final message explicitly describes FINISH/FAIL/KILL/LOST terminal job handling rather than only required finished jobs, consistent with excessive outputs. No later required promise or unexecuted native call. Official reward0 retained; no score-based retry.|
|single-manufacturing-equipment-maintenance-all|attempt-004/task__6afc21bc|0.0|artifact_content_preheat_region_calculation|23 completed native tools; event22 writes q01-q05, event23 reloads actual JSONs and checks run counts/keys, event24 reads output files. All five physically copied and parseable. Handbook pages actually extracted with fitz and read. Submitted calculation uses both endpoint temperatures <=150C but omits lower100C bound, while unchanged official Q1 uses100<=T<=150 at both endpoints. First Q1 assertion R0001 actual1.77 vs expected1.74;6other tests pass. Formal reward0 kept. No unfinished required action or score-based repeat.|
|single-video-silence-remover-RI-002|attempt-002/task__76e4f148|0.0|content_segment_detection_and_removal_amount|27 completed native tools. Events24/25 run actual video processor/report generator;26 re-reads actual ffprobe streams+JSON math;27 cleans intermediates before final. Both required files copied; strict JSON and real read-only ffprobe succeed. Actual MP4 duration512.003991s. Official recall55.6%=5/9<60%, precision38.5%=5/13<60%, removed88s vs expected254, compressed512.004s vs expected346. Normal content failure, not missing/export/verifier failure. No score-based repeat. Agent execution840.1s exceeds task soft processing-time note10min but does not exhaust configured agent budget; record separately, no manual reward change.|
|single-video-silence-remover-all|attempt-005/task__927b8d7d|0.0|content_segment_detection_and_removal_amount|Actual MP4 and JSON exist and parse. Native video-processing call event16 returned still-running; model explicitly waited via event17 and obtained process completion before generating report18 and final ffprobe/JSON validation19. Actual MP4 duration537.003991s,13 removed segments,total63s. Official recall5/9=55.6%,precision5/13=38.5%,removed63vs254,compressed537vs346 fail. Five other tests pass. Normal content failure, no missing/export/unfinished action; original0 retained, no score-based retry. Agent_execution360.1s within soft10min processing guideline.|
|location-data-to-d3|attempt-005/task__449fa769|0.0|artifact_javascript_syntax|Full ACP reviewed: model copies fixed CSV inputs, downloads D3v6, writes CSS/HTML/JS, lists actual outputs and reads generated JS in final two tools. Native write/read commands complete before descriptive final message, with no required future action. Final invitation to open the HTML is optional user viewing, not an unperformed required model operation. Actual syntax/parser and unchanged official browser verifier checks are separate admission gates; this semantic review alone does not certify reward or task success. Official browser verifier completes10 tests:3pass7fail; page_errors contains Invalid or unexpected token, zero rendered bubbles/rows. Actual generated JS is retained for node --check confirmation. This is a submitted program format defect, not the hypothetical SVG.inner_text compatibility bug, which this run does not reach. Retain reward0 and classify separately from infrastructure; one same-config format confirmation can consume remaining predeclared slot.|
|single-manufacturing-equipment-maintenance-RI-001|attempt-004/task__56471cbf|0.0|artifact_numeric_and_representative_sensor_selection|Actual event24 writes q01-q05 after recovering PDF extraction regexes, reports extracted100/150C,2C/s,20C,30/60s; events25-29 re-read each real output. Mistyped ls in33 fails but corrected34 lists all5 files successfully before descriptive final35. Missing optional AGENTS file is not a task failure and model creates its own notes32; task output files are generated by model, not auditor. Official verifier completes7 tests4pass3fail:Q01 R0004 produced1.75 vs1.68;Q02 R0001 produced132.61 vs129.95, consistent with final declared minimum-peak coldest-TC instead of verifier minimum-TAL selection;Q05 best_run_id null for Compute_IO. No unperformed required final action; normal numeric/content failure, no score-based retry. Actual JSON schema and Skill/image/API/resource/exit gates remain separately verified.|
|single-manufacturing-equipment-maintenance-RI-002|attempt-004/task__fbede960|0.0|artifact_numeric_preheat_lower_bound_and_tal_tc_selection|Actual toolkit full body read event2; missing optional file utility/pdftotext is recovered with pypdf5.1 installation and extraction. Initial model PDF regex fails14 and edit17 misses, but repaired18 and actual solver run19 succeeds exit0;20 reloads all5 actual nonempty JSONs with run coverage,21 previews each before descriptive final22. No unperformed final action or unresolved model write. Official7tests5pass2fail:Q01 R0001 ramp1.77 vs1.74 (model final explicitly uses bothT<=150 and omits100 lowerbound);Q02 R0001 selected159.57 vs129.95 minimumTAL. Normal content/numeric failure, not infrastructure;0 retained,no score repeat.|
|single-sec-financial-report-RI-001|attempt-004/task__2b76a86c|0.0|artifact_content_financial_q2_count|Full ACP reviewed. Missing optional bs4 at4 is recovered with actual grep/sed readme inspection5/6, then model computes and writes answers.json7 exit0 and re-reads actual file8 before descriptive final9. No unperformed required action; all4 schema keys present. Official verifier completes2tests1pass1fail; existence passes,quality stops at Q2 value3457 vs Gold2451 after Q1 tolerance check succeeds. Do not infer Q3/Q4 official success from stopped assertion; raw0 preserved. Normal content/count failure, no infrastructure or score-based retry.|
|single-sec-financial-report-RI-003|attempt-005/task__9ee8e6b3|0.0|artifact_content_financial_q2_count|Full ACP reviewed. Optional bs4 import failure6 recovered by actual readme grep/nl7/8; computations9-14 finish exit0. Model explicitly finds no preexisting answers15, creates actual file16, validates/re-reads with python-m-json.tool17 exit0 before descriptive final18. Q1 value75753182516 satisfies tolerance; Q2 model counts3457 uniqueCUSIPs, official requires2451 and quality test stops there. Two tests complete1pass1fail,raw0 retained; Q3/Q4 official success not inferred after stopped Q2assert. Prior attempt004 has API callback fault and remains separate invalid record;005 independently passes all other gates only when checked. No score-based rerun.|
|single-sec-financial-report-all|attempt-004/task__6efbc686|0.0|artifact_content_financial_q2_count|Full ACP reviewed. Actual task guidance skill read2, data computations5 initially use wrong VALUE scaling; model checks actual metadata/readme6/7, recomputes and rewrites8 exit0 with dollar values, re-reads actual answers9 before descriptive final12. Optional AGENTS/git checks10/11 do not promise another required task action. JSON all4 keys present and source files are real. Official2tests1pass1fail; Q1 tolerance succeeds, Q2 value3456 vs2451 fails and stopsqualitytest; Q3/Q4 not claimed officiallypassed. Normal content/count failure,0 retained and no score-based repeat.|
|single-video-silence-remover-RI-003|attempt-002/task__909a75c6|0.0|content_segment_detection_duration_and_audio_report_agreement|Full ACP reviewed: task-guidance Skill read3; model uses multiple silence/audio/freeze analyses, then actual integrated processor28 finishes with codec footer and exit0 and writes both files.29 reloadsreport;30 removes intermediates;31 lists both required outputs and ffprobes actual MP4 duration453.003991 before descriptive final32. Auditor read-only ffprobe confirms realvideo+audio streams and matching copied artifact SHA. Official9tests4pass5fail:recall2/9=22.2%,precision2/16=12.5%,removed147.001vs254,compressed453.004vs346 fail;waveform correlation0.044 vs0.95 alsofails. No verifier exception observed. Exact encoding/rounding contribution to audio correlation is not isolated, so do not claim a proven encoding root cause; other4 independent content checks already force binary reward0 regardless of the audio check. Normal task content failure, not missing artifact/export/unfinished operation. No score-based repeat.|

以上文件存在/格式/运行/内容结论按具体任务解释。Flink提交Java，由verifier编译运行生成out.txt，不能因agent结束时out.txt未产生就判缺交付；PDDL计划能UTF8读取但官方PDDLReader实际拒绝，不能称计划格式合格。媒体必须由ffprobe打开，不能仅凭后缀或文字声明。没有任务要求输出Excel/PDF，未作此类不适用的通过声明。

## 逐项55清单与证据

|实验ID|原attempt|原奖励（非最终采用）|当前状态|候选采用attempt|采用奖励|
|---|---|---:|---|---|---:|
|location-data-to-d3|attempt-004|1.0|valid_failure|attempt-005/task__449fa769|0.0|
|location-dialogue-parser|attempt-001|0.0|verifier_semantics_disputed|—|—|
|location-flink-query|attempt-010|0.0|retry_cap_no_valid_result|—|—|
|location-manufacturing-equipment-maintenance|attempt-004|0.0|historical_resource_evidence_insufficient|—|—|
|location-pddl-airport-planning|attempt-004|0.0|historical_resource_evidence_insufficient|—|—|
|single-fix-build-google-auto-RI-001|attempt-005|0.0|retry_cap_no_valid_result|—|—|
|single-fix-build-google-auto-RI-002|attempt-001|0.0|retry_cap_no_valid_result|—|—|
|single-fix-build-google-auto-all|attempt-001|0.0|retry_cap_no_valid_result|—|—|
|single-flink-query-RI-001|attempt-007|0.0|valid_failure|attempt-009/task__8628a96d|0.0|
|single-flink-query-RI-002|attempt-002|0.0|retry_cap_no_valid_result|—|—|
|single-flink-query-all|attempt-002|0.0|valid_failure|attempt-003/task__29f2ca0d|0.0|
|single-manufacturing-equipment-maintenance-RI-001|attempt-002|0.0|valid_failure|attempt-004/task__56471cbf|0.0|
|single-manufacturing-equipment-maintenance-RI-002|attempt-003|0.0|valid_failure|attempt-004/task__fbede960|0.0|
|single-manufacturing-equipment-maintenance-all|attempt-002|0.0|valid_failure|attempt-004/task__6afc21bc|0.0|
|single-sec-financial-report-RI-001|attempt-003|0.0|valid_failure|attempt-004/task__2b76a86c|0.0|
|single-sec-financial-report-RI-002|attempt-003|0.0|retry_cap_no_valid_result|—|—|
|single-sec-financial-report-RI-003|attempt-003|0.0|valid_failure|attempt-005/task__9ee8e6b3|0.0|
|single-sec-financial-report-all|attempt-003|0.0|valid_failure|attempt-004/task__6efbc686|0.0|
|single-video-silence-remover-RI-001|attempt-001|0.0|retry_cap_no_valid_result|—|—|
|single-video-silence-remover-RI-002|attempt-001|0.0|valid_failure|attempt-002/task__76e4f148|0.0|
|single-video-silence-remover-RI-003|attempt-001|0.0|valid_failure|attempt-002/task__909a75c6|0.0|
|single-video-silence-remover-all|attempt-004|0.0|valid_failure|attempt-005/task__927b8d7d|0.0|
|dialogue-parser--full_gold|attempt-005|0.0|retry_cap_no_valid_result|—|—|
|dialogue-parser--original|attempt-002|0.833|historical_evidence_insufficient|—|—|
|fix-build-google-auto--all_faults|attempt-002|0.0|retry_cap_no_valid_result|—|—|
|single-fix-build-google-auto-RI-001--condition_baseline|attempt-002|0.0|retry_cap_no_valid_result|—|—|
|single-fix-build-google-auto-RI-002--condition_baseline|attempt-003|0.0|retry_cap_no_valid_result|—|—|
|fix-build-google-auto--full_gold|attempt-003|0.0|retry_cap_no_valid_result|—|—|
|fix-build-google-auto--original|attempt-002|0.0|retry_cap_no_valid_result|—|—|
|flink-query--all_faults|attempt-003|0.0|retry_cap_no_valid_result|—|—|
|single-flink-query-RI-001--condition_baseline|attempt-002|0.0|rerun_or_adjudication_pending|—|—|
|single-flink-query-RI-002--condition_baseline|attempt-002|0.0|retry_cap_no_valid_result|—|—|
|flink-query--full_gold|attempt-002|0.0|rerun_or_adjudication_pending|—|—|
|flink-query--original|attempt-002|0.0|historical_evidence_insufficient|—|—|
|manufacturing-equipment-maintenance--all_faults|attempt-002|0.0|historical_evidence_insufficient|—|—|
|single-manufacturing-equipment-maintenance-RI-001--condition_baseline|attempt-002|0.0|rerun_or_adjudication_pending|—|—|
|single-manufacturing-equipment-maintenance-RI-002--condition_baseline|attempt-002|0.0|historical_evidence_insufficient|—|—|
|manufacturing-equipment-maintenance--full_gold|attempt-002|0.0|rerun_or_adjudication_pending|—|—|
|manufacturing-equipment-maintenance--original|attempt-002|0.0|rerun_or_adjudication_pending|—|—|
|pddl-airport-planning--full_gold|attempt-003|1.0|historical_evidence_insufficient|—|—|
|pddl-airport-planning--original|attempt-003|0.0|retry_cap_no_valid_result|—|—|
|sec-financial-report--all_faults|attempt-003|0.0|historical_evidence_insufficient|—|—|
|single-sec-financial-report-RI-001--condition_baseline|attempt-003|0.0|historical_evidence_insufficient|—|—|
|single-sec-financial-report-RI-002--condition_baseline|attempt-003|1.0|historical_evidence_insufficient|—|—|
|single-sec-financial-report-RI-003--condition_baseline|attempt-003|0.0|historical_evidence_insufficient|—|—|
|sec-financial-report--full_gold|attempt-003|1.0|rerun_or_adjudication_pending|—|—|
|sec-financial-report--original|attempt-003|0.0|historical_evidence_insufficient|—|—|
|video-silence-remover--all_faults|attempt-001|0.0|rerun_or_adjudication_pending|—|—|
|single-video-silence-remover-RI-001--condition_baseline|attempt-001|0.0|retry_cap_no_valid_result|—|—|
|single-video-silence-remover-RI-002--condition_baseline|attempt-001|0.0|retry_cap_no_valid_result|—|—|
|single-video-silence-remover-RI-003--condition_baseline|attempt-001|0.0|rerun_or_adjudication_pending|—|—|
|video-silence-remover--full_gold|attempt-001|1.0|historical_evidence_insufficient|—|—|
|video-silence-remover--original|attempt-001|0.0|rerun_or_adjudication_pending|—|—|
|data-to-d3--full_gold|attempt-004|1.0|historical_evidence_insufficient|—|—|
|data-to-d3--original|attempt-002|0.0|retry_cap_no_valid_result|—|—|

完整逐项路径与依据：[live_audit_report.json](</Users/king/Library/Application Support/SkillTTA/controlled-gpt52/audits/controlled55-strict-20261124/audit-evidence/live_audit_report.json>)、[live_entries.csv](</Users/king/Library/Application Support/SkillTTA/controlled-gpt52/audits/controlled55-strict-20261124/audit-evidence/live_entries.csv>)。新旧attempt/原因/原分/配置差异：[live-rerun-registry.json](</Users/king/Library/Application Support/SkillTTA/controlled-gpt52/audits/controlled55-strict-20261124/audit-evidence/live-rerun-registry.json>)，实际内部rollout清单：[inner_rollout_inventory.json](</Users/king/Library/Application Support/SkillTTA/controlled-gpt52/audits/controlled55-strict-20261124/audit-evidence/inner_rollout_inventory.json>)。各候选接纳门槛与实际产物哈希：[normal_rollout_adjudication.json](</Users/king/Library/Application Support/SkillTTA/controlled-gpt52/audits/controlled55-strict-20261124/audit-evidence/normal_rollout_adjudication.json>)。

原始55缓存、所有原attempt目录均保留；已关闭的新attempt和内部rollout以APFS副本+SHA留在本地，未覆盖原目录。审计员中断的旧005遗留服务已冻结，并取回真实ACP、5JSON和原verifier评分；无正式result.json，绝不人工合成或采用其评分。部分旧iCloud日志仍不可读，原占位文件保留，未伪造恢复。

审计脚本和本地证据根目录：`/Users/king/Library/Application Support/SkillTTA/controlled-gpt52/audits/controlled55-strict-20261124`。主要脚本：audit_native_call_accounting.py、check_all_result_error_fields.py、compare_runtime_image_identity.py、check_task_json_contracts.py、adjudicate_completed_normal_rollouts.py、audit_repair_stage_provenance.py、update_local_status_report.py。本文件由render_intermediate_audit_report.py生成。

**尚未完成**：当前9个补跑/复核条件、已完成确认的逐项结果记录、部分历史证据的可读性/实际镜像证明及最终完整统计。不得据本中间报告宣布55项全部完成或给出整体严格审计通过率。

按实际rollout展开的逐attempt账本：[attempt_audit_ledger.json](</Users/king/Library/Application Support/SkillTTA/controlled-gpt52/audits/controlled55-strict-20261124/audit-evidence/attempt_audit_ledger.json>)、[attempt_audit_ledger.csv](</Users/king/Library/Application Support/SkillTTA/controlled-gpt52/audits/controlled55-strict-20261124/audit-evidence/attempt_audit_ledger.csv>)。账本包含可见模型配置、正式错误字段、原始分、采用分、实际镜像证据、verifier退出或重放证据、结果与轨迹路径、日志哈希、产物解析及判定依据。未获证的退出码明确留空，不填作0。

Google异常结束的逐事件复核：[google_abnormal_ending_semantic_reviews.json](</Users/king/Library/Application Support/SkillTTA/controlled-gpt52/audits/controlled55-strict-20261124/audit-evidence/google_abnormal_ending_semantic_reviews.json>)；报告内部一致性检查及审计脚本哈希：[report_consistency_check.json](</Users/king/Library/Application Support/SkillTTA/controlled-gpt52/audits/controlled55-strict-20261124/audit-evidence/report_consistency_check.json>)。一致性检查只核对报告记账，不代表实验有效性全部通过。
