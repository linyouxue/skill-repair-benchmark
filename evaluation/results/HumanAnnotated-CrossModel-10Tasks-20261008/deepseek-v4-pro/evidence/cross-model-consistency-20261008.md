# DeepSeek V4 Pro 十题机制一致性审计

审计时间：2026-10-08T00:36:19.208606+08:00。10/10官方原版已结束，原始评分3 PASS / 7 FAIL；账户累计扣费16.25元，预算120元，余额87.69元，未触发预算停止。

**Flink PASS存在参考解答接触。** DeepSeek在真实请求第40–50行下载、浏览并执行远端oracle，读取checker及期望输出，执行返回完成标记与exit code 0。保留原始3/3评分，但它不能计入独立解题PASS，也不能证明旧缺陷未复现。其余两项PASS为Seismic与Egomotion；无已知参考答案接触的记录为9题；Shock另有强制工具缺失，纯能力/Skill因果需隔离。证据仅输出路径/索引和响应布尔元数据，没有显示参考答案或评分源码。

**不能给十题整体贴cross_model_consistent。** 明确加入DeepSeek的条目现为4个，分布在PDDL、Scala、Flink三题；Flink仅D002由隔离r002新增确认；Scala两个流程条目有关联，不是独立样本。RaR仅观察期限链相近子模式，Shock新查明强制Playwright MCP缺失，原同机制因果标签已撤回；其他原子机制分别保留未复现、未进入阶段、证据不足或参考接触限制。

|任务|原始结果|parent/实际请求|CTRF通过/总数|本轮机制结论|
|---|---|---:|---:|---|
|pddl-airport-planning|FAIL|23/23|1/2|canonical落盘缺口：GPT/Claude/DS；Gemini最终自行恢复|
|python-scala-translation|FAIL|34/34|未导出CTRF；canonical FAIL|包/项目契约与项目验收缺口：四模型；Option签名项未确证|
|flink-query|r001 PASS*；r002 FAIL|58/58；60/60|3/3；2/3|r001隔离；r002复现D002，无SUBMIT仍输出0；其余两项未复现|
|reserves-at-risk-calc|FAIL|30/30|3/5|旧实体遗漏未复现；期限链仅相近子模式|
|seismic-phase-picking|PASS|60/60|2/2|PASS且有峰值处理；旧失败机制本轮未复现|
|dynamic-object-aware-egomotion|PASS|29/29|11/11|PASS且开展模型/warp核对；旧失败机制未复现|
|shock-analysis-supply|FAIL|60/60|1/9|交付前耗尽行为相近，但强制Playwright MCP缺失；因果标签隔离|
|enterprise-information-search|FAIL|41/41|2/3|已扫描平铺/线程，答案仍错；旧漏扫原因未确证|
|azure-bgp-oscillation-route-leak|FAIL|10/10|3/4|显式映射分类失败；不能继承旧allowlist/偏好环过报|
|video-silence-remover|FAIL|38/38|7/9|recall与precision失败；旧三个GPT项及CG候选误删因果未确证|

## 已确认加入DeepSeek的机制

|条目|同机制支持的模型|边界|
|---|---|---|
|PDDL D001|GPT-5.2、Claude Opus 4.7、DeepSeek V4 Pro|Gemini中途遇到但最终修正；GPT含历史有效诊断|
|Scala D001|GPT-5.2、Claude Opus 4.7、Gemini 3.1 Pro、DeepSeek V4 Pro|确认默认包/项目契约缺口，不继承所有API子项|
|Scala D002|GPT-5.2、Claude Opus 4.7、Gemini 3.1 Pro、DeepSeek V4 Pro|standalone与自测替代项目验收，与D001有关联|
|Flink D002|GPT-5.2、Gemini 3.1 Pro、DeepSeek V4 Pro|Gemini/DeepSeek原版；GPT修补Round1诊断，未确认Claude|

以上是行为机制一致性；没有运行DeepSeek fresh修补/消融，不能证明原Skill是唯一原因，也不构成DeepSeek修补F→P或新Gold。已有GPT/Claude/Gemini标签保持原文件，支持集合来自既有标注及Gemini修复前对照，其他模型未在本轮重跑。

## 逐条结论

|任务/来源ID|本轮判定|证据与边界|
|---|---|---|
|pddl-airport-planning / D001|已复现同一机制|最终两份计划全部为function-display行，canonical括号行均为0；存在性通过、numerical失败。同一落盘机制已复现。Gemini中途也遇到，但自行修正且最终PASS，不加入稳定最终失败集合。GPT来源含有效历史诊断轮，其旧协议边界保留。|
|python-scala-translation / D001|已复现同一机制|最终Scala无package声明；轨迹先读Python后写实现，没有读取现有build与消费者契约。公开项目需要named package；官方FAIL，同一包/项目可见性机制支持四模型。完整公开API遗漏不是本条统一确认范围。|
|python-scala-translation / D002|已复现同一机制|多次独立scalac与自写测试，未运行原有SBT项目测试，最终仍FAIL。与D001为关联流程缺口，不将两条当作独立成功样本。|
|python-scala-translation / D003|同机制证据不足|本轮存在Option使用，但没有逐签名证据证明同一构造器变更导致失败；不能从使用Option或整题FAIL继承该子项。|
|video-silence-remover / D001|最终产物未建立该机制|曾运行原detector，但最终手工改为240秒边界，不能把最终recall失败直接归到原moving-average偏移。|
|video-silence-remover / D002|最终产物未建立该机制|使用官方combiner，未见额外正间隔合并逻辑；precision失败不足以证明此机制。|
|video-silence-remover / D003|最终产物未建立该机制|未观察到threshold_ratio调参；不能把默认阈值误检当作反向调参机制。|
|dynamic-object-aware-egomotion / D001|本轮未复现|本轮11/11，且实际开展warp方向、frame/mask索引与产物核对；没有同一错位证据。PASS只界定本次产物，不能推导Skill已修复。|
|dynamic-object-aware-egomotion / D002|本轮未复现|本轮比较full affine与homography并检查残差，官方运动与mask均通过，没有旧的实际对象误检证据。|
|dynamic-object-aware-egomotion / D003|本轮未复现|本轮采样与mask等11项通过，未见额外尾帧失败。GPT标注涉及诊断证据，Gemini对照说明有效GPT原版为规则网格，不能把诊断标签扩展为各模型原版共同错误。|
|enterprise-information-search / D001|同机制证据不足|本轮实际读取报告频道的顶层消息与thread，并汇总全部消息；answers内容聚合失败没有逐reviewer反馈。不能声称重复旧的未扫描机制；也不能断言答案完整。Gemini原版是检索/交付未完成的不同机制。|
|reserves-at-risk-calc / D001|本轮未复现|公开模板2025行非空国家Value列D/F/J/L/M/N/O/Q均被本轮引用；Volume仅用于未在Value列出现的Slovakia。本轮Step2 FAIL不能继承旧的实体遗漏/混源机制。|
|reserves-at-risk-calc / D002|仅观察相近子模式|实际C5=C4*SQRT(12)，exposure直接使用C5，再传播到RaR；与既有期限混用有相近子模式。Step1通过而Step2/3失败，但near-term题面有期限歧义，汇总测试不能排除其他原因。百分比/100存在，不能同时确认全部单位/假设子项，也未证明同一因果，暂不赋本轮cross_model_consistent。|
|flink-query / D001|隔离r002未复现|最终68–70行只接受FINISH；旧污染r001继续隔离。|
|flink-query / D002|隔离r002已复现|159–164行空stageState仍转0并collect；Gemini/DeepSeek原版、GPT修补Round1诊断支持，无Claude独立证据。|
|azure-bgp-oscillation-route-leak / D001|同机制证据不足|DeepSeek以显式字典分类，UDR/intent均true/true，RPKI为false/false。没有旧allowlist路径；RPKI标签相似不足以证明同一推理层级原因，方案分类聚合失败也不定位该行。Gemini的关键词fallback为相关机制，不能继承整个复合条目。|
|seismic-phase-picking / D001|本轮未复现|本轮有数据/幅值检查且2/2通过，没有实际有效通道被丢弃的证据；Gemini短channels跳过是相关但不同实现。|
|seismic-phase-picking / D002|本轮未复现|本轮有效CSV被接受，没有量化概率塌缩导致失败的证据。不能由PASS推导所有推理健康条件已成立。|
|seismic-phase-picking / D003|本轮未复现|本轮使用find_peaks及后续窗口内argmax；局部argmax不等于旧的无条件一对输出，未复现同一失败。Claude固定窗口/单峰是相关子项而非自动等同。|
|seismic-phase-picking / D004|本轮未复现|未观察到相同越界裁剪产生无证据到时的失败；ClaudeS约束P的子模式须另辨，不能整体继承。|
|shock-analysis-supply / D001|环境保真度混杂，撤销因果一致性|44/60轮数据获取/恢复，真实workbook与公开模板相同、0公式。题面明确要求Playwright MCP，但全60请求工具目录及环境均缺失；另有IMF403/反机器人障碍。可保留共同耗尽行为，不能确认干净的跨模型Skill因果。|
|shock-analysis-supply / D002|未进入该计算阶段|本轮尚未到有效经济计算；不能从缺公式的1/9推导同一billions/millions错误。|
|shock-analysis-supply / D003|未进入该计算阶段|本轮没有形成旧Round2可计算模型，不能把未构建计算链等同于重算/HP初值机制。|
|video-silence-remover / CG-D001|同机制证据不足|本轮做过全局多阈值silencedetect、开场短帧RMS/ZCR及候选能量对照，随后沿用默认pause候选。候选仍主要依赖能量，存在审核不足风险；但precision聚合失败不证明与Claude/Gemini同一候选误删，中间音频/候选文件已由agent删掉，未伪造归档。需独立原音频证据才可加DeepSeek。|
|azure-bgp-oscillation-route-leak / C-D001|本轮未复现|DeepSeek将export/community置为oscillation=false、leak=true，与Claude原版过报偏好环修复不同。|
|reserves-at-risk-calc / C-D001|本轮未复现|本轮exposure未额外乘SQRT(3)。与年化值直接入链的相关性不等于同一具体算式机制；保留题面期限歧义。|
|flink-query / G-D-extra|隔离r002未复现|155–157行检查finishSeen，无流末兜底绕过完成谓词；旧污染r001继续隔离。|
|seismic-phase-picking / G-D-extra|本轮未复现|Gemini独立原版对象时间语义错误，与GPT的annotation时间轴和Claude的peak_time不同。DeepSeek以概率峰窗口处理，未观察同一start_time取值错误。|

## 协议、费用与归档

真实provider元数据共383次请求，响应model均为deepseek-v4-pro，thinking=enabled、reasoning_effort=high、max_tokens=32768。OpenHands不支持ACP effort，因此executor的ACP值为null，high由provider层实施；不能用executor字段null推断未启用high。固定runtime、冻结task/Skill/verifier、每题60 parent和共享预算continuation沿用批准流程。

十题n_skill_invocations均为0。bundle快照暴露验证均通过，并另存实际请求中的Skill全文匹配证据；Scala精确5/6，Flink精确0/2，其他题全部精确匹配。零精确匹配不证明未读；Flink另有参考解答接触，无法据此归因。

实际导出tar和真实交付逐文件核对后，累计删除本批次12个停止容器（含2个ACP无效启动环境）及10个零容器引用任务镜像tag。本次最终Docker查询确认自有容器/镜像均无剩余，原worker与supervisor均已结束。未删除卷或其他流程资源；没有可靠独占VHD空间差，不报告虚构物理回收字节。原始结果、轨迹、真实产物、诊断与哈希清单保留于主记录，未额外备份或push。

三次无效启动另列infra：PDDL/Scala ACP effort接口不支持，Enterprise并行子网预留冲突；均为provider前失败、留证审核后按最多两次启动恢复。没有重跑有效FAIL。

## 证据索引

- [逐条结构化一致性审计](atomic-consistency-audit-20261008.json)
- [十题原始结果与安全CTRF投影](official-original-summary-20261008.json)
- [最终真实资源、费用与归档扫描](heartbeat-scan-20261008-0010.json)
- [Flink参考接触响应元数据](reference-access-response-metadata-20261008.json)
- [助手代码与产物元数据投影](mechanism-code-projection-20261008.json)
- [RaR/Video补充行为投影](mechanism-followup-20261008.json)
- [公开RaR模板覆盖核对](public-template-coverage-20261008.json)

未修改任何原Skill或verifier，未追加付费验证。若后续需要Skill修补，应先审核首错、因果和最小修改位置，再另行确认。

每30分钟heartbeat已通过应用工具暂停并核查配置，其他设置保留，聊天保持开放。完成回执：[completion-and-heartbeat-pause-20261008.json](completion-and-heartbeat-pause-20261008.json)。

## 2026-10-08 Shock归因更正与Flink受限重跑

进一步核查发现Shock强制Playwright MCP缺失，已撤销该项DeepSeek cross_model_consistent标签；Shock归因更正时确认3条；Flink隔离r002后增至4条，分布PDDL、Scala、Flink三题。第8轮32,768输出token全为reasoning并截断，284.431秒无工具动作；44/60轮用于外部来源获取/恢复，最后4轮才安装浏览器。部分数据已可用但没有任何保存/写公式，最终模板逐字节未变。完整分析见[Shock预算报告](shock-budget-analysis-20261008.md)。

用户已明确授权Flink重新运行：保留原污染r001，新增fresh原Skill r002，仅对本次agent的答案访问实施网络隔离；task/Skill/verifier、固定OpenHands runtime、V4 Pro/high、60 parent与原120元共享预算继续保留。先由root预装公开starter Maven依赖，必须完成agent离线编译与外网/通用代理阻断探针，才能发送实际模型请求。运行证据位于[隔离重跑目录](flink-noanswers-20261008/state.json)。


## Flink隔离r002最终验收

2026-10-08T09:37:30.958609+08:00：有效FAIL、2/3（构建/运行通过，输出失败）、60/60 parent和真实V4 Pro/high请求。未见成功答案访问；D002已复现，D001/G-D-extra未复现。native0但两份Skill全文注入全部60请求（仅示例口令脱敏规范化），轨迹硬门通过。新增账户观测扣费约4.26元，共享累计20.51元，未触发120元预算停止。47份真实主记录及9个源文件逐文件核对，最终agent输出/日志已保存，所属容器/镜像/空网络精确清理。原r001污染评分永不作为独立证据。完整[验收报告](flink-noanswers-20261008/report-r002-20261008.md)。原十题历史评分和其他模型来源标注保留，没有付费修补或新Gold。

2026-10-08：Flink r002验收、归档、精确清理全部完成，deepseek-30已通过应用工具暂停并核实实际配置；worker及gateway均结束，聊天保留。[完成与暂停回执](flink-noanswers-20261008/completion-and-heartbeat-pause-20261008.json)。
