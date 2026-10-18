# 数据来源与发布范围

数据源为已冻结的`jpg-ocr-skill-repair-200-v1`，120/40/40成员和原图未改变。test2是原validation的用途别名，不是重新划分数据。

原始小票来自SROIE来源链，建设阶段使用的镜像为[zzzDavid/ICDAR-2019-SROIE](https://github.com/zzzDavid/ICDAR-2019-SROIE)，固定版本`27be4271b251c256f695acbade9a801bffe85994`。CC-BY-4.0信息来自[jsdnrs镜像说明](https://github.com/jsdnrs/ICDAR2019-SROIE/blob/main/DATASET.md)，该镜像引用官方RRC下载页；本次直接访问RRC页面超时，未据此宣称完成官方许可条款的独立核验。保留这一来源声明及核验边界，不把仓库的Apache-2.0套用于全部图片。

原数据集引用：Huang et al., *ICDAR2019 Competition on Scanned Receipt OCR and Information Extraction*，ICDAR 2019，DOI：[10.1109/ICDAR.2019.00244](https://doi.org/10.1109/ICDAR.2019.00244)。本版本从原来源选取200张图并冻结成员与批次，另组织Skill修复用的运行证据及允许反馈；未重新标为原论文的标准训练/测试切分。

官方Skill及其附件沿用baseline实际冻结快照，保留包内原有许可文件。原Task和grader原字节保留。选定run与归档成员清单在`trajectory_inventory.json`。组织者的本地来源定位、SSH配置、凭据和缓存不进入本公开目录。

`pdf`和`xlsx`的原`LICENSE.txt`为Anthropic自定义条款，含再分发、复制及衍生作品限制。官方[Skills说明](https://github.com/anthropics/skills#about-this-repository)将这些文档Skill列为source-available而非开源；具体条款见包内[pdf/LICENSE.txt](train/skills/original/pdf/LICENSE.txt)和[xlsx/LICENSE.txt](train/skills/original/xlsx/LICENSE.txt)。完整LLM归档包含当时实际预载的Skill正文，也涉及相同来源材料。本发布保留这些条款，不声称取得额外的公开分发或修改授权；仓库公开可读不替代相应权利。其他Skill同样不因被收录而重新许可。

训练输入目录不提供策展转录、来源答案、GT值或verifier断言。GT和原评分实现随`evaluation_only/runtime/`公开；按实验协议，它们不得进入修复上下文。已有三遍baseline原始文件和账本保持原样；本次仅复制材料、无损归档并导出允许反馈，没有重新生成模型回答。
