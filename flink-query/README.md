# Flink Query：作业活动阶段统计与同源日志迁移

本目录提供SkillsBench原题、原skill、指定GPT-5.2失败轨迹的离线诊断材料，以及三批冻结同源输入。补全Java/Flink程序，按task SUBMIT事件形成10分钟session，对正常完成且有活动的job输出最大阶段提交次数。 修复使用原题和diagnosis，冻结skill后才使用evaluation。没有重新运行模型或生成方法成绩。

```text
flink-query/
├── task.md / environment/      # 原题、原输入、完整skill与许可
├── verifier/                   # item-accuracy-v1连续正确率，仅评分侧部署
├── oracle/                     # 原参考解法，不供诊断/修复读取
├── diagnosis/                  # GPT-5.2完整轨迹索引、允许反馈
│   ├── index.json              # 固定来源与完整记录索引
│   └── outputs/                # 原状态、反馈与产物未归档说明
├── tools/                      # 离线整理来源与反馈，不改变adapter接口
├── result/README.md            # 冻结skills、真实修复过程与原题执行的提交要求
├── evaluation/                 # 冻结后三组同源评测
│   ├── group_01/               # 一组输入和评分资源，另有02/03
│   └── prepare_task.py         # 隔离导出一个新任务，不调用模型
└── tests/                      # 诊断、评分和导出的免费回归
```

## 同学先怎样接入

先读取以下材料，按各自方法的诊断、修复、迭代和选版机制处理。表中包内路径均相对于本目录：

| 材料 | 位置 | 内容 |
|---|---|---|
| 原题 | [task.md](task.md) | 任务要求、输入输出路径约定与执行配置 |
| 原输入与程序骨架 | [environment/workspace/data/](environment/workspace/data/)、[src/](environment/workspace/src/)、[pom.xml](environment/workspace/pom.xml) | 原始job/task事件、字段说明、Java骨架及构建依赖 |
| 原 Skill | [pdf/SKILL.md](environment/skills/pdf/SKILL.md)、[senior-data-engineer/SKILL.md](environment/skills/senior-data-engineer/SKILL.md)、[完整bundle](environment/skills/) | 两个原Skill的正文、支持文件和许可；修复时保留完整bundle |
| 完整失败轨迹 | [ACP事件](https://github.com/linyouxue/skill-repair-benchmark/blob/bee9b0df5b04a300735e5009f5238f5d5c8aaf61/evaluation/results/GPT52-AllTasks-RepresentativeRuns-20260916/tasks/flink-query/selected_run/trajectory/acp_trajectory.jsonl)、[完整LLM请求/响应](https://github.com/linyouxue/skill-repair-benchmark/blob/bee9b0df5b04a300735e5009f5238f5d5c8aaf61/evaluation/results/GPT52-AllTasks-RepresentativeRuns-20260916/tasks/flink-query/selected_run/trajectory/llm_trajectory.jsonl)、[ATIF轨迹](https://github.com/linyouxue/skill-repair-benchmark/blob/bee9b0df5b04a300735e5009f5238f5d5c8aaf61/evaluation/results/GPT52-AllTasks-RepresentativeRuns-20260916/tasks/flink-query/selected_run/trainer/atif.json) | 固定提交中的指定GPT-5.2原始失败运行，交给现有方法adapter读取 |
| 反馈与运行状态 | [allowed_feedback.json](diagnosis/outputs/allowed_feedback.json)、[execution_metadata.json](diagnosis/outputs/execution_metadata.json)、[output_inventory.json](diagnosis/outputs/output_inventory.json) | 原reward、测试名称及对错、运行元数据和原产物归档状态；不提供隐藏答案 |

包内[diagnosis/records/](diagnosis/records/)另提供便于程序读取的整理记录，记录关系与固定来源见[index](diagnosis/index.json)。各方法沿用现有adapter读取这些完整材料，保留原方法的诊断、修订和选版机制。

指定历史运行的Java/JAR、输出tuple和完整工作区未归档，不能从轨迹中的完成声明补造；原reward=0保留，新评分下的历史正确率为null。修复使用上述原题材料，泛化输入在冻结Skill后再使用。

## 统一 adapter 接入

修复侧沿用现有方法adapter的输入契约，使用上表中的原Task、原完整Skill bundle、完整ACP/LLM轨迹和允许反馈。各子阶段继续按原方法处理这些材料，本任务包不新增请求格式、专用读取API或过程提交格式。

执行侧按[统一执行器接入说明](../DELIVERY_GUIDE.md#5-入口-b修复算法自动调用)初始化`BenchmarkExecutor`，`tasks_root`指向包含本任务目录的父目录。将修复后的完整bundle交给同一个接口：

```python
result = executor.run(
    task_id="flink-query",
    condition="method-skill",
    skill_bundle="/path/to/method-output/full-skills",
    method_id="your-method",
    stage="final",
    rollout_id="flink-query-final-unique-run-id",
)
```

每次执行使用新的`rollout_id`。不同任务仅替换`task_id`、完整bundle及运行标识，继续使用同一执行器、OpenHands adapter和既有公共API。

## 当前评分

`reward = (正确输出正例数 + 正确排除负例数) / (正例数 + 负例数 + 额外错误项数)`。正例要求恰好一条正确`(job_id,count)`，缺失、错值、重复记错；负例没有输出才记对。未知输出ID每个、非法非空行每行各作一个额外错误项，已知负例不重复扣分。整个输出缺失或不可读得0。

原输入共1324个作业：644个应输出、680个应排除。644条参考值由原CSV独立计算，逐项与原参考表一致；仅评分侧存放。可读空输出在负例上仍得分，基线为680/1324，不能把它误认为完成了正例计算。最终`score`/`accuracy`/`job_accuracy`一致，另报`positive_job_accuracy`及正负例计数。

运行时间不加权；保留原执行时限，候选编译错误、运行错误或运行超时记0，未分类构建/环境故障单列。`reward.txt`写连续分数，`strict_success`/`task_passed`另表严格全对；CTRF测试通过比例不一定等于分数。旧失败轨迹的历史reward=0保持原样，其原产物未归档，新正确率不可计算，不能改记0或拿旧CTRF通过比例代替。

## 原生执行与交付

把本目录作为原生task目录，或复制到固定SkillsBench checkout的`tasks/flink-query/`后，按仓库[统一执行器接入说明](../DELIVERY_GUIDE.md#5-入口-b修复算法自动调用)运行。原task.md、路径、公共API和60次父迭代约束保留，不把整个本目录挂到Agent；只部署environment和原题，结束后才部署verifier。本包不读取或保存API密钥。

最终上传完整`pdf/`、`senior-data-engineer/`及支持文件/许可，只允许修改现有SKILL.md正文。真实修复过程和同一冻结版本的原题执行须同时保留，Java源码、实际JAR和输出tuple文件应来自该次真实执行。见[result提交说明](result/README.md)。普通FAIL也如实提交，不要求全对；泛化数据和评分答案不用于修复或回头选版。

## 冻结后的同源评测

```bash
python flink-query/evaluation/prepare_task.py --group group_02 --output /tmp/flink-query-group02
python flink-query/evaluation/score_results.py --group group_02 --actual /path/to/actual-output --report /tmp/flink-query-accuracy.json
```

actual是实际输出文件或分片目录。命令成功仅表示评分完成，结果读取JSON；不重跑模型。批次构建、挑战集属性及使用边界见[evaluation说明](evaluation/README.md)。本轮未指定正式泛化重复次数。

## 免费验证、来源与限制

消费者、诊断读取器和离线评分测试只需Python标准库；实际原题执行还需要Docker环境中的Java、Maven和Flink：

```bash
python -m unittest discover -s flink-query/tests -v
python flink-query/tools/prepare_diagnosis.py --validate-only
```

原题固定SkillsBench `b63b7b2850226b6aa4fb5929a8c1ac7bc4d9a6af`，原输入、skill和许可保留。原历史运行未归档完整task tree，不能把本目录的新task digest冒称历史digest；后者在诊断元数据中另存。Flink环境仅沿用已验证的同版本1.20.3发行包镜像下载、官方SHA512校验和评分所需python3，不改原pom的1.18.0依赖、Java骨架或数据。

当前数据为pilot-v2、评分为item-accuracy-v1。离线验证见[VALIDATION.json](VALIDATION.json)；先前Docker环境验收与当前打包/评分复核分别记录，不宣称本次重演完整Docker。来源、许可及抽样记录见[source](evaluation/source/README.md)。
