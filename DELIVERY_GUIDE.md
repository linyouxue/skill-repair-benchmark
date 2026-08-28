# benchmark-executor 交付与接入说明

> 本文面向第一次拿到交付 ZIP 的同学。只想理解协议时读
> [BENCHMARK_EXECUTOR.md](./BENCHMARK_EXECUTOR.md)；准备运行或接入方法时，按本文
> 顺序执行。标有“付费”的步骤会调用模型，其余安装和检查不会消耗模型额度。

## 0. 第一次使用：从解压到一条有效 rollout

这一节给出一条完整、可复制的首次使用路径。最低机器验收只运行 **1 条
original-skill rollout**：它同时覆盖任务镜像、Docker 网络、动态 LiteLLM、
OpenHands、模型请求、完整 Skill 预载和官方 verifier。no-skill 是需要验证基线
剥离语义时再运行的第 2 条付费 rollout，不是安装的必做步骤。

### 0.1 准备四项输入

开始前确认已经拿到：

1. 课题组 GitHub 固定 commit/tag，或与其对应的 release ZIP；
2. 课题组统一的 SkillsBench 版本和 Core-25 清单；
3. 本轮实验指定的完整模型路由与 reasoning effort；
4. 对应供应商的 API key 和可用余额/配额。

本仓库和 release ZIP 都不包含 SkillsBench tasks、API key、Core-25 清单或任何方法的修复代码。
当前示例采用 SkillsBench tag `v1.1`，其 tag 指向 commit
`b63b7b2850226b6aa4fb5929a8c1ac7bc4d9a6af`；若协调者发布了新的冻结版本，
用协调者给出的值替换本文示例，不能在同一轮正式实验中混用。

### 0.2 在 Linux/WSL 文件系统中获取固定版本

Windows 用户先打开 Docker Desktop 并启用目标 WSL distro 的 integration，然后在
WSL 终端操作。建议把 executor 放在 `~/` 下，不要长期从 `/mnt/c/...` 运行。若
协调者提供 GitHub 仓库，clone 后必须 checkout 公布的 commit 或 tag：

```bash
git clone https://github.com/linyouxue/skill-repair-benchmark.git \
  "$HOME/benchmark-executor"
cd "$HOME/benchmark-executor"
git checkout --detach <课题组公布的commit或tag>
test "$(git rev-parse HEAD)" = "<课题组公布的完整commit SHA>"
test -z "$(git status --porcelain)"
```

若收到的是 release ZIP，使用能恢复 ZIP Unix mode 的 `unzip`；不要用 Python
`zipfile` 解压后直接运行，因为它不会恢复 executable bit：

```bash
# Ubuntu/WSL 若尚未安装 unzip：sudo apt-get install unzip
export EXECUTOR_ZIP="/mnt/c/Users/<Windows用户名>/Downloads/<交付包文件名>.zip"
export EXECUTOR_HOME="$HOME/benchmark-executor-delivery"

mkdir -p "$EXECUTOR_HOME"
unzip -q "$EXECUTOR_ZIP" -d "$EXECUTOR_HOME"
cd "$EXECUTOR_HOME/benchmark-executor"

test -f DELIVERY_GUIDE.md
test -f BENCHMARK_EXECUTOR_VERSION.json
```

Linux/macOS 用户只需把 `EXECUTOR_ZIP` 换成本机实际路径。若已经正确解压到 Linux
文件系统，或已按 GitHub 路径 checkout，可以直接进入仓库根目录继续。

### 0.3 检查依赖并安装锁定环境

支持 Linux、WSL2 和 macOS；Windows 原生 Python 不受支持。需要 Python 3.12+、
`uv`、Git、Docker Engine/Desktop 和 Docker Compose v2。

```bash
python3 --version
uv --version
git --version
docker version
docker compose version
docker run --rm hello-world

uv sync --extra dev --locked
uv run --locked bench --version
```

`docker version` 必须同时出现 Client 和 Server；只有 Client 通常表示 Docker daemon
或 WSL integration 尚未连通。不要执行 `uv tool install benchflow`，也不要用全局
`bench` 代替这里的 `uv run --locked bench`。

### 0.4 获取并冻结 SkillsBench

第一次使用可从官方仓库获取当前组内示例版本：

```bash
cd "$HOME"
git clone --depth 1 --branch v1.1 \
  https://github.com/benchflow-ai/skillsbench.git skillsbench-v1.1
cd "$HOME/skillsbench-v1.1"

export EXPECTED_SKILLSBENCH_COMMIT="b63b7b2850226b6aa4fb5929a8c1ac7bc4d9a6af"
git checkout --detach "$EXPECTED_SKILLSBENCH_COMMIT"
test "$(git rev-parse HEAD)" = "$EXPECTED_SKILLSBENCH_COMMIT"
test -z "$(git status --porcelain)"
test -f tasks/dialogue-parser/task.md
```

已有 task checkout 时不要重复 clone，只需对现有目录执行后三项核对。正式实验应
使用协调者发布的 commit 和任务清单；`result.json` 中的 live `task_digest` 可以
帮助事后发现差异，但不会替你阻止两位同学使用不同 checkout。

### 0.5 配置模型和 API key

回到 executor 根目录：

```bash
cd "$EXECUTOR_HOME/benchmark-executor"
cp .env.sample .env
chmod 600 .env
```

编辑 `.env`。例如通过 OpenRouter 使用 GPT-5.2 时，至少填写：

```dotenv
BENCHMARK_MODEL=openrouter/openai/gpt-5.2
BENCHMARK_REASONING_EFFORT=
SKILLSBENCH_ROOT=~/skillsbench-v1.1
BENCHMARK_JOBS_ROOT=~/benchmark-executor-jobs
TASK_ID=dialogue-parser
OPENROUTER_API_KEY=<你的 key>
```

不同路由使用不同 key：

| 模型路由示例 | 需要的变量 |
|---|---|
| `openrouter/<上游>/<模型>` | `OPENROUTER_API_KEY` |
| `openai/<模型>` | `OPENAI_API_KEY` |
| `deepseek/<模型>` | `DEEPSEEK_API_KEY` |

模型是否实际可用取决于供应商账户、地区、余额和模型权限；路由格式正确不等于账户
一定有访问权。不要把真实 key 写进文档、代码、日志或要发送的 ZIP。

将 `.env` 真正导出到当前 shell：

```bash
set -a
source .env
set +a

test -n "$BENCHMARK_MODEL"
test -d "$SKILLSBENCH_ROOT/tasks/$TASK_ID"
```

BenchFlow CLI 会读取当前目录的 `.env` 作为 provider 凭据，但 shell 会在 CLI 启动
前展开 `"$BENCHMARK_MODEL"`，Python 示例也读取 `os.environ`；因此这里仍必须
source/export。若从其他目录启动，可显式设置 `BENCHFLOW_DOTENV_PATH` 指向该文件。

### 0.6 先做免费离线检查

下面的命令不会调用模型：

```bash
uv run --locked pytest -q \
  tests/test_benchmark_executor.py \
  tests/test_public_benchmark_executor.py \
  tests/test_verifier_output.py \
  tests/agents/test_openhands_benchmark_adapter.py \
  tests/test_rollout_hard_deadline.py \
  tests/test_package_benchmark_executor.py

uv run --locked bench tasks check \
  "$SKILLSBENCH_ROOT/tasks/$TASK_ID" \
  --level structural
```

第一条检查公共 API、协议 guard、Skill preload、verifier 失败闭锁和 iteration
accounting；第二条只
检查选定 task 的结构。两者通过后再决定是否开始付费 smoke。

### 0.7 运行一条 original-skill smoke（付费）

以下代码会真实调用 `BENCHMARK_MODEL`，产生一条 rollout 并计费。它使用公共
Python API，因此会直接生成 `benchmark_result.json` 和严格的 `comparable` 判定。

```bash
uv run --locked python - <<'PY'
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from benchmark_executor import BenchmarkExecutor

task_id = os.environ.get("TASK_ID", "dialogue-parser")
reasoning_effort = os.environ.get("BENCHMARK_REASONING_EFFORT", "").strip() or None
rollout_id = f"{task_id}-original-smoke-{datetime.now(UTC):%Y%m%dT%H%M%SZ}"

executor = BenchmarkExecutor(
    tasks_root=Path(os.environ["SKILLSBENCH_ROOT"]) / "tasks",
    jobs_root=os.environ["BENCHMARK_JOBS_ROOT"],
    model=os.environ["BENCHMARK_MODEL"],
    reasoning_effort=reasoning_effort,
    protocol="skillrepair-v1",
)
result = executor.run(
    task_id=task_id,
    condition="original-skill",
    method_id="machine-smoke",
    stage="original-skill-smoke",
    rollout_id=rollout_id,
)

print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
if not result.comparable:
    diagnostics = {
        "protocol_evidence_valid": result.protocol_evidence_valid,
        "execution_ok": result.execution_ok,
        "trajectory_complete": result.trajectory_complete,
        "iteration_accounting_complete": result.iteration_accounting_complete,
        "skill_exposure_verified": result.skill_exposure.verified,
        "error": result.error,
        "error_category": result.error_category,
        "verifier_error": result.verifier_error,
        "verifier_error_category": result.verifier_error_category,
        "export_error": result.export_error,
    }
    print(json.dumps(diagnostics, ensure_ascii=False, indent=2))
    raise SystemExit(2)
PY
```

验收标准是 `execution_ok: true` 且 `comparable: true`。`task_passed: false` 仍可能是
一条完整、有效的任务失败，不代表环境没跑通。一次 smoke 只能证明这一台机器在
这个 task、模型和供应商路由上的链路有效；其他 task 的首次镜像构建仍可能遇到
任务特异问题。

若还要验证 no-skill 路径，再运行一条新的付费 rollout，把上例中的
`condition="original-skill"` 改成 `condition="no-skill"`，并相应修改 `stage`；
时间戳会生成新的 `rollout_id`，不会覆盖第一条结果。

### 0.8 接下来做什么

- 只做人工复现：继续看第 4 节的 CLI 命令；
- 把 SkillRevise、SkillHone 等方法接入：直接看第 5 节 Python API；
- 判断任务失败、基础设施错误和证据缺失：看第 7 节；
- 遇到 Docker、代理、API key 或 bundle 问题：看第 10 节。

## 1. 交付边界

本仓库是所有方法共享的 task rollout 执行基础设施。SkillGen、SkillRevise、
SkillHone 等方法在仓库外完成诊断、修复、refinement 和 gate；一旦需要让模型
真正执行一次 SkillsBench task，就调用这里的统一执行器。

```text
方法自己的 diagnosis / repair / refinement
                    │
                    │ task_id + complete skill bundle
                    ▼
             benchmark-executor
                    │
                    ▼
       同一个 BenchFlow Rollout 后端
                    │
                    ▼
       OpenHands + 选定模型 + 官方 verifier
```

每种方法不得复制自己的 BenchFlow，也不得修改 adapter、60 次 iteration 限制或
watchdog。模型与供应商不与执行协议绑定：每轮模型对比可以选择不同路由，但同一
组方法比较必须使用相同的模型、reasoning effort 和执行协议。

## 2. 安装

支持 Linux、WSL2 和 macOS，要求 Python 3.12+、`uv`、Git、Docker Engine
20.10+ 和 Docker Compose v2。Windows/macOS 使用 Docker Desktop，Linux 服务器
可直接使用原生 Docker Engine；Windows 原生 Python 不受支持。

执行器不会保存或写死任何同学的局域网 IP、VPN IP 或代理端口。Windows/WSL2 与
macOS 的 Docker Desktop 通过稳定的 `host.docker.internal` 让任务容器访问本机
LiteLLM；原生 Linux 由 Compose 自动补充 `host-gateway` 映射，并让 LiteLLM 只
监听 Docker bridge；无法识别或绑定 bridge 时安全停止，不回退到可能暴露公网的
`0.0.0.0`。端口由每条 rollout 动态分配，不固定为 4000，以支持并行运行和用量
隔离。LiteLLM 启动后、首次模型请求前，执行器会从实际 task 容器访问健康端点；
无法连通则直接记为基础设施错误，不产生 provider 请求。

同学不需要手动启动固定的 `localhost:4000` LiteLLM 服务，也不需要查找或填写
Docker bridge IP。每条 rollout 的动态端口、host-gateway 映射和健康检查都由
executor 管理。

模型供应商的出站网络和代理由每台机器自己的系统环境负责。若通过
`DOCKER_HOST=ssh://...` 从另一台机器控制远程 daemon，`host.docker.internal` 会
指向远程 Docker 宿主机而非本地 runner；这种拓扑不受支持，请直接在 Docker
服务器上运行 executor，或另行把 LiteLLM 部署到任务容器可访问的网络中。

### 2.1 先分清四条网络链路

“浏览器能访问供应商”不能证明一次 Docker rollout 的全部网络都正常。正式排错前，
先确定失败属于哪一层：

| 网络链路 | 谁发起请求 | 本执行器是否自动处理 | 应在哪里配置 |
|---|---|---|---|
| Docker daemon → 镜像仓库 | Docker daemon | 否 | Docker Desktop 或 Linux daemon 的代理/镜像源 |
| host LiteLLM → 模型供应商 | 启动 executor 的 Linux/WSL 进程 | 继承 runner 环境 | runner 的 `HTTP_PROXY`、`HTTPS_PROXY`、`NO_PROXY` |
| task container → host LiteLLM | OpenHands 所在任务容器 | 是 | 动态端口、`host.docker.internal` 与 Linux `host-gateway` 由 executor 管理 |
| task/verifier container → apt、uv、PyPI 等 | 任务或官方 verifier 容器 | 否 | Docker bridge 的直接出站网络，或管理员批准的容器代理 |

第三条链路只承载模型请求。第四条链路是独立的：部分官方 verifier 会在
`test.sh` 中执行 `apt-get`、`curl`、`uv` 或 `pip`。runner 上的代理不会自动复制到
容器里，因为这可能把带凭据的代理暴露给不受信任的 task/agent。反过来，Docker
daemon 能拉取镜像，也不表示运行中的容器一定能访问 PyPI。

无论是否使用代理，都建议保留：

```bash
export NO_PROXY="localhost,127.0.0.1,::1,host.docker.internal"
```

否则通用代理可能错误截获 task container 到动态 LiteLLM 的本地请求，造成
task-container health preflight 失败。

### 2.2 runner 直连或使用本机代理

Linux 服务器可以直连供应商时，不要设置代理变量。需要代理时，在启动 executor
的同一个 shell 中设置并先做不带 API key 的连通性检查：

```bash
export HTTP_PROXY="http://<runner可达的代理地址>:<端口>"
export HTTPS_PROXY="$HTTP_PROXY"
export NO_PROXY="localhost,127.0.0.1,::1,host.docker.internal"

curl -I --max-time 20 https://openrouter.ai/
```

这里的 `curl` 只检查网络，不调用模型、不产生模型费用。若实验使用其他供应商，
将 URL 换成该供应商的公开 HTTPS 站点。不要在命令行或截图中打印 API key。

Windows + WSL2 使用 FIClash、Clash 等本机代理时：

- WSL mirrored networking 下，可以先尝试 Windows 代理实际监听的
  `http://127.0.0.1:<mixed-port>`；
- WSL 默认 NAT 下，`127.0.0.1` 指向 WSL 自己，不能无条件照抄 Windows 代理地址；
- 若改为 Windows 主机地址访问，代理必须允许对应 WSL 网段，Windows 防火墙也要
  只放行需要的本地网段。不要为了方便把代理端口直接暴露到公网；
- 以 WSL 内上面的 `curl` 成功为准，Windows 浏览器成功不算验收。

确认后再把相同变量写入本机 `.env`，并执行 `set -a; source .env; set +a`。

### 2.3 Linux 服务器临时借用本地 FIClash

本地 VPN/代理不会自动作用于远程服务器。仅用于短期兼容性测试时，可以建立一条
只绑定服务器 loopback 的 SSH 反向隧道。假设 FIClash mixed port 是本机 `7890`，
服务器临时端口使用 `17890`：

```powershell
# 在 Windows PowerShell 保持该进程运行
ssh -N -T `
  -o ExitOnForwardFailure=yes `
  -o ServerAliveInterval=30 `
  -o ServerAliveCountMax=3 `
  -R 127.0.0.1:17890:127.0.0.1:7890 `
  <user>@<server>
```

然后在服务器上、启动 executor 的同一个 shell 中：

```bash
export HTTP_PROXY="http://127.0.0.1:17890"
export HTTPS_PROXY="$HTTP_PROXY"
export NO_PROXY="localhost,127.0.0.1,::1,host.docker.internal"

curl -I --max-time 20 https://openrouter.ai/
```

该方案只解决 **host LiteLLM → 模型供应商**。远程 `127.0.0.1:17890` 对普通 Docker
bridge 容器不可见，因此不能据此认定 verifier 的 `apt`/`uv` 网络已修好。测试期间
本机 FIClash、SSH 和电脑都必须保持运行；结束后关闭 SSH 进程。多用户服务器上的
其他本地用户也可能访问 loopback TCP 端口，所以只适合临时测试，不应作为长期共享
代理，更不能把 `-R` 地址改成 `0.0.0.0`。

### 2.4 task/verifier 容器需要外网时

若官方 verifier 需要在线安装依赖，推荐由服务器管理员为 Docker bridge 提供直接
出站网络、内部镜像源或受控的容器代理。容器代理地址必须从容器内可达；宿主机的
`127.0.0.1`、WSL 的临时地址和个人 VPN IP 都不能写死进 executor。

当前协议不会自动把 runner 的 `HTTP_PROXY`/`HTTPS_PROXY` 注入 task 或 verifier。
这是有意的凭据隔离。若某轮实验必须增加容器代理，应由协调者统一发布同一配置，
先在所有机器上验证，并记录为实验环境的一部分；不能由不同方法负责人各自改
BenchFlow。Docker daemon 的镜像代理仍需管理员单独配置。

如果 verifier 因依赖下载失败而没有真正执行测试，执行器会将其标记为
`verifier_dep_install`、`task_passed=None`、`comparable=False`。不要把留下的
`reward.txt=0` 当成模型失败；处理步骤见第 7.1 节。

```bash
cd /path/to/benchmark-executor
uv sync --extra dev --locked
```

方法代码在另一个项目时，可以把本地执行器安装到该方法明确指定的虚拟环境中：

```bash
cd /path/to/method-project
uv sync --locked
uv pip install --python .venv/bin/python -e /path/to/benchmark-executor
```

这条命令只把执行器源码装进方法项目的 `.venv`，不会自动让该环境继承执行器仓库的
`uv.lock`。方法项目应把自身依赖写入 `pyproject.toml` 并提交自己的 lock；正式运行前，
仍需在交付仓库中完成第 0.6 节基于原始 `uv.lock` 的离线验收。不要依赖“当前 shell
碰巧激活了哪个 venv”，也不要把执行器安装到系统 Python。

不要安装或升级 PyPI 上的普通 `benchflow` 来替代本仓库；普通版本不包含本项目的
Skill 预载 adapter 和 60-iteration 证据链。

## 3. 固定任务源、执行协议与可切换模型

正式实验需要同时冻结两层内容：

- executor 固定 OpenHands、adapter、Docker、60 iterations、watchdog 和证据契约；
- 实验协调者固定 SkillsBench commit、Core-25 清单及 task digest、模型路由和
  reasoning effort。

`comparable == true` 只验证一条 rollout 的 executor 证据完整，不会把本机 task
digest 与课题组清单自动比对。因此，所有参与者仍必须在运行前核对 SkillsBench
checkout，不能把事后记录 digest 当作事前冻结的替代品。

固定协议 ID 为 `skillrepair-v1`。机器可读说明位于
`BENCHMARK_EXECUTOR_VERSION.json`，其中固定：

- OpenHands 及其 pinned 版本；
- persistent `AgentContext` 的完整 `SKILL.md` 预载；
- 每个 BenchFlow execution Step 最多 60 次父 Agent iteration；
- 禁用 delegation；
- Docker sandbox；
- 三项仅用于防卡死的高阈值 watchdog；
- `no-skill`、`original-skill`、`method-skill` 三种条件；
- 一次 Python API 调用只产生一次 rollout，不做隐式重试。

模型、供应商路由和 reasoning effort 不属于协议常量，而是每个 executor 实例的
实验变量。例如：

```text
openrouter/openai/gpt-5.2   # 经 OpenRouter，仅为当前示例
openai/<实验指定模型>       # 经 OpenAI 直连
deepseek/<实验指定模型>     # 经 DeepSeek
```

供应商由 BenchFlow/LiteLLM 模型路由的首段确定；正式执行必须使用仓库已注册、
带供应商前缀的完整路由，不能写成裸模型名 `gpt-5.2`。切换供应商时同时设置对应
的 API key。模型在构造 `BenchmarkExecutor` 时选定，单次 `run()` 无法覆盖，因此
同一方法不会在不同 refinement 轮次中意外换模型。实际 model、provider route 和
reasoning effort 会随 rollout 留证：选择信息在 `executor_request.json`，BenchFlow
实际模型配置在 `config.json`，最终执行证据在 `result.json`。

评测另一个模型时，新建一个 `BenchmarkExecutor`，并给它单独的 `jobs_root`（例如
`jobs/by-model/deepseek-v4`）；不要在已有模型的输出目录中复用同一 `rollout_id`。
这样切换模型只改路由和输出根目录，方法的 `run()` 调用本身保持不变。

### 3.1 task 与候选 Skill bundle 的目录约束

SkillsBench v1.1 中一个带官方 Skill 的可修复 task 典型结构如下：

```text
tasks/<task-id>/
├── task.md
├── environment/
│   ├── Dockerfile
│   └── skills/
│       ├── <skill-a>/SKILL.md
│       └── <skill-b>/SKILL.md
├── oracle/
└── verifier/
```

`original-skill` 读取 `environment/skills/`。`method-skill` 的 `--skills-dir` 或
`skill_bundle` 则必须指向下面的 `full-skills/` 根目录：

```text
full-skills/
├── <skill-a>/
│   ├── SKILL.md
│   ├── references/       # 可选
│   ├── scripts/          # 可选
│   └── assets/           # 可选
└── <skill-b>/
    └── SKILL.md
```

每个 Skill 使用一层 `<skill-name>/SKILL.md`。不要提交根目录
`full-skills/SKILL.md`，也不要多套一层 `full-skills/group/<skill-name>/SKILL.md`。
人工修复官方 Skill 时，先完整复制官方 bundle，再修改副本；不要只建立一个 patch
目录：

```bash
export CANDIDATE_BUNDLE="$HOME/method-runs/$TASK_ID/round-1/full-skills"
test ! -e "$CANDIDATE_BUNDLE"
mkdir -p "$CANDIDATE_BUNDLE"
cp -a "$TASK_DIR/environment/skills/." "$CANDIDATE_BUNDLE/"
find "$CANDIDATE_BUNDLE" -mindepth 2 -maxdepth 2 -name SKILL.md -print
```

把复制后的目录视为该轮冻结输入。方法可以修改其中正文或配套文件，但一次 rollout
启动后不得原地改写该 bundle；下一轮先复制成新的完整目录。

## 4. 入口 A：人工或调试运行

适用于检查环境和手动复现单条 rollout。CLI 的 `--tasks-dir` 指向**一个 task
目录**；不要在带自定义 `--skills-dir` 时传整个 `tasks/` 父目录。

```bash
export TASK_DIR="$SKILLSBENCH_ROOT/tasks/$TASK_ID"
export RUN_TAG="$(date -u +%Y%m%dT%H%M%SZ)"
```

下列命令都显式固定 `--sandbox docker`。若本轮实验指定了非空 reasoning effort，
还必须给每条命令追加完全相同的 `--reasoning-effort <固定值>`；未传表示 `None`。

### no-skill

```bash
uv run --locked bench eval run \
  --tasks-dir "$TASK_DIR" \
  --agent openhands \
  --model "$BENCHMARK_MODEL" \
  --sandbox docker \
  --skill-mode no-skill \
  --retry-attempts 0 \
  --concurrency 1 \
  --jobs-dir "$BENCHMARK_JOBS_ROOT/manual/$RUN_TAG/no-skill"
```

### original-skill

```bash
uv run --locked bench eval run \
  --tasks-dir "$TASK_DIR" \
  --agent openhands \
  --model "$BENCHMARK_MODEL" \
  --sandbox docker \
  --skill-mode with-skill \
  --retry-attempts 0 \
  --concurrency 1 \
  --jobs-dir "$BENCHMARK_JOBS_ROOT/manual/$RUN_TAG/original-skill"
```

### method-skill

```bash
uv run --locked bench eval run \
  --tasks-dir "$TASK_DIR" \
  --agent openhands \
  --model "$BENCHMARK_MODEL" \
  --sandbox docker \
  --skill-mode with-skill \
  --skills-dir /path/to/method-output/full-skills \
  --retry-attempts 0 \
  --concurrency 1 \
  --jobs-dir "$BENCHMARK_JOBS_ROOT/manual/$RUN_TAG/method-skill"
```

`--skills-dir` 必须指向该 task 的完整 bundle，而不是只包含修改文件的 patch。

不要照搬“`--config configs/skillrepair-v1.yaml` 再追加 `--tasks-dir` 和
`--skills-dir`”的写法：当前 BenchFlow 把 `--config` 视为完整任务来源，与
`--tasks-dir` 互斥，而且 config 模式不会用 CLI 的 `--skills-dir` 覆盖 YAML。
本项目因此用运行时 guard 固定协议，而不是交付一个看似生效、实际会忽略字段的
YAML。

CLI 会写原生 `result.json`、trajectory、verifier 和 job `summary.json`，但不会
生成公共 API 的 `BenchmarkResult`、`benchmark_result.json` 或 `comparable`。
CLI 适合人工观察；正式方法接入和最终可比性判断使用第 5 节 Python API。每个
condition/trial 使用新的空 `--jobs-dir`，不要把多个条件写进同一恢复目录。

## 5. 入口 B：修复算法自动调用

适用于 SkillRevise、SkillHone、SkillOpt 等多轮算法。算法代码直接调用 Python
API，不拼接 shell 命令，也不会另起一套 BenchFlow。

```python
import os
from pathlib import Path

from benchmark_executor import BenchmarkExecutor

executor = BenchmarkExecutor(
    tasks_root=Path(os.environ["SKILLSBENCH_ROOT"]) / "tasks",
    jobs_root=Path(os.environ["BENCHMARK_JOBS_ROOT"]) / "skillrevise",
    model=os.environ["BENCHMARK_MODEL"],
    reasoning_effort=(
        os.environ.get("BENCHMARK_REASONING_EFFORT", "").strip() or None
    ),
    protocol="skillrepair-v1",
)

result = executor.run(
    task_id="manufacturing-codebook-normalization",
    condition="method-skill",
    skill_bundle="/path/to/round-2/full-skills",
    method_id="skillrevise",
    stage="round-2",
    rollout_id="manufacturing-codebook-normalization-r2",
)
```

`tasks_root` 通常指向 SkillsBench 的 `tasks/` 父目录；`task_id` 再选择其中一个
子目录。同步脚本或普通工作线程使用 `run()`。在 Jupyter、FastAPI 或其他当前
线程已有 event loop 的异步上下文中使用：

```python
result = await executor.run_async(...)
```

不要在同一个 running event loop 中调用同步的 `run()`，也不要让算法内部用
subprocess 调用 `bench`。方法侧也不要通过 Scene Role 或 `agent_env` 覆盖 model、
reasoning effort、通用 provider endpoint；这些入口会被正式执行器拒绝。

三种 Python condition 的输入约束为：

| `condition` | `skill_bundle` |
|---|---|
| `no-skill` | 必须为 `None` |
| `original-skill` | 必须为 `None`，读取 task 官方 bundle |
| `method-skill` | 必须是该 task 的完整、冻结 bundle |

一个 `BenchmarkExecutor` 实例固定一个模型路由和 reasoning effort；一次 `run()`
只产生一条 rollout，没有隐式重试。`method_id` 与 `rollout_id` 都必须是安全的单个
路径名，且每条新 rollout 使用新的 ID。

## 6. 多轮修复示例

```python
bundle = original_full_bundle

for round_index in range(3):
    result = executor.run(
        task_id=task_id,
        condition="method-skill",
        skill_bundle=bundle,
        method_id="skillrevise",
        stage=f"round-{round_index}",
        rollout_id=f"{task_id}-r{round_index}",
    )

    if not result.comparable:
        raise RuntimeError(
            f"invalid rollout evidence: {result.artifacts.result_json}"
        )

    diagnosis = skillrevise.diagnose(
        skill_bundle=bundle,
        trajectory=result.trajectory,
        verifier_components=result.verifier_components,
    )
    bundle = skillrevise.revise(bundle, diagnosis)
```

其中 `diagnose()`、`revise()`、候选选择和历史管理都属于方法；只有
`executor.run()` 属于统一评测基础设施。

## 7. 返回结果与判定规则

`BenchmarkResult` 的主要字段：

| 字段 | 含义 |
|---|---|
| `task_passed` / `success` | 官方 reward 存在且等于 1；无可靠 verdict 时为 `None` |
| `execution_ok` | Agent、verifier 和 export 链路均无错误 |
| `comparable` | 协议、Skill 暴露、iteration 和 trajectory 证据完整，可进入方法比较 |
| `reward` | 官方总 reward；未评分为 `None` |
| `error` / `error_category` | Agent 或主执行链路错误及稳定类别 |
| `verifier_error` / `verifier_error_category` | verifier 错误及稳定类别；`verifier_dep_install` 表示依赖安装失败 |
| `verifier_components` | `rewards` 中除顶层 `reward` 外的细粒度证据 |
| `trajectory` | 严格解析的 ACP trajectory 事件 |
| `artifacts` | result/config/trajectory/verifier 路径，以及可选的任务导出目录 |
| `agent_iterations` | 已完成 Step 的父 Agent iteration 总数 |
| `provider_requests` | 可严格解析的 `llm_trajectory.jsonl` 记录数；文件缺失或损坏为 `None` |
| `provider_route` / `provider_base_url` | 声明的供应商路由与运行时解析出的实际 endpoint |
| `provider_protocol` | 运行时解析出的供应商协议，例如 `openai-completions` |
| `skill_exposure` | expected/observed bundle SHA、Skill 数量和预载核验 |
| `wall_time_sec` | rollout 总耗时，单位秒 |
| `cost_usd` | 可用时的供应商费用 |
| `termination_reason` | `end_turn`、`max_iterations`、`stuck` 等停止原因 |

注意：`max_iterations` 是正常的预算终止，不是 infrastructure error；workspace 仍会
交给官方 verifier。`n_skill_invocations=0` 也不代表没看到 Skill，是否预载应看
`result.skill_exposure.verified`。

判断时使用以下顺序：

| `execution_ok` | `comparable` | `task_passed` | 解释与处理 |
|---:|---:|---:|---|
| `True` | `True` | `True` | 有效任务成功，纳入比较 |
| `True` | `True` | `False` | 有效任务失败，同样纳入比较 |
| `True` | `False` | 任意 | 执行结束但证据不完整，排除并排查缺失项 |
| `False` | `False` | `None` | Agent、verifier 或 export 基础设施失败，排除 |

### 7.1 verifier 失败、`reward=0` 与重新验证

`reward=0` 只有在官方 verifier **真正执行到评分逻辑并产生可信证据**时，才表示有效的
任务失败。某些 `test.sh` 在依赖安装失败后仍会继续执行，并在结尾无条件写入
`reward.txt=0`；旧版执行器可能因此把基础设施故障误记为可比较失败。

当前版本会在解析 reward 前扫描本次 `verifier/test-stdout.txt`。确认出现依赖安装
失败时，即使 `reward.txt` 或 `reward.json` 已存在，也会忽略该 reward，并输出：

```text
verifier_error_category = "verifier_dep_install"
execution_ok = false
task_passed = null
comparable = false
reward = null
```

错误摘要只包含固定、脱敏的诊断文字；可能含凭据或私有下载 URL 的原始输出只保留在
`verifier/test-stdout.txt`。`benchmark_result.json` 和 Python `BenchmarkResult` 都会
暴露 `verifier_error_category`，便于汇总脚本排除。不能只看容器退出码，也不能因为
`reward.txt=0` 存在就手工改回任务失败。

发现 `verifier_dep_install` 后按以下顺序处理：

1. 保留原 rollout，不覆盖、不计入方法成功率或失败率；
2. 查看 `verifier/test-stdout.txt`，确认失败的是 DNS、代理、下载源还是依赖解析；
3. 修复对应的容器出站网络、内部镜像或官方 verifier 环境；不要只修 host
   LiteLLM 的 provider 代理；
4. 先重新执行官方 verifier，确认测试框架真正启动且生成该 task 应有的官方证据；
5. 原 sandbox/workspace 仍完整时，允许把这次操作保存为单独的
   **verifier-only diagnostic retest**，但它不会自动把原 rollout 改成 comparable；
6. 原 workspace 已销毁、答案被人工重建，或官方 task/verifier 内容发生变化时，
   必须在冻结后的统一环境中重新跑完整 rollout，才能生成正式可比较结果。

不是所有 SkillsBench task 都要求 `ctrf.json`，因此执行器不会把“缺少 CTRF”单独作为
全局失败条件。应以该 task 的官方 verifier 契约、stdout 和 reward 共同判断。若修改
了官方 verifier 本身，协调者必须发布新的冻结 task commit，并在同一比较组上统一
重跑；不能只给某一个方法使用修后的 verifier。

对当前版本升级前已经生成的历史结果，若看到 `reward=0`/`comparable=true`，同时
`test-stdout.txt` 含依赖下载失败或 `uvx: command not found`，应将旧结果人工标记为
non-comparable，并按上述规则重新验证或重跑，不得直接沿用旧结论。

`comparable=True` 不等于任务通过，也不证明所有同学使用了同一 SkillsBench commit；
后者必须由冻结 checkout、Core-25 manifest 和 task digest 共同保证。若
`comparable=False`，优先查看：

```python
print(result.protocol_evidence_valid)
print(result.execution_ok)
print(result.trajectory_complete)
print(result.iteration_accounting_complete)
print(result.skill_exposure.verified)
print(result.error, result.error_category)
print(result.verifier_error, result.verifier_error_category)
print(result.export_error)
```

## 8. 输出与防覆盖

### 8.1 Python API 输出

公共 API 的输出结构为：

```text
<jobs_root>/
└── <method_id>/
    └── <rollout_id>/
        ├── executor_request.json
        ├── config.json
        ├── result.json
        ├── benchmark_result.json
        ├── trajectory/
        ├── verifier/
        └── artifacts/
```

`method_id` 和 `rollout_id` 必须是安全的单个路径名。目标目录已存在时 API 直接
拒绝，不恢复、不覆盖，防止不同模型、不同轮次或不同 bundle 的结果混写。

其中 `trajectory/`、`verifier/` 和各 JSON 结果文件由执行器保存；`artifacts/`
只对应任务容器中的 `/logs/artifacts`，任务没有向该位置写文件时可以为空。
SkillsBench 任务通常在 `/app` 中完成工作，执行器不会自动归档整个 `/app`；因此
`artifacts/` 为空不表示执行失败，也不影响 `execution_ok` 或 `comparable`。

### 8.2 原生 CLI 输出

CLI 不经过公共 Python wrapper，目录结构不同：

```text
<cli-jobs-dir>/
└── <自动生成的时间戳 job>/
    ├── summary.json
    └── <task-id>__<随机后缀>/
        ├── config.json
        ├── result.json
        ├── trajectory/
        ├── verifier/
        └── artifacts/
```

CLI 结束时会打印实际 Artifacts 与 Summary 路径。它不生成
`executor_request.json`、`benchmark_result.json` 或 `comparable`。同一个
`--jobs-dir` 可能触发原生恢复语义，因此每个 condition 和 trial 使用新的空目录。

## 9. 打包交付

课题组可以同时发布 GitHub 固定 commit/tag 和由该 commit 生成的 release ZIP。前者
便于审查、协作与追踪修复，后者便于同学直接部署。两种分发方式必须指向同一份源码；
协调者应同时公布 commit SHA、ZIP SHA256 和协议 ID `skillrepair-v1`。

### 9.1 生成 release ZIP

本节仅供维护者在包含 `.git/` 的原始 Git 工作树中生成 release。收到 release ZIP
的同学解压后直接按前述步骤安装和运行，无需重新打包；解压目录不包含 `.git/`，
不能在其中运行下面的打包命令。

维护者不要直接压缩整个开发目录。先运行：

```bash
uv run --locked python tools/package_benchmark_executor.py --check-only
uv run --locked python tools/package_benchmark_executor.py
```

默认生成同级的 `benchmark-executor-release.zip`，自动排除 `.git`、`.venv`、缓存、
运行结果和 `.env`，并执行 API key 格式门禁。打包器从 Git index 恢复 Unix mode，
对所有 `.sh` 和 shebang 脚本转换 LF，并在最终 ZIP 上重新执行 line-ending gate。

### 9.2 同步到 GitHub

维护者只能把源代码、锁文件、测试和文档推送到课题组指定仓库。以下内容不得提交：

- `.env`、API key、代理认证信息或 SSH 私钥；
- `jobs/`、rollout trajectory、verifier 输出和人工实验结果；
- `.venv/`、缓存、Docker 导出层和本机临时文件；
- SkillsBench task 私有副本，除非协调者明确决定把冻结 task source 一并版本化。

推送前至少执行：

```bash
git status --short
git diff --check
uv run --locked pytest -q \
  tests/test_verifier_output.py \
  tests/test_benchmark_executor.py \
  tests/test_public_benchmark_executor.py \
  tests/agents/test_openhands_benchmark_adapter.py \
  tests/test_rollout_hard_deadline.py \
  tests/test_package_benchmark_executor.py
uv run --locked python tools/package_benchmark_executor.py --check-only
```

随后只添加本次交付所需路径，复核 staged diff 和远端，再提交、推送：

```bash
git add <本次明确修改的源码、测试和文档>
git diff --cached --stat
git diff --cached
git remote -v
git commit -m "feat: add unified SkillsBench benchmark executor"
git push <课题组远端> <分支>
```

不要默认把代码推回上游 `benchflow-ai/benchflow`；应使用课题组自己的 GitHub fork 或
项目仓库。正式发布时建议为通过验收的 commit 建 tag/release，并把受控打包器生成的
ZIP 作为 release asset。收到 GitHub 链接的同学必须 checkout 协调者公布的 commit
或 tag，不能直接跟随持续变化的默认分支。

## 10. 常见问题与排错

| 现象 | 先检查什么 | 处理方式 |
|---|---|---|
| `docker version` 只有 Client 或连接失败 | Docker daemon、Docker Desktop WSL integration | 启动 daemon；Windows 中为当前 distro 重新启用 integration |
| `docker compose` 不存在 | Docker Compose v2 | 更新 Docker Desktop/Engine 的 Compose plugin |
| task-container health preflight 失败 | Docker 网络、host-gateway、代理的 `NO_PROXY` | 不要硬编码 bridge IP；确认 `host.docker.internal` 未被代理转发 |
| Windows 浏览器能联网，WSL provider 请求失败 | WSL 是否继承了可访问的代理地址 | 在 WSL 配置 `HTTP_PROXY`/`HTTPS_PROXY`；默认 NAT 下不要照抄 `127.0.0.1`，先用 WSL 内 `curl` 验证；Docker Desktop 镜像代理需单独配置 |
| Linux 服务器经本地 SSH 隧道能调模型，但 verifier 下载失败 | host 代理与容器出站是两条链路 | 按第 2.4 节配置管理员批准的 Docker bridge 出站网络；不要把远端 `127.0.0.1` 当容器代理 |
| 401 / 403 | key、账户权限、模型授权 | 核对模型路由首段对应的 key；不要打印完整 key |
| 402 | 供应商余额 | 充值或更换经实验批准的账户，不要自动换模型 |
| 429 | provider 限流 | 降低并发并按实验重试规则处理，不能因任务失败自行补跑 |
| provider 5xx 或连接中断 | 供应商状态、trajectory 是否已有请求 | 按统一基础设施重试规则记录；不要当作方法失败 |
| 提示裸模型名或 provider route 无效 | `BENCHMARK_MODEL` | 使用 `openrouter/...`、`openai/...`、`deepseek/...` 等已注册完整路由 |
| task 不存在 | `SKILLSBENCH_ROOT`、`TASK_ID`、checkout commit | 确认 API 指向 `tasks/` 父目录，CLI 指向单个 task 目录 |
| original-skill 在 task prompt 前失败 | `environment/skills` 是否存在且含 `SKILL.md` | 核对冻结 task 是否完整、是否误用了无 Skill task |
| method-skill bundle 被拒绝 | bundle 缺 `SKILL.md`、只交 patch、非 UTF-8、含 symlink | 先在方法外合成完整 bundle，再提交 executor |
| `rollout_id` 已存在 | Python API 输出目录 | 生成新 ID；不要覆盖或混写原结果 |
| `comparable=False` | 第 7 节列出的六类证据 | 保留产物并定位缺失项，不把它计为方法成功或失败 |
| `verifier_dep_install`，但目录里有 `reward.txt=0` | `verifier/test-stdout.txt` 与第 7.1 节 | reward 不可信；先修容器/verifier 环境并重新验证，不计为方法失败 |
| `artifacts/` 为空 | task 是否向 `/logs/artifacts` 写文件 | 这是允许状态；以 result、verifier 和 comparable 为准 |
| Windows 侧 `uv` 无法处理 `.venv/lib64` | 是否在 Windows 原生 Python 或 `/mnt/c` 工作树运行 | 按支持边界把仓库放进 WSL/Linux 文件系统，删除并在该环境重建本机 `.venv` |
| `bad interpreter` / `bash\r` | 是否使用原始交付 ZIP及 Linux `unzip` | 不要用资源管理器重新压缩；核对交付包 SHA 后在 Linux/WSL 重新解压 |

如果动态 LiteLLM 或 task-container preflight 报错，不要自行在 4000 端口另起一个
LiteLLM，也不要把个人 VPN IP 写入代码。先保存 `result.json`、console 错误和
rollout 目录，再由维护者判断是本机网络、Docker 拓扑还是 provider 问题。

## 11. 正式实验前的共同核对单

协调者发起一轮实验时，应同时给出以下信息；只发 executor ZIP 还不足以定义一轮
可比较实验：

| 项目 | 必须明确的值 |
|---|---|
| Executor | ZIP 文件名、SHA256、`protocol=skillrepair-v1` |
| Task source | SkillsBench commit、Core-25 manifest/任务 ID、必要时 task digest |
| Model | 完整 provider route、reasoning effort、所需 key 的变量名 |
| Conditions | 要运行 no-skill、original-skill、method-skill 中的哪些条件 |
| Sampling | 每个条件的 trial 数、随机性设置和统一重试规则 |
| Method output | `method_id` 命名规则、完整 bundle 路径、round/stage 规则 |
| Result policy | `comparable=False`、provider 故障和人工补跑如何记录与排除 |

同学开始前至少回传一次**不含密钥**的环境核对信息：executor ZIP SHA、SkillsBench
commit、`BENCHMARK_MODEL`、reasoning effort、Docker/Compose 版本和第 0.6 节测试结果。
出现故障时回传 console 错误、对应 rollout 目录及 `result.json`；不要发送 `.env`、
完整 API key 或包含其他私人实验的整个 jobs 根目录。
