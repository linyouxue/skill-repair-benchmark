# `jpg-ocr-stat` 人工标注

## 当前状态

| 字段 | 内容 |
|---|---|
| Original-Skill 证据 | `jpg-ocr-stat-original-skill-v11x-20260903-r001-recovery001` |
| 原始结果 | 有效运行，reward 0，32/60 iterations，终止原因为 `stuck` |
| Skill 暴露 | 5 个官方 `SKILL.md` 正文 persistent preload，digest 校验一致 |
| 当前阶段 | 最小 Gold repair 已收敛：直接基于官方原始 `image-ocr/SKILL.md` 增加 exact structured-field adjudication 约束 |
| 验收标准 | 官方 verifier 对最终 Excel 的单 sheet、schema、排序、null handling 与逐行 oracle equality 全部通过 |
| 最终状态 | `verifier-only validated (1/1; final-artifact completion)` |
| 最终归因 | 1 个 `skill_ambiguous_guidance`：multi-pass coverage aggregation 与 exact-field conflict adjudication 未区分 |
| 产物归档 | 四轮 `artifacts/` 均为空；live verifier 计分有效，但无法独立重放工作簿或核对 SHA |

## 修复前诊断

模型完成了 22 张收据的多轮 OCR 并打印过完整记录，但每次修改字段解析规则都会重新执行完整批次。最终写 Excel 的命令又启动了第 5 次全量 OCR，连续四次轮询没有新输出，任务以 `stuck` 结束，`/app/workspace/stat_ocr.xlsx` 未生成。

首个关键错误出现在轨迹 event 9：模型对每张图片组合多种预处理和 PSM，并按整页平均置信度只保留一份 OCR 文本，却没有把各 pass 的文本、字段候选及来源持久化。event 15、20、25 和 30 又重复运行完整批次。定向 OCR 曾找到更可靠的字段文本，但最终选择逻辑没有利用这些证据。

官方 verifier 在文件存在性断言处停止，结果为 0/1。离线将最后一次完整打印的 22 行记录与 oracle 对比，仅用于诊断，可确认仍有 3 个字段不匹配；这些 oracle 值没有写入修复 Skill。

## Round 1 修复标签

| ID | 标签 | Skill | 位置 | 修复内容 |
|---|---|---|---|---|
| RI-001 | `skill_missing_guidance` | `image-ocr` | `Batch Processing Multiple Images / Checkpointed Batch OCR` | 增量缓存每图、每 pass 观察；解析只消费缓存；仅对证据不足的图片有限重试；单独物化并检查最终产物。 |
| RI-002 | `skill_ambiguous_guidance` | `image-ocr` | `Multi-Pass OCR Strategy / Quality Self-Check` | 保留 pass provenance；按字段结合标签邻近、关键词优先级、格式、版面和跨 pass 共识裁决；整页平均置信度不作为整份文本的唯一选择依据。 |

`xlsx` Skill 不计入修复：原 Skill 已要求保存，模型最终代码也包含 `wb.save()`；未写盘是上游 OCR 被反复嵌入最终命令导致，没有证据表明 Excel 指导本身存在缺陷。

## Round 1 验证

`jpg-ocr-stat-round-1-r001` 不计入方法结果：执行在第一次模型请求前停于
OpenHands 安装阶段，900 秒后超时；该次记录为 0 provider 请求、0 token、
无 verifier 和 reward，属于基础设施无效运行。

`jpg-ocr-stat-round-1-r002` 从本机复用了经收据校验的
同一 OpenHands runtime（CLI commit `2df8a2835d3f1bd2f2eadf5a7a2e1ad0dfb0d271`，
SDK/tools `1.28.1`）。本地缓存不匹配时直接失败，不降级到其他版本。

`jpg-ocr-stat-round-1-r002` 同样不计入方法结果：本地 OpenHands runtime 已
成功安装，但旧版 LiteLLM 容器连通性探针仅支持 `curl`；该任务镜像没有
`curl`，因此仍在首个模型请求前结束，0 provider 请求、无 verifier/reward。
执行器已将内部探针修为 `curl` 或 Python 标准库直连（显式绕过公网代理），
下一次有效验证编号为 `jpg-ocr-stat-round-1-r003`。

## Round 1 有效验证

`jpg-ocr-stat-round-1-r003` 是有效运行：59/60 iterations、59 次 provider
请求、57 次完成的工具调用，正常 `end_turn`，无基础设施或 verifier 错误。
官方 verifier 首个且经离线全表比较确认的错误为：`071.jpg` 的
`total_amount` 输出 `17.76`，oracle 为 `17.70`。OCR 文本同时包含较早的
sales total 与较后的 adjusted total；模型仍让重复度和通用 `TOTAL` 规则
覆盖了最终计算阶段语义。

## Round 2 修复与验证

Round 2 在 `image-ocr/SKILL.md` 增加金额候选语义裁决：先执行任务排除词，
再区分最终应付、调整/舍入后金额与较早的 sales/subtotal，并禁止把频次、
最大值或最后一个数字当作跨语义类别的主判据。

`jpg-ocr-stat-round-2-r001` 是有效失败：12/60 iterations、12 次 provider
请求、10 次工具调用，正常 `end_turn`，reward 0。它修正了上一轮
`071.jpg` 的 `17.76 -> 17.70`，但完整输出相对 oracle 仍有 4 个字段错误：

| 文件 | 字段 | Round 2 输出 | Oracle |
|---|---|---:|---:|
| `009.jpg` | `total_amount` | `11.00` | `26.60` |
| `052.jpg` | `total_amount` | `10.08` | `10.00` |
| `077.jpg` | `total_amount` | `21.30` | `23.25` |
| `078.jpg` | `total_amount` | `100.00` | `92.80` |

首错 `009.jpg` 的机制可以从轨迹直接复核：解析器先命中商品表头
`QTY ITEM TOTAL`，本行没有金额便无条件读取下一行，误把商品金额当成总额；
随后又在该 OCR pass 首次命中时提前返回，没有继续枚举后面的最终应付行。

## Round 3 修复与验证

Round 3 继续在官方 Skill 基础上增加实现门槛：完整枚举候选、显式排除商品
表头、限制 next-line fallback、保存候选语义和拒绝理由，并要求完成前审计
实际选择行为，而不只检查 Excel schema。

`jpg-ocr-stat-round-3-r001` 仍是有效失败：21/60 iterations、21 次 provider
请求、20 次工具调用，418.8 秒，正常 `end_turn`；`execution_ok=true`，
无 API、Docker、OpenHands、verifier、超时或导出错误。5 个 Skill 正文已经
persistent preload，观测 digest 与预期一致；`n_skill_invocations=0` 表示没有
显式 `invoke_skill`，但不表示正文不可见。

官方 verifier 先通过文件存在、单 sheet、schema、排序及 null 规则，随后在
严格逐行比较的首个错误处停止：`034.jpg` 日期输出 `2018-08-09`，oracle 为
`2018-03-09`。查看原图可直接确认打印日期是 `09/03/2018`，不是 verifier
问题。离线使用同一 task digest 的 oracle 对 verifier 已打印的 22 行做完整
诊断比较，共发现 5 个字段错误：

| 文件 | 字段 | Round 3 输出 | Oracle |
|---|---|---:|---:|
| `034.jpg` | `date` | `2018-08-09` | `2018-03-09` |
| `071.jpg` | `total_amount` | `17.76` | `17.70` |
| `078.jpg` | `total_amount` | `100.00` | `92.80` |
| `090.jpg` | `date` | `2017-03-19` | `2017-03-13` |
| `097.jpg` | `date` | `2016-01-12` | `2018-01-12` |

模型确实实现了“遍历多处 total 再选择”和部分表头过滤，因此修正了 Round 2
的 `009.jpg`；但它仍只对每张图运行一次 OCR，`MoneyCandidate` 仅保存
`amount/rank/line_index`，没有保存 pass、原始行、normalized label、
semantic class 或 rejection reason，也没有生成 candidate audit 或触发定向
重试。金额代码仍使用 `amounts[-1]`，同级候选直接选择页面最靠后的一个；
`TOTAL SALES` 又被排在 `TOTAL AFTER ADJ` 之前。日期解析同样取单次 OCR 的
首个合法结果，因此把被 OCR 误读的月份、日期或年份直接写入工作簿。

## 最终判断

| 字段 | 结论 |
|---|---|
| 最终状态 | `not-agent-validated` |
| 主要失败标签 | `agent_did_not_follow` |
| Gold eligibility | `false` |
| 四轮有效验证错误字段数 | Round 1：1；Round 2：4；Round 3：5；Round 4：7 |
| 是否继续修 Skill | Round 4 已把规则前置为 blocking gate，但模型仍弱化或跳过关键约束；继续只改措辞的边际价值很低 |

上述判断只对应当时的 Round 4 candidate；后续继续压缩并重构 repair 后，最终 Gold
不再沿用 Round 4 的长 blocking gate，而是回到官方原始 Skill，只保留 exact
structured receipt fields 所需的最小 adjudication contract。最终状态以下文
“最终 Gold 收尾”为准。

## Round 4 用户授权的追加修复

用户在审阅 Round 3 的有效失败后，显式要求继续强化 Skill 并重新运行；因此本轮是
对原 3 轮上限的人工覆盖，不改变前三轮的历史结论。

Round 4 将强制执行以下新增约束：每个非空日期和金额至少需要两个不同 OCR
配置对同一来源区域给出一致结果；任何数字分歧必须触发定向第三次 OCR；禁止
单 pass 首个合法日期、`amounts[-1]` 和未经验证的 next-line fallback；每个
候选必须保存 pass、原始行、位置、语义类别和拒绝理由；只有程序化 candidate
audit 全部通过且重开后的产物与 audited rows 一致时才允许结束。

候选 Skill 位于 `round-4/bundle/skills/image-ocr/SKILL.md`，验证 rollout 为
`jpg-ocr-stat-round-4-r001`。本节不包含具体失败文件名或 oracle 值。

### Round 4 验收结果

该 rollout 是有效失败：`execution_ok=true`、reward 0、6/60 iterations、6 次
provider 请求、4 次工具调用，正常 `end_turn`；无 API、Docker、OpenHands、
verifier、超时或导出错误。总耗时 6050.1 秒，其中 5752.6 秒发生在 agent setup，
并非模型迭代耗尽。5 个 Skill 正文均已 persistent preload 且 digest 匹配，
`n_skill_invocations=0` 仅表示没有显式工具调用 Skill。

官方 verifier 完成了严格逐单元格比较。离线复核其打印的完整 23 行后，共发现
7 个错误，全部是 `total_amount`；所有日期均正确：

| 文件 | Round 4 输出 | Oracle |
|---|---:|---:|
| `052.jpg` | `1000.00` | `10.00` |
| `063.jpg` | `54.00` | `85.54` |
| `069.jpg` | `6.00` | `9.90` |
| `074.jpg` | `24.00` | `102.00` |
| `078.jpg` | `80.00` | `92.80` |
| `087.jpg` | `0.00` | `538.00` |
| `088.jpg` | `80.00` | `99.80` |

Round 4 的强化确实改变了实现：模型为每张图生成了多个 OCR pass，并要求同一
归一化值至少出现在两个 pass 中，因此修正了 Round 3 的三个日期误读以及
`071.jpg`。但实现仍弱化了 Skill 的关键门槛：它只按 value 和 pass ID 聚合，
没有验证候选来自同一语义字段和来源区域；只有“没有任何 winner”才运行 targeted
pass，而不是候选分歧时运行；没有持久化 candidate audit；next-line pairing 仍缺少
空间和字段语义确认；最终只检查 sheet、表头、行数和排序，没有执行 Skill 明确要求的
blocking assertions。模型随后主动结束并声称已验证完成。

因此，Round 4 相比 Round 3 的错误字段数从 5 增至 7，整体发生回退。由于规则已
完整、明确且处于提示前部，而模型仍只选择性落实其中一部分，本轮继续归为
`agent_did_not_follow`，不归为 verifier 问题，也不能作为 agent-validated Gold repair。

## 最终 Gold 收尾（2026-09-17）

后续人工审计发现，早期 repair 把 task-specific gate 叠得过长，不适合作为最终
Gold。最终版本重新以官方原始 `image-ocr/SKILL.md` 为 base，只保留一个统一缺陷：

> 官方 `Multi-Pass OCR Strategy > Combine results` 建议聚合多个 OCR pass 以提高
> 文本覆盖率，但没有区分 coverage aggregation 与 `date` / `total_amount` 这类
> exact structured fields 的候选裁决。

最终 RI-001 / D001 要求：各 OCR pass 保持分离并保留候选的 pass/receipt-region
来源；非空读数冲突时仍视为 unresolved，不允许用全局 frequency / majority vote
直接选值；`total_amount` 先应用任务 exclusion rules，再以明确 final-payable 语义
优先，generic `TOTAL` / `AMOUNT` 只作 fallback；冲突时仅对相关字段/行做 targeted
OCR；已解决字段冻结；最终写盘后 reopen 核对 schema、排序和 resolved values。

该最小 repair 下，最后两个 unresolved total 已通过 field-local targeted OCR 明确得到：

- `011.jpg`：`TOTAL 15.00` → `15.00`
- `078.jpg`：`GRAND TOTAL 92.80` → `92.80`

将这两个已经解析出的字段写回最终 checkpoint 后，直接调用官方
`verifier/test_outputs.py::test_outputs()`，输出的 `results` sheet 共 23 行（表头 +
22 条数据），与 `stat_oracle.xlsx` 逐行严格一致，得到 `VERIFIER_ONLY_PASS`。

因此最终 Ground Truth 只保留上述 1 个 `skill_ambiguous_guidance`，不再把早期
Round 1–4 的多条 task-specific 强化规则拆成额外 Gold defects。正式方法比较时应
保持该精简 repair，并给 22-image multi-pass OCR 足够且统一的 iteration budget。

