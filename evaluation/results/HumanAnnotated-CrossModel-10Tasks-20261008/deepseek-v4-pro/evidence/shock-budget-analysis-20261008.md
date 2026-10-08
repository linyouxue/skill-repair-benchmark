# Shock 60 轮预算耗尽分析

耗尽的是 60 次 parent iteration，而非 120 元账户预算。模型始终停留在获取/检查输入、恢复网页访问与安装浏览器阶段，未进入保存经济模型的阶段；最终工作簿与公开初始模板逐字节一致。网络障碍和缺少题目指定的 Playwright MCP 是真实混杂，不能把该结果归为 Skill 的唯一因果或纯模型能力失败。

本报告为只读审计，没有重跑 Shock、修改 Skill/verifier 或追加付费调用。

## 60 轮如何花掉

| 请求轮号 | 阶段 | 请求数 | 占 60 轮 | 输出 token | reasoning token |
|---|---|---:|---:|---:|---:|
| 1–7 | 模板定位与逐表检查 | 7 | 11.67% | 4,152 | 2,942 |
| 8–8 | 输出上限被全 reasoning 消耗 | 1 | 1.67% | 32,768 | 32,768 |
| 9–12 | 依赖检查与重复安装 | 4 | 6.67% | 6,614 | 6,142 |
| 13–29 | PWT/ECB/FRED/IMF 数据源探索 | 17 | 28.33% | 18,627 | 15,316 |
| 30–40 | Anubis 反机器人挑战研究与旧版 PWT 下载恢复 | 11 | 18.33% | 14,425 | 11,621 |
| 41–52 | 旧版 PWT 解析/变量检查及升级到 PWT 11 | 12 | 20.0% | 5,318 | 2,297 |
| 53–56 | IMF WEO/API 访问恢复 | 4 | 6.67% | 6,113 | 4,906 |
| 57–60 | Playwright 与浏览器临末安装 | 4 | 6.67% | 1,481 | 1,108 |

第 13–56 轮共 44 次请求（73.33%）用于外部数据获取、可达性恢复与源文件检查。其中 30–40 轮共 11 次请求专门研究 Anubis 反机器人脚本/源码与挑战流程；41–52 轮又继续解析旧版 PWT、核对变量并重新下载 PWT 11。选择新版本本身有公开任务所需最新年份的理由，问题是这些工作耗尽了交付窗口，任何已取得的局部输入都没有写进最终模板。

第 8 轮输出 32,768 token，全部为 reasoning，finish_reason=length，工具动作数为 0。这一轮的长思考耗费独立输出/时间预算，却没有产出可执行动作；它消耗 1/60 parent 轮，不能把它说成独自耗掉 60 轮。

## 实际障碍与恢复策略

- Dataverse 的首次 PWT 文件实为反机器人 HTML（第 19 轮反馈），模型随后下载 Anubis JS/Go 源码并写下载 helper。第 30 轮有明确 timeout。第 40 轮恢复下载后，41–45 轮已进入 PWT Excel 数据/metadata 读取；并非一直完全取不到任何数据。
- FRED 第 20 轮 HTTP 200；ECB 第 28 轮解析 CSV。模型仍未把这些局部输入写入最终工作簿。
- IMF 第 14、55、56 轮出现 HTTP 403；第 56 轮部分 API 返回 200，不能由此断言所需 GDP 级别与增长序列均已齐备。
- 题目原文明确要求 “Use Playwright MCP.”；公开 Dockerfile 没有安装 Playwright/browser/MCP，model 全 60 个请求的工具目录均无该工具。到第 57 轮才检查 Python Playwright，随后 58–60 轮安装包和 Chromium；MCP 缺失与网络可达性属于 experiment-fidelity 风险。
- 模型没有对恢复过程设短预算、没有先保存已完成的模板输入/公式骨架，也没有转入 HP filter 与生产函数计算。仅增加 parent 轮数无法证明会解决这些障碍；当前证据不支持盲目加轮数或把缺陷唯一归到通用 xlsx Skill。

## 结果与健康边界

Agent 执行 1086.5 秒（18.11 分钟），总运行 1248.0 秒（20.80 分钟）。60 次模型请求、59 次工具动作、1 个任务 prompt；没有 text-only continuation。provider prompt token 3,601,913，其中 cache hit 3,535,232；输出 89,498、reasoning 77,100、累计 total token 3,691,411。累计输入包含重复上下文，不能当成独立信息量。

原模板与 pre-verifier 真实导出均为 62,018 字节，SHA-256 `633dc9a157273c9f643c2b267440c57babb4b1cc8b5f1e3ee8e930001834e097`；逐字节一致，五张表总公式数均为 0。轨迹中保存 workbook/编辑公式动作均为 0。只比较 agent 导出，未把 verifier 生成的 `test-supply_modified.xlsx` 当作模型产物。

CTRF：1/9 PASS；只有 required_sheets_exist 通过，数据、公式、HP filter、生产函数等八项失败。这里只投影 summary 与 test name/status；不读取或展示 hidden checker。

validator：exit 0，healthy 1/1，required ACP/LLM/results.jsonl、token/timing 元数据完整。该门只证明轨迹/结果健康；结合指定浏览器缺失和访问障碍，发布判断为 **publishable with attribution quarantine**：评分与描述性行为可保留，纯能力/Skill 因果标签需隔离。native n_skill_invocations=0，但完整 Skill 正文注入证据与 frozen bundle exposure 已核实；正文暴露不能证明唯一因果。

## 证据索引

- 主 run：`/mnt/c/Users/linyuanjing/Desktop/skill论文/SkillGen-benchmarking/manual_annotation_runs_deepseek/shock-analysis-supply/runs/deepseekv4pro-original-skill/shock-analysis-supply-deepseekv4pro-original-r001`。
- 精确轮号、action 摘要、HTTP/timeout/bot challenge 布尔元数据、token 数与工作簿逐表摘要见同名 JSON。
- `result.json` / `agent/acp_trajectory.jsonl` / `trajectory/llm_trajectory.jsonl` / `results.jsonl`。
- `artifacts/pre-verifier-inputs.tar.gz` 中 `root/test-supply.xlsx`，与公开 `environment/test-supply.xlsx` 比较。
- 公开 `task.md` / `environment/Dockerfile`；评分仅 `verifier/ctrf.json` summary 与 name/status。
