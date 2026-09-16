# Official Skill 基线 —— Core-22 代表性运行结果

本目录归档了人工验收过程中使用的 22 个 SkillsBench 任务，每个任务保留一条具有代表性的执行记录。

本目录属于**执行证据归档**，不是某个 Skill 修复方法的提交结果，因此不会包含 `submission.json`，也不会包含任何修复后的 Skill bundle。

## 运行选择规则

- 每个任务选取的代表运行必须与 `VALIDATION.json` 中人工确认的 PASS/FAIL 标签一致。
- 如果存在结果一致的 completion guard 运行，优先使用 guard 运行。
- 如果没有结果一致的 guard 运行，则使用对应的非 guard 运行。
- 对选中的运行，保留完整的运行证据，包括：
  - executor / result / config 等元数据；
  - 原始模型执行轨迹；
  - trainer 导出结果；
  - verifier 输出；
  - artifacts（若该运行实际生成）；
  - timing / reward 等运行信息；
  - 能够对应到该次运行的外层日志。
- **不上传官方 Skill bundle 内容**。具体而言，本目录明确排除：
  - `inputs/skills/**`
  - 旧版 runner 中的 `input-skill-bundle/**`

`MANIFEST.json` 用于记录每个任务代表运行的来源及 provenance。

`VALIDATION.json` 用于记录每个任务的人工验收结果、实际运行结果以及二者是否一致。

`STATUS.csv` 提供一份便于快速查看的表格化汇总。

## 目录结构

```text
OfficialSkillBaseline-Core22-20260916/
├── README.md
├── MANIFEST.json
├── VALIDATION.json
├── STATUS.csv
├── tasks/
│   └── <task-id>/
│       ├── run_selection.json
│       └── original_run/
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
│           ├── artifacts/                 # 存在时保留
│           ├── logs/                      # 存在对应运行日志时保留
│           └── run_metadata/              # 仅用于旧版 runner 的必要元数据
└── trajectory_timelines/
    ├── before/
    ├── after/
    ├── unknown/
    └── trajectory_timeline_index.json
