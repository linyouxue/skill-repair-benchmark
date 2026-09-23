# SkillsBench 重放模块

这个包把共享执行器生成的轨迹转换成 CausalFlow 可使用的命令与资源依赖。

| 文件 | 作用 |
| --- | --- |
| `atif.py` | 读取 ATIF 轨迹和官方 reward |
| `schema.py` | 定义命令、文件事件和重放结果的数据结构 |
| `snapshot.py` | 记录运行前后文件快照与写入变化 |
| `shell_io.py` | 从 shell 命令中保守推断文件读写 |
| `graph.py` | 建立任务文件、Skill、命令和 verifier 之间的依赖 |
| `planner.py` | 选择完整重放或安全的局部重放范围 |
| `container_replay_driver.py` | 在 Docker 中执行记录命令并收集结果 |
| `semantic.py` | 添加模型判断的语义依赖，正式实验需单独标记 |
| `openrouter_acp_agent.py` | 早期轻量 agent 适配和资源事件记录，当前统一任务执行优先使用共享执行器 |

当前人工缺陷实验通过 `repro_wrappers/audit_shared_executor_replay.py` 和 `run_skillsbench_full_causalflow.py` 使用本包。
