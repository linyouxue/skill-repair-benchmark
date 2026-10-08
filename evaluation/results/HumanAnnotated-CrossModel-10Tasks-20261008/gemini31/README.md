# Gemini 3.1 Pro 十题结果

**Gemini与OpenHands不适配。** 多命令调用被终端拒绝后反复出现，重复动作与停滞继续消耗轮数；100/200轮运行没有解决这一调用模式。

|系列|PASS / FAIL|通过任务|
|---|---|---|
|10题官方原版，60轮|1 / 9|PDDL|
|9题候选，60轮|1 / 8|Video|
|6题候选，100轮|1 / 5|Scala，10/10|
|5题后续候选，100/200轮|0 / 5|—|

Video形成1题1缺陷的独立Gold。Scala在100轮候选中已通过项目测试，尾部停止原因为stuck。

跨模型共同机制：Scala项目契约；Flink完成条件与输出资格；Video候选误删。对应模型组合和十题筛选见[合并结论](../README.md)。

[逐题结果](STATUS.csv) · [100轮结果](budget100-20261007/README.md) · [100/200轮结果](budget-followup-20261007/README.md) · [工具调用记录](budget-followup-20261007/HARNESS_ANALYSIS.md) · [Gold](gold.json) · [完整轨迹与文件索引](MANIFEST.json)
