# 官方 Skill + Opus4.7 小票训练集 baseline

18批已完成有效评分，实际交付16份原始20行Excel及1份合并120行Excel。主指标字段正确率均值为 **60.00%**。

本报告只包含训练集：冻结的120张小票重复3次，共360次小票观测、720个日期/金额字段。三个重复不是三个数据划分，训练、验证、测试分开报告。日期和金额各占一半；划分按票据隔离、失败机制分层。原22张仅作历史开发材料。本次仅运行官方Skill baseline，没有Skill Repair调用。

**训练集三次重复结果**

| 数据集与重复 | 字段正确率 | 日期正确率 | 金额正确率 | 整票正确率 | 合并Excel |
|---|---:|---:|---:|---:|---|
| 训练集第1次 | 59.58% (143/240) | 65.00% | 54.17% | 46.67% | 未完整交付，未生成合并表 |
| 训练集第2次 | 65.00% (156/240) | 80.83% | 49.17% | 42.50% | [下载](baseline_merged/round_02_stat_ocr.xlsx) |
| 训练集第3次 | 55.42% (133/240) | 65.83% | 45.00% | 40.83% | 未完整交付，未生成合并表 |

总体日期正确率为70.56%，金额正确率为49.44%，整票正确率为43.33%。
字段正确率三次均值60.00%，总体标准差 **3.92个百分点**，范围55.42%—65.00%。标准差仅描述这3次重复的波动，不是置信区间。
官方整批全对通过数为 **0/18**；这是原整批指标，主指标仍采用字段正确率。

**冲突与歧义分层**

以下为同一固定分层三次重复的合并统计，独立票数不会因重复增加。

| 冻结分层 | 独立票数 | 字段正确率 | 日期 | 金额 | 整票 |
|---|---:|---:|---:|---:|---:|
| 未发现提示冲突 | 43 | 68.60% | 72.09% | 65.12% | 55.04% |
| 提示冲突但票面最终付款唯一 | 11 | 50.00% | 57.58% | 42.42% | 27.27% |
| 原题字面规则歧义 | 66 | 56.06% | 71.72% | 40.40% | 38.38% |

主指标包含本划分全部120张票，其中66张属于字面歧义层；其成绩单独报告，不能直接解释为模型能力不足。另列54张非字面歧义票的补充字段正确率为 **64.81%**（210/324字段观测）。保留冻结分层，不据小层结果作普遍结论。

**真实产物与评分依据**

| 槽位 | 原始Excel | 字节 | 有效评分路径 |
|---|---|---:|---|
| train-r01-b01 / attempt 1 | 未交付（正常模型FAIL） | 0 | native_original_verifier |
| train-r01-b02 / attempt 1 | [原始20行Excel](runs/train-r01-b02/selected_run/artifacts/stat_ocr.xlsx) | 5303 | native_original_verifier |
| train-r01-b03 / attempt 2 | [原始20行Excel](runs/train-r01-b03/selected_run/artifacts/stat_ocr.xlsx) | 5330 | native_original_verifier |
| train-r01-b04 / attempt 1 | [原始20行Excel](runs/train-r01-b04/selected_run/artifacts/stat_ocr.xlsx) | 5353 | native_original_verifier |
| train-r01-b05 / attempt 12 | [原始20行Excel](runs/train-r01-b05/selected_run/artifacts/stat_ocr.xlsx) | 5307 | native_original_verifier |
| train-r01-b06 / attempt 1 | [原始20行Excel](runs/train-r01-b06/selected_run/artifacts/stat_ocr.xlsx) | 5341 | native_original_verifier |
| train-r02-b01 / attempt 2 | [原始20行Excel](runs/train-r02-b01/selected_run/artifacts/stat_ocr.xlsx) | 5316 | native_original_verifier |
| train-r02-b02 / attempt 1 | [原始20行Excel](runs/train-r02-b02/selected_run/artifacts/stat_ocr.xlsx) | 5327 | native_original_verifier |
| train-r02-b03 / attempt 2 | [原始20行Excel](runs/train-r02-b03/selected_run/artifacts/stat_ocr.xlsx) | 5329 | native_original_verifier |
| train-r02-b04 / attempt 3 | [原始20行Excel](runs/train-r02-b04/selected_run/artifacts/stat_ocr.xlsx) | 5337 | native_original_verifier |
| train-r02-b05 / attempt 2 | [原始20行Excel](runs/train-r02-b05/selected_run/artifacts/stat_ocr.xlsx) | 5323 | native_original_verifier |
| train-r02-b06 / attempt 2 | [原始20行Excel](runs/train-r02-b06/selected_run/artifacts/stat_ocr.xlsx) | 5331 | native_original_verifier |
| train-r03-b01 / attempt 1 | 未交付（正常模型FAIL） | 0 | native_original_verifier |
| train-r03-b02 / attempt 1 | [原始20行Excel](runs/train-r03-b02/selected_run/artifacts/stat_ocr.xlsx) | 5325 | native_original_verifier |
| train-r03-b03 / attempt 4 | [原始20行Excel](runs/train-r03-b03/selected_run/artifacts/stat_ocr.xlsx) | 5327 | native_original_verifier |
| train-r03-b04 / attempt 2 | [原始20行Excel](runs/train-r03-b04/selected_run/artifacts/stat_ocr.xlsx) | 5342 | native_trajectory_publication_no_space_before_verifier |
| train-r03-b05 / attempt 1 | [原始20行Excel](runs/train-r03-b05/selected_run/artifacts/stat_ocr.xlsx) | 5300 | native_trajectory_publication_no_space_before_verifier |
| train-r03-b06 / attempt 1 | [原始20行Excel](runs/train-r03-b06/selected_run/artifacts/stat_ocr.xlsx) | 5347 | native_original_verifier |

逐批核对了实际归档、Excel格式/行数、原始attempt与canonical字节、普通CTRF或verified免费恢复收据。原始Excel全部保留，合并表仅拼接实际预测并按文件名排序；没有用GT替换预测或修正错误。
正常未交付Excel的批次共2个；沿用既有score_extended空预测计分，缺失字段算不正确，三次重复仍保留360票/720字段分母，不删除失败来提高准确率。缺失原表不补造，对应重复不生成不完整的120行合并表；候选选择资格仍按原规则判为不合格。
每批都预载完整5个官方Skill正文，全部18批bundle摘要一致并匹配实际观测；显式工具式n_skill_invocations逐批为[0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]，正文使用证据来自持久上下文预载记录；超时导致返回元数据缺失时，以原首个模型请求中的5份完整正文匹配收据核实，匹配使用既有日志脱敏规则，不改原Skill。实际迭代数保留于summary逐批元数据；预算60次parent、guard=1、Opus max、输出上限16384，切换前批次单并发，后续每遍最多6批并行。未读取隐藏答案指导Skill修复。

**执行兼容性与终止条件**

原Task、官方Skill、源JPG、GT和verifier源文件保持不变；最终免费check-only重新核实冻结输入与官方来源一致。执行层存在明确披露的适配：超限整图按共同规则缩放为无损PNG、合格图片URL保留字节且文字/凭据仍脱敏、HTTP响应完整缓冲、传输最多一次额外重试、失败连接池重建，以及评分shell执行副本LF规范化和固定版本离线依赖引导。
离线kit在native hardening之后部署，准备/上传/原判分合计遵守原600秒。逐批评分路径列于上表。只有明确60轮MaxIterationsReached且实际导出了Excel，才免费评分原产物一次并保留生成错误；确认评分基础设施故障也从真实产物免费恢复。预算耗尽未被当作infra重跑，未增加轮数，也未因低分重新生成。
普通空闲超时先核实实际请求与网络证据，不能仅凭末条HTTP200认定模型失败或基础设施故障。本次训练第9槽经历本机关机与代理中断，因果未确认；用户明确要求另开尝试重跑该槽，旧超时、原生0分、轨迹及费用全部保留在历史，主指标只使用所选新尝试。此前已完成8槽不重跑，后续3槽的0调用Skill部署失败单独保留为无效启动。
所有共同适配与严格恢复条件同样适用于各方法/划分。本次各尝试及诊断均保留；其他划分的结果和费用不混入本报告。
详见执行协议（历史源文件，未作为本目录入口）和传输与恢复记录（历史源文件，未作为本目录入口）。

**费用与次数**

累计确认provider usage.cost为 **$160.241402**，含历史诊断/失败。18个选定有效生成尝试的确认费用为$135.075693；其余确认费用来自保留的历史/中断尝试。
另保留 **$660.33034** 的未知费用估计，共227条事件。这不是确认扣款，不能与确认费用相加称为实际总花费。
账本共1583条网关记账尝试，HTTP状态分布为{"200": 1352, "403": 1, "unknown": 225, "402": 2, "429": 3}；这些条目包含本地池等待、失败HTTP和诊断，不等同于成功付费模型调用数。本次baseline本地美元/API次数上限按用户要求取消，仅记账；账号总usage不是本实验费用。免费验收阶段模型调用0。

机器可读汇总：[summary.json](baseline_summary_original.json)。三份round_metrics.json保留每批及分层汇总，不包含期待日期/金额。后续实验仍需按各自授权运行，本结果不包含人工或自动修复方法的成绩。

训练后续批次使用data2上的本实验独立Docker，复用原依赖镜像的相同依赖层，保留原冻结workspace COPY及Harness自动追加的完整Skill COPY和链接；构建执行副本与Compose缓存参数有适配。原Task/Dockerfile源、模型设置、原评分及分母保持不变。

第三遍第4、5批在耗尽60轮parent生成预算、且已导出真实Excel后，原Harness发布轨迹到宿主临时文件时发生ENOSPC，pytest未启动。保留原失败和账本，从原不可变任务镜像及原Excel免费执行native hardening和原verifier；没有重做模型生成。后续宿主TMPDIR设到data2上的本实验独立目录，原评分源、600秒时限和固定分母保持不变。
