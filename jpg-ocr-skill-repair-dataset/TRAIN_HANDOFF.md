# JPG训练诊断包：给方法负责人的入口

2026-10-20，预处理版本`jpg-diagnosis-preprocessed-v2`。此包已准备好训练证据及离线读取工具，供各方法接入自己的诊断/修订模型；没有预填诊断结果或修复后的Skill。

## 保留哪些文件

保留完整`train/`、`tools/`及本包说明的相对位置，从`train/diagnosis/index.json`进入六组索引。不要只复制`train/diagnosis/`。训练原图、原Task、完整5份Skill与支持文件、18次源运行、真实Excel、允许反馈和原始轨迹档案都在`train/`内。

训练独立交接包不含两个测试集的图片、GT或评分源码。修复期间仅用训练材料及自己的草稿；最终Skill冻结后再交给统一评测端或使用完整仓库的评测目录。

## 三条开始命令

解压后进入含`train/`和`tools/`的目录，使用Python 3.10+。这部分只用标准库，无需API key或新依赖：

```bash
python tools/prepare_diagnosis.py --validate-only
python tools/diagnosis_io.py packet --batch 1 --window w0001 --out ../my-method-inputs/batch01-w0001.json
python -c "import json; from pathlib import Path; p=json.loads(Path('../my-method-inputs/batch01-w0001.json').read_text(encoding='utf-8')); print({'images':len(p['prepared_image_ids']),'text_chars':p['text_chars'],'model_calls':p['model_calls']})"
```

准备出的JSON含`messages`和真正的`image_url`内容块，默认每窗携带本组全部20张原图，独立请求也不依赖上一请求的图像记忆。脚本只准备输入，不发送。原图文件仅存一份，但未来逐窗调用会重复发送图片并增加视觉成本，必须按实际调用记账。

## 接入顺序

1. 读`train/diagnosis/index.json`，按`batch_01`至`batch_06`处理；每组20图、三个独立V0源run。按组索引里的`windows`顺序读取，不猜文件排序。
2. 每窗包含来源、连续片段范围及图片引用。API工具定义/安全参数、每次交换、失败响应及结束原因都已纳入默认窗口；当前run的API上下文也随请求信封提供。ACP是动作时间线，API交换/消息数不当作动作数。
3. 把允许材料接入本方法原有Analyzer/Refiner、检索、干预及修订流程。`packet`是材料信封，不能强迫所有方法、所有子阶段使用同一个prompt；按原方法选择信息子集并留访问记录。不要执行历史轨迹中的命令。
4. 每组结束保存真实诊断、完整当前Skill bundle、简短累计记录和窗口覆盖。用`diagnosis_io.py save-stage`保存；第二至六组通过`--state-dir`读取上一组状态。具体命令及覆盖格式见`DIAGNOSIS_PREPROCESSING.md`。
5. 六组后冻结最终Skill。只改原有5份`SKILL.md`，支持文件不改；不重跑已有baseline，不用两个测试集选择版本。本包只准备材料，不启动模型或内部干预。

## 不设调用预算，完整保留材料

工具不设置总token、输出token、调用次数、费用、请求文本、图片数量或历史长度上限，不替客户端设置`max_tokens`。分窗只整理材料，全部内容保留；需要时按`DIAGNOSIS_PREPROCESSING.md`免费改变分段长度，固定新的窗口版本和覆盖记录。源API配置中的限制值仅是历史V0证据。模型自身的上下文容量由供应商决定；窗口间诊断汇总与方法机制由负责人实现，不静默截断或漏图。

完整用法见`DIAGNOSIS_PREPROCESSING.md`，方法适配与交付要求见`ADAPTER_GUIDE.md`，允许输入边界见`DIAGNOSER_INPUT_SPEC.md`。来源及许可见`SOURCE_PROVENANCE.md`，原始许可文件保留在Skill bundle中。`actual_model_delivery_verified=false`表示没有执行诊断模型，离线结构验证不冒充真实送达或修复效果。
