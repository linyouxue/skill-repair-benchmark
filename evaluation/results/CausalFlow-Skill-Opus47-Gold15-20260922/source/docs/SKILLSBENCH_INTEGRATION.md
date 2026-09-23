# SkillsBench 接入：文件资源图与局部重放

> 更新时间：2026-08-12  
> 当前状态：正式任务端到端、Docker 完整/局部重放、OpenRouter 局部修复及失败日志消融已通过。

> 这份文档记录早期集成过程。当前任务级结论见 [`SUBSET25_RESULTS.md`](../current/SUBSET25_RESULTS.md)，最新人工缺陷结果见 [`DEFECTIVE_SKILL_REPORT.md`](../current/DEFECTIVE_SKILL_REPORT.md)。

## 1. 已经接通什么

现在可以把一条真实 SkillsBench 运行转换成版本化文件资源图：

```text
输入文件版本 → 读取命令 → 输出文件版本 → 下游命令 → verifier
```

图不会默认添加“上一条命令 → 下一条命令”的顺序边。不同文件分支可以保持独立；证据不足的边保留为 `may/inferred`，运行时确认的文件读写升级为 `must/observed`。

| 组件 | 用途 |
| --- | --- |
| `skillsbench_replay/atif.py` | 读取 ATIF、result、reward，并恢复命令及读写观测。 |
| `skillsbench_replay/shell_io.py` | 保守推断 shell 文件访问；heredoc 源码不再误解析为 shell 参数。 |
| `skillsbench_replay/graph.py` | 构建版本化文件图，不生成全局顺序链。 |
| `skillsbench_replay/planner.py` | 从变化资源求后代命令切片。 |
| `skillsbench_replay/semantic.py` | 添加稀疏的“技能→模型决策→命令”软依赖，并区分模型推断与干预证据。 |
| `skillsbench_replay/openrouter_acp_agent.py` | 轻量 Python ACP 代理；把部署的技能正文加入模型上下文，并记录技能启用、每条命令、文件写差分和 Python `open()` 读取。 |
| `repro_wrappers/run_skillsbench_openrouter_task.py` | 用 OpenRouter 运行正式 SkillsBench 任务；需要代理时只制作运行副本，不改变题意、技能、测试或判分规则。 |
| `repro_wrappers/run_skillsbench_openrouter_smoke.py` | 运行低依赖 hello-world 诊断任务。 |
| `repro_wrappers/run_skillsbench_causalflow_repair.py` | 选择一个失败命令，生成替代命令，以图切片在干净容器中最小重放并调用官方程序判分。 |
| `repro_wrappers/archive/summarize_skillsbench_causalflow_comparison.py` | 汇总原始失败、普通重跑与局部修复，并识别网络和判分依赖故障。该脚本已经归档。 |

运行测试与分析：

```bash
python -m unittest discover -s tests -v

../skillsbench/.venv/bin/python \
  repro_wrappers/run_skillsbench_openrouter_task.py \
  llm-prefix-cache-replay --with-task-skills \
  --model openai/gpt-5.2-codex --jobs-label <new-label>

python -m skillsbench_replay \
  --run-dir ../skillsbench/jobs/<job>/<task-run> \
  --task-dir ../skillsbench/tasks/<task> \
  --output repro_wrappers/results/<name>.json
```

API 密钥只通过内存中的 BenchFlow 配置注入 Docker，不进入命令行和持久化 config。

正式运行器还会处理两类常见网络环境差异：

- `--docker-build-mode auto` 在简单任务缺少 BuildKit 前端镜像时使用本地旧构建器，避免为已经缓存的基础镜像再次访问 Docker Hub；
- `--verifier-proxy auto` 在宿主机配置了代理时，只给 `jobs/causalflow_prepared/` 下的任务副本增加 `verifier.env` 代理模板。原始任务、测试、技能和 Dockerfile 不修改，代理值也不会写入副本。

每次完成的正式 rollout 会自动生成 `causalflow_analysis.json`，包含命令事件、版本化文件资源图、verifier 依赖和局部切片。可用 `--docker-build-mode buildkit` 或 `--verifier-proxy off` 关闭兼容行为，以检查原始环境配置。

## 2. 实验结果

| 实验 | 结果 | 能说明什么 |
| --- | --- | --- |
| 三命令双分支确定性 smoke | full 3 条、selective 2 条；最终文件和 verifier 一致；命令减少 33.3% | 非顺序链切片逻辑正确。 |
| 真实 hello-world ACP | reward=1；2 条命令；写 `hello.txt` 为 observed/must | 真实命令恢复、写入观测和 verifier 接线已通。 |
| 正式 `llm-prefix-cache-replay`，no-skill，`gpt-4o-mini` | reward=0；10 项测试通过 2 项 | 模型把 S3FIFO 简化为近似 LRU，并误用任意块命中；这是解题失败，不是接入失败。 |
| 同一正式任务，with-skill，`gpt-5.2-codex` | **reward=1；10/10 测试通过** | 原版任务、skill、代理、Docker、轨迹、verifier 已端到端接通。 |
| 上一项加 Python 运行时读取审计 | reward 仍为 **1**；6 条命令，6 条 observed/must 边 | 插桩未改变结果，并补到了脚本内部的真实文件读取。 |
| 修改正式任务 `config.json` 的 Docker 重放 | full 6 条、selective 2 条；7/7 配对输出和 verifier 一致 | 首个正式任务局部重放对照通过。 |
| hard `tictoc-unnecessary-abort-detection` | 格式测试 3/3；隐藏策略 reward=0.45；13 条命令、9 条 observed/must 边 | 接入跨到第二类任务；模型策略错误，不能计为成功。 |
| TicToc 技能消融 | 原装 0.45、1.00；协议单改 1.00、1.00；轨迹单改 0.35；联合 1.00 | 单一协议 Skill 修改可解决，否定该案例的“必须联合修复”假设。 |
| TicToc 双模型语义边 | 两模型一致连接“轨迹 Skill→第 12 步决策”，对协议 Skill 判断不一致；消融又为协议边提供初步干预证据 | 语义边必须由真实干预校准，不能只靠模型判断。 |
| `azure-bgp-oscillation-route-leak`，`gpt-4o-mini` | 官方 22 项检查通过 13 项；任务完整结束，无环境错误 | 较弱模型在振荡、泄漏检测和方案分类上出现多处推理错误。 |
| 同一 Azure BGP 任务，`gpt-5.2-codex` | 官方 22 项检查通过 **21 项**；只错 1 个 RPKI 方案；任务完整结束，无环境错误 | 该任务能够区分模型推理质量，并提供足够细的修复信号。 |
| Azure BGP 双模型语义定位 | 两模型都定位到第 6 步“生成分析程序”，平均置信度 0.84；技能到 verifier 的结构路径接通 | 下一项工程缺口是保存模型检查点并重新生成受技能影响的决策。 |
| 三任务失败后局部修复，隐藏失败日志 | Azure 0→0、TicToc 0.45→1.00、Civ6 0→0.70；局部只执行 2、2、1 条命令 | 两项改善不依赖判分提示；Civ6 实测跳过 23/24 条历史命令。 |
| 同三任务，允许失败日志 | Azure 0→1.00、TicToc 0.45→0.85、Civ6 0→0.70 | 失败反馈能明显抬高 Azure 结果，正式评测必须分开报告信息条件。 |
| 同三任务普通完整重跑 | Azure 0、TicToc 1.00、Civ6 0 | 普通重跑是必要对照；TicToc 的二次成功不能全归因于局部修复。 |

TicToc 的事后 scorer 诊断很明确：模型仅按 `commit_ts < current_wts` 选择全部软中止，漏掉了 `(local_wts, commit_ts]` 时间窗内 `ats_at_write < ats_at_abort` 的必要写冲突。这给后续局部修复提供了具体目标。

正式成功结果：

| 指标 | 数值 |
| --- | ---: |
| 请求数 | 2,000 |
| prompt token | 27,441,774 |
| hit token | 2,394,659 |
| 命中率 | 8.726327% |
| 最终驻留块 | 2,535 |

分析文件：`repro_wrappers/results/skillsbench_llm_prefix_cache_audited_success_analysis.json`。

## 3. 真实成功图告诉了什么

成功轨迹有 6 条命令。核心文件路径如下：

```text
compute_report.py(v1) ─┐
config.json(v0) ───────┼→ step 5: python compute_report.py
trace.jsonl(v0) ───────┘             │
                                     ▼
                               report.json(v1)
                                     │
                         ┌───────────┴───────────┐
                         ▼                       ▼
                    step 6 检查             SkillsBench verifier
```

`step 5` 对 `compute_report.py`、`config.json`、`trace.jsonl` 的读取，以及对 `report.json` 的写入，均由运行时观测支持，不再只靠命令字符串猜测。

当前图切片给出：

| 变化资源 | 选择命令 | 图上命令减少 | 能到 verifier |
| --- | --- | ---: | --- |
| `config.json` | step 5、6 | 66.7% | 是 |
| `trace.jsonl` | step 5、6 | 66.7% | 是 |
| `prefix-cache-replay/SKILL.md` | step 3 | 83.3% | **否** |

对 `config.json` 的实测干预把容量从 4096 改为 2048。完整 6 条与局部 step 5、6 在 7 次 Docker 配对中均通过动态 oracle，最终 4 个文件的 SHA-256 完全一致。命令减少 **66.7%**；完整重放中位数 0.3108 秒，局部重放 0.3048 秒，墙钟只减少 **2.0%**。原因是被跳过的 4 条命令只是 `ls/cat/写入同一脚本`，主要计算和 verifier 都在不可跳过的 step 5、6。这个结果说明“切掉很多节点”不等于“明显加速”，后续必须按耗时/token 加权选实验。

结果文件：`repro_wrappers/results/skillsbench_llm_prefix_cache_docker_replay.json`。这是对正式任务的研究性输入干预，不是 SkillsBench 官方分数。

skill 变化则暴露了当前最重要的研究缺口：skill 文本通过 LLM 上下文影响后续源码生成，这不是普通文件读写边。若 skill 改变，当前系统必须回退到包含代码生成的更宽重放，不能直接采用 step 3 的切片。

这也明确了方法创新点：需要建立稀疏的“skill/观察 → 模型决策 → 生成命令 → artifact”语义边，而不是退回把全部步骤串成一条长链。2026-08-10 的原型已加入显式决策节点：TicToc 的两个技能结构切片均落到第 12 步决策，随后连接输出文件和 verifier。

但技能变化不能复用第 12 步的旧命令，必须重新调用模型生成命令。当前命令重放器不具备模型状态恢复能力，因此会标记 `fallback_required`；只有结构切片支持 3/13 条命令（理论减少 76.9%），尚不能把它报告成实际加速。

## 4. 已确认的限制和处理

1. BenchFlow 0.6.3 会把 ACP 工具 `arguments` 导出为空对象；命令暂从 `extra.title` 恢复，并明确标记为 `title_fallback`，不冒充结构化证据。
2. shell 文本推断统一是 `may/inferred`；工作区 SHA-256 差分确认写入，Python audit hook 确认脚本内部读取，二者才是 `must/observed`。
3. 绝对路径、删除、安装、网络、heredoc 等不会在宿主机重放。正式重放必须在 Docker 内进行。
4. `dialogue-parser` 原版环境构建失败的直接原因是 Debian HTTP 源超时；已通过可见日志定位，不属于代理或建图错误。无 apt 构建依赖的正式缓存任务已成功运行。
5. `skillsbench/` 的 tracked 文件未修改；运行产物只在其被忽略的 `jobs/` 下。
6. 如果变化资源的图后代到不了 verifier，调度器会标记 `fallback_required` 并选择完整重放；skill 变化已有回归测试。
7. OpenRouter 瞬时 429/5xx、异常空响应、`IncompleteRead`、远端断连和 SSL 中断现会退避重试；判分容器的 502/依赖下载失败会单独标记，不计为模型失败。
8. 修复模型使用目标步骤之前的轨迹文字获取语义结论。当前图可靠缩小了执行范围，但尚未把全部推理结论表示为显式依赖节点。

## 5. 下一步

1. 保存每个工具调用前的模型上下文，实现从最早受影响决策点恢复并重新生成命令。
2. 对双模型语义边做重复技能干预，用输出变化和评分变化校准，避免重新引入全局顺序链。
3. 选择下游存在昂贵但无关分支的任务；当前缓存任务虽然命令减少 66.7%，但墙钟只减少 2.0%。
4. 重跑 `dialogue-parser`；若 Debian 源仍不稳定，记录为基础设施排除项，不改任务内容冒充正式分数。
5. 再选一个文档或表格任务，验证 Python audit 之外的进程级文件读取方案。

正式报告必须同时给出 full/selective verifier 一致率、输出状态一致率、fallback 率、命令/token/时间缩减；只报告图更稀疏或预测命令更少不够。
