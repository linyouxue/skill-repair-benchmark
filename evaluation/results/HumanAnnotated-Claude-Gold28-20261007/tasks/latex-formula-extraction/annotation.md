# Claude 人工标注：latex-formula-extraction

## 当前状态

2026-10-06 已纳入新增14题，待诊断。用户已确认沿用自主修复、必要付费fresh及每30分钟检查。

原Opus有效未通过：latex-formula-extraction-opus47-original-skill-r001；reward=0.0，end_turn。证据目录：/mnt/c/Users/linyuanjing/Desktop/skill论文/SkillGen-benchmarking/expanded_original_skill_runs/opus47-openrouter-v1.1-20260919/runs/opus47-original-skill/latex-formula-extraction-opus47-original-skill-r001。

GPT未改Skill成功只作范围证据，不继承其归因或产物。首错、步骤、标签、最小修复与执行遵循待核查。尚未启动模型；费用未知null。


## 2026-10-07T00:34:19.992611+08:00 原轮诊断与 Round1 最小候选（未启动）

原轮有效FAIL：5PASS/2FAIL、reward0，24/60正常end_turn，24provider全200，22工具/1显式Skill、29完整ACP；marker首请求全文精确暴露；pdf全文除日志将公开qpdf示例password脱敏外精确，不能宣称未经脱敏wire逐字节证明，执行/验证/导出错误null。ACP21–23看过原PDF，首错ACP24将来源括号异常规范化后，仅检查自己的规范化LaTeX，宣称无需修正版；25创建四行实际输出，27自查、28错误宣布完成。实际verifier复制Markdown与ACP25逐字节一致。公开PDF独立3倍渲染与6倍局部图确认来源括号异常。主归因agent_visual_transcription_normalization_and_self_check，原题面已明确保留原式并另附修正，原Skill一般公式保留指导也已存在，另记来源核对与修正边界说明不足；不能称原任务指导缺失。

候选仅原marker Overview追加通用来源核对/原式与修正版分离说明，+313字节、正文2393字节；其余13文件不变，反向恢复精确，无新步骤/helper、公式/数量/页码/题号/答案/评分改动。详见original-audit.json、round-1/repair-plan.json及diff。原Marker两次失败分别为OCR-error缓存缺失/权限与改HF_HOME后超时，属于中间工具依赖问题；原轮最终为正常断言FAIL。任务局部Dockerfile只补预下载官方包要求的第六个固定版本OCR-error模型，原task/PDF/verifier和五模型不变；免费实际模型下载/六模型离线加载gate待执行，未声称完成。

边界记录：初读原pytest失败stdout意外暴露期望公式字面量；不打开expected文件/oracle，不向候选加入任何答案，归因另由公开PDF、实际输出和轨迹独立核查。该暴露限制永久保留。原main/预导出缺失、已删除中间产物不重建；未来PASS不证明Skill唯一因果。当前0新模型调用，费用null，未入Gold。


## 2026-10-07T00:37:21.552442+08:00 Round1 真实启动

免费preflight确认原task digest不变、执行副本digest sha256:24579ebad8289d92da3152331429adb53634413287161e5be86286a798942e59、原PDF SHA一致、candidate反向恢复及pinned runtime通过，六模型固定revision配置端点/PyPI/Chromium端点可达；68个既有Docker网络和路由与default 10.253.235.0/24非重叠。启动Cfree 29150277632字节高于5GB。仅environment/Dockerfile补官方实际依赖第六模型预缓存，task/PDF/verifier不改；原/执行任务必须分开记录，未来PASS不证明Skill唯一因果。

唯一活动 latex-formula-extraction-opus47-manual-round-1-r001，runner 73692 实际run_round1.py，所属compose build 73754, 73776 正常构建main；当前docker_build、startup/题锁held，容器为空符合构建。已确认真实build后结束本次监控。容器六模型真实离线加载gate仍待执行，首个provider前fail-closed；不得把端点可达说成模型已加载或推理正常。provider/reward/费用未知null。首次start-confirmation不覆盖，下次读真实result/日志/轨迹/PID/container/compose/buildx/锁/gate，正常进展即结束，不重复启动。


### 2026-10-07T01:22:48.626071+08:00 latex Round1 付费前基础设施终止

r001在镜像export/unpack阶段退出255，0provider、0工具/Skill调用、0字节ACP，gate未执行，reward/费用null。六模型download阶段日志完成，不等于离线加载通过。C盘实测约25MB、WSL Docker挂载Input/output error，Windows CLI引擎查询500；记录磁盘耗尽与引擎故障，尚不锁定内部唯一崩溃因果，不称OOM/Skill或模型FAIL。原result/log/input/初次启动与poll证据保留；当前无活动rollout，不入Gold，仍新增5/14、Gold20/29、累计结束provider300。uv官方cache prune报告0；精确删除两个未运行Temp安装器420334848字节，仅恢复约445MB，不能声称达5GB。正在正常停止故障Docker、核查释放空间；未重跑/未新付费。原候选与评分不变。


### 2026-10-07T01:37:53.126153+08:00 基础设施恢复准备

原Round1 r001保持pre-provider void，0模型调用。Windows临时闲置安装器删除420334848字节；官方uv cache prune无可删条目，0字节。精确删除已通过HVAC/视觉稳定性两题9个停止容器、4个可解析无引用镜像（含本次void CUDA镜像），另6个历史image ID在删除前已不可解析，不能声称本轮删除。其余50容器ID/名称/镜像关联/状态一致。单独四条父缓存筛选返回0B；随后确认本次CUDA安装缓存及全部下游10条私有缓存的封闭依赖链，用精确ID正则筛选删除，Docker报告24.12GB。未全局prune、未force、未删卷/真实主产物、未新建D重复归档；实际C盘回收待离线压缩完成。

独立recovery002已准备，同一+313字节Marker候选不变；任务副本仅Dockerfile变化，20文件逐字节比较与反向恢复通过。官方CPU Torch2.14.1+cpu cp312 x86_64 wheel HEAD200、196253677字节、官方index SHA5a6363570c753812540a05eb82380e329469cbe668643e88111414c12627711f，直接哈希固定安装；pip关闭cache，HF只修缺少read/traverse权限的条目，避免已可读模型全量copy-up。CPU/backend/基础设施介入影响可比性，不能证明Skill唯一因果；尚未启动，真实六模型离线加载gate尚未执行。证据dependencies/cpu-recovery002-receipt.json及recovery-storage-20261007。


### 2026-10-07T01:41:17.778623+08:00 容量与Docker恢复，独立recovery002已真实构建

精确删除后的离线压缩完成：VHD长度240605200384→222352637952，减少18252562432字节；C可用235831296→21640798208字节，两种口径分别记录。仅DockerSafeStart恢复Windows/WSL引擎29.8.1健康。recovery002免费preflight通过原digest49df78d85f4e04b51db20f17bdfcfb479f19b2e1c8acaf2090a03f8b85c78238、执行digestebad48a72e46a20bdbc7b36a96361b7454b3f7cfb0f8225fa7a4becacbfa46e2、候选/runtime/真实PDF/所有依赖端点；68既有网络与路由不重叠，default10.253.236.0/24。启动Cfree21621612544字节>5GB。唯一runner1109实际run_round1_recovery002.py，compose1367/1391与buildx1429属于本rollout真实main构建，startup/题锁held，当前容器为空符合构建。六模型CPU离线实际加载gate尚待执行，不把preflight HEAD当gate通过；provider/评分/费用未知null。首次收据round-1-r001-recovery002-start-confirmation.json保留。已确认真实build后结束本次监控，不重复启动；新增5/14、Gold20/29、累计结束proxy300不变。


### 2026-10-07T02:34:04.783578+08:00 验收及独立验证契约修订

2026-10-07T02:34:04.783578+08:00 latex恢复轮正常end_turn、34/60、34provider全200、30工具/0显式Skill、48完整ACP；首provider前CPU六模型真实离线gate通过。原checker保持有效FAIL6PASS/1FAIL、reward0。实际ACP31–34来源核对、44–45保留原式另附修正已遵循；剩余单字符括号修复被唯一像素样式拒绝，另发现原RGBA getbbox颜色假阳性。单独v2验证修订接受已保留原式内普通加减分组笔误的两种单字符修复，同时改RGB比较；其他数学token、原式像素核对及六项检查不变。真实交付单独补评7PASS/reward1，0额外模型调用；原真实旧输出负控仍5PASS/2FAIL，改修正版运算符6PASS/1FAIL，漏保留原式5PASS/2FAIL。v1弱像素比较的试验PASS未入Gold。原result与原FAIL不覆盖，不与原评分直接等同比较，不把checker问题当Skill缺陷。预verifier archive244457字节SHA57fe5813360973b4c9daec72a505b98ba1e41c18e11a685b6913b36519fbf085两文件与停止main、原verifier输出及补评后真交付一致；没有改真交付或重建。原公式意外暴露/原产物缺口/wire脱敏/CPU后端/权限警告与跨流程维护影响等限制保留。记录入04增量及Claude兼容Gold21项RI/D一一对应，旧01/02/03不变；新增6/14、Gold21/29，累计结束provider334不是费用。latex禁止重跑，当前无活动，转manufacturing-fjsp-optimization。


## 2026-10-07 完成轮主记录单副本迁移

2026-10-07T04:18:26.384417+08:00 完成的recovery002真实run目录58文件139556844字节移至D:/SkillGen-benchmarking-storage/manual_annotation_runs_claude/latex-formula-extraction/runs/claude-manual-annotation/latex-formula-extraction-opus47-manual-round-1-r001-recovery002；原C路径保留junction。所有58文件在迁移前、D副本及C junction均逐文件大小/SHA一致，临时C副本已删除，只有一份主数据，无永久重复归档。上述D收据及manifest.primary_run_storage记录证据。原版FAIL、v2补评PASS、所有质量/暴露/比较限制、Gold逻辑路径及内容均未更改。
