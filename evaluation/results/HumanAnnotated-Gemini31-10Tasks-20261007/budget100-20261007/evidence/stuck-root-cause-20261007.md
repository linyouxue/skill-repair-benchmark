Flink 的 stuck 是模型动作循环：父轮30–33的四个独立HTTP200响应都再次写同一份 TaskEvent.java。四次工具执行均exit0；前三次成功反馈按正确tool_call_id进入下一请求，历史条数60→62→64→66且前缀完整保留。因此，可见尾部不是provider重试、执行器重放或工具反馈丢失。

固定OpenHands SDK1.28.1默认在4次相同动作/结果或6步交替模式后判定stuck，比较时忽略call/generation/action ID。Flink与前者吻合；运行上限100没有被用尽。实现依据是固定runtime archive中的conversation/types.py:62–72、stuck_detector.py:140–174和275–309，文件SHA、精确请求ID及反馈SHA见同名JSON。

Scala 的尾部是另一种交替循环：新sbt命令返回“前一命令仍在运行，本命令没有执行”；随后模型发只有reset:true的调用，却遗漏真实schema必需的command字段，因而reset本身被拒绝。相同错误反馈均进入下一请求，但模型继续交替重复这两类动作。父轮62–67/ACP64–69与6步交替检测吻合。不能把它描述成三次新的sbt编译都耗时过长。

SDK LocalConversation检测后设为STUCK；固定CLI通常返回ACP end_turn，benchflow adapter再按真实execution_status映射成语义stuck（openhands_benchmark_adapter.py:477–495）。这是对话的终止原因，与任务评分独立。Scala已由官方完整10个测试通过、质量22/25，仍是有效PASS，无需因stuck标签重跑。

限制：保存的ACP不含内部detector分支日志，具体分支来自尾部模式与固定源码的对应推断；不能观察模型或provider内部状态，也未排查Scala原先命令为何仍在运行。可见请求历史没有截断，但不能证明服务内部完全没有其他因素。提高轮数上限不会自动解除循环检测；新fresh运行可能走不同路径，不能据此保证重跑成功。

本次仅复用已完成健康门并读取尾部轨迹和本地固定源码；没有重复validator/评分、调用模型或Judge、访问隐藏评分源码、修改任何候选/共享代码/旧Gold/state或操作Docker。

后续已结束运行的有限补充：Enterprise在27轮停住，四个独立模型响应重复执行同一解析脚本；真实报错是把Slack列表当成字典调用.items()。错误反馈正常进入下一请求，但模型没有修正脚本，也没有交付answer.json。这与Flink反复执行已成功写入的机制不同，都在100上限之前停住。

地震题43轮的尾部则是四次合法空command/is_input等待，运行中的命令没有新输出，触发同动作/结果检测。这里存在合法等待被提前截断的可能，不能把所有stuck统一归因于模型能力不足。现有真实第一份CSV得到1/2；第二份CSV未确证。保持原SDK检测不变，按用户授权仅再fresh一次。

Shock不是重复停滞：实际模型已100/100达到预算；其后发布轨迹的Docker mkdir10秒超时让原评分缺失。保留原infra记录和真实停止容器后，零模型运行冻结原verifier得到2/9 FAIL，真实工作簿和脚本归档完整。此评分在明确标为派生的恢复记录中，原result/summary/双轨迹SHA均未变。控制面超时与预算耗尽须分开分析。

以上补充复用各题已完成的独立审查收据，不重新调查全部轨迹或修改候选。对应JSON列出审查位置；模型/供应商内部为何未改变策略仍无法从可见轨迹证明。
