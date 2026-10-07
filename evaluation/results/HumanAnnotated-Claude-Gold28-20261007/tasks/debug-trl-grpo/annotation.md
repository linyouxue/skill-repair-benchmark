# Claude 人工标注：debug-trl-grpo

## 当前状态

2026-10-06T18:59:43.612753+08:00 Round2已独立有效PASS：原verifier12/12、reward1，22/60正常end_turn，22provider全200、16工具/0显式Skill、3份精确全文预载、31完整ACP，错误null。147字节单条契约内联实际执行，真实预verifier导出4文件与停止main23fb027408ba逐字节一致。已更新04增量Gold及Claude兼容副本，新增2/14、总17/29，禁止重跑。原归因及限制见下文。

原Opus有效未通过：debug-trl-grpo-opus47-original-skill-r001-recovery002；reward=0.6，end_turn。证据目录：/mnt/c/Users/linyuanjing/Desktop/skill论文/SkillGen-benchmarking/expanded_original_skill_runs/opus47-openrouter-v1.1-20260919/runs/opus47-original-skill/debug-trl-grpo-opus47-original-skill-r001-recovery002。

GPT未改Skill成功只作范围证据，不继承其归因或产物。诊断、步骤、标签、最小修复及逐轮执行遵循见下文；费用未知null。

## 原始审计与功能步骤

原轮27/60正常end_turn、27provider全200、21工具/0显式Skill、3份主Skill全文精确预载、39完整ACP，Agent/verifier/export错误null。原checker权重0.35+0.25两组全部通过，decode组在未完成推理断言失败，reward0.6；10项已PASS、1项FAIL、最后reward端到端项被本组短路而未运行。没有预算耗尽或infra错误。原轮无真实源文件导出且已无所属容器，保留证据缺口，不从轨迹重建或冒充原产物。

| 步骤 | 输入→输出 | 证据 |
|---|---|---|
| S1 任务与数值路径排查 | 冻结TRL/禁止改脚本→log-softmax、advantage诊断 | ACP3–20 |
| S2 解码契约确定 | 原分支+调用点→三类输入输出 | ACP9、21；trl/rl-post-training |
| S3 局部修复 | 分支契约→库源码改动 | ACP22、23、25 |
| S4 小输入验收及交付 | 真实函数→逐分支结果 | ACP27–38、原verifier |

ACP9正确识别原实现误删无标签文本。首个持久首错ACP21先说unfinished应empty，随后改口将所有无close均pass-through；25删去整个else，使unfinished推理也输出。30 mock探针列出unfinished但只打印、无正确期望断言，31/38将其错误当作完成。原rl-post-training/references/common-pitfalls.md早已定义三类输出，diagnostic-workflow Stage1.2也有unfinished应为空；本轮Agent未读取这两份参考。原trl主条目反把准确policy委托给含缺陷实现。归因为agent_did_not_follow，另记参考未加载/主条目委托错误源的routing问题，不倒推原Skill缺失或唯一因果。

## RI-001 / Round1最小修补

仅替换trl/SKILL.md的decode_and_strip_padding Contract最后一个bullet，将“policy defined in implementation”改为修改前读取原common-pitfalls三类契约、分别保留并逐项验收。参考原文、verify_pipeline.py及其余8文件不变；不新建步骤/helper、不改checker/奖励/训练脚本、不注入测试样本/数值/闭合源码答案。仅强化现有参考入口；一处反向替换逐字节恢复原版。差异53字节。

准备独立fresh验证：Opus4.7、统一BenchmarkExecutor、60parent/32768/no effort/text-only≤1共享预算；task/verifier/输入冻结不变，真实预verifier导出utils、grpo_trainer及禁止改的两个脚本，保留停止main。依赖免费预检后才启动。费用未知null。


## Round1有效FAIL复核与Round2独立最小候选

Round1最早语义首错为ACP9：因希望获得gradient signal，认为未关闭reasoning应返回raw text。ACP28声称读取参考但实际只引用候选入口句；21个工具动作无参考文件读取。ACP29删整个else，33 mock只打印而未用正确期望断言，34/38将unfinished raw text判为正确。原指导仍已存在，入口强化未执行，不能倒推原指导缺失/修改导致回退/唯一因果。ACP31自行选择未缓存gpt2而离线probe失败，随后用mock执行；原verifier正常运行，不将该工具失败记成infra。完整证据round-1-r001-fail-audit.json。

Round2删除未奏效的读取入口句，从原版同一bullet替换为三类原契约：无marker原样保留、已关闭提取首个closing后内容、已打开但无关闭输出空。源于原common-pitfalls原文，不修改参考或verify_pipeline、不新建步骤/helper、不注入checker样本/参数/源码答案。原始agent_did_not_follow归因和原产物缺口保留。后续PASS也不能证明原Skill缺失或唯一因果。候选差异及反向恢复检查见round-2/from-original.diff与repair-plan.json。


## Round2有效PASS与入库证据

ACP9/19直接引用新增主Contract并正确区分无marker/complete/incomplete；25/26保留opened-unclosed=>empty而放行plain，28实测三类输出分别为pass-through/suffix/empty，29/30总结与实际输出一致。没有显式Skill调用或单独参考读取；3份全文首请求精确暴露可核验。原verifier12项全部执行通过，真实4文件与停止main一致，archive36708字节；审计round-2-r001-pass-audit.json。

保留质量限制：Agent mock只打印未assert，checker独立验证；实际源码docstring仍错误概括所有no-close为incomplete；未进行完整训练证明持续学习；没有另导出的verifier源码snapshot，不能声称三方SHA一致。原source-export/container缺口、原agent_did_not_follow与唯一因果未证实保留，不因Gold入库改写。
