# 论文来源与标注

[逐篇快照](snapshot.json)列出每组文件名和出版记录。训练 PDF 来自固定版本的 SkillsBench 原题，其中第二篇也是 Interspeech 2024 出版原件。三个泛化组共 15 篇，沿用同届出版版式，每篇 5 页。论文的著作权归各自权利人所有。[SkillsBench 原题](https://github.com/benchflow-ai/skillsbench/tree/b63b7b2850226b6aa4fb5929a8c1ac7bc4d9a6af/tasks/paper-anonymizer) · [ISCA 论文集](https://www.isca-archive.org/interspeech_2024/)

低栏外占比条件下，每三篇含 13 个作者栏字段和 9 个首页出版字段。高栏外占比条件下，每三篇含 10 个作者栏字段、9 个首页出版字段和 3 段第 4 或第 5 页的致谢。两种条件都要遮盖 22 项。组间使用不同论文，栏外占比的变化也涉及字段类型。每篇至少有一处逐页保留区，每篇另计一个元数据项。

每组的 `expected_output.json` 按文件和字段保存标注。页码从 1 开始，矩形使用 PyMuPDF 页面坐标。一个字段可包含多行，带有 `identity_words` 的作者栏按词检查。渲染与文字检查使用同一版本的 PyMuPDF。
