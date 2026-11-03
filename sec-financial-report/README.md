# SEC Financial Report：原题训练材料与三批同源测试

本包保留 SkillsBench 原题、原 Skill、原始输入和原 GT，将最终指标改为答案项正确率。新测试沿用原 helper 实际执行的统计口径，各自计算参考答案。没有调用付费模型，也没有启动新的修复实验。

```text
sec-financial-report/
├── task.md / environment/       # 原题、两份完整原始ZIP、完整原Skill
├── diagnosis/                   # GPT-5.2完整轨迹、恢复的原输出和允许反馈
├── verifier/ / oracle/          # 当前评分与原参考，仅评分/组织侧使用
├── result/README.md             # 最终冻结Skill和原题真实执行的提交要求
├── evaluation/                  # 冻结后的三批测试输入、评分及导出工具
│   ├── group_01/                # 20案例/200答案项；另有02和03
│   └── results/README.md        # 泛化执行结果的提交要求
├── tools/ / tests/              # 材料复核、环境检查和免费回归
└── validation/                  # 参考计算与历史输出重放证据
```

拿到仓库后，先按下表读取原题、原Skill、完整轨迹和反馈，交给现有方法adapter。原题两份ZIP和三批冻结输入已包含，无需另外下载全量SEC源数据。执行器安装与初始化沿用[统一接入说明](../DELIVERY_GUIDE.md#5-入口-b修复算法自动调用)，使用其Python3.12及Docker环境。本包的免费检查可从仓库根运行：

```bash
python -B -m unittest discover -s sec-financial-report/tests -v
```

修复及原题执行的最终交付见[result说明](result/README.md)；冻结Skill后再读取[evaluation说明](evaluation/README.md)并导出测试任务。

## 原题和修复材料的位置

| 材料 | 位置 |
|---|---|
| 原题、原执行配置 | [task.md](task.md) |
| 原始输入 | [2025-Q2 ZIP](environment/13f-2025-q2.zip)、[2025-Q3 ZIP](environment/13f-2025-q3.zip) |
| 原 Skill | [13f-analyzer](environment/skills/13f-analyzer/SKILL.md)、[fuzzy-name-search](environment/skills/fuzzy-name-search/SKILL.md)，支持脚本见 [完整 bundle](environment/skills/) |
| 指定 GPT-5.2 完整原生轨迹 | [ACP](diagnosis/source_run/trajectory/acp_trajectory.jsonl)、[LLM 请求/响应](diagnosis/source_run/trajectory/llm_trajectory.jsonl)、[ATIF](diagnosis/source_run/trainer/atif.json) |
| 反馈、运行状态与产物清单 | [allowed_feedback.json](diagnosis/outputs/allowed_feedback.json)、[execution_metadata.json](diagnosis/outputs/execution_metadata.json)、[output_inventory.json](diagnosis/outputs/output_inventory.json) |
| 原生记录及固定来源索引 | [diagnosis/index.json](diagnosis/index.json)、[源运行审计](validation/source_run_audit.json) |
| 恢复的原模型输出 | [answers.json](diagnosis/recovered_output/answers.json)、[恢复来源](diagnosis/recovered_output/provenance.json) |

指定旧运行的历史 reward=0 原样保留，原 verifier 确实因 uv 下载失败而未进入 pytest。本次从 ACP/LLM 中的原始写入命令和实际文件回读恢复原输出，并完成 Docker verifier-only 重放：原版测试为1通过/1失败，逐项正确率为 **4/10（40%）**；q1、q4正确，q2错误，q3五个位置均错误。因此可作为**经重放确认的模型 FAIL**诊断材料。原文件未独立归档，恢复文件不冒称原归档；[diagnosis说明](diagnosis/README.md)列明来源与使用范围，[重放结果](validation/verifier_replay/SUMMARY.json)保留原评分故障与本次有效重放的区别。

两份 Skill 正文在原执行器中被预载；显式 Skill 调用数为 0，30/30 次响应记录包含 Skill 指令，详见审计。历史运行步数和成绩不追改。

## 统一接入

修复侧沿用各方法原有 adapter：读取原题、原完整 Skill bundle、完整轨迹和允许反馈，继续使用该方法自己的诊断、迭代和选版方式。本包不增加专用 adapter 或请求格式。

执行侧沿用现有统一 `BenchmarkExecutor`，`tasks_root` 指向包含 `sec-financial-report/` 的父目录。传入修复后的完整 bundle：

```python
result = executor.run(
    task_id="sec-financial-report",
    condition="method-skill",
    skill_bundle="/path/to/frozen/full-skills",
    method_id="your-method",
    stage="final",
    rollout_id="sec-final-unique-run-id",
)
```

使用当前统一执行器的 60 次父迭代和既有 completion guard。每次执行使用新 rollout_id。只有 environment 与题面提供给 Agent，verifier 在 Agent 退出后部署；不要将整个本包挂入容器。`oracle/`、`verifier/`、`validation/` 和测试参考仅在组织者/评分侧使用。

## 评分与 GT

原题的 [expected_output.json](verifier/expected_output.json) 保持原字节，当前评分直接读取该文件，不另存一套训练 GT；原二元 verifier 存于 [source/original_verifier](evaluation/source/original_verifier/)。当前 [test.sh](verifier/test.sh) 用 Python 标准库运行 [native_grade.py](verifier/native_grade.py)，无需联网安装评分依赖。

每个案例 10 项：q1 金额 1 项、q2 股票持仓行数 1 项、q3 前五 CUSIP 各 1 项、q4 前三经理名各 1 项。判对规则沿用原题：q1 相对误差严格小于 0.001（0.1%），q2 精确相等，CUSIP 保留前导零且按位匹配，经理名仅转小写比较且顺序必须正确。

`accuracy = 正确项数 / (预期项数 + 额外错误项数)`。缺失、非法或错位的项记错；多余排名元素每个、未知 case_id 每个各增加一个错误项。原题允许的额外对象字段仍忽略。整个输出缺失、不可读或非法 JSON 得 0。另报 strict_success；运行时间不加权，保留原执行时限。历史二元 reward 不改写成新正确率。

**保留原口径的已知局限：**原 helper 的股票类别表漏逗号，Python 会拼接部分字符串。为保持原任务可比性，本包按其实际求值结果计数和聚合，不扩大股票范围。这里的“股票数”是筛选后的行数，不是不同 CUSIP 数。q1 是 13F 申报持仓 VALUE 合计，并非基金所有资产。规则见 [statistical_contract.json](environment/statistical_contract.json)。

## 三批同源测试如何构建

| 批次 | 基准报告期 → 当前报告期 | 案例数 | 答案项 |
|---|---|---:|---:|
| group_01 | 2024-Q1 → 2024-Q2 | 20 | 200 |
| group_02 | 2024-Q3 → 2024-Q4 | 20 | 200 |
| group_03 | 2025-Q4 → 2026-Q1 | 20 | 200 |

原题训练保留 2025-Q2/Q3 的完整原始 ZIP，问 Renaissance、Berkshire 和 Palantir。新增输入来自 SEC 同一 Form 13F 数据发布渠道。ZIP 发布窗口与持仓报告期不同，构建时同时核对 COVERPAGE 和 SUBMISSION 的报告期，只保留非修订的初始 13F-HR；同 CIK 若有多份初始申报，取最早申报日，再按 accession 选择。

每批从两个报告期都有申报、两期持仓行数均至少 50 的经理中按固定 SHA256 顺序选候选。选 20 个经理回答 q1/q2，另外 20 个回答 q3，再选 20 个证券回答 q4；排除排名前列或截止处并列、正增持不足五项或持有人不足三名的查询。筛选不使用任何模型成绩。成员和来源见各批 metadata.json，构建程序见 [build_dataset.py](tools/build_dataset.py)。

保留全部 40 个查询经理在两期的完整持仓行；当前期还保留全部合格经理关于 20 个查询证券的持仓行，防止 q4 因只保留查询经理而漏掉真正的持有人。四张表的选中原始行保持原字节，压缩文件的行数与解压校验值记录在 metadata.json。

三批报告期互不重叠，均不使用训练报告期；查询目标 CIK 和查询证券 CUSIP 在批次间不重复，也排除原题目标。其他持仓证券、q4 返回的经理可能重复，不宣称所有实体互斥。这是同源的时间和查询目标迁移挑战集，不是难度匹配的 IID 抽样。新题提供 CIK/CUSIP 消歧，将同样四问参数化成 20 个案例；不宣称题面逐字相同，也不把每批 200 个相关答案项当成 200 次独立 Agent 实验。

三批冻结输入与参考都直接随包提供。选取输入时使用的六份全量SEC ZIP不重复提交Git；来源、报告期、大小和SHA见[source说明](evaluation/source/README.md)及SOURCES.json，供组织者按需重新构建，不影响同学直接执行已冻结任务。

冻结 Skill 后，隔离导出一批原生任务：

```bash
python sec-financial-report/evaluation/prepare_task.py --group group_01 --output /tmp/sec-group01/tasks/sec-financial-report
```

将执行器的 tasks_root 指向 `/tmp/sec-group01/tasks`，仍调用同一 task_id 和公共 API。导出环境不含其他批次、diagnosis、oracle 或参考答案。完整本地包包含测试资料，修复/选版阶段应由组织者隔离，不向方法开放测试答案。

## 免费复核

Python 整数聚合从完整源 ZIP 计算新参考；[独立 SQLite 程序](tools/verify_references_sqlite.py) 从原题 ZIP 和实际导出的测试行重新计算，不导入主计算模块。原题先与未变的官方 GT 比较，再检查全部新案例。结果见 [reference_crosscheck.json](validation/reference_crosscheck.json) 与 [VALIDATION_REPORT.md](VALIDATION_REPORT.md)。

```bash
python -B sec-financial-report/tools/verify_references_sqlite.py
python -B -m unittest discover -s sec-financial-report/tests -v
```

单独计算实际输出的正确率：

```bash
python sec-financial-report/verifier/score_accuracy.py --actual /path/to/answers.json --reference sec-financial-report/evaluation/group_01/verifier/reference_answers.json --report /tmp/sec-accuracy.json
```

原题来源固定 SkillsBench `b63b7b2850226b6aa4fb5929a8c1ac7bc4d9a6af`，旧轨迹固定 benchmark `bee9b0df5b04a300735e5009f5238f5d5c8aaf61`。八份 ZIP 的来源、大小和 SHA256 见 [SOURCES.json](evaluation/source/SOURCES.json)；SEC 原始发布见 [Form 13F data sets](https://www.sec.gov/data-research/sec-markets-data/form-13f-data-sets)。已完成7次历史输出/独立答案的Docker评分重放，610个独立复算答案项全部通过；原题及三批导出任务还通过了Docker构建、8张输入表读取与原环境中的评分检查，见[环境记录](validation/task_environments/SUMMARY.json)和[验证报告](VALIDATION_REPORT.md)。这些检查没有调用模型，不代表新增方法成绩。来源和许可另见[source说明](evaluation/source/README.md)。
