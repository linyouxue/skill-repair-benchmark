
# JPG评测

版本日期：2026-10-27。

图片、参考表和评分代码现已公开，仅供最终冻结Skill评测，不用于修复、诊断或选版。当前需要评测group1，2，3沿用[result提交与执行约定](../result/README.md)及[group2结果提交说明](results/methods/README.md)。

现有baseline和人工Skill结果见 [results/README.md](results/README.md)：按数据集列出每次字段正确率和均值，同目录提供原Excel、原评分及运行记录。

```text
evaluation/
├── README.md             # 选择口径、导出和评测命令
├── manifest.json         # 60个成员、来源、原像素裁剪及旧错误统计
├── quality_check.json    # 图片/参考表/原verifier与导出检查
├── api_image_check.json  # group1/3全部40张的API图片尺寸与格式检查
├── selection_summary.json # 新两组旧错误次数、旧划分和尺寸汇总
├── prepare_task.py       # 免费导出单组20张隔离任务
├── score_results.py      # 免费评测真实Excel，三组固定120字段
├── results/              # 现有baseline、均值、原Excel、评分与轨迹
├── group_01/             # 新20张；images/及冻结stat_oracle.xlsx
├── group_02/             # 保留v1；图片和参考表不变
├── group_03/             # 新20张；images/及冻结stat_oracle.xlsx
└── source/               # 原SROIE许可、署名与来源说明
```



## 准备一组20张任务

在已有`openpyxl`的Python环境，从本包`jpg-ocr-stat`的父目录运行：

```bash
python jpg-ocr-stat/evaluation/prepare_task.py \
  --group group_02 \
  --skills /path/to/frozen-final/skills \
  --output /path/to/new-tasks/jpg-group02
```

本轮只准备group2。不传`--skills`时使用原5个Skill。准备命令只复制文件，不构建Docker、不启动Agent、不调用API。导出的Task、Dockerfile和verifier代码保持原样，只换入本组20张图片、冻结参考表和20成员spec；原600秒评分时间不变。参考表只放verifier侧，不挂到Agent工作区。

实际运行仍交给统一SkillsBench/BenchFlow执行器，冻结Skill后再跑；准备脚本不会自行保证65次父迭代，执行配置必须独立留证。本次文档更新没有调用模型或重跑实验。

## 评测真实Excel

实际运行须保存原`stat_ocr.xlsx`和完整执行轨迹。唯一工作表`results`，表头`filename,date,total_amount`，按本组PNG文件名排序20行。日期为`YYYY-MM-DD`字符串，金额为两位小数字符串。缺失产物如实记录，不拿参考表补造Agent输出。

```text
predictions/
└── group_02/stat_ocr.xlsx
```

```bash
python jpg-ocr-stat/verifier/score_accuracy.py \
  --actual /path/to/predictions/group_02/stat_ocr.xlsx \
  --oracle /path/to/new-tasks/jpg-group02/verifier/stat_oracle.xlsx \
  --spec /path/to/new-tasks/jpg-group02/verifier/receipt_spec.json \
  --report /path/to/group02-field-accuracy.json
```

上述命令使用同一verifier的评分实现，只评测group2，每次固定40字段；三个重复的均值为三次字段正确率的算术均值。缺表不缩分母，基础设施故障需另行说明。原`score_results.py`仍是三组汇总工具，本轮不要把未运行的group1/3计成零分后使用其120字段总分。免费检查中的参考表自比和缺表fixture均为软件检查，不是模型成绩或真实预测Excel。

## 免费回归检查

在已有固定测试依赖`pytest==8.4.1`、`pytest-json-ctrf==0.3.5`、`openpyxl==3.1.5`的环境运行：

```bash
python -m unittest discover -s jpg-ocr-stat/tests -p test_generalization.py -v
```

本次7项通过，覆盖成员和导出路径、仅修改SKILL.md的范围、固定分母、缺表及40项CTRF评分证据。检查不调用模型，也不重跑已有实验。
