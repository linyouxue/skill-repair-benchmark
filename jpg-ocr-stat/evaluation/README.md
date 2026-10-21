# JPG OCR 泛化评测：3组独立小票

这里提供 **3组各20张、共60张互不重复的SROIE小票**，用于评测最终冻结Skill对原22张任务之外票据的泛化。每张评分日期和金额两个字段，每组固定40字段，总计120字段。三组是不同小票集合，不是同一集合的三次重复。

图片、参考表和评分代码现在公开，**仅供最终评测，不得用于修复、诊断、选版或根据评测反馈继续调整Skill**。选样未使用方法预测或方法成绩。22张来自此前公开200张扩展集，38张从SROIE补充；完整成员和旧划分映射见 [manifest.json](manifest.json)。全部来源本来就是公开数据，因此不称为严格未见数据或盲测；使用过旧扩展集或已查看这些材料的方法应披露实际暴露情况。

```text
evaluation/
├── README.md                # 任务准备、Excel提交与结果解释
├── manifest.json            # 冻结成员、来源版本、裁剪坐标和目检记录
├── quality_check.json       # 实际尺寸、源像素/参考表一致性和隔离导出检查
├── prepare_task.py          # 免费导出一组隔离的原生任务
├── score_results.py         # 免费评测三份实际Excel，固定120字段分母
├── group_01/
│   ├── images/              # 第一组20张无损PNG小票
│   └── stat_oracle.xlsx     # 第一组冻结参考表，仅供评分侧
├── group_02/
│   ├── images/              # 第二组20张无损PNG小票
│   └── stat_oracle.xlsx     # 第二组冻结参考表，仅供评分侧
├── group_03/
│   ├── images/              # 第三组20张无损PNG小票
│   └── stat_oracle.xlsx     # 第三组冻结参考表，仅供评分侧
└── source/
    ├── README.md            # SROIE来源、许可、处理与引用
    ├── LICENSE              # 来源附带的CC-BY 4.0许可
    └── NOTICE               # 来源附带的署名和修改说明
```

## 图片筛选与分组

最终图片真实短边至少800像素、长边至少1600像素，逐张查看原始分辨率并复查裁剪结果。保留票据内容，不含桌面或其他物品；只对外缘空白、扫描背景或旁边的其他纸张做矩形裁剪。PNG像素与原JPEG解码后的对应裁剪区域逐字节相同；没有放大、透视插值、锐化、补字、翻译或生成式修改。原有手写标记、印章、折痕和打印特征保留。

**语言采用已确认的例外：商品和业务正文为英文；商户和地址允许保留非英文的拉丁字母原文，例如JALAN/JLN。品牌、型号和人名保留原文。** 排除了中文印章及非英文商品或业务词句，不把“拉丁字母”直接当成英文。整张票不应描述为严格全英文。

三组混合金额竞争、税费、实付与找零、舍入行、日期上下文、货号和计量单位等可见特征。同一商户不同票据可出现在不同组，故这里不属于按商户隔离的泛化测试。原22票及同票的重拍、旋转和裁剪变体不作为新样本。

| 组 | 小票 | 商户 | 来自旧200张 | 多金额行 | 舍入行 | 日期上下文/重复日期 | 货号和单位 | 手写标记 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| group_01 | 20 | 15 | 6 | 20 | 13 | 3 | 13 | 6 |
| group_02 | 20 | 15 | 8 | 20 | 13 | 3 | 13 | 6 |
| group_03 | 20 | 16 | 8 | 20 | 14 | 3 | 13 | 6 |

最终宽度范围为800–1259像素，长度范围为1600–2895像素；逐组尺寸及实际文件一致性检查见 [quality_check.json](quality_check.json)。

这些是可重叠的版式特征，**不是观察到的方法错误标签**。“略难于原任务”是选样目标，尚未运行方法实验来证明难度差异。本次不增加歧义分层，也不根据原题字面规则是否唯一决定答案来剔除票据。

参考答案以已有口径为基础：旧200张使用此前冻结的日期/金额；补充票使用SROIE的原实体标注，转换为ISO日期和两位小数金额字符串。经原票与原题规则核实的参考错误单独记录在 [manifest.json](manifest.json) 的 `reference_corrections` 中，不按新方法输出修改答案。参考答案并非本次全部重新人工重标，来源标注或任务规则之间可能仍有不一致；成绩应解释为对当前冻结参考表的精确一致率。

2026-10-21更正：`group_03/X51005719917.png` 的金额从 `60.60` 改为 `33.00`。原票的 `Sub-Total` 为60.60、优惠券折扣为27.60、`Grand Total` 为33.00；现金50.00减找零17.00也为33.00。依据原题优先取 `GRAND TOTAL` 的规则，更正此前误用折前小计的来源标注，日期及其他59张参考答案不变。本次未运行模型或重跑已有实验。

## 为最终Skill准备一组原生任务

先冻结一个方法配置对应的最终完整5-Skill bundle，三组都使用同一份版本。沿用 [result/README.md](../result/README.md) 的提交与执行约定；只允许现有5份`SKILL.md`正文变化，支持文件和许可保留。若使用过扩展集，不得隐去该暴露情况。

在已有`openpyxl==3.1.5`的Python环境，从仓库根目录运行：

```bash
python jpg-ocr-stat/evaluation/prepare_task.py \
  --group group_01 \
  --skills /path/to/frozen-final/skills \
  --output /path/to/new-tasks/jpg-eval-group-01
```

另外两组将`--group`换成`group_02`、`group_03`，输出到各自不存在的新目录。输出必须位于本任务目录和候选Skill目录之外；不传`--skills`时使用原5个Skill。

此命令只复制文件，不构建Docker、不调用模型。输出包含原`task.md`、原`environment/Dockerfile`、完整Skill和该组20张图；图片仍位于`environment/workspace/dataset/img/`。原字段评分器被复制到`verifier/`，只替换导出任务中的参考表，并写入固定20成员的`verifier/receipt_spec.json`。原任务及其22票参考表不被修改。

之后将导出目录交给现有SkillsBench/BenchFlow执行流程。**不要把整个`evaluation/`或参考表挂进Agent工作区。** 正常原生评分产生40项CTRF检查和连续reward，超时仍沿用原600秒；依赖/收集故障不当成普通0分。执行模型与实际父迭代配置按统一协议落实并留证；既有最终执行约定为65次父迭代，准备脚本本身不修改执行器，也不证明其已按65运行。

本次交付只验证离线准备和评分，没有运行这些泛化任务，未产生泛化方法成绩或真实预测Excel。

## 提交并离线评测实际Excel

每组执行均应实际生成并导出`/app/workspace/stat_ocr.xlsx`。保留原文件，不从参考表补造输出，不为缺文件缩减分母。唯一工作表为`results`，表头恰为`filename,date,total_amount`，文件名使用当前组PNG名、按文件名排序，日期为`YYYY-MM-DD`字符串，金额为两位小数字符串。每组20行，不合并成一份60行的输入表。

将三份真实Excel按下面路径保存，并按既有结果格式保留对应原始执行轨迹、模型/配置、终止原因和导出记录：

```text
my-predictions/
├── group_01/stat_ocr.xlsx    # 第一组实际原Excel
├── group_02/stat_ocr.xlsx    # 第二组实际原Excel
└── group_03/stat_ocr.xlsx    # 第三组实际原Excel
```

从仓库根目录免费评分：

```bash
python jpg-ocr-stat/evaluation/score_results.py \
  --predictions /path/to/my-predictions \
  --report /path/to/generalization-accuracy.json
```

报告分别给出三组的字段、日期、金额、整票正确率、交付状态及逐字段对错，再用全部60票汇总：

```text
每组 field_accuracy = (日期正确数 + 金额正确数) / 40
overall.field_accuracy = 三组正确字段总数 / 120
overall.date_accuracy = 三组正确日期总数 / 60
overall.amount_accuracy = 三组正确金额总数 / 60
overall.receipt_joint_accuracy = 日期和金额都正确的票数 / 60
```

缺整份Excel按该组40字段全错；缺行、空字段和错误值保留固定分母。精确字符串比较、格式问题单列及重复行后行覆盖等规则与 [原字段评分器](../README.md#评分口径) 一致，不另加模糊匹配或容错。JSON不回显参考答案或实际预测值。命令成功表示评分完成，不表示所有字段正确；参考表/冻结成员损坏则报错退出。

三组泛化成绩与原22票任务成绩、旧120/40/40扩展集成绩分别报告。多次运行要分别保存运行ID和原Excel，不能看到分数后挑选最好的一次冒充预先冻结的结果。

## 免费检查

```bash
python -m unittest discover -s jpg-ocr-stat/tests -v
```

需已有原固定测试依赖`pytest==8.4.1`、`pytest-json-ctrf==0.3.5`、`openpyxl==3.1.5`。新增回归只执行合成Excel，覆盖20票分母、120字段聚合、缺交付、冻结成员、隔离导出路径、仅修改SKILL.md及40项CTRF连续reward；原22票44字段回归同时保留。本次未调用付费模型，也未重跑或改写已有实验。
