# JPG小票Skill修复数据集

2026-10-18发布版本。包含200张冻结小票、既有官方Skill baseline及多模态adapter输入契约，用于研究可复用Skill的人工与自动修复差异；比较结论以实际执行结果为准。

## 目录结构

```text
jpg-ocr-skill-repair-dataset/
├── README.md                         # 数据集说明、获取与使用入口
├── ADAPTER_GUIDE.md                  # 各修复方法的多模态适配与交付要求
├── DIAGNOSER_INPUT_SPEC.md           # 诊断输入、权限边界与六阶段修复规则
├── SOURCE_PROVENANCE.md              # 数据和Skill的来源、引用及许可记录
├── train/                           # 仅供人工与模型修复使用的训练材料
│   ├── images/                      # 120张冻结训练原图
│   ├── batches/                     # 固定六组、每组20图及三遍运行映射
│   ├── runs/                        # 18次选定运行、允许反馈和真实产物
│   ├── archives/                    # 完整ACP、LLM及ATIF轨迹的无损归档
│   ├── skills/                      # 原始5个官方Skill及支持文件
│   ├── baseline_merged/             # 第二遍真实完整的120行合并Excel
│   ├── task_prompt.md               # 字节不变的原任务正文
│   ├── baseline_report_original.md  # 既有训练正确率、交付情况与费用报告
│   └── baseline_summary_original.json # 既有训练结果的机器可读汇总
├── evaluation_only/                 # 最终冻结后评测使用，禁止进入修复上下文
│   ├── test1/                       # 原测试集40图及既有三遍baseline
│   ├── test2/                       # 原验证集40图，现仅作最终评测
│   ├── runtime/                     # GT、原评分实现及配套免费评分工具
│   └── README.md                    # 评测材料的使用边界
├── tools/                           # 不调用模型的本地辅助检查
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
| `evaluation_only/test2/` | 40 | 原验证baseline，保留 | 最终冻结后评测，不再选版本 |

120/40/40成员不变。`split_aliases.json`保留test1→原test、test2→原validation的映射，未改动原实验目录。两个评测集曾有baseline及汇总成绩，不能宣称从未有人接触的盲测。

本版本公开整套材料，包括`evaluation_only/`中的图片、轨迹、GT和原评分实现。公开可访问不等于允许用于修复：修复模型与人工修复过程仅使用`train/`及方法自己的修订草稿。不要把整个数据集目录挂载到诊断容器；`evaluation_only/`仅在最终评测工作区使用。该目录划分是实验使用约定，不是访问控制；已接触测试细节的情况须如实披露。组织者的连接配置、本地来源定位和凭据不进入发布目录。

## 获取与免费查看

只获取本目录，可在有Git和Python 3的环境执行：

```bash
git clone --filter=blob:none --sparse https://github.com/linyouxue/skill-repair-benchmark.git
cd skill-repair-benchmark
git sparse-checkout set jpg-ocr-skill-repair-dataset
cd jpg-ocr-skill-repair-dataset
python -c "import json; from pathlib import Path; m=json.loads(Path('MANIFEST.json').read_text(encoding='utf-8')); print({s: {'images': x['unique_receipts'], 'runs': len(x['runs'])} for s,x in m['splits'].items()})"
```

清单输出应为训练120图/18次运行、测试1和测试2各40图/6次运行。此命令只读清单，不调用模型或verifier。首次合入`main`前，请先在本PR分支查看材料；正式使用时固定经审核的commit。完整轨迹解压后约32.7GiB，可按`archive_index.json`逐份读取，避免一次展开全部。

## 从哪里开始

1. 阅读[Diagnoser输入契约](DIAGNOSER_INPUT_SPEC.md)。
2. 按[adapter适配说明](ADAPTER_GUIDE.md)接入现有方法，保留原方法机制。
3. 查看`train/batches/batch_01/manifest.json`至`batch_06/manifest.json`。每组20张图、三次baseline执行记录，固定顺序处理六组。
4. 归档和真实文件以`MANIFEST.json`及`trajectory_inventory.json`为准，离线核查结果见`validation_report.json`。

主比较只允许修改原有5份`SKILL.md`；其他支持文件保留。每种方法独立从官方V0开始，六阶段后冻结最后版本。中间不新增整套训练评测，不使用测试集选版。需要新增Skill/helper或改变原机制的方法应单独披露适配变体。

## 运行记录和完整轨迹

沿用GitHub代表运行的`run_selection.json`、`selected_run/`、`trajectory/`风格；每个选定训练槽位单独归档，不按高分重新选尝试。历史传输/402/启动失败和被替换尝试不被当作额外的Skill失败训练样本。

- `selected_run/trajectory/acp_trajectory.jsonl`：完整ACP时间线的直接副本。
- `selected_run/trajectory/archive_index.json`：完整轨迹归档位置、成员名及大小。
- `archives/<run_id>.tar.xz`：无损保留ACP、完整LLM轨迹及存在的ATIF，不裁剪模型交换。解压可用`tar -xf <archive>.tar.xz`或Python标准库`tarfile`。
- `selected_run/artifacts/stat_ocr.xlsx`：仅在原来真实交付时存在。训练共有16份原Excel；两批正常未交付只标缺失，不补造。
- `allowed_feedback.json`：训练字段对错和汇总，不含正确答案值。
- `train/baseline_report_original.md`及`baseline_summary_original.json`：沿用既有训练汇总、正确率和费用，未重新计分；报告中的产物链接适配为包内路径，未随包交付的历史源文件仅保留文字说明。仅第二遍有真实完整的120行合并表，放在`train/baseline_merged/`，未生成其余两遍合并表。机器汇总中的历史绝对路径只表达来源，实际定位以`MANIFEST.json`为准。

这些原始LLM日志包含反复发送的历史上下文，不能把每行都当成独立新动作。先按ACP建立索引，再按需追溯LLM中的精确工具参数和视觉内容。完整档案可用不等于需要一次全部塞进模型。

## 重要解释

18个训练批次均有完整5份官方Skill正文预载证据，显式工具式Skill调用次数为0；不能把0直接解释成未暴露正文。两批评分恢复保留60轮耗尽和宿主发布轨迹时磁盘满的原终止信息：它们使用原Excel免费完成评分，不是自然生成完成，也不是重做模型。

主指标为日期与金额等权的字段正确率；每遍训练分母240字段，三遍720字段。缺交付保留分母。原官方整批reward另报，不能用整批FAIL替代字段正确率。

本次发布只整理既有材料、计算允许的训练对错标记和校验复制文件，没有模型调用、baseline重跑或原verifier重演。本数据集不授权启动付费实验；诊断模型、调用预算和正式运行安排仍需另定。

来源为已冻结的`jpg-ocr-skill-repair-200-v1`和已有官方Skill baseline。图片及第三方Skill的来源、许可声明与限制见[SOURCE_PROVENANCE.md](SOURCE_PROVENANCE.md)。其中`pdf`和`xlsx`是Anthropic的source-available材料，原许可限制再分发及衍生作品；本发布保留原许可，不宣称获得了额外授权，也不将它们重新许可为Apache-2.0。
