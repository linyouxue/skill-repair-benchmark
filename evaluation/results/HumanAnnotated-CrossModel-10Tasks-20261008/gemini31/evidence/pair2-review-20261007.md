# 第二批修复前证据对照

第一批已经按 pair1-closure-20261007.md 收束；本批只处理 flink-query 与 reserves-at-risk-calc。十题官方原版均有效结束，官方原版不重跑。本记录为候选审核，不是 Gemini 缺陷标注/Gold；最终 model_sensitivity 只用于证据支持的 defect。

## flink-query

Gemini 原版 flink-query-gemini31-original-r001：60 parent、62 provider、max_iterations、reward0，官方 Maven 与 Flink 运行通过，精确输出失败（missing0、extra675）。健康审计见 flink-health-20261006.json。真实预 verifier tar 含六份 Java/config 文件；未含 out.txt，不从轨迹重建运行输出。

ACP 36 已成功提取并读取公开 format.pdf，必要枚举信息可见。此前 PDF 安装/权限尝试花费许多步骤，但最终恢复，不能把内容失败当作必要输入全程不可用。

ACP 45 将 finished 解读成 FAIL/FINISH/KILL/LOST；ACP 50 写入 job event 3/4/5/6 filter，并对空 max state 默认0后输出。ACP 52 又为任务活动及结束事件注册 Long.MAX_VALUE-1 的兜底 timer，onTimer 只检查尚未输出，未检查真正完成或有 qualifying aggregate。实际 tar 中上述代码保留：即使没有收到符合任务定义的完成事件，流结束也会输出；仅有生命周期事件、无任务活动的 key 还会被合成零行。ACP 54 自己承认兜底会输出所有有任务但未完成的作业，并仍认为合理。

GPT 原版 flink-query-original-skill-v11x-20260903-r002 的 ACP 34 将原先 FINISH filter 扩为 FINISH || KILL，最终 missing0、extra313；其原始轨迹及旧诊断中的空 aggregate→0 与无条件 emit 相互印证。Claude 原版 flink-query-opus47-original-skill-r001 的 ACP 17/26 将 finished 解读为任意 terminal，ACP 29 实现 FINISH/FAIL/KILL/LOST，ACP 43 的 Python reference 沿用同一错误集合；官方 missing0、extra258。

因此三模型的结束事件语义扩大有共同原始证据。空活动合成零行在 GPT/Gemini 有证据，Claude 当前证据没有同类失败；Gemini 的不检查完成条件的流结束兜底又是单独机制。不能把三种现象都统称为同一个跨模型缺陷。

原 senior-data-engineer Skill 有通用窗口、数据质量、scaffolding 及监控步骤，正文没有把业务词映射到文档枚举、对每条输出路径逐一检查输出资格，以及独立正反例验证的具体门槛。公开 task/PDF 提供业务定义；候选属于可复用语义契约/验证指导，兼有 agent_semantic_misinterpretation，不能声称原 Skill 错误是唯一原因。

本题候选完整复制 Gemini 原版 snapshot，只在 senior-data-engineer/SKILL.md 正文起始加入一个短门槛：由公开契约分别定义 contributing、completion、output eligibility；相邻终止状态不自动等同；每条普通/timer/流末输出路径都必须满足同一资格，null aggregate 不合成零行；执行正例和相邻状态/无活动/未完成的反例；参考程序从公开契约独立定义，不能复制待验证谓词。不给出本题枚举数字、job ID、行数、计数、隐藏期望或实现答案；PDF Skill、脚本、原任务与 verifier 原样保留。

## reserves-at-risk-calc

Gemini 原版 reserves-at-risk-calc-gemini31-original-r001：8 parent/provider 后 stuck、reward0。ACP 8 猜测 PCOMM.ashx URL，得到167字节429 JSON，ACP 9–12 连续四次 cat 同一个文件。模型没有创建工作簿，真实 pre-verifier tar 为空；官方五项都因 rar_result.xlsx 缺失失败。健康审计见 reserves-health-20261006.json。

task 要求从 commodity-prices 官方入口下载数据库，没有要求模型猜测的 PCOMM.ashx。先前零模型依赖检查发现入口及实际链接的 Excel 可访问（reserves-network-check-20261006.json）。这不证明原轮每一瞬间的历史网络状况，但单一猜测 URL 的429不足以认定任务全部必要来源不可达。当前是错误下载选择后的不变动作循环，没有进入 Excel 计算。

GPT 原版 reserves-at-risk-calc-original-skill-v11x-20260903-r001 的 ACP 22 已创建工作簿，实体集合不完整，并通过 annualized 波动率再乘 SQRT(3/12) 引入三个月预测期限。Claude 原版 reserves-at-risk-calc-opus47-original-skill-r001 的 ACP 10–13 曾从无效猜测下载恢复为访问官方入口、提取链接并成功获取真实 Excel；ACP 20/25 则把估计窗口当成预测期限，加入 SQRT(3)，最终原版3/5。两者实际进入计算；Gemini 原版未进入，不能继承其实体/期限/百分比 defect，模型敏感性对此只能保持证据不足。

本题候选不导入旧 Gold 的国家、期限缩放、置信系数或参考值。只对当前首错做一个可复用的外部工作簿输入步骤：从任务给定官方入口提取真实链接；检查响应状态、实际文件类型及可解析的 sheet/header，禁止把 HTML/JSON 错误当作工作簿；读取一次错误后改变有证据的操作，不连续重复同一文件读取；若所有允许官方路径确实失败，明确记录依赖障碍，禁止编造数据。数据可用后继续原有模板、Excel 公式及重算验收步骤。没有硬编码本题正确下载链接、输出数据或评分约定。

原 xlsx Skill 有读取/公式/重算规则及来源标注，缺少外部下载内容验证与错误恢复具体流程。候选是 acquisition_validation_guidance，同时保留模型 stuck 行为责任；此次 fresh 验证不能倒推原版已经暴露计算语义缺陷。

## 本批启动与验收范围

候选均从各自 Gemini 原版 inputs/skills 复制完整 bundle，保持原结构，仅各改一个 SKILL.md，差异及 rationale 存本题 round-1。继续既有 run_original.py/start_repair.py/launch_original.sh --repair、冻结 task digest、固定 runtime、Gemini3.1Pro、60 parent、32768 输出、默认 reasoning_effort、一次共享预算 continuation。无新 provider 探针，无其他模型/Judge；两题至多两个活动 rollout、共享启动锁、独立网络镜像状态及 Linux cwd，保护另一 Claude 流程。资源门按用户最新指令忽略。

本批有待 fresh 验证，没有 F→P、没有 Gemini Gold、没有最终 model_sensitivity。每个结束结果须核对真实原产物、正文暴露与原生调用、canonical reward/测试、轨迹完整与因果；对已有明确指导的忽略不能无限补提醒重跑。正常活动确认后结束扫描，由30分钟巡检接续。

## 00:42 派发记录

两份候选的独立健康门已通过（pair2-candidate-health-20261007.json），无必须在启动前修正项。复用既有入口派发 flink-query-gemini31-manual-round-1-r001（PID73951）与 reserves-at-risk-calc-gemini31-manual-round-1-r001（PID73990）；本地冻结 task digest、完整 bundle 差异及既有 runtime archive 检查均通过，没有新增付费 provider 探针。

真实进程命令及各自启动日志已确认；两者均打开共享 Docker 启动锁，正等待另一 Claude 的 latex-formula-extraction 构建（PID73692 持锁、compose73754/buildx73812）。当前未确认 Gemini 自身 build/container/provider 开始，不能把“派发”当成模型已运行；也不能因容器为空重启或重复派发。仅保持既有锁排队，没有操作其他 Claude 流程。详细快照见 pair2-repair-startup-evidence-20261007.json。

本次结束扫描；下一次按 comparison-state 的两项 active_repair_rollouts 接续实际活动或终态，不填第三题、不重跑已结束原版。

## 01:07–01:37 基础设施中断记录

首轮两题r001均在compose build返回-11，ACP为空且无LLM/评分/真实产物，已由pair2-infra-health-20261007.json隔离。01:29仅用既有DockerSafeStart入口恢复无存活引擎；候选不改，以r002明确替代无效启动。r002已派发，但尚未确认自身build/container/provider，01:34外部进程执行Docker desktop stop、WSL shutdown和Docker VHD离线压缩，两份PID消失，仅留下inputs/config，summary未写出。没有可判定的模型结果，reward/provider/费用均null，不伪造canonical，不计Skill FAIL/F→P/Gold。

实际CLI /app/quit与VM explicit Stop()日志、Win32_Process维护命令和压缩完成收据见pair2-r002-interruption-evidence-20261007.json；压缩01:37完成。该证据解释此次r002中断，不能倒推先前r001 -11的来源或断言资源/OOM。当前基础设施恢复前不重复派发；保留同一候选与两题屏障，待外部维护结束且引擎/集成恢复后有限接续。没有修改或停止另一Claude流程。

## 01:40 同候选恢复派发

外部离线压缩已完成，Docker进程01:38恢复，实际Docker info/WSL集成正常。已有基础设施根因与恢复新证据后，复用既有入口以同一候选明确派发两题r003，未做付费provider探针。Flink PID1475、RaR PID1540实际命令正确且均打开共享启动锁；Claude latex恢复构建PID1109持锁、真实compose1367/buildx1429活动，Gemini正常等待，尚未确认自身build/container/provider。详见pair2-r003-startup-evidence-20261007.json。结束本次有限扫描，下一次只接续实际r003活动/终态，不重复派发；候选、评分、原10题与Gold均不变。
