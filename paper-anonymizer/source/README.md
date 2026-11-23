# 论文来源与标注

[逐篇快照](snapshot.json)记录来源类别、文件名、出版记录或固定版本的 arXiv 链接。训练沿用 SkillsBench 原件。三篇分别是 23 页的 VERA 预印本、5 页的 Interspeech 2024 论文和 12 页的 ICML 2025 工作坊论文 SpeechPrune。按实际 PDF 的页数和首页出版标记归类。泛化测试另选 18 篇，每类 6 篇，每三篇各取一类。论文著作权归各自权利人所有。[SkillsBench 原题](https://github.com/benchflow-ai/skillsbench/tree/b63b7b2850226b6aa4fb5929a8c1ac7bc4d9a6af/tasks/paper-anonymizer) · [ISCA 原题出版记录](https://www.isca-archive.org/interspeech_2024/shi24_interspeech.html) · [SpeechPrune 工作坊记录](https://icml.cc/virtual/2025/52870)

人工逐篇标出印刷署名、出版标记、作者附注、个人项目地址与致谢。每三篇共有 20 或 25 个应遮字段，按来源分别保留 23、9、12 个标题及正文抽样区域。每页至少覆盖一处。训练组与前三个测试组的栏外占比为 40%，group_04 为 65%。占比的分母只计应遮字段。技术实现按 PDF 中的位置区分首页作者栏与页脚、正文等栏外区域。[测试组逐项定位](line_labels.json)

每组的 `expected_output.json` 按文件和字段保存标注。页码从 1 开始，矩形使用 PyMuPDF 页面坐标。一个字段可包含多行，带有 `identity_words` 的作者栏按词检查。渲染与文字检查使用同一版本的 PyMuPDF。

运行 `python tools/build_references.py` 可从冻结 PDF 复核标注；运行 `python tools/validate_local.py` 可导出训练组和四个测试组并重放参考提交和负例。
