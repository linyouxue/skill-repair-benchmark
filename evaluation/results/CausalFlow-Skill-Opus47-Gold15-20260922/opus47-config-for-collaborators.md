# Claude Opus 4.7 实验配置与15题清单

核对日期：2026-09-22。用于向同学说明本轮 CausalFlow→Skill 实验的配置语义，并适配不同中转站。本文是说明文件，不修改正在运行的实验。

## temperature、effort、thinking 分别是什么

| 参数 | 本轮请求/配置 | 可供复现的语义 |
|---|---|---|
| 模型 | OpenRouter：`anthropic/claude-opus-4.7` | 必须实际路由到 Claude Opus 4.7；其他站的模型别名自行对应 |
| temperature | 方法和Skill转写请求主动省略；执行器入口未手动指定 | 官方默认 **1.0**；使用默认采样，不能写成0、0.35或0.7 |
| effort | 未显式设置 `reasoning_effort` / `output_config.effort` | 官方默认 **high**，不是medium、xhigh或max |
| thinking | 未显式开启；本轮冻结OpenRouter目录为 `default_enabled=false` | **关闭独立thinking模式**；与effort=high并不矛盾 |
| max_tokens | 32768 | 每次请求输出上限，不是整题总预算，也不是thinking预算 |
| top_p / top_k | 不设置 | 保留默认行为 |
| fresh rollout迭代上限 | 60 | 每题60次parent iterations；text-only continuation共享此预算 |

Anthropic文档说明，Opus4.7的temperature只能采用默认值：默认是1.0，显式传1.0为兼容用途，其他值会被拒绝。因此优先不传；中转站表单必须填数值时填1.0。[temperature官方说明](https://platform.claude.com/docs/en/api/messages/create)

官方API的effort默认是high；effort同时影响普通输出与工具调用，即使thinking关闭也有意义。不能把“未传effort”写成effort=none或没有推理能力。[effort官方说明](https://platform.claude.com/docs/en/build-with-claude/effort)

Opus4.7原生API的thinking默认关闭，开启adaptive thinking需单独设置。[thinking官方说明](https://platform.claude.com/docs/en/build-with-claude/thinking)

## 证据边界

上述1.0/high是按官方默认规则解释本轮配置，不是服务端回显的采样参数。当前方法/adapter代码不发送temperature与effort；冻结的OpenRouter模型目录同时记录`default_effort=high`、`default_enabled=false`。两次真实接口探针的reasoning_tokens均为0；已核对的当前azure任务6次执行响应也均为0。

任务轨迹日志仅保留部分请求字段，不记录temperature、reasoning和max_tokens；不能仅凭这些字段在日志中缺失，声称捕获到了完整网络请求。第三方中转若有参数重写，需要按其实际转发规则核对，不能把所有站的“默认”一概视为相同。

## 不同中转站如何填写

统一的配置目标为：**Opus4.7，默认temperature 1.0，默认effort high，thinking关闭，max_tokens 32768。** 基础地址和密钥使用同学自己的中转站配置。

如果中转站提供Anthropic Messages兼容接口，可按下列参数语义明确指定。模型ID按中转站提供的别名替换；实际任务仍需自己的system/messages、tools或JSON schema。

```json
{
  "model": "<该中转站的Opus4.7模型ID>",
  "max_tokens": 32768,
  "thinking": {"type": "disabled"},
  "output_config": {"effort": "high"},
  "messages": [{"role": "user", "content": "<实际任务输入>"}]
}
```

temperature在示例中省略，对应默认1.0。上例是为了明确表达跨站配置目标；本轮历史请求采用省略参数的方式。

如果是OpenAI Chat Completions兼容接口，不能直接假定支持Anthropic的字段。对OpenRouter，原实验省略整个reasoning对象；若新配置需要明确关闭，可用`"reasoning":{"enabled":false}`，effort字段继续省略。对其他中转站，应使用它明确定义的“关闭thinking”方式。

**不要为了填上high，直接添加`reasoning_effort="high"`或`reasoning={"effort":"high"}`。** 一些网关会据此自动开启thinking，改变本轮条件；Anthropic的`output_config.effort`与网关的reasoning开关不能机械互换。OpenRouter文档明确说明可由effort推断reasoning是否启用。[OpenRouter参数说明](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens)

如果中转站只提供一个“推理强度”下拉框，选high会同时开启thinking，且没有独立关闭选项，则该界面无法直接完整表达本轮配置。需要确认其API映射，或将差异记录为thinking-enabled条件。

## 本轮实验其他固定条件

- 修复方法、Skill转写、fresh rollout均使用Opus4.7。
- 最多3题并发，方法与验证共用资源门限；每题单轮Skill修复、一次有效fresh rollout。
- 复用已有original-skill失败轨迹，不重新运行original-skill。32768/60描述的是本轮新调用；历史baseline存在128000输出上限等例外，见manifest记录，不回填成统一参数。
- 当前CausalFlow配置：严格双重重放；每步骤1次干预，每因果步骤3个修复候选；full-trace/full-success；随后增加一次Skill适配阶段。
- Gold裁判独立使用GPT-5.5、medium effort、8192输出上限；全部worker结束后评分。这不是Opus的effort设置。

## 15个任务

以下为31题Gold中选取的15个Claude首轮失败任务，共对应32个Gold缺陷。列表为任务集合，不代表并行调度顺序。

```text
azure-bgp-oscillation-route-leak
data-to-d3
dynamic-object-aware-egomotion
enterprise-information-search
fix-build-agentops
flink-query
jpg-ocr-stat
manufacturing-equipment-maintenance
paper-anonymizer
pddl-airport-planning
python-scala-translation
reserves-at-risk-calc
seismic-phase-picking
shock-analysis-supply
video-silence-remover
```

同目录证据：protocol.json、manifest.json、model_catalog.json、model-preflight-20260922.json，以及experiment.py、source/llm_client.py。本文不含密钥。
