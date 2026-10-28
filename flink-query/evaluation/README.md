# 冻结后的同源输入评测

同源输入来自Google clusterdata-2011-2。分别合并8个连续job/task分片，筛选窗口内可观察生命周期的正例，排除原题1324个job ID及批间重叠。字段、微秒时间、入选原始行和事件顺序保留；只拼接、过滤和重新gzip。

| 批次 | 原分片 | 正例 | 负例 | task事件行 |
|---|---|---:|---:|---:|
| group_01 | 00002—00009 | 49 | 60 | 3,422 |
| group_02 | 00010—00017 | 53 | 60 | 14,441 |
| group_03 | 00018—00025 | 60 | 60 | 23,310 |

正例按多阶段优先、其余重复提交、其余普通互斥分层，每层最多20，按固定pilot-v1:job_id哈希排序；多阶段不足时不凑数。每批负例包括20个active+KILL无FINISH、20个FINISH无activity、20个KILL无activity，按pilot-v2-neg:job_id哈希选择。负例仅描述提供窗口内输出资格，不宣称全29天生命周期完整。原162个正例和参考值不变，v2补180个真实负例。Python、独立SQLite及真实Java/Flink已交叉核对新组答案，先前3批Docker运行均通过；本次打包没有新Agent或Docker重演。

这是按公开输入特征或训练已知错误机制设计的同源挑战集，不是难度匹配的随机IID样本，未按待测方法成绩选题。修复仅使用原任务和diagnosis，evaluation输入、GT、策展代码及其成绩不回流修复/调参/选版。正式比较固定模型、执行预算和skill版本，使用全新工作区；本轮未制定重复次数。

## 导出与评分

从仓库根运行，目标目录必须不存在：

```bash
python flink-query/evaluation/prepare_task.py --group group_01 --output /tmp/flink-query-group01
python flink-query/evaluation/score_results.py --group group_01 --actual /path/to/actual-output --report /tmp/flink-query-group01-score.json
```

同样支持group_02/03。actual为真实tuple文件或分片目录，输出顺序不影响计分。导出只含原题、原skill、选定组输入和评测侧verifier，不带diagnosis、oracle、其他组或策展参考程序。参考表与负例ID只在verifier部署，不能把整个仓库作为Agent输入。

采用[任务根说明](../README.md)中的item-accuracy-v1，时耗不加权、严格完成另存；正常评分错误按正确率计分，基础设施异常单列。每组分数单独报告，不把批内多个job当成独立Agent实验；跨批汇总和重复次数由正式协议确定。命令退出0只表示评分完成。

已准备数据不等于已有方法成绩。[结果提交说明](results/README.md)只接收真实产物/原始评分，不制造空排行榜。原数据来源与许可见[source](source/README.md)。
