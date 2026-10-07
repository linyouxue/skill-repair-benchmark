Gemini 60→100→本次100/200轮比较（2026-10-07T18:29:44.401477+08:00）

源100轮六题1 PASS/5 FAIL；本次五题单次fresh为0 PASS/5 FAIL。Scala已PASS，未复跑。

|任务|60轮修补候选|100轮fresh|本次fresh|本次parent/provider及停止|
|---|---|---|---|---|
|python-scala-translation|FAIL 0/0（测试复制早退）|PASS 10/10|已PASS，未复跑|—|
|flink-query|FAIL 0/3|FAIL 1/3|FAIL 2/3|68/70，end_turn（上限100）|
|reserves-at-risk-calc|FAIL 1/5|FAIL 1/5|FAIL 1/5|200/201，max_iterations（上限200）|
|seismic-phase-picking|FAIL 0/2|FAIL 1/2|FAIL 0/2|9/9，stuck（上限100）|
|shock-analysis-supply|FAIL 1/9|FAIL 2/9|FAIL 1/9|200/200，max_iterations（上限200）|
|enterprise-information-search|FAIL 1/3|FAIL 1/3|FAIL 1/3|100/108，max_iterations（上限100）|

每题均沿用完整候选字节与冻结task/verifier；原版、60轮、100轮历史及Gold保留。表中60轮是修补候选试次，不是官方原版。所有评分均经独立健康审查；RaR/Shock控制面异常的原记录未覆写，比较使用明确标为派生的零模型原verifier恢复结果。

python-scala-translation：100轮试次在67 parent后通过10/10，尾部忙终端与缺command的reset交替触发stuck。评分与停止原因独立；已PASS所以本次排除。单次fresh不能分离预算与路径差异。

flink-query：同100上限fresh绕过源试次四次重复成功写文件的停滞，68 parent正常end_turn，2/3；仅输出匹配未通过。改善不能归因于提高预算。

reserves-at-risk-calc：200 parent仍1/5；真实最终工作簿1314公式无非空cache，Volume1有存储error cell。加预算未带来PASS，评分前控制面故障另用真实产物零模型补验。

seismic-phase-picking：同100上限fresh仅9 parent，四个独立模型响应合法空command/is_input等待，无新输出后被SDK判stuck。反馈进入下一请求；合法等待提前截止构成归因限制。真实CSV为127行、57预测文件，0/2。

shock-analysis-supply：200 parent达到预算，真实最终工作簿5表、0公式，1/9；源100为99公式全无cache、2/9，属于不同fresh产物，不能把当前0公式归为同一工作簿被删。最后fix_supply2.py仅读PWT行并print，无save/recalc，执行成功仅证明诊断。评分前控制面超时单独保留，实际产物零模型原verifier补验得到明确派生评分；未建立经济首错或纯预算因果。

enterprise-information-search：同100上限fresh在parent73交付answer.json，随后继续检索至100，答案未再更新，仍1/3。19次不支持的多命令形态被工具拒绝，反馈完整进入下一请求；与源27轮反复list.items报错不同。自报tokens全0与真实usage矛盾，未据此推定动机。

提高parent上限不会关闭SDK的4次同动作/结果及6步交替停滞检测。
独立provider响应及正确反馈链支持真实模型重复生成；未发现可见执行器重放或反馈丢失。
合法wait被同动作检测提前截止是SDK与工具交互因素，不能统一归为模型能力不足。
同100上限fresh路径已明显变化，因此单次fresh实验不能独立估计预算因果收益。
任务涉及模型规划、工具格式、长程执行及产物交付；这些可观察行为与旧Claude/GPT原子缺陷须逐个匹配，不能由共同FAIL推出cross_model_consistent。

五次followup结束资源均已逐文件核实主记录并精确清理：5停止容器、5零引用任务镜像标签、0卷，无force/prune；空间限制见JSON和逐题cleanup收据。费用未知null；新增结果仅本地，没有push。

评分、实际调用、逐测试name/status、正式审查及清理路径见同名JSON；重复机制证据复用../budget100-20261007/stuck-root-cause-20261007.json/.md。
