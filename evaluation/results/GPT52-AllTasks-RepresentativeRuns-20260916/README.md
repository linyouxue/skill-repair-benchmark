# GPT-5.2 SkillsBench 全任务代表运行归档

本目录收录本轮 SkillsBench **全部 87 个任务**各 1 条代表性 GPT-5.2 运行，用于课题组统一复核执行轨迹、PASS/FAIL、verifier 结果和运行元数据。

本目录是**执行证据归档**，不是某个 Skill 修复方法的 `submission.json`，也不包含官方 Skill bundle 正文。

## 选择规则

1. 模型统一为 `openrouter/openai/gpt-5.2`。
2. 已经人工复核过的 Core-22 任务原样复用 `OfficialSkillBaseline-Core22-20260916` 中的代表运行，不重新改选。
3. 其余任务优先选择**有效的 completion-guard Original-Skill 运行**。
4. 若不存在有效 guard 运行，则选择**时间上最后一条有效的 GPT-5.2 Original-Skill 运行**。
5. provider/API、Docker/sandbox、OpenHands/transport、verifier 执行错误以及没有明确 P/F 的运行全部排除，不参与代表运行选择。
6. 每个任务最终只保留 1 条代表运行，并在 `STATUS.csv` 与 `run_selection.json` 中明确记录 `PASS` 或 `FAIL`。

当前结果：

- 任务数：**87 / 87**
- PASS：**48**
- FAIL：**39**
- 自动排除的基础设施无效或无明确 P/F 候选运行：**43**

## 目录结构

```text
GPT52-AllTasks-RepresentativeRuns-20260916/
├── README.md
├── MANIFEST.json
├── STATUS.csv
├── EXCLUDED_RUNS.json
├── VALIDATION.json
├── tasks/
│   └── <task-id>/
│       ├── run_selection.json
│       └── selected_run/
│           ├── executor_request.json      # 该 runner 有生成时保留
│           ├── benchmark_result.json      # 该 runner 有生成时保留
│           ├── result.json
│           ├── config.json
│           ├── prompts.json
│           ├── results.jsonl
│           ├── rewards.jsonl
│           ├── timing.json
│           ├── agent/
│           ├── trajectory/
│           ├── trainer/
│           ├── verifier/
│           ├── artifacts/
│           ├── logs/                      # 能对应到该轮时保留
│           └── run_metadata/              # 旧 WSL runner 的必要外围元数据
└── trajectory_timelines/
    ├── before/
    ├── after/
    ├── unknown/
    └── trajectory_timeline_index.json
```

`selected_run/` 中保留选中运行生成的全部核心证据，仅排除官方 Skill bundle：`inputs/skills/**` 和旧 runner 的 `input-skill-bundle/**`。

## P/F 口径

- `PASS`：该条选中运行的任务级 verifier 判定通过（或旧 runner reward 为完整通过）。
- `FAIL`：运行本身有效、verifier 正常执行，但任务级结果未达到完整通过；部分分数也记为 FAIL。
- 基础设施错误运行不进入 P/F，不会被选为代表运行。

## 文件说明

- `MANIFEST.json`：87 条最终代表运行的来源、模型、condition、guard、rollout ID、P/F 与选择原因。
- `STATUS.csv`：面向人工快速查看的 87 行 P/F 汇总表。
- `EXCLUDED_RUNS.json`：自动筛掉的基础设施无效/无明确 P/F GPT-5.2 Original-Skill 候选运行及原因。
- `VALIDATION.json`：归档完成后的结构、P/F、轨迹数和 Skill bundle 泄漏检查。
- `trajectory_timelines/`：使用仓库统一的 `evaluation/results/export_trajectory.py` 生成的 Markdown 可读轨迹；原始 `trajectory/acp_trajectory.jsonl` 仍是 source of truth。
