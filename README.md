# SkillsBench 统一 Benchmark Executor

本仓库是课题组共享的 SkillsBench **task rollout 执行器**。SkillGen、
SkillRevise、SkillHone 等方法可以在仓库外实现各自的诊断、修复与 refinement，
但凡需要让模型真正执行一次 task，都应调用这一份 executor，以统一 OpenHands、
Skill 暴露方式、60 次 iteration 限制、Docker 环境、官方 verifier 和结果证据。

> 第一次拿到交付 ZIP，请从
> [DELIVERY_GUIDE.md](./DELIVERY_GUIDE.md#0-第一次使用从解压到一条有效-rollout)
> 开始，不要按上游 BenchFlow 的普通安装教程操作。

## 文档导航

| 你要做什么 | 阅读位置 |
|---|---|
| 第一次安装并跑通一条任务 | [DELIVERY_GUIDE.md：第一次使用](./DELIVERY_GUIDE.md#0-第一次使用从解压到一条有效-rollout) |
| 手动运行 no-skill / original-skill / method-skill | [DELIVERY_GUIDE.md：人工或调试运行](./DELIVERY_GUIDE.md#4-入口-a人工或调试运行) |
| 在 SkillRevise、SkillHone 等算法中调用 rollout | [DELIVERY_GUIDE.md：修复算法自动调用](./DELIVERY_GUIDE.md#5-入口-b修复算法自动调用) |
| 配置 WSL、Linux 服务器或临时 SSH 代理 | [DELIVERY_GUIDE.md：网络与代理](./DELIVERY_GUIDE.md#21-先分清四条网络链路) |
| 判断结果能否进入方法比较 | [DELIVERY_GUIDE.md：返回结果](./DELIVERY_GUIDE.md#7-返回结果与判定规则) |
| 理解固定协议、Skill 预载和 iteration 定义 | [BENCHMARK_EXECUTOR.md](./BENCHMARK_EXECUTOR.md) |
| 查看机器可读的固定版本 | [BENCHMARK_EXECUTOR_VERSION.json](./BENCHMARK_EXECUTOR_VERSION.json) |

## 交付包包含什么

- 固定版本的 BenchFlow 源码及锁定依赖；
- OpenHands benchmark adapter；
- `skillrepair-v1` 公共 Python API；
- no-skill、original-skill、method-skill 三种条件；
- 每个 BenchFlow execution Step 最多 60 次根 Agent iteration；
- persistent `AgentContext` 中的完整 `SKILL.md` 预载与证据；
- 动态 LiteLLM、本机 Docker/原生 Linux host-gateway 适配和容器内健康检查；
- 默认关闭、由每台机器自行配置的 verifier 进程定向依赖代理与付费前连通性检查；
- result、trajectory、verifier 与 Skill exposure 的统一结果契约。

交付包**不包含**：

- SkillsBench task 仓库或 Core-25 任务副本；
- GPT-5.2、DeepSeek 等供应商的 API key；
- 各方法自己的 diagnosis、repair、refinement 或候选选择代码；
- 已有实验轨迹和运行结果。

这些内容必须由实验协调者或各方法负责人另行提供。正式比较时，所有同学必须使用
同一 SkillsBench commit、Core-25 清单、模型路由和 reasoning effort。

## 第一次使用的最短路径

1. 从课题组 GitHub 固定 commit/tag 获取源码，或在 Linux、macOS、WSL2 中解压
   对应 release ZIP；Windows 原生 Python 不受支持。
2. 启动 Docker，并确认 `docker version` 能同时看到 Client 和 Server。
3. 在本仓库运行 `uv sync --extra dev --locked`，不要安装 PyPI 版 BenchFlow。
4. 获取课题组冻结的 SkillsBench task source，并核对 commit。
5. 从 `.env.sample` 创建本机 `.env`，填写模型路由和对应供应商的 key。
6. 运行不调用模型的离线测试。
7. 明确付费后，只运行一条 original-skill smoke rollout。
8. 只有 `comparable == true` 的结果才能进入方法比较。

完整命令、结果判定和排错方法都在
[DELIVERY_GUIDE.md](./DELIVERY_GUIDE.md) 中。

## 三种评测条件

| 条件 | Skill 来源 | 主要用途 |
|---|---|---|
| `no-skill` | 不向 Agent 暴露 task 官方 Skill | 基础模型能力与 Skill 增量的参照 |
| `original-skill` | task 自带的完整官方 bundle | Skill 修复方法的基线 |
| `method-skill` | 方法提交的完整、冻结 bundle | 测量生成或修复后的效果 |

`method-skill` 的输入必须是完整 bundle，不是只包含本轮改动的 patch。执行器不会替
方法自动 merge 官方 Skill 与修改文件。

## 两个入口

- 人工查看原生 rollout 或单条调试：使用仓库内的 `uv run --locked bench eval run ...`。
- 修复算法正式接入：使用 `from benchmark_executor import BenchmarkExecutor`。

首次机器验收和正式方法接入都推荐 Python API：它会额外生成
`benchmark_result.json` 并给出 `comparable`。不要在算法内部拼接 shell 命令。

## 不能改变的比较条件

- 不要从 PyPI 安装上游 BenchFlow 覆盖本仓库。
- 不要为每种方法复制并修改一套 BenchFlow。
- 不要把同一组方法放到不同模型、供应商路由、reasoning effort 或 task commit 上比较。
- 不要把 `task_passed == false` 当作基础设施故障；先检查 `execution_ok` 和 `comparable`。
- verifier 依赖安装失败时，即使脚本留下 `reward.txt=0`，该结果也是
  `verifier_dep_install` / `non-comparable`，不能算作方法失败。
- 不要因为 `artifacts/` 为空就认定任务失败；许多 task 不向 `/logs/artifacts` 写文件。
- 不要覆盖已有 rollout 目录；每次运行使用唯一的 `rollout_id`。

## 版本与上游关系

本项目基于 BenchFlow `v0.6.7` / commit
`aadad44acf27f193df98f438443116d514f51fb8`，但包含课题组评测所需的 adapter 和
执行协议约束。仓库中的 `docs/` 保留上游 BenchFlow 参考资料；它们用于理解底层
框架，不替代本项目的交付指南。

课题组当前项目仓库为
[linyouxue/skill-repair-benchmark](https://github.com/linyouxue/skill-repair-benchmark)
（私有仓库，需要仓库权限）。正式实验应 checkout 协调者公布的 commit 或 release
tag，不要无条件跟随持续变化的默认分支。

SkillsBench 官方仓库为
[benchflow-ai/skillsbench](https://github.com/benchflow-ai/skillsbench)。本指南当前
示例使用 tag `v1.1` 对应的 commit
`b63b7b2850226b6aa4fb5929a8c1ac7bc4d9a6af`。若课题组协调者另行发布冻结版本，
以协调者通知为准，但同一轮正式实验不得混用不同 commit。

## License

BenchFlow 上游及本交付代码遵循仓库中的 Apache-2.0 License。
