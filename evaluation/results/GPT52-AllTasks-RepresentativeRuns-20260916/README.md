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

### 需要先处理然后再运行的任务

- **enterprise-information-search**：运行时去掉任务说明里面的"tokens":"xxx"中的"",verifier与任务说明冲突,应该是xxx而不是"xxx"
- **simpo-code-reproduction**：请在运行 simpo-code-reproduction 前统一修复 verifier 的依赖缺失：在该任务 verifier/test.sh 的 uvx fallback 分支依赖列表中，新增一行 --with rich==11.2.0 \，确保 
verifier 自建的 Python 3.10 环境能够导入 trl.trainer 所需的 rich
- **organize-messy-files**:请把verifier中test_no_allowed_files_outside_subject_folders这个函数换成下面这个函数
```python
def test_no_allowed_files_outside_subject_folders():
    """No expected task-input files should exist outside the five subject folders."""
    subject_root = find_subject_root()
    allowed_roots = {subject_root / subject for subject in SUBJECTS}
    excluded_root = Path("/root/papers/all")

    # Only task-owned input files are relevant to this assertion.
    expected_names = {
        normalize_filename(name)
        for name in FILE_TO_SUBJECT
    }

    stray = []

    for path in Path("/root").rglob("*"):
        if path.is_dir() or path.suffix.lower() not in ALLOWED_EXTENSIONS:
            continue

        # Ignore unrelated PDF/DOCX/PPTX files belonging to the runtime,
        # installed packages, temporary environments, etc.
        if normalize_filename(path.name) not in expected_names:
            continue

        # The unsorted source directory is checked separately by
        # test_no_leftover_expected_files_in_unsorted_folder().
        if excluded_root in path.parents:
            continue

        if not any(
            root in path.parents or path.parent == root
            for root in allowed_roots
        ):
            stray.append(str(path))

    assert not stray, (
        f"Found expected task-input files outside subject folders: {stray[:10]}"
    )
```
- **jpg-ocr-stat**:运行的时候可以把调用最大次数从60改成65

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
## 未入 Gold 的 8 题

| 任务 | 当前状态 |
|---|---|
| `civ6-adjacency-optimizer` | 存在评测/任务定义问题，见下一节；不能自动转化为 Skill Gold |
| `financial-modeling-qa` | 存在评测/任务定义问题，见下一节；不能自动转化为 Skill Gold |
| `invoice-fraud-detection` | 存在评测/任务定义问题，见下一节；不能自动转化为 Skill Gold |
| `manufacturing-codebook-normalization` | 存在评测/任务定义问题，见下一节；不能自动转化为 Skill Gold |
| `quantum-numerical-simulation` | 存在评测/任务定义问题，见下一节；不能自动转化为 Skill Gold |
| `setup-fuzzing-py` | 存在评测/任务定义问题，见下一节；不能自动转化为 Skill Gold |
| `shock-analysis-demand` | 存在评测/任务定义问题，见下一节；不能自动转化为 Skill Gold |
| `xlsx-recover-data` | 存在评测/任务定义问题，见下一节；不能自动转化为 Skill Gold |

## 未入 Gold 任务的 verifier / 任务定义问题

### 1. invoice-fraud-detection

**判定：修复所需的关键规则未公开，需借助 verifier 判分信息才能确定修复方向。**

- **公开要求/输入**：题面只说明 PO 缺失时填 `null`，没有说明非空的 `PO-INVALID` 也必须转为 `null`。发票第 4、8、15、38、45 页实际包含该字符串，保留原始字段是公开要求下的一种合理处理。
- **verifier 揭示的要求**：verifier 对 `po_number` 做精确比较，ground truth 将上述页记为 `null`。通过判分信息才能确定，本题所要求的修复是把 `PO-INVALID` 转为 `null`，而不是继续保留原字符串。
- **为什么影响 Skill 修复评估**：修复方法看不到 verifier 时，很难仅凭题面、发票和原始 Skill 判断必须增加这条特殊处理；即使注意到 PO 无效，也无法唯一确定应保留原文、标记无效，还是置为 `null`。利用 verifier 的期望值补入该规则，属于利用隐藏验收信息确定修复方向，不能直接当作从公开材料独立发现的 Skill 缺陷。
- **当前状态及处理边界**：未入 Gold。应先在公开任务规范中明确 `PO-INVALID` 的输出处理，再让看不到 verifier 的修复方法评估和修改 Skill；不宜直接把隐藏的 `PO-INVALID → null` 规则加入 Skill 后，声称完成了无 verifier 信息辅助的修复。


### 2. xlsx-recover-data

**判定：verifier 使用了错误的恢复目标，把符合原表计算逻辑的答案判错；不能把迎合这个错误目标当作 Skill 修复。**

**任务背景。** 这题要求恢复 Excel 中丢失的数据，恢复值应与原工作簿的业务含义、相邻单元格和计算规则一致。争议点是 `Growth Analysis!B8` 的年度平均值：该行涉及 FY2019–FY2024 六个年度，同一行其他部门也按六年计算。

**verifier 具体错在哪里。** 官方数据生成脚本和 `answers.txt` 给出的恢复值为 `7610.3`，但 oracle 与 verifier 使用了只覆盖 FY2019–FY2023 的五年平均 `7444.4`，漏掉 FY2024。这里不是小数精度或四舍五入问题，而是参与平均的年份范围不同。六年原始数值是 `6906、7139、7301、7614、8262、8440`，六项平均为 `7610.3`；只取前五项才得到 `7444.4`。

**为什么当前不能进入 Gold。** 修复方法依据原表的六年布局恢复 `7610.3`，仍会被当前 verifier 拒绝。只有获知错误的判分目标，才可能刻意少算一年以通过；这样的改动会背离原数据逻辑，不能算作修复官方 Skill 的能力提升。此处也不能笼统说“官方答案一致”：生成脚本/answers 与 oracle/verifier 本身就不一致。

**应先处理什么。** 统一工作簿生成逻辑、参考答案和 verifier 的年份范围，使用同一六年平均目标，再重新评估 Agent 的恢复结果和原始 Skill 是否存在独立缺陷。当前不将这次目标值冲突转化为 Gold RI。

### 3. financial-modeling-qa

**判定：任务输入缺少影响结果的关键记录，oracle 私下补值，verifier 却要求唯一答案；公开材料不足以支撑这个验收目标。**

**任务背景。** 这题要求根据工作簿中的游戏记录和背景规则计算胜场差。要得到唯一结果，参与计算的回合数据必须完整。但公开工作簿 `Data!C24:J24` 为空，缺少 Turn 15；对应的 Game 8 只有 Turn 16。

**verifier 具体错在哪里。** oracle 没有依据公开的恢复规则处理缺失，而是直接补入 `Turn 15 / Game 8 / [4,6,4,2,4,5]`。verifier 随后固定要求答案为 `23`。这组六个骰子值没有提供给 Agent，题面也没有规定缺失时应使用它们。因此，“23”实际上依赖于隐藏补值，而非只依赖公开工作簿。

**为什么这不是普通计算失误。** 先前只读审计确认工作簿有 5999 条有效 turn，缺失集合为 `{15}`。将缺失的六个骰子枚举为全部 `6^6=46656` 种合法组合后，最终答案可能是 `23、24、25`：三者分别对应 14100、810、31746 种组合。这说明缺失记录确实会改变结果，不能从已提供数据唯一推出 `23`；反过来，也不能直接把 `25` 宣称为唯一正确答案。

**为什么当前不能进入 Gold。** 看不到 oracle/verifier 的修复方法无法恢复这组特定隐藏骰子值。若把隐藏补值或最终答案写入 Skill，得到的是答案信息辅助，而不是可从公开输入发现的 Skill 缺陷修复。应先补齐真实缺失记录，或公开确定的缺失处理规则，再重新生成参考结果和验证；在此之前，不以“没有输出23”为依据构造 Gold RI。

### 4. setup-fuzzing-py

**判定：verifier 一方面拒绝题面允许的路径表示，另一方面没有一致地复用交付环境；两类失败都不能直接归因于 Skill。**

**任务背景。** 这题要求发现五个 Python 库、记录它们的路径，并在各库根目录的 `.venv` 中准备依赖和运行 fuzzer。验收应检查是否找到正确目录，以及提交的 fuzzer 能否在约定环境中运行。

**问题一：把路径检查写成名称精确匹配。** `test_discovery` 使用 `assert lib in lines`，期待某一行恰好是 `arrow` 等库名。Agent 写出 `/app/arrow` 时，虽然给出了明确的库路径，仍会因字符串不相等而失败。题面要求的是 path，没有公开规定只能提交裸目录名；verifier 没有先将绝对/相对路径规范化后再比较。

**问题二：复验时换了依赖环境。** 对 `minisgl`，verifier 使用 `uv run --with atheris==3.0.0 --no-project`，没有直接使用已交付的 `.venv`，也没有像其他库一样通过 `--with .` 加入项目。历史记录中，fuzzer 在交付环境运行成功，换到该复验环境后出现 `ModuleNotFoundError`。这说明失败至少涉及 verifier 创建的环境缺少项目依赖，不能仅凭这个异常认定 Agent 未安装依赖。

**为什么当前不能进入 Gold。** 在看不到 verifier 时，修复方法难以推断“path 必须写裸库名”，也没有理由用 Skill 去补偿某个库独有、未公开的复验命令。把这些特殊处理写进 Skill 会把验收实现问题包装成原始 Skill 缺陷。

**应先处理什么。** 统一路径规范，并使复验使用题面约定的交付环境，或公开可重复的独立安装协议。修复后重新测试；这两个问题不意味着全部 fuzzer 已经正确，也不免除其他真实实现错误。

### 5. manufacturing-codebook-normalization

**判定：verifier 用不适合连续中文的词面重合指标代理语义支持，可能拒绝有依据的 codebook 映射。**

**任务背景。** 这题要把制造现场的非标准描述映射到规范 codebook。输入可能含错字、缩写和中英混写，所以核心要求是理解描述含义，再选择相应标准代码，而不是简单逐词复制词典。

**verifier 具体错在哪里。** T11 使用 token 集合的 Jaccard 重合度衡量预测是否受到原文支持，要求至少 70% 的 known 预测达到 `overlap >= 0.01`。但它的 `TOKEN_RE` 只按非中英数字字符切分，不会对连续中文做词语分割。长中文描述会被视为一个整体 token，即使里面包含 codebook 的原样关键词，也可能与词典短 token 完全不相等。

**直观例子。** 仅为解释机制，假设原文是“设备出现接触不良”，词典关键词是“接触不良”。原文整体 token 与词典 token 不相等，集合交集可以为空，于是 overlap 为 0；但人可以直接从原文找到同一个故障词。先前审计在真实输入中也发现了这类“含原样关键词却零重合”的情况，因此不是只存在于假设例子中的风险。

**为什么当前不能进入 Gold。** 在该测试下，失败不一定表示映射没有语义依据。如果根据隐藏 tokenizer 的行为要求 Skill 改写文本、插入分隔符或迎合词面重合，就把修复目标从“正确理解制造描述”变成了“通过特定分词器”。因此当前不能仅凭 T11 不通过就构造可靠的 Skill Gold。

**应先处理什么。** 让支持度检查能够识别中文词组、原文子串或经验证的语义对应关系，并用人工确认的正反例检验误判。模型本身仍可能存在分段、选错代码和消歧错误；修 verifier 后应逐项复核，不把所有失败一并豁免。

### 6. civ6-adjacency-optimizer

**判定：verifier 的格式检查与核心评估器、官方参考产物互相矛盾；连官方 oracle 的输出也不能满足全部检查。**

**任务背景。** 这题围绕《文明 VI》的区域布局和相邻加成进行优化，需要提交区域的位置及相邻加成结果。同一种区域是否可以有多个位置、坐标如何表示，必须在输出规范和各层测试之间保持一致。

**verifier 具体错在哪里。** 官方 `scenario_3` reference 将 `NEIGHBORHOOD` 表示成六个坐标的列表，核心 evaluator 的 `_normalize_coords` 也支持这种多坐标表示。但外层 `test_placements_have_coordinates` 要求每个 district 的 `coords` 长度必须为 2，且两个元素都是数字，也就是只接受单个 `[x, y]`。

**为什么构成直接冲突。** 一个区域提交多个合法坐标时，核心 evaluator 可以处理，格式检查却先拒绝；按官方 `oracle/solve.sh` 生成参考 JSON，也会遇到这个矛盾。这不是 Agent 选址不好或优化分数不够，而是不同测试层对同一字段采用了不同的数据结构。参考产物另有一个独立问题：包含 `CANAL` placement，却没有对应的 `adjacency_bonuses`。

**为什么当前不能进入 Gold。** 修复方法无法从互相矛盾的规范中得到稳定的正确提交方式；按多坐标参考实现可能被格式门拒绝，为了格式门强行改成单坐标又可能丢失布局信息。不能把适配这种内部冲突当成官方 Skill 的独立缺陷修复，也不能把 reference 漏字段归咎于 Agent。

**应先处理什么。** 明确每类区域允许的数量与坐标结构，统一格式检查、核心 evaluator 和 oracle，再补齐参考产物的加成字段。以官方参考产物能通过完整验收为基础，重新评估真正的布局/求解能力问题。

### 7. quantum-numerical-simulation

**判定：verifier 比较的参考结果来自另一套耦合强度，遵守题面方程的实现也可能被判错。**

**任务背景。** 这题要求根据给定的量子系统方程进行数值模拟，并提交相应的 Wigner 数组。数组是否正确，取决于实际使用的哈密顿量；即使网格、形状和数值精度都正确，只要相互作用系数不同，就不是同一个模拟问题。

**verifier 具体错在哪里。** 题面相互作用项写成 `g(a†+a)(J+ + J−)`，并指定 `g=2/sqrt(N)`。但 oracle/reference 的预计算使用 `g(a†+a)Jx`。由于 `Jx=(J+ + J−)/2`，在保持同一个 g 时，参考计算的相互作用强度只有题面的一半。若用 Jx 实现题面方程，应对应 `2g(a†+a)Jx`，而不是参考中的 `g(a†+a)Jx`。

**为什么影响验收。** verifier 拿预计算的 Wigner 数组作为目标，而目标本身由不同方程产生。因此失败可能来自参考方程不一致，而非 Agent 的数值算法有错；这也不是单纯增大容差就能合理解决的浮点误差。

**为什么当前不能进入 Gold。** 不读取隐藏参考实现的修复方法没有理由把题面耦合强度主动减半。若通过 Skill 加入这个半系数来换取通过，实际上是在教 Agent 偏离公开方程，不能作为可靠的 Skill 修复真值。

**应先处理什么。** 确定任务真正要使用的方程，统一题面、oracle 和预计算程序，并重新生成参考数组后验收。历史 Agent 还出现过数组形状和 NaN 等独立问题，这些仍应检查；指出参考方程错误不等于宣布原提交整体正确。

### 8. shock-analysis-demand

**判定：任务没有提供完整布局和唯一分配规则，verifier 却按隐藏答案的固定单元格与固定比例验收。**

**任务背景。** 这题要求在 Excel 中建立需求冲击分析模型，整理宏观数据并把项目投入按年度分配。题面使用“填入 WEO_Data 相关行”“SUT Calc C–H/C46”等措辞，像是在现成模型模板上补全内容；但实际输入工作簿只有 `NA` 一个 sheet，大小为 33×11，没有相应工作表布局。

**问题一：隐含了未提供的模板。** Agent 可以自行创建缺少的 sheet，但无法仅凭不存在的模板确定隐藏答案采用的每个固定行列。oracle 直接复制完整的 `answer_demand.xlsx`，verifier 又要求特定位置的结果。缺表本身不代表无法建模，问题在于验收把未完整公开的布局当成了唯一标准。

**问题二：把“钟形分配”当成唯一数列。** 题面只说项目分配是 bell shape，没有给出八年具体权重或生成算法。verifier 却固定检查 `NA!D9:D16` 为 `[0.05, 0.10, 0.15, 0.20, 0.20, 0.15, 0.10, 0.05]`。例如 `[0.02, 0.08, 0.17, 0.23, 0.23, 0.17, 0.08, 0.02]` 同样对称、向中间集中且总和为 1，却不符合这一隐藏数列。

**为什么当前不能进入 Gold。** 看不到 verifier/answer 的修复方法无法唯一推断指定权重和全部布局。若把隐藏单元格结构、具体八年比例直接写进 Skill，再以通过为依据认定修复成功，混入的是答案规范信息，而非从公开材料发现的原始 Skill 缺陷。

**应先处理什么。** 提供完整模板和明确的分配权重/计算算法；若允许多种钟形方案，verifier 应检查公开的形状、总和与模型计算一致性，而非只认一份答案。历史 Agent 长时间检索、未完成建表等执行问题仍独立存在，但当前不能用隐藏布局/权重造成的失败作为 Gold 归因依据。

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
