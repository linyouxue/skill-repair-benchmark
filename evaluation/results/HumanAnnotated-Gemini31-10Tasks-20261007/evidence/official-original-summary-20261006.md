# Gemini 3.1 Pro 官方原版结果汇总

10/10 有效原版结束：1 PASS、9 FAIL。2次早期基础设施无效尝试已排除。官方有效FAIL没有为追求PASS而重跑。

|任务|结果|Parent|请求|结束原因|native Skill调用|全文Skill数|
|---|---|---:|---:|---|---:|---:|
|pddl-airport-planning|PASS|36|36|end_turn|0|1|
|python-scala-translation|FAIL|11|12|end_turn|0|6|
|flink-query|FAIL|60|62|max_iterations|0|2|
|reserves-at-risk-calc|FAIL|8|8|stuck|0|1|
|seismic-phase-picking|FAIL|60|62|max_iterations|0|4|
|dynamic-object-aware-egomotion|FAIL|23|23|end_turn|0|4|
|shock-analysis-supply|FAIL|60|60|max_iterations|0|1|
|enterprise-information-search|FAIL|60|60|max_iterations|1|1|
|azure-bgp-oscillation-route-leak|FAIL|18|18|end_turn|0|1|
|video-silence-remover|FAIL|13|13|end_turn|0|7|

所有有效轮次均确认原版Skill全文预载。native工具调用合计1次（enterprise），其余为0；这不表示模型未看到Skill正文。Video还实际运行了全部7份Skill自带脚本。

轨迹、实际provider token/timing、官方verifier、真实pre-verifier tar及逐题健康审计索引见同名JSON。费用未知，保持null。

PDDL的原pre-verifier导出路径错误，45字节空tar原样保留；停止容器中真实输出在verifier后零模型恢复，单独标明来源，不冒充pre-verifier产物。部分CTRF合并参数化测试名，完整子测试以stdout和health记录为准。

原版结束后进入逐defect对照。cross_model_consistent属于defects[].model_sensitivity的取值；当前汇总没有给10题统一贴标签，也没有新建Gemini Gold。

另一Claude标注流程没有被修改；资源等待按用户最新指令解除，两题屏障和运行隔离仍保留。
