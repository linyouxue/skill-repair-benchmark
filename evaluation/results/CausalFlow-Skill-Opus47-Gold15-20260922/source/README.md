# CausalFlow × Claude × SkillsBench 交付包

这个包用于两件事：

1. 用 Claude Opus 4.7 和原始 Skill 跑一条 SkillsBench rollout；
2. 对失败 rollout 运行 CausalFlow 的因果归因和局部修复。

模型、数据路径和输出路径集中在 `config/claude_opus47.env`。正常情况下，只需修改这个配置文件和本地 `.env`，不用改 Python 源码。

## 一、准备环境

系统要求：Linux、macOS 或 WSL2，Python 3.12、`uv`、Git、Docker Engine/Desktop 和 Docker Compose v2。机器上还需要一份 SkillsBench checkout；交付包没有复制任务数据。

```bash
cd CausalFlow_Claude_Adapter_20260922
cp .env.example .env
# 编辑 .env，填写 OPENROUTER_API_KEY

# 编辑配置中的 SKILLSBENCH_ROOT；其余参数已有 Claude 默认值
vim config/claude_opus47.env

bash scripts/setup.sh
./.venv/bin/python scripts/run_experiment.py check
```

`check` 只检查路径、Docker 和 key 是否存在，不发送模型请求。

## 二、运行 Claude 原始 Skill

下面的命令会真实请求模型并产生费用：

```bash
./.venv/bin/python scripts/run_experiment.py original \
  --task-id dialogue-parser
```

程序会先打印预计运行目录。结果位于：

```text
runs/<method-id>/<rollout-id>/
```

其中 `benchmark_result.json` 是统一结果摘要，`result.json`、`trajectory/` 和 `verifier/` 保存执行证据。

只查看将要执行的命令时，在子命令前加 `--dry-run`：

```bash
./.venv/bin/python scripts/run_experiment.py --dry-run original \
  --task-id dialogue-parser
```

## 三、对失败轨迹运行 CausalFlow

只有原始 reward 小于 1.0 时才需要诊断。把上一步的运行目录传给 `diagnose`：

```bash
./.venv/bin/python scripts/run_experiment.py diagnose \
  --task-id dialogue-parser \
  --run-dir runs/causalflow-claude-opus47/<rollout-id>
```

默认输出到 `outputs/`。该入口会重新构建任务镜像、严格重放基线、计算 CRS，并评估候选局部修复。若运行来自共享执行器且没有原始 workspace 哈希，按下面三步准备重放证据：

```bash
# 1. 构建供严格重放使用的任务镜像
./.venv/bin/python scripts/run_experiment.py prebuild \
  --task-id dialogue-parser \
  --image causalflow-dialogue-parser:latest

# 2. 双重重放并保存审计证据
./.venv/bin/python scripts/run_experiment.py audit \
  --task-id dialogue-parser \
  --run-dir runs/causalflow-claude-opus47/<rollout-id> \
  --image causalflow-dialogue-parser:latest

# 3. 将同一镜像和审计文件交给完整 CausalFlow
./.venv/bin/python scripts/run_experiment.py diagnose \
  --task-id dialogue-parser \
  --run-dir runs/causalflow-claude-opus47/<rollout-id> \
  --existing-image causalflow-dialogue-parser:latest \
  --shared-executor-replay-audit \
  outputs/dialogue-parser-<rollout-id>-replay-audit.json
```

只验证轨迹能否严格重放，不调用 CausalFlow 模型：

```bash
./.venv/bin/python scripts/run_experiment.py diagnose \
  --task-id dialogue-parser \
  --run-dir runs/causalflow-claude-opus47/<rollout-id> \
  --strict-replay-only
```

单独运行较轻量的局部命令修复：

```bash
./.venv/bin/python scripts/run_experiment.py repair \
  --task-id dialogue-parser \
  --run-dir runs/causalflow-claude-opus47/<rollout-id> \
  --proposals 2
```

## 四、两个模型名为什么不同

配置里故意保留两种写法：

| 参数 | 默认值 | 使用位置 |
|---|---|---|
| `BENCHMARK_MODEL` | `openrouter/anthropic/claude-opus-4.7` | BenchFlow/LiteLLM 跑原始任务 |
| `CAUSALFLOW_MODEL` | `anthropic/claude-opus-4.7` | CausalFlow 直接请求 OpenRouter |

前者需要 LiteLLM 的 provider 前缀；后者直接使用 OpenRouter 的模型 ID。不要把两者机械改成同一个字符串。

## 五、交付包中的本地适配

- 删除了原代码里的个人绝对路径，路径统一由配置文件读取。
- Claude Opus 4.7 已设为默认 backbone。
- `OPENROUTER_API_KEY` 和旧变量 `OPENROUTER_SECRET_KEY` 均可识别。
- 随包共享执行器固定在 commit `b88b4b9482d08ad91d01058ecade523d753c086f`。
- 保留了本地 OpenHands Skill 隔离补丁：关闭项目、用户和公共 Skill 的二次自动发现，只使用执行器注入并校验过的任务 Skill bundle。
- 未包含任何真实 API key、虚拟环境、历史运行、模型输出或缓存。

本地补丁和文件来源见 `ADAPTATION_NOTES.md`。原项目说明保存在 `docs/README_ORIGINAL.md`。

## 六、离线自测

```bash
bash scripts/smoke_test.sh
```

该脚本编译交付源码并运行不需要 Docker、网络和模型额度的核心单元测试。
