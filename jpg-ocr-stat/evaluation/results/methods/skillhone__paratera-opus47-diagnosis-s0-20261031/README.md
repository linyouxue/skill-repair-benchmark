# SkillHone / Paratera Opus4.7 / group_02

最终Skill与修复过程见[原任务提交](../../../../result/skillhone__paratera-opus47-diagnosis-s0-20261031/README.md)及[完整skills](../../../../result/skillhone__paratera-opus47-diagnosis-s0-20261031/skills/)，原生冻结commit `cefb35d9a1adc54ff956c83c7f4406e85947264f`。本目录引用同一版本，不重复放Skill；公开冻结文件固定于Git提交[`87c9af56be340dc6ccb016eb39e7bf751994341f`](https://github.com/linyouxue/skill-repair-benchmark/tree/87c9af56be340dc6ccb016eb39e7bf751994341f/jpg-ocr-stat/result/skillhone__paratera-opus47-diagnosis-s0-20261031/skills)。

数据为[`556fd216287be7e58480ed5a6dd935ca3370e639`的group_02](https://github.com/linyouxue/skill-repair-benchmark/tree/556fd216287be7e58480ed5a6dd935ca3370e639/jpg-ocr-stat/evaluation/group_02)，每次20张/固定40日期金额字段，原生同一verifier。执行模型Paratera Claude-Opus-4.7，统一BenchmarkExecutor/OpenHands CLI2df8a2835d3f1bd2f2eadf5a7a2e1ad0dfb0d271、SDK/tools1.28.1；每次65父步，guard最多1且共享额度，单请求输出上限16384。修复模型与实现细节均在原任务README和已有配置中。

| 组别 | 第1次 | 第2次 | 第3次 | 均值 |
|---|---:|---:|---:|---:|
| group_02 | 95.00% | 95.00% | 95.00% | **95.00%** |

三次均38/40字段，严格全对0/3。全部既定运行保留，正常错误不缩分母，不用泛化结果继续改或挑Skill；未运行group1/3。

| 运行目录 | 字段正确率 | 日期 | 金额 | 已用父步/65 | 原生run ID |
|---|---:|---:|---:|---:|---|
| run_01 | 95.00% | 20/20 | 18/20 | 28 | `jpg-frozen-group_02-r1-38562b97a8` |
| run_02 | 95.00% | 19/20 | 19/20 | 47 | `jpg-frozen-group_02-r2-b34890a803` |
| run_03 | 95.00% | 20/20 | 18/20 | 31 | `jpg-frozen-group_02-r3-940344bdc9` |

每次目录的stat_ocr.xlsx均由该次真实/app tar原样导出；原result.json/benchmark_result.json、原评分和ACP在对应run目录，完整LLM请求响应、actual tar及所有已有原生文件见[无损归档](https://github.com/linyouxue/skill-repair-benchmark/releases/download/jpg-skillhone-opus47-diagnosis-s0-20261031/jpg-skillhone-opus47-group02-20261031.tar.xz)，成员按group_02/run_01、02、03对应。trajectory/README.md列出完整LLM成员路径，文件没有从摘要重造。原生usage保留，实际提供商扣费未知。

独立记录执行端实际图片序列化：三次单请求最大内联图片块分别1、0、4；第2次未观察到直接图片块，不能声称每次都由模型直接看图。修复端实际带图HTTP200的证据另在原任务提交中。所有额外材料接触、人工参与和启发式披露同该README。上传整理新增模型/Verifier调用0。
