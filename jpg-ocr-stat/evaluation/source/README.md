# 来源、版本和处理

图片来自ICDAR2019-SROIE，原作者为Huang等及ICDAR2019 Robust Reading Challenge组织者。使用的公开版本：

- [SROIE来源与数据说明](https://github.com/jsdnrs/ICDAR2019-SROIE/blob/77c4c11490e3c4179ee22f86611569c71c04b5f9/DATASET.md)，元数据提交`77c4c11490e3c4179ee22f86611569c71c04b5f9`。
- [图像镜像](https://huggingface.co/datasets/jsdnrs/ICDAR2019-SROIE/tree/bffe40c26759f3376ec2b3ae9031dbba54cd587c)，版本`bffe40c26759f3376ec2b3ae9031dbba54cd587c`。
- 旧200张中已保存的原JPEG复用此前的[zzzDavid镜像](https://huggingface.co/datasets/zzzDavid/ICDAR-2019-SROIE/tree/27be4271b251c256f695acbade9a801bffe85994)。其数字ID通过商户、地址、日期和金额标注建立交叉映射，再核查图像尺寸及内容；当前文件统一采用SROIE的`X…`源ID。

保留来源附带的 [LICENSE](LICENSE) 和 [NOTICE](NOTICE)。来源声明派生SROIE材料遵循CC-BY 4.0，使用时应保留署名、来源、许可及修改说明。这不改变原任务5个Skill各自的许可。

本次只选择60张，排除原22票及相同票据的变体；矩形裁剪边缘背景后无损保存为PNG。每张原尺寸、最终尺寸和裁剪坐标见 [manifest.json](../manifest.json)，未缩放或修改像素文字。旧200张答案照用冻结表，补充票照用来源实体标注，仅统一日期/金额的输出格式；不复制来源全部OCR标注或旧方法成绩作为修复输入。

当前60张及参考表公开，但只允许最终冻结Skill评测。SROIE及部分旧样本已公开，不能据此声称严格盲测或完全未暴露。语言筛选允许商户/地址保留非英文拉丁字母原文，业务正文要求英文。

参考论文：[ICDAR2019 Competition on Scanned Receipt OCR and Information Extraction](https://arxiv.org/abs/2103.10213)。
