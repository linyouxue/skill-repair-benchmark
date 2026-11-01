# SkillHone / Tatu GPT-5.2 xhigh / 冻结后三组结果

同一最终完整Skill与修复过程见[原任务提交](../../../result/skillhone__tatu-gpt52-xhigh-diagnosis-s0-20261031/README.md)及[skills](../../../result/skillhone__tatu-gpt52-xhigh-diagnosis-s0-20261031/skills/)，公开冻结commit `371591d0d41c82960d98289ec08e01f589a7d5fb`、原生commit `2c6f56b0ea0925eb685be06845dbdfe8665c4f7f`。

修复和执行模型均为Tatu GPT-5.2 / xhigh / 单请求输出上限16384。统一BenchmarkExecutor/OpenHands CLI `2df8a2835d3f1bd2f2eadf5a7a2e1ad0dfb0d271`、SDK/tools1.28.1；每次60父步含最多guard1，无任务子Agent，原生API接续共享原额度。任务/发布diagnosis来源`556fd216287be7e58480ed5a6dd935ca3370e639`，评分item-accuracy-v1。

| 阶段 | 第1次 | 第2次 | 第3次 | 均值 | 全对 |
|---|---:|---:|---:|---:|---:|
| original | 100.00% | 100.00% | — | **100.00%** | 2/2 |
| group_01 | 0.00% | 0.00% | 0.00% | **0.00%** | 0/3 |
| group_02 | 100.00% | 100.00% | 100.00% | **100.00%** | 3/3 |
| group_03 | 0.00% | 0.00% | 0.00% | **0.00%** | 0/3 |

original行仅作关联，原题真实证据在result提交；本目录保留group_01/02/03各3次独立运行。此为2026-10-31已获单独授权、实际完成的历史扩展评测；后续PDDL只运行group2的政策不删除这些已有成绩，不在本次上传新增模型调用。

PDDL实际修复1轮，原生max-tokens停止后host只提交已有输出字节；开发probe为1后冻结。追加原题r1、group_01 r3、group_03 r2各有一次用户授权工具中断，共3个最终样本有人为工具干预，不称无人干预。group_01 r2与group_03 r1到原6小时watchdog，官方0保留有效预算停止；原execution_ok=false、父步和轨迹/正文暴露完整性未知项原样保留，不补造。原题r1的旧grep中断以及另外两条长计算/遗留后台进程清理均有真实收据。

各组/evidence/run_01..03的canonical-response和acceptance记录真实run ID、累计步数、人工干预、原评分和缺失项。完整LLM/ACP/真实工作区及Java/JAR/输出见[泛化原生归档](https://github.com/linyouxue/skill-repair-benchmark/releases/download/pddl-flink-skillhone-gpt52-diagnosis-s0-20261101/pddl-airport-planning-skillhone-generalization-20261101.tar.xz)，[索引](evidence/native-run-index.json)对应每个native-runs成员。Git实际产物从各自原tar解出，原归档与已有SHA记录保持，不用摘要补造。所有正常0/部分正确保留，不缩分母、不回流选版；费用和用量见原任务证据。
