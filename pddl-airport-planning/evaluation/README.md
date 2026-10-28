# 冻结后的同源输入评测

原环境包含1—30题，全部排除于严格未见测试。上游IPC2004 Airport套件共50题，选定31/32、36/37、46/47三组，每组仍交两份计划。1—30的60个domain/problem与原环境已核对。

| 批次 | 实例 | 变化 | 可解性 / 环境状态 |
|---|---|---|---|
| group_01 | 31、32 | Airport4 / Half Munich，9/10架飞机 | 已有426/460步有效见证 |
| group_02 | 36、37 | Airport5 / Munich，2/3架飞机 | 已有合法见证，先前Docker验收2/2 |
| group_03 | 46、47 | Airport5 / Munich，6/8架飞机 | 已有292/358步有效见证 |

六题均已有免费求解的合法见证，验收原规则和全部目标，不要求最优。逐阶段累计目标或飞机优先搜索只用于策展证明可解，未写入参评skill；能解不代表在原Agent预算下同难度。只有group_02先前做过Docker端到端验证，另两组为本地语义验证。

这是按公开输入特征或训练已知错误机制设计的同源挑战集，不是难度匹配的随机IID样本，未按待测方法成绩选题。修复仅使用原任务和diagnosis，evaluation输入、GT、策展代码及其成绩不回流修复/调参/选版。正式比较固定模型、执行预算和skill版本，使用全新工作区；本轮未制定重复次数。

## 导出与评分

从仓库根运行，目标目录必须不存在：

```bash
python pddl-airport-planning/evaluation/prepare_task.py --group group_01 --output /tmp/pddl-airport-planning-group01
python pddl-airport-planning/evaluation/score_results.py --group group_01 --actual /path/to/actual-output --report /tmp/pddl-airport-planning-group01-score.json
```

同样支持group_02/03。actual为实际计划目录，文件名按对应inputs/problem.json。导出只含原题、原skill、选定组输入和评测侧verifier，不带diagnosis、oracle、其他组或策展参考程序。verifier在Agent结束后部署，不能把整个仓库作为Agent输入。

采用[任务根说明](../README.md)中的item-accuracy-v1，时耗不加权、严格完成另存；正常评分错误按正确率计分，基础设施异常单列。每组分数单独报告，不把批内多个job当成独立Agent实验；跨批汇总和重复次数由正式协议确定。命令退出0只表示评分完成。

已准备数据不等于已有方法成绩。[结果提交说明](results/README.md)只接收真实产物/原始评分，不制造空排行榜。原数据来源与许可见[source](source/README.md)。
