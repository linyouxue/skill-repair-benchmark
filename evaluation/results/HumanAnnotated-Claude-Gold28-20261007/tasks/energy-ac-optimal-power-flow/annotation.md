# Claude 人工标注：energy-ac-optimal-power-flow

## 当前状态

2026-10-06T20:03:09.531363+08:00 Round2已独立有效PASS：原checker23PASS/1skip、reward1，11/60正常end_turn、11provider全200，9工具/0显式Skill、3主Skill首请求精确预载、17完整ACP，错误null。真实四文件预导出与停止main一致，已入04增量及Claude兼容Gold；新增3/14、总18/29。原归因/原产物缺口/skip与质量限制保留，禁止重跑。

原Opus有效未通过：energy-ac-optimal-power-flow-opus47-original-skill-r001；reward=0.0，end_turn。证据目录：/mnt/c/Users/linyuanjing/Desktop/skill论文/SkillGen-benchmarking/expanded_original_skill_runs/opus47-openrouter-v1.1-20260919/runs/opus47-original-skill/energy-ac-optimal-power-flow-opus47-original-skill-r001。

GPT未改Skill成功只作范围证据，不继承其归因或产物。原始诊断与最小候选见下文；本题Round1正常结束但有效FAIL，provider14/评分0/费用未知null。


## 原始功能步骤与RI-001

| 步骤 | 输入→输出 | 原轨迹 |
|---|---|---|
| S1 契约及数据读取 | math-model/network→映射/单位/在运元件 | ACP3–7 |
| S2 ACOPF建模求解 | 支路pi、shunts及bounds→可行调度/电压 | ACP13/14 |
| S3 汇总导出 | 解的物理量→report总量 | ACP13源payload349–352 |
| S4 独立验收 | report/schema/守恒→结论 | ACP16–18及原checker |

ACP13已正确将Gs*Vm²纳入P节点平衡，却在汇总明确写“Losses=gen-load-shunt”，再用total_losses字段输出支路耗散边界。原checker实际425.117299减423.878529=1.23877MW；ACP16仅检查结构及打印summary，未将总量守恒核对，17/18宣称正确。原checker22项PASS，缺current limit列skip1项，唯一loss consistency失败正常。原模型/Skill已有shunt方程，不应记作物理方程缺失；归因agent_semantic_misinterpretation，另记总损耗report边界未明确及premature completion。没有原report/source导出或保留容器，因此没有在原最优电压上独立复算shunt精确值，trace payload不冒充真实源文件。

RI-001只在ac-branch-pi-model原Aggregate bus injections下两条节点平衡式后补一个紧凑paragraph：统一单位后，总active losses=发电-指定bus demand=支路耗散+实际电压的active shunt耗能；导出前核对该求和恒等式，支路损耗单独不包括shunt。来自题面公开math-model方程求和，原physics指导保留，不改casadi/data Skill、task/verifier/目标值/隐藏阈值，无步骤/helper/数值答案。源与候选只差一处，其他3文件不变，反向删除恢复原版。独立fresh Opus4.7采用60parent/32768/no effort/text-only≤1共享预算；真实预verifier导出report及公开inputs、可选solve_acopf.py，保留停止main。差异与免费预检见round-1/from-original.diff、repair-plan.json及preflight。


## Round1 启动确认：2026-10-06T19:07:42.347693+08:00

免费预检task/input/runtime、依赖端点、55既有Docker网络及主机路由不重叠通过。启动线C可用12543942656字节高于5GB。runner26369实际run_round1.py，所属compose/build或main真实活动已确认，当前runtime_setup；startup锁free/题锁held，独立10.253.227.0/24。证据round-1-r001-start-confirmation.json；每题唯一活动，启动后结束本次监控，下次从真实result/日志/轨迹/PID/容器/compose/buildx/锁接续，不重复启动。provider/评分/费用未知null；不入Gold，原证据缺口及归因保留。


## Round1 有效FAIL验收：2026-10-06T19:30:18.688502+08:00

14/60正常end_turn、14provider全200，12工具/0显式Skill、3主Skill首请求精确预载、21完整ACP，Agent/verifier/export错误null。原checker22PASS/1FAIL/1skip，唯一total-loss一致性仍失败。首错ACP15真实solve_opf.py294–296把gen-load-shunt存入总损耗，327导出；18仅结构打印，19/20错误接受。Round1新增报告边界指导已全文暴露但未执行，不倒推原物理指导缺失/修改造成回退/唯一因果。正常断言不是infra/预算，不能补验消除FAIL，不入Gold。

真实report53262字节SHA143f4b76bdeeb637e6edb6ac72cfed8b2793bf08ee32577edfd9dc6f2a317d9f，与pre-verifier archive21776字节SHAadbd03147dca8abee2feaf9a57a2857b1b096551c7f5bbaae84b2081fb8fe2ac及停止main一致，输入两文件也一致。source实际名solve_opf.py，不在原可选solve_acopf.py预归档范围；从停止main真实恢复12868字节SHA5970598ec279bc90c18b0da8391418196fb59cf235a17655705f520f3c36f608，匹配ACP15 create payload，明确恢复发生在verifier后，不冒充预导出source。独立用真实导出舍入电压复算active shunt1.238769712MW，与总量差1.240000000MW在舍入精度内一致。无模型调用的物理核对仅诊断，未修改真实报告/评分。详细round-1-r001-fail-audit.json及round-1-r001-audit/solve_opf.py；原产物缺口仍保留。


## Round2 最小独立方案：2026-10-06T19:31:32.173588+08:00

依Round1实际未遵循证据，从冻结原版重建，只替换同一位置新增paragraph。直接绑定“报告load统计指定bus demand”时的总损耗边界：gen减该demand，含active shunt；直接核对导出totals，branch-only另列。删除Round1泛化文字，原结构不变，只1处+263字节，较Round1-46字节，其他3文件逐字节不变；无新步骤/helper/数值/阈值/题目或checker改动，不称保证通过。runner仅独立ID、输出及task-local网络10.253.228.0/24，并把Round1实际solver名solve_opf.py加入可选真实预归档范围；不影响Agent输入/模型/预算。免费预检后再付费启动，prepared时尚无新模型调用。


## Round2 启动确认：2026-10-06T19:32:43.984520+08:00

免费task/input/runtime及依赖端点预检通过，57既有Docker网络与主机路由均不重叠，task-local10.253.228.0/24。启动Cfree10257960960字节>5GB；runner32920实际run_round2.py，maine94853b11024归属同project/service main，真实running10.253.228.2，runtime_setup，startup锁free/题锁held。确认后结束本次监控，下次先查真实result/日志/最近轨迹/PID/容器/compose/buildx/锁，不重复启动。provider/评分/费用未知null；与Round1独立预算、进程、输出及网络。


## Round2 有效PASS与Gold：2026-10-06T20:03:09.531363+08:00

实际solve_acopf.py在ACP11/源302–303将total_losses设为gen减specified demand，含active shunt，不再减去该项；原节点shunt方程保留。ACP14打印gen-minus-load、shunt及branch-only分量，15/16实际采用正确总量，原checker独立23项通过、0失败、1项因公开input缺current limits跳过。11provider全200、无续跑、Agent/verifier/export错误null。真实report53785字节SHAe9fca062ac4cc5166838f048d10490c950fd8a5064849d2f0b27eebcd79e0f55，solve_acopf.py12400字节SHA4cb99c0d50b3bdb587998a84c4f01fdc0a0563afd0b2b412d2d3054da335cfef，与预归档/停止main逐字节一致；公开network/math-model也一致，源匹配ACP11 create payload，不是重建。archive25930字节SHAf81e0c0935ed0a7f7bccb3560c7f07ce2d928935338acfffc46998f14309973b。

正常停止maine94853b11024保留，137/OOMKilledfalse不单独诊断OOM；runner已结束、startup/题锁free。原tag/原physics指导存在/原缺口保持，Round1未遵循另记。两个IPOPT起点和成本checker不证明全局最优，模型“global”结论过强；文字列3条满载支路而实际report4条，后者原checker通过。ACP14仅打印而非assert，未另存verifier源码snapshot，不声称三方源SHA一致。一次fresh PASS不证明修改必要性或唯一因果。详见round-2-r001-pass-audit.json；立即入04及Claude兼容Gold18项一一对应，01/02/03不变。
