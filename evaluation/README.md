# Skill 诊断与修复细粒度评测

> [!IMPORTANT]
> **跑任务的首要规则：先确认运行有效，再判断 PASS / FAIL。**
>
> 只有基础设施完整正常、模型请求成功获得响应、OpenHands / 工具链正常运行、verifier 正常执行的 rollout，才算有效运行。
>
> **任何 provider 连接失败、API 429 / 5xx、Docker / 环境启动失败、工具通信中断、依赖下载失败等基础设施问题，都不计入 PASS / FAIL，也不计入 Verified Fix Rate 的分子或分母。问题修复后，必须重新运行完整 rollout。**
>
> 本文“执行无报错但无判决时按任务失败计分”的规则，仅适用于满足上述有效运行前提的情况。基础设施故障导致的无响应、无判决或任务未完成，不能按任务失败计分；应保留故障记录，修复问题后以新的 rollout ID 重新运行。
>
> 关于 task / verifier 的网络与代理：
> 需要区分模型 API、task 环境依赖和 verifier 依赖三条网络路径。服务器宿主机上的 HTTP_PROXY/HTTPS_PROXY 主要用于模型 provider 等宿主侧网络请求，并不意味着 task 容器或 verifier 会自动继承同一代理。
> 部分 SkillsBench task 在环境准备或执行过程中可能通过 pip、uv、apt、GitHub 等获取额外依赖，该阶段目前不会自动注入 executor 的 verifier-only proxy。
> 这类依赖如果下载出现问题可以优先尝试使用清华镜像等国内镜像，或者提前缓存/预构建 Docker 镜像。
> verifier 如果自身需要联网安装依赖，可以使用 executor 提供的 verifier-only proxy。该代理默认关闭，只在最终 sandbox test-script verifier 进程中临时注入。
> llm-judge 等宿主侧 verifier 不使用这个代理，需要走其自身的模型/provider 网络配置。

同学可在自己的机器上完成全部评测：准备诊断和最终 Skill bundle，使用统一 executor 运行任务，再由本脚本读取本地运行目录，生成 Diagnosis/Repair P/R/F1、Location Accuracy、Regression 和 Verified Fix Rate。Gold 由组织者维护，大模型按照固定判据判断语义，Python 负责校验、计数和计算指标。无需将运行文件交回组织者处理。

当前默认 Gold 为 `evaluation/data/core25/gold.json`，由统一人工 Gold repair 清单转换，包含 **7 个任务、14 个 defect（Core-25 当前已整理子集）**。不指定 `--gold` 时直接使用它；真实提交的 `benchmark_version` 应为 `core25-gold-defects-20260909-v1`。数据说明、来源边界和对应提交模板见 [数据说明](data/core25/README.md) 与 [提交模板](data/core25/submission.template.json)。这不是完整的 Core-25 Gold；扩展集尚未发布。下文 `examples/` 的 `v1` 是独立教学样例，使用时须显式指定其 `--gold`。

本版本采用讨论后简化的协议：**诊断按缺陷一对一匹配；修复按缺陷做二值判断，不计算文本相似度，也不计算 Condition Coverage。** Regression 单独报告。另在最终报表中汇总 executor 真实运行的 **Verified Fix Rate**；语义评分和实际任务通过率分别报告，评测器本身不运行任务。

## 与 executor 的关系及运行环境

本目录是独立的内容评测工具，通过读取文件和裁判响应计分，不导入或修改 `benchmark_executor`，也不调用 Docker 或运行 task。现有 executor 负责生成真实运行证据，入口和运行协议保持原样。真实任务通过率与本工具的 Diagnosis/Repair 指标分别报告。

离线检查与计分仅需 Python 3.12+ 标准库，可在 Windows、Linux 或 macOS 运行；测试另需 `pytest`。调用在线裁判才需要 `openai` SDK。可以在独立 Python 环境中安装 `openai`；已配置好 executor 环境的同学也可使用仓库已有的 `judge` extra。无需为离线计分安装或启动 executor。

## 同学在本地完成全部评测

1. 获取本仓库、约定的 SkillsBench 任务源和统一实验配置。仓库已包含本版 Gold、Original/reference 快照及提交模板；完整任务数据、verifier、Docker 环境和本人的 API key 按 [executor 安装与接入指南](../DELIVERY_GUIDE.md) 配置。
2. 复制并填写 [提交模板](data/core25/submission.template.json)，保存自己的逐项诊断与完整 Final Skill。方法生成诊断、修复时只使用规定的任务输入；Gold 供后续评分使用。
3. 用现有 `BenchmarkExecutor.run()` 执行冻结的最终 Skill，条件为 `method-skill`，`method_id` 与提交文件一致。保留完整输出目录 `jobs_root/<method_id>/<rollout_id>/`。若要使用原始通过跳过机制，先以同一方法 ID、模型和协议运行 `original-skill`，通过后填写下面的 `original_pass` 行。具体运行示例见 [Python API 接入](../DELIVERY_GUIDE.md#5-入口-b修复算法自动调用)。
4. 指定本地运行目录，执行下面的评测命令。`--executor-runs-dir` 自动查找对应运行、核验 Original-pass 标记并汇总 Verified Fix Rate，不需要手写结果清单或申请组织者批准。

以下命令在仓库根目录运行，先配置 `OPENROUTER_API_KEY`；它会调用 GPT-5.5 裁判。将路径换成自己的路径，输出目录必须不存在或为空：

```bash
python evaluation/scripts/evaluate_skill_diagnosis_repair.py --submission path/to/submission.json --executor-runs-dir path/to/jobs/method_a --output .cache/skill-evaluation/method-a --execute --judge-model openai/gpt-5.5 --omit-temperature --reasoning-effort medium --max-input-chars 2000000
```

完成后直接查看本机输出目录中的 `summary.json` 或 `summary.csv`，所有指标并列报告。`benchmark_result.json` 和 `executor_request.json` 由 executor 自动生成，本脚本自动读取；**组织者不用提供这两个文件，同学不用手工填写或回传它们。** `executor-results.json` 也由脚本自动生成在本次输出目录中。

Verified Fix Rate 必须来自实际运行过的 verifier，不能仅凭 Gold 或修复文本生成。这个评测命令不会自动补跑任务：缺少运行会明确报告 `missing_result` 和覆盖率，不会悄悄发起 rollout。已有裁判响应时，将 `--execute` 和模型参数换成 `--judge-responses path/to/judge_responses.json`，即可在本地离线重计全部指标。

## 快速检查本版 Gold

以下命令在仓库根目录运行，默认读取已发布的 7 任务 Gold，检查 Gold 预测及参考修复的文件输入并生成 14 个独立请求；**不调用模型、不产生分数**：

```bash
python evaluation/scripts/evaluate_skill_diagnosis_repair.py --submission evaluation/data/core25/submission.gold-reference.json --output .cache/skill-evaluation/core25-reference-dry-run --max-input-chars 2000000 --dry-run
```

开始正式评测时，复制并填写 [提交模板](data/core25/submission.template.json)，将 `--submission` 换成方法自己的提交路径。先按第 4 节验证离线示例，再按第 5 节显式开启在线裁判。输出目录应为新目录或空目录。

## 1. 同学提交什么

同学在本地准备 `submission.json`；正常评测任务还需准备完整修复后目录。提交必须包含 Gold 的全部任务，每个任务恰好一条记录，不需要知道 Gold 的 `defect_id`，也不需要自己填写评分或修复正确性。

```json
{
  "method_id": "method_a",
  "benchmark_version": "v1",
  "tasks": [
    {
      "task_id": "example-task",
      "diagnoses": [
        {
          "prediction_id": "P1",
          "description": "说明问题对象以及错误机制。",
          "locations": [
            {"file": "skill-a/SKILL.md", "section": "区间合并"}
          ]
        }
      ],
      "repaired_bundle": "repaired/skills"
    }
  ]
}
```

- 正常评测任务必须提供 `diagnoses` 数组，缺失或填写 `null` 都属于输入错误。
- 正常评测任务填写 `diagnoses: []`：没有诊断预测，该任务的全部 Gold 缺陷计为 FN；不能仅凭空数组跳过诊断评测。
- 诊断应逐项描述独立缺陷。`locations` 是位置证据，不能代替缺陷描述。
- `repaired_bundle` 指向最终完整目录，包含需要的脚本和参考文件。没有修改就提供与原始内容相同的目录。
- `repaired_bundle` 只能使用 `submission.json` 所在目录内部的相对路径，不能使用绝对路径、逃逸到该目录之外，或通过软链接及 Windows junction 引用其他内容。bundle 内也不能包含这些链接。
- 位置中的 `file` 相对于 bundle 根目录。
- 使用 `--executor-runs-dir` 时，若同一 Final 有多次运行，可增加 `executor_run_id` 指定本轮使用的 rollout ID，例如 `"executor_run_id": "dialogue-parser-final-trial-1"`。不填写时只能自动选中唯一匹配；脚本不会按是否通过或时间先后挑选运行。

### 原始运行已通过的任务

如果同学使用原始 Skill 的运行已经通过，可在提交中标记跳过该任务的诊断与修复评测：

```json
{
  "task_id": "example-task",
  "original_pass": true,
  "original_run_id": "run-001"
}
```

此行仍须保留在 `tasks` 中。`diagnoses` 可以省略或为 `[]`，不能为 `null` 或非空数组；`repaired_bundle` 必须省略。使用 `--executor-runs-dir` 时，脚本在本地查找该 `original_run_id`，检查它使用 `original-skill`、`execution_ok=true`、`task_passed=true`，并核对 `inputs/skills/` 与 Gold Original 逐字节一致、`result.json` 中的实际 Skill 预载证据一致。应保留该次运行的完整目录；单独填写 `original_pass: true` 不能跳过。

成功核验后状态为 `skipped_original_pass`，不调用裁判，也不将原始运行通过当成一次正确诊断或成功修复。同学在本地完成这些检查，无需组织者另行提供核验清单。

## 2. 评测组织者准备什么

组织者提供原始 bundle、`gold.json` 和统一实验配置，Gold 只标注原始 Skill 已存在的问题。当前发布的 7 任务相关文件已在仓库内，同学可直接用它们在本地评分。Gold 与验收要求是评测输入，不作为参评方法的修复输入。各方法的运行产物由同学本地 executor 生成，不需要组织者预先收集或代为评分。

`original_bundle` 属于组织者的可信输入，可使用相对于 `gold.json` 的路径，也可使用外部或绝对路径；它与参评者提交的 `repaired_bundle` 路径限制不同。

```json
{
  "benchmark_version": "v1",
  "tasks": [
    {
      "task_id": "example-task",
      "original_bundle": "original/skills",
      "defects": [
        {
          "defect_id": "D01",
          "description": "错误合并存在正长度间隔的区间。",
          "locations": [
            {"file": "skill-a/SKILL.md", "section": "区间合并"}
          ],
          "repair_requirement": "只允许合并重叠或首尾相接的区间；存在正长度间隔时必须分开。"
        }
      ]
    }
  ]
}
```

`repair_requirement` 是完整修复的验收要求，可以描述多项必要行为，但最终每个缺陷只有一个正确/不正确的修复判定。不同措辞、不同实现只要等效地满足要求，都可判为正确。

### 兼容旧流程：手工指定原始通过核验清单

以下保留此前由组织者核验的清单格式，供已有实验重放使用。**本地自动流程不需要此文件**，直接使用 `--executor-runs-dir`。只有选择旧流程时，才使用 `--verified-original-passes PATH` 单独提供核验清单：

```json
{
  "method_id": "method_a",
  "benchmark_version": "v1",
  "protocol_id": "original-v1",
  "runs": [
    {
      "task_id": "example-task",
      "run_id": "run-001",
      "passed": true,
      "execution_ok": true,
      "original_bundle": "original/skills",
      "verifier_report": "evidence/run-001-verifier.json"
    }
  ]
}
```

这里的两个路径相对于核验清单。`original_bundle` 指向该次运行实际使用的 Original 输入快照；`verifier_report` 指向非空的执行证据文件。脚本检查 method/version 一致、清单任务集合与跳过申请恰好一致、run ID 匹配且唯一、`passed` 与 `execution_ok` 均为 `true`、输入快照的文件集合与字节和 Gold Original 完全一致，以及证据文件存在且非空。不满足条件属于输入错误，不会静默跳过或按零分处理。

这个兼容入口仍使用组织者核验并指定的清单，不将手填 `passed: true` 当作自动验证。本地新入口改为读取 executor 的实际报告、请求、Original 输入快照和预载记录；两种入口不能同时使用。无论使用哪种入口，都应保留 Gold 的历史缺陷和标注证据，不因某次原始运行通过而删除 Gold。

## 3. 如何计分

汇总采用 micro 口径：先将参与评测任务的 TP、FP、FN 分别相加，再计算 Precision、Recall 和 F1，不对任务分数直接取平均。任何公式的分母为零时输出 `null`。例如，参与评测的 Gold 非空但完全没有修复尝试、也没有额外有害修改时，Repair Recall 和 F1 为 `0`，Repair Precision 为 `null`。

核验通过的跳过任务不计入 TP、FP、FN、Location Accuracy、Regression 或置信度统计。其余任务照常评测。因此，这些 P/R/F1 是**排除已核验原始通过任务后的条件指标**；不同方法跳过的任务集合不同，不能仅凭条件 F1 直接排名，须同时报告任务集合和跳过比例。全部任务都跳过时，状态为 `complete`、退出码为 `0`，评测指标为 `null`，而不是满分。

### Diagnosis

按问题对象与错误机制将预测和 Gold 一对一匹配，位置仅作辅助。一个预测不能命中多个 Gold，一个 Gold 不能给多个预测重复得分。

- `TP_d`：正确匹配的缺陷数。
- `FP_d`：未正确匹配的诊断预测数。
- `FN_d`：未匹配到的 Gold 缺陷数。
- `Precision_d = TP_d / (TP_d + FP_d)`。
- `Recall_d = TP_d / (TP_d + FN_d)`。
- `F1_d = 2 × TP_d / (2 × TP_d + FP_d + FN_d)`。
- `Location Accuracy`：正确诊断匹配中，位置判断正确的比例。

### Repair

对非跳过任务的每个 Gold 缺陷分别判断 `repair_present`（是否进行了针对性修复）和 `repair_correct`（最终是否完整修好）。修复判断独立于诊断匹配，即使诊断未命中，也可在最终内容确实修好时得到修复分。

- `TP_r`：完整修好的 Gold 缺陷数。
- `FN_r`：未完整修好的 Gold 缺陷数。
- `FP_r`：尝试但失败的 Gold 缺陷数，加上 `harmful_or_unsupported` 的额外修改项数。
- `Precision_r = TP_r / (TP_r + FP_r)`。
- `Recall_r = TP_r / (TP_r + FN_r)`，即完整缺陷修复率。
- `F1_r = 2 × TP_r / (2 × TP_r + FP_r + FN_r)`。

未尝试修复的 Gold 只计 FN；尝试但没有完整修好的 Gold 同时计 FP 和 FN。一个缺陷相关的多处修改只算一次尝试。只有一部分要求满足仍属于失败，不另外计算条件覆盖分。

对 Gold 之外的修改，按独立修改目的归并后分类：

| 分类 | 处理 |
| --- | --- |
| `benign` | 无害编辑或等价重构，不计 FP |
| `possible_new_defect` | 可能修复了 Gold 漏标的原始问题，记录供后续复核，不立即计 FP，也不立即增加 TP |
| `harmful_or_unsupported` | 有害修改或确认不成立的修复，每个独立项计 1 个 FP |

修改目的决定计数，不按行数或文件数计算。`possible_new_defect` 作为非阻塞记录，供下一版统一 Gold 使用；不要只给某个方法临时增加 Gold 得分。

### Regression

裁判结合原始与最终完整内容判断是否有实质性修改，以及是否引入新的缺陷。

`Regression Rate = 发生 regression 的 bundle 数 / 有实质性修改的 bundle 数`。

同时输出新增 regression 缺陷数和证据。实质性修改由语义裁判判断，不是看到文件差异就自动认定。原始与最终字节完全相同的 bundle 不应报告修复或 regression。

有害额外修改可能同时产生修复 FP 和 regression 记录：前者说明修改不成立，后者说明原本正确的行为被改坏。它们分别报告，不再合成一个总分。

### Verified Fix Rate（真实 verifier 指标）

`Verified Fix Rate = 修复后明确通过 verifier 的任务数 / 执行无报错的修复后任务数`。

它按任务计数，与按缺陷计算的 Diagnosis/Repair F1 并列报告，不使用 LLM 的 `repair_correct` 推算。结果通过输入校验后，`execution_ok == true` 的任务进入分母：`task_passed == true` 计为通过，`false` 或 `null` 均计为任务失败。有通过判决时，`trajectory_complete == false` 不影响通过计分。

| 情况 | VFR 处理 |
| --- | --- |
| 有效修复后运行，通过 verifier | 分子 +1、分母 +1 |
| 有效修复后运行，未通过 verifier | 仅分母 +1 |
| 执行无报错，但 `task_passed=null`、`reward=null`，没有判决 | 按失败计，分母 +1，不中断评测 |
| 有通过判决，但 `trajectory_complete=false` | 仍按通过计，分子 +1、分母 +1 |
| 基础设施错误，`execution_ok=false` | 不进入分母，记 `invalid_execution` |
| 未提供该任务的运行结果 | 不进入分母，记 `missing_result` |
| 原始运行已核验通过并跳过 | 不进入分子或分母，保留跳过状态 |

同时报告 `verified_fix_coverage = 纳入 VFR 计分的任务数 / 非跳过任务数`、无效数、缺失数和逐任务明细。`verified_fix_valid_task_count` 沿用字段名，表示纳入计分的任务数，包括执行无报错但无判决的失败任务。例如四个非跳过任务中，一通过、一失败、一基础设施错误、一未运行，VFR 为 **1/2**、coverage 为 **2/4**，状态为 `partial`。不能把这种不完整覆盖的 50% 当作全部四个任务的结果。分母为零时为 `null`；全部跳过也不是满分。

例如两次执行均无报错：A 有通过判决但轨迹不完整，B 没有判决，则通过数为 1、失败数为 1，VFR 为 **1/2**，coverage 为 **2/2**。逐任务报告保留 B 原始的 `task_passed: null` 和 `reward: null`，只将评分 `status` 标为 `failed`，不伪造 verifier 判决。原始通过跳过仍要求明确的 `task_passed=true`；无判决不能申请跳过。

每个任务只导入一次预先确定的最终运行。方法、最终候选和运行选择规则应在评测前固定，不应只提交成功运行或从多次随机运行中挑最好结果。不同方法的任务集合、有效覆盖范围和模型设置应一同核对。

#### 自动读取本地 executor 目录

使用 `--executor-runs-dir DIR`，可指定整个 `jobs_root`、某方法的目录，或单个 rollout 目录。脚本根据提交的 `method_id`、`task_id` 和 Final 内容标识匹配 `method-skill` 运行；其他方法、Gold 外任务和其他候选 bundle 不参与本轮汇总。

每个任务只能选中一条运行。同一 Final 有多条运行时会报错，需用提交行中的 `executor_run_id` 指定预先确定的轮次，或传入只包含本轮运行的目录。未完成但已有 `executor_request.json` 的运行也参与选择，不会因为它没有结果而自动改选另一条成功记录；被选中但缺少报告时记为 `missing_result`。失败结果必须保留，有效失败会计入 VFR 分母。

脚本核对 report/request 的 method/task/rollout ID、运行条件、`skillrepair-v1` 协议版本 2、模型与 reasoning effort，并用 executor 已有的 bundle SHA256 格式核对最终提交内容。guard 开启、关闭、缺少记录或不同产物中的 guard 元数据不一致均不作为拒绝条件。不能拿 Original 或另一个修复轮次的通过结果来计分。本轮 Original 跳过和 Final 验证运行不得混用模型或 reasoning effort。轨迹完整性不作为计分门槛；有明确判决时仍校验 reward 与判决一致，以及协议、iteration 和 Skill 暴露证据。执行无报错且判决、reward 均为空时直接按失败计；声明无判决但又给出非空 reward，或 `execution_ok=true` 却同时记录执行错误，仍属于输入矛盾。

脚本检查本地运行产物的结构和一致性，不重跑 verifier。运行目录应保留实际 executor 产物；同一轮比较仍使用统一任务源、环境、预算和轮次规则。Gold 和评测提示不会因为执行通过而自动改写。

已有裁判响应时，可以离线补充或重计 Verified Fix Rate：

```bash
python evaluation/scripts/evaluate_skill_diagnosis_repair.py --submission path/to/submission.json --judge-responses path/to/judge_responses.json --executor-runs-dir path/to/jobs/method_a --output .cache/skill-evaluation/with-verifier --max-input-chars 2000000
```

原始通过任务也在同一次命令中本地核验。verifier 结果只进入 reporting，不放入诊断或修复的 LLM 请求；有待复核的语义判断不会抹掉已经有效的实际 verifier 结果。

#### 兼容旧流程：手工指定 Final 结果清单

此前的 `--executor-results PATH` 仍可读取手工指定的清单，便于重放已有实验；**本地自动流程无需准备此文件**。清单引用 executor 已生成的 `benchmark_result.json`，旁边保留同一次运行的 `executor_request.json`：

```json
{
  "method_id": "method_a",
  "benchmark_version": "core25-gold-defects-20260909-v1",
  "tasks": [
    {
      "task_id": "dialogue-parser",
      "benchmark_result": "runs/dialogue-parser-final/benchmark_result.json"
    }
  ]
}
```

路径相对于清单文件。上例只提供一个任务，其他非跳过任务会明确记为缺失，原始已通过而跳过的任务不应列入此清单。旧流程有跳过任务时，还需传入 `--verified-original-passes`。`--executor-runs-dir` 不能与这两个旧参数同时使用。

两种 executor 输入均未提供时，Diagnosis/Repair 照常计分，VFR 为 `null`、状态为 `not_provided`，不能将它写作真实修复通过率为零。

## 4. 先离线跑通样例

以下命令均在仓库根目录运行。`examples/` 中的任务、Skill、Gold、预测和裁判响应全部为**虚构教学数据**，不能当作真实模型评测结果。

`--output` 应使用不存在或为空的目录；重复运行时选择新的输出目录。

仅检查输入并生成待判定请求，不调用 API、不评分：

```bash
python evaluation/scripts/evaluate_skill_diagnosis_repair.py --gold evaluation/examples/gold.json --submission evaluation/examples/submission.json --output .cache/skill-evaluation/example-dry-run --dry-run
```

使用样例裁判响应完成离线计分，不调用 API：

```bash
python evaluation/scripts/evaluate_skill_diagnosis_repair.py --gold evaluation/examples/gold.json --submission evaluation/examples/submission.json --output .cache/skill-evaluation/example-offline --judge-responses evaluation/examples/judge_responses.json
```

样例预期如下：

| 内容 | 判定 |
| --- | --- |
| P1 → D01、P2 → D02 | 正确诊断，且位置均正确 |
| P3 | 误报；Gold D03 未被诊断到 |
| D01 | 尝试且完整修好 |
| D02 | 尝试但失败 |
| D03 | 未尝试，未修好 |
| E1 修改标题 | `benign` |
| E2 删除原音轨 | `harmful_or_unsupported`，并产生一个新缺陷 |

因此 Diagnosis TP/FP/FN = **2/1/1**，P/R/F1 均为 **2/3**；Repair TP/FP/FN = **1/2/2**，P/R/F1 均为 **1/3**；Location Accuracy = **1**；Regression Rate = **1**，新增缺陷数 = **1**。

### 旧清单格式的原始通过教学样例

`examples/original-pass/` 提供单任务全部跳过的提交、组织者核验清单及非空报告。它们也是**虚构数据，没有实际运行任务或 verifier**；只用于验证输入格式和跳过逻辑。清单引用已有 `examples/original/skills`，与教学 Gold 的 Original 相同。

```bash
python evaluation/scripts/evaluate_skill_diagnosis_repair.py --gold evaluation/examples/gold.json --submission evaluation/examples/original-pass/submission.json --verified-original-passes evaluation/examples/original-pass/verified-original-passes.json --output .cache/skill-evaluation/example-original-pass --execute
```

该例中唯一任务和 3 个 Gold 缺陷全部跳过，调用裁判次数为 `0`，不需要模型或密钥，不产生 API 费用；状态为 `complete`，指标为 `null`。如将 `--execute` 换为 `--dry-run`，只核查输入，`maximum_judge_requests` 为 `0`。

### 本地自动汇总 verifier 的离线教学样例

`examples/executor-results/` 提供**虚构**的 executor report/request，只验证格式与计算，不是真实任务通过证据：

```bash
python evaluation/scripts/evaluate_skill_diagnosis_repair.py --gold evaluation/examples/gold.json --submission evaluation/examples/submission.json --judge-responses evaluation/examples/judge_responses.json --executor-runs-dir evaluation/examples/executor-results/runs --output .cache/skill-evaluation/example-local
```

此例 Diagnosis F1 仍为 **2/3**、Repair F1 仍为 **1/3**；虚构 verifier 记录通过，所以 VFR 为 **1/1**、coverage 为 **1/1**。输出还自动包含 `executor-results.json`，无需读取或手写 `manifest.json`。这只演示指标独立，不是实验成绩。

## 5. 使用模型裁判

三个模式 `--dry-run`、`--judge-responses PATH`、`--execute` 必须且只能选择一个。`--execute` 在存在非跳过任务时调用 API，并要求显式提供 `--judge-model`；全部任务都经核验跳过时不需要模型或密钥，也不会调用 API。

每个非跳过任务使用两个独立、没有共享对话历史的裁判请求，二者采用相同模型和温度：

| 阶段 | 裁判可见内容 |
| --- | --- |
| `diagnosis` | Gold 缺陷描述与位置、提交的诊断预测、原始 bundle、`task_context`；不含修复要求、diff 或最终 bundle |
| `repair` | 包含修复要求的 Gold、原始 bundle、diff、最终 bundle、`task_context`；不含诊断预测 |

这样诊断裁判不能根据最终修复反推诊断是否正确，修复裁判也不会受方法的诊断解释影响。`--dry-run` 的 `maximum_judge_requests` 为非跳过任务数的两倍，仍不调用 API。

```bash
python evaluation/scripts/evaluate_skill_diagnosis_repair.py --gold path/to/gold.json --submission path/to/submission.json --output .cache/skill-evaluation/live-run --execute --judge-model YOUR_JUDGE_MODEL
```

本版使用 GPT-5.5 的命令示例（会产生 API 费用；先设置 `OPENROUTER_API_KEY`）：

```bash
python evaluation/scripts/evaluate_skill_diagnosis_repair.py --submission path/to/submission.json --executor-runs-dir path/to/jobs/method_a --output .cache/skill-evaluation/gpt55-run --execute --judge-model openai/gpt-5.5 --omit-temperature --reasoning-effort medium --max-input-chars 2000000
```

这里显式省略温度，并固定裁判 reasoning effort 为 `medium`。`--executor-runs-dir` 同时处理本地 verifier 汇总与 Original-pass 核验；裁判模型参数与执行任务的模型参数分别记录。本次修改只做离线检查，没有重新运行 GPT-5.5 或任务 rollout。

运行前在环境变量中配置密钥，不要把密钥写入提交文件或命令参数。本次提供的离线样例不调用模型、不产生 API 费用。

| 参数 | 默认值或用途 |
| --- | --- |
| `--executor-runs-dir` | 推荐：读取本地 executor 运行目录，自动汇总 VFR 并核验原始通过跳过；不补跑任务 |
| `--verified-original-passes` | 兼容旧流程：手工指定原始通过核验清单；不与本地目录参数同时使用 |
| `--executor-results` | 兼容旧流程：手工指定 Final executor 结果清单；不与本地目录参数同时使用 |
| `--base-url` | `https://openrouter.ai/api/v1`，可换为兼容服务 |
| `--api-key-env` | `OPENROUTER_API_KEY`，指定密钥所在环境变量的名称 |
| `--temperature` | `0` |
| `--omit-temperature` | 不发送温度参数，元数据记录为 `null`，用于不支持温度的模型 |
| `--reasoning-effort` | 可选 `none/low/medium/high/xhigh`；未指定时不发送，使用服务默认值 |
| `--confidence-threshold` | `0.8`，仅控制低置信度警告，不阻塞或改变计分 |
| `--max-input-chars` | 每次请求 `250000`，超出时报错，不静默截断 |
| `--max-output-tokens` | 每次请求 `8192` |
| `--timeout` | `180` 秒 |

同一轮比较应使用相同 Gold、裁判模型、提示与参数。模型置信度只用于警告统计和可选抽查，不等同于经过校准的正确概率。

## 6. 输出与复核

| 文件 | 内容 |
| --- | --- |
| `summary.json` / `summary.csv` | 汇总计数、指标和状态 |
| `verifier_results.json` | Verified Fix Rate、有效覆盖率及逐任务通过/失败/无效/缺失/跳过明细 |
| `executor-results.json` | 本地目录模式自动生成的 Final 结果索引，另记录已选中但缺报告的运行；dry-run 也生成 |
| `details.json` | 逐任务、逐缺陷的判断、原因和计算结果 |
| `review_queue.json` | 警告、候选 Gold 遗漏及阻塞复核项，由 `blocking` 区分 |
| `skipped_tasks.json` | 已核验跳过的任务、对应 Gold defect ID 和原始运行证据 |
| `judge_responses.json` | 可重新计分的裁判响应 |
| `requests.jsonl` | 每个非跳过任务两行独立请求，带 `phase` 字段；保留完整可核查输入，包括提交内容及评测 Gold |

`--dry-run` 不产生评分。完整评分输出用于核查与复现，`requests.jsonl` 含评测 Gold，不应当作公开给参评方法的输入。

汇总还报告以下任务范围，避免把跳过与成功修复混淆：

| 字段 | 含义 |
| --- | --- |
| `task_count` / `total_gold_defect_count` | 提交覆盖的全部任务数 / 全部 Gold 缺陷数 |
| `skipped_original_pass_task_count` / `skipped_gold_defect_count` | 经核验跳过的任务数 / 这些任务的 Gold 缺陷数 |
| `evaluated_task_count` / `evaluated_gold_defect_count` | 非跳过任务数 / 这些任务的 Gold 缺陷数 |
| `scored_task_count` | 正常评测结果为 `complete` 的任务数，不包含跳过任务 |
| `skipped_original_pass_rate` | 已核验且跳过的任务数 / 全部任务数 |
| `skipped_original_pass_task_ids` | 已核验跳过的任务 ID 列表 |

`evaluated_task_count` 描述评测范围，不保证其中任务都已完成评分。`skipped_original_pass_rate` 只描述已核验并采用跳过机制的比例；其他任务的原始运行结果可能未知，不能把该比例当成完整原始任务通过率。

当前计分版本为 `skill-diagnosis-repair-scoring-v1.4`：有通过判决但轨迹不完整仍算通过，执行无报错但无判决按失败计入分母。Diagnosis/Repair 语义判据与 `v2.1` prompt 不变，已有裁判响应可离线重计；比较不同方法时应统一使用新的 VFR 口径。本地模式记录 `evidence_policy: "local_executor_artifacts"`、`original_pass_policy: "local_executor_verified_skip"` 及 `executor_runs_dir`；旧清单模式记录 `evidence_policy: "provided_manifests"`。输出的 `evaluation_scope` 为 `excluding_verified_original_pass` 或 `all_gold_tasks`，分别标明是否排除了原始通过任务。`maximum_judge_requests` 是非跳过任务数的两倍，表示请求上限；全部跳过的 `--execute` 记录 `mode: "original_pass_only"`，无需模型调用。

`summary.json` 顶层与 `summary.csv` 均包含 `verified_fix_rate`、`verified_fix_status`、`verified_fix_coverage`，以及 `verified_fix_eligible_task_count`、`verified_fix_valid_task_count`、`verified_fix_passed_task_count`、`verified_fix_failed_task_count`、`verified_fix_invalid_task_count`、`verified_fix_missing_task_count`。VFR 状态为 `complete`、`partial`、`not_provided` 或 `no_eligible_tasks`；语义评测的 `status` 单独保留。`--dry-run` 会核查 executor 输入，但不输出正式评分。

导入 `judge_responses.json` 时必须包含 `"prompt_version": "skill-diagnosis-repair-v2.1"`。每个非跳过任务分别保存 `diagnosis_result` 和 `repair_result`，不再使用旧版联合 `result` 包装：

```json
{
  "method_id": "method_a",
  "benchmark_version": "v1",
  "prompt_version": "skill-diagnosis-repair-v2.1",
  "judge_model": "offline-example",
  "tasks": [
    {
      "task_id": "example-task",
      "diagnosis_result": {"diagnoses": []},
      "repair_result": {
        "repairs": [],
        "extra_modifications": [],
        "regression": {}
      }
    }
  ]
}
```

上面只展示包装结构，实际条目必须完整，详见 `examples/judge_responses.json`。旧联合裁判响应不能冒充独立请求的结果。当前 v2.1 提示明确要求模糊匹配时作出证据最充分的唯一判断，并说明低置信度只警告、不阻塞；先前 v2 的提示仍暗示人工复核，因此旧结果需使用当前提示重新裁判，不能仅修改版本号。

导入时保留响应中的 `temperature`、`reasoning_effort`、`max_output_tokens`、`base_url` 历史元数据，缺失字段记为 `null`，不会用当前命令参数补成历史模型设置。`requests.jsonl` 中的 `prepared_prompt_version` 表示本次重建请求所用的模板版本，不是对历史请求的额外证明。样例是按当前判据编写的手工离线判定，因此不填写虚构的温度或真实模型设置。

原始通过机制不改变 `skill-diagnosis-repair-v2.1` 提示版本。相同提交及跳过集合下，现有响应可以离线重新计分。跳过任务的响应行保存 `status: "skipped_original_pass"` 和 `original_run.run_id`，不需要诊断或修复裁判结果；重新计分仍须传入 `--executor-runs-dir` 核验本地证据，或沿用旧流程的 `--verified-original-passes` 清单，且状态、任务集合和 run ID 必须匹配，不能仅凭旧响应跳过核验。

对于非跳过任务，每个诊断预测必须有一条裁判记录，每个 Gold 缺陷必须有一条修复记录，不能只返回命中或成功项。缺文件、未知 ID、漏裁判条目等属于评测错误，不按零分处理。

低于阈值的有效置信度只记录 `low_confidence` 警告（`blocking=false`），按裁判的语义结论正常计分，任务仍可完成。置信度恰好等于阈值不触发警告。`possible_new_defect` 同样不阻塞，不立即改变本轮 Gold 或 FP。当前不启用自动二审，也不因低置信度额外调用模型。

匹配冲突、修改判断自相矛盾或无法检查的二进制修改仍需阻塞复核；格式错误、漏条目以及缺失/非法 `confidence` 等仍按评测错误处理。这些情况下不生成正式汇总分数。处理异常后可修订并留存裁判响应，再用 `--judge-responses` 重新计分。

`summary.json` 顶层及 `summary.csv` 增加以下统计，`details.json` 的逐任务 `confidence_summary` 保留相同计数口径：

| 字段 | 含义 |
| --- | --- |
| `low_confidence_count` | 置信度严格低于阈值的判定记录数 |
| `total_judgment_count` | 诊断记录数 + Gold 修复记录数 + 额外修改记录数 + bundle regression 记录数 |
| `low_confidence_rate` | 低置信度记录数 / 总记录数；无可统计记录时为 `null` |
| `confidence_task_count` | 可统计完整判定记录的任务数 |

每条含 `confidence` 的记录计一次：诊断匹配与定位共享一条记录，bundle regression 也只计一条，不按其中布尔字段或新缺陷数量重复计算。字段校验完成但存在匹配冲突的任务仍可提供这些统计；格式错误、缺条目或二进制无法检查的任务不纳入分母，可结合 `confidence_task_count` 与总任务数检查统计覆盖范围。

输出通过 `confidence_policy: "warn_only"` 标记当前计分策略，v2.1 提示与该策略保持一致。低置信度比例仅描述模型自报置信度分布，不能据此声称裁判准确率或重复判定稳定性；例如只能表述“96.2% 的判定记录自报置信度达到预设阈值”。

退出码：`0` 表示完成，`1` 表示存在阻塞复核项，`2` 表示输入、裁判响应或执行错误。

## 7. 维护与离线测试

测试使用虚构判定或 Mock，不发送模型请求；数据检查还验证发布子集、默认 Gold 和文件路径。Windows 未获系统权限时，真实软链接测试会跳过，其他路径检查仍运行。

```bash
python -m pytest evaluation/tests -q
```

需要从原始 RI 重新转换 Gold 时，使用随附脚本。转换逐条保留描述和验收要求，禁止覆盖已存在的文件；输出路径不同会相应调整内部相对引用。

```bash
python evaluation/scripts/prepare_skill_evaluation_gold.py --output .cache/skill-evaluation/rebuilt-gold.json
```

修改 Gold 标签、修复要求或评分判据时，应发布新版本并统一重计所有方法。参考自测只是检查工具，不能据此自动删除或放宽未获满分的 Gold。
