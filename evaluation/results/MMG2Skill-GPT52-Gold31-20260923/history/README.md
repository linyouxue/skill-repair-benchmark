# MMG2Skill → Skill / GPT-5.2 / Gold31

用户于 2026-09-23 确认 Q1=A、Q2–Q4 推荐方案。范围固定为冻结 Gold v25 的 31 题、57 缺陷。

方法：复用真实 GPT-5.2 original-skill 轨迹，运行原 MMG2Skill 分块 Analyzer，随后一次 Refiner、一次 fresh GPT-5.2 rollout。使用 OpenRouter，省略 reasoning effort 和 temperature。Analyzer 每块 15 个近似 ACP tool-event turn；按完整方法配置使用 32768 输出 token、32768 response/rolling-summary 字符上限。JPG fresh 65 步，其余 60，最多三个独立 worker，内存总门限 11264 MiB，重任务独占，Docker build 串行。

## 输入与接口适配

- 31/31 原始完整 bundle 均匹配历史 executor 的 SHA-256；不重新执行 original-skill。输入及任务环境已冻结，原共享 Gold 不改。
- 用户提供的 ZIP 是 25 题 diagnosis-only 入口；本目录调用其中原 Analyzer 与 Refiner，扩展至已批准的 31 题完整流程。上游 commit `c12d8b1e8998ed76bad2ab85425959f44ca085b8`。
- `include_tutorial_in_refine=false`。修正 ReviserRunner 正常路径和恢复路径中无条件 tutorial=None 退出，并让 Refiner 在禁用教程时接受 None。保留原算法和提示词；这是无教程适配，不能称为有教程的完整原论文实验。
- 复用附件 ACP 转换：一个可见 tool event 对应近似 predict-turn，不输入 agent thought/system prompt、verifier、Gold 或参考修复。
- Analyzer 只有轨迹定位，不生成 Skill 文件定位。提交的 diagnoses 保留原因、证据和轨迹位置；locations 为空，不能虚构定位命中。
- 每题只有一轮 Refiner。保留完整 bundle 的 scripts/references/其他文件，只覆盖已有对应 SKILL.md 的模型返回正文/description。保留未改变 Skill 的原字节和无关 frontmatter。
- 所有方法请求及完整响应落盘。恢复使用相同请求已成功响应；不确定的 pending 请求阻塞，禁止盲目重复付费。无效 API/解析结果不能冒充未修改 bundle。
- fresh runtime 复用已验证的固定 OpenHands runtime、精确依赖缓存、代理配置、并发启动锁；各 worker 独立进程和 cwd。缓存通过本目录 infra-cache 链接只读引用 CausalFlow 的依赖缓存。
- 尽量在 verifier 前导出真实工作目录；此导出仅用于验收/基础设施恢复，不回流方法输入。

## 验收与计分

全部可运行 worker 结束后才调用 GPT-5.5 medium Gold。冻结 v1.4 评测脚本，保留原语义分数；`finalize.py` 完全离线生成 F→P 全 Gold defect 计诊断/修复 TP、FP/FN=0 的第二版本。定位为原命中数/新 TP；其他独立裁判信息不被改写。统计前必须核验真实 verifier 和正文暴露，自动报告标注 provisional。

已知启动前阻塞：Druid 声明 24576 MiB，超过当前 WSL 15701 MiB；不修改其资源声明。AgentOps 原 py37 验收与固定依赖冲突，等待用户决定是否沿用 CausalFlow 的 py38–py312 修正矩阵。两题不得伪报完成，也不在明知不可验收时启动付费修复。

运行入口：WSL `bash launch.sh --preflight --probe`，通过后 `bash launch.sh --run`。不要再次启动已有 controller；状态见 `batch_state.json`、`task_state/`、`worker_logs/`、`generation/`、`runs/`。用户已授权本次运行；未授权自动 GitHub 发布。确认实际开始后按用户偏好结束当前交互，不另建自动监控。

2026-09-23 启动门限实测：C 盘剩约 9.2GiB，全部实验 worker 均被门限拦截；仅完成一次 22-token GPT-5.2 连接探针。已停止空派发 controller，状态为 `blocked_before_paid_experiment`，等待存储处理。没有方法调用、fresh rollout 或 Gold 调用。腾出空间后 `bash launch.sh --run --resume-prelaunch` 会先归档本次未计费的派发状态并从同一冻结输入启动；不重复探针。

2026-09-23 用户指定 Druid 复用北大服务器环境，其余题目本地先跑。控制器已将 Druid 移出本地队列，等待服务器 task_state 完成；等待期间最多两个本地 worker，Gold 等待服务器任务结束。AgentOps 协议选择仍单独等待。已回收约 47.94 GB Docker build cache 并删除 9 个非本批任务镜像；镜像层及当前实验运行依赖保留。旧源码备份到 D:/experiment-retired-code-20260923，删除源目录被自动审批拒绝，尚未删除。

2026-09-23 19:14 本地正式启动：Docker 空闲块最终回收到 C 盘，可用约 113 GiB。用户因服务器连接不稳定暂缓 Druid，本地已按原 15 GiB 磁盘门限启动；Gold 继续等待全部任务。没有降低资源/磁盘门限，没有重跑 original-skill。

2026-09-23 用户新增授权：每小时检查基础设施故障并修复后断点恢复/重新入队；全31题有效结束且验收无误后评测，保留原Gold并生成F→P全缺陷TP版本，上传GitHub。本次自动检查ID为 mmg2skill，状态ACTIVE，附当前任务；正常运行保持安静。发布目录 evaluation/results/MMG2Skill-GPT52-Gold31-20260923，使用分支+PR，遵守main人工review，成功记录publication.json后结束自动检查。此授权取代上文未授权GitHub发布的旧说明。Druid仍按用户最新指令暂缓，AgentOps矩阵待确认。

2026-09-23 19:34 共用适配恢复：原解析器将正文H1/代码注释切成Skill，现按已知名称与description封装重解析保存响应；不改prompt/模型内容、不追加Refiner。快照按真实workspace及存在目录导出，修复/root任务无/app导致tar失败；企业检索无保存产物只能复用bundle补fresh r002。PDDL真实计划解析失败不重跑。reserves方法已完成，初始镜像缺失在fresh前按冻结Dockerfile重建及离线输入/版本核验。--resume-queue接管状态，controller5902；原失败证据和恢复范围见recovery-history/20260923T113352Z-adapter-export-recovery及recovery_queue.json。实际安装日志已证实本地OpenHands，verifier代理explicit；针对性回归见recovery-checks-20260923.json。
