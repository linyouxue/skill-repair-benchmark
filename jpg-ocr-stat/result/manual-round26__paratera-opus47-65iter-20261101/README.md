# 人工主线 Round26 / Paratera Opus4.7 / 65父迭代

最终版本为主线人工Round26，完整[五Skill](skills/)共18文件原样冻结，与[已公开历史版本](https://github.com/linyouxue/skill-repair-benchmark/tree/6adffb1e027b55b8b08650cc44811177838bc196/evaluation/results/%E5%AF%B9%E4%BA%8Ejpg-ocr-stat%E7%9A%84%E5%B0%9D%E8%AF%95/skills/bundles/round-26/bundle/skills)及三次实际输入逐字节一致；仅`image-ocr/SKILL.md`相对原版改变。人工修复过程、历次辅助模型未知项、样本专门化及历史oracle/泛化材料接触见[修复来源与披露](evidence/repair/README.md)，不冒充自动方法或严格未见评测。

三次均为2026-11-01使用同一Skill、原22票任务和Paratera `Claude-Opus-4.7`（`paratera/Claude-Opus-4.7`，Chat Completions `/v1`），BenchmarkExecutor/OpenHands CLI `2df8a2835d3f1bd2f2eadf5a7a2e1ad0dfb0d271`、SDK/tools 1.28.1，每次最多65父迭代、共享guard续行最多1次、单请求输出上限16384，reasoning effort未显式设置。任务材料固定于[`556fd216287be7e58480ed5a6dd935ca3370e639`](https://github.com/linyouxue/skill-repair-benchmark/tree/556fd216287be7e58480ed5a6dd935ca3370e639/jpg-ocr-stat)；以各run原始配置和元数据为准，不把当前60步公共默认值改写为本批设置。该批无新增修复或自动选版；此前Round5结果已知后由用户指定这份既有候选。

| 原22票 | 独立run ID | 字段正确率 | 实际父步/上限 | 终止原因 | 原Excel与完整记录 |
|---|---|---:|---:|---|---|
| 第1次 | `jpg-human-r26-original-r1-7de22ee1` | 100.00%（44/44） | 57/65 | `end_turn` | [Excel](evidence/final_runs/run_01/artifacts/stat_ocr.xlsx) · [证据](evidence/final_runs/run_01/) |
| 第2次 | `jpg-human-r26-original-r2-940208d8` | 100.00%（44/44） | 65/65 | `max_iterations` | [Excel](evidence/final_runs/run_02/artifacts/stat_ocr.xlsx) · [证据](evidence/final_runs/run_02/) |
| 第3次 | `jpg-human-r26-original-r3-9721a78c` | 97.73%（43/44） | 65/65 | `max_iterations` | [Excel](evidence/final_runs/run_03/artifacts/stat_ocr.xlsx) · [证据](evidence/final_runs/run_03/) |

**三次字段正确率算术均值为99.24%（131/132字段），严格全对2/3。** run_01有效评分来自同一产物的仅verifier补验，非模型重跑；run_02/03正常耗尽65步，保留原状态。三次完整ACP/LLM、真实Excel及评分均已保存；补验来源、压缩读取方法和证据边界见[evidence/README.md](evidence/README.md)。显式`n_skill_invocations`三次均0，完整正文预载已核验，不声称逐条指导都被遵循。本次仅整理已有结果，新增模型调用与评分调用均0；原生费用未确认。
