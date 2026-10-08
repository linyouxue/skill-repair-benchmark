# Gemini与OpenHands接口、重复操作及预算

现有结果支持工具接口摩擦和停滞检测影响了运行，不能单凭提高预算后仍FAIL判断Gemini纯粹能力不足，也不能认定整个Gemini协议不受支持。

|本次复跑|实际parent|终端拒绝多命令的事件数|事件数/parent|
|---|---:|---:|---:|
|Flink|68|2|2.9%|
|RaR|200|33|16.5%|
|Seismic|9|1|11.1%|
|Shock|200|55|27.5%|
|Enterprise|100|19|19.0%|

计数对应规范ACP中包含 `Cannot execute multiple commands at once.` 的工具事件；具体行号与源文件见 [HARNESS_ANALYSIS.json](HARNESS_ANALYSIS.json)。比例的分母是parent轮数，不是所有工具调用数。这些拒绝消耗轮数，但没有对应的反事实运行证明消除它们后会PASS。

模型可生成被正确解析的函数调用，而命令内容仍违反终端“一次一个命令”的约束。例如分行发送下载/读取，或heredoc写文件后再换行执行脚本。终端会拒绝这种形态，属于模型生成习惯与工具语义的摩擦；它不等同于provider持续400、JSON无法解析或全部工具不能执行。Flink最终成功编译并运行作业，Enterprise实际交付answer.json，说明有效执行路径也存在。

重复操作有不同机制。源100轮Flink连续四个独立模型响应重复已成功的同一文件写入；源Enterprise连续运行将Slack列表当dict的错误脚本。已保存的工具反馈按正确call ID进入后续请求，可见证据支持模型再次生成同样动作，未显示执行器重放或反馈丢失。Scala尾部忙终端与缺少必需command的reset交替，虽然触发stuck，官方代码测试已经10/10 PASS。证据与固定SDK实现依据见 [源100轮重复操作调查](../budget100-20261007/evidence/stuck-root-cause-20261007.md)。

Seismic此次9轮结束，其中父6–9都是合法空command/is_input等待，30秒内无新输出且“仍在运行”的反馈正确传给下一请求。SDK将四次相同动作/结果判为stuck，合法等待可能被提前截断。这是接口/停止策略的归因限制，不能把它等同于无效命令循环。实际提交CSV得0/2；停止后的反事实结果未知，见 [Seismic独立审查](evidence/seismic-r001-health-mechanism-20261007.json)。

提高parent上限不会改变一次一个命令的约束，也不会关闭SDK的4次同动作/结果与6步交替模式检测。RaR200仍有1314个公式无非空cache并有error cell；Shock200最终5表0公式；Enterprise在parent73写答案后继续检索至100且未更新答案。任务内容、产物交付与验证行为也贡献了失败，因此全部轮数耗尽不能用一个适配原因概括。

这些是同候选fresh路径的观测，不是对预算、工具接口和模型能力分别控制的实验；没有与Claude/GPT在匹配条件下的工具拒绝率比较。当前可以定位可见调用和反馈问题，不能据此判定“纯模型能力不足”或“三模型缺陷一致”。[60→100→复跑比较](evidence/summary-60-100-followup-20261007.md)保留评分、停止原因和不同产物路径。
