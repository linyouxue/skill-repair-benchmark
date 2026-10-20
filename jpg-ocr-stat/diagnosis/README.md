# 原始 JPG 任务的 Opus 诊断包

本包整理的是 [Opus47原始Skill的79任务结果](https://github.com/linyouxue/skill-repair-benchmark/tree/70f97e72aeee8c85f77e8304cbec579e486f7de2/evaluation/results/Opus47-OriginalSkill-79Tasks-20260920) 中最终选用的JPG运行：`jpg-ocr-stat-opus47-original-skill-r003-infra-recovery`。它对应原任务的22张小票和一条真实轨迹，可直接交给参评同学接入各自的诊断方法。

最终修复结果的上传要求见 [结果提交说明](../result/README.md)。最终提交仅需完整 `skills/`、简短 `README.md` 和 `evidence/`；证据可复用已有原格式日志或压缩归档，无需转换为新schema。

```text
diagnosis/
├── index.json                 # 权威运行、各证据流与全部窗口的入口
├── task_prompt.md             # 原运行实际收到的任务提示
├── images.json                # 原22图及历史视觉证据的可核查说明
├── validation.json            # 原交换、动作关联和无损分片的离线检查结果
├── records/                   # 动作、唯一消息、API上下文/交换、ATIF步骤
├── windows/                   # 连续无损分片，每个独立窗口附齐22图
└── outputs/                   # 原Excel、实际预测、允许反馈、执行信息和产物清单
```

原图和完整Skill支持文件复用任务内的 `../environment/`。完整原始日志留在上述来源目录，通过固定提交、真实文件名、行号和JSON指针追溯，不另造一份完整原日志副本。读取本包窗口不需要联网，也不会访问评分答案；重建包时需要完整仓库和原运行日志。

当前已生成37个窗口、380条派生记录：74条ACP、195条规范化唯一消息、1份API上下文、65次API交换和45个ATIF步骤。195条消息同时纳入了响应，包含只看请求历史时遗漏的最后一次响应。全部记录的窗口分片可逐字符重组；43条实际工具动作均有精确LLM和ATIF关联。

## 先怎样接入

在完整仓库根目录，用Python构造第一个窗口的输入：

```bash
python jpg-ocr-stat/tools/diagnosis_io.py packet \
  --window w0001 --out /tmp/jpg-window-0001.json
```

生成的JSON中，`messages` 是文本加 `image_url` 内容块：图像为实际图片字节生成的data URL，不能只把文件路径或Base64字符串作为普通文字交给模型。此入口只构造输入，**没有发送请求，也不证明模型已经收到或理解图片**。

方法代码可以直接导入读取器：

```python
import importlib.util
from pathlib import Path

task = Path("jpg-ocr-stat").resolve()
spec = importlib.util.spec_from_file_location("jpg_diagnosis_io", task / "tools/diagnosis_io.py")
io = importlib.util.module_from_spec(spec)
spec.loader.exec_module(io)

# 每种方法自行配置模型客户端并发送packet["messages"]。
# 此示例没有模型调用。
packet = io.load_window(task, "w0001")
```

全部窗口及顺序见 `index.json` 的 `windows`。逐个读取其 `window_id`，使用方法自身的诊断、检索和修订机制。每窗包含：

- 原实际Task、完整5份Skill正文、实际预测、允许的反馈与执行信息。
- 当前窗口的记录分片、来源和字符区间，以及前后窗和剩余范围。
- 精确调用、观察、响应、ATIF步骤和API上下文的关联记录。重复的请求历史默认保留有序消息ID，不在每个输入里再次展开；全部唯一消息已独立分窗，没有删掉历史内容。
- 22张原图的实际多模态内容块。图片文件只存一份，但独立请求会重新发送，产生的模型成本由方法实际请求记录。

需要定位一条完整记录时，可用 `io.load_record(task, record_id)`，或：

```bash
python jpg-ocr-stat/tools/diagnosis_io.py record \
  --id 'jpg-ocr-stat-opus47-original-skill-r003-infra-recovery:e0001' \
  --out /tmp/jpg-exchange-0001.json
```

实际记录ID以窗口和记录文件为准。需要检查原模型请求的完整历史时，在 `packet` 命令中增加 `--expand-request-history`，或调用 `io.load_window(task, window_id, expand_request_history=True)`。完整前缀会按引用展开，不做截断；默认不展开是避免重复发送，当前模式也写入输入材料。

读取器不会设置输出token、调用次数、费用或文本长度上限。分窗只划分源记录，**不是预算限制**；补齐关联记录、Task、Skill和图片后，实际输入可能大于窗口的字符数。适配方须依据所用模型上下文容量安排读取和请求，不能隐瞒跳过或只截首尾。

## 图片、动作和输出分别意味着什么

原日志包含65次模型交换、74条ACP事件，其中43条实际工具动作（27次终端、16次文件编辑）；另有22次`think`调用保留在LLM证据中。ACP动作、LLM交换、思考和ATIF步骤是不同视图，不能相加冒充额外执行步数，也不能把批量脚本拆成虚构的22条单票过程。

本条日志没有直接发给原Agent的多模态图像消息。原Agent通过脚本、PIL和Tesseract处理图片、读取OCR文字；这不等于没有处理图片。现在给Diagnoser附上22张原图，是明确新增的诊断材料，不能倒写成原Agent当时看过这些图像像素。未实际归档的裁剪图或脚本文件不予补造，相关调用与文字结果仍保留。

`outputs/stat_ocr.xlsx` 是原 `artifacts/pre-verifier-inputs.tar.gz` 中 `app/workspace/stat_ocr.xlsx` 的5367字节原件，含22行实际预测。它不是从模型最后的文字声明重建的表格。诊断时应按真实的修改、执行和保存顺序判断输出；最后一次脚本修改不自动意味着归档Excel已由该修改重新生成。

原运行达到65次迭代上限后结束，原native评分为FAIL、reward为0。原记录及两个早期基础设施失败尝试保留在来源目录；本包只选择最终r003，**不把三个尝试当作三次有效重复实验**。

## 正确率和允许反馈

`outputs/allowed_feedback.json` 是对原Excel调用本任务新字段评测器得到的**离线派生反馈**，不是原运行当时的reward。固定分母为22票、44字段，包含日期/金额逐字段对错、汇总及交付状态，不提供正确答案值或verifier断言。

实际预测放在 `outputs/predictions.json`，原评分与终止状态放在执行元数据中；二者与派生反馈分别保留。没有重新生成模型输出，没有重放原native verifier，也没有改写历史成绩。诊断读取器只允许访问诊断材料、原图和Skill目录，不加载 `oracle/` 或 `verifier/` 中的参考答案。

本原Excel的离线派生结果为：日期21/22、金额19/22，字段正确率40/44＝90.91%，整票正确率18/22＝81.82%，交付格式检查无问题。原native的0分表示原先的整表严格测试未通过，不能解释为所有字段都错了。

## 可选：使用 save-result 归档过程

`save-result` 是可选的过程归档工具，供方法保存诊断、草稿、历史和窗口覆盖。它生成的 `diagnosis.md`、`history.md`、`coverage.json`、`result.json` 不要求作为最终上传的独立文件；最终提交以 [结果提交说明](../result/README.md) 为准。

当前Skill草稿和累计历史可通过 `packet --draft-dir /path/to/current-skills --history /path/to/history.md` 带入。草稿目录直接包含5个Skill子目录；只有这5份现有 `SKILL.md` 正文允许修改，支持文件和许可应保留。

如需使用此工具，准备真实的诊断文档、完整候选Skill目录、累计历史，以及每窗的覆盖记录。覆盖记录格式如下；调用此工具时，文件须列出全部窗口且每窗一次：

```json
[
  {"window_id": "w0001", "status": "consumed", "request_or_tool_record": "method-logs/request-0001.json"},
  {"window_id": "w0002", "status": "skipped", "reason": "这里填写实际原因"}
]
```

```bash
python jpg-ocr-stat/tools/diagnosis_io.py save-result \
  --state-dir /tmp/my-jpg-method-result \
  --diagnosis /path/to/diagnosis.md \
  --candidate-dir /path/to/current-skills \
  --history /path/to/history.md \
  --coverage /path/to/coverage.json
```

工具输出保存到包外、候选Skill目录之外的新目录，包括诊断、草稿、历史、覆盖记录和收据；不会覆盖原包或既有方法结果。`consumed`由方法提供真实请求/工具记录引用，辅助脚本不把这个自报状态认证成模型理解证据。这里是一个任务的处理过程，没有强制六阶段或六轮修订。

## 离线重建与验证

消费已生成材料只需Python标准库。重建还需要原评分器使用的 `openpyxl==3.1.5`，并复用本仓库扩展数据集的无损规范化、引用及分片工具：

```bash
python jpg-ocr-stat/tools/prepare_diagnosis.py \
  --source-run evaluation/results/Opus47-OriginalSkill-79Tasks-20260920/runs/opus47-original-skill/jpg-ocr-stat-opus47-original-skill-r003-infra-recovery \
  --source-ref 70f97e72aeee8c85f77e8304cbec579e486f7de2 --refresh
```

来源可为本地未压缩日志，也可为完整checkout中的公开gzip日志。输出固定在本任务的 `diagnosis/`；上例带 `--refresh` 是因为已发布本包含生成结果，只刷新索引登记的本次派生文件，不改README或原始材料。`--window-chars`可调整无损分段大小，不是模型token预算。

已实际核验全部37个窗口可构造图文输入、每窗22图字节一致、全部65交换可从索引还原、末次响应可检索、原Excel字节一致；另有13项合成回归测试覆盖读取和结果保存边界。这些检查没有调用Diagnoser，也没有重放原native verifier。可免费复查：

```bash
python jpg-ocr-stat/tools/prepare_diagnosis.py --validate-only
python -m unittest discover -s jpg-ocr-stat/tests -p 'test_diagnosis_io.py' -v
```
