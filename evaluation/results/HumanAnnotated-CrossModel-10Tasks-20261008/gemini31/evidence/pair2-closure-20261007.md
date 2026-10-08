# 第二批有效修复验证收束

两题首份有效模型修复尝试都是 round-1-r003；r001/r002为已隔离基础设施尝试，原始记录保留。10题官方原版仍1 PASS/9 FAIL，原版不重跑。

|任务|本轮有效结果|预算与请求|实际Skill调用|真实预评分产物|
|---|---|---|---|---|
|flink-query|FAIL，reward0，3/3测试失败|60 parent/60 provider，max_iterations|1，实际调用pdf；senior依赖正文预加载|4891字节tar，8个源码/配置文件|
|reserves-at-risk-calc|FAIL，reward0，1/5测试通过（formulas_present）|60 parent/61 provider，max_iterations|0，xlsx正文预加载|55224字节tar，57470字节真实工作簿|

两份validator各执行一次均exit0/healthy、无issues/warnings；独立健康审计为pair2-r003-health-20261007.json。完整轨迹/正文暴露/日志脱敏限制、provider重试、评分顺序和产物SHA以该审计为准。费用未知null。具体因果与原始文件索引为pair2-r003-causal-review-20261007.json；验收前不伪造原产物或放宽评分。

Flink初期PDF解析工具缺失与安装权限失败消耗步骤，但ACP27/28已成功读取公开PDF，不是必要资料全程不可达。ACP38初版只按任务活动session输出；最终源码没有消费job_input，没有完成资格检查，也没有候选要求的真实正反例测试。ACP43修改公开题面禁止修改的pom.xml来运行standalone jar，这是模型违反任务约束。ACP48已经见到Duration→Time编译错误，49修回并于50编译通过；61又改回Duration，最后源码仍不兼容，此后没有编译。预算结束后官方三个测试均未通过，不能拿中间编译通过代表最终交付。候选已明确输出资格与验证步骤而未执行；当前没有支持新增Skill修补的缺口，不机械追加提醒或重复Round2。

RaR ACP6/7从真实官方入口选择实际下载链接，并下载/解析Excel；16复制模板开始填价/公式，原版错误下载后重复读取的首错已避开。这是步骤改善，不是任务F→P或Skill唯一因果证明。后续双引号shell中的绝对单元格引用被展开，ACP58/61实际读到=C12**；63/64最后才通过quoted脚本修回。中间表格索引/实体选择、引号及工具命令边界错误消耗预算。真实最终工作簿1321个公式都没有缓存值，轨迹无recalc/soffice/data-only读回，模板已有Volume E15 #N/A未修；原xlsx Workflow5/6及214–283已经明确要求重算、修错与读回。本轮正常公式/结果断言失败，不能当verifier基础设施异常进行零模型补验。没有新确定Skill缺口，不盲目重复同候选或只追加提醒。

本批没有实际F→P，没有Gemini Gold或正式defect标注。Flink原版三模型结束事件语义扩大的共同证据仍作为候选保留；不能把本轮未采用job completion、编译回退、pom违规都混成同一跨模型机制。RaR原Gemini未进入计算，不能将新轮数学/lookup/引号错误回填为原版跨模型缺陷。model_sensitivity仅在defect层且按证据成立，不在task层预填。

完整原始尝试、失败候选和有限诊断保留；固定第二批在独立健康门收束后推进第三批seismic-phase-picking与dynamic-object-aware-egomotion。未来若有新的具体Skill缺口可以重新评估，本次没有无依据的额外付费模型调用或Judge。
