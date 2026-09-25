# 人工诊断与 Skill 修复标注：`fix-build-agentops`

## 1. 当前状态

| 字段 | 内容 |
|---|---|
| 状态 | `Round 1 有效 FAIL；Round 2 r003 verified-fix PASS（faithful verifier-only replay），已纳入 Ground Truth` |
| Original rollout | `fix-build-agentops-original-skill-v11x-20260903-r001` |
| Original结果 | reward 0；官方子测试 2/3；60/60 iterations |
| Skill暴露 | persistent full-body exposure 已验证 |

## 2. 修复前证据

模型成功生成了失败说明和标准 diff 文件，但官方 build 仍失败。轨迹中最重要的过程证据是：一次局部测试已经达到 `9 passed, 1 failed`，随后模型继续修改全局 session 初始化逻辑，测试回退为 `5 passed, 5 failed`，却没有恢复到此前较优状态。模型还多次手工计算 unified diff 的 hunk 行数，造成 `corrupt patch`，耗费了大量轮次。

官方 verifier 中另有 Python 3.7、3.8、3.9 解释器不可用的环境信号。该信号必须与 Python 3.11 下可复现的代码测试失败分开记录，不能把全部失败简单归因于 Skill，也不能通过掩盖测试来取得通过。

## 3. Repair items

| Repair ID | Tag | Skill与位置 | Gold repair requirement | 状态 |
|---|---|---|---|---|
| RI-001 | `skill_missing_guidance` | `analyze-ci/SKILL.md` → `Local or Reproduced CI Failures` | 先忠实复现提供的CI；区分基础设施和代码错误；每次修改比较失败集合；用版本控制生成并校验diff；只有产物存在且权威构建已运行后才能结束 | `Round 1 未通过；Round 2 继续强化` |
| RI-002 | `skill_missing_guidance` | `testing-python/SKILL.md` → `Regression Gate for Stateful SDK Repairs` | 对singleton/session类SDK同时做单测、模块测试和完整套件；检查跨测试共享状态；出现新增失败时恢复上一个更优状态 | `Round 1 未通过；Round 2 继续强化` |

## 4. Round 1 验证计划（已执行）

- 候选 bundle：`round-1/bundle/skills/`
- Fresh rollout：`fix-build-agentops-round-1-r001`
- 配置：GPT-5.2、OpenHands、60 parent iterations、completion guard开启（最多一次 text-only continuation）。
- 只有基础设施、provider、OpenHands/工具链与 verifier 均完整正常，且官方 verifier 全部通过，才升级为 `agent-validated`。
- 如果仍失败，将根据新轨迹区分剩余 Skill 缺陷、模型执行问题和 verifier 环境问题，不把本轮直接写成已验证 Gold repair。

## 5. Round 1 fresh rollout 结果与 Round 2 追加修复

- `r001`：基础设施错误，Docker Hub 不可达；不计 PASS/FAIL。
- `r002`：基础设施错误，cached OpenHands runtime Python 版本不匹配；不计 PASS/FAIL。
- `r003`：首次有效 Round 1 development rollout。原始 verifier 在 `test_build_success` 处 240 秒超时；随后 verifier-only 重跑完整结束，`test_note_exists` 与 `test_diff_exists` 通过，`test_build_success` 失败，reward=0，因此 Round 1 判定为有效 FAIL。
- 回查 BugSwarm 捕获的原始 failed CI 后确认：真正基线为 Python 3.10/3.11 均 `9 passed, 1 failed`，唯一失败为 `tests/test_events.py::TestEvents::test_record_timestamp`。r003 没有先以该捕获日志为最高优先级证据，而是把新构造 editable-install 环境中的 packaging 问题误当 root cause。
- r003 后续修改 `singleton()` 构造语义，新增 `Client._tags_for_future_session` 的 `AttributeError`，属于候选补丁制造的新 regression，而非原始任务失败。

Round 2 新增：

| Repair ID | Tag | Skill与位置 | Gold repair requirement |
|---|---|---|---|
| RI-003 | `skill_ambiguous_guidance` | `analyze-ci/SKILL.md` → `Local or Reproduced CI Failures / Evidence hierarchy` | 明确捕获的原始 CI/reproducer 日志高于新构造本地环境；已有代码级 CI failure 时，不得用 lower-ranked installer failure 替换 root cause；修改 packaging/tox/workflow 前必须有权威证据 |
| RI-004 | `skill_ambiguous_guidance` + `skill_missing_guidance` | `testing-python/SKILL.md` → `Regression Gate for Stateful SDK Repairs` | 明确 test-order dependence 不等于 singleton/reset 语义错误；先从 failing assertion 的 owning object/state transition 定位；全局生命周期修改出现新 failure node/exception class 必须立即回滚 |

Round 2 从 Round 1 bundle 继承未修改 Skill，仅覆盖 `analyze-ci` 和 `testing-python`，保持四 Skill 暴露条件一致。

## 6. Round 2 r003 最终验证与 Gold 判定

- `r001`：OpenRouter credit 额度不足导致 provider 402，属于基础设施/provider 无效轮。
- `r002`：尝试限制输出 token 后仍由上游请求 65536，继续触发 provider 402，属于无效轮；随后恢复原始 GPT-5.2/OpenRouter 配置。
- `r003`：Agent 正常运行至 54/60 parent iterations、52 tool calls，completion guard 实际续跑 1 次后正常 `end_turn`。四份 Skill 正文通过 persistent AgentContext 完整预载，expected/observed bundle digest 均为 `sha256:186c22e3c9b98cd96e92ee226856ad82e28acf7cb5c2d4c5a08fa3a748440d24`。
- r003 原始 executor verifier 安装了当时最新的 `tox 4.61.4`。`py310`、`py311`、`py312` 均为 `10 passed`，但环境没有 `py37/py38/py39`，新版 tox 将三项计为 `FAIL`，导致 `test_build_success` 失败、raw reward=0。
- 回查原始 BugSwarm passing job `24653510459-orig.log` 后确认：2024 年实际安装的是 `tox 4.15.0`，同样缺失的 `py37/py38/py39` 被计为 `SKIP`；原始 passing summary 为 `py37/38/39 SKIP, py310 OK, py311 OK, py312 SKIP`。
- faithful verifier-only replay 使用干净 `bf__fix-build-agentops:latest`，重新应用 r003 的 `patch_1.diff`、`patch_2.diff`、`patch_3.diff` 与同一 `failed_reasons.txt`，不重跑 Agent、不改变候选代码；仅把 verifier runtime 固定为历史实际版本 `tox==4.15.0`。官方 verifier 最终 `test_note_exists`、`test_diff_exists`、`test_build_success` **3/3 全部通过**，`reward=1`，耗时 269.10 秒。

因此本任务按“基础设施/verifier 漂移修复后重跑”的统一有效性规则记为 **Verified Fix PASS**。原 raw `reward=0` 不覆盖，作为 verifier dependency drift 的历史 provenance 保留。

### 最终 Gold defect 合并规则

Round 1 的 RI-001 与 Round 2 的 RI-003 是同一个 `analyze-ci` 原始缺陷的递进强化；Round 1 的 RI-002 与 Round 2 的 RI-004 是同一个 `testing-python` 原始缺陷的递进强化。为避免把 repair iteration 重复当成独立 defect，最终 `gold_repairs.json` 只保留两项：

1. **RI-001 / `skill_missing_guidance`**：本地 failed-repo 场景缺少 captured-CI-first 的权威证据层级、infra/code 分离、last-known-good rollback 与 authoritative completion gate。
2. **RI-002 / `skill_missing_guidance`**：stateful SDK 场景缺少“顺序依赖不等于 singleton repair target”的定位规则、owning-object/state-transition 优先级和 global lifecycle regression rollback gate。

两项只获得完整 Round 2 bundle 的联合 PASS，没有逐项消融。并且 r003 Agent 仍未严格执行 RI-001 的 captured-log-first 要求，也通过 singleton `__init__` re-entry 处理状态而非最小 event-field transition，因此 **Verified Fix Rate 的 PASS 不等于 Diagnosis/Repair-Adherence 满分**。这两类指标应继续分开报告。

