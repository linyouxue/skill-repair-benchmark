# 数据来源

题面、Java 骨架和原 Skill 来自 [SkillsBench 固定提交](https://github.com/benchflow-ai/skillsbench/tree/b63b7b2850226b6aa4fb5929a8c1ac7bc4d9a6af/tasks/flink-query)。日志源为 John Wilkes 与 Charles Reiss 发布的 [Google ClusterData2011_2](https://github.com/google/cluster-data/blob/master/ClusterData2011_2.md) 分片 00002–00025，数据和文档按 [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) 使用。原 Skill 附带许可随 bundle 保留。

四组按作业选择与原题对齐的正负例、事件行数和提交频次，并按测试组控制双阶段作业比例。基准规模组包含 67 个按真实事件模板构建的新作业，双倍组包含 134 个。部分作业使用了独立 ID、时间戳平移和 Job 表事件删减。[分组配额与错误对照](audit/summary.json)

阶段边界按 599、599.999999、600、600.000001 和 601 秒构造。前三级归为一阶段，后两级分成两阶段。另保留 12 个真实双阶段作业供离线核对。[真实样例](audit/natural_two_stage/)

每组参考值由 Python 和 SQLite 分别从实际日志复算。`*-lineage.json` 记录作业级变更，完整重建还需要组织者的构建脚本、上版输入和原分片。[导出与评分复核](audit/export-verification.json)
