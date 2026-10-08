# MMG2Skill / GPT-5.2 Gold31 existing results

GPT-5.2已有结果快照：31题方法/bundle已完成，31题有效执行（5 PASS、26 FAIL），Druid 已完成有效运行并判定 FAIL。**这不是31题最终完成报告；语义Gold未启动，不能填造TP/FP/FN。**

发布整理阶段不追加模型或裁判调用。2026-10-08的已授权guard3重跑作为单独协议变更列于下文。MMG原Analyzer分块15、一次Refiner、include_tutorial_in_refine=false，32768限制；复用历史original-skill轨迹，不重跑基线。固定本地OpenHands，fresh60步/JPG65步。两个模型的响应和评分独立保存。

- [任务、基线、bundle、有效run索引](task-index.json)
- [完整方法提交](submission.json)：指向 `tasks/<task_id>/repaired_skill/`，完整保留所有支持文件。
- [真实执行结果注册表](executor-results.json)，原始和历史失败run均保留，选择有效结果以索引为准。
- [部分执行汇总](partial-execution-summary.json)：31题均有有效验收，语义Gold尚未运行。
- `trajectory_timelines/` 是仓库export_trajectory.py生成的完整before/after可读轨迹；原始轨迹保留。
- `tasks/<task_id>/` 按仓库README包含 `repaired_skill/`、`original_run/`、`repaired_run/`；后两者均含executor_request/result/benchmark_result及原始trajectory。GPT Druid的当前有效FAIL与早期基础设施失败证据分别保留。
- `generation/` 保存方法请求/响应与adapter；`runs/`、`submission/` 额外保留原批次路径，便于核对历史引用。
- GPT AgentOps的 `repaired_run/RESULT_PROVENANCE.json` 明确区分原fresh和verifier-only恢复：顶部结果采用已审核派生验收，原超时及恢复verifier均保留。
- [大文件下载和校验清单](large-files.json)：工作区快照不裁剪、不从轨迹重建，大文件保存在同仓库GitHub附件中。

## 恢复与离线复算

在本目录执行 `python restore_files.py` 解压压缩文本；加 `--download-assets` 下载并校验完整工作区快照。若无需工作区本体，所有报告/语义评分可直接读取。

GPT未裁判；不在发布时追加付费评分或伪造最终指标。冻结评测脚本与31题Gold输入仅为后续复算准备。

## 协议偏离和证据限制

- AgentOps按用户授权修正为py38–py312矩阵，原断言/依赖pins保持。GPT选用真实snapshot的verifier-only派生验收结果，原超时r001保留；不能据raw r001覆盖有效派生结果。Claude为有效timestamp断言失败。
- GPT manufacturing允许且仅执行过一次额外Analyzer重试，旧不完整响应及授权记录保留；此例外未套用Claude。
- Druid早期远端请求曾受地区访问门限阻断；2026-09-27 已通过有效服务器运行完成 50 次模型请求与正式 verifier，最终为模型/方法 FAIL；早期基础设施失败证据仍保留。
- Shock题面的Excel/Playwright/Solver能力与基础harness不完全匹配；结构健康不等于环境完全满足要求。
- Claude Python→Scala原轨迹输入采用已授权重建副本，误脱敏/重建限制在独立审计中保留；Flink/PDDL等其他限制见完整报告。
- n_skill_invocations与正文预加载证据分别保留在真实result和审计中。fresh通过不等于语义Gold内容修复成功。

`history/`为原本地配置/脚本快照，保留历史绝对路径；直接复算请用本目录便携入口，不执行旧launch脚本。

大附件的 `also_restore_to` 给出标准 `tasks/*/repaired_run` 路径；恢复脚本会同时恢复原历史路径与这些标准路径。可读轨迹索引由原始唯一rollout导出，未手工修改；标准目录是相同证据的字节一致副本。

## 2026-10-08 completion guard3 replacements

[Replacement report and protocol disclosure](reruns/completion-guard3-20261008/README.md) · [Current replacement index](reruns/completion-guard3-20261008/replacement-index.json).

The listed canonical repaired runs and submission IDs now select the audited guard3 reruns. SkillTTA replaces Azure, Energy, Reserves and Python→Scala; MMG2Skill replaces Dialogue only. Each method directory contains only its corresponding replacements. Energy changes from FAIL to PASS; the other four remain valid FAILs. SkillTTA is now 5 PASS / 26 FAIL (31 valid tasks); MMG2Skill remains 5 PASS / 26 FAIL (31 valid tasks). All other task candidates, method diagnoses, baselines and historical semantic scores are unchanged. The full method bundles are byte-identical reused inputs; only these selected executions use guard3 with the same 60-step parent budget. No semantic judge was invoked for this publication, and execution PASS is not substituted for semantic TP. Prior canonical files remain available in Git history; MMG raw historical runs also remain under runs/.

Current readable export: 31 before / 35 after / 0 unknown unique rollouts. MMG includes explicitly historical runs in this count; current selection is defined by submission.json and task-index.json. RESULT_PROVENANCE.json identifies the original private snapshot SHA and public credential-sanitized derivative SHA; only the obsolete local proxy token is redacted, not workspace output content.
