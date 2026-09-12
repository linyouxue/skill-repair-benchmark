# Skill 错误样本操作说明

本目录提供 7 个可直接运行的错误 Skill 样本。所有命令均在仓库根目录执行。

## 1. 安装环境

安装 `uv` 和 Docker。启动 Docker 后运行：

```bash
uv sync --extra dev --locked
docker version
```

获取实验使用的 SkillsBench 版本：

```bash
git clone https://github.com/benchflow-ai/skillsbench.git ../skillsbench
git -C ../skillsbench checkout 9a1f4dd5f7659f75707435da3ce854b6e48321d1
```

复制环境变量模板并填写模型密钥：

```bash
cp .env.sample .env
chmod 600 .env
```

使用 OpenRouter 时至少填写：

```dotenv
BENCHMARK_MODEL=openrouter/openai/gpt-5.2
OPENROUTER_API_KEY=<你的密钥>
```

将配置载入当前终端：

```bash
set -a
source .env
set +a
export SKILLSBENCH_TASKS_ROOT="$(cd ../skillsbench/tasks && pwd)"
export BENCHMARK_JOBS_ROOT="$(pwd)/jobs/skill-error-injection"
```

## 2. 检查代码包

```bash
uv run python benchmarks/skill-error-injection/run_case.py check
```

输出中的 `"ok": true` 表示 7 个样本的修改文件和摘要均通过检查。

查看全部样本：

```bash
uv run python benchmarks/skill-error-injection/run_case.py list
```

`fully_validated` 表示样本已经完成原始组、故障组和恢复回放。`mechanism_confirmed` 表示模型执行了错误规则，任务随后未通过评分。

## 3. 运行错误 Skill

先选择样本：

```bash
export CASE_ID=sec13f-wrong-total-row-stock-count-v1
```

执行一次故障任务：

```bash
uv run python benchmarks/skill-error-injection/run_case.py run \
  --case "$CASE_ID" \
  --condition defective \
  --rollout-id "${CASE_ID}-defective-r0"
```

工具会读取本地 SkillsBench 任务中的原始 Skill，覆盖当前样本提供的修改文件，然后把生成的完整 Skill 包交给统一执行器。

每次运行必须使用新的 `rollout-id`。执行器拒绝覆盖已有目录。

## 4. 准备修复结果

生成供修复方法使用的完整 Skill 目录：

```bash
mkdir -p "method-output/$CASE_ID"
uv run python benchmarks/skill-error-injection/run_case.py materialize \
  --case "$CASE_ID" \
  --output "method-output/$CASE_ID/full-skills"
```

命令拒绝覆盖已有目录。修复方法应修改 `method-output/$CASE_ID/full-skills`。提交目录必须保留全部 Skill 文件、脚本和资源。

## 5. 运行修复后的 Skill

```bash
uv run python benchmarks/skill-error-injection/run_case.py run \
  --case "$CASE_ID" \
  --condition repaired \
  --skills-dir "method-output/$CASE_ID/full-skills" \
  --method-id "<方法名称>" \
  --rollout-id "${CASE_ID}-repaired-r0"
```

如需运行任务自带的原始 Skill：

```bash
uv run python benchmarks/skill-error-injection/run_case.py run \
  --case "$CASE_ID" \
  --condition original \
  --rollout-id "${CASE_ID}-original-r0"
```

## 6. 查看结果

结果保存在：

```text
$BENCHMARK_JOBS_ROOT/<方法名称>/<rollout-id>/
```

查看统一结果：

```bash
jq '{execution_ok, task_passed, reward, error_category}' \
  "$BENCHMARK_JOBS_ROOT/<方法名称>/<rollout-id>/benchmark_result.json"
```

`execution_ok` 为 `true` 时，本次任务执行具备评分条件。`task_passed` 为 `true` 表示通过官方评分；`false` 表示任务执行完成，但结果未通过。

保留以下文件，便于复核：

- `benchmark_result.json`
- `executor_request.json`
- `result.json`
- `trajectory/`
- `verifier/`
- 修复后的完整 Skill 目录

本目录的 7 个错误注入案例与 `evaluation/data/core25/` 的 7 个 Gold 任务并非同一集合。CausalFlow 的 Core-25 [提交格式导出说明](../../evaluation/README.md#causalflow-结果转提交格式)可用于对接评估器，但不能直接拿此目录的错误注入案例套用 Core-25 Gold 评分。
