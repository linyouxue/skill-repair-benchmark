# SEC 机构持仓泛化评测

四组使用同一份七问题面。每组给 10 对申报机构和目标证券，每对输出 10 个计分项，共 100 项。季度和查询名称随组替换，输出均为 `/root/answers.json`。顶层键为 `case_001` 至 `case_010`，每个案例包含 `q1_answer` 至 `q7_answer`。

```text
sec-financial-report/
├── task.md / stock_classes.json  # 固定七问题型和 25 个股票类别
├── environment/skills/          # 两份 Skill 与类别表修正后的脚本
├── data/
│   ├── archives/                # 六份完整 SEC 源 ZIP，四组共用
│   ├── train/                    # 训练查询名单和训练 GT
│   ├── test_period/              # 同对象换季度
│   ├── test_entity/              # 同季度换对象
│   ├── test_both/                # 换对象和季度
│   └── manifest.json             # 季度、来源和申报覆盖记录
├── evaluation/prepare_task.py   # 导出一组原生任务
├── verifier/                    # 逐项正确率与原生评分入口
└── tools/ / VALIDATION.json     # 两套参考计算与验证结果
```

| 集合 | 基准期 → 当前期 | 查询对象 | 答案项 |
| --- | --- | --- | ---: |
| train | 2024 Q1 → Q2 | A 组 | 100 |
| test_period | 2024 Q3 → Q4 | A 组 | 100 |
| test_entity | 2024 Q1 → Q2 | B 组 | 100 |
| test_both | 2025 Q4 → 2026 Q1 | B 组 | 100 |

A 与 B 的机构 CIK、目标证券 CUSIP 和查询证券名称互斥。训练组和只换对象组使用字节一致的两份完整 SEC ZIP。四组均提供对应两季的全量申报包和完整持仓明细，由 Agent 自行查找并筛选所需记录。按季度和名称核对机构，按发行人名和证券类别从非期权记录定位目标 CUSIP，筛除前二排名内部及截止处并列的案例。

## 口径和原 Skill

[股票类别表](stock_classes.json)列出补齐逗号后的 25 个独立类别，两份 Skill 附带的相关脚本采用同一名单。两份原 `SKILL.md` 正文沿用。总市值以原始美元 `VALUE` 求和。股票行数和涨跌榜先筛类别，涨跌榜按 CUSIP 聚合后做当前减基准，缺失期视为零。持有人榜按目标 CUSIP 对当前期合格申报聚合。报送使用每个 CIK 在对应报告期内符合规则的初始 13F-HR；有多个时沿用旧构建器的最早申报日及编号顺序。

四组 GT 均从完整源 ZIP 按上述规则计算。训练诊断使用 `train` 上真实生成的输出和反馈，冻结 Skill 后再评测三个测试组。新版训练轨迹待运行。

## 通过统一执行器接入

进入本任务包目录后运行以下命令。

```bash
python evaluation/prepare_task.py --group train --output /tmp/sec-v2-train/tasks/sec-financial-report
python evaluation/prepare_task.py --group test_period --output /tmp/sec-v2-period/tasks/sec-financial-report
```

将 `tasks_root` 设为对应导出目录的父目录。继续使用现有方法 adapter 和 `BenchmarkExecutor.run(task_id="sec-financial-report", ...)`。导出从包内 `data/archives/` 读取两份完整季度 ZIP，也可用 `--archives-dir` 指定源目录。verifier 在 Agent 退出后部署，其 `expected_output.json` 只供评分。导出环境的两个兼容路径分别让证券搜索脚本和持有人排名脚本读取本组当前期。

每答对一个位置计一项。金额沿用相对误差严格小于 0.1% 的规则，计数精确匹配，排名按位置比较。缺项和错项记错，多余案例或排名项增加错误项。标准分母为 100，运行时间不参与正确率。

```bash
python verifier/score_accuracy.py --actual /path/to/answers.json --reference /tmp/sec-v2-period/tasks/sec-financial-report/verifier/expected_output.json --report /tmp/sec-v2-period-accuracy.json
```

## 数据来源与复核

[数据清单](data/manifest.json)记录六个完整源 ZIP 及各组使用的季度。参考计算按冻结查询名单从全量数据使用 Python 整数聚合。独立复核程序直接扫描同六份完整 ZIP，用 SQLite 查询逐项核对参考值、名称匹配、排名并列、持仓及持有人记录覆盖。四组 400 项一致，Docker 逐项评分均通过。 [验证记录](VALIDATION.json)

```bash
python -B tools/build_v2.py --output /tmp/sec-v2-reference-rebuild
python -B tools/verify_v2_sqlite.py
```
