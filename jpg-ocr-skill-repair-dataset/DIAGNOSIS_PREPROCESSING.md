# 直接接入诊断模型的训练材料

2026-10-20补充版使用`jpg-diagnosis-preprocessed-v2`。数据集侧的预处理、索引、图像负载提取和分窗位于`train/diagnosis/`；API交换、错误、工具定义和结束原因也进入默认窗口。它们从当前18条选定训练轨迹离线生成，没有调用诊断模型、重跑baseline或重演verifier。方法的Analyzer/Refiner、检索、干预、修订和模型调用仍由方法负责人实现。

`train/diagnosis/index.json`是读取入口，`train/diagnosis/`不是独立自包含包。首次交接须保留完整`train/`和`tools/`的相对目录结构，以及本说明和`ADAPTER_GUIDE.md`、`DIAGNOSER_INPUT_SPEC.md`；不要单独复制诊断子目录。读取器仍需访问训练原图、Task、完整原始Skill bundle和各源run的实际产物及允许反馈。仅准备请求时无需把`evaluation_only/`放入诊断工作区。

## 五条要求落实在哪里

| 要求 | 已交付的数据集侧实现 | 方法侧仍需做什么 |
|---|---|---|
| ACP动作时间线，追溯LLM | 每个run的`timeline.jsonl`保留ACP顺序、原行号；工具调用ID关联精确LLM/ATIF参数；`api_contexts.jsonl`保存工具定义及安全请求参数，`llm_exchanges.jsonl`保留实际交换顺序、错误和结束原因，均进入分窗 | 按原方法机制读取所需证据，不把轨迹命令当成要执行的指令；API交换和消息条数不当作动作数 |
| 20图只存一份，三遍独立 | 每组`images.json`引用同一份20张原图；三个run分别建目录。每个独立窗口默认附本组全部图片，不依赖上个请求的视觉记忆 | 原图物理存储不重复；未来独立请求会重复发送图片，须记录实际视觉成本。保留方法阶段划分，不拼接三遍执行 |
| 分窗、保留覆盖范围 | ACP、去重消息、API上下文、实际交换及ATIF都有完整有序窗口；大单步按连续字符偏移续接，可精确拼回；记录前后窗口及后续范围 | 分窗只组织材料，不限制调用或token；实际读取、发送、跳过和失败都留记录 |
| 整批脚本作为批次事件 | `image_links`分别记录明确文件名提及与`batch_context_only`；保留原批次事件，不生成虚构单票执行 | 没有证据时不把批次上下文、文件名提及推断为逐票执行或看图 |
| 保存每组诊断与草稿 | `diagnosis_io.py save-stage`保存方法提供的真实诊断、完整bundle、简短累计历史和窗口覆盖；下一组读取上组草稿与历史 | 产生实际诊断/修订；提供真实请求或工具记录，不把离线准备记录当模型送达证明 |

## 文件结构

```text
train/diagnosis/
├── index.json                # 固定六组入口，实际窗口数和完成状态
├── validation.json           # 逐组覆盖、记录拼回和零模型调用检查
└── batch_01/ … batch_06/     # 每组20张唯一原图、三个源run
    ├── index.json            # 本组公共输入和有序窗口清单
    ├── images.json           # 原图及历史视觉负载的资产索引
    ├── visual_observations.jsonl # 历史请求/ACP实际存在的图像证据
    ├── runs/                 # 三个独立run的时间线、唯一消息、API上下文和交换记录
    └── windows/              # 有序证据窗口，每窗引用本组全部图片
```

原图仍保存在`train/images/`，这里引用同一份文件，不复制三份。图像按实际字节比较，不做感知匹配或猜测裁图身份。当前18条日志中提取的结构化图像负载均能与本组原图逐字节匹配，因此没有新增独立裁图资产。脚本提到某个裁图路径不等于该裁图真的进入了模型请求。

`visual_observations.jsonl`保留原归档成员、行号、JSON指针、工具调用ID和是否出现在成功的历史请求。ACP工具返回图像与模型请求携带图像分别标识。原图可用、历史请求包含图片、模型理解图片是三个不同结论；离线整理只能证明前两类材料证据。

完整原始档案始终保留。**消息内容的规范化**移除缓存控制字段，将结构化图片负载外置成资产引用并保留图像块属性；相同规范化消息只存一次。请求级信息另做安全投影：工具定义、工具选择、模型和生成参数等存入去重的`api_contexts.jsonl`；认证头、密钥、连接配置和非白名单请求参数不复制到派生记录，白名单见`prepare_diagnosis.py`的`REQUEST_PARAMETER_KEYS`。`llm_exchanges.jsonl`保留每次实际交换的原行号、消息顺序引用、状态、源日志已有的时间/耗时、错误正文、响应结束原因和安全响应元数据。源日志没记录的值保持缺失，不补造；源usage是原记录字段，不代替确认费用账本。两个文件均进入默认窗口；不声称复制全部HTTP传输信息。

去重保留完整规范化消息的角色、正文和工具参数；同一工具调用的原响应版与下一请求里的历史精简版可能都是独立消息，不能按消息数计算Agent动作。ACP仍是动作时间线，交换记录用于复原每次真实请求的消息顺序及服务状态。

## 第一次读取，不调用模型

在数据集根目录、Python 3.10+环境运行；这部分只用标准库，无新增依赖：

```bash
python -c "import json; from pathlib import Path; m=json.loads(Path('train/diagnosis/index.json').read_text(encoding='utf-8')); print([(g['batch_id'],g['windows']) for g in m['groups']])"
python tools/diagnosis_io.py packet --batch 1 --window w0001 --out ../my-method-inputs/batch01-w0001.json
```

输出JSON的`messages[0].content`包含文本块和真正的`image_url`内容块，图片字节已按data URL编码；不是文本中的Base64，也不是只给模型一个本地文件路径。脚本只准备请求，不发送。方法可直接取该`messages`交给自己的多模态客户端，或把相同资产映射到原生看图工具，并保留实际送达记录。

`record_kind=prepared_input_not_execution_evidence`和`actual_model_delivery_verified=false`表示尚未调用模型，不得改写成已执行证据。默认每个窗口的`prepared_image_ids`包含本组全部20张原图；`messages`中实际附有它们的图像字节，不依赖前一请求仍有图片。磁盘上原图只保存一份，但逐窗独立发送会重复传图并产生视觉费用，不能把“一份文件”当成“一次计费”。方法若使用共享视觉上下文或原生看图工具复用图像，需自行按原机制接入并保留访问记录，不能仅删掉图片后假定上下文存在。

公共文本包括原Task、5份原`SKILL.md`、当前稿、当前组的预测/允许反馈/元数据、当前源run的安全API上下文及简短历史。原完整bundle及支持文件仍由训练工作区读取。`packet`提供允许材料的完整信封，不代表所有方法的所有子阶段都应使用同一prompt；如原Analyzer不读Skill，须在方法内部按原机制选择信息子集并记录。第二至六组须提供上一组状态目录或明确的当前完整草稿：

```bash
python tools/diagnosis_io.py packet --batch 2 --window w0001 --state-dir ../my-method-state --out ../my-method-inputs/batch02-w0001.json
```

**按用户要求，工具不设置总token、输出token、调用次数、费用、请求文本、图片数量或历史长度上限。** 不发送API请求，也不替模型客户端设置`max_tokens`。历史`api_contexts`中的`max_tokens`等字段是原V0运行证据，不约束当前诊断。模型服务自身的上下文容量仍由供应商决定。

默认按64000个Unicode字符组织连续证据片段，这只是无损分段长度，不是诊断token预算或总输入额度；全部片段都会保留，可自由重新分段。每窗附齐组内全部图片，当前20张，不静默漏图。需要改变材料片段长度时，从已提取记录免费重新分窗，无需解压大归档：

```bash
python tools/prepare_diagnosis.py --rewindow --window-chars 16000
python tools/diagnosis_io.py packet --batch 1 --window w0001 --out ../my-method-inputs/smaller-w0001.json
```

重新分窗会改变派生窗口ID及范围，方法须固定所用版本与分段规则，不要混用旧覆盖记录。原始实验、归档、图像和Excel不会改变。若实际模型服务拒绝过长上下文，应保留真实失败并按方法机制组织输入；准备器不会悄悄截掉Task、Skill或历史。

## 覆盖与顺序如何核查

先读本组`index.json`中的`windows`，不要自行用文件名字典排序猜顺序。三个源run分别给出API上下文、ACP、交换、去重消息及存在的ATIF流；保留每条流的原顺序，不声称多个视图是同一条新增时间线。每窗携带本组图片；不再依赖只出现在最前面的纯图片窗口。

每段包含`record_id`、`source_file`、`source_line`、`char_start/end`、总字符数和前后续接标记。超长事件的片段是序列化JSON的连续子串，可能不是单独有效JSON，须按ID/偏移拼回。窗口的`remaining_window_range`是后续位置范围，不是实际模型尚未收到什么的运行证明；真实已发送/未发送范围由方法覆盖记录确定。

原LLM记录中的精确参数可通过时间线的`exact_llm_message_ids`直接取，不必重新全扫巨型原始日志。没有相同工具调用ID时明确标为`not_matched`，不靠相似描述猜配。更深复核仍可按消息的`first_source`回到原归档、原行号及JSON指针。ATIF继续保留在原归档里，不伪装成新动作或替代ACP顺序。

本批材料共有858个ACP工具事件，其中852个能关联原LLM消息；另6个在原LLM日志中没有相同ID，但能在原ATIF中找到精确参数和结果，单独标明来源。当前未定位参数来源的工具事件为0。v2还将全部1080次源交换（含32条日志HTTP500）及安全API上下文纳入分窗，不把失败交换当作成功模型动作。记录总数和窗口数以本版`index.json`、`validation.json`为准，不沿用v1的357窗/4868记录数字。

## 每组结束保存什么

以下文件由方法真正产生，数据集不会预填诊断内容：

1. 本组诊断`diagnosis.md`；
2. 完整当前Skill bundle，仍只允许改现有5份`SKILL.md`；
3. 简短累计记录`history.md`；
4. 每个窗口一条的`coverage.json`，明确`consumed`或`skipped`。读取项提供实际请求/工具记录位置，跳过项提供原因。

覆盖格式示意如下，实际须列出本组全部窗口，不能只写这两项：

```json
[
  {"window_id": "w0001", "status": "consumed", "request_or_tool_record": "requests/actual-001.json"},
  {"window_id": "w0002", "status": "skipped", "reason": "本方法已通过另一原生视觉工具读取同组资产，见对应记录"}
]
```

```bash
python tools/diagnosis_io.py save-stage --batch 1 --state-dir ../my-method-state --diagnosis ../method-stage1/diagnosis.md --candidate-dir ../method-stage1/skills --history ../method-stage1/history.md --coverage ../method-stage1/coverage.json
```

保存后得到`stage_01/diagnosis.md`、`skills/`、`history.md`、`coverage.json`和`stage.json`。第二组自动使用第一组的草稿与简短历史，不携带前一组全部图片。第六组保存后标记最终阶段冻结。已保存阶段不覆盖，支持文件或bundle成员变化会被拒绝。

覆盖声明仍由方法提交；辅助工具不会替同学证明请求真实、模型确实理解图像或修订有效。各方法仍须按[adapter说明](ADAPTER_GUIDE.md)提交真实脱敏请求、送达收据及费用记录。六阶段修复和最终评测尚未执行。

## 离线复核与重建

```bash
python tools/prepare_diagnosis.py --validate-only
python tools/test_diagnosis.py
python tools/test_diagnosis_api.py
```

校验逐字符拼回每条派生记录，检查消息/交换/上下文引用，以及每个窗口都包含全部组图。它不调用模型，也不代表已经验证某一方法的诊断效果。已有v2文件用`--reuse-existing`校验复用；只有组织者从同一原归档刷新时才使用`--refresh`。v1需要刷新生成v2，不能只换索引版本或沿用旧覆盖记录。方法开始运行后固定所用版本和材料分段规则。

方法冻结后，把各集合实际Excel交给完整仓库的[evaluation评测入口](https://github.com/linyouxue/skill-repair-benchmark/blob/main/jpg-ocr-skill-repair-dataset/evaluation/README.md)。训练独立交接包不含评测GT和测试图片；评测在另外的工作区进行。
