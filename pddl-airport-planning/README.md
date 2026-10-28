# PDDL Airport：机场规划与同源实例迁移

本目录提供SkillsBench原题、原skill、指定GPT-5.2失败轨迹的离线诊断材料，以及三批冻结同源输入。读取domain/problem，用规划器求解并保存规范PDDL计划；验收逐步检查动作合法性和全部目标。 修复使用原题和diagnosis，冻结skill后才使用evaluation。没有重新运行模型或生成方法成绩。

```text
pddl-airport-planning/
├── task.md / environment/      # 原题、原输入、完整skill与许可
├── verifier/                   # item-accuracy-v1连续正确率，仅评分侧部署
├── oracle/                     # 原参考解法，不供诊断/修复读取
├── diagnosis/                  # GPT-5.2索引、无损记录/窗口、允许反馈
│   ├── index.json              # 固定来源与记录/窗口索引
│   └── outputs/                # 原状态、反馈与产物未归档说明
├── tools/                      # 构建材料、读取packet/record/input、可选过程保存
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
| 原输入 | [environment/problem.json](environment/problem.json)、[environment/airport/](environment/airport/) | 原题要求的task01/02，以及原环境可见的全部domain/problem文件 |
| 原 Skill | [environment/skills/pddl-skills/SKILL.md](environment/skills/pddl-skills/SKILL.md)、[完整bundle](environment/skills/pddl-skills/) | 原Skill正文、支持文件和许可；修复时保留完整bundle |
| 完整失败轨迹 | [ACP事件](https://github.com/linyouxue/skill-repair-benchmark/blob/bee9b0df5b04a300735e5009f5238f5d5c8aaf61/evaluation/results/GPT52-AllTasks-RepresentativeRuns-20260916/tasks/pddl-airport-planning/selected_run/trajectory/acp_trajectory.jsonl)、[完整LLM请求/响应](https://github.com/linyouxue/skill-repair-benchmark/blob/bee9b0df5b04a300735e5009f5238f5d5c8aaf61/evaluation/results/GPT52-AllTasks-RepresentativeRuns-20260916/tasks/pddl-airport-planning/selected_run/trajectory/llm_trajectory.jsonl)、[ATIF轨迹](https://github.com/linyouxue/skill-repair-benchmark/blob/bee9b0df5b04a300735e5009f5238f5d5c8aaf61/evaluation/results/GPT52-AllTasks-RepresentativeRuns-20260916/tasks/pddl-airport-planning/selected_run/trainer/atif.json) | 固定提交中的指定GPT-5.2原始失败运行，可直接读取，无需先分窗 |
| 反馈与运行状态 | [allowed_feedback.json](diagnosis/outputs/allowed_feedback.json)、[execution_metadata.json](diagnosis/outputs/execution_metadata.json)、[output_inventory.json](diagnosis/outputs/output_inventory.json) | 原reward、测试名称及对错、运行元数据和原产物归档状态；不提供隐藏答案 |

包内[diagnosis/records/](diagnosis/records/)另提供便于程序读取的整理记录，记录关系与固定来源见[index](diagnosis/index.json)。同学可以直接读取完整轨迹，也可以按自身方法分段；不要求使用本包的分窗工具。

指定历史运行的计划原文件未归档，不能从轨迹中的完成声明补造；原reward=0保留，新评分下的历史正确率为null。修复使用上述原题材料，泛化输入在冻结Skill后再使用。

## 当前评分

`reward = 有效计划数 / 要求计划数`。每批两题，得到0、0.5或1。缺失、语法错误、动作非法或未达到目标，该题记错；接受任意有效计划，不匹配参考序列、步数或最优性。

原任务仍只要求解problem.json指定的task01/02；原环境可见的1—30题全部保留，严格未见测试只用31以后实例。

运行时间不加权；保留原执行时限，未完成的候选计划记错，未分类环境故障单列。`reward.txt`写连续分数，`strict_success`/`task_passed`另表严格全对；CTRF测试通过比例不一定等于分数。旧失败轨迹的历史reward=0保持原样，其原产物未归档，新正确率不可计算，不能改记0或拿旧CTRF通过比例代替。

## 原生执行与交付

把本目录作为原生task目录，或复制到固定SkillsBench checkout的`tasks/pddl-airport-planning/`后，按仓库[统一执行器接入说明](../DELIVERY_GUIDE.md#5-入口-b修复算法自动调用)运行。原task.md、路径、公共API和60次父迭代约束保留，不把整个本目录挂到Agent；只部署environment和原题，结束后才部署verifier。本包不读取或保存API密钥。

最终上传完整`pddl-skills/`及支持文件/许可，只允许修改现有SKILL.md正文。真实修复过程和同一冻结版本的原题执行须同时保留，计划原文件应来自该次真实执行。见[result提交说明](result/README.md)。普通FAIL也如实提交，不要求全对；泛化数据和评分答案不用于修复或回头选版。

## 冻结后的同源评测

```bash
python pddl-airport-planning/evaluation/prepare_task.py --group group_02 --output /tmp/pddl-airport-planning-group02
python pddl-airport-planning/evaluation/score_results.py --group group_02 --actual /path/to/actual-output --report /tmp/pddl-airport-planning-accuracy.json
```

actual是包含该组计划文件的目录。命令成功仅表示评分完成，结果读取JSON；不重跑模型。批次构建、挑战集属性及使用边界见[evaluation说明](evaluation/README.md)。本轮未指定正式泛化重复次数。

## 免费验证、来源与限制

消费者和诊断读取器只需Python标准库；PDDL语义评分及测试还需`unified-planning==1.3.0`：

```bash
python -m pip install unified-planning==1.3.0
python -m unittest discover -s pddl-airport-planning/tests -v
python pddl-airport-planning/tools/prepare_diagnosis.py --validate-only
```

原题固定SkillsBench `b63b7b2850226b6aa4fb5929a8c1ac7bc4d9a6af`，原输入、skill和许可保留。原历史运行未归档完整task tree，不能把本目录的新task digest冒称历史digest；后者在诊断元数据中另存。

当前数据为pilot-v2、评分为item-accuracy-v1。离线验证见[VALIDATION.json](VALIDATION.json)；先前Docker环境验收与当前打包/评分复核分别记录，不宣称本次重演完整Docker。来源、许可及抽样记录见[source](evaluation/source/README.md)。

## 可选工具：分窗与按需读取

需要分段读取长轨迹时，可在完整仓库根目录用Python 3.11或更新版本导出一个窗口，输出为包外的新文件：

```bash
python pddl-airport-planning/tools/diagnosis_io.py packet --window w0001 --out /tmp/pddl-airport-planning-window.json
```

返回JSON的`messages`可交给方法自身的模型客户端；工具只准备材料，不发送请求。12个窗口是同一条失败轨迹的连续片段，不是12个样本，也不要求12次模型调用。`record`可回溯完整记录，`input`可按需读取原输入；用法见[诊断说明](diagnosis/README.md)。使用分窗、整段读取或其他读取方式，由各方法自行决定。
