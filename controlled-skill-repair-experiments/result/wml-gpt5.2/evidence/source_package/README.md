# WML / GPT-5.2 / controlled experiments

本目录交付 22 条 WML 受控修复实验，33 条可跨方法复用的直接执行对照，以及 5 题按分工要求复用的历史无提示 WML 修复结果。先看 summary.json 与 selection_manifest.json；尚未完成的运行不能当成最终结果。

- skills/<trial>/：最终冻结、实际 rollout 使用的完整 WML 修后包。
- inputs/<trial>/、evidence/repair/<trial>/：隔离修复输入、WML 两阶段诊断与修复响应及用量。
- experiments/repair/<trial>/jobs/selected/<rollout>/：选定模型执行、verifier 与原始模型轨迹。
- experiments/control/<condition>/jobs/selected/<rollout>/：同配置直接执行对照，不能当成无提示 WML 修复。
- reports/score_template.csv：官方 22 行模板，保留目标修复/其他 Gold 保留的 AI 辅助复核标注；任务 pass/fail 不能替代语义评分。
- unhinted-reuse/zenmux-gpt5.2/<task>/：5 题已发布的历史无提示结果，保留原模型、端点、预算和轨迹；与 Tatumass 受控结果分开列示。
- unhinted-reuse/tatumass-gpt5.2-validation/dialogue-parser/：用户授权的冻结历史 Skill 补充执行验证；原 Zenmux 末尾异常仍保留，不改写为正常运行。
- evidence/environment-acceptance/、evidence/verifier-compatibility/：本轮参考验收、用户授权的 D3 SVG 兼容差异。D3 v1 与原 verifier 分数分开记录，任务、Gold 和输入未改。

历史所有尝试仍保留在 source work 目录及审计目录；selection_manifest.json 提供旧/新 attempt 和原文件路径。此整理不覆盖原记录，不从模型文字或评分 JSON 重建产物。历史归档不足和运行末尾的异常均如实披露在审计文件中。未声称这是独立人工复核。

无提示历史配置为 Zenmux GPT-5.2，受控配置为 Tatumass GPT-5.2，按分工复用，但不是严格同端点配对实验，不合并计算同配置修复收益。完整运行轨迹导出后见 trajectory_timelines/。
