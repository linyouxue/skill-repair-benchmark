# JPG现有实验结果

同学上传泛化评测结果请看[精简提交说明](methods/README.md)：每个方法配置一份README，加上三组各次运行的原Excel、完整轨迹和评分记录。最终Skill仍提交到[`jpg-ocr-stat/result/`](../../result/README.md)。

指标为日期和金额的字段正确率。原始Skill均使用Opus4.7，最多65次父迭代；同一集合的全部现有有效重复直接取算术均值。

| 数据集 | 每次票数 | 第1次 | 第2次 | 第3次 | 均值 |
|---|---:|---:|---:|---:|---:|
| 原任务 | 22 | 77.27% | 100.00% | 93.18% | **90.15%** |
| group_01 | 20 | 67.50% | 62.50% | — | **65.00%** |
| group_02 | 20 | 92.50% | 82.50% | 97.50% | **90.83%** |
| group_03 | 20 | 82.50% | 77.50% | — | **80.00%** |

group1、group3为当前新版图片，group2保持不变。旧版组1/3的结果保留在`historical-v1/`，不混入新版均值；对应图片和参考表可从[旧版数据](https://github.com/linyouxue/skill-repair-benchmark/tree/64e7ca807b19b8e3c19e96853a50f175e6dbdb19/jpg-ocr-stat/evaluation)追溯。

## 人工Skill现有结果

| Skill | 数据集 | 次数 | 字段正确率 |
|---|---|---:|---:|
| manual-round28 | group_02 | 1 | 97.50% |
| manual-round26 | group_02 | 1 | 97.50% |

人工Skill各为一次探索结果，分别保留，不与原始Skill baseline混算。

## 文件

- `summary.json`：全部成绩和当前baseline均值。
- `runs.csv`：18次已有有效运行的逐次数据，含10次当前baseline、2次人工Skill、6次旧版结果。
- `baseline/`、`manual/`、`historical-v1/`：每次真实原Excel、原评分及已有验收记录；`run.json`对应运行身份。
- `manual/<run>/skills/`：人工Round26/28实际使用的完整冻结Skill及支持文件、许可。
- `trajectory/`（各运行内）：15次本地运行的完整LLM记录（无损XZ）与已有ACP、ATIF或恢复会话原件；恢复前原段和接续段分别保留。
- `accounting.json`：已保存的用量与费用记录，估算与实际确认字段沿用原记录。

另3份远端旧LLM日志本次未补取，已在对应`run.json`中标记；18份原Excel和评分均齐全，不用另一条轨迹替代。

当前评测图片和参考表见[上级目录](../README.md)，原22票任务见[任务目录](../../README.md)。本次只整理已有数据，不重跑、不重新评分。
