# Flink 作业阶段统计评测

基于 SkillsBench 的 `flink-query`。任务要求用 Java/Flink 从 Google 集群日志中筛出正常结束且有提交活动的作业，再输出每个作业在单个活动阶段内的最高提交次数。任务包包含一组修复输入、三组受控泛化测试和已有的三类运行结果。

| 目录 | 内容 |
|---|---|
| [task.md](task.md) 和 [environment](environment/) | `repair` 修复题、冻结日志、Java 骨架和完整原 Skill |
| [diagnosis](diagnosis/README.md) | `repair` 原 Skill 失败的实际输出、分数和阶段反馈 |
| [evaluation](evaluation/README.md) | 三组泛化输入、隔离导出入口和接入说明 |
| [verifier](verifier/) | 连续正确率入口及 `repair` 参考答案 |
| [result](result/README.md) | 原 Skill、冻结修复 Skill 和修复组运行证据 |
| [evaluation/results](evaluation/results/README.md) | 四组成绩对照、逐次索引和补测记录 |
| [source](source/README.md) | Google 日志来源、构造方式与验证记录 |

## 修复与泛化测试

| 数据集 | 作业数 | 应输出 / 应排除 | 双阶段作业 | 用途 |
|---|---:|---:|---:|---|
| `repair` | 1,324 | 644 / 680 | 32 | 修复、反馈和选版 |
| `scale` | 2,648 | 1,288 / 1,360 | 64 | 作业规模翻倍 |
| `stages` | 1,324 | 644 / 680 | 64 | 增加双阶段作业 |
| `combined` | 2,648 | 1,288 / 1,360 | 128 | 同时增大规模和双阶段占比 |

四组共 7,944 个互不重叠的作业，使用相同的题面、输入格式和输出路径。每组各自保留原题的正负例结构，包含时间间隔在 600 秒附近的边界样例。

## 同学接入

先用 `repair` 和诊断材料修复、选版。冻结一份完整 Skill 后，分别导出三组泛化任务。导出目录的父级作为 `tasks_root`，沿用现有方法 adapter 和 BenchmarkExecutor，任务 ID 为 `flink-query`。每组使用独立的 rollout ID。参考答案和评分反馈由评测侧部署。

```bash
python flink-query/evaluation/prepare_task.py --split scale --output /tmp/flink-scale/tasks/flink-query
```

## 环境准备

在 Linux、WSL2 或 macOS 安装 Python 3.12+ 和 Docker 后，在仓库根目录执行免费环境检查。该命令构建镜像，并在断网的新容器中分别用 root 和 Agent 用户编译、运行一个独立的 Flink 小程序。

```bash
python flink-query/tools/check_environment.py
```

Docker 构建阶段按原 `pom.xml` 准备 Maven 依赖。Agent 与 verifier 使用镜像自带的离线缓存。首次构建需要联网，冷构建时限为 30 分钟。Maven 默认使用华为云镜像，也可通过 `--maven-repository-url` 指定其他 Maven Central 镜像。实际模型运行按仓库的 [执行器接入说明](../DELIVERY_GUIDE.md) 配置 API。

## 评分

连续正确率为 **（正确输出数 + 正确排除数）÷（输入作业数 + 未知输出 ID 数 + 非法行数）**。正例须恰好输出一次且计数正确，负例须无输出。缺失、不可读、空输出或无合法 tuple 时计 0。阶段和边界反馈另存于 `stage_feedback.json`。

每个作业按 Task SUBMIT 事件划分阶段。两次提交间隔恰好 600 秒时合并为同一阶段，超过 600 秒时开启新阶段。

替换前的原题和三批旧评测结果可查阅[历史提交](https://github.com/linyouxue/skill-repair-benchmark/tree/b53bf2f7d10a5c576cccfe05ddbaafdc2d32d155/flink-query)。
