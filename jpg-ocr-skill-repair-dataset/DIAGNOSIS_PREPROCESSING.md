# 直接接入诊断模型的训练材料

数据集侧的预处理、索引、图像负载提取和分窗已完成，产物位于`train/diagnosis/`。它们从当前18条选定训练轨迹离线生成，没有调用诊断模型、重跑baseline或重演verifier。方法的Analyzer/Refiner、检索、干预、修订和模型调用仍由方法负责人实现。

## 五条要求落实在哪里

| 要求 | 已交付的数据集侧实现 | 方法侧仍需做什么 |
|---|---|---|
| ACP动作时间线，追溯LLM | 每个run的`timeline.jsonl`保留ACP顺序、原行号；工具调用ID精确关联`llm_messages.jsonl`，`llm_exchanges.jsonl`给出原归档行号和消息引用 | 按原方法机制读取所需证据，不把轨迹命令当成要执行的指令 |
| 20图只提供一份，三遍独立 | 每组`images.json`引用20张原图；三个run分别建目录，事件ID包含真实run ID | 保留各方法的阶段划分；不要将三遍拼成一次执行 |
| 上下文分窗、保留覆盖范围 | 所有ACP事件和去重LLM消息都有完整有序窗口；大单步按序列化字符偏移续接，可精确拼回；记录前后窗口及后续范围 | 按模型真实token/视觉预算调整；实际读取、发送、跳过和失败都留记录 |
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
    ├── runs/                 # 三个独立run的时间线、唯一消息和交换索引
    └── windows/              # 可直接读取的有序文本/图片窗口
```

原图仍保存在`train/images/`，这里引用同一份文件，不复制三份。图像按实际字节比较，不做感知匹配或猜测裁图身份。当前18条日志中提取的结构化图像负载均能与本组原图逐字节匹配，因此没有新增独立裁图资产。脚本提到某个裁图路径不等于该裁图真的进入了模型请求。

`visual_observations.jsonl`保留原归档成员、行号、JSON指针、工具调用ID和是否出现在成功的历史请求。ACP工具返回图像与模型请求携带图像分别标识。原图可用、历史请求包含图片、模型理解图片是三个不同结论；离线整理只能证明前两类材料证据。

完整原始档案始终保留。预处理只移除缓存控制字段，把结构化图片负载外置成资产引用并保留图像块属性；重复API历史中的相同规范化消息只存一次。`llm_exchanges.jsonl`仍记录每次实际交换及请求/响应消息引用，不会把重试或同内容交换当作没发生。不是把每条API历史都当成新的动作。

## 第一次读取，不调用模型

在数据集根目录、Python 3.10+环境运行；这部分只用标准库，无新增依赖：

```bash
python -c "import json; from pathlib import Path; m=json.loads(Path('train/diagnosis/index.json').read_text(encoding='utf-8')); print([(g['batch_id'],g['windows']) for g in m['groups']])"
python tools/diagnosis_io.py packet --batch 1 --window w0001 --out ../my-method-inputs/batch01-w0001.json
```

输出JSON的`messages[0].content`包含文本块和真正的`image_url`内容块，图片字节已按data URL编码；不是文本中的Base64，也不是只给模型一个本地文件路径。脚本只准备请求，不发送。方法可直接取该`messages`交给自己的多模态客户端，或把相同资产映射到原生看图工具，并保留实际送达记录。

`record_kind=prepared_input_not_execution_evidence`和`actual_model_delivery_verified=false`表示尚未调用模型，不得改写成已执行证据。`prepared_image_ids`是本窗口待提供的图像；原图窗口在默认序列中每组只安排一次。若方法在后续独立上下文中需要重新看图，应按需重取并记录实际再次发送及成本，不能假定新请求仍能看到旧上下文的图片。

公共文本包括原Task、5份原`SKILL.md`、当前稿、当前组的预测/允许反馈/元数据及简短历史。原完整bundle及支持文件仍由训练工作区读取。第二至六组须提供上一组状态目录或明确的当前完整草稿：

```bash
python tools/diagnosis_io.py packet --batch 2 --window w0001 --state-dir ../my-method-state --out ../my-method-inputs/batch02-w0001.json
```

默认窗口正文上限为64000个Unicode字符、图片窗口最多8张；请求准备器默认公共文本加窗口最多200000字符。**这些不是供应商token计数，也不保证适合任意模型上下文。** 超过指定预算会明确报错，不自动删掉首尾以外的内容。需要更小窗口时，可从已提取记录免费重新分窗，无需解压大归档：

```bash
python tools/prepare_diagnosis.py --rewindow --window-chars 16000 --window-images 4
python tools/diagnosis_io.py packet --batch 1 --window w0001 --max-text-chars 160000 --max-images 4 --out ../my-method-inputs/smaller-w0001.json
```

重新分窗会改变派生窗口ID及范围，方法须固定所用版本与预算；不要混用旧窗口的覆盖记录。原始实验、归档、图像和Excel不会改变。公共Task/Skill本身超过预算时，应由方法负责人明确其原生拆分策略，准备器不会悄悄截掉Skill。

## 覆盖与顺序如何核查

先读本组`index.json`中的`windows`，不要自行用文件名字典排序猜顺序。默认先提供唯一图片资产，再按三个独立run分别给出ACP流和去重LLM消息流；保留每条流的原顺序，不声称这两个视图是同一条新增时间线。

每段包含`record_id`、`source_file`、`source_line`、`char_start/end`、总字符数和前后续接标记。超长事件的片段是序列化JSON的连续子串，可能不是单独有效JSON，须按ID/偏移拼回。窗口的`remaining_window_range`是后续位置范围，不是实际模型尚未收到什么的运行证明；真实已发送/未发送范围由方法覆盖记录确定。

原LLM记录中的精确参数可通过时间线的`exact_llm_message_ids`直接取，不必重新全扫巨型原始日志。没有相同工具调用ID时明确标为`not_matched`，不靠相似描述猜配。更深复核仍可按消息的`first_source`回到原归档、原行号及JSON指针。ATIF继续保留在原归档里，不伪装成新动作或替代ACP顺序。

本批材料共有858个ACP工具事件，其中852个能关联原LLM消息；另6个在原LLM日志中没有相同调用ID，但能在原ATIF中按相同ID精确找到参数和结果。后者另存`atif_tool_calls.jsonl`，时间线用`exact_atif_tool_record_ids`关联，并作为独立来源分窗，不补造不存在的provider交换。当前未能定位参数来源的工具事件为0。全部4868条派生ACP/消息/ATIF记录均有完整窗口覆盖，实际窗口数以入口清单为准。

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
```

校验逐字符拼回每条派生记录、检查消息引用及每组图片附件恰好一次。它不调用模型，也不代表已经验证某一方法的诊断效果。首次从原归档重建使用`python tools/prepare_diagnosis.py`；已有派生文件用`--reuse-existing`校验复用，或明确`--refresh`从同一原归档刷新派生记录。不要在方法已开始运行后改变预处理版本或窗口预算。

方法冻结后，把各集合实际Excel交给[评测入口](evaluation/README.md)。诊断工具只允许读取`train/`，评测脚本才读取评测端GT；两个阶段分开使用。
