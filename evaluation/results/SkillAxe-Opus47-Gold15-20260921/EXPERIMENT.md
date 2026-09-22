# SkillAxe / Claude Opus 4.7 / Gold 失败 15 题

复用 2026-09-19 Claude 批次的最终有效失败轨迹，在 v25 的 31 个 Gold 任务中选出 15 个失败任务、32 个 defect。16 个已通过任务不进入本轮修复或条件指标分母。

## 固定协议

- SkillAxe 修复器：OpenRouter `anthropic/claude-opus-4.7`，单轮联合诊断/修复；最多 32,768 输出 tokens，不覆盖 reasoning effort，不发送该模型未列为支持的 temperature。
- 原脚本 SYSTEM、四维提示、JSON schema 与轨迹压缩保留；轨迹首尾合计约 32,000 字符，每事件最多 3,500，verifier 尾部最多 18,000。输入 Skill 正文来自该有效轨迹，完整 bundle 来自该次 rollout 的 inputs/skills。
- 只允许修改已有、已暴露的 SKILL.md；附件和 helper 保留。API/JSON 失败最多 3 次请求，不是依据验证结果反复修复。
- fresh rollout：OpenHands / skillrepair-v1 / method-skill，统一输出上限 32,768、60 parent iterations、每 step 最多一次 text-only continuation；每题运行一次，不自动重试 rollout。独立子进程，最多 3 并发，沿用资源独占与 Docker startup 锁、固定本地 runtime archive 和已有基础设施补丁。
- Gold 裁判：`openai/gpt-5.5`、medium、temperature 省略、8,192 输出 tokens、240 秒超时；每题 diagnosis 和 repair 各一次，最多 30 请求，无自动重试。
- 用户已授权整轮计费，不设美元金额上限。基础设施错误单列，不能当作任务失败。

## 输入来源与比较范围

原始来源 ZIP 中的两个脚本保存在 source/。run_injected_skillaxe_gpt52.py 实际面向人工注错修复，不是 fresh rollout 验证器，本轮不调用。

gold.subset.json 仅供裁判，缺陷内容沿用 v25，仅筛任务和更换 original_bundle 路径。jpg-ocr-stat 缺失的原始快照使用已有 Claude 输入补齐；manufacturing 的旧 Gold 快照与 Claude 输入仅有行尾空格差异。未修改全局 Gold。日志中示例密码、连接串和 Bearer token 的脱敏仅用于输入一致性检查；修复提示仍使用原脚本从轨迹提取的正文。

历史 baseline 中六题使用 128,000 输出上限，jpg 使用 65 轮。本轮按用户指令统一为 32,768 / 60，未重跑 baseline。修复成功率是这 15 个历史失败任务上的单次失败转通过率，不能称作完全相同预算下的因果提升，也不能代替 31/87 题全量成绩。

## 运行和产物

使用 Windows 现有 OPENROUTER_API_KEY 经 WSLENV 传给 Ubuntu；密钥不写入文件。launch.sh 设置与已有 Claude 批次相同的代理和固定 runtime 环境。

- manifest.json：15 个任务、baseline rollout、正文清单和历史配置。
- protocol.json：本轮配置与用户授权范围。
- inputs/<task>/request.json：准确修复请求，不包含 Gold 标签。
- generation/<task>/：原始响应、usage、诊断、四维自评和更新文件。
- submission/submission.json 与 submission/tasks/<task>/skills/：完整正式提交；全部生成成功后写总提交。
- gold-dry-run/ 与 gold-evaluation/：提交格式检查及独立 Gold 裁判结果。
- runs/skillaxe-opus47-gold15-20260921/：fresh rollout 轨迹、产物和 verifier 结果。
- batch_state.json、batch.log、worker_logs/：运行状态和日志。

生成完成的任务可立即开始 fresh rollout；全部生成完成后自动启动 Gold 评分，与剩余 rollout 并行。重复启动会拒绝，避免意外重复计费。修复失败、评测错误或基础设施错误会保留原始证据并使最终状态为 needs_attention。

离线检查：3 项测试覆盖完整 bundle 附件保留、越界更新拒绝、截断响应拒绝；preflight-gold/ 只使用未修改 bundle 验证输入格式，不是方法分数。
