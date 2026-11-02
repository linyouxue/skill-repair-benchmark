# Skill 修复实验数据与运行说明

数据分为两组，每组 5 题。第一组提供问题位置，让方法自行判断怎么修改；第二组先补好其他问题，只留一处待修，用来比较单点修复和多点修复的表现。Gold 指已有人工核验的完整修复版。

题目数据、Skill、Gold、检查器和运行脚本都在包内。运行时用 `export` 生成单次模型输入，Gold 和检查器留在本地评测使用。目前已完成数据构造和离线检查，模型重跑尚未进行。

## 1. 题目与实验设置

第一组从原始 Skill 开始，只提供位置提示。

| 题目 ID | 任务要求 | 修复点数 | 提示范围 |
|---|---|---:|---|
| `dialogue-parser` | 将对话文本转成节点、连线和图文件 | 1 | 添加连线、导出及 End 的处理 |
| `data-to-d3` | 制作股票气泡图和表格，支持悬浮提示与双向点击 | 1 | 图形上的文字层与点击联动 |
| `flink-query` | 从事件日志计算作业的最长提交阶段及其中的任务数 | 2 | 完成事件判定、结果输出资格 |
| `manufacturing-equipment-maintenance` | 分析回流焊温度数据，生成五类维护结果 | 2 | 交付完成条件、Q02 的代表热电偶选择 |
| `pddl-airport-planning` | 生成机场调度计划，并按要求保存 | 1 | 计划保存流程及保存接口的输入 |

例如，对话题的提示是“检查 Adding Edges、Export 以及 End 相关的处理约定”，具体处理方式由修复方法判断。中英文提示保存在 `datasets/catalog.json`。

第二组每次保留其他问题的 Gold 修复，撤回一处目标修复。

| 题目 ID | 修复点数 | 修复内容，按编号顺序排列 |
|---|---:|---|
| `manufacturing-equipment-maintenance` | 2 | 五个结果文件的交付；Q02 的 TAL 传感器选择 |
| `sec-financial-report` | 3 | 脚本路径；股票数量口径；跨季度持仓金额增幅排名 |
| `video-silence-remover` | 3 | 平滑后的时间对齐；区间合并；阈值调节 |
| `fix-build-google-auto` | 2 | 构建工具链与失败复现；嵌套 Maven 测试项目依赖 |
| `flink-query` | 2 | 完成事件类型；结果输出资格 |

文件名中的 `RI-001` 表示第一个修复点，`leave_RI-001` 表示留出这一点待修。同一个问题可能涉及多个文件或段落，构造时会一起处理。

第二组共 12 个留一版本，另有 5 个全缺陷对照。加上第一组，合计 22 个修复输入条件。两组有两题重合，底层共 8 个不同任务。

各方法使用相同的起始 Skill。若要在某个方法过去的失败产物上补入其他 Gold，需要另外核对那份产物，并单独记录这组实验。

## 2. 数据来源与文件

题目选自 [HumanAnnotated-Gold31-20260917](https://github.com/linyouxue/skill-repair-benchmark/tree/c9ca883d1af68fe12bb7e07275999543bd1cd963/evaluation/results/HumanAnnotated-Gold31-20260917)，原数据共 31 题、57 处标注，标注方式记录为 `human-verified-ai-assisted`。

| 内容 | 固定版本 |
|---|---|
| 原始 Skill、Gold 与标注 | `c9ca883d1af68fe12bb7e07275999543bd1cd963` |
| SkillsBench 题目、环境、参考解法和检查器 | `b63b7b2850226b6aa4fb5929a8c1ac7bc4d9a6af` |

原始 Skill 取自 Gold 仓库的 `evaluation/data/skillsbench87/originals/<task>/skills`。运行脚本会用当前实验条件中的 Skill 替换任务环境自带的副本。

| 路径 | 内容 |
|---|---|
| `datasets/catalog.json` | 题目、实验条件和提示清单 |
| `organizer/tasks/` | 原题数据、环境配置、参考解法和检查器 |
| `organizer/original_skills/` | 原始 Skill |
| `organizer/gold_skills/` | 完整 Gold |
| `organizer/conditions/` | 留一版本和全缺陷对照 |
| `organizer/annotations/`、`organizer/evidence/` | 原有标注和历史运行记录 |
| `organizer/repair_groups.json` | 修复点对应的文件及前后文本 |
| `organizer/provenance.json` | 来源、文件校验值和版本差异 |
| `tools/` | 导出、修复接入、执行和结果收集脚本 |

第一组直接使用原始 Skill。第二组从完整 Gold 撤回目标修复，将相关位置恢复为原始内容，同时保留其他修复。

有两题还包含不属于单个标注点的改动。视频题新增了执行完成检查；Google Auto 重写了整篇 Skill，删去了原来的通用 Maven 教程。这些改动在各自的留一版本和全缺陷对照中保持一致。因此，比较单点与多点修复时使用 `all_faults`；`original` 则保留真正的原始 Skill，供单独对照。具体差异见 `repair_groups.json`。

各文件的原有许可证一并保留。

## 3. 模型输入

每次用 `export` 导出一个条件，并使用新的会话和独立检索缓存。同题其他版本可能包含当前待修问题的答案，因此各次运行的输入和历史记录需要分开。

导出目录包含：

```text
prompt.md           原题要求
hint.txt            问题位置提示
skills/             本次待修的 Skill 和随附脚本
request.json        修复请求与输出格式
INPUT_SHA256.json   输入文件校验值
```

Gold、检查器和其他版本保留在评测端。内置 API 适配器只发送导出目录中的题目、提示和 Skill 文本。接入有文件读取能力的代理时，可在独立容器或机器上运行，只挂载单次输入目录和输出目录；单纯切换工作目录仍可能读到其他文件。

构造时已处理同一修复在不同段落、文件和脚本中的重复内容。原题原有的信息仍然保留，例如 SEC 的辅助脚本本身就包含部分正确计算逻辑，模型也可以从中推断修复方法。本包的检查范围是新增 Gold 内容的分组和可见范围，公开数据可能带来的预训练污染尚未评估。

## 4. 运行方法

列题、导出和离线检查使用 Python 3.9+ 标准库。执行原题需要 Python 3.12+、BenchFlow 0.6.5、Docker、模型访问配置和联网下载依赖的条件。Flink 使用 amd64 Java 路径，推荐在 Linux amd64 环境运行。

安装执行工具，并查看可用代理：

```bash
uv tool install --python 3.12 "benchflow==0.6.5"
bench agent list
```

包内带有题目数据，Docker 镜像和模型权重需另行准备。Google Auto 依赖下列镜像，其中包含项目、旧版 JDK 和工具链：

```bash
docker pull bugswarm/cached-images:google-auto-101506036
```

该镜像尚未在本次环境中完成拉取和构建验证。运行时记录实际镜像 digest，各方法使用同一版本。拉取失败单独记为环境问题。

在解压目录检查文件、查看题目：

```bash
python3 tools/package_release.py --check
python3 tools/runner.py list --dataset location
python3 tools/runner.py list --dataset single
```

以 Flink 的第一个修复点为例，将输入导出到包外的新目录：

```bash
python3 tools/runner.py export \
  --trial single-flink-query-RI-001 \
  --out ../run-input-001 --language zh
```

自己的修复方法按以下接口接入：

```text
YOUR_ADAPTER request.json output_directory
```

方法返回完整的 `output_directory/skills/`，包括未改动的文件；运行说明可写入 `response.json`。修改范围为 Skill 及随附脚本，题目、数据和检查器保持固定。

包内也提供了 OpenAI 兼容 Chat Completions API 的接入示例。先在本机设置 `OPENAI_API_KEY`、`OPENAI_BASE_URL` 和 `OPENAI_MODEL`，再运行：

```bash
python3 tools/runner.py repair \
  --input ../run-input-001 --out ../candidate-001 \
  --adapter python3 "$(pwd)/tools/openai_compatible.py"
```

`repair` 会切换到导出目录，因此适配器使用绝对路径。示例中的 `$(pwd)` 取当前解压目录。接口参数可通过 `python3 tools/openai_compatible.py --help` 查看。密钥通过环境变量传入。

这个示例用于跑通接入流程。比较 WML、Revise 等方法时，接入各自的修复实现。

修复完成后，用候选 Skill 执行原题：

```bash
python3 tools/runner.py prepare-eval \
  --trial single-flink-query-RI-001 \
  --candidate ../candidate-001 \
  --out ../eval-001

python3 tools/runner.py eval \
  --prepared ../eval-001 \
  --jobs ../results/experiment-001 \
  --agent YOUR_AGENT --model YOUR_MODEL \
  --method YOUR_REPAIR_METHOD --repair-model YOUR_REPAIR_MODEL
```

`YOUR_AGENT` 从 `bench agent list` 中选择。`YOUR_MODEL` 是执行原题的模型，`YOUR_REPAIR_MODEL` 用于记录修复模型，两者可以分别配置。检查器由 BenchFlow 在任务执行后使用。

若 BenchFlow 的任务元数据版本需要适配，可使用 `prepare-eval --help` 中的 `--metadata-key`。工具会记录这项改动及输入、候选文件的校验值；其他依赖和环境调整另行记录。

## 5. 对照与结果记录

正式比较前，在相同执行模型和预算下检查以下条件：

| 条件 | 用途 |
|---|---|
| `full_gold` | 完整 Gold 直接执行原题，确认当前设置下能否通过 |
| `original` | 原始 Skill 直接执行，查看历史问题是否仍会出现 |
| `condition_baseline` | 留一版本直接执行，确认缺少目标修复时的表现 |
| `all_faults` | 所有标注点均未修、其余改动固定，用于和留一实验比较 |

例如，准备完整 Gold 和留一版本的执行目录：

```bash
python3 tools/runner.py control \
  --task flink-query --condition full_gold --out ../gold-control

python3 tools/runner.py control \
  --task flink-query --condition condition_baseline \
  --trial single-flink-query-RI-001 --out ../heldout-control
```

这两份材料直接给执行器，省去修复环节。执行命令与前面相同，例如：

```bash
python3 tools/runner.py eval \
  --prepared ../gold-control --jobs ../results/gold-control \
  --agent YOUR_AGENT --model YOUR_MODEL
```

如果某个留一版本未经修复就能通过，应将这项结果单独列出，修复后的通过率也要结合它解释。完整 Gold 若无法通过，则先检查环境、预算和 Gold 对当前设置的适用性。

结果记录分为三项：原题是否通过、目标问题是否修好、其他已提供的修复是否保留。等价的修复方法都可以接受，判断依据是规则和执行行为。人工复核表头在 `organizer/score_template.csv`。

每个方法一轮完整实验包括第一组 5 次、第二组 12 次留一修复和 5 次全缺陷修复。同一执行配置下的对照结果可以跨方法复用。运行次数和重复次数按预算安排，执行超时设置见各题 `task.md`。

如果各单点都能修好，而全缺陷版本失败，可以进一步检查修复顺序、多点组合和预算分配。同时需要考虑留一输入已更接近正确答案、提示数量不同和运行随机性等因素。任务通过也可能来自执行模型自行绕过缺陷，因此还需查看候选 Skill 和实际执行记录。

收集结果：

```bash
python3 tools/runner.py collect --runs ../results --out ../results-summary.json
```

一个结果目录使用同一套实验设置。`collect` 按任务、条件、方法、修复模型、执行代理和执行模型分组；预算、推理强度、镜像或温度/种子策略不同的实验，放在不同目录汇总。

保留输入、候选 Skill、执行目录、日志和 API 用量，并记录模型版本与预算。工具不会自动设置温度或种子，未设置或不支持时如实填写。执行命令和文件校验值会自动保存。

## 6. 验证记录

已完成的离线检查包括：455 个来源文件的校验、28 种修复组合的正反向重构、17 个条件目录、22 个单次输入、8 项工具测试，以及 8 个任务的 BenchFlow 结构检查。结果保存在 `organizer/release_validation.json` 和 `organizer/independent_review.json`；后者为自动交叉审查记录。

历史 Gold 的通过记录对应原来的模型、预算和流程。Flink 的历史结果同时标记了 `task_passed=true`、`comparable=false` 和 `protocol_evidence_valid=false`，属于带额外执行保障的诊断运行。回流焊、机场规划等题的原始失败记录也有协议差异，详细信息保存在 `organizer/evidence/` 和来源清单中。

新构造的留一版本仍需按本次实验设置重跑。原题检查器覆盖的是任务验收要求，目标修复是否成立还需结合 Skill 差分和执行记录核对。

可以再次运行离线检查：

```bash
python3 -B tools/validate_release.py
# 已安装 BenchFlow 时，额外检查任务配置：
python3 -B tools/validate_release.py --bench-check
```
