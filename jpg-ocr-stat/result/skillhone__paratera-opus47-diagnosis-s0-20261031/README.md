# SkillHone / Paratera Opus4.7 / diagnosis S0

最终完整5个Skill位于[skills/](skills/)，原生冻结commit为`cefb35d9a1adc54ff956c83c7f4406e85947264f`；公开冻结Skill文件固定于Git提交[`87c9af56be340dc6ccb016eb39e7bf751994341f`](https://github.com/linyouxue/skill-repair-benchmark/tree/87c9af56be340dc6ccb016eb39e7bf751994341f/jpg-ocr-stat/result/skillhone__paratera-opus47-diagnosis-s0-20261031/skills)。实际只修改[image-ocr/SKILL.md](skills/image-ocr/SKILL.md)的Receipt Extraction Patterns（第341行起，新增60行），支持文件及许可完整保留。[真实diff](evidence/repair/skill.diff)。

方法使用固定官方SkillHone `7e0ce7ce6e8239cb870822d3db5ff66c5ef644d1`的Tracker/runRepair/runBenchmark及DSH `0.2.1-rc.2`，外层按用户指定从历史diagnosis S0先修复，再原题评测；最多5修复轮或候选原题满分即停，最终只按训练反馈选版。这是有训练诊断输入的外层迭代安排，没有使用默认CLI完整Explorer/社区参考下载流程。实际执行1轮，候选开发probe满分后冻结，未声称完成5轮。代码与配置见[evidence/method-code](evidence/method-code/)。

修复模型和执行模型均为Paratera `Claude-Opus-4.7`，Chat Completions，根base_url为https://llmapi.paratera.com，实际路由/v1；单请求输出上限16384，未声称配置xhigh。执行使用共享BenchmarkExecutor/OpenHands，CLI `2df8a2835d3f1bd2f2eadf5a7a2e1ad0dfb0d271`、SDK/tools1.28.1。65父步只在私有JPG worker贯通policy/runtime/result contract，公共执行器默认仍60；真实配置和原生结果保留。

原Task、22原图、5原Skill和发布diagnosis来自数据commit[`556fd216287be7e58480ed5a6dd935ca3370e639`](https://github.com/linyouxue/skill-repair-benchmark/tree/556fd216287be7e58480ed5a6dd935ca3370e639/jpg-ocr-stat)，未把oracle/verifier或泛化反馈交给修复端。历史S0仅有离线40/44反馈，不冒充本次新基线。第1次下表是方法内部已发生的候选开发执行，确实使用同一最终Skill并符合65总额，因此按提交说明计入3次原题；第2/3次是冻结后的独立追加确认。它们各从原任务初态开始，第1次的checkpoint接续只算同一次，38步含原中断和权限故障步；原生接续段结果不改写，完整前段/接续段分别保留。

| 原22票 | 字段正确率 | 日期 | 金额 | 累计父步/65 | 原生run ID | 原Excel/评分/轨迹 |
|---|---:|---:|---:|---:|---|---|
| 第1次 | 100.00% | 22/22 | 22/22 | 38 | `jpg-ocr-stat-probe-0-0-4fec25956e-checkpoint-03` | [run_01](evidence/final_runs/run_01/) |
| 第2次 | 100.00% | 22/22 | 22/22 | 58 | `jpg-frozen-original-r1-6df67b452d` | [run_02](evidence/final_runs/run_02/) |
| 第3次 | 93.18% | 19/22 | 22/22 | 21 | `jpg-frozen-original-r2-2d3ab8c65f` | [run_03](evidence/final_runs/run_03/) |

**三次同最终版本均值：97.73%，严格全对2/3。** 其中第1次用于开发停止/选版；只看冻结后两次追加确认时均值为96.59%、全对1/2。这两个统计口径分别披露，不把开发probe称为盲测，也不挑最好一次。固定每次44字段，正常错误全部保留。

真实DSH修复端22次请求中9次带实际图片并HTTP200、最多6个内联块、native read_image历史6次；[标量证据](evidence/repair/dsh-image-evidence.json)与原生压缩会话/附件可对应，不宣称全部22图逐一视觉读取。OpenHands原题执行的直接图片块记录也原样保留，其中第3次未观察到直接图片块，不用vision能力配置冒充看图。

必要披露：Codex只写接线、调度、恢复和验收，没有手写/人工改候选Skill。DSH新增地区/版式启发式（马来西亚/东南亚日期与rounding后TOTAL优先）及47.70→47.68等金额/日期示例，位置与作用见上述新增节，原样保留，没有逐文件答案表。宿主Codex曾意外见过旧group_01/03答案片段，见[披露](evidence/repair/host-context-disclosure.md)；本次使用全新隔离DSH上下文，不传该聊天或泛化资料。没有同期配对基线，旧原Skill另有单次满分记录，因此不声称因果修复增益或严格未见结论。

完整真实修复日志、原生session与附件、全部原题运行段及实际/app tar见[证据归档](https://github.com/linyouxue/skill-repair-benchmark/releases/download/jpg-skillhone-opus47-diagnosis-s0-20261031/jpg-skillhone-opus47-original-repair-20261031.tar.xz)；[成员索引](evidence/repair/native-evidence.json)。原生配置、已有usage、CTRF/accuracy/reward和6份真实Excel均保留；提供商实际扣费未知。上传整理新增模型/Verifier调用0。group_02的3次结果另见[methods目录](../../evaluation/results/methods/skillhone__paratera-opus47-diagnosis-s0-20261031/README.md)，未回传修复或选版。
