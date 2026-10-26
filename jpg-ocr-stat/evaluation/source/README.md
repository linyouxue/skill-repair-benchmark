# 来源、版本和处理

图片来自ICDAR2019-SROIE，原作者为Huang等及ICDAR2019 Robust Reading Challenge组织者。使用的公开版本：

- [SROIE来源与数据说明](https://github.com/jsdnrs/ICDAR2019-SROIE/blob/77c4c11490e3c4179ee22f86611569c71c04b5f9/DATASET.md)，元数据提交`77c4c11490e3c4179ee22f86611569c71c04b5f9`。
- [图像镜像](https://huggingface.co/datasets/jsdnrs/ICDAR2019-SROIE/tree/bffe40c26759f3376ec2b3ae9031dbba54cd587c)，版本`bffe40c26759f3376ec2b3ae9031dbba54cd587c`。
- 旧200张中已保存的原JPEG复用此前的[zzzDavid镜像](https://huggingface.co/datasets/zzzDavid/ICDAR-2019-SROIE/tree/27be4271b251c256f695acbade9a801bffe85994)。其数字ID通过商户、地址、日期和金额标注建立交叉映射，再核查图像尺寸及内容。v2新group1/3用`receipt_….png`保持旧成员映射，group2保留原`X….png`文件名；SROIE源ID均在manifest记录。

保留来源附带的 [LICENSE](LICENSE) 和 [NOTICE](NOTICE)。来源声明派生SROIE材料遵循CC-BY 4.0，使用时应保留署名、来源、许可及修改说明。这不改变原任务5个Skill各自的许可。

v2共有60张：新group1/3的40张全部来自旧200张，按其历史baseline错误再筛英文正文和清晰度；group2的20张从v1原样保留。原22票和同票变体排除。每张原尺寸、最终尺寸和裁剪坐标见 [manifest.json](../manifest.json)。当前`api-3000px-20261025`修订中，39张新图保持源像素裁剪；仅group1的`receipt_0088.png`将已裁票据1468×3307以LANCZOS等比缩小为1332×3000并保存PNG，以满足本次上游多图请求的尺寸要求。未进一步裁字、改字或翻译，不修改上游原图和标注文件；新40张参考值及group2参考表均保持原样。全部40张离线格式/尺寸检查见[api_image_check.json](../api_image_check.json)，没有付费调用API验证。

本v2只用于最终冻结Skill评测。源SROIE、旧200张和v1已公开，且本v2明确按历史错误筛选，不能称严格盲测、完全未暴露或随机总体泛化估计。业务正文要求英文。许可和来源署名继续完整保留。

参考论文：[ICDAR2019 Competition on Scanned Receipt OCR and Information Extraction](https://arxiv.org/abs/2103.10213)。
