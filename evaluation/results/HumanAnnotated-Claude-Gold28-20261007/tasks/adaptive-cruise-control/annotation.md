# Claude 人工标注：adaptive-cruise-control

## 当前状态

2026-10-06T17:50:12.282957+08:00 Round1有效PASS，原verifier12/12、reward1，24/60正常end_turn、24provider全200、21工具/0显式Skill、5份全文精确预载、38完整ACP。7文件预导出/verifier/停止容器三方逐字节相同，见round-1-r001-pass-audit.json与fresh-artifact-threeway.json。不重跑本题。

## 基线与有效性

原rollout adaptive-cruise-control-opus47-protocol-v1-r001；execution_ok=true、reward0、原verifier11/12；34/60parent、34provider、27工具、正常end_turn。错误/Agent/verifier/export均null，完整46条ACP；n_skill_invocations=0，但5份Skill全文预载digest匹配。不是预算耗尽、无Skill暴露或基础设施失败。原artifacts为空；verifier目录保留真实源文件/CSV/YAML/report，不重建或冒充Agent独立导出。

## 功能步骤

| 步骤 | 输入→输出 | 对应Skill/证据 |
|---|---|---|
| S1 输入及契约清点 | CSV/YAML→模式/动力学/目标 | csv-processing、yaml-config；ACP3–7 |
| S2 控制器与模拟器 | PID+模式+相对运动→可运行代码 | pid-controller、vehicle-dynamics；ACP8–11、19–22 |
| S3 离线调参及性能判定 | 真实模拟误差→最终gains | simulation-metrics；ACP13、28–31，tune.py |
| S4 写盘及最终验收 | 固定gains→CSV/report | simulation-metrics；ACP32–45，原verifier |

## 首错、下游与归因

首个未纠正的关键误差口径在ACP13的score_distance：先对有正负号的distance_error求平均，再取abs，振荡可互相抵消。ACP19–22修复了此前把传感器距离直接用于闭环模拟的问题；该问题已自纠，不作为本候选修补项。ACP28将采样改为自行选定40–70秒窗口并取后半段，仍保留abs(mean(error))；ACP30据该指标接受参数。ACP38报告同类signed bias约0.099米，ACP39/45声称全目标满足，但原verifier TestDistanceControl 用mean(abs(error))得到2.5568673267326734米，11/12有效FAIL。窗口与指标差异分别保留，候选不注入50–60秒隐藏检查窗口。

RI-001拟标签skill_ambiguous_guidance，secondary agent_metric_definition_mismatch_and_premature_success_claim。原simulation-metrics已含定值目标abs(target-final_mean)示例，该偏差指标本身数学上有效，不记为一概错误；原文没有区分偏差与振荡跟踪误差大小。Agent在具体任务中选错reducer，不能证明原Skill唯一因果。免费CSV交叉复算及各真实文件SHA见original-audit.json。

## Round1最小修改

仅在原simulation-metrics/SKILL.md的Steady-State Error条目替换一句说明，区分定值绝对偏差与每个稳态段的mean absolute tracking error，并要求调参与最终验收使用一致指标/数据选择。保留原代码和结构；无新helper、参数答案、测试时间、隐藏阈值。其余4份Skill逐字节不变，反向一处替换恢复原版，diff见round-1/from-original.diff。测试本候选的整体结果，不预设通过或单句必要性。

## 执行与验收

原冻结task、input、verifier不变；Opus4.7/60parent/32768输出/no effort/最多一次共享预算text-only续跑。复用固定CLI/SDK runtime、独立进程/稳定cwd/题锁及Docker启动锁、独立非重叠IPAM；verifier前归档真实源代码、YAML、CSV及report，保留停止main容器。PASS后核对全部12项、完整轨迹与实际指标/reducer执行、导出，再局部入Claude RI/D Gold；FAIL保留并诊断，不无变化重跑。

## Round1验收与限制

ACP20明确引用新增指标说明，23在tune.py落实MAE，29从真实交付CSV验算。实际MAE40–70为0.254224489556714、原checker50–60为0.2684458905721237，min_distance18.272602109847668。

一次fresh有效PASS，不能证明单句修补必要性或原Skill唯一因果；40–70秒窗口由Agent依据可见CSV选择而非注入checker窗口。MAE reducer及采样窗一致，但tune.py使用更新后ego_speed推进距离，simulation.py使用更新前速度，离线调参与交付动力学并非逐步相同，故调参MAE约0.262、min_distance19.44与交付0.254224/18.272602有差异。该质量限制不被12/12 PASS掩盖。

归因保留skill_ambiguous_guidance与Agent指标定义/过早成功宣称；原偏差示例不被改记为普遍错误。Skill+218字节的一处修补fresh通过，不修改原verifier。
