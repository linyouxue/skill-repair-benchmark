# SkillHone 冻结候选重跑结果：guard3，21个独立槽位

**本文件和本目录属于重跑诊断，不是新增Skill修复，也不替换上层已发布的79轮主实验。**

本批涉及11条输入、21个独立的“输入/源轮”槽位。每槽复用源轮 `inputs/skills` 的完整冻结候选，
各执行一次原题；同候选也不合并槽位。SkillHone/DSH修复调用为0。

原槽位均为0分；本次官方评分 3/21 满分，其余18槽正常失败。
这不是22条输入的最终修复率，不能与上层79轮统计混算。

## 逐槽对应

| 输入 / 源轮 | 原guard1分数 | 重跑guard3分数 | 原根步→新根步 | 实际guard | 估算美元 |
|---|---:|---:|---:|---:|---:|
| location-data-to-d3 / R3 | 0 | 1 | 4→31 | 1/3 | 1.0196466 |
| location-data-to-d3 / R4 | 0 | 0 | 4→24 | 1/3 | 0.9215266 |
| location-flink-query / R2 | 0 | 0 | 20→40 | 2/3 | 1.3397447 |
| location-flink-query / R3 | 0 | 0 | 17→31 | 2/3 | 0.8154006 |
| location-flink-query / R4 | 0 | 0 | 4→38 | 1/3 | 0.8758795 |
| single-fix-build-google-auto-all / R1 | 0 | 0 | 4→60 | 2/3 | 1.2603804 |
| single-fix-build-google-auto-all / R3 | 0 | 0 | 4→60 | 1/3 | 1.2439840 |
| single-fix-build-google-auto-all / R4 | 0 | 0 | 28→60 | 2/3 | 1.2553776 |
| single-fix-build-google-auto-RI-001 / R2 | 0 | 0 | 5→60 | 1/3 | 1.3726612 |
| single-fix-build-google-auto-RI-001 / R3 | 0 | 0 | 4→60 | 2/3 | 1.2161902 |
| single-fix-build-google-auto-RI-001 / R4 | 0 | 0 | 33→60 | 2/3 | 1.5825981 |
| single-fix-build-google-auto-RI-001 / R5 | 0 | 0 | 4→60 | 2/3 | 1.5618109 |
| single-fix-build-google-auto-RI-002 / R1 | 0 | 1 | 4→34 | 0/3 | 0.5843330 |
| single-flink-query-RI-001 / R1 | 0 | 0 | 11→45 | 1/3 | 1.8826756 |
| single-manufacturing-equipment-maintenance-RI-002 / R2 | 0 | 0 | 4→22 | 0/3 | 0.4530001 |
| single-sec-financial-report-RI-001 / R1 | 0 | 1 | 4→38 | 1/3 | 0.6064468 |
| single-sec-financial-report-RI-002 / R1 | 0 | 0 | 4→30 | 0/3 | 0.3450661 |
| single-sec-financial-report-RI-002 / R2 | 0 | 0 | 4→19 | 1/3 | 0.1900581 |
| single-sec-financial-report-RI-003 / R4 | 0 | 0 | 4→17 | 2/3 | 0.1852879 |
| single-video-silence-remover-all / R1 | 0 | 0 | 46→23 | 2/3 | 0.2881778 |
| single-video-silence-remover-all / R5 | 0 | 0 | 8→34 | 1/3 | 0.6120163 |

## 协议和解释边界

- Tatu GPT-5.2/xhigh，每请求最大输出16384；同一共享BenchmarkExecutor，完整method-skill bundle。
- text-only continuation总上限从1改为3，仍共享每Step60根Agent iteration；全局默认1未改。
- 固定OpenHands CLI commit `2df8a2835d3f1bd2f2eadf5a7a2e1ad0dfb0d271`，SDK/tools1.28.1。
- 三个通过槽实际只使用0或1次guard；没有槽用到第3次，也没有guard额度耗尽。
  单次额外执行有随机性，不能把0→1直接归因于增加guard机会；没有新增guard1对照。
- 全部槽未观察到纯未来承诺式文本终止；D3源R4的占位finish和Google跑满60步仍单独保留。
- 八槽API中断沿原容器/会话/检查点恢复，前缀与续段调用合并，仍为各槽一次有效执行。
  原生恢复保留partial_trajectory、derived_from和training_ready=false，不声明SFT完整。
- Google RI001源R5有用户明确批准的一次人工SIGTERM：仅停止等待密码的sudo，原Agent进程、
  conversation、工作区和预算保持不变。原官方verifier900秒超时后仅从原实际归档补评分，
  无模型重跑。该干预和评分恢复必须随该槽一起解释，不能称完全无人干预。
- 四个任务的镜像运行manifest/config与源实验相同；Flink保留同Java17/Flink1.20.3基底及
  8份逐字节一致公开输入；D3沿同基底/原Dockerfile重建，未固定浏览器的历史二进制一致性未知。
- n_skill_invocations全部为0。17槽每条成功provider instructions包含全部SKILL原字节；
  4个Flink槽因脱敏保留直接原字节观测unknown，不能据此断定正文未进入上下文。
- 已检查公开工具轨迹、完整候选和实际归档；未观察到隐藏Gold/verifier/其他trial访问或评分篡改。
  Google RI002的公开集成测试POM依赖/编码变更单独披露，不泛称完全未改测试相关文件。

## 用量与产物

执行共846次真实供应商请求，838条HTTP200、8条HTTP500；
已观测总tokens 43,946,245，供应商只给total，输入/输出拆分未知。
估算执行费用 $19.6122619，实际账单未知；8条500的用量未知。
trainer兼容字段把total编码到input、output=0，不能当作供应商真实拆分。

`candidates/`保存每槽完整实际冻结bundle，包括原有4个pyc；所有文件均逐路径/字节核验。
`artifacts/`仅从原pre-verifier tar提取实际存在的任务交付，未补造缺失文件；
评分失败时已有交付也保留，缺失和未独立验证项见逐槽artifact-inventory。
`evidence/`保存评分、用量、轨迹清单、只读审计及provider instructions投影。
完整ACP/LLM、training rows和完整工作区tar保留本地；投影不是完整轨迹或训练数据。
导出的result/benchmark_result增加 `rerun_experiment` 标记，原始评分字段未改，canonical本地记录未因此改写。

源79轮主实验与其候选、评分保持不变：[上层主实验](../FINAL_RESULTS.md)。
