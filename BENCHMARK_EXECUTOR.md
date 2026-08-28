# SkillsBench 统一 Rollout 执行器

> 本文定义执行协议和证据语义。第一次拿到交付 ZIP、准备环境或接入修复算法时，
> 请先按 [DELIVERY_GUIDE.md](./DELIVERY_GUIDE.md) 操作。

## 1. 边界

`benchmark-executor` 只负责一次真实的 SkillsBench task rollout：准备统一环境、执行 OpenHands、保存轨迹、运行官方 verifier。SkillGen、SkillRevise 等方法自己的诊断、修复和 refinement 循环必须放在该执行器外部。

统一关系是：

```text
任意方法的诊断 / 修复 / refinement
              │
              │ 提交 frozen full skill bundle
              ▼
同一个 benchmark-executor
              │
              ├─ OpenHands + 本组实验选定的模型/供应商路由
              ├─ persistent AgentContext 预载
              ├─ 每个 BenchFlow execution Step 最多 60 次 parent iteration
              └─ SkillsBench 官方 verifier
```

不要为每种方法复制或修改一套 BenchFlow。方法只读取本执行器输出的 `result.json`、trajectory 和 verifier 结果，再在外部决定下一版 Skill。

## 2. 固定执行协议

| 项目 | 固定值 |
|---|---|
| BenchFlow 基线 | `v0.6.7`，commit `aadad44acf27f193df98f438443116d514f51fb8` |
| Agent | `openhands` |
| 模型与供应商 | 每个 executor 实例或 CLI 命令显式选择；逐 rollout 记录 |
| Delegation | 禁用，避免子 Agent 形成额外预算轴 |
| 主要预算 | 每个 BenchFlow execution Step 最多 60 次 parent-agent iteration |
| 单次 LLM 请求卡死保护 | 3600 秒 |
| Agent idle 卡死保护 | 3600 秒 |
| Agent wall-clock 卡死保护 | 21600 秒（6 小时） |

为了避免把“执行器固定”误解成“整场实验的所有输入都自动固定”，三类责任必须分开：

| 层级 | 由谁固定 | 具体内容 |
|---|---|---|
| 执行器协议 | 本交付仓库 | BenchFlow/OpenHands 版本、Docker sandbox、Skill 预载、60 iterations、delegation guard、证据格式 |
| 实验公共输入 | 实验协调者 | SkillsBench commit、Core-25 task 清单及 digest、模型路由、reasoning effort、trial 数和重试规则 |
| 方法输入 | 各方法负责人 | `method_id`、候选完整 Skill bundle、轮次和唯一 `rollout_id` |

本 ZIP 不包含 SkillsBench task 仓库，也不会把本机 task digest 自动同课题组清单比较。
`comparable=True` 只能说明当前 rollout 的执行器证据完整；正式实验仍需先核对公共任务版本。

后三项只是防止 API、工具或传输永久挂死，不是用于比较方法的时间预算。命中 60 次限制不是 infrastructure error：执行器保留当前 workspace，继续运行 verifier，由 reward 判断结果，并在 `result.json` 中记录 `stop_reason=max_iterations`。

OpenHands 未显式指定模型、跳过 pinned Agent 安装，或在 Scene/Role 上另外指定
Agent、不同模型/reasoning、Role 环境覆盖和局部 Skill，都会在启动 sandbox 前失败。
模型路由必须带仓库已注册的供应商前缀，裸模型名不构成可审计的正式结果。模型本身不属于固定协议：
可以用 OpenRouter、模型厂商直连或其他 BenchFlow/LiteLLM 路由，但同一组方法对比
必须选择相同的模型路由与 reasoning effort。自定义 full bundle 一次只能对应一个
task；这些限制用于防止不同方法无意间形成不同的执行协议。仓库仍保留
上游其他 Agent 的通用代码，但它们不会产生 `executor` 证据，不能作为本项目的正式结果。

这里的一个 iteration 是 OpenHands 根 Agent 的一次 `agent.step()`，不是一个业务步骤、一个 shell 命令或一个 Skill 条目。正式执行器会禁用 delegation，因此不会出现不计入根 Agent 60 次的子 Agent 内部 step。

## 3. 三种评测条件

以下命令均从本仓库根目录运行，并且一次命令只执行一个 task。先在一个地方选择
完整的 BenchFlow/LiteLLM 路由；更换模型或供应商时只改这个变量，并设置对应
供应商的密钥：

```bash
export BENCHMARK_MODEL="openrouter/openai/gpt-5.2"  # 仅为示例
export OPENROUTER_API_KEY="..."
```

### 3.1 no-skill

```bash
uv run --locked bench eval run \
  --tasks-dir /path/to/skillsbench/tasks/<task-id> \
  --agent openhands \
  --model "$BENCHMARK_MODEL" \
  --sandbox docker \
  --skill-mode no-skill \
  --retry-attempts 0 \
  --concurrency 1 \
  --jobs-dir /path/to/output/no-skill
```

官方 Skill 会从 task 的运行副本中剥离，adapter 不预载 Skill。调用方即使伪造内部预载环境变量也会被执行器清除。

### 3.2 original-skill

```bash
uv run --locked bench eval run \
  --tasks-dir /path/to/skillsbench/tasks/<task-id> \
  --agent openhands \
  --model "$BENCHMARK_MODEL" \
  --sandbox docker \
  --skill-mode with-skill \
  --retry-attempts 0 \
  --concurrency 1 \
  --jobs-dir /path/to/output/original-skill
```

不要传 `--skills-dir`。执行器使用该 task 自带的 `environment/skills`，结果中的 `evaluation_condition` 为 `original-skill`。

### 3.3 method-skill

```bash
uv run --locked bench eval run \
  --tasks-dir /path/to/skillsbench/tasks/<task-id> \
  --agent openhands \
  --model "$BENCHMARK_MODEL" \
  --sandbox docker \
  --skill-mode with-skill \
  --skills-dir /path/to/method-output/full-skills \
  --retry-attempts 0 \
  --concurrency 1 \
  --jobs-dir /path/to/output/method-skill
```

`--skills-dir` 必须是方法产出的完整、冻结 bundle，而不是 patch：

```text
full-skills/
├── skill-a/
│   ├── SKILL.md
│   ├── scripts/
│   ├── references/
│   └── assets/
└── skill-b/
    └── SKILL.md
```

执行器不会把方法输出和官方 Skill 自动 merge。若方法只修改一个文件，它必须先在外部把官方 bundle 与修改合成为完整候选 bundle，再提交执行。

当前 `--skills-dir` 是一次运行的单一 bundle，因此 method-skill 不允许在一次命令中批量运行多个不同 task；否则同一 bundle 会错误地应用到多个 task。

## 4. Skill adapter 的实际行为

对 `original-skill` 和 `method-skill`：

1. 执行器在 rollout 创建时把完整 bundle 复制到该次输出的 `inputs/skills/`。
2. 所有文件按相对路径和原始字节计算确定性 SHA256；脚本、references 和 assets 也在 digest 中。
3. bundle 部署到 sandbox 后，OpenHands adapter 在 `Conversation` 创建前重新计算 digest。
4. adapter 按 POSIX 相对路径排序，把所有 `SKILL.md` 正文完整追加到 persistent `AgentContext.system_message_suffix`。
5. 完成以上步骤后，本次选定的模型才第一次看到原始 task prompt。

预载不增加 user turn、LLM 请求或 iteration。正文整轮可见，不需要模型先调用 `invoke_skill` 才能读取。因此在这个执行协议下，`n_skill_invocations=0` 不能再解释成“模型没有看到 Skill”；应查看 `executor.skill_context_preloaded`、`preloaded_skill_count` 和 bundle digest。

出现以下任一情况会在原始 task prompt 前失败：bundle 为空、没有 `SKILL.md`、`SKILL.md` 不是 UTF-8、包含 symlink、部署前后 digest 不一致。

## 5. 输出证据

本节描述原生 rollout 目录中的证据。CLI 会生成 `config.json`、`result.json`、
trajectory、verifier 和 artifacts；公共 Python API 会在此基础上额外生成
`executor_request.json`、`benchmark_result.json`，并返回 `BenchmarkResult.comparable`。
两种入口的完整目录差异和判定表见交付指南第 7、8 节。

verifier reward 采用失败闭锁语义：若本次 `test-stdout.txt` 显示依赖安装失败，执行器
不会接受随后留下的 `reward.txt=0` 或 `reward.json`，而是记录
`verifier_error_category=verifier_dep_install`、清空可信 reward，并令公共结果
`task_passed=None`、`comparable=False`。这是 verifier 基础设施错误，不是方法失败。
修复和 verifier-only diagnostic retest 的边界见交付指南第 7.1 节。

每个 rollout 的 `config.json` 和 `result.json` 都包含 `executor`。`config.json`
记录固定协议和预期预载状态；任务结束后，`result.json` 在同一块中追加 observed
计数、停止原因和 sandbox 侧预载证明，例如：

```json
{
  "executor": {
    "evaluation_condition": "method-skill",
    "protocol_version": 1,
    "benchflow_base_commit": "aadad44acf27f193df98f438443116d514f51fb8",
    "openhands_cli_commit": "2df8a2835d3f1bd2f2eadf5a7a2e1ad0dfb0d271",
    "model": "<selected-provider>/<selected-model>",
    "provider_route": "<selected-provider>",
    "provider_base_url": "<resolved-endpoint>",
    "provider_protocol": "openai-completions",
    "max_parent_iterations_per_step": 60,
    "skill_context_preloaded": true,
    "skill_bundle_sha256": "sha256:...",
    "preloaded_skill_count": 2,
    "preloaded_skill_files": ["skill-a/SKILL.md", "skill-b/SKILL.md"],
    "iteration_limit_reached": false,
    "stop_reason": "end_turn",
    "skill_context_preload_observed": true,
    "skill_context_preload_matches_expected": true,
    "prompt_runs": [
      {
        "prompt_ordinal": 1,
        "stop_reason": "end_turn",
        "acp_stop_reason": "end_turn",
        "iterations_used": 23,
        "max_iterations": 60
      }
    ]
  }
}
```

执行结束后，`result.json.agent_result` 还会给出：

- `stop_reason`：`end_turn`、`max_iterations`、`stuck`、`conversation_error` 等细粒度原因；
- `acp_stop_reason`：ACP 协议允许的原始枚举；
- `iterations_used`：该 rollout 所有已完成 prompt 的 parent iteration 总数；
- `max_iterations_per_run`：60；
- `prompt_runs`：每个 BenchFlow Step 对应的独立计数和停止原因。

若第一个 prompt 完成前就发生基础设施错误，`iterations_used` 为 `null`，不会伪写为
0；若前面的 Step 已完成而后续 Step 异常，只汇总已完成 Step，并记录
`iteration_accounting_complete=false`。

## 6. 安装、离线验证与打包

人工调试与修复算法自动调用是两个入口，但都落到同一个 Rollout 后端。公共
Python API、模型切换方法和交付边界见 [DELIVERY_GUIDE.md](./DELIVERY_GUIDE.md)。

支持 Linux、WSL2 和 macOS，要求 Python 3.12+、`uv`、Docker Engine 20.10+
和 Docker Compose v2；Windows/macOS 使用 Docker Desktop，Linux 服务器可以使用
原生 Docker Engine。Windows 原生 Python 不受支持；在 Windows 上请从 WSL2
进入本仓库后运行：

```bash
uv sync --extra dev --locked
uv run --locked pytest -q \
  tests/test_benchmark_executor.py \
  tests/test_public_benchmark_executor.py \
  tests/test_verifier_output.py \
  tests/agents/test_openhands_benchmark_adapter.py \
  tests/test_rollout_hard_deadline.py \
  tests/test_package_benchmark_executor.py
```

这些是离线单元测试，不调用付费模型。正式 smoke test 需要另行授权，并消耗所选
供应商账户的余额或配额。

以下打包命令仅供维护者在包含 `.git/` 的原始 Git 工作树中生成 release。收到
release ZIP 的同学解压后无需重新打包；解压目录不包含 `.git/`，不能在其中运行
这些命令。

维护者不要直接在资源管理器中把整个开发目录压缩，因为其中可能包含 `.git/`、`.venv/`
和缓存。使用随仓库提供的受控打包器；它只打包 Git 可见源码，排除运行目录，
并对高置信度 API key 格式做门禁：

```bash
uv run --locked python tools/package_benchmark_executor.py --check-only
uv run --locked python tools/package_benchmark_executor.py
```

默认产物为本目录上一级的 `benchmark-executor-release.zip`，解压后仍是
`benchmark-executor/`。脚本拒绝覆盖已有 zip；需要重打时先把旧包移走或通过
`--output` 指定新文件名。打包器会从 Git index 恢复 Unix executable mode，统一
`.sh` 与 shebang 脚本的 LF 换行，并在最终 ZIP 上再次执行权限、换行、敏感信息和
禁止目录门禁；不要用资源管理器重新压缩正式交付包。
