# 适配与来源记录

## 源码来源

- CausalFlow：来自本机 `CausalFlow-main` 当前工作副本；该目录没有 Git 元数据，无法提供统一 commit。
- 共享执行器：`linyouxue/skill-repair-benchmark` commit `b88b4b9482d08ad91d01058ecade523d753c086f`。
- 模型路由：与组内 Opus 4.7 结果使用的 `openrouter/anthropic/claude-opus-4.7` 对齐。

## 交付包内的改动

1. `scripts/run_experiment.py` 将 original-skill、完整 CausalFlow 和局部修复入口统一到一个配置文件。
2. `run_unified_skillsbench_task.py` 删除个人绝对路径，并把默认 rollout 模型改为 Claude Opus 4.7。
3. `run_skillsbench_full_causalflow.py` 与 `run_skillsbench_causalflow_repair.py` 从环境变量读取 CausalFlow 模型。
4. `llm_client.py` 优先读取标准变量 `OPENROUTER_API_KEY`，并兼容旧变量名。
5. 共享执行器保留工作副本中的 OpenHands Skill 隔离补丁。补丁原文在 `patches/shared_executor_local_changes.diff`。
6. CausalFlow 主模型、结果预测、critic 和 meta-critic 均改为配置读取，默认使用同一 Claude Opus 4.7 路由，避免隐藏调用 GPT 或 Gemini。

## 未收入 ZIP 的内容

- `.env` 和所有真实凭据；
- `.venv`、`.git`、`__pycache__` 和工具缓存；
- 历史 rollout、结果目录、日志和模型生成物；
- 私有缺陷 registry、外部 baseline 仓库和 SkillsBench 任务数据。

这些排除项不会影响本包的入口代码。运行前需把 `SKILLSBENCH_ROOT` 指向本机任务仓库。
