# 第一批原始证据对照与待验证修复

本记录在10/10官方原版有效结束之后创建。它是修复前审核，不是Gemini Gold，也不把任务失败直接转换为Skill缺陷。

## pddl-airport-planning

GPT-5.2与Claude的有效原始失败均留下function-call格式计划，内存求解有效，但官方PDDLReader无法解析写盘文件。已查看两份原始ACP轨迹；GPT来源为expanded_original_skill_runs/gpt52-openrouter-v1.1-20260903/runs/expanded-original-skill/pddl-airport-planning-original-skill-v11x-20260908-guarddiag-infra-r003，Claude来源为expanded_original_skill_runs/opus47-openrouter-v1.1-20260919/runs/opus47-original-skill/pddl-airport-planning-opus47-original-skill-r001。GPT历史诊断的旧协议元数据边界继续保留，不重算其标准协议通过率。

Gemini有效原版r002最终官方2/2、reward1。ACP第9行同样先写function-call格式，第19行自行parse_plan明确报Cannot interpret；第23–26行改成canonical括号格式并验证成功。第32–35行再次产生并发现该格式错误，最终第38–40行恢复canonical写盘并对两个exact文件验证成功，第41行结束。

因此，三模型中均观察到相同的中途格式陷阱，但只有GPT/Claude把错误交付到最终verifier；Gemini自行恢复，不能声称三模型最终稳定失败一致。Gemini本题不做付费修补、不新记defect或Gold。本题对model_sensitivity的最终统计须区分“共同中途暴露”与“最终稳定暴露”，不能继承此前10题一致的总括。

Gemini原版pre-verifier空tar仍是runner导出路径错误；已有停止容器真实文件恢复明确发生在verifier后。不能把该归档缺口归因于Skill，不能冒充原始pre-verifier产物。

## python-scala-translation

首个关键错误是未发现已有项目消费者契约便生成默认包Scala源码。Gemini ACP第3行只读Python；第8行写Tokenizer.scala；第9行仅standalone scalac；第10–12行创建并运行自写smoke test；第14行结束。全轨迹没有读取公开build.sbt/TokenizerSpec.scala或运行现有SBT项目测试。真实tar中最终15,306-byte Scala没有package声明；官方output.log第18–81行记录21个not found，质量23/25但实际项目测试未能编译。

公开Dockerfile明确提供/root/build.sbt、/root/TokenizerSpec.scala和/root/localtest，公开测试以package tokenizer开头。构建包含Scala2.13.12及Circe、ScalaTest依赖。必要输入可见；本次21个错误为生成代码的项目契约不匹配，不是verifier安装故障。

已核对GPT原版python-scala-translation-original-skill-r003与Claude原版python-scala-translation-opus47-original-skill-r001的ACP：两者也没有读取已有build/test，最终只验证独立编译或自建测试，并在官方项目测试编译时遇到同类21个符号不可见。因此“缺少项目契约发现与最终项目验证门槛”支持共同候选机制。原Skill的idioms以一般惯用法为主；libraries虽有ScalaTest/build.sbt示例，未要求先检查已有消费者。兼有模型的验收遗漏，不能将指导缺口认定为唯一原因。

Gemini源码包含TokenRegistry、TokenFunctor、JsonTokenizer等定义，故不能机械继承Claude的缺类表现。未在本记录给GPT的Option/public API子项全部贴跨模型标签；包修正后可能暴露的签名差异仍须逐项证据核对。

## 候选最小修改及fresh验证（待执行）

从Gemini原版六份Skill快照复制完整bundle，保留原结构。候选只在python-scala-idioms/SKILL.md正文开头增加一段项目契约门槛：实现前读完整Python源和已提供的公开build/test，提取包、依赖和调用签名；惯用法转换必须保持公开API及完整源码覆盖；对最终交付文件在隔离SBT项目运行未修改的公开测试，成功必须有实际测试执行并全部通过；standalone scalac和自写smoke test不能作为完成依据。具体公开文件入口为/root/build.sbt、/root/TokenizerSpec.scala；隔离项目只复制最终源码与公开构建/测试文件，避免与预置参考源码或同名suite混用。

参考Claude低轮次已验证机制，但不整套继承其强化内容，不写具体翻译实现、隐藏测试、答案或评分阈值。当前第一批PDDL原版PASS作为无需修补处理，Scala至多一个活动Gemini fresh rollout；第一批复核/必要验证收束后才推进下一批。固定模型、60 parent、32768输出、默认reasoning_effort、一次共享预算continuation、原BenchmarkExecutor及OpenHands缓存继续沿用；仅使用独立Gemini目录、镜像tag、网络与启动锁。

只有真实fresh F→P及证据支持后才写Gemini修复标注/独立Gold及defect的model_sensitivity。若未遵循已有明确指导，记录执行遗漏；没有新证据时不追加重复提醒或盲目重跑。当前没有新repair rollout、没有Gemini Gold或最终模型敏感性标签。

## 23:32 启动记录

上述修复前审核已落实为第一轮候选：完整六文件原版bundle，只在idioms开头新增21行项目契约和验收步骤，其他内容保留。Frozen task digest、实际差异和固定runtime archive均通过本地预检，没有额外付费探针。fresh rollout为python-scala-translation-gemini31-manual-round-1-r001，runner65178，实际compose build65179及buildx65240已核实；startup证据另存。当前是构建中的待验证候选，没有Gold或最终model_sensitivity标签。正常活动按30分钟巡检接续，不持续等待整题。
