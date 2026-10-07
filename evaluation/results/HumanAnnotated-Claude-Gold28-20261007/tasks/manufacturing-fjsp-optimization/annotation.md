# Claude 人工标注：manufacturing-fjsp-optimization

## 当前状态

2026-10-06 已纳入新增14题，待诊断。用户已确认沿用自主修复、必要付费fresh及每30分钟检查。

原Opus有效未通过：manufacturing-fjsp-optimization-opus47-original-skill-r001；reward=0.0，end_turn。证据目录：/mnt/c/Users/linyuanjing/Desktop/skill论文/SkillGen-benchmarking/expanded_original_skill_runs/opus47-openrouter-v1.1-20260919/runs/opus47-original-skill/manufacturing-fjsp-optimization-opus47-original-skill-r001。

GPT未改Skill成功只作范围证据，不继承其归因或产物。首错、步骤、标签、最小修复与执行遵循待核查。尚未启动模型；费用未知null。


## 2026-10-07T02:41:50.930972+08:00 原轮完整诊断与公开契约阻塞

原轮有效FAIL13PASS/2FAIL，reward0；11/60正常end_turn、11provider全200、7工具/0显式Skill、14完整ACP。原Skill4824字节首请求精确全文暴露，已有明确零停机重叠/先后顺序/预算指导，未提供冻结例外。首错ACP5识别冻结与停机冲突后自行假定冻结工序免检，ACP6源93–100保留冲突、147–153自检跳过；ACP9继续该假定，7/10/11/13错误验收。原失败是正常停机/改进断言，不是预算或基础设施错误。

公开policy.json的freeze enabled=true、freeze_until=6、lock_fields=machine/start/end；公开baseline中job2/op0固定机器1、[5,9)，公开停机机器1[5,20)。三字段全部锁定时该重叠不可消除，严格契约无解。原checker get_freeze_policy只读fields/freeze_fields，漏读实际lock_fields，独立原函数调用返回(6,[])，故freeze子测试直接return，PASS为空检查。另有题面less makespan与policy ratio/实际checker目标边界不一致，保留不推定意图。详见public-contract-evidence及original-audit.json。

主归因agent_invented_hard_constraint_exception；另记task_policy_freeze_downtime_contract_conflict、verifier_lock_fields_parser_omission及premature success。原source与真实JSON/CSV没有主导出、原main不存在，仅保留ACP打印/创建证据，不从轨迹重建冒充产物。未改原Skill/task/checker、未补评消除FAIL、未入Gold、0新模型调用、费用null。已向用户询问保留原题单列阻塞或另建明确停机优先的修订题版本；未答复前不执行依赖该选择的修改/付费尝试，继续其他独立任务。


## 用户确认后的处理

2026-10-07T17:29:32.343846+08:00 用户明确确认附件处理：制造题单列task/verifier contract conflict，排除纯Skill Repair F→P，不复现verifier false PASS，原结果/GPT Gold保留。TicToc固定原abort candidate commit_ts，不重新选时间；Claude ACP5/6缺失写历史时忽略current_wts的遗漏已由公开输入独立核实，另存public-missing-history-diagnosis.json。只在冻结原23文件的transaction-trace-analysis原步骤3追加快照变化边界规则+299字节，其余22原字节、反向精确、无新步骤/章节/helper/答案/目标/阈值/task/checker改动。独立Round1 prepared未启动；真实容器输入/runtime模型前gate尚未执行，0新模型。用户附件中的GPT算法/评分policy标签/答案数量/具体ID永久披露隔离，不写入Skill/模型/gate/目标，不继承GPT通过或声称唯一因果。完成目标调整为13有效PASS+1单列conflict，当前12/13，Gold27/28（原14题选择集保留），累计已结束provider539不是费用；12已通过题禁重跑。
