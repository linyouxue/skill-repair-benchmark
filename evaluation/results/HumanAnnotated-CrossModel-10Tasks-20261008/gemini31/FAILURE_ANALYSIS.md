# 十题失败机制与模型依赖分析

这批结果支持**修补效果及失败路径具有模型依赖性**，但不能推出“十题都不 consistent”，也不能据此给 Gemini、Claude、GPT 的总体能力排名。需要区分任务最终失败、同一原子缺陷是否出现、以及某份修补是否足以让整个任务通过。

## 实际结果

官方原版先完成10题，1 PASS/9 FAIL。随后对9道原版FAIL题，各取得一份有效fresh候选验证：1 PASS/8 FAIL；另有6份启动/外部中断的infra记录隔离，不计模型FAIL。原版另有2份无效尝试。全部使用冻结原verifier，没有为PASS改评分或补写答案。费用未知，保持null。

|任务|原版实际评分|fresh候选评分|关键机制与结论|
|---|---|---|---|
|PDDL|2/2 PASS|无需|三模型中途都遇到计划文本格式陷阱，Gemini自行恢复并最终PASS；有共同暴露，但不是共同最终失败。|
|Python→Scala|项目测试无法编译，FAIL|0/0实际测试，FAIL|三模型均有未发现项目消费者契约的原始证据。Gemini候选后发现包/测试，但未按隔离验收指导执行，移走公开测试使官方测试复制早退；不是10项测试全部执行后失败。|
|Flink|2/3 FAIL|0/3 FAIL|三模型均扩大“finished”的事件语义；不同模型的零行/流末兜底问题须分别认定。候选后编译API回退、pom违规及未落实输出资格检查遮蔽验证。|
|RaR|0/5 FAIL|1/5 FAIL|Gemini原版在错误下载后的不变读取循环结束，未进入旧GPT/Claude期限/公式缺陷。候选改善下载，随后未执行原xlsx已要求的重算/错误扫描，1321公式没有缓存。|
|Seismic|0/2 FAIL|0/2 FAIL|Gemini用Pick.start_time，GPT原始有效轨迹采用annotation时间轴，Claude用peak_time。候选已采用峰值时间，但预算内未交results.csv，无法判断F1改善。|
|Dynamic|9/11 FAIL|10/11 FAIL|Gemini照原示例追加非网格源尾帧；GPT/Claude未出现该采样首错。候选修正采样且mask测试通过，剩余motion质量不足，不能由分数倒推具体方向错误。|
|Shock|1/9 FAIL|1/9 FAIL|大量预算花在来源获取，真实工作簿为5表0公式；尚未触发Claude旧经济单位缺陷。题面原生Excel/Solver/Playwright接口未被证明存在，程序契约限制必须单独保留。|
|Enterprise|1/3 FAIL|1/3 FAIL|Gemini困在代号过滤/嵌套schema检索，候选改善部分发现但仍未交answer.json。Claude已出答案后暴露的reviewer完整性缺陷在此无答案可检验；GPT早停又是另一条路径。|
|Azure|20/22 FAIL|21/22 FAIL|覆盖遗漏与GPT有限关键词问题接近，候选修正hierarchy。剩余RPKI原verifier契约断言保留；不能导入Claude另行修订契约的22/22或固定评分标签。|
|Video|8/9 FAIL|9/9 PASS|实际采用已有Claude音频候选审核，形成唯一独立Gemini Gold；Gemini/Claude同机制有证据，GPT同一原子机制尚未确证。|

Azure数字来自参数化pytest stdout；其CTRF将分类参数聚合成一个类别，不能把3/4类别计数当成参数级结果。早期pair5修复前文字把18次parent/provider误写成18项通过，上传前已对照原stdout局部改为20/22；原始分数与轨迹没有改动。

## 为什么既有修补只有一题转PASS

**失败阶段不同，旧缺陷可能根本没有被触发。** RaR尚未下载工作簿、Shock尚未完成计算模型、Enterprise尚未形成答案时，旧Gold的公式、单位、reviewer缺陷都没有可比较的最终产物。此时应记“未复现/被前置失败遮蔽”，不是确认缺陷不一致，也不是确认Skill有错。

**局部机制被修正，不等于整个任务通过。** Scala发现项目包契约后仍修改必需输入路径；Seismic已改用peak_time仍未提交CSV；Dynamic采样纠正但运动分类仍失败；Azure修好覆盖遗漏仍有单项契约问题。因而F→F可以同时包含某个缺陷的改善和另一个瓶颈。Gold采用实际F→P门槛，未获Gold不等于否定所有共同原始机制。

**完成能力与预算有明显关系。** 9份有效fresh中6份达到60次parent上限：Scala、Flink、RaR、Seismic、Shock、Enterprise。这些轨迹有真实工具行为、完整usage/评分，并非6次Docker超时。反复尝试工具、组织项目、恢复错误、遵循已有指导和及时交付，本身就是当前模型配置的任务完成能力；不能当成与模型无关的噪音。但也没有证据证明增加预算就一定成功。

**存在任务/评分边界，不宜全部算成模型弱。** Azure剩余是原评分契约争议；Shock原生接口能力未确证；PDDL有效PASS的原预评分tar存在runner路径归档缺口，真实停止容器恢复发生在评分后并单独记录。这些限制与正常断言FAIL、Skill缺口、模型执行问题必须分开。历史基础设施失败已经隔离，不应重复计入八个有效fresh FAIL。

原版native Skill调用总计1次；fresh总计2次（Flink、Azure各1）。所有19个有效选择运行均有可复核完整正文注入证据。因此不能仅根据native调用低，就把本批失败归因于Skill未提供或正文未暴露。

## 对“模型能力相关”的判断边界

可以说：**这组任务中的Skill缺陷显现、错误恢复、预算使用和修补迁移效果，受到模型与执行配置影响。** PDDL自行纠错与动态采样的不同路径是直接例子；Video则提供了跨Gemini/Claude迁移成功的反例，说明也存在可复用的Skill问题。

目前不能说“Gemini总能力比另两模型弱”或“Skill效果主要由能力决定”，原因是：

- 每题仅一份有效Gemini原版和一份有效候选验证，没有重复试验来估计随机波动。
- 这10题来自既有人工标注关注任务，不是随机抽取的总体能力样本。
- Claude/GPT Gold使用过不同修复轮次、候选及人工介入；部分旧PASS是verifier-only/契约补验，不能等同本批冻结verifier下的fresh PASS。
- 相同60 parent上限不等于相同推理计算、token消费或能力条件；本批按模型/SDK默认reasoning运行。
- 本批没有配对no-skill控制，不能分离Skill本身的净效应、模型能力与工具/预算交互。

因此，1/9应称“这组已审核候选在本次fresh Gemini验证中的任务转PASS结果”，不是总体能力得分，也不是三模型一致性比例。当前Gold只有Video D001，defects[].model_sensitivity为null；跨三模型同一原子机制证据不足，不能预填cross_model_consistent。

## 结果应怎样用于研究

建议保留两层结果：任务级官方reward/PASS与原子缺陷级的共同暴露、未复现、遮蔽和已验证迁移。多模型共有原始首错（如Scala、Flink）可以作为有限共同机制证据，但失败候选尚不能算已验证成功的Gold。将当前结果描述为“跨模型既有缺陷迁移验证及模型依赖失败案例”比“十题全部一致”更符合证据。

若未来研究需要量化能力或迁移差异，应另行预注册匹配候选、相同原verifier、重复次数和预算的对照；本次不新增模型调用、Judge或为补标签盲目补跑。

## 证据入口

- [STATUS.csv](STATUS.csv)、[MANIFEST.json](MANIFEST.json)：19份有效运行、source→published路径、实际调用、结束原因与逐文件哈希。
- [第一批原始对照](evidence/pair1-review-20261006.md)、[第一批收束](evidence/pair1-closure-20261007.md)。
- [第二批原始对照](evidence/pair2-review-20261007.md)、[因果](evidence/pair2-r003-causal-review-20261007.json)。
- [第三批原始对照](evidence/pair3-review-20261007.md)、[因果](evidence/pair3-r001-causal-review-20261007.json)。
- [第四批原始对照](evidence/pair4-review-20261007.md)、[因果](evidence/pair4-r002-causal-review-20261007.json)。
- [第五批原始对照](evidence/pair5-review-20261007.md)、[健康](evidence/pair5-r001-health-20261007.json)、[因果](evidence/pair5-r001-causal-review-20261007.json)。
- [旧Claude Gold15（现并入Gold28）](../../HumanAnnotated-Claude-Gold28-20261007/README.md)、[旧GPT Gold31](../../HumanAnnotated-Gold31-20260917/README.md)：注意各自fresh/补验与修补轮次边界。

