# SkillHone / Tatu GPT-5.2 xhigh / diagnosis S0

完整冻结Skill见[skills/](skills/)，原生选中commit `6ad7401191933a4bef0f9527aba2e82e1f559d1a`，第2轮。公开Skill固定于`371591d0d41c82960d98289ec08e01f589a7d5fb`，与已验收冻结ZIP逐字节一致。

修复和执行模型均为Tatu GPT-5.2 / xhigh / 单请求输出上限16384。统一BenchmarkExecutor/OpenHands CLI `2df8a2835d3f1bd2f2eadf5a7a2e1ad0dfb0d271`、SDK/tools1.28.1；每次60父步含最多guard1，无任务子Agent，原生API接续共享原额度。任务/发布diagnosis来源`556fd216287be7e58480ed5a6dd935ca3370e639`，评分item-accuracy-v1。

方法为官方SkillHone `7e0ce7ce6e8239cb870822d3db5ff66c5ef644d1`与DSH `0.2.1-rc.2`，外层从给定S0修复、原题开发评测、最多5轮或通过即停；并非默认完整Explorer/社区下载流程。第二轮起只用刚结束的真实原题失败轨迹、实际工作区和允许反馈重建当前diagnosis，全新隔离上下文，不叠加旧S0或泛化资料。接线/恢复时期代码快照见[evidence/method-code](evidence/method-code/)，执行时事实以原生请求、会话和配置为准。

Flink实际完成5轮开发，分数[0,0.7409365558912386,0.7409365558912386,0,0]；第2轮为最高版本并冻结，第5轮原生确已completed、产生另一候选且开发0，未选择它，不把早期摘要的未改动说法当结论。所有冻结后运行均保留；group_03 r3正常0且未生成JAR，不补写或重做。

| 阶段 | 第1次 | 第2次 | 第3次 | 均值 | 全对 |
|---|---:|---:|---:|---:|---:|
| original | 74.09% | 74.09% | — | **74.09%** | 0/2 |
| group_01 | 44.95% | 44.95% | 44.95% | **44.95%** | 0/3 |
| group_02 | 46.90% | 53.10% | 46.90% | **48.97%** | 0/3 |
| group_03 | 50.00% | 50.00% | 0.00% | **33.33%** | 0/3 |

上表original仅指冻结后追加原题2次；开发probe与确认结果分开，断点接续不另算独立样本。全部既定运行均保留，不挑最好一次；旧S0 binary0/连续分未知不冒充新baseline。最终测试不回流修复、调参或选版。候选真实变更见[evidence/repair/selected-skill.diff](evidence/repair/selected-skill.diff)，开发候选及选择依据见[原生轮次记录](evidence/repair/development-rounds.json)。Codex只接线、恢复与验收，未手写候选Skill；原输入/训练示例及方法新增规则原样保留，具体位置和作用由真实diff与会话披露，不据已有分数声称因果增益。

完整修复原生Zstd会话/请求审计/harness日志、开发执行及追加原题全部保留段、LLM和真实/app tar见[原题与修复归档](https://github.com/linyouxue/skill-repair-benchmark/releases/download/pddl-flink-skillhone-gpt52-diagnosis-s0-20261101/flink-query-skillhone-original-repair-20261101.tar.xz)；[成员/运行索引](evidence/native-run-index.json)定位native-runs和repair成员。Git内保留原始result/config/ACP/accuracy/CTRF/reward及实际文本产物；大JAR位于每次真实pre-verifier tar，见artifact-members.json，未重造。

泛化三组各3次见[对应评测提交](../../evaluation/results/skillhone__tatu-gpt52-xhigh-diagnosis-s0-20261031/README.md)，引用本同一冻结Skill，不重复提交原输入/原始S0失败轨迹。API成功接续前段与后段都在归档内；已废弃不可恢复尝试仅保留ID/原因/调用/费用简记。原n_skill_invocations与完整正文预载证据分别报告，未知项保持未知；不把“可用”或“预载”当作逐条遵循。

[用量](evidence/usage.json)区分现存段已知执行器估算、未知段、DSH修复统计及废弃调用；估算不是供应商实际扣费，后者未知。附件中已有原生文件字节保留；上传整理新增模型/Verifier调用0，未自动合并main。

选中版本只改`senior-data-engineer/SKILL.md`的Task-Focused Playbooks：先编译/补POJO、gz CSV按列解析、微秒转毫秒、SUBMIT事件和按jobId的10分钟session window、tuple输出及既有test-injection钩子。包含原任务结构相关的规则和示例，原样保留，不声称为完全任务无关指导。

每次实际评分用tuple输出原件在对应`verifier/actual-flink.txt`（存在时原样保留）；并非从准确率重造，原生缺失/空输出如实保留。Java源码由评分前真实tar导出，大JAR在该tar中。
