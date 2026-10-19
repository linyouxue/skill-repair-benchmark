# 训练集三遍结果与累计费用

2026-10-19补交后的当前选定版本。仅包含120张训练集小票的三遍观测，固定分母360票/720字段，其他划分的结果和费用不混入。

第1遍第1批、第3遍第1批各采用新attempt02；其他16槽沿用原产物和得分。这是为补齐实际Excel交付而增加生成尝试后的选择，不是未经重跑的首次baseline，也不是Skill修复效果。原实验、被替换尝试和全部费用记录在组织者原记录中保留；发布目录仅保留当前版本。

| 重复 | 字段正确率 | 日期正确率 | 金额正确率 | 整票正确率 | 实际合并Excel |
|---|---:|---:|---:|---:|---|
| 第1遍 | 71.67%（172/240） | 79.17% | 64.17% | 55.83% | [120行原预测合并](baseline_merged/round_01_stat_ocr.xlsx) |
| 第2遍 | 65.00%（156/240） | 80.83% | 49.17% | 42.50% | [120行原预测合并](baseline_merged/round_02_stat_ocr.xlsx) |
| 第3遍 | 65.83%（158/240） | 80.00% | 51.67% | 45.83% | [120行原预测合并](baseline_merged/round_03_stat_ocr.xlsx) |

字段正确率三遍均值 **67.50%**，合计486/720；总体标准差2.97个百分点，仅描述三次波动，不是置信区间。

合计日期80.00%、金额55.00%、整票48.06%。原官方整批全对通过数为 **0/18**。

## 分层结果

| 分层 | 三遍票观测 | 字段正确率 | 金额正确率 |
|---|---:|---:|---:|
| 未发现提示冲突 | 129 | 74.81% | 69.77% |
| 提示冲突但付款唯一 | 33 | 54.55% | 45.45% |
| 原题字面规则歧义 | 198 | 64.90% | 46.97% |

## 实际原表与终止状态

选定18份真实20行原Excel，三份完整120行合并表。原表逐字节复制；合并仅拼接实际预测，保留日期和两位金额字符串，不用GT填值、不修改预测。

| 槽位 | 当前运行 | 原Excel |
|---|---|---|
| train-r01-b01 | train-r01-b01-a02 | [原文件](runs/train-r01-b01/selected_run/artifacts/stat_ocr.xlsx) |
| train-r01-b02 | train-r01-b02-a01 | [原文件](runs/train-r01-b02/selected_run/artifacts/stat_ocr.xlsx) |
| train-r01-b03 | train-r01-b03-a02 | [原文件](runs/train-r01-b03/selected_run/artifacts/stat_ocr.xlsx) |
| train-r01-b04 | train-r01-b04-a01 | [原文件](runs/train-r01-b04/selected_run/artifacts/stat_ocr.xlsx) |
| train-r01-b05 | train-r01-b05-a12 | [原文件](runs/train-r01-b05/selected_run/artifacts/stat_ocr.xlsx) |
| train-r01-b06 | train-r01-b06-a01 | [原文件](runs/train-r01-b06/selected_run/artifacts/stat_ocr.xlsx) |
| train-r02-b01 | train-r02-b01-a02 | [原文件](runs/train-r02-b01/selected_run/artifacts/stat_ocr.xlsx) |
| train-r02-b02 | train-r02-b02-a01 | [原文件](runs/train-r02-b02/selected_run/artifacts/stat_ocr.xlsx) |
| train-r02-b03 | train-r02-b03-a02 | [原文件](runs/train-r02-b03/selected_run/artifacts/stat_ocr.xlsx) |
| train-r02-b04 | train-r02-b04-a03 | [原文件](runs/train-r02-b04/selected_run/artifacts/stat_ocr.xlsx) |
| train-r02-b05 | train-r02-b05-a02 | [原文件](runs/train-r02-b05/selected_run/artifacts/stat_ocr.xlsx) |
| train-r02-b06 | train-r02-b06-a02 | [原文件](runs/train-r02-b06/selected_run/artifacts/stat_ocr.xlsx) |
| train-r03-b01 | train-r03-b01-a02 | [原文件](runs/train-r03-b01/selected_run/artifacts/stat_ocr.xlsx) |
| train-r03-b02 | train-r03-b02-a01 | [原文件](runs/train-r03-b02/selected_run/artifacts/stat_ocr.xlsx) |
| train-r03-b03 | train-r03-b03-a04 | [原文件](runs/train-r03-b03/selected_run/artifacts/stat_ocr.xlsx) |
| train-r03-b04 | train-r03-b04-a02 | [原文件](runs/train-r03-b04/selected_run/artifacts/stat_ocr.xlsx) |
| train-r03-b05 | train-r03-b05-a01 | [原文件](runs/train-r03-b05/selected_run/artifacts/stat_ocr.xlsx) |
| train-r03-b06 | train-r03-b06-a01 | [原文件](runs/train-r03-b06/selected_run/artifacts/stat_ocr.xlsx) |

四个指定替换槽均保留60轮耗尽的预算终止，真实原生评分为FAIL；不能表述为模型自然完成。每批5份官方Skill正文预载，显式工具式Skill调用为0，使用证据来自正文预载。

第三遍第4、5批仍沿用原Excel及既有免费评分恢复证据：60轮已耗尽，宿主发布轨迹遇到errno28盘满，原verifier开始前失败；随后只免费补评，未重做模型。这两批有效FAIL未再次评分。

## 仅本划分的累计费用

- **累计确认provider费用：$171.47141450。**
- 未知费用预留估计另记$660.33034，不是确认扣款，不与上项相加。
- 累计费用包括本划分的全部历史失败、中断和补交尝试，每个原始账本仅计一次；不把网关事件数当付费成功调用数，也不用账号usage替代实验费用。
- 原训练累计确认$160.241402，本次两槽补交新增$11.23001250。

## 复核与使用边界

本次发布验收只复用原生判决、读取真实Excel并聚合字段对错；0模型调用、0原生verifier重演。原Task、完整5Skill、源图、GT和评分器保持冻结。

当前选择、轨迹和实际产物以包根MANIFEST及trajectory_inventory为准。修复仅使用训练材料；测试1/2只用于最终冻结后的评测，不回流修订或选版。

[机器可读汇总](baseline_summary.json)。逐遍字段及分层汇总：[第一遍](round_01_metrics.json)、[第二遍](round_02_metrics.json)、[第三遍](round_03_metrics.json)。
