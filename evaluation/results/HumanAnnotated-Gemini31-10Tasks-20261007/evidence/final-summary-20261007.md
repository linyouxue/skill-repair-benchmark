# Gemini十题验证最终汇总

官方原版10/10有效结束：1 PASS、9 FAIL；之后9题各取得一份有效fresh修补验证，1 PASS、8 FAIL。6份修补前置infra/外部中断记录独立隔离，不计正常模型FAIL；原版另有2份早期无效尝试。费用未知，保持null。

唯一F→P为Video：8/9→9/9，已记录1题1项Gemini独立Gold。Gemini与Claude的相对低能量候选未经音频审核机制一致，GPT同一原子机制未确证；Gold中defects[].model_sensitivity=null，不总括十题/全部缺陷三模型一致。Azure21/22的原origin-validation契约FAIL保留，没有修改verifier或按评分标签修补。其余有效FAIL与未复现/遮蔽边界完整保留，无新证据不盲目追加运行。

|任务|官方原版|有效修补验证|收束结论|
|---|---|---|---|
|pddl-airport-planning|PASS|无需|原版PASS，无Gemini缺陷/修补|
|python-scala-translation|FAIL|FAIL|项目发现改善，未遵循隔离验证且移走公开测试；未F→P|
|flink-query|FAIL|FAIL|部分终止事件语义有共同原轨迹证据；修补后编译回退/未遵循完成验证，未F→P|
|reserves-at-risk-calc|FAIL|FAIL|原版下载卡住未进入旧计算缺陷；修补后重算/错误扫描未执行|
|seismic-phase-picking|FAIL|FAIL|采用峰值时间后仍预算探索未交CSV；三模型原索引机制不同|
|dynamic-object-aware-egomotion|FAIL|FAIL|目标采样修正已采用，10/11；剩余运动质量机制不足|
|shock-analysis-supply|FAIL|FAIL|下载改善但0公式，旧经济单位缺陷未触发|
|enterprise-information-search|FAIL|FAIL|别名/报告发现改善，schema反复错误耗尽预算无答案；旧reviewer缺陷证据不足|
|azure-bgp-oscillation-route-leak|FAIL|FAIL|覆盖遗漏改善21/22；原origin-validation契约争议保留，未F→P|
|video-silence-remover|FAIL|PASS|8/9→9/9，1项独立Gold；Gemini/Claude同机制，GPT同机制未确证|

原版native调用合计1次，所有有效原版均确认完整正文注入；最后修补Azure native1，Video native0但7份全文及实际脚本采用已核实。模型固定、60 parent、32768输出/default reasoning、预算共享continuation、两题批次及隔离均保持。任务数据、官方Skill与verifier没有修改，无额外模型/Judge、无push。

实际输出/诊断已逐文件保存主记录或已核实既有远端副本；最后两批各精确清理2个Gemini停止容器/2个零引用任务镜像，不制造D重复归档、不强删/prune/删卷/干预其他流程。最后一批Docker LayersSize实测减少1306574860字节，C空闲观测变化-19873792字节（受并发写入影响），物理VHD回收未知，详见各清理收据。

独立Gold：[gold.json](gold_repairs/gemini31_gold1_20261007/gold.json)；标注：[annotation.md](video-silence-remover/annotation.md)。完整矩阵及证据索引：[final-summary-20261007.json](final-summary-20261007.json)，原版权威：[official-original-summary-20261006.json](official-original-summary-20261006.json)，最后批健康/因果/清理：pair5-r001-health-20261007.json、pair5-r001-causal-review-20261007.json、pair5-r001-cleanup-20261007.json。

已完成五个固定pair的证据对照、必要验证与记录；Gemini巡检已由automation_update确认暂停（PAUSED），保留此对话。收据：automation-paused-20261007.json。
