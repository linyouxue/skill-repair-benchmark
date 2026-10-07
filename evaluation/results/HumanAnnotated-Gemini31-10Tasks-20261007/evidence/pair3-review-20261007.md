# 第三批修复前原始机制对照

健康门复用seismic-health-20261006.json、dynamic-health-20261006.json；官方原版不重跑。实际完整原始轨迹与三模型证据索引分别见pair3-seismic-evidence-20261007.json、pair3-dynamic-evidence-20261007.json。只使用公开task、原Skill快照与已记录工具行为，未读取隐藏oracle/verifier/expected来设计修改。

地震拾取：Gemini首次缺少component identity已在ACP10恢复；最终实际results.csv由ACP47–50的完成运行生成167个pick，仍把pick.start_time当到达时刻，且跳过短channels数据。原API正文只有返回列表/print示例，未区分Pick窗口起点和概率峰值时间。GPT有效原版为r001-recovery001（r001 infra/r002无canonical不代替）；ACP12实际对象确认peak_time与start_time不同，最终ACP31用annotation时间轴。Claude ACP7/20即用peak_time，后续修正padding列。候选仅更正seisbench-model-api的结果对象及时间/原采样索引示例，保留其他文件、算法选择和已有归一化指导；不预先保证F1或继承旧Gold。通用API语义依据[SeisBench官方源码文档](https://seisbench.readthedocs.io/en/stable/_modules/seisbench/util/annotations.html)及GPT原始运行的安装对象观测。本候选不写标签、采样答案、概率/隐藏阈值。

动态物体自运动估计：Gemini ACP9直接照sampling原23–25行的range+append(n-1)追加非网格源尾帧，实际19个采样；GPT时间网格和Claude stride-only均18，采样首错不共同。公开task仅5FPS、sample ordinal及半开区间，没有完整bin或floor(duration*rate)约定。候选仅改sampling-and-indexing：按请求率构建t=0且t<duration的共享网格，取消无条件尾帧，分清源frame ID和sample ordinal；检查非整采样周期尾端及半开终点，保留其他Skill。禁止把已知18/207或隐藏标签写进候选。

两题从各自Gemini原版inputs/skills复制完整round-1/bundle/skills；modified_files分别仅seisbench-model-api/SKILL.md与sampling-and-indexing/SKILL.md，diff保存在各自skill.patch。候选待一次fresh Gemini验证；实际F→P与可复核机制支持后才进行正式defect级model_sensitivity/独立Gold，不能预贴cross_model_consistent。
