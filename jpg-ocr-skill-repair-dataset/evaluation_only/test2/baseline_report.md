# 测试集2三遍结果与累计费用

2026-10-19补交后的当前选定版本。仅包含40张测试集2小票的三遍观测，固定分母120票/240字段，其他划分的结果和费用不混入。

第2遍第2批采用新attempt04，第3遍第1批采用新attempt03；其他四槽沿用原产物和得分。这是为补齐实际Excel交付而增加生成尝试后的选择，不是未经重跑的首次baseline，也不是Skill修复效果。原实验、被替换尝试和全部费用记录在组织者原记录中保留；发布目录仅保留当前版本。

| 重复 | 字段正确率 | 日期正确率 | 金额正确率 | 整票正确率 | 实际合并Excel |
|---|---:|---:|---:|---:|---|
| 第1遍 | 77.50%（62/80） | 90.00% | 65.00% | 60.00% | [40行原预测合并](baseline_merged/round_01_stat_ocr.xlsx) |
| 第2遍 | 61.25%（49/80） | 82.50% | 40.00% | 32.50% | [40行原预测合并](baseline_merged/round_02_stat_ocr.xlsx) |
| 第3遍 | 65.00%（52/80） | 80.00% | 50.00% | 40.00% | [40行原预测合并](baseline_merged/round_03_stat_ocr.xlsx) |

字段正确率三遍均值 **67.92%**，合计163/240；总体标准差6.95个百分点，仅描述三次波动，不是置信区间。

合计日期84.17%、金额51.67%、整票44.17%。原官方整批全对通过数为 **0/6**。

## 分层结果

| 分层 | 三遍票观测 | 字段正确率 | 金额正确率 |
|---|---:|---:|---:|
| 未发现提示冲突 | 42 | 83.33% | 69.05% |
| 提示冲突但付款唯一 | 12 | 54.17% | 25.00% |
| 原题字面规则歧义 | 66 | 60.61% | 45.45% |

## 实际原表与终止状态

选定6份真实20行原Excel，三份完整40行合并表。原表逐字节复制；合并仅拼接实际预测，保留日期和两位金额字符串，不用GT填值、不修改预测。

| 槽位 | 当前运行 | 原Excel |
|---|---|---|
| validation-r01-b01 | validation-r01-b01-a01 | [原文件](runs/validation-r01-b01/selected_run/artifacts/stat_ocr.xlsx) |
| validation-r01-b02 | validation-r01-b02-a01 | [原文件](runs/validation-r01-b02/selected_run/artifacts/stat_ocr.xlsx) |
| validation-r02-b01 | validation-r02-b01-a01 | [原文件](runs/validation-r02-b01/selected_run/artifacts/stat_ocr.xlsx) |
| validation-r02-b02 | validation-r02-b02-a04 | [原文件](runs/validation-r02-b02/selected_run/artifacts/stat_ocr.xlsx) |
| validation-r03-b01 | validation-r03-b01-a03 | [原文件](runs/validation-r03-b01/selected_run/artifacts/stat_ocr.xlsx) |
| validation-r03-b02 | validation-r03-b02-a01 | [原文件](runs/validation-r03-b02/selected_run/artifacts/stat_ocr.xlsx) |

四个指定替换槽均保留60轮耗尽的预算终止，真实原生评分为FAIL；不能表述为模型自然完成。每批5份官方Skill正文预载，显式工具式Skill调用为0，使用证据来自正文预载。

## 仅本划分的累计费用

- **累计确认provider费用：$72.90073975。**
- 未知费用预留估计另记$16.97135，不是确认扣款，不与上项相加。
- 累计费用包括本划分的全部历史失败、中断和补交尝试，每个原始账本仅计一次；不把网关事件数当付费成功调用数，也不用账号usage替代实验费用。
- 原测试2累计确认$44.9246375；第一轮两槽补交$12.855175；暂停后中断attempt03确认$4.5970375；最终attempt04确认$10.52388975。
- 未被选中的attempt03虽保存5343字节Excel并得到原生FAIL，但生成在休眠暂停后的空闲超时中断，不混入当前attempt04轨迹或结果。

## 复核与使用边界

本次发布验收只复用原生判决、读取真实Excel并聚合字段对错；0模型调用、0原生verifier重演。原Task、完整5Skill、源图、GT和评分器保持冻结。

当前选择、轨迹和实际产物以包根MANIFEST及trajectory_inventory为准。修复仅使用训练材料；测试1/2只用于最终冻结后的评测，不回流修订或选版。

[机器可读汇总](baseline_summary.json)。逐遍字段及分层汇总：[第一遍](round_01_metrics.json)、[第二遍](round_02_metrics.json)、[第三遍](round_03_metrics.json)。
