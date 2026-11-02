# `jpg-ocr-stat` 人工标注

## 当前状态

| 字段 | 内容 |
|---|---|
| Original-Skill 证据 | `jpg-ocr-stat-original-skill-v11x-20260903-r001-recovery001` |
| 原始结果 | 有效运行，reward 0，32/60 iterations，终止原因为 `stuck` |
| Skill 暴露 | 5 个官方 `SKILL.md` 正文 persistent preload，digest 校验一致 |
| 当前阶段 | 2026-10-09 四组冻结补跑已启动：复用 Round 15/16/17 各一次，新增 9 次，每组补齐 3 次；2 路并发，首批为 Round 15 r002 与 Round 18 r001-recovery001 |
| 验收标准 | 官方 verifier 对最终 Excel 的单 sheet、schema、排序、null handling 与逐行 oracle equality 全部通过 |
| 最终状态 | Round 16 已有修改 task 提示后的 fresh agent 通过；未修改官方 task 的历史最小 repair 仍为 `verifier-only validated`，不将两者混作原 task 的 agent-validated Gold |
| 最终归因 | 1 个 `skill_ambiguous_guidance`：multi-pass coverage aggregation 与 exact-field conflict adjudication 未区分 |
| 产物归档 | 历史轮次及 Round 15/16/17 的 `artifacts/` 为空；本次新运行在 cleanup 前由 runner 导出真实最终 Excel，并保留中间工作簿采样及字段诊断；实际文件待运行结束验收 |

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

## Round 14：用户提供七条字段抽取与交付要求（2026-10-08）

用户要求重新验证：在新一轮中去掉此前人工补充的 gate/contract，仅在官方
`image-ocr/SKILL.md` 正文前添加用户提供的七条要求，完整保留官方 bundle。
历史 Round 1–13 和 verifier-only 结论不覆盖。本轮不注入样本答案，不修改
task/verifier，不把此前 verifier-only 通过当作本轮 fresh rollout 通过。

候选：`round-14/bundle/skills/image-ocr/SKILL.md`；说明：`round-14/repair_notes.md`。
英文版验证 ID：`jpg-ocr-stat-round-14-r002`；GPT-5.2 / OpenRouter；60 iterations；
completion guard 开启；单次 fresh rollout，启动后停止监控，等待用户通知。
2026-10-08 20:22 已确认对应 Docker Compose/buildx 开始构建，代理参数已注入。
启动后停止监控；模型运行及本轮验证结果待用户通知结束后记录。

用户随后要求七条 guidance 全部使用英文，并删除额外引导句。核查发现 `r001`
已自行因 Docker 网络地址池耗尽结束，镜像已构建，但 task container 未启动、
ACP trajectory 为 0 字节。中文输入快照保留，计为基础设施失败，不计模型 PASS/FAIL；
修正后的英文候选使用 fresh `r002` 验证，不改写此前 rollout 的输入记录。

英文版 `r002` 已确认对应 task container 启动，输入快照为英文七条要求且无额外
引导句。清理仅涉及一个已核实无容器的旧 JPG 网络；不改执行器或模型配置。
停止监控，等待用户通知完成后验收。

### Round 14 英文版 r002 验收

用户通知结束后验收：本轮为有效模型失败，不是基础设施失败或极短异常停工。

| 指标 | 结果 |
|---|---|
| Rollout | `jpg-ocr-stat-round-14-r002` |
| 模型 | `openrouter/openai/gpt-5.2` |
| 正式评分 | reward `0`，`task_passed=false` |
| 执行健康 | `execution_ok=true`；无 API、verifier 或导出错误字段 |
| 官方子测试 | `::test_outputs`：failed（0/1） |
| 失败断言 | 逐行内容相等断言 `row_a == row_e`；未公开 oracle 字段值 |
| Iterations / provider | 18/60；18 次请求和成功响应 |
| 工具 / Skill 显式调用 | 17 次工具调用；`n_skill_invocations=0`，但 5 个 Skill 全文 persistent preload 已验证 |
| Guard | 开启；续跑次数 0；最终真实调用 `finish` |
| 总耗时 / 成本 | 577.8 秒（约 9 分 38 秒）；$0.5635525 |
| 总 token | 784700；输入/输出拆分计数为 0，不当作真实零消耗 |
| 轨迹完整性 | validator `healthy=true`；ACP 22 events、LLM 18 exchanges、trainer row 完整 |
| 文件交付证据 | 请求 15 成功重新打开工作簿，打印 `results` sheet、3 列及 22 条数据；请求 17 确认文件存在，5361 bytes |

修补规则只有部分落实，不能把模型自报“完成”当作字段准确性验证：

| 用户要求 | 轨迹中的实际实现 | 证据位置 |
|---|---|---|
| 数字补位须有同字段票面证据 | `has_any_decimal_elsewhere` 取整张票据是否出现小数；据此或数字长度插入小数位，而非确认目标字段的标点 | 请求 14，`parse_amount_token` / `extract_total_amount` |
| 候选保留原文、标签、区域及来源，跨行确认同字段 | 候选仅为 `(priority, line_index, amount)`；当前行或下一行直接取 `nums[-1]`，未保存完整字段证据或确认跨行绑定 | 请求 14，`extract_total_amount` |
| 日期解释和修复须有票面证据 | 非法月份使用 `mo % 10` 转成合法月份，并返回首个合法日期，缺少局部重识别裁决 | 请求 14，`extract_date` |
| 增量保存、局部更新、稳定已确认结果 | 请求 10、13、14 都重新遍历全批 OCR、构造工作簿；未落实持久化字段证据/未决项或隔离已确认字段 | 请求 10、13、14 |
| 以交付物和字段依据核验完成 | 已保存并重开 Excel，但主要检查 sheet、输出行和文件存在；没有核查每个弱回退字段的来源证据 | 请求 14、15、17、18 |

本轮定位为 `agent_did_not_follow` / 字段抽取策略执行失败；没有证据支持把这次
失败归因于网络、iteration 耗尽或官方 verifier 异常，也不能凭单次结果断言该模型
必然无法解决任务。官方总测试会在首次不相等时停止，本轮不从未披露的 oracle
推导总错误字段数，不利用其具体答案修改后续候选。

归档限制：`artifacts/` 仍为空，task container 已不在；本轮保留输入、两类轨迹、
result、CTRF 和 trainer row，但没有导出的真实 `stat_ocr.xlsx`，不能独立做 workbook
verifier replay。轨迹中的工作簿打印不等于原文件归档；不事后重建并冒充原产物。
未因这次验收自动修改 Skill、计费重跑、更新 Gold 为正式通过或推送 GitHub。

## Round 15：强化英文七条的执行与完成条件

用户在 Round 14 结果后明确要求再强化描述并尝试一次。Round 15 保留官方正文、
完整 bundle 和原七条结构；不叠加早期 gate、不注入样本答案、不改变执行器。
重点将已观察到的页级小数推断、行末数字/无验证跨行绑定、月份取余、全批重算
以及仅结构核验后 `finish` 明确为不满足字段证据要求；弱回退即使非空也须局部
复核，最终文件要逐行核对已保存的工作记录。

候选：`round-15/bundle/skills/image-ocr/SKILL.md`；说明：`round-15/repair_notes.md`。
验证：`jpg-ocr-stat-round-15-r001`；GPT-5.2 / OpenRouter；60 iterations；guard 开启；
代理与同 commit 本地 OpenHands 缓存沿用。单次验证结果待记录，不预先提升 Gold。

Round 15 已确认对应 task container 运行，输入快照为英文强化七条版本；复用
任务镜像。确认实际启动后停止监控，等待用户通知结束再验收。

### Round 15 r001 验收

| 指标 | 结果 |
|---|---|
| 正式评分 | reward `0`，`task_passed=false`，官方 `::test_outputs` 0/1 |
| 失败位置 | 逐行内容相等断言 `row_a == row_e`；不展示隐藏期望字段 |
| 执行健康 | `execution_ok=true`；API、Docker、verifier、导出错误字段均无异常 |
| Iterations / provider / tools | 14/60；14 次正常 provider 响应；12 次工具调用 |
| 耗时 / 成本 / token | 1035.7 秒（约 17 分 16 秒）；$1.2085871；519011 total tokens |
| Skill 正文 | 5 个全文 persistent preload 已验证；显式 Skill 工具调用为 0，不代表没有注入正文 |
| Guard | 开启；请求 12 纯文本结束后使用 1 次 continuation；请求 13 重开 Excel，请求 14 真实调用 `finish` |
| 轨迹校验 | validator `healthy=true`，ACP 19 events、LLM 14 exchanges、trainer row 完整 |
| 文件证据 | 22 条数据、3 列、`results` sheet；重开和排序/格式检查成功；没有空日期或金额 |

强化规则确实改变了生成程序，但没有让官方任务通过。与 Round 14 相比：

| 检查点 | Round 14 | Round 15 |
|---|---|---|
| 整页小数标志猜补小数位 | 存在 | 已去掉，金额解析要求 token 中有小数点 |
| 非法月份取余 | 存在 | 已去掉 |
| 字段来源记录 | 候选主要是 priority/index/amount | 新建 `FieldCandidate`，保存 source、line_index、line_text、note，并实际写入 `ocr_evidence.json` |
| 反复全批重算 | 请求 10、13、14 三次全批 | 主程序实际执行一次，但证据 JSON 仍是在全部图片处理完后一次性写入，不是逐图检查点 |
| 疑点触发 | 缺少同字段局部裁决 | 仍把首个非空候选当作确认；没有 crop 或 unresolved 状态，没有弱回退强制复核 |
| 文件内容核验 | 结构/打印核验为主 | 仍主要检查 sheet、行列数、格式、空值、排序和打印，没有逐字段确认接受依据 |

首个关键裁决错误位于请求 5 的 `receipt_ocr_to_xlsx.py`：

- `extract_fields_for_image` 第 341–345 行只在 `best_date/best_total is None` 时选取
  当前 pass 的首候选；第 347–362 行在两者非空时直接写 final 并返回。这里把“找到
  候选”当作“有足够证据确认”，弱回退或冲突不会进入局部复核；也没有保留后续
  更强证据纠错的路径。
- `extract_total_candidates` 第 252–271 行仍用下一行最后一个金额，未证明标签
  与数字属于同一字段；第 275–276 行按关键词和更靠后的行位置排序，而不是先
  完成最终应付字段裁决。
- 第 19–28、52–53、227–228 行仍按 GST/TAX/SST 等字样整行排除。请求 11 仅扫描
  部分可疑标签、显示 `sus_date=0 / sus_total=0`，没有实际做带标签上下文的局部 OCR。
- 请求 4 有一次超长 `file_editor` arguments 不可解析；工具明确拒绝后，请求 5
  重建脚本成功、请求 6 执行成功。该已恢复的模型工具参数错误没有阻断后续交付，
  不能据此把整体评分失败当成基础设施失败。

归因须区分两类证据：非空即接受、弱回退没有局部复核及结构检查替代字段验证，
是本轮可观察的 `agent_did_not_follow`；但 GST 整行排除和下一行末数字策略也来自
官方公开 `task.md` 的 hint（第 70、72–80 行）。它们与本轮修补要求存在冲突，不能
把遵循 task hint 而违反 Skill 的行为全部归为纯模型能力缺陷，也不能仅据这些冲突
声称 verifier 本身错误。没有读取隐藏期望值来计算全部错误字段或构造后续修补。

结论：强化有行为层面的效果，尚无任务成功证据；不将本轮升级为正式 Gold repair。
`artifacts/` 仍为空且任务容器已清理，真实工作簿和证据 JSON 未导出，不能独立
replay；只有原始输入、评分和轨迹证据可复核，不用打印记录重建冒充原产物。
本次验收不修改 candidate、执行器或 task，也不自动计费重跑或推送。

## Round 16：公开 task hint 修正与剩余执行缺口强化

用户在 Round 15 验收后授权修改冲突提示并重跑。本轮从此前实际执行的任务目录
复制完整任务到 `round-16/task-variant/tasks/jpg-ocr-stat`，仅修改副本 `task.md`：
含 GST/TAX/SST 的最终应付字段不再整行自动排除；跨行取值必须证明同字段绑定，
不能直接采用下一行末数字。上游原任务、旧轮次、verifier、oracle、输入图片与
环境均不改。静态目录比较确认任务副本仅 `task.md` 不同。

Skill 仅强化 `image-ocr` 新增七条中的 1、4、5、6、7：显式字段确认状态、
基于抽取证据的实际局部复核、允许更强证据纠正首候选、逐图增量落盘及逐字段
交付核验。已见改善的数字/日期保守解析条款及官方原正文保持不变；完整 bundle
18 个文件中仅 `image-ocr/SKILL.md` 改动，新增描述为英文。

本轮为 `jpg-ocr-stat-round-16-r001`，GPT-5.2 / OpenRouter、reasoning effort `None`、
60 iterations、guard 开启；复用任务镜像、既有代理注入及同 commit 本地 OpenHands。
说明见 `round-16/repair_notes.md`，单次 fresh rollout 结果待验收。

解释边界：task hint 和 Skill 同时修改，是修改任务提示后的诊断实验，不能作为
未修改官方 task 的通过结果，也不能把收益单独归因于 Skill；尚不更新正式 Gold。

已确认 `jpg-ocr-stat-round-16-r001-main-1` 为 Up，复用 `bf__jpg-ocr-stat`；rollout
输入快照的英文 `image-ocr/SKILL.md` 与 Round 16 候选完全一致。确认实际启动后
停止监控，等待用户通知完成再验收，不在此时判断结果。

### Round 16 r001 验收

用户询问是否结束后检查：本轮已于本地时间 2026-10-08 21:53:17 结束，
不再安排 10 分钟后复查。

| 指标 | 结果 |
|---|---|
| 正式评分 | reward `1`，`task_passed=true`，未修改的官方 `::test_outputs` passed，1/1 |
| 执行健康 | `execution_ok=true`；无终态 API、verifier、导出错误 |
| Iterations / provider / tools | 29/60；30 次 provider 请求、29 次成功响应；27 次工具调用完成 |
| 耗时 / 成本 / token | 1440.7 秒（约 24 分 1 秒）；$0.7683466；1406725 total tokens |
| Skill 正文 | 5 个 Skill 全文 preload 已验证；provider Responses 的 `instructions` 中实际包含 Round 16 的确认状态、review queue 和 checkpoint 条款 |
| 显式 Skill 调用 / guard | `n_skill_invocations=0`；guard continuation 使用 1 次，未耗尽 60 次预算 |
| 轨迹校验 | validator `healthy=true`；ACP 33 events、LLM 30 exchanges、trainer row 完整且 training-ready |
| 归档限制 | `artifacts/` 无文件，task container 已不在；保留真实评分和轨迹，但没有原始 Excel 导出，不能独立 replay |

模型做了针对具体收据的定向 OCR/日期候选复核，在最终修正工作簿后重新打开并
检查文件。轨迹也仍包含全批 OCR 后再次全批生成；因此“任务通过”不等于七条
guidance 均完全落实。未从 verifier 读取隐藏期望值来构造后续修补。

验收结论：本轮是健康的修改-task 诊断性通过，不是原始官方 task 的 Skill-only
成功证据。task hint 与 Skill 同时改变，不能分离二者收益；单次通过也不能证明
稳定性。当前记录更新到此，不自动再计费、不改 Gold/report 的原 task 成功分类、
不推送 GitHub；因真实工作簿归档缺口，不删除保留的任务镜像。

## Round 17：强化前的 Skill 与已修正 task 对照

用户要求检查是否是 task 描述冲突导致失败，使用强化前版本重跑已修正的 task。
本轮复用 Round 15 r001 的完整冻结 Skill 输入，18 个文件逐字节一致；不再新增
guidance，也不使用上轮生成代码、数值或 Excel。Task 直接沿用 Round 16 的隔离
副本，未继续改公开 hint、数据、verifier 或环境。

Round 14 同样可能通过，并非因精简而不适用；本轮选 Round 15 是因为它是
Round 16 强化前的直接版本，可与 Round 15 原 task 失败及 Round 16 通过形成
针对性对照。一次通过/失败仍不足以消除随机性或证明某次强化是必要条件。

Rollout：`jpg-ocr-stat-round-17-r001`；GPT-5.2 / OpenRouter；reasoning effort `None`；
60 iterations；guard 开启；执行器、代理注入、pinned 本地 OpenHands 缓存沿用。
本轮仅一次 fresh rollout，结果待验收。说明见 `round-17/repair_notes.md`。

已确认 `jpg-ocr-stat-round-17-r001-main-1` 为 Up；executor 记录的 task digest 与
Round 16 相同，实际输入 Skill 快照与 Round 15 相同。停止监控，用户通知结束后
再验收，不额外计费运行其他 Skill 版本。

### Round 17 r001 验收

本轮已于本地时间 2026-10-08 22:39:11 结束，不是仍在 OCR，也不是极短异常停工。

| 指标 | 结果 |
|---|---|
| 评分 | reward `0`，`task_passed=false`；官方 `::test_outputs` failed，0/1 |
| 执行 | `execution_ok=true`；无终态 API、Docker、verifier 或导出错误 |
| Iterations / provider / tools | 41/60；41 次 provider 请求及成功响应；40 次工具调用均完成 |
| 耗时 / 成本 / token | 1627.0 秒（约 27 分 7 秒）；$0.7504168；1940823 total tokens |
| 轨迹校验 | validator `healthy=true`；ACP 44 events、LLM 41 exchanges、trainer row 完整且 training-ready |
| 对照输入 | task digest 与 Round 16 一致；启动 prompt 中两条修正 hint 实际存在；provider `instructions` 中包含本轮 `image-ocr` 全文 |
| Skill 调用 | `n_skill_invocations=0`；executor 记录 5 个 Skill persistent preload，相关 `image-ocr` 正文注入另有上述 provider 证据 |
| 归档 | `artifacts/` 无文件，容器已不在；没有导出的真实工作簿，不能独立 replay，任务镜像暂不删除 |

轨迹显示模型针对日期做了复核和解析调整，但修改后多次重新执行全批 OCR；
最后三次核验主要是空日期、金额两位小数及 ISO 日期格式。字段非空与格式合法
仍不能替代内容正确性；这些轨迹行为不是具体错误字段的完整定位。

| 对照 | Task hint | Skill | Reward |
|---|---|---|---|
| Round 15 r001 | 原始 | Round 15 | 0 |
| Round 17 r001 | 修正 | Round 15 冻结输入原样复用 | 0 |
| Round 16 r001 | 与 Round 17 相同的修正版本 | Round 16 强化版 | 1 |

这次结果没有支持“只修 task hint 就足以让 Round 15 Skill 通过”；Round 16 的
强化仍可能有贡献，但各条件仅一次样本，不能证明强化是唯一原因或必要条件，
也不能据此否定 task 冲突的影响。记录为修改-task 的有效失败；不自动重跑、
不修改 Skill/执行器、不提升 Gold 或推送 GitHub。

## 2026-10-09：四组冻结补跑与字段级诊断

用户确认复用历史有效运行、并行补跑。所有 Skill 来自历史 rollout 的真实 `inputs/skills` 快照，不再强化或调整；原始 task 复用此前 WSL runtime task，修正 task 复用 Round 16 的独立版本。已直接逐文件核对冻结副本与来源一致，数据和 verifier 不变。

| 组 | Task hint | Skill | 历史有效次数 | 新增有效目标 |
|---|---|---|---:|---:|
| Round 15 | 原始 | Round 15 | 1 | 2 |
| Round 16 | 修正 GST / 跨行取值 | Round 16 | 1 | 2 |
| Round 17 | 与 Round 16 相同 | Round 15 | 1 | 2 |
| Round 18 | 原始 | Round 16 | 0 | 3 |

共新增 9 次有效尝试目标。GPT-5.2 / OpenRouter、未显式设置 reasoning effort、guard=1、60 iterations、同 commit OpenHands 本地安装源和已有 runner/build/task/verifier 代理注入均复用。每个 rollout 独立进程和目录，Docker startup 复用跨进程锁；最多 2 路模型执行并行。普通 FAIL 不改变后续样本数，也不根据中途结果改 Skill。

初次 `jpg-ocr-stat-round-18-r001` 在 Docker Compose 创建网络时遇到 `all predefined address pools have been fully subnetted`，未进入模型请求，reward 未产生，不计为 Skill/模型 FAIL。确认后仅删除了两个无容器引用、属于历史 JPG 实验的旧网络，没有删除镜像、卷或数据。恢复槽位为 `jpg-ocr-stat-round-18-r001-recovery001`；Round 15 r002 未中断。已核验两条对应 task container 均处于运行状态。后台发生新的基础设施或证据导出故障时暂停后续启动，不擅自增加付费次数。

### 不只记录 PASS / FAIL

每个新运行保存真实最终 `artifacts/stat_ocr.xlsx`。runner 每 10 秒只读采样实际写盘的工作簿，内容变化时保存一份，用于事后检查回退；保存模型生成的 OCR/解析 JSON、脚本及文本作为归因证据。采样之外和从未写盘的状态仍不可知。

rollout 结束后，宿主机离线生成 `field_evidence/fields.json` / `fields.csv`，逐项记录 22 张收据的日期和金额，共 44 个字段：filename、字段、实际单元格与值、正确/错误/缺失状态、已观察到的回退及证据引用。采用官方字符串比较规则；filename 对齐的诊断与官方行顺序要求分开，不替代官方 reward。Oracle 字段值不写入诊断表，更不反馈给 agent 或其他补跑。

批次结束后重点核对同组重复出错的字段、错误在收据之间的漂移，以及“正确→错误”前后的 OCR 重跑或解析改动。原因初始为待轨迹核实，不把集合漂移直接证明为随机性，也不把反复错误直接证明为 Skill 缺陷。历史三次缺真实 Excel，不能补造 44 字段对照；保留它们的官方评分与真实轨迹证据，并明确字段分析的可用样本数。

启动脚本、冻结输入、批次状态及方法说明在 `repeat-2x2-20261009/`。当前不升级 Gold，不修改统一执行器源码，不推送 GitHub；确认开跑后停止人工监控，等用户通知再验收。

### 2026-10-09 首两条验收及调度恢复

本次通知后核查发现并非全部九条结束。父调度器接管旧 worker 后读取不存在的
`AdoptedWorker.returncode`，退出并阻止剩余七条启动；Round 18 的模型执行和真实
Excel 导出已完成，但后处理 `wslpath` 未指定稳定 cwd，字段核对未完成。这两项
是本地批次脚本错误，不是模型失败原因。只修调度和离线诊断，没有改统一执行器、
冻结 task/Skill、模型配置或代理，没有重复调用已完成的模型。

| 新运行 | 官方结果 | 有效执行 | provider / tool | 字段正确 | 已观察到回退的字段数 | 耗时 | 成本 |
|---|---|---|---|---:|---:|---:|---:|
| Round 15 r002 | reward=0，0/1 | 是 | 28 / 26 | 38/44 | 3 | 781.7 秒 | $0.8851969 |
| Round 18 r001-recovery001 | reward=0，0/1 | 是 | 23 / 21 | 33/44 | 1 | 1055.2 秒 | $0.69100535 |

两条均有实际 provider 成功响应、完整 ACP/LLM 轨迹及真实最终 Excel；官方唯一
`::test_outputs` 正常执行但失败。实验 validator 均 `healthy=true`，无 provider
终态错误。Round 18 字段分析已从原始归档工作簿在宿主机离线补齐，没有重建 Excel
或重跑模型；恢复的 worker receipt 明确记录 `model_rerun=false`。

- Round 15 最终错误：`034.jpg:date`、`074.jpg:date`、`074.jpg:total_amount`、
  `078.jpg:total_amount`、`090.jpg:date`、`097.jpg:date`。
- Round 18 最终错误：`011.jpg:total_amount`、`034.jpg:total_amount`、
  `039.jpg:total_amount`、`063.jpg:total_amount`、`069.jpg:total_amount`、
  `071.jpg:total_amount`、`074.jpg:total_amount`、`078.jpg:total_amount`、
  `080.jpg:total_amount`、`087.jpg:total_amount`、`094.jpg:total_amount`。
- 两条最终错误交集为 `074.jpg:total_amount`、`078.jpg:total_amount`；它们来自
  不同 Skill 条件，不能作为“同组重复失败”的结论。
- 已保存快照中，Round 15 的 `074.jpg:date`、`090.jpg:date`、`097.jpg:date`，
  Round 18 的 `087.jpg:total_amount` 出现正确后变错。此处确认的是实际写盘的回退，
  OCR 重跑、解析修改还是其他覆盖导致，暂标为待轨迹核实，不推测填因。

调度修补的三项针对性测试通过：路径转换固定 cwd、恢复保持原试验编号，以及
接管已结束 worker 不依赖 `returncode` 属性。剩余七个槽位继续原已授权的冻结队列，
两路并行；已完成两条保留，不额外付费重跑。当前样本不齐，不能比较四组稳定通过率。

### 主机中断后从批次检查点恢复

用户报告主机内存耗尽，并补充当时同时运行游戏；确认仍采用两路并行。
WSL 的父进程和两个 worker 均已退出。中断前已完成的 Round 15 r002、
Round 17 r002、Round 18 r001-recovery001 不重跑。

Round 16 r002 的原始 `result.json`、完整 ACP/LLM、verifier reward=0 和真实 Excel
已在 21:04 前后落盘，模型有 31 次成功响应，没有终态错误；仅派生 `results.jsonl`
和 API 返回记录未完成。复用现有 exporter 和 BenchmarkResult normalization 离线
补齐，随后 validator `healthy=true`，44 字段诊断也已补齐。此轮保留为正式有效失败，
不重新调用模型或 verifier；`postprocessing_recovery.json` 单独记录恢复来源。

Round 18 r002 未完成模型/评分，保留原轨迹、两份采样 Excel 和停止容器中导出的
`field_evidence/interrupted_workspace/stat_ocr.xlsx`，该文件不是正式最终交付物。
Docker 状态为 exit=255、OOMKilled=false，因此记录为“用户报告的主机内存中断”，
不声称已证实容器自身 OOM。此尝试标为 void，不计模型/Skill FAIL。已导出证据后仅
删除该停止容器及无引用的该实验网络，任务镜像和卷未删除。

恢复槽位使用 `jpg-ocr-stat-round-18-r002-recovery001`，从原冻结输入开启 fresh
rollout，不把中断时的工作簿、OCR 缓存或 agent 历史注入新尝试。这里恢复的是批次
检查点，而非继续旧模型会话。四条有效结果保留，剩余五个有效槽位继续；Skill、
task、模型、guard、60 iterations 和代理/同 commit 本地 OpenHands 均不变。

## 2026-10-10：Round19 流程模板，修正 Task 下三次冻结验证

四组重复结果显示同一配置仍存在未交付、字段裁决错误和正确字段回退。
用户确认新一轮在官方 Skill 基础上增补流程模板，不重写官方正文；使用此前
修正 GST／跨行提示的 Task 跑 3 次，将本任务的调用上限改为 65，随后补充最多
3 条并行。该批是流程模板与 65 轮上限的联合变更，不能把相对旧批的全部变化
单独归因于 Skill。

Round19 复制完整官方五-Skill bundle，仅在 `image-ocr/SKILL.md` 末尾增补英文
`Structured Receipt Workflow Template`。原文、结构和其他 Skill 文件保留，
不叠加 Round15/16 的累计人工指导。模板规定字段记录状态、逐图检查点、非空
弱候选复核队列、局部复核、增量更新和实际工作簿核验，提供结构与流程伪代码，
不包含收据编号、答案或完整任务解题脚本。

- 冻结输入及调度：`repeat-template-20261010/`。
- 运行编号：`jpg-ocr-stat-round-19-r001`、`r002`、`r003`，均 fresh rollout。
- GPT-5.2 / OpenRouter，reasoning effort 未显式设置，guard=1；任务数据和
  verifier 不修改，复用既有代理与同 commit OpenHands 本地 runtime archive。
- 65 轮只在独立 worker 进程内生效；统一执行器源码、其他任务默认值及旧批不改。
- 最多 3 路；同时检查 Windows 与 WSL 可用内存，资源不足则排队。普通有效
  FAIL 不追加重跑；基础设施或归档故障暂停后续启动，等待处理。
- 继续导出真实 Excel、工作文件与保存快照，结束后离线记录 44 字段及回退，
  不向模型反馈 oracle。

已核验 `jpg-ocr-stat-round-19-r001-main-1` 实际处于运行状态；其余槽位由后台
按内存和并发上限调度。按用户要求，确认启动后停止人工监控，不新增定时检查，
等待用户告知完成后统一验收；当前不升级 Gold，不推送 GitHub。

## 2026-10-10：Round20 三处流程模板修补，三次冻结验证

Round19 三次均未正式通过：前两次已交付工作簿，仍存在字段裁决错误和已正确
字段回退；第三次的长 OCR 命令没有进度输出，连续相同空等待触发 OpenHands
stuck 判定，没有交付最终 Excel。第三次不能按“44 字段全部识别错误”处理，也
没有证据证明只要不中断就能通过。

用户确认按推荐修补三处，在 Round19 追加模板基础上新开 Round20；官方 Skill
原文和其余 bundle 文件不重写。`image-ocr/SKILL.md` 的英文模板补充：

1. 最终应付额结合税费、折扣、舍入调整及标签关系裁决，关键词不能单独确认。
2. 实际字段 ledger／review queue、非空弱候选复核、同字段证据纠错和恢复时
   的已确认字段保护，消除初始循环无条件覆盖旧结果的路径。
3. 长 OCR 的逐 pass／逐图进度、逐图检查点及较长工具等待，避免连续空等待。

冻结目录：`repeat-template-round20-20261010/`；候选：`round-20/bundle/skills/`。
运行编号为 `jpg-ocr-stat-round-20-r001`、`r002`、`r003`，均为新的完整 rollout。
沿用同一修正 Task、GPT-5.2／OpenRouter、reasoning effort 未显式设置、guard=1、
65 轮、既有代理与同 commit 本地 OpenHands archive。最多 3 路，内存不足排队。
65 轮仍仅在独立 worker 中生效；不修改共享执行器、旧批或 verifier。

复用 Round19 调度和真实产物归档，结束后离线核查 44 字段及快照回退，不向模型
泄露 oracle。普通有效 FAIL 不重跑；基础设施／归档失败暂停等待处理。按用户
要求，只确认实际启动后停止人工检查，不新增监控，不推送或提前升级 Gold。

20:44（Asia/Shanghai）已核验 `jpg-ocr-stat-round-20-r001-main-1` 实际运行；
后台 runner 和 r001／r002 worker 已启动，r003 当时仍按资源门槛排队。
冻结检查确认修正 Task 与原来源一致、官方 Skill 正文保留、其余文件未改。
至此停止人工检查，等待用户通知完成后验收。
