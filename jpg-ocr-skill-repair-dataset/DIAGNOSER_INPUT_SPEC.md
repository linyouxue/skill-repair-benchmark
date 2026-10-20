# 诊断与修复方法输入契约

版本：`jpg-multimodal-repair-handoff-20261020-v2`。

“方法可获得”指整个诊断/修复流程的允许访问范围，不要求每个子阶段使用完全相同的prompt。例如MMG Analyzer原本只看轨迹，Skill对齐属于Refiner；应保留这种阶段设计，并记录各阶段实际使用的材料。

## 九项允许信息

| 项目 | 内容及文件 |
|---|---|
| 1. task prompt | `train/task_prompt.md`，字节不变的原Task；本批图片成员由batch manifest提供。 |
| 2. 当前Skill | `train/skills/original/`完整5个Skill和支持文件，及方法自己的当前草稿。原Skill和草稿必须分别标识。 |
| 3. 完整trajectory | 18个选定有效运行的完整生成过程、动作/参数/结果及图像关联。ACP直接读取，完整LLM/ATIF在无损归档内。 |
| 4. 实际输出/output inventory | 真实Excel、`agent_predictions.json`和`output_inventory.json`。预测值是Agent实际输出，不是答案；缺失行和文件须原样标记。 |
| 5. allowed result/execution metadata | `allowed_execution_metadata.json`，包含模型、协议、迭代、终止、正文暴露、导出和评分路径等白名单字段。 |
| 6. 允许的reward/状态 | `allowed_feedback.json`：原官方reward/PASS-FAIL、日期/金额逐字段对错、固定分母汇总及交付问题。 |
| 7. 训练视觉证据 | 120张唯一训练原图。每组20图，三遍共用原图；原运行的实际看图/裁图证据如有，则另按步骤标识其来源。 |
| 8. 对应关系 | batch manifest和run selection把图片、重复、选定attempt、版本及输出关联起来；跨多图的命令保留为批次级事件。 |
| 9. 输入权限 | 只可读取训练材料和方法本地草稿，不读取两个测试集、评测GT、评分断言/源码、隐藏答案或组织者连接配置。 |

## 完整证据与模型输入

本版本按以下契约生成`train/diagnosis/`：ACP动作索引、唯一LLM消息、安全API上下文、包含失败响应和结束原因的实际交换、视觉资产与连续窗口。API消息去重不删除交换顺序；动作数以ACP为准。每个独立窗口引用本组全部原图，图片文件本身不重复存储，真实多次发送的视觉成本另记。读取和免费请求组装入口见[DIAGNOSIS_PREPROCESSING.md](DIAGNOSIS_PREPROCESSING.md)。数据集侧准备不包含各方法真实诊断、修订或实际模型送达验收。

完整档案不能被静默截成首尾。输入超限时按步骤开多个窗口，保留先后顺序、精确来源和未发送范围。整套API历史包含大量重复前缀，不需要重复注入。合并三遍时，每次行为仍保留自己的run ID与步骤编号，不拼成一条虚构执行。

一条命令同时处理多张票时，代码和工具结果只存一次并关联相关票，不能凭猜测分出不存在的单票步骤。精确命令参数需从原LLM记录补查时，注明原记录位置。图片的来源资产与Agent实际观察资产分开标记，不把后来给Diagnoser看的原图称为Agent当时看过的图。

原图应进入真正的`image_url`/`input_image`/供应商对应图像块，或者通过可审计的看图工具交给视觉模型。普通文件路径、Markdown路径或写进文本的Base64均不证明图片已送达。已发送图片也不等于模型理解正确；这里只核查交付证据。

## 版本与评分含义

全部源轨迹由官方V0产生。第一阶段可从V0开始；后续修订草稿没有新的整套rollout，不能把旧错误归因给新草稿，也不能声称修改已经改善正确率。

训练反馈只给正确/错误标记，不含GT字段值、oracle、verifier断言或策展转录。不要把`verifier/test-stdout.txt`、CTRF失败message/trace或整个原始result递交模型；先做允许字段投影。存在于全套评测包中不等于允许进入修复上下文。

正常无Excel是有效交付失败，计入固定分母；不能据此虚构逐票OCR过程。60轮耗尽与真实产物评分、评分基础设施恢复、自然结束分别保留。原历史402的部分产物不属于选定训练例。

## 六阶段安排

按`batch_01`至`batch_06`顺序，每阶段读取20张原图、三次源运行、当前草稿和本方法之前的累计记录。建议新请求只携带本批材料、当前草稿及简短累计记录，避免重复发送前批全部图片。一次阶段可由原方法的多个内部调用完成；六阶段不代表只能调用六次API。内部干预/重放计入方法成本，未经授权不得执行。

最终产物为第六阶段的完整bundle，只修改以下文件：

```text
image-ocr/SKILL.md
openai-vision/SKILL.md
pdf/SKILL.md
video-frame-extraction/SKILL.md
xlsx/SKILL.md
```

附件、helper和其余文件保持原字节；不新增Skill或工具。方法适配中需要不同范围的变体须单独报告。人工修复遵守同样的信息边界。
