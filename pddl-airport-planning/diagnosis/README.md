# 指定GPT-5.2失败轨迹的诊断材料

只选择用户指定归档的这一条真实运行：`pddl-airport-planning-original-skill-v11x-20260908-guarddiag-infra-r003`。固定来源为[index.source](index.json)，模型为openrouter/openai/gpt-5.2、original-skill、execution_ok=true、历史FAIL/reward=0。实际21/60次父迭代，终止原因为`end_turn`；不是按文件名中的infra/recovery判断有效性。

```text
diagnosis/
├── index.json / validation.json   # 固定来源、记录/窗口索引与无损验证
├── task_prompt.md / inputs.json   # 实际Task与原输入只读清单
├── records/                      # ACP、唯一消息、API上下文/交换、ATIF
├── windows/                      # 12个连续无损窗口
└── outputs/                      # 历史状态、原测试对错、原产物未归档说明
```

每个窗口含实际Task、原/当前skill、原输入索引、允许反馈和该窗记录。公共档案中的redaction保持原样，不逆向恢复。原API采用Responses输出形状，推理、消息、function_call以及首条响应中实际记录的预载instructions均有独立记录/上下文，不丢掉最后一次响应。重复请求历史默认保留有序ID；所有唯一消息另行分窗。

## 读取

从仓库根目录运行：

```bash
python pddl-airport-planning/tools/diagnosis_io.py packet --window w0001 --out /tmp/pddl-airport-planning-window.json
python pddl-airport-planning/tools/diagnosis_io.py record --id 'pddl-airport-planning-original-skill-v11x-20260908-guarddiag-infra-r003:e0001' --out /tmp/pddl-airport-planning-exchange.json
python pddl-airport-planning/tools/diagnosis_io.py input --path environment/problem.json --out /tmp/pddl-airport-planning-input.json
```

`packet`返回`messages`，不会调用模型。`input`按清单完整读取PDDL、Java、文本或解压CSV，不静默截断；PDF仍用方法自己的PDF读取工具处理原文件。packet可加`--draft-dir /path/to/skills --history /path/to/history.md`，需要完整重复请求前缀时加`--expand-request-history`。原输入只在environment保存一份，不在每窗反复内联全部CSV或30个机场实例。

方法也可用importlib加载`tools/diagnosis_io.py`，调用`load_window(task_dir, 'w0001')`、`load_record(task_dir, record_id)`、`load_input(task_dir, indexed_path)`。窗口大小是源记录分段长度，不是模型token、调用或费用限制；关联展开后packet可能更大。哪些材料真正被消费，应以方法的真实请求/工具记录为准。

## 允许反馈与缺失项

`outputs/allowed_feedback.json`仅提供原reward和原CTRF测试名称/通过失败状态，不带断言消息或参考答案。原输出文件/JAR/工作区没有归档，状态为`not_archived`；这不证明模型未生成文件。当前正确率为null，不能由CTRF通过比例反推，也不借用其他模型产物或策展计划补造。

完整skill正文已预载到历史Agent；实际invoke_skill/activate_skill/Skill调用数为0，正文预载证据在首条LLM响应的`/response/body/instructions`。这两项分别记录，不能把可用或0次显式调用直接当作正文没有提供。新输入的GT、oracle、已修好参考skill和verifier断言不进入诊断packet。

## 可选过程保存

沿用JPG操作习惯，`save-result`可在包外的新目录归档方法自己的diagnosis、完整skills、history和全窗口coverage；不是强制的新提交schema。coverage每窗一次，`consumed`需真实请求/工具记录引用，`skipped`需实际原因；不会认证模型理解：

```bash
python pddl-airport-planning/tools/diagnosis_io.py save-result --state-dir /tmp/pddl-airport-planning-method-state --diagnosis /path/to/diagnosis.md --candidate-dir /path/to/skills --history /path/to/history.md --coverage /path/to/coverage.json
```

最终上传以[result说明](../result/README.md)为准，不用辅助工具写入任务包内部。

## 离线重建

在包含固定源日志、Git对象及既有JPG无损分窗工具的完整checkout中：

```bash
python pddl-airport-planning/tools/prepare_diagnosis.py --refresh
python pddl-airport-planning/tools/prepare_diagnosis.py --validate-only
```

构建核对固定提交Git blob，只刷新索引登记的同源派生文件，不改README或历史运行。消费者只读prepared包不需要Git或联网。免费检查不等于已经调用Diagnoser或跑完修复方法。
