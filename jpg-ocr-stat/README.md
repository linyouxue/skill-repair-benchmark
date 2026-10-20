# JPG OCR Stat：按字段正确率评分的 SkillsBench 任务

这是原 [SkillsBench `jpg-ocr-stat`](https://github.com/benchflow-ai/skillsbench/tree/9a1f4dd5f7659f75707435da3ce854b6e48321d1/tasks/jpg-ocr-stat) 的独立任务副本。原任务有 **22张小票、44个日期/金额字段**。本目录保留原题、图片、环境、5个 Skill、参考表和 oracle，只把原来整份 Excel 全对才得1分的 verifier，改为逐字段正确率。

它使用原 SkillsBench 的22张图片，和本仓库另一个目录里的120/40/40划分数据集分别使用、分别报告。

需要用已有Opus轨迹修复Skill的同学，从 [diagnosis/README.md](diagnosis/README.md) 开始：这里提供79任务结果中JPG最终选用运行的索引、无损分窗、22张原图、原Excel和允许的逐字段反馈，以及不会调用模型的读取入口。

```text
jpg-ocr-stat/
├── task.md                  # 原任务提示与原生执行配置
├── environment/
│   ├── Dockerfile           # 原容器环境和依赖
│   ├── workspace/           # 原22张JPG，位于dataset/img/
│   └── skills/              # 原5个Skill、支持文件和许可
├── oracle/
│   └── solve.sh             # 原参考解法，未修改
├── verifier/
│   ├── test.sh              # 原生入口，写连续reward及CTRF
│   ├── test_outputs.py      # 日期/金额44项独立检查
│   ├── score_accuracy.py    # 正确率计算，也可单独评测Excel
│   ├── write_reward.py      # 验证评分完成后写reward
│   └── stat_oracle.xlsx     # 原22票参考表，未修改
├── diagnosis/
│   ├── README.md            # 同学接入Diagnoser的使用说明
│   ├── index.json           # Opus原始运行的证据、产物与分窗索引
│   ├── records/             # 动作、唯一消息、API交换及ATIF关联
│   ├── windows/             # 无损连续分片，每窗附齐22张原图
│   └── outputs/             # 原Excel、实际预测及离线派生反馈
├── tools/
│   ├── prepare_diagnosis.py # 从指定原运行离线构建诊断包
│   └── diagnosis_io.py      # 构造图文输入、按ID回溯、保存方法结果
└── tests/
    ├── test_score_accuracy.py # 合成Excel与评分边界测试
    ├── test_native_reward.py  # pytest→CTRF→reward链路测试
    └── test_diagnosis_io.py   # 诊断输入、图像、来源及结果保存边界
```

## 评分口径

Agent仍须输出 `/app/workspace/stat_ocr.xlsx`，唯一工作表为 `results`，表头为 `filename,date,total_amount`。

```text
reward = field_accuracy = (日期正确数 + 金额正确数) / 44
date_accuracy = 日期正确数 / 22
amount_accuracy = 金额正确数 / 22
receipt_joint_accuracy = 日期和金额都正确的票数 / 22
```

- 每张票的日期、金额独立计分。例如只错1个字段，得到 `43/44 ≈ 0.97727`；只对22个字段，得到 `0.5`。
- 缺文件、不可读文件、错误工作表或错误表头按空预测评分；缺行、空字段、错误字段都保留44字段固定分母。
- 按文件名对应参考表，使用既有离线评测脚本的单元格字符串精确比较：`None`转为空字符串，其他值取`str(value)`。不新增金额舍入、模糊匹配或日期归一化。
- 行顺序、行数、重复文件名、额外文件名、日期/金额类型和格式问题另记为 `delivery_issues`，不把字段正确率整体清零。重复文件名沿用既有评测器的后行覆盖规则；无关额外行不给分。因而 `reward=1` 不一定等于格式完全合规，需同时查看交付状态。
- 只返回逐票日期/金额的对错、交付状态和汇总，不在评分报告中输出参考答案值或预测值。参考表本身仍是随任务发布的原评分资源，应只部署到 verifier 侧。

这里复用 [扩展数据集评测器的读取与汇总规则](../jpg-ocr-skill-repair-dataset/evaluation_only/runtime/score_extended.py)，但评分样本使用原 SkillsBench 的22票参考表，不使用扩展数据集的GT，也不增加冲突/歧义分层。

## 在 SkillsBench / BenchFlow 中使用

将本目录作为原生任务目录交给现有执行器，或者将本目录内容复制到你自己的 SkillsBench checkout 的 `tasks/jpg-ocr-stat/` 后使用原运行命令。无需修改执行器代码。

- `task.md` 的原 `verifier.type=test-script`、`timeout_sec=600`、hardening设置保留。
- verifier仍由框架部署到 `/verifier/`；入口为 `/verifier/test.sh`，实际产物路径不变。
- uv、pytest、pytest-json-ctrf、openpyxl版本仍分别为 `0.9.7 / 8.4.1 / 0.3.5 / 3.1.5`。
- 正常评分产生 `/logs/verifier/accuracy.json`、`ctrf.json` 和 `reward.txt`。CTRF中44项测试的通过数除以44就是reward。
- pytest退出1表示有字段错误，入口仍写入连续分数；依赖/收集错误、缺失或不完整的CTRF不会被伪装成正常0分。每次运行先移除旧评分文件，防止复用旧reward。
- BenchFlow允许 `[0,1]` 内的小数reward，但它的 `task_passed` 仍以 `reward == 1.0` 判定。比较方法时请汇总 `reward` / `field_accuracy`，不要只统计 `task_passed`。

## 只评测同学交回的Excel

在已有 `openpyxl==3.1.5` 的Python环境，从仓库根目录运行：

```bash
python jpg-ocr-stat/verifier/score_accuracy.py \
  --actual /path/to/stat_ocr.xlsx \
  --report /path/to/accuracy.json
```

默认读取本目录原 `verifier/stat_oracle.xlsx`。`accuracy.json` 包含 `reward`、`all_receipts`、`field_feedback`、`delivery_status` 和 `delivery_issues`。这是免费本地评测，不会启动Agent或调用模型。命令执行成功表示评分完成，分数应从JSON读取；评分基础设施异常会以非零状态退出。

## 免费回归验证

复用上述原固定版本依赖，不需要调用模型：

```bash
python -m unittest discover -s jpg-ocr-stat/tests -v
```

测试覆盖全对、部分正确、缺文件、缺行、空值、错误sheet/header、类型/格式、重复/额外文件名，以及实际pytest的44字段CTRF到连续reward的写入。正常评分失败与评分基础设施错误分别验证；测试只创建临时合成Excel，不修改已有实验。

## 来源与改动范围

来源固定为 SkillsBench 提交 [`9a1f4dd5f7659f75707435da3ce854b6e48321d1`](https://github.com/benchflow-ai/skillsbench/commit/9a1f4dd5f7659f75707435da3ce854b6e48321d1) 的 `tasks/jpg-ocr-stat/`。原 `task.md`、`environment/`、`oracle/`、`verifier/stat_oracle.xlsx` 逐文件保留；`pdf`、`xlsx` 等Skill各自附带的许可文件也保留，遵循原许可。

有意替换 `verifier/test.sh` 和 `verifier/test_outputs.py`；新增评分核心、reward写入器、离线测试及本说明。诊断包另从已有Opus运行派生，原reward与新正确率分别标注。原题仍保留原来的输出要求和措辞，**评分语义以本README的逐字段正确率为准**。已有训练集/测试集实验、历史轨迹、Excel和成绩均未重跑或回填。
