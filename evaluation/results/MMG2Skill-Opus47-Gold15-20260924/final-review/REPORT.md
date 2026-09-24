# MMG2Skill · Claude Opus 4.7 · Gold15 最终报告

本批15题、32个Gold缺陷已完成真实执行验收、三个独立轨迹审计及新版v1.4评测。实际结果为 **2 PASS / 13 FAIL**，执行通过率 **13.33%**；当前有效run没有未完成验收或可恢复基础设施错误。已知任务工具与环境保真限制仍保留，不能解读成所有环境要求均满足。

模型为 anthropic/claude-opus-4.7，经OpenRouter；复用历史 original-skill 轨迹。MMG Analyzer分块15、一次Refiner、无教程、32768限制，仅更新已有SKILL.md并保留完整bundle；fresh通常60步，JPG实际65步。执行器为固定本地OpenHands。

裁判为 GPT-5.5 medium，共30个独立成功响应，全部原样保存；本次汇总仅离线复算，新增模型调用0。原语义评分与按用户规则得到的F→P替代评分分开保留。

|版本|维度|TP|FP|FN|Precision|Recall|F1|
|---|---|---:|---:|---:|---:|---:|---:|
|原语义Gold|诊断|5|24|27|17.24%|15.62%|16.39%|
|原语义Gold|修复|1|27|31|3.57%|3.12%|3.33%|
|F→P全缺陷TP|诊断|10|21|22|32.26%|31.25%|31.75%|
|F→P全缺陷TP|修复|5|24|27|17.24%|15.62%|16.39%|

F→P任务为 data-to-d3（1缺陷）和 seismic-phase-picking（4缺陷）：这5个Gold缺陷在替代版本中均设为诊断/修复TP，两题对应FP/FN清零。该规则并不证明5个缺陷均被内容修复，也不修改原裁判。定位命中数保持0，原始定位accuracy为0/5，替代版本为0/10，均为0%。

文件实际变化的bundle为15/15；裁判判定实质修改14个，其中6个发生内容回归，回归率6/14=42.86%，回归缺陷13个。Gold修复失败21个、有害额外改动6个、疑似新缺陷12个。这些独立判断在替代版本中保持原值。

113项裁判判断中25项置信度低于0.8（22.12%）；review队列37项，其中阻断项0。完整理由与疑似新缺陷见 gold-v1.4/details.json、review_queue.json；低置信度按冻结协议只提示，不追加裁判挑选结果。

全部15题有可复核的Skill正文预加载证据；n_skill_invocations总计1（Flink为1，其余为0）。不能将0次工具调用当作未暴露正文，也不能仅凭正文暴露或fresh PASS宣称修复有因果效果。部分日志对示例密码或Token字符串误脱敏，逐字差异和对应bundle证据保留在独立审计中。

|任务|Gold缺陷|实际执行|F→P|invoke_skill|
|---|---:|---|---|---:|
|azure-bgp-oscillation-route-leak|1|FAIL|否|0|
|data-to-d3|1|PASS|是|0|
|dynamic-object-aware-egomotion|3|FAIL|否|0|
|enterprise-information-search|1|FAIL|否|0|
|fix-build-agentops|2|FAIL|否|0|
|flink-query|2|FAIL|否|1|
|jpg-ocr-stat|1|FAIL|否|0|
|manufacturing-equipment-maintenance|2|FAIL|否|0|
|paper-anonymizer|3|FAIL|否|0|
|pddl-airport-planning|1|FAIL|否|0|
|python-scala-translation|3|FAIL|否|0|
|reserves-at-risk-calc|2|FAIL|否|0|
|seismic-phase-picking|4|PASS|是|0|
|shock-analysis-supply|3|FAIL|否|0|
|video-silence-remover|3|FAIL|否|0|

必须保留的协议与环境限制：

- AgentOps采用用户批准的py38–py312矩阵，测试断言及依赖pins不变；依赖预热在正式240秒验收计时前完成。五个环境均真实执行，失败来自timestamp断言。
- Shock题面要求Excel/Playwright/Solver，但固定基础工具harness不提供完整对应能力；实际使用Python/openpyxl/LibreOffice，数据来源/期间也存在限制。原verifier完整运行，FAIL来自量纲断言；不能把它解释为纯粹模型能力失败或环境完全合规。
- Flink缺pdftotext/pip/sudo等代理侧工具，正式Maven构建和作业运行正常，输出内容断言失败。
- PDDL题面示例和verifier格式存在既有歧义；实际计划输出格式断言未通过。
- Python→Scala历史输入使用已授权重建副本；新提交缺package tokenizer导致包/API测试失败，另有日志误脱敏限制。
- Reserves使用LibreOffice重算，不等同于已证明原生Excel操作流程合规。
- 原AgentOps/Flink模型前启动环境故障及各自r001证据保留；仅恢复fresh r002，没有重做成功方法或重试有效FAIL。

复算与证据入口：

- `report.json`：总表、逐题原始/替代指标及限制。
- `original-semantic-summary.json`、`gold-v1.4/`：30个原裁判响应的离线语义计分与真实执行率。
- `outcome-adjusted-summary.json`、`outcome-adjusted-details.json`：5个缺陷的明确TP覆盖记录，原judgment保留。
- `execution-audit-{a,b,c}.json`、`execution-audit-gate.json`：真实轨迹、原verifier、快照与正文证据。
- 上级 `gold-api-checkpoints/`、`gold-evaluation/`、`submission/`、`runs/`、`recovery-history/` 保留原始可追溯材料。

用户已授权发布本批现有结果，当前通过结果PR提交，等待人工review。GPT-5.2批次独立监控：30题本地有效完成，Druid仍因服务商地区访问限制未获有效验收，因此GPT31尚未完成或结算。
