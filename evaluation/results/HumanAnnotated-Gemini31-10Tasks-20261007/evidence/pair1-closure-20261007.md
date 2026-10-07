# 第一批证据收束

两题官方原版均已有效结束。本记录是有限轨迹对照与修复尝试结论，不是 Gemini Gold。原始证据入口及共同机制见 pair1-review-20261006.md。

## PDDL

Gemini 官方原版 reward=1、2/2，最终写盘格式正确。GPT/Claude 最终失败的 function-call 计划格式在 Gemini 中途也出现，但 Gemini 自行纠正。不能把共同中途暴露写成三模型最终稳定失败；不修补、不新建 Gemini defect。

## Python → Scala round 1

- rollout：python-scala-translation-gemini31-manual-round-1-r001。
- canonical：execution_ok=true，reward=0，60 parent、66 provider requests，max_iterations；所有顶层 error/verifier_error/export_error 为 null。费用未知 null。
- 候选为原版完整六 Skill bundle，仅 idioms 增加项目契约发现、保留公开测试及隔离最终文件验收步骤。expected/observed bundle digest 相同；原生 Skill 调用为 0，新增正文实际预载。
- 真实预 verifier tar 为 7,787 字节，含 Tokenizer.scala（9,098 字节）、Tokenizer.py、build.sbt；未含原路径 TokenizerSpec.scala 或 translation-validation.log。不是从轨迹重建的文件。
- ACP 3–5 实际读取 Python、build.sbt 与公开 TokenizerSpec，最终产物也有 package tokenizer：项目发现/包契约出现局部改善。
- 模型没有执行候选的临时隔离项目命令，而在 /root 项目反复 sbt test，制造测试编入 main、重复定义及源码副本错位问题。ACP 18 重写复制的测试，内容与公开测试一致，没有弱化十项断言；ACP 24 将原 /root/TokenizerSpec.scala 移进 src/test，此后没有恢复原路径。ACP 25/54/62 的本地 10/10 不等于最终交付文件的隔离验收，也不能替代官方所需输入路径的保留。
- 官方 verifier 编译成功，测试结果为 0/0，质量 21/25，最终 FAIL。这里不是十个测试执行后失败，也不是质量分数低于通过条件。冻结 verifier/test_outputs.py 第 245–251 行先复制原路径测试，复制失败即返回零测试；第 259 行之后才会运行 sbt，第 742 行要求实际十项测试。公开测试原路径被移走、预归档缺失及 0/0 无 sbt 测试输出共同支持“模型破坏所需输入路径导致测试复制早退”；日志未直接打印该异常详情，此证据边界保留。

这是有效的候选验证 FAIL；没有证据支持 verifier 安装/网络/控制面故障。不能恢复或重建产物后冒充本轮 F→P，也不做基础设施补验。

首轮新增规则已要求隔离测试及保留公开输入。后续失误归为 agent_did_not_follow、输入路径修改和预算耗尽；本轮没有发现值得再付费验证的新 Skill 缺口。不靠重复提醒盲目启动 round 2。

## 当前结论及后续

Scala 原版的项目契约候选机制在三份原始轨迹中有共同证据，但此次最小候选未取得 Gemini F→P，只能记为未验证成功。没有新增 Gemini defect/独立 Gold，没有最终 model_sensitivity 标签；GPT/Claude API、Option 或缺类子项不会自动继承。

第一批当前必要验证已收束：PDDL 无需修补，Scala 保留失败尝试和未成功候选。若后来获得新的具体修复证据再评估；当前推进固定第二批 flink-query 与 reserves-at-risk-calc。两题的原版首错必须分别审核，不能把 reserves 原版未进入计算阶段的下载循环当作已暴露旧模型的公式缺陷。

独立健康审计：python-scala-round1-health-20261007.json。完整 summary、轨迹、真实 tar 与原评分均保存在本 Gemini 根；其他 Claude 工作流未改动。
