# 第五批：优先验证已有Claude/GPT标注

先前四批已收束，所有官方原版结果有效；本次不重跑原版，不重新扩展缺陷体系。既有标注分别读取GPT Gold01与Claude Gold02及对应annotation、实际原轨迹和已验证候选。逐defect的一致性是待验证假设，正式model_sensitivity/Gold须真实F→P和同一机制支持。

Azure：Gemini原版18 parent/18 provider正常end_turn，正文完整注入、native0，官方总计20/22。ACP14/20构建有限关键词分类，未命中即默认False；真实报告的route-preference hierarchy候选未进行实际效果分类，接近GPT D001有限白名单缺口。Gemini并未复现Claude原版将provider export restriction过报为解除peer偏好环，也未复现其Round1的Tier1/3不一致。原指导已有总体分层，缺少完整候选机制覆盖；候选从Gemini原版完整快照出发，仅改azure-bgp/SKILL.md，参考ClaudeRound2的独立效果/判定层检查，并参考GPT既有经验补两句按完整描述逐项恰好评估、关键词未匹配不能默认False。

保留Azure评分契约限制：ClaudeRound2原verifier实际21/22、reward0；另行origin-validation契约补验22/22不能当本Gemini官方成功。本轮仍用冻结原verifier。旧GPT固定RPKI类别标签不复制；[RFC6811](https://www.rfc-editor.org/rfc/rfc6811.html#section-6)说明origin验证不保护完整路径，需依实际prefix/origin及策略拒绝证据判断。严格停止广告、接收传播与转发containment的术语边界据公开任务记录，不能按隐藏expected labels设计候选。

Video：Gemini原版13 parent/13 provider正常end_turn、native0但七份全文预加载，官方8/9，仅precision失败。ACP4默认opening221；ACP6以ratio0.5/min2/window30产生11候选28秒；ACP7未经原音频审核便合并成12段249秒。与Claude原始低相对能量候选直接剪辑首错相符。原Skill过度声称能避免音量变化误检；候选保留原2秒粗筛，仅按同录音20ms RMS的log能量两簇进行独立候选验证、输出审核记录，并保守核查开场变更证据。它是完整逐字ClaudeRound3已验证9/9候选在Gemini原版快照上的三文件差异，不移植答案/固定时间/段数。

GPT Video的moving-window索引偏移存在于共享原脚本，但未由本Gemini音频证据证明其为precision主要根因；Gemini保留[522,524]与[525,527]之间的正gap，无ratio调参，也没有手工扩大opening。因此不把三个旧GPT缺陷或整题直接判为三模型一致。

完整原始对照、源路径及候选SHA：pair5-original-evidence-20261007.json；候选有限健康/机制核查：pair5-candidate-health-20261007.json。完整bundle集合与support files保留；Azure只改1文件，Video14文件中只改3文件。共享任务数据/官方Skill/verifier不变，无额外模型/Judge/provider探针。健康核查通过后，固定模型/60 parent/32768/default reasoning/共享continuation预算，每题一次fresh、独立进程/镜像/网络，两题屏障继续。
