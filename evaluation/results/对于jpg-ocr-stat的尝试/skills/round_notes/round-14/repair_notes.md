# jpg-ocr-stat Round 14

日期：2026-10-08。

用户明确要求以其提供的七条修复要求替换此前人工添加的 guidance，并用 GPT-5.2 验证一次。本轮不叠加 Round 1–13 的 gate，也不覆盖历史候选或结果。

本轮从官方完整 Skill bundle 复制，仅在 `image-ocr/SKILL.md` frontmatter 后增加英文“Structured Receipt Field Extraction and Delivery”。官方正文和其他 Skill、支持文件保持不变。七条要求按用户提供的内容忠实译成英文，涵盖字段证据、最终应付语义、保守解析、局部复核、稳定结果、增量保存和实际交付物核验；删除额外引导句，不要求固定 OCR 投票次数，不含具体样本答案。

待验证的问题：此前候选与轨迹存在跨字段混合候选、弱数字/日期回退、疑点处理与已确认字段不隔离，以及日志/checkpoint 与最终写盘成果脱节的风险。本轮观察用户提供的精简合同能否使模型完成精确抽取与交付，不预先认定为模型能力或 verifier 问题。

英文版运行：`jpg-ocr-stat-round-14-r002`；模型 `openrouter/openai/gpt-5.2`；reasoning effort 沿用此前配置（不显式设置）；60 parent iterations；completion guard 开启，text-only continuation 最多 1 次且共享 iteration budget；单次 fresh rollout。官方 task/verifier 不修改。

基础设施复用已有执行器、同 commit OpenHands 本地 runtime archive，并为 runner、task、OpenHands/依赖、verifier 与构建依赖注入现有代理。不得写入具体 API key。英文版结果与轨迹归档到本任务 `runs/manual-annotation/jpg-ocr-stat-round-14-r002/`。

状态：2026-10-08 20:22 已启动 `jpg-ocr-stat-round-14-r001`，确认对应 Docker Compose build / buildx 进程实际运行，构建命令包含 HTTP/HTTPS 代理参数；启动检查时尚在构建，不声称模型已获得响应。启动后按用户偏好停止监控，等待用户通知结束。不能据此更新为正式通过。

用户随后纠正 Skill 须为英文，并要求删除额外引导句。核查时 `r001` 已自行结束：镜像构建成功，但 Docker 网络地址池耗尽（`all predefined address pools have been fully subnetted`）使 task container 无法启动；ACP trajectory 为 0 字节，没有进入模型执行。不是人为成功停止，也不是模型/Skill 失败。中文输入快照保留，不改写。修复该基础设施阻塞后，按用户纠正后的英文 Skill 启动 `r002`；结果待验证。

已核实并仅删除本任务无容器引用的旧网络 `jpg-ocr-stat-opus47-manual-round-2-r001_default`；该旧 Compose project 也没有任何停止或运行容器。未删镜像/卷/文件，未全局 prune。`r002` 已复用构建好的任务镜像并启动 `jpg-ocr-stat-round-14-r002-main-1`；运行输入快照确认为英文七条要求，官方正文保留，额外引导句已删除。确认容器启动后停止监控。

## 英文版 r002 结果

2026-10-08 用户通知结束后核查：reward 0，execution_ok=true，官方 `::test_outputs`
0/1，失败于逐行内容相等断言 `row_a == row_e`；18/60 iterations，18 次正常 provider
响应，17 次工具调用，577.8 秒，$0.5635525。确定性轨迹 validator 为 healthy，5 个
Skill 全文 preload 已核实。guard 未触发续跑；模型最终调用 `finish`。

模型已生成并重开 Excel，不是极短异常停工；但实际脚本仍按整页小数证据补金额
小数位、按最后数字/下一行选择金额、按月份取余修正日期，且三次全批重算而未
落实字段证据及增量缓存。因此本轮为有效失败、`agent_did_not_follow`，不证明
verifier 错误或模型一定不能解决。具体证据见本任务 `annotation.md` 的 Round 14
验收节；没有读取/展示隐藏期望字段用于修补，也未自动发起下一轮。

交付物有执行/重开打印证据，但 `artifacts/` 没有真实工作簿导出，且容器已清理，
无法独立 verifier replay；输入与轨迹证据保留，不把打印重建为原始产物。
