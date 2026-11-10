# SEC 机构持仓泛化评测

训练使用 2024 Q1、Q2 的完整 SEC Form 13F 数据。三组测试沿用同一套七问，按季度和查询对象划分。每组 10 个案例、100 个答案项。

```text
sec-financial-report/
├── task.md / environment/       # 训练题面、完整季度 ZIP 和两份 Skill
├── verifier/                   # 训练参考与逐项评分入口
├── result/README.md             # 冻结 Skill 和训练结果的交付要求
├── evaluation/
│   ├── group_01/               # 同对象换季度
│   ├── group_02/               # 同季度换对象，复用训练 ZIP
│   ├── group_03/               # 换对象和季度
│   └── prepare_task.py         # 隔离导出单组任务
└── tools/ / VALIDATION.json     # 参考答案重算与验证
```

## 同学先怎样接入

| 材料 | 位置 |
| --- | --- |
| 训练题面 | [task.md](task.md) |
| 训练输入 | [2024 Q1](environment/2024-q1.zip)、[2024 Q2](environment/2024-q2.zip) |
| 完整 Skill | [environment/skills/](environment/skills/) |
| 训练评分 | [verifier/](verifier/) |
| 冻结后的三组测试 | [evaluation/README.md](evaluation/README.md) |

根目录可以直接作为原生训练任务使用。继续用统一 `BenchmarkExecutor` 和现有方法 adapter，`tasks_root` 指向本目录的父目录，`task_id="sec-financial-report"`。新版训练诊断待运行。

## 数据与评分

Agent 从完整季度申报表里自行查找机构、筛选持仓和计算排名。训练组和 `group_02` 使用同两份输入 ZIP，只换查询的机构和证券。各组共享补齐逗号后的 25 个股票类别。 [股票类别表](evaluation/source/stock_classes.json) · [来源和批次清单](evaluation/manifest.json)

输出 `/root/answers.json`，顶层为 10 个案例。每个案例按七问给四个数值和三份有序的前二名单。金额按相对误差严格小于 0.1% 判对，计数精确匹配，排名按位置比较。缺项和错项记错，多余案例或排名项增加错误项。GT 仅在评分侧部署。

四组参考由 Python 和 SQLite 从六份完整 ZIP 独立计算，400 项一致。Docker 验证使用独立复算结果，四组各通过 100/100。 [验证记录](VALIDATION.json)
