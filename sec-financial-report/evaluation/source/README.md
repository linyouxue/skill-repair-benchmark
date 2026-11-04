# 来源、原始材料与重新构建

原题固定SkillsBench `b63b7b2850226b6aa4fb5929a8c1ac7bc4d9a6af` 的 `tasks/sec-financial-report/`。原task、Skill/脚本、Dockerfile、oracle和GT保持原字节，原二元评分文件保留在original_verifier。上游为Apache-2.0，版权及许可沿用上游仓库；本包修改的是评分入口、打包工具和说明，未修改原GT或原Skill。数据来源和原文件Git blob逐项见[SOURCES.json](SOURCES.json)，许可全文沿用仓库根LICENSE。

| 用途 | 报告期 | 包内位置 |
|---|---|---|
| 原题训练 | 2025-Q2/Q3 | environment中的两份完整ZIP，已随包提交 |
| group_01来源 | 2024-Q1/Q2 | 六份全量ZIP按需下载；冻结行已在group_01/inputs |
| group_02来源 | 2024-Q3/Q4 | 同上，冻结行在group_02/inputs |
| group_03来源 | 2025-Q4/2026-Q1 | 同上，冻结行在group_03/inputs |

六份全量源ZIP来自[SEC Form 13F data sets](https://www.sec.gov/data-research/sec-markets-data/form-13f-data-sets)，SOURCES.json记录实际URL、大小和SHA256。ZIP发布窗口不同于持仓报告季度，使用COVERPAGE和SUBMISSION中的报告日期选取。原数据是申报者提交的记录，不能把q1等同于经理所有经济资产；第三批case_009中SUMMARYPAGE与明细求和不一致，按公开的原helper明细求和口径计分。

同学直接使用已冻结任务时无需以下重新构建步骤。组织者需要复核策展时，在固定SkillsBench checkout旁从本仓库根执行：

```bash
python sec-financial-report/tools/acquire_sources.py --skillsbench /path/to/skillsbench
python sec-financial-report/tools/build_dataset.py
python sec-financial-report/tools/verify_references_sqlite.py
```

acquire_sources只恢复未修改的固定原材料并取得八份ZIP，遇到被编辑的原材料会拒绝覆盖。全量held-out ZIP保存在本地 `evaluation/source/archives/`，被本包.gitignore排除，不是同学执行所需的额外下载。构建与参考计算不调用模型。

诊断来源固定benchmark `bee9b0df5b04a300735e5009f5238f5d5c8aaf61` 中的指定GPT-5.2运行，原生轨迹保留原字节。原评分故障与后续恢复输出的有效重放分开记录，见[diagnosis说明](../../diagnosis/README.md)。参考计算、源数据和历史原生材料各自保留原来源，不因放在本仓库而替换其适用条款。
