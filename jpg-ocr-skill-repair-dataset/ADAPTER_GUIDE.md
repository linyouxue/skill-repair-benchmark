# 给方法负责人的JPG多模态adapter适配说明

## 本轮需要做什么

接入统一训练材料并保留原方法的诊断、检索、干预和修订机制。不要把不同方法都改成同一句“看图后重写Skill”。主结果标为“方法名＋JPG多模态适配”，列明新增阶段、改变的输入及仍保留的原流程。

方法整体可获得[九项输入](DIAGNOSER_INPUT_SPEC.md)。每阶段可按原机制使用子集，但须真实记录。仅在归档目录看见图片或调用了视觉能力模型，均不证明实际诊断请求含图。

## 接入步骤

数据集侧已完成ACP/LLM索引、消息去重、视觉资产关联、完整分窗、真实图像块请求组装和阶段文件保存工具。直接按[预处理读取入口](DIAGNOSIS_PREPROCESSING.md)使用`train/diagnosis/`，不要求同学重新处理巨型重复日志。下列步骤中，方法内部诊断/修订及模型调用仍由各方法负责人接入，尚无正式运行或送达收据。

1. 保留完整`train/`目录结构和配套`tools/`，从`train/diagnosis/index.json`开始；不要只复制`train/diagnosis/`，它仍引用外部训练原图、Task、Skill和运行产物。将训练材料及这些工具挂载到诊断工作区，把方法输出放在独立可写目录。不要挂载`evaluation_only/`或`_organizer/`。共享评测资料的同学也须遵守该隔离。
2. 用`train/batches/batch_XX/manifest.json`定位20张唯一原图和三遍源运行。读取原Task、原完整bundle及本方法当前草稿。
3. 读取本组已生成的`timeline.jsonl`与`windows/`；按`exact_llm_message_ids`补查精确参数，按消息`first_source`回溯原日志。完整窗口和续接范围已准备好，不得无记录地只留首尾。
4. 用`diagnosis_io.py packet`或库函数`load_window`取得文本和真正的`image_url`图像块。v2默认每窗附本组全部20张原图，并包含当前源run的安全API上下文；API交换、失败响应和结束原因也有窗口。无需依赖上一请求的看图记忆，但独立多次发送会产生重复视觉成本。可以等价接入原生看图工具/共享视觉上下文，须记录实际访问。`packet`是完整允许材料信封，各子阶段仍按原方法选择信息子集，不强迫所有Analyzer都读Skill。请求准备不等于已发送，正式调用由方法客户端执行并记录。
5. 保留原方法内部步骤；可用`diagnosis_io.py save-stage`保存实际产生的诊断、完整草稿、简短累计记录及逐窗口读取/跳过记录。第二组起自动读取前组状态。六组后冻结最终版本，中间不新增整套训练评测，不用两个测试集选版。
6. 保存实际诊断输入记录，并检查只修改现有5份`SKILL.md`、完整支持文件仍保留。工具不设token、调用次数或费用上限；本轮只准备材料，本地结构检查不启动正式模型调用。

## 诊断请求需要留什么证据

各方法每阶段保存一份`adapter_input_record.json`，原始请求内容另行脱敏留档。记录至少包括：

- 方法名、上游/适配版本、阶段号、batch ID、当前草稿版本与源Skill版本；
- 三个实际源run ID，以及各子阶段读取的轨迹类型和步骤/行号范围；
- 可用20张原图的asset ID，实际交给视觉请求/看图工具的asset ID；
- 原生子阶段名称、使用的信息子集、请求图像块数量或看图工具返回给模型的记录位置；
- 文本截断、未读取区段和失败输入，不得把缺图默认为0成本成功；
- 请求文件、返回收据和调用/成本记录的路径，不在记录里放API key、认证头或隐藏答案。

`adapter_input_record.example.json`是未执行的空模板，不是运行证据。使用`tools/check_adapter_record.py <record.json>`仅检查结构和输入范围；免费检查通过不等于模型已收到图。正式运行的请求/交付收据才支持后者。

## 已查到的旧适配情况

GitHub核查固定在`linyouxue/skill-repair-benchmark`提交`c214102dcdfa8c598ec7ba9206b46e4a5bca4a72`，避免把后来修改当成旧实验条件。

| 方法/版本 | 事实及需要核对的点 |
|---|---|
| MMG2Skill GPT JPG | 实际3次Analyzer、1次Refiner均为纯文本。SkillsBench转换仅抽取`content.text`；原框架有图像通路，不能说原方法不支持图片。Analyzer原生不读Skill，Skill对齐在Refiner；应保持此阶段划分。 |
| SkillAxe Opus JPG | 本地真实修复请求的system/user均为字符串，未附图片；compact_trace还截取首尾。旧适配把verifier stdout直接拼进prompt，新契约须改为允许反馈投影。GPT版没有足够实际请求证据，不能照推。 |
| CausalFlow已发布Opus适配 | 方法客户端接收文本prompt；JPG没有识别出causal steps。不能据此断定缺图就是失败原因。补图时保留干预与重放机制，并披露改动。 |
| SkillTTA GPT修复适配 | 原输入明确不读历史目标轨迹，使用Task、原bundle和BigCodeBench样例。加入JPG失败轨迹与图片是新增适配，必须如实命名，不能称完全未改的原版。 |
| SkillAxe GPT、SkillRevise、SkillGrad、SkillOpt、WML | 公开产物不能证明诊断模型是否收到图片，暂记未知。需要方法负责人提供真实诊断请求/源码或补上输入记录，不能依据after rollout推断。 |

证据入口：

- [MMG实际请求](https://github.com/linyouxue/skill-repair-benchmark/blob/c214102dcdfa8c598ec7ba9206b46e4a5bca4a72/evaluation/results/MMG2Skill-GPT52-Gold31-20260923/generation/jpg-ocr-stat/analysis_calls/call-001.request.json)
- [MMG转换代码](https://github.com/linyouxue/skill-repair-benchmark/blob/c214102dcdfa8c598ec7ba9206b46e4a5bca4a72/evaluation/results/MMG2Skill-GPT52-Gold31-20260923/method-source/experiments/skillsbench_cf25/run_diagnosis.py#L85-L135)
- [MMG Analyzer阶段边界](https://github.com/linyouxue/skill-repair-benchmark/blob/c214102dcdfa8c598ec7ba9206b46e4a5bca4a72/evaluation/results/MMG2Skill-GPT52-Gold31-20260923/method-source/anything2skill/reviser/analyzer.py#L9-L15)
- [CausalFlow客户端](https://github.com/linyouxue/skill-repair-benchmark/blob/c214102dcdfa8c598ec7ba9206b46e4a5bca4a72/evaluation/results/CausalFlow-Skill-Opus47-Gold15-20260922/source/llm_client.py#L98-L153)
- [SkillTTA输入来源](https://github.com/linyouxue/skill-repair-benchmark/blob/c214102dcdfa8c598ec7ba9206b46e4a5bca4a72/evaluation/results/SkillTTA-GPT52-Gold31-Local30-20260924/tasks/jpg-ocr-stat/method_output/provenance.json)
- [SkillGrad发布范围](https://github.com/linyouxue/skill-repair-benchmark/blob/c214102dcdfa8c598ec7ba9206b46e4a5bca4a72/evaluation/results/SkillGrad/main31_clean_20261004_finalized/README.md)

## 最终需交回的结果

完整最终bundle、每阶段原生诊断/修订产物、输入访问记录、必要的脱敏请求与交付收据、实际调用与费用账本。诊断内容以本方法实际产生为准，不在评测时根据最终diff补写。归档中没有正式运行的请求就明确标未运行，不补造。

最终评测须使用固定Task、模型/harness执行设置及原评分规则。两个测试集只在Skill冻结后进入评测端，结果不回流修复。已有baseline不重跑，主指标用固定分母字段正确率，其他指标和方法成本分别报告。

同学交回真实Excel后，可使用[evaluation/README.md](evaluation/README.md)的离线脚本分别评测train/test1/test2，得到逐批、逐遍及总体字段结果。该脚本复用原扩展字段口径，不执行原官方整批verifier，也不会由Excel推测方法调用费用。
