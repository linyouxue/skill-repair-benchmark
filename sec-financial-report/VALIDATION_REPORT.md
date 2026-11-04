# SEC 本地构建与复核

日期：2026-11-03。原题训练输入、三批测试输入和正确率评分器已完成构建。指定历史输出已从实际工具观测恢复，并完成 Docker verifier-only 重放：原版评分未通过，逐项正确率为40%。独立复算的原题及三批答案全部通过当前评分；原题与三批导出的实际任务环境均已完成Docker构建、数据读取和评分检查。本轮未调用模型，未执行新的Agent rollout。

## 原 GT 直接沿用

原题、两份 Skill 和全部支持脚本、原输入 ZIP、原 oracle 及 `verifier/expected_output.json` 与固定 SkillsBench Git blob 一致。当前训练评分直接读取原 expected_output，不另立训练 GT。原二元 verifier 的原字节保留在 `evaluation/source/original_verifier/`。

原 helper 类别列表缺逗号，部分字面量被拼接；这是原口径的一项局限。早期比较已发现扩展类别会改变 q2/q3，见 validation 中的 training_reference_audit、training_reference_sqlite。用户最终要求保留原题可比性，因此主构建使用原类别表实际求值结果。原有历史分数不重算、不追改。

原题的独立整数求和与原官方四问 GT 全部一致，q1 也与 SUMMARYPAGE 相符。原 verifier 的金额判据实际为 `abs(answer/reference - 1) < 0.001`，即严格 0.1% 相对误差；当前保留该浮点运算及阈值。q2 保留精确比较，q3 保留有序 CUSIP，q4 仅忽略大小写，不去除空白。

## 三批真实同源数据

训练使用原始 2025-Q2/Q3 两份 ZIP。另下载六份 SEC Form 13F ZIP，按两个连续报告期一批冻结：

| 批次 | 报告期 | 案例/答案项 | 基准/当前持仓行 |
|---|---|---:|---:|
| group_01 | 2024-Q1 / Q2 | 20 / 200 | 25,202 / 37,188 |
| group_02 | 2024-Q3 / Q4 | 20 / 200 | 11,805 / 22,338 |
| group_03 | 2025-Q4 / 2026-Q1 | 20 / 200 | 21,295 / 39,209 |

八份完整源 ZIP 的来源及 SHA256 在 SOURCES.json，训练两份还匹配原 Git blob。所有查询以固定公开标识的 SHA256 顺序选取，只按完整查询条件和排名无歧义筛选，不依赖方法成绩。新测试显式给出 CIK/CUSIP，是相同四问模板的参数化任务，非逐字相同题面。

查询目标经理共 120 个、查询证券共 60 个，批次之间不重复，排除原题目标；报告期也与训练和其他批次不重叠。其他证券及答案中的持有人仍可重复。每批 20 案例/200 答案项具有组内相关性，不当作 200 次独立模型实验。

测试环境保留查询经理的完整两期持仓，并保留全部合格当前期申报中查询证券的行；q4 未截断为仅查询经理。导出行保留原始内容，四张表的行数和解压 SHA256 已检查。metadata.json 和 manifest.json 记录最终成员。

## 参考答案的两套计算

主程序从完整 ZIP 流式读取，用 Python 整数按原口径聚合。第二个程序独立解析原题 ZIP 和实际测试压缩输入，用 SQLite 查询重新计算，不导入主聚合代码或主程序中间结果；股票类别从原 helper 的 AST 实际字面量独立取得。

原题 10 项和测试 600 项，共 **610/610 一致**。原题和全部新案例在前五增持、前三持有人内部及截止处均无并列，已从原始持仓数据复核。原题两期的 Renaissance 与 Berkshire 在所需报告期均能唯一匹配到一份非修订初始申报。这里的标准结果唯一以原Skill既定统计口径为前提；q1接受相对误差严格小于0.1%的近似输出，不改变精确求和参考值。完整复核记录为 `validation/reference_crosscheck.json`，SQL 为 `validation/sqlite_queries.json`。

复核中发现两项源名称末尾有空格，早期生成时误去除；已保留原始名称，主程序也已移除 `.strip()`，最终 SQLite 比对全部通过。

第三批 case_009 的 SUMMARYPAGE 汇总与原始 INFOTABLE 行求和不一致。q1 公开定义和原 helper 都以 INFOTABLE.VALUE 求和为准；两套程序对此结果一致，不将 SUMMARYPAGE 当作该案例答案。该源数据差异在复核 JSON 中明确列出，其余 60 个案例的 q1 与 SUMMARYPAGE 一致。

## 正确率评分与隔离导出

每例 10 个答案位置，缺失/错值/错位记错；额外排名元素与未知案例各算额外错误项。reward 为连续正确率，严格全对另报。运行时间不加权；原时限保留。评分仅依赖 Python 标准库，避免原 uv 在线下载依赖成为评分前置条件。

免费测试覆盖原输入/Skill/GT 的字节保留、实际类别表一致、三批成员和报告期互斥、输入解压校验、三批原生隔离导出、原评分谓词、部分正确、缺失和非法输出、顺序、多余输出、评分依赖错误与普通零分分离，以及原生 reward/CTRF 生成。

原生导出只把所选批次及原 Skill 放入 environment；不含 diagnosis、oracle、其他批次或 GT。参考放 verifier，须在 Agent 退出后部署。继续使用现有方法 adapter 和统一 BenchmarkExecutor，不新增接入格式。测试结果见 `VALIDATION.json`。

## 历史 GPT-5.2 原输出恢复与评分重放

保留固定来源的 13 份原生文件，包括完整 ACP/LLM/ATIF 和原评分 stdout，逐个匹配来源 Git blob。指定 r003 历史评分确实停在 uv 下载失败，未进入 pytest；该阶段保持基础设施故障判定，不把其原 reward0 当成评分健康的证据。

本次找到足够的原输出证据：ACP第30行记录写入命令与成功执行，第31行由 file_editor 实际回读完整1—16行；对应 LLM第28行写入、第29行查看调用及第30行回读 observation。写入字面量、实际回读以及两份轨迹完全一致，之后没有工具改写。程序只用AST读取字面量和解析回读，不执行 Agent 代码，也不修正任何答案。恢复文件为 `diagnosis/recovered_output/answers.json`；来源见相邻 provenance.json。恢复文件296字节，其SHA属于本次恢复文件，不冒称当年独立归档文件的哈希。

先在验证镜像中装好原版本 pytest8.4.1、pytest-json-ctrf0.3.5，绕过原失败的 apt/curl/uv 下载启动步骤。实际评分时关闭网络，将原test_outputs.py与原GT按原绝对路径只读挂入；原测试和GT的Git blob及评分前后SHA均一致。

| 输入 | 原版测试结果 | 当前答案正确率 |
|---|---|---:|
| GPT-5.2恢复的原输出 | 文件存在通过，答案质量失败（1通过/1失败） | 4/10，40% |
| SQLite独立重算的原题输出 | 2/2全部通过 | 10/10，100% |
| SQLite独立重算group_01输出 | 使用当前批量评分器 | 200/200，100% |
| SQLite独立重算group_02输出 | 使用当前批量评分器 | 200/200，100% |
| SQLite独立重算group_03输出 | 使用当前批量评分器 | 200/200，100% |

旧输出的q1正确，q2错误，q3五个排名位置均错，q4三个位置均正确。说明环境确实曾妨碍评分，但恢复输出本身也确实答错；可作为“经重放确认的模型FAIL”使用，保留原评分故障和恢复来源标记。不能称原评分阶段健康，也不能把恢复文件冒充原文件独立归档。

共7次Docker评分重放，610/610个独立复算答案项被当前评分接受。实际计算输出保留在 `validation/verifier_replay/independent_answers/`，不是把GT文件直接当作本次作答；两套计算仍先逐项比对。逐次CTRF、连续分数、调用参数与输入哈希见 `validation/verifier_replay/SUMMARY.json` 及对应目录。恢复和重放脚本在tools目录，可免费复核。

## 原题与三批实际环境检查

使用原始environment/Dockerfile构建原题镜像，并分别用prepare_task导出三批任务、构建其实际Dockerfile。每个环境都读取两个报告期的COVERPAGE、SUBMISSION、SUMMARYPAGE、INFOTABLE共8张表，确认pandas2.3.3和rapidfuzz3.14.3，随后用独立复算输出运行该环境的当前评分器：原题10/10、三批各200/200。

这4次环境与评分检查和先前7次评分重放分别记录，累计11次Docker评分容器运行。临时导出和专属镜像已清理，完整构建、输入读取、评分日志及镜像标识见 `validation/task_environments/SUMMARY.json` 和各子目录。可用 `python sec-financial-report/tools/check_task_environments.py` 免费重做该检查；需要Docker及构建时的软件包下载网络，不调用模型。

本次发布只整理材料和验证结果，没有付费模型调用、没有新修复候选或新模型成绩。所有fixture均标明独立计算来源；环境/评分检查不冒称真实Agent执行。
