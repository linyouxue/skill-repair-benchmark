# DeepSeek V4 Pro 十题结果

**官方原版2 PASS / 8 FAIL。** Seismic为2/2 PASS，Egomotion为11/11 PASS。Flink采用无答案访问r002，构建和运行通过，输出语义失败，得2/3。

**DeepSeek复现4条原子机制，分布于3题：** PDDL计划序列化、Scala项目/包契约、Scala真实项目验收、Flink无SUBMIT/有效聚合仍输出0。Scala两条机制关联；Flink的GPT证据来自修补Round1诊断。

Shock缺少Playwright MCP，最终没有建立计算链，不纳入共同缺陷集合。Flink旧r001接触参考答案，其历史3/3保存在排除目录；当前十题使用r002结果。

[十题合并结论](../README.md) · [逐题结果](STATUS.csv) · [逐原子机制判断](evidence/atomic-consistency-audit-20261008.json) · [Flink结果](evidence/flink-noanswers-report-r002-20261008.md) · [完整轨迹与文件索引](MANIFEST.json)
