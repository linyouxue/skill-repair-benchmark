# MMG2Skill / Claude Opus 4.7 Gold15

15题/32缺陷已完成验收及语义评测：2 PASS、13 FAIL，实际通过率13.33%。原语义与F→P全缺陷TP替代版本均保留。

本次仅整理并发布已有结果，模型/裁判新增调用均为0。MMG原Analyzer分块15、一次Refiner、include_tutorial_in_refine=false，32768限制；复用历史original-skill轨迹，不重跑基线。固定本地OpenHands，fresh60步/JPG65步。两个模型的响应和评分独立保存。

- [任务、基线、bundle、有效run索引](task-index.json)
- [完整方法提交](submission.json)：31/15题完整Skill bundle，包含所有支持文件。
- [真实执行结果注册表](executor-results.json)，原始和历史失败run均保留，选择有效结果以索引为准。
- [完整最终报告](final-review/REPORT.md)，[原语义评分](final-review/original-semantic-summary.json)，[F→P全缺陷TP版本](final-review/outcome-adjusted-summary.json)。
- `trajectory_timelines/` 是仓库export_trajectory.py生成的完整before/after可读轨迹；原始轨迹保留。
- `generation/` 保存真实方法请求/响应与adapter；`runs/` 保存fresh结果/验收；`tasks/*/original_run/` 为复用的原始运行。
- [大文件下载和校验清单](large-files.json)：工作区快照不裁剪、不从轨迹重建，大文件保存在同仓库GitHub附件中。

## 恢复与离线复算

在本目录执行 `python restore_files.py` 解压压缩文本；加 `--download-assets` 下载并校验完整工作区快照。若无需工作区本体，所有报告/语义评分可直接读取。

执行 `python recompute_scores.py` 使用已保存的30个裁判响应重新计算原语义评分和F→P替代指标，无API调用。

## 协议偏离和证据限制

- AgentOps按用户授权修正为py38–py312矩阵，原断言/依赖pins保持。GPT选用真实snapshot的verifier-only派生验收结果，原超时r001保留；不能据raw r001覆盖有效派生结果。Claude为有效timestamp断言失败。
- GPT manufacturing允许且仅执行过一次额外Analyzer重试，旧不完整响应及授权记录保留；此例外未套用Claude。
- Druid远端GPT首请求被OpenRouter地区访问门限403拒绝，无成功模型响应或正式verifier；`remote-evidence/`保留真实失败，不能算有效模型FAIL。
- Shock题面的Excel/Playwright/Solver能力与基础harness不完全匹配；结构健康不等于环境完全满足要求。
- Claude Python→Scala原轨迹输入采用已授权重建副本，误脱敏/重建限制在独立审计中保留；Flink/PDDL等其他限制见完整报告。
- n_skill_invocations与正文预加载证据分别保留在真实result和审计中。fresh通过不等于语义Gold内容修复成功。

`history/`为原本地配置/脚本快照，保留历史绝对路径；直接复算请用本目录便携入口，不执行旧launch脚本。
