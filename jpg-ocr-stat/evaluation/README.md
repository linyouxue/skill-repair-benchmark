# 注意：泛化性测试暂时只在 group2 进行

**目前只运行 `group_02`（20张小票）；`group_01`、`group_03` 暂时不用跑。两组图片和已有结果保留，等待后续安排。**

# JPG评测

版本日期：2026-10-27。

图片、参考表和评分代码现已公开，仅供最终冻结Skill评测，不用于修复、诊断或选版。当前只评测group2，沿用[result提交与执行约定](../result/README.md)及[group2结果提交说明](results/methods/README.md)。

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

## 从哪些票据选择

200张中，156张至少一遍出现字段错误，104张至少两遍出错，63张三遍都出现错误。每票每遍2字段，共1200字段，405个错误中91个为空值。筛选区分非空错误、未填字段和整行缺失，不能只据空值断言图片识别困难。

排除原22张、与当前group2重复、来源身份映射不明确及业务正文含非英文的票据。先看重复错误和非空错误，再逐张查看整图及日期/金额原始像素；目检中继续剔除中文手写批注、非英文商品词和不合适的背景。确定40张后，按商户、旧划分和日期/金额错误数量均衡分组，未修改答案。

| 新组 | 张数 | 商户 | 至少两遍出错 | 三遍都出错 | 旧三遍错字段/120 | 旧三遍字段一致率 |
|---|---:|---:|---:|---:|---:|---:|
| group1 | 20 | 19 | 20 | 12 | 68/120 | 43.33% |
| group3 | 20 | 18 | 20 | 12 | 65/120 | 45.83% |

**表中成绩是这批成员在旧200张实验中的回看统计，不是新20张分组下的实验结果。** 上一图片版的3次baseline尝试因多图尺寸拒绝及共享网关停转发而中断，未形成有效评分；当前图片版已有baseline成绩见[results/README.md](results/README.md)。旧三遍所处批次、上下文和配置与新实验不同。

两个新组共27张来自旧训练划分、9张来自旧测试2、4张来自旧测试1；这些材料此前已经公开。它们适合检查同类日期/金额错误能否被修复，不能称为严格未见数据、盲测或不经过筛选的整体泛化估计。旧v1成员可从Git历史追溯，既有实验原始记录和成绩不改，旧成绩不重标为v2。

## 清晰度、语言与图片处理

按用户最新要求，取消v1固定短边800、长边1600像素门槛。以原22张中打印很淡的`074.jpg`（583×1303）作为可复核的低清晰度参照，目检要求日期、金额和业务文字在原始像素下可辨，较该参照更易阅读。清晰度没有公认的单一像素排序，这里不把图像尺寸、锐度分数或放大后的像素数当成清晰度证明。

新group1最终宽384–1332、高810–3000；新group3宽401–887、高813–2361。39张仍与原JPEG对应裁剪区域像素一致。`receipt_0088.png`保留整张已裁票据，以LANCZOS等比重采样至1332×3000后保存PNG；它不再声明为源像素逐字节一致。没有进一步裁掉票面内容，也没有放大、锐化、补字、翻译或生成文字，日期/金额参考值不变；缩小后已复查整图可读性。原大图和过去实验输入、轨迹、Excel及费用记录保留不改。

3000像素门槛依据本次AIGW-default实际HTTP400响应：含21个图片块的请求中，3307像素长边被上游多图校验拒绝。本次只做离线图片检查，没有付费试发，也不声明验证了任意未来API请求。执行器还需检查Agent临时生成的拼图、裁片及历史消息中的图像，不能只根据路径判断已适配。旧任务导出目录保持原样，后续需重新用下面的免费命令导出当前图片修订，不能重用旧图片副本。

业务和商品正文为英文，品牌、型号和商品专名保留。中文批注及`BATU`、`MEE MAMAK`、`BAWANG PUTIH`、`TEPUNG`等非英文业务/商品词所在候选已剔除，未通过删除这些文字来“变成英文”。

参考答案原样取自旧200张冻结表，日期为ISO字符串、金额为两位小数字符串；未按新模型输出改答案。本次没有全面重新人工标注，当前verifier仍衡量对冻结参考答案的精确一致率。

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
