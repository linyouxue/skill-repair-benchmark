# CausalFlow → Skill / Claude Opus 4.7

用户于2026-09-22确认：复用SkillAxe同一15题、32个Gold defect的Claude原始失败轨迹，原始baseline不重新生成。保留CausalFlow严格双重重放、每命令1次干预、每因果步骤3候选、full-trace/full-success。随后单次Skill转写，完整bundle与submission，再一次Claude fresh rollout。全部worker结束后才启动GPT-5.5 medium Gold评测。

这是一种明确新增Skill转写阶段的适配方法。原CausalFlow只修复行动命令，不能声称原包本身就输出Skill修复。内部输出token上限由2048提高到已批准的32768；任务rollout使用32768/60 iterations，方法与验证最高3并发并共用资源门限。不设金额上限。

## 源码兼容改动

- llm_client.py：Opus4.7省略temperature；记录每次完成的调用计数。
- skillsbench_replay/atif.py：支持已有Chat Completions轨迹，保留原tool-call ID及精确arguments；原Responses解析保留。
- full wrapper：记录反事实重放完成事件，便于只读监控。
- 2026-09-22 用户要求补齐 flink-query：将有明确前置软超时及最终退出码的 terminal 空等待关联到前一条命令，保留原始参数与输出；该 Maven 命令按原300秒命令＋300秒等待允许同步运行600秒，其他命令维持120秒。审计、方法baseline及反事实分支共同使用此映射；未匹配等待仍拒绝。支持原轨迹带图标的 Exit code 输出，继续严格检查退出码。原baseline不重新调用模型。
- task.md资源兼容：sandbox缺失时读取environment中的原cpus/memory_mb；不改变资源限制。4项等待/资源/真实轨迹测试与3项已有适配测试通过。预检现为344条命令、1个已关联等待，无缺失参数；原预检保留在compatibility-fix-before。flink-query仍须通过运行时双重重放，才能进入付费修复阶段。
- 其余原方法逻辑保留；原ZIP未改动。包内共享执行器不用于fresh rollout，统一复用上一轮本地固定OpenHands运行时及已验证执行器。

## 异常与结果解释

严格重放不一致时停止该题，不做付费因果归因；不会将其判为模型FAIL。内部生成不完整时停止Skill转写，不把API错误冒充无因果发现。完整方法得到零因果步骤时，保留原bundle并输出空诊断，记no_causal_steps。

Gold仅评分具有完整submission的任务，所有缺项在batch_state.json列出；不能把缺项从总体15题里隐藏。真实执行PASS/FAIL/INFRA_ERROR/NOT_RUN与Gold内容评分分开。最终完整报告包含P/R/F1、定位、回归、置信度、调用统计，并另附F→P全TP敏感性统计。

## 运行

launch.sh --prepare只冻结输入；--preflight为免费检查；--run启动单一后台批次。文件锁和已有batch_state检查防止重复批次。每题单独Python进程、独立cwd。build串行，内部重放与fresh rollout共同受资源门限管理。监控不得隐式重新运行任何题或追加付费尝试。

## 2026-09-22 用户授权停止修复后恢复

旧批次尚未进入模型阶段，5题先后因资源字段或重放日志权限错误退出，其余停在构建/排队；已终止旧controller及其worker、构建进程。保留所有历史证据于recovery-history，使用`--resume-pre-model`恢复15题；该入口只允许所有任务均未进入模型阶段且无method/generation/runs/Gold产物时执行，并验证无残留实验进程。已有原始轨迹及构建缓存复用。

重放容器退出时恢复临时日志的宿主UID/GID；强杀时使用无网络、仅挂载本次日志目录的清理容器恢复。实际命令仍为非root，verifier仍为root且其两处入口均不允许agent读取。正常、verifier失败、整容器超时3项Docker测试通过。

模型实测记录见model-preflight-20260922.json：方法intervention和Skill adapter完整schema均由Opus4.7真实返回stop并通过结构验证，合计1601 tokens、$0.011325。探针只用toy数据，输出上限1024；正式实验仍为32768。这些探针不计入实验修复结果，也不代表未来请求不会遭遇网络或限流错误。

## 2026-09-22 两题基础设施恢复

用户另行授权修复并重排 reserves-at-risk-calc、seismic-phase-picking；二者均未进入方法模型调用。旧失败证据单独归档，其他已完成结果和活worker保留。`--resume-queue --retry-task <id>`仅允许指定的模型调用前失败任务，接管现有worker并计入同一资源门限，只派发pending任务，禁止因接管竞态重复付费阶段。

- reserves：TUNA直连下载失败。镜像源、依赖及版本保留，构建显式传大小写代理参数，移除该worker的外部NO_PROXY豁免；fresh rollout的临时Dockerfile使用同一代理路径，不写回原task。隔离Ubuntu24.04容器成功下载32.8 MB索引及ca-certificates包；两项本地网络配置测试通过。
- seismic：第二次verifier的uv安装器TLS下载失败。只在verifier阶段挂载并核验本地uv/uvx 0.9.7，精确替代原安装器下载；原test.sh、pytest/pandas版本和判分均保留，严格双重重放仍须通过。三个无模型测试通过，含真实任务镜像断网测试及agent/verifier隔离检查。

本轮未重排后来出现错误的data-to-d3（镜像站连接失败）及python-scala-translation（脱敏文本破坏重放Scala源码，另有verifier下载失败）；不得把它们计为有效模型FAIL。恢复不重跑original-skill模型轨迹，也不追加已完成修复的尝试。

## 2026-09-22 后续基础设施修复

用户再次授权修复基础设施并将受影响任务加入原队列。17:31已归档并重排data-to-d3、dynamic-object-aware-egomotion、fix-build-agentops、jpg-ocr-stat，旧证据在recovery-history/20260922T093120Z-infra-retry。接管保留仍活跃worker，最多3个任务共用原资源门限；未重跑任何已完成付费结果。

- data-to-d3复用APT代理修复，并从本次精确失败容器保留已完整下载的179MB依赖包；临时构建配置有界重试、超时和禁用HTTP pipeline，APT仍验证索引及包完整性，原包名和版本不改。
- verifier仅在原脚本精确请求uv0.9.7时使用同版本缓存；保留测试源文件、agent/verifier隔离与严格双重重放。
- fix-build-agentops构建固定使用官方uv/uvx0.9.22缓存，官方SHA256核验及真实基础镜像断网安装验证通过。replay预构建与fresh rollout临时构建上下文均使用同一替换，原task未改。
- flink-query的原pom对应Maven缓存已完成：官方Central依赖和插件2356个文件、154,213,618字节，依赖tar为140,794,060字节。离线-o检查以及原Maven命令不额外传-s/-o的独立禁网容器检查均通过；证据见infra-cache/maven/flink-query/ready.json。缓存不含任务源码、输出、答案或settings。每次重放复制独立可写仓库，宿主缓存只读挂载；fresh rollout也复制相同依赖。
- verifier阶段补齐正式BenchFlow已有的/tests别名和task.md中verifier.env；真实镜像断网检查确认agent仍不能读取verifier，环境变量仅在verifier阶段导出。
- reserves-at-risk-calc原有25条可执行命令曾被task_tracker的两条title_fallback打乱预期退出码。审计、方法trace及反事实统一筛选kind=execute，保留原命令顺序及历史非零退出码；4项回归通过，已完成任务的方法输入不受影响。
- 模型参数、原始轨迹命令、600秒Maven命令＋等待预算、每步干预和候选数量均保持原设置；网络或适配失败不记作模型FAIL。

18:04再次归档data-to-d3、fix-build-agentops及reserves-at-risk-calc的模型调用前失败并重排，证据见recovery-history/20260922T100427Z-infra-retry。18:14 Maven检查完成后，flink-query也已加入pending队列。控制器接管保留dynamic-object-aware-egomotion、jpg-ocr-stat及manufacturing-equipment-maintenance的原worker，三者真实任务容器已核验；空出资源后自动派发待运行任务。

截至18:14，python-scala-translation因原始tool-call及历史副本脱敏损坏、seismic因权重下载失败、paper-anonymizer因两次重放产物manifest不同而阻塞；均不属于有效模型FAIL。后续恢复如下。

## 2026-09-22 18:35 三题恢复

用户明确要求修复上述三题并入队，另确认Python→Scala“重建轨迹，不单独报告”。三题已重新加入原队列，旧失败证据在recovery-history/20260922T103519Z-infra-retry。接管保留reserves、dynamic及jpg的现有worker，资源空出后自动派发，未中断已有付费阶段。

- python-scala-translation：原轨迹把普通Scala token标识符误脱敏，无法无损恢复。经用户批准，仅在副本的9个file-editor参数字段中补回15处代码片段；原始无效插值、重载等模型错误不提前修正，17条命令顺序及原退出码要求保留。原日志不改，副本在reconstructed-inputs/python-scala-translation，input-provenance.json记录逐项重建。重建后原轨迹自带的最终编译与自测在断网容器通过。另从原镜像scala/scalac启动器提取6个依赖JAR（Scala 2.13.12等），非root默认编译及运行断网验证通过，重放与fresh rollout均使用独立HOME缓存。同一批次及汇总计数，不另出重建版报告，但保留该题输入来源备注，不能描述为无损原轨迹。
- seismic-phase-picking：Windows curl可从原官方地址完整下载，WSL/OpenSSL通路仍出现TLS EOF。缓存PhaseNet scedc/stead与EQTransformer scedc的v2元数据和权重；官方目录列出的最后修改时间为2023-03-30，下载长度逐项校验。相同镜像、禁网、默认from_pretrained调用均成功。仅依赖权重进入只读archive，各分支和fresh rollout复制独立缓存；无任务数据或答案。历史原始权重字节未导出，正式两次重放仍须匹配原测试和退出码。
- paper-anonymizer：原方法用的PDF库每次save会随机更新trailer中第二个/ID。用原轨迹最终脚本离线生成三份PDF各两次，证明全文件仅该字段不同。语义manifest只归一化未加密、普通trailer的第二个32位十六进制ID；第一个ID、正文、元数据、对象流、交叉引用等字节仍参与比较，其他PDF保持原字节摘要。修改作者元数据仍被检测，未修改原PDF、生成脚本、verifier或判分。

两个依赖缓存的就绪证据分别在infra-cache/<task_id>/ready.json；PDF验证见infra-cache/paper-id/verified.json。fresh运行器缓存激活/失败关闭测试通过，15题344命令离线预检已更新。Gold仍等待全部worker结束，严格双重重放没有取消。

## 2026-09-22 22:58 fresh 基础设施恢复与预算更正

用户授权修复基础设施错误后继续排队，并明确 jpg-ocr-stat 的 parent iteration 预算为65。该题后续独立 fresh worker 同步设置 protocol/result/ACP 三模块为65；正在运行的原方法 worker 不重启，其后续动态加载 SkillAxe runtime 时同样获得已核对的65配置。历史运行记录不追改。

reserves-at-risk-calc 的方法和修复 bundle 已完成，但 fresh r001 在模型调用前因 APT 代理连接失败终止。现保留方法、bundle 与 r001，只恢复 fresh 阶段。复用同原任务 Dockerfile 构建的不可变初始镜像 sha256:c596e89fa54d3d42f7f7023463fd1ccd468b4ebe7e966837a9cced0795a891a3，禁网验证输入 Excel 与源文件 SHA 一致、/root/output 和 /app 无输出、五个 Python 包均为原精确版本，证据在 infra-cache/reserves-at-risk-calc/prebuilt-image.json。它不是重放容器快照，不携带模型答案。r002 暴露 DockerSandbox 还缓存了一份 prebuilt image 环境变量，亦在模型调用前失败；已补齐两处镜像字段并保留 r002，排队 r003。原资源门限不变，控制器接管保留其他现有 worker。

recover_fresh_tasks.sh 仅接纳零模型请求的 Docker 启动错误，并只执行 fresh_rollout；原方法/适配不会再调用。其他方法前基础设施恢复仍使用 recover_infrastructure_tasks.sh。verify_fresh_recovery.py 检查不可变镜像、两处 prebuilt 字段同步以及 fresh 恢复分支不触发方法/适配调用。Gold仍等待所有worker结束。

后续 r003 在容器启动后被原 skill_deployment_missing 检查正确阻断，仍无模型调用：临时 Dockerfile 标记 bundle 已经 COPY，但初始预构建镜像实际不带 /skills。现仅对该任务显式上传运行器冻结的完整 skills_dir，然后仍执行原部署及正文指纹检查；preflight_reserves_bootstrap.py 在真实禁网容器验证部署和全部3文件字节。执行器清理删除旧镜像后，原依赖/输入缓存层 sha256:9f5e96b30fac586466e2c48d4553e8a2403fcd1f70b711a18262a5ddc422aeb6 原样复用，仅最后 Python 可用性 no-op 层重建，现使用的新完整镜像ID记于 prebuilt-image.json。r003 保留，继续排 r004 fresh；此恢复入口明确允许已证实的零请求部署基础设施故障。
