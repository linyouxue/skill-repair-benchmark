# SkillTTA GPT-5.2：22 条控制条件 + 5 条无提示复用对照

本目录包含完整修后 Skill、方法诊断与两轮迭代材料、原始尝试、补跑、轨迹和评分证据。模型补跑队列已结束；有效结果、无有效结果及证据缺口分别登记，当前不是“27 条全部严格有效”的声明。本包范围是22条修复条件和5条复用对照；audit中的Controlled55中间报告属于更大的背景范围，不能替代本包状态。查看 PACKAGE_STATUS.json 和 controlled22_results.csv。

- 22 条控制条件：5 个位置提示、12 个留一单点修复、5 个全缺陷修复。模型 gpt-5.2@AZUREOPENAI-default，端点 https://maas.tatucloud.com/deployer/coding_tatu/v1，OpenHands，high；冻结 Skill 与原预算不变。
- 5 条无提示对照：按组会清单复用 GitHub SkillTTA-GPT52-Gold31-Local30-20260924 的同名原题方法修复结果。模型 openrouter/openai/gpt-5.2，端点 OpenRouter，60 iterations；历史方法为 SkillTTA + repair adapter（一次修复），与本轮两轮修复、端点/预算及结束保障存在差异，详见 no_hint_controls/audit.json，不能宣称精确同配置比较。
- 原始奖励均未改动。旧 EXECUTION_AUDIT.json 和 runner outcome.valid 作为原始记录保留，其中的初步/旧有效性声明不代表本次审计接纳；以 controlled22_results.csv 和任务 audit.json 的严格门槛为准。submission.json 中未获证条目的 executor_run_id/adopted_reward 为 null，历史执行标识另外保存。未获证或基础设施无效不计作模型有效失败。
- tasks/<trial>/repaired_skill 是原方法最终候选；attempts 保留已读取的原始运行和新 attempt；artifact_snapshots 是只读复制的真实产物，没有人工补建或修复。
- no_hint_controls/<task>/ 保存历史原包执行、修后执行、方法材料及完整修后 Skill；Git blob 和 SHA256 下载证据在 source_metadata。
- audit/reference_acceptance 保存官方参考解法的环境验收命令、退出、日志、奖励和哈希；8 个任务、11 组资源一致参考验收均通过。此结论不自动证明每个模型运行有效。
- COPY_PROVENANCE.json 列出来源与字节哈希；无法读取的旧 iCloud 文件另列，不伪造恢复。MANIFEST_SHA256.json 在正式打包时生成。

任务通过率不等于目标缺陷修复率。condition_review 是离线文本/Gold原子保留证据，不是额外执行的语义诊断评分；没有将任务奖励替代诊断TP或修复语义分数。

这是 AI 辅助审计，不是独立人工复核。原任务、输入、Gold、verifier、评分逻辑和模型输出没有因整理而修改。最终待办及当前统计以 PACKAGE_STATUS.json 为准。
