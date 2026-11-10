# SkillTTA / Claude-Opus-4.7（Paratera strict）

- 最终 Skill 版本：`skilltta-claude-opus-4.7-paratera-strict-final`，已冻结；直接位于 `skills/`，包含完整 5 个 Skill、18 个文件。
- 方法与代码版本：SkillTTA retrieval + synthesis、37 个多模态诊断窗口、两轮迭代修复；本次实际实现快照见 `evidence/implementation/`。
- 实际模型与配置：修复模型和三次最终执行模型均为 Paratera 的 `Claude-Opus-4.7`，服务地址为 `https://llmapi.paratera.com`；密钥未写入提交材料。最终任务执行使用 OpenHands/BenchFlow，父迭代上限真实配置为 65，Skill 通过挂载后的原生 `invoke_skill` 使用，未把完整 `SKILL.md` 预加载到提示词。
- 最终版本标识：修复适配器内容审计哈希 `3fccc7e7232494db63d7d6d37f1eb292c61e0ab4dee227a5a25d7d3941bc8ead`；三次执行器挂载清单哈希均为 `sha256:3b08efcd569bf2ce7819d884a0772e921cc155b3a0b259b5bc0a83ce296f2e35`。两者计算口径不同，均指向本目录同一冻结文件集。
- 修复材料与版本：仅使用原 22 张 JPG 小票、原 Task、原 5 个 Skill，以及 `evidence/diagnosis_package/` 中允许使用的诊断材料。37/37 个诊断请求均实际发送 22 个 `image/jpeg` 图片内容块，HTTP 均为 200，响应模型均核验为 `Claude-Opus-4.7`；请求、审计、响应和收据见 `evidence/repair/model_calls/`。
- 方法内部新增执行：37 个多模态诊断窗口、一次 synthesis 和两轮 repair；完整入口见 `evidence/repair/`。第 2 轮首次响应因长度截断，保留原记录后用紧凑请求重试成功。
- 三次最终执行与原 Excel：三次均从任务初始状态独立运行，使用同一冻结 Skill、同一执行模型和相同配置；每次原始 `stat_ocr.xlsx`、评分、ACP/LLM 轨迹及执行元数据均位于对应的 `evidence/final_runs/run_0N/`。
- 必要披露：未读取 oracle 解法、参考答案值或 verifier 断言；未使用 group2 或其他扩展图片进行修复、选版或回挑。SkillTTA 的 synthesis 输入使用了方法内部既有的 retrieval/task-guidance。适配器与 runner 由代理修改；最终 Skill 文本由模型生成并自动应用，没有人工逐字修改 Skill。`image-ocr/SKILL.md` 中包含从原 22 图诊断所得的小票版式/OCR 样本模式，作用是提高日期和金额抽取稳健性。
- 本目录不包含后续 group2 泛化结果；按上传规范，泛化评测另行提交。

| 评测集合 | 第 1 次字段正确率 | 第 2 次 | 第 3 次 | 三次均值 |
|---|---:|---:|---:|---:|
| 原 22 张小票（每次 44 字段） | 43/44 = 97.7273% | 41/44 = 93.1818% | 43/44 = 97.7273% | 127/132 = 96.2121% |

## 三次运行索引

| 运行 | run ID | 65 轮配置 / 实际使用 | 终止原因 | 原 Excel | 评分与完整证据 |
|---|---|---:|---|---|---|
| 1 | `jpg-ocr-stat-skilltta-claude47-paratera-strict-final-r001` | 65 / 19 | `end_turn` | `evidence/final_runs/run_01/artifacts/stat_ocr.xlsx` | `evidence/final_runs/run_01/` |
| 2 | `jpg-ocr-stat-skilltta-claude47-paratera-strict-final-r002` | 65 / 65 | `max_iterations`（普通 FAIL，照实保留） | `evidence/final_runs/run_02/artifacts/stat_ocr.xlsx` | `evidence/final_runs/run_02/` |
| 3 | `jpg-ocr-stat-skilltta-claude47-paratera-strict-final-r003` | 65 / 54 | `end_turn` | `evidence/final_runs/run_03/artifacts/stat_ocr.xlsx` | `evidence/final_runs/run_03/` |

评分明细位于各运行的 `verifier/accuracy.json`、`verifier/ctrf.json` 和 `verifier/reward.txt`；执行器原始记录位于 `executor_request.json`、`result.json`、`benchmark_result.json` 和 `config.json`。证据目录说明及分卷轨迹恢复方法见 `evidence/README.md`。
