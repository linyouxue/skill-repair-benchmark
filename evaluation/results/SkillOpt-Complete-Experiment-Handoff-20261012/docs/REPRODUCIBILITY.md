# Reproducibility

## 实验配置

共同参数：

- method: SkillOpt；
- diagnosis samples N=3；
- edit budget L=4；
- progressive repair rounds R=2；
- 三个 task worker 并行；
- 每个任务内部 diagnosis samples 顺序执行；
- acceptance gate 使用同一个任务，不是 held-out validation。

GPT track：

- baseline: `openrouter/openai/gpt-5.2` 的 31 条失败代表轨迹；
- optimizer: 360 API 的 `openai/gpt-5.2`；
- gate agent model: `ai360/openai/gpt-5.2`。

Opus track：

- baseline: `openrouter/anthropic/claude-opus-4.7` 的 15 条失败轨迹；
- optimizer: Tatu API 的 `claude-opus-4-7`；
- gate agent model: `tatu/claude-opus-4-7`。

## 命令

原始命令保存在：

- `runs/gpt52-31-skillopt-gpt52-ai360-20261011/commands/`
- `runs/opus47-15-skillopt-opus47-tatu-20261008/commands/`

核心入口是：

```bash
python code/scripts/run_method.py --method skillopt --task <task-id> --run-id <run-id>
```

实际运行前需根据对应 `commands/env.sh` 设置模型、N/L/R 和 provider。该脚本引用原机器
绝对路径，移机复现时应改为当前目录。API credentials 不在包内，使用
`code/env.template` 自行配置。

## 代码

- `code/SkillOpt/`：实验时使用的 SkillOpt 方法源码快照；
- `code/adapters/`：本实验适配层；
- `code/scripts/run_method.py`：两轮 gate、rejected buffer 与跨轮 evidence 主循环；
- `code/skill-repair-benchmark/src/`：BenchmarkExecutor/BenchFlow 源码快照；
- `code/evaluation/scripts/`：submission evaluator；
- `code/skill-repair-benchmark/pyproject.toml` 与 `uv.lock`：Python 依赖锁定。

任务执行协议在 `executor_request.json` 中统一记录：BenchFlow base commit
`aadad44acf27f193df98f438443116d514f51fb8`、OpenHands CLI commit
`2df8a2835d3f1bd2f2eadf5a7a2e1ad0dfb0d271`、SDK/tools `1.28.1`。

根适配工作区本身没有 Git metadata，因此不能只用一个提交号标识；本包提供完整源码
快照，并以 `metadata/FILE_MANIFEST.sha256` 固定其内容。evaluation 源仓库检查时的本地
HEAD 为 `558cab0c802a2654d7e051718ad9f7595c01ee4b`，工作树不是 clean，故源码快照优先于
单独 commit ID。

## 环境边界

- 凭据必须外部提供；本包不含 `.env`。
- Docker image、系统包仓库和第三方 API 是外部依赖。
- `multilingual-video-dubbing` 在 Apple Silicon 上使用 `linux/amd64` Docker emulation。
- 完全复现仍可能受 Docker image、apt/pip、模型 API 和第三方服务随时间变化影响。

