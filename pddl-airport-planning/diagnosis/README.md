# 指定GPT-5.2失败轨迹的诊断材料

只选择用户指定归档的这一条真实运行：`pddl-airport-planning-original-skill-v11x-20260908-guarddiag-infra-r003`。固定来源为[index.source](index.json)，模型为openrouter/openai/gpt-5.2、original-skill、execution_ok=true、历史FAIL/reward=0。实际21/60次父迭代，终止原因为`end_turn`；不是按文件名中的infra/recovery判断有效性。

```text
diagnosis/
├── index.json / validation.json   # 固定来源、完整记录索引和离线核对
├── task_prompt.md / inputs.json   # 实际Task与原输入只读清单
├── records/                      # ACP、唯一消息、API上下文/交换、ATIF
└── outputs/                      # 历史状态、允许反馈和产物归档状态
```

## 沿用原 adapter 接入

各方法继续使用现有adapter与原生诊断、修订和选版流程。材料位置如下：

| 材料 | 位置 |
|---|---|
| 原题和原输入 | [task.md](../task.md)、[environment/](../environment/)，文件清单见[inputs.json](inputs.json) |
| 原完整Skill bundle | [environment/skills/](../environment/skills/)，以及方法自己的当前草稿 |
| 完整失败轨迹 | [原始ACP](https://github.com/linyouxue/skill-repair-benchmark/blob/bee9b0df5b04a300735e5009f5238f5d5c8aaf61/evaluation/results/GPT52-AllTasks-RepresentativeRuns-20260916/tasks/pddl-airport-planning/selected_run/trajectory/acp_trajectory.jsonl)、[完整LLM请求/响应](https://github.com/linyouxue/skill-repair-benchmark/blob/bee9b0df5b04a300735e5009f5238f5d5c8aaf61/evaluation/results/GPT52-AllTasks-RepresentativeRuns-20260916/tasks/pddl-airport-planning/selected_run/trajectory/llm_trajectory.jsonl)、[ATIF](https://github.com/linyouxue/skill-repair-benchmark/blob/bee9b0df5b04a300735e5009f5238f5d5c8aaf61/evaluation/results/GPT52-AllTasks-RepresentativeRuns-20260916/tasks/pddl-airport-planning/selected_run/trainer/atif.json) |
| 允许反馈和运行状态 | [allowed_feedback.json](outputs/allowed_feedback.json)、[execution_metadata.json](outputs/execution_metadata.json)、[output_inventory.json](outputs/output_inventory.json) |

原始轨迹是现有方法adapter的输入；包内`records/`仅为完整记录的整理索引，关联关系见[index](index.json)。公共档案中的redaction保留原样。LLM整理记录保留Responses输出、推理/消息/function_call、首条响应中的Skill正文预载instructions及最后一次响应；重复请求历史以有序ID关联到完整唯一消息。

修复后的完整Skill bundle仍通过`BenchmarkExecutor.run(task_id=..., condition="method-skill", skill_bundle=...)`执行，具体见[统一adapter接入](../README.md#统一-adapter-接入)。本目录不提供另一套方法adapter，也不改变统一执行器接口。

## 允许反馈与缺失项

`outputs/allowed_feedback.json`仅提供原reward和原CTRF测试名称/通过失败状态，不带断言消息或参考答案。原输出文件/JAR/工作区没有归档，状态为`not_archived`；这不证明模型未生成文件。当前正确率为null，不能由CTRF通过比例反推，也不借用其他模型产物或策展计划补造。

完整skill正文已预载到历史Agent；实际invoke_skill/activate_skill/Skill调用数为0，正文预载证据在首条LLM响应的`/response/body/instructions`。这两项分别记录，不能把可用或0次显式调用直接当作正文没有提供。新输入的GT、oracle、已修好参考skill和verifier断言不进入修复输入。


真实诊断、修订、选版及原题执行证据沿用方法自身记录格式，最终交付见[result说明](../result/README.md)。离线材料本身不能证明模型已读取或理解，需以真实请求、工具记录和实际产物为准。

## 离线重建

在包含固定源日志、Git对象和既有API安全参数整理函数的完整checkout中：

```bash
python pddl-airport-planning/tools/prepare_diagnosis.py --refresh
python pddl-airport-planning/tools/prepare_diagnosis.py --validate-only
```

构建核对固定提交Git blob，只刷新索引登记的同源派生文件，不改README或历史运行。方法接入直接使用上述材料及现有adapter，无需执行重建命令；免费检查不代表已经运行修复方法。
