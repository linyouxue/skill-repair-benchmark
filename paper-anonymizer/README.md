# 论文匿名化评测

基于 SkillsBench 的 `paper-anonymizer`。任务要求编辑整篇论文 PDF，清除印刷内容和文档属性中的作者线索，同时保留科学内容和版式。

| 目录 | 内容 |
|---|---|
| [task.md](task.md) 和 [environment](environment/) | 三篇原题训练 PDF、作答环境和两份原 Skill |
| [diagnosis](diagnosis/README.md) | 原题、原输入、GPT-5.2 原 Skill 失败轨迹和允许反馈 |
| [evaluation](evaluation/README.md) | 三个测试组、隔离导出入口及接入说明 |
| [verifier](verifier/) | 逐项正确率入口和训练集参考答案 |
| [result](result/README.md) | 第五轮冻结 Skill、原题实际提交及复算证据 |
| [evaluation/results](evaluation/results/README.md) | 三组测试的模型评测状态 |
| [source](source/README.md) | 逐篇出处、分组和评分项的构造方法 |

## 训练与泛化测试

| 数据集 | 论文数 / 总页数 | 应遮字段中位于作者栏外的项数 | 评分分母 |
|---|---:|---:|---:|
| train | 3 / 40 | 8/20（40.0%） | 67 |
| group_01 | 6 / 30 | 18/44（40.9%） | 94 |
| group_02 | 3 / 15 | 12/22（54.5%） | 47 |
| group_03 | 6 / 30 | 24/44（54.5%） | 94 |

训练集保留原题三篇 PDF。三个泛化组取自 Interspeech 2024，共 15 篇互不重复的五页论文，每三篇的应遮字段数均为 7、7、8。比较 `group_02` 与 `group_03` 可以在相同栏外占比下观察论文数翻倍的影响。比较 `group_01` 与 `group_03` 可以在相同论文数和评分分母下观察后页致谢增加时的表现。训练论文的版式、篇幅各异，现有分组无法单独估计两个因素的交互效应。

## 同学接入

用训练组和诊断材料修复、选版，冻结完整 Skill 后再逐组导出。填写执行器参数时，任务 ID 用 `paper-anonymizer`，`tasks_root` 指向导出目录的父级。每次运行处理该组全部 PDF，保存至 `/root/redacted/`。

```bash
python paper-anonymizer/evaluation/prepare_task.py --split group_01 --output /tmp/paper-g1/tasks/paper-anonymizer
```

## 评分

**正确率 =（正确遮盖的字段数 + 正确保留的区域数 + 元数据清理合格的论文数）÷ 该组全部标注项数。** 每项一分。

| 计分项 | 检查方式 |
|---|---|
| 遮盖字段 | 检查标注处的可见字迹、可提取文字和关联外链。跨行或跨页致谢作为一项，全部标注行均须清除。 |
| 保留区域 | 将逐页抽样的正文与标题区域同输入 PDF 的渲染进行比较。 |
| 文档属性 | 每篇一项，清除作者、标题、主题、关键词和嵌入的 XMP。 |

缺交、损坏、改变页面几何或丢失全部标注保留区时，该篇计零。其他论文照常评分。例如训练集中第二篇有 19 项，若仅漏掉跨页致谢，得 18/19。
