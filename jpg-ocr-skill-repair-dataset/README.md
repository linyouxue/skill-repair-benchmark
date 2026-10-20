# JPG小票Skill修复数据集

2026-10-20诊断包v2更新。包含200张冻结小票、原始官方Skill运行证据、诊断索引/多模态窗口及Excel离线评测入口。v2补齐API交换、失败响应、工具定义和结束原因，并为每个独立窗口附本组全部原图；完整说明见[预处理入口](DIAGNOSIS_PREPROCESSING.md)。训练两槽和测试2两槽按用户要求采用补交尝试，当前结果不是未重跑的首次baseline。各方法内部适配和正式诊断/修复尚未执行。

## 目录结构

```text
jpg-ocr-skill-repair-dataset/
├── README.md                         # 数据集说明、获取与使用入口
├── ADAPTER_GUIDE.md                  # 各修复方法的多模态适配与交付要求
├── DIAGNOSER_INPUT_SPEC.md           # 诊断输入、权限边界与六阶段修复规则
├── DIAGNOSIS_PREPROCESSING.md        # 已完成的预处理、分窗读取及阶段保存方法
├── TRAIN_HANDOFF.md                 # 只交付训练材料时的最短使用说明
├── SOURCE_PROVENANCE.md              # 数据和Skill的来源、引用及许可记录
├── train/                           # 仅供人工与模型修复使用的训练材料
│   ├── images/                      # 120张冻结训练原图
│   ├── batches/                     # 固定六组、每组20图及三遍运行映射
│   ├── runs/                        # 18次选定运行、允许反馈和真实产物
│   ├── archives/                    # 完整ACP、LLM及ATIF轨迹的无损归档
│   ├── diagnosis/                   # 六组已生成的动作索引、视觉证据与完整窗口
│   ├── skills/                      # 原始5个官方Skill及支持文件
│   ├── baseline_merged/             # 三遍各120行的真实预测合并Excel
│   ├── task_prompt.md               # 字节不变的原任务正文
│   ├── baseline_report.md           # 当前选定训练结果、补交说明与累计费用
│   └── baseline_summary.json        # 当前训练结果的机器可读汇总
├── evaluation_only/                 # 最终冻结后评测使用，禁止进入修复上下文
│   ├── test1/                       # 原测试集40图及既有三遍baseline
│   ├── test2/                       # 原验证集40图，现仅作最终评测
│   ├── runtime/                     # GT、原评分实现及配套免费评分工具
│   └── README.md                    # 评测材料的使用边界
├── evaluation/                      # 接收同学Excel，独立报告各集合准确率
│   ├── evaluate.py                  # 分批表/合并表的逐批、逐遍与总体评分入口
│   └── README.md                    # 提交目录、命令、固定分母与输出说明
├── tools/                           # 不调用模型的预处理与本地辅助检查
│   ├── prepare_diagnosis.py         # 从原轨迹生成索引、视觉资产及有序窗口
│   ├── diagnosis_io.py              # 组装真实图像内容块，保存方法自己的阶段产物
│   └── check_adapter_record.py      # 检查adapter输入记录的结构与范围
├── adapter_input_record.example.json # 未执行的adapter记录模板
├── MANIFEST.json                    # 数据划分、选定运行与产物路径总清单
├── protocol.json                    # 固定指标、可编辑范围与发布状态
├── split_aliases.json               # test1/test2与原split名称的映射
├── trajectory_inventory.json        # 30份轨迹归档的路径、成员与大小
├── validation_report.json           # 免费整理与发布副本检查结果
└── .gitattributes                   # 保持冻结文件字节，禁用换行转换
```

## 数据与使用边界

| 目录 | 独立票数 | 既有baseline | 用途 |
|---|---:|---|---|
| `train/` | 120 | 三遍、18个选定有效批次 | 诊断、修订Skill |
| `evaluation_only/test1/` | 40 | 原测试baseline，保留 | 最终冻结后评测 |
| `evaluation_only/test2/` | 40 | 原验证集三遍，两个槽位采用补交产物 | 最终冻结后评测，不再选版本 |

120/40/40成员不变。`split_aliases.json`保留test1→原test、test2→原validation的映射，未改动原实验目录。两个评测集曾有baseline及汇总成绩，不能宣称从未有人接触的盲测。

本版本公开整套材料，包括`evaluation_only/`中的图片、轨迹、GT和原评分实现。公开可访问不等于允许用于修复：修复模型与人工修复过程仅使用`train/`及方法自己的修订草稿。不要把整个数据集目录挂载到诊断容器；`evaluation_only/`仅在最终评测工作区使用。该目录划分是实验使用约定，不是访问控制；已接触测试细节的情况须如实披露。组织者的连接配置、本地来源定位和凭据不进入发布目录。

## 获取与免费查看

只获取本目录，可在有Git和Python 3的环境执行。以下示例读取main；若使用尚未合并的PR版本，先检出该PR头分支，避免混用旧版材料：

```bash
git clone --filter=blob:none --sparse https://github.com/linyouxue/skill-repair-benchmark.git
cd skill-repair-benchmark
git sparse-checkout set jpg-ocr-skill-repair-dataset
cd jpg-ocr-skill-repair-dataset
python -c "import json; from pathlib import Path; m=json.loads(Path('MANIFEST.json').read_text(encoding='utf-8')); print({s: {'images': x['unique_receipts'], 'runs': len(x['runs'])} for s,x in m['splits'].items()})"
```

清单输出应为训练120图/18次运行、测试1和测试2各40图/6次运行。此命令只读清单，不调用模型或verifier。正式使用时固定经审核的commit。完整轨迹较大，精确成员大小见`trajectory_inventory.json`，可按`archive_index.json`逐份读取，避免一次展开全部。

## 从哪里开始

交给同学时，请保留完整的`train/`目录结构、`tools/`及本目录的说明文档，并从`train/diagnosis/index.json`进入。**不要只拷贝`train/diagnosis/`**：窗口仍引用`train/images/`、原Task、完整Skill bundle和`train/runs/`中的真实预测、反馈及元数据。诊断工作区只挂载训练材料和这些工具，不挂载`evaluation_only/`。

1. 阅读[Diagnoser输入契约](DIAGNOSER_INPUT_SPEC.md)。
2. 按[已完成的预处理与读取说明](DIAGNOSIS_PREPROCESSING.md)，从`train/diagnosis/index.json`进入六组索引，直接读取已生成窗口，无需自己全扫重复API历史。
3. 按[adapter适配说明](ADAPTER_GUIDE.md)把窗口接入各方法原有诊断/修订机制。每组20张图、三个独立baseline运行，固定顺序处理六组；方法内部实现和正式模型调用由方法负责人完成。
4. 归档和真实文件以`MANIFEST.json`及`trajectory_inventory.json`为准，离线核查结果见`validation_report.json`。

主比较只允许修改原有5份`SKILL.md`；其他支持文件保留。每种方法独立从官方V0开始，六阶段后冻结最后版本。中间不新增整套训练评测，不使用测试集选版。需要新增Skill/helper或改变原机制的方法应单独披露适配变体。

### 免费准备第一份诊断输入

```bash
python tools/diagnosis_io.py packet --batch 1 --window w0001 --out ../my-method-inputs/batch01-w0001.json
python tools/prepare_diagnosis.py --validate-only
```

第一条命令生成含本组全部20张原图的真正`image_url`内容块，不发送模型请求；API交换、失败响应和安全参数也纳入默认证据窗口。原图磁盘只存一份，逐窗独立发送仍会重复计视觉成本。工具不设置总token、输出token、调用次数、费用、文本、图片数量或历史长度上限，不截断材料；分窗只整理证据，模型服务的上下文容量由供应商决定。用法见[预处理说明](DIAGNOSIS_PREPROCESSING.md)，独立交接方式见[TRAIN_HANDOFF.md](TRAIN_HANDOFF.md)。

### 用同学交回的Excel评测

```bash
python evaluation/evaluate.py --split test2 --predictions-dir ../my-results-test2 --method MyMethod --out ../scores/MyMethod-test2
```

每个集合分别运行；训练18份原表、测试1/2各六份，或各自三份完整合并表。提交目录与合并表命令见[evaluation/README.md](evaluation/README.md)。输出逐批CSV、逐字段对错、逐遍与分层JSON及Markdown汇总；缺交付保留固定分母，不混入其他集合或费用，不执行模型/原生verifier。复用既有openpyxl评测栈，没有新增依赖。

本次离线检查已核对30份原Excel和9份合并表，训练/测试1/测试2的逐遍字段正确数分别为172/156/158、55/53/38、62/49/52，与既有结果一致。预处理覆盖检查见`train/diagnosis/validation.json`，评测一致性检查见`evaluation/validation.json`。这些检查不代表人工或自动修复实验已经运行。

v2诊断包另已验收463个窗口、5966条派生记录、18份安全API上下文和1080次源交换（含32条失败响应）。每窗20张原图的9260个图像块均已核对，14项相关回归测试通过；工具不设模型用量限制。原始实验、轨迹归档、Skill、图片、Excel、评分与费用结果不变。

## 运行记录和完整轨迹

沿用GitHub代表运行的`run_selection.json`、`selected_run/`、`trajectory/`风格；每个槽位只公开当前选定运行，不按最高分选尝试。训练`train-r01-b01/a02`、`train-r03-b01/a02`，测试2`validation-r02-b02/a04`、`validation-r03-b01/a03`是用户为补齐真实Excel指定的新选择。历史失败及被替换尝试保留在原实验和累计费用账本中，不作为额外训练样本，也不在本发布目录保留旧版文件。

- `selected_run/trajectory/acp_trajectory.jsonl`：完整ACP时间线的直接副本。
- `selected_run/trajectory/archive_index.json`：完整轨迹归档位置、成员名及大小。
- `archives/<run_id>.tar.xz`：无损保留ACP、完整LLM轨迹及存在的ATIF，不裁剪模型交换。解压可用`tar -xf <archive>.tar.xz`或Python标准库`tarfile`。
- `selected_run/artifacts/stat_ocr.xlsx`：逐字节保存实际导出的原表。当前训练18份、测试1六份、测试2六份，共30份；没有从GT填值或从轨迹重构表格。
- `allowed_feedback.json`：训练字段对错和汇总，不含正确答案值。
- [训练结果](train/baseline_report.md)及[机器汇总](train/baseline_summary.json)：补交后当前18槽的结果。三份120行真合并表位于`train/baseline_merged/`。
- [测试2结果](evaluation_only/test2/baseline_report.md)及[机器汇总](evaluation_only/test2/baseline_summary.json)：补交后当前六槽的结果。三份40行真合并表位于`evaluation_only/test2/baseline_merged/`。测试1原轨迹、原表和原结果未修改。

这些原始LLM日志包含反复发送的历史上下文，不能把每行都当成独立新动作。先按ACP建立索引，再按需追溯LLM中的精确工具参数和视觉内容。完整档案可用不等于需要一次全部塞进模型。

## 重要解释

18个训练批次均有完整5份官方Skill正文预载证据，显式工具式Skill调用次数为0；不能把0直接解释成未暴露正文。两批评分恢复保留60轮耗尽和宿主发布轨迹时磁盘满的原终止信息：它们使用原Excel免费完成评分，不是自然生成完成，也不是重做模型。

主指标为日期与金额等权的字段正确率；每遍训练分母240字段，三遍720字段。缺交付保留分母。原官方整批reward另报，不能用整批FAIL替代字段正确率。

| 划分 | 三遍字段正确率 | 三遍均值 | 累计确认provider费用 |
|---|---|---:|---:|
| 训练，补交版 | 71.67% / 65.00% / 65.83% | 67.50%（486/720） | $171.47141450 |
| 测试1，原结果 | 68.75% / 66.25% / 47.50% | 60.83%（146/240） | $48.732565 |
| 测试2，补交版 | 77.50% / 61.25% / 65.00% | 67.92%（163/240） | $72.90073975 |

各集合分别计分、计费，累计费用包括各自全部历史失败、中断和补交尝试，未知费用估计单独报告，不当作实际扣款。四个替换槽都在60轮耗尽后交付真实Excel，原生评分为FAIL，不能说成自然生成完成或Skill修复效果。补交版增加了生成机会，不能当成未重跑首次baseline。

本次材料准备只复制归档、计算允许反馈及聚合现有预测，没有调用模型或重演原verifier。此前指定槽位的付费补交由独立用户授权执行。本包不设置调用预算，也不自动启动新的付费实验；正式运行由方法负责人执行并记录实际用量。

来源为已冻结的`jpg-ocr-skill-repair-200-v1`和已有官方Skill baseline。图片及第三方Skill的来源、许可声明与限制见[SOURCE_PROVENANCE.md](SOURCE_PROVENANCE.md)。其中`pdf`和`xlsx`是Anthropic的source-available材料，原许可限制再分发及衍生作品；本发布保留原许可，不宣称获得了额外授权，也不将它们重新许可为Apache-2.0。
