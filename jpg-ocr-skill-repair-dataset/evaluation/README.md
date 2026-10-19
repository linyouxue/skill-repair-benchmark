# 用同学交回的Excel评测

该入口只读已有Excel，输出逐批、逐遍及分集合汇总。不启动Agent，不调用模型、pytest或原官方verifier，不更改原表，不自动重跑缺交付批次。沿用原评测栈的Python 3.10+和openpyxl 3.1.5，本次没有新增或安装依赖。先在数据集根目录检查现有环境：

```bash
python -c "import openpyxl; print(openpyxl.__version__)"
```

评测端需保留包内`evaluation_only/runtime/`和各集合的batch manifest。GT只由评测脚本读取，不能交给Diagnoser。两个测试集只在最终Skill冻结后评测，结果不回流修复或选版。

## 交回什么Excel

遵循原Task：唯一工作表`results`；表头严格为`filename,date,total_amount`；文件名排序；日期为`YYYY-MM-DD`字符串；金额为恰好两位小数的字符串；提取失败可为null。

默认一次评测一个集合的三遍输出，每批20张。以测试2为例：

```text
my-results-test2/
├── round_01/                 # 第一遍
│   ├── batch_01/stat_ocr.xlsx # 第1批20张
│   └── batch_02/stat_ocr.xlsx # 第2批20张
├── round_02/                 # 同样两批
└── round_03/                 # 同样两批
```

训练集每遍是`batch_01`至`batch_06`；测试1和测试2每遍是`batch_01`至`batch_02`。文件名成员以各集合`batches/batch_XX/manifest.json`为准。

## 运行评测

在数据集根目录执行，输出目录放在数据集以外：

```bash
python evaluation/evaluate.py --split test2 --predictions-dir ../my-results-test2 --method MyMethod --out ../scores/MyMethod-test2
python evaluation/evaluate.py --split test1 --predictions-dir ../my-results-test1 --method MyMethod --out ../scores/MyMethod-test1
python evaluation/evaluate.py --split train --predictions-dir ../my-results-train --method MyMethod --out ../scores/MyMethod-train
```

三次命令分别报告，不把120/40/40混成一个成绩。已有非空输出目录不会被覆盖。若只提供第一遍，另两遍仍按缺交付计分并标记未齐全，不能称为三遍完整实验。

若已经有三份完整合并表，可改为`--layout merged`。目录分别是`round_01/stat_ocr.xlsx`、`round_02/stat_ocr.xlsx`、`round_03/stat_ocr.xlsx`，训练各120行，测试各40行：

```bash
python evaluation/evaluate.py --split test2 --layout merged --predictions-dir ../my-merged-test2 --method MyMethod --out ../scores/MyMethod-test2-merged
```

合并模式同样生成逐批报告。两种模式是同一预测的不同读取方式，不能把结果再相加。

## 保留原来的文件位置

用`--inputs ../submission.json`替代`--predictions-dir`，文件路径相对于该JSON，也支持显式绝对路径。测试2分批模式模板：

```json
{
  "split": "test2",
  "layout": "batches",
  "rounds": [
    {"repeat": 1, "files": {"batch_01": "r1-b1.xlsx", "batch_02": "r1-b2.xlsx"}},
    {"repeat": 2, "files": {"batch_01": "r2-b1.xlsx", "batch_02": "r2-b2.xlsx"}},
    {"repeat": 3, "files": {"batch_01": "r3-b1.xlsx", "batch_02": "r3-b2.xlsx"}}
  ]
}
```

```bash
python evaluation/evaluate.py --split test2 --inputs ../submission.json --method MyMethod --out ../scores/MyMethod-test2
```

缺交付可以显式填`null`。三个repeat及全部batch键必须登记，避免漏登记。合并模式中每遍的`files`只含`{"merged": "对应合并表.xlsx"}`，CLI同时指定`--layout merged`。

## 输出和评分口径

| 文件 | 内容 |
|---|---|
| `report.md` | 三遍字段、日期、金额、整票正确率，均值/总体标准差及分层 |
| `summary.json` | 逐批、逐遍、总体、分层与交付问题的机器汇总 |
| `batch_metrics.csv` | 每批正确字段数、分母、各项正确率及格式问题 |
| `field_feedback.csv` | 每票日期/金额对错和预测是否存在，不含正确答案值 |

字段口径复用原`score_extended.py`的读取、格式检查与精确字符串比较，不添加纠错、容差或答案补全。日期、金额各一个字段，`filename`只是对应标识；两字段都对才算整票对。

- 训练每遍120票/240字段，三遍360票观测/720字段。
- 测试1和测试2各自每遍40票/80字段，三遍120票观测/240字段。
- 缺文件、缺行、null均保留固定分母，缺预测字段计错。
- 格式问题单独报告。沿用原扩展字段口径：能读取的预测按原值比较；错误表头、工作表或不可读文件可能无法读取预测，按空预测计分。重复文件名沿用原读取器的后行覆盖，同时标记交付无效。格式不合格不等于合格交付。
- 输出三遍均值、总体标准差与池化汇总。三遍分母相等时，均值等于池化字段正确率。
- 脚本不执行原官方整批verifier，不生成原官方reward或PASS率，不能拿字段正确率冒充它们。
- Excel不能说明方法费用，因此费用不从Excel估计，也不混入baseline费用；实际方法账本另报。

训练逐字段反馈可按既定边界进入修复；测试1/2反馈只留最终评测侧。合成边界测试使用`python evaluation/test_evaluate.py`。既有原Excel与合并表的离线一致性检查见`validation.json`；没有重跑模型或原生verifier。
