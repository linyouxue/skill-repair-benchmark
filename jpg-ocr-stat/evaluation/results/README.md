# JPG现有实验结果


同学上传泛化评测结果请看[精简提交说明](methods/README.md)：每个方法配置一份README，加上group2各次运行的原Excel、完整轨迹和评分记录。最终Skill仍提交到[`jpg-ocr-stat/result/`](../../result/README.md)。

指标为日期和金额的字段正确率。原始Skill均使用Opus4.7，最多65次父迭代；同一集合的全部现有有效重复直接取算术均值。

| 数据集 | 每次票数 | 第1次 | 第2次 | 第3次 | 均值 |
|---|---:|---:|---:|---:|---:|
| 原任务 | 22 | 77.27% | 100.00% | 93.18% | **90.15%** |
| group_01 | 20 | 67.50% | 62.50% | 75.00% | **68.33%** |
| group_02 | 20 | 92.50% | 82.50% | 97.50% | **90.83%** |
| group_03 | 20 | 82.50% | 77.50% | 90.00% | **83.33%** |

group1、group3为当前新版图片，group2保持不变。group1、group3的前两次使用Tatu/AIGW，第3次使用Paratera，执行模型均为Opus4.7。旧版组1/3的结果保留在`historical-v1/`，不混入新版均值；对应图片和参考表可从[旧版数据](https://github.com/linyouxue/skill-repair-benchmark/tree/64e7ca807b19b8e3c19e96853a50f175e6dbdb19/jpg-ocr-stat/evaluation)追溯。

group1、group3的逐票错误模式和数量见[错误分析](groups13-error-analysis-20261027.md)，基于已有两次baseline，不重跑或更改成绩。

## 人工Skill现有结果

| Skill | 数据集 | 次数 | 第1次 | 第2次 | 第3次 | 均值 |
|---|---|---:|---:|---:|---:|---:|
| manual-round26 | group_01 | 3 | 75.00% | 92.50% | 95.00% | **87.50%** |
| manual-round26 | group_02 | 3 | 97.50% | 97.50% | 97.50% | **97.50%** |
| manual-round26 | group_03 | 3 | 90.00% | 87.50% | 87.50% | **88.33%** |

人工Round26共9次（group_01、group_02、group_03 各3次），均值为各数据集三次字段正确率的算术均值。group_02 第一次使用Tatu/AIGW、后两次使用Paratera；group_01/group_03 六次均使用Paratera（`paratera/Claude-Opus-4.7`，数据版本 `v2-current-images`，每次上限65次父迭代）。人工Round26不与原始Skill baseline混算。

## SkillHone现有结果

group_01 三次均值为65.00%，group_03 三次均值为80.00%。逐次成绩与group_02的原始材料见[SkillHone结果目录](methods/skilhone-opus4.7/README.md)。

## 文件

- `summary.json`：全部成绩和当前baseline均值。
- `runs.csv`：27次已有有效运行的逐次数据，含12次当前baseline、9次人工Skill、6次旧版结果。
- `baseline/`、`manual/`、`historical-v1/`：每次真实原Excel、原评分及已有验收记录；`run.json`对应运行身份。
- `manual/<run>/skills/`：group_02 三次人工Round26实际使用的完整冻结Skill及支持文件、许可；group_01/group_03 六次直接引用同一冻结Skill目录。
- `trajectory/`（各运行内）：24次本地运行的完整LLM记录（无损XZ）与已有ACP、ATIF或恢复会话原件；恢复前原段和接续段分别保留。
- `accounting.json`：已保存的用量与费用记录，估算与实际确认字段沿用原记录。

另3份远端旧LLM日志本次未补取，已在对应`run.json`中标记；27份原Excel和评分均齐全，不用另一条轨迹替代。

当前评测图片和参考表见[上级目录](../README.md)，原22票任务见[任务目录](../../README.md)。本次只整理已有数据，不重跑、不重新评分。
