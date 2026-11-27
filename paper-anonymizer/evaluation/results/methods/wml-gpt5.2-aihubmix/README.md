# WML 论文匿名化评测

使用 `gpt-5.2@AIHUBMIX-default` 和同一份冻结 Skill，在腾讯云通过 OpenHands 评测。四组泛化等权平均正确率为 **97.08%**。

| 数据组 | 采用的运行 | 得分 | 正确率 |
|---|---|---:|---:|
| train | [wml-paper-train-01](../../../../result/wml-gpt5.2-aihubmix/evidence/train/wml-paper-train-01/run.json) | 62/67 | 92.54% |
| group_01 | [wml-paper-group_01-03](group_01/wml-paper-group_01-03/run.json) | 129/134 | 96.27% |
| group_02 | [wml-paper-group_02-01](group_02/wml-paper-group_02-01/run.json) | 72/72 | 100.00% |
| group_03 | [wml-paper-group_03-02](group_03/wml-paper-group_03-02/run.json) | 139/144 | 96.53% |
| group_04 | [wml-paper-group_04-01](group_04/wml-paper-group_04-01/run.json) | 64/67 | 95.52% |

五组正式结果共 21 份 PDF，离线复算与原评分一致。Group 4 达到 60 次迭代上限时已完成最后一次匿名化脚本执行，采用当时提交的 PDF。

三次提前结束的运行保留原始评分和轨迹。两次各留有六份 PDF，一次没有提交。其评分排除于泛化均值。

[全部八次运行](runs.json) · [评分汇总](summary.json) · [冻结 Skill 与训练材料](../../../../result/wml-gpt5.2-aihubmix/README.md)
