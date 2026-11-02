# SkillHone / Tatu GPT-5.2 xhigh / diagnosis S0

完整冻结Skill见[skills/](skills/)，原生选中commit `2c6f56b0ea0925eb685be06845dbdfe8665c4f7f`，第1轮。公开Skill固定于`371591d0d41c82960d98289ec08e01f589a7d5fb`，与已验收冻结ZIP逐字节一致。

修复和执行模型均为Tatu GPT-5.2 / xhigh / 单请求输出上限16384。统一BenchmarkExecutor/OpenHands CLI `2df8a2835d3f1bd2f2eadf5a7a2e1ad0dfb0d271`、SDK/tools1.28.1；每次60父步含最多guard1，无任务子Agent，原生API接续共享原额度。任务/发布diagnosis来源`556fd216287be7e58480ed5a6dd935ca3370e639`，评分item-accuracy-v1。

方法为官方SkillHone `7e0ce7ce6e8239cb870822d3db5ff66c5ef644d1`与DSH `0.2.1-rc.2`，外层从给定S0修复、原题开发评测、最多5轮或通过即停；并非默认完整Explorer/社区下载流程。第二轮起只用刚结束的真实原题失败轨迹、实际工作区和允许反馈重建当前diagnosis，全新隔离上下文，不叠加旧S0或泛化资料。接线/恢复时期代码快照见[evidence/method-code](evidence/method-code/)，执行时事实以原生请求、会话和配置为准。

PDDL实际修复1轮，原生max-tokens停止后host只提交已有输出字节；开发probe为1后冻结。追加原题r1、group_01 r3、group_03 r2各有一次用户授权工具中断，共3个最终样本有人为工具干预，不称无人干预。group_01 r2与group_03 r1到原6小时watchdog，官方0保留有效预算停止；原execution_ok=false、父步和轨迹/正文暴露完整性未知项原样保留，不补造。原题r1的旧grep中断以及另外两条长计算/遗留后台进程清理均有真实收据。

| 阶段 | 第1次 | 第2次 | 第3次 | 均值 | 全对 |
|---|---:|---:|---:|---:|---:|
| original | 100.00% | 100.00% | 100.00% | **100.00%** | 3/3 |
| group_01 | 0.00% | 0.00% | 0.00% | **0.00%** | 0/3 |
| group_02 | 100.00% | 100.00% | 100.00% | **100.00%** | 3/3 |
| group_03 | 0.00% | 0.00% | 0.00% | **0.00%** | 0/3 |

上表original按最终选中轮次的开发执行1次＋冻结后追加确认2次统计。第1次为第1轮候选的开发probe，参与停止/选版；第2、3次为独立追加确认，三次不全是冻结后盲测。断点接续不另算独立样本。全部既定运行均保留，不挑最好一次；旧S0 binary0/连续分未知不冒充新baseline。最终测试不回流修复、调参或选版。候选真实变更见[evidence/repair/selected-skill.diff](evidence/repair/selected-skill.diff)，开发候选及选择依据见[原生轮次记录](evidence/repair/development-rounds.json)。Codex只接线、恢复与验收，未手写候选Skill；原输入/训练示例及方法新增规则原样保留，具体位置和作用由真实diff与会话披露，不据已有分数声称因果增益。

## 原题三次运行与证据

三次使用同一最终冻结Skill；每次原题执行上限60父迭代。第1次的已有[验收记录](evidence/repair/round-1/acceptance.json)核对冻结bundle与真实计划，原段1步＋checkpoint接续13步合计14步，只算一次执行。各次原始配置、结果及评分保留原身份，不为调整展示次序重命名或改写。

| original次序 | 执行身份 | 原生run ID | 累计父步/60 | 配置、评分与轨迹 |
|---|---|---|---:|---|
| 第1次 | 第1轮选中候选开发执行 | `pddl-airport-planning-probe-0-0-d804f88f8a-checkpoint-01` | 14 | [开发运行](evidence/development_native/pddl-airport-planning-probe-0-0-d804f88f8a-checkpoint-01/) |
| 第2次 | 冻结后追加确认r1 | `pddl-airport-planning-frozen-original-r1-03bafec3` | 27 | [确认运行r1](evidence/final_runs/run_01/) |
| 第3次 | 冻结后追加确认r2 | `pddl-airport-planning-frozen-original-r2-11fcb2e9` | 23 | [确认运行r2](evidence/final_runs/run_02/) |

第1次的完整LLM及评分前真实工作区已在下述原题与修复归档中，成员前缀为`native-runs/pddl-airport-planning-probe-0-0-d804f88f8a-checkpoint-01/`；真实两份计划位于其`artifacts/pre-verifier-workspace.tar.gz`内。原中断前段另以`native-runs/pddl-airport-planning-probe-0-0-d804f88f8a/`保留，不能把两段算成两次。

完整修复原生Zstd会话/请求审计/harness日志、开发执行及追加原题全部保留段、LLM和真实/app tar见[原题与修复归档](https://github.com/linyouxue/skill-repair-benchmark/releases/download/pddl-flink-skillhone-gpt52-diagnosis-s0-20261101/pddl-airport-planning-skillhone-original-repair-20261101.tar.xz)；[成员/运行索引](evidence/native-run-index.json)定位native-runs和repair成员。Git内保留原始result/config/ACP/accuracy/CTRF/reward及实际文本产物；大JAR位于每次真实pre-verifier tar，见artifact-members.json，未重造。

泛化三组各3次见[对应评测提交](../../evaluation/results/skillhone__tatu-gpt52-xhigh-diagnosis-s0-20261031/README.md)，引用本同一冻结Skill，不重复提交原输入/原始S0失败轨迹。API成功接续前段与后段都在归档内；已废弃不可恢复尝试仅保留ID/原因/调用/费用简记。原n_skill_invocations与完整正文预载证据分别报告，未知项保持未知；不把“可用”或“预载”当作逐条遵循。

[用量](evidence/usage.json)区分现存段已知执行器估算、未知段、DSH修复统计及废弃调用；估算不是供应商实际扣费，后者未知。附件中已有原生文件字节保留；上传整理新增模型/Verifier调用0，未自动合并main。

选中版本只改`pddl-skills/SKILL.md`：明确problem/plan对象传入、使用PDDLWriter序列化并以plan validator验证，不改变原规划器支持文件。
