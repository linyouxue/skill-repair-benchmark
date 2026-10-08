# 十题跨模型结果

**Gemini与OpenHands不适配。** 重复的错误工具调用和停滞在100/200轮运行中持续出现，增加轮数没有解决调用方式不适配的问题。

**适合标记 `cross_model_consistent` 的任务：PDDL、Python→Scala、Flink、Video。** 标记对应下表中的具体缺陷及模型组合。**四模型共同复现的是Python→Scala。** 其余六题不纳入共同缺陷集合。

|任务|判断|同机制模型组合|结论|
|---|---|---|---|
|pddl-airport-planning|适合|GPT、Claude、DeepSeek|计划文本序列化与落盘格式错误；Gemini自行恢复并PASS。GPT包含历史有效诊断轮。|
|python-scala-translation|适合|GPT、Claude、Gemini、DeepSeek|未识别项目/包契约，用独立编译和自测替代真实项目验收。Gemini在100轮候选运行中达到10/10 PASS。|
|flink-query|适合|D001：GPT、Claude、Gemini；D002：GPT、Gemini、DeepSeek|D001扩大FINISH完成条件；D002无SUBMIT/有效聚合仍输出0。D002的GPT证据来自修补Round1诊断，Gemini/DeepSeek来自原版。|
|video-silence-remover|适合|Claude、Gemini|能量候选审核不足导致误删；Gemini候选由8/9变为9/9 PASS。|
|reserves-at-risk-calc|不适合|—|Gemini停在下载/重算，DeepSeek覆盖了原遗漏实体；期限链没有形成共同原子失败机制。|
|seismic-phase-picking|不适合|—|各模型的时间取值与提交路径不同；DeepSeek原版2/2 PASS。|
|dynamic-object-aware-egomotion|不适合|—|Gemini额外尾帧采样与其他模型的运动问题不同；DeepSeek原版11/11 PASS。|
|shock-analysis-supply|不适合|—|Playwright MCP缺失、来源访问受阻，最终工作簿没有计算链。|
|enterprise-information-search|不适合|—|检索/交付与反馈聚合发生在不同失败阶段，没有共同原子缺陷。|
|azure-bgp-oscillation-route-leak|不适合|—|关键词覆盖、显式映射与评分契约问题不同。|

|运行系列|PASS / FAIL|结论|
|---|---|---|
|Gemini官方原版，10题|1 / 9|PDDL通过。|
|Gemini 60轮候选，9题|1 / 8|Video通过。|
|Gemini 100轮候选，6题|1 / 5|Scala通过。|
|Gemini后续100/200轮，5题|0 / 5|增加轮数没有新增PASS。|
|DeepSeek官方原版，10题|2 / 8|Seismic、Egomotion通过；Flink使用无答案访问r002，2/3 FAIL。|

[Gemini结果](gemini31/README.md) · [DeepSeek结果](deepseek-v4-pro/README.md) · [逐原子机制结论](deepseek-v4-pro/evidence/atomic-consistency-audit-20261008.json) · [Gemini工具调用与停滞记录](gemini31/budget-followup-20261007/HARNESS_ANALYSIS.md)
