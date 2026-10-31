# PDDL Airport现有实验结果

## 原始Skill baseline

模型为Tatu GPT-5.2，reasoning effort为xhigh，单请求输出上限16384。使用完整官方原Skill；每次最多60次父迭代，completion guard最多1次且共享此额度，无子Agent。数据版本pilot-v2，评分item-accuracy-v1；2026-10-30完成验收。

分数以百分比显示（100%=reward 1）。每次要求两份计划；reward为有效计划数/2，接受任何满足动作与目标约束的有效计划。每组3次独立有效运行直接取算术均值，正常FAIL/0分均计入；基础设施故障及恢复来源另列。

| 数据集 | 有效次数 | 第1次 | 第2次 | 第3次 | 均值 | 全对次数 |
|---|---:|---:|---:|---:|---:|---:|
| 原任务 | 3/3 | 100.00% | 100.00% | 0.00% | **66.67%** | 2/3 |
| group_01 | 3/3 | 0.00% | 0.00% | 0.00% | **0.00%** | 0/3 |
| group_02 | 3/3 | 0.00% | 100.00% | 100.00% | **66.67%** | 2/3 |
| group_03 | 3/3 | 0.00% | 50.00% | 0.00% | **16.67%** | 0/3 |

**合计12/12条有效，平均reward 37.50%，严格全对4/12。**全对次数要求单次reward=1；它与连续reward均值分别报告。

完整逐次结果、原Skill版本和证据见[baseline报告](baseline/README.md)、[汇总表](baseline/summary.csv)、[12次运行索引](baseline/STATUS.csv)及[原生证据下载](baseline/evidence-assets.json)。原始精度分数保存在CSV/JSON；本页百分比四舍五入至两位小数。本组使用同一冻结原Skill，没有根据泛化成绩修订或选择Skill。

## 提交真实泛化结果

先按[原任务result说明](../../result/README.md)冻结完整skill及真实修复/原题执行证据，再按协调者确定的组与重复次数运行。

在本目录提交`<method_id>__<config_id>/README.md`和`evidence/`。README指出原任务result中的同一冻结skill版本、实际模型/执行器/数据/评分版本、group、每次独立run ID及分数。evidence保留每次执行的完整ACP和LLM、原生配置/元数据、实际计划原文件、accuracy/CTRF/reward与用量；允许无损压缩或可访问归档引用。不要从摘要重建产物，不只挑最好一次；正常FAIL计入并保留，infra单列且不伪造分数。

不同协议/版本的分数分开呈现。不得用测试反馈继续改skill；若改了，作为另一个版本重新安排，不能继续称原冻结版。无需重复上传原输入、诊断包或skill全副本；通过固定仓库commit/相对路径关联。上传前移除凭据，提交面向main的PR，不直接覆盖他人结果。
