**请每个方法单独建立一个目录**
大致最后结构如下：
```text
results/
├── Method1/
│   ├── submission.json
│   │
│   ├── tasks/
│   │   ├── dialogue-parser/
│   │   │   ├── repaired_skill/
│   │   │   │   ├── SKILL.md
│   │   │   │   ├── scripts/
│   │   │   │   ├── references/
│   │   │   │   └── ...
│   │   │   │
│   │   │   ├── original_run/
│   │   │   │   ├── executor_request.json
│   │   │   │   ├── result.json
│   │   │   │   ├── benchmark_result.json
│   │   │   │   └── trajectory/
│   │   │   │       └── acp_trajectory.jsonl
│   │   │   │
│   │   │   └── repaired_run/
│   │   │       ├── executor_request.json
│   │   │       ├── result.json
│   │   │       ├── benchmark_result.json
│   │   │       └── trajectory/
│   │   │           └── acp_trajectory.jsonl
│   │   │
│   │   ├── court-form-filling/
│   │   │   ├── repaired_skill/
│   │   │   │   └── ...
│   │   │   ├── original_run/
│   │   │   │   └── ...
│   │   │   └── repaired_run/
│   │   │       └── ...
│   │   │
│   │   └── <other-task>/
│   │       └── ...
│   │
│   └── trajectory_timelines/
│       ├── before/
│       │   ├── dialogue-parser__Method1__<run_id>.md
│       │   ├── court-form-filling__Method1__<run_id>.md
│       │   └── ...
│       │
│       ├── after/
│       │   ├── dialogue-parser__Method1__<run_id>.md
│       │   ├── court-form-filling__Method1__<run_id>.md
│       │   └── ...
│       │
│       ├── unknown/
│       │   └── ...
│       │
│       └── trajectory_timeline_index.json
│
├── Method2/...
└── ...
```
# 关于诊断和修复结果的上传

请按照现有 evaluation 的格式准备 `submission.json`。

示例：
```json
{
  "method_id": "xxx",
  "benchmark_version": "core25-gold-defects-20260909-v1",
  "tasks": [
    {
      "task_id": "dialogue-parser",
      "diagnoses": [
        {
          "prediction_id": "P001",
          "description": "方法诊断出的 Skill 缺陷描述",
          "locations": [
            {
              "file": "xxx/SKILL.md",
              "section": "..."
            }
          ]
        }
      ],
      "repaired_bundle": "tasks/dialogue-parser/repaired_skill",
      "executor_run_id": "dialogue-parser-final-r001"
    }
  ]
}
```
然后对所有参与诊断与修复评测的任务，必须上传方法最终生成并用于 method-skill rollout 的完整 repaired_bundle；对于经核验的 original_pass 跳过任务，不需要提供修复后的 Skill

# 关于模型运行轨迹的上传
使用脚本export_trajectory.py把模型运行轨迹转换成md文件后上传

假设当前方法的结果目录为：
```text
results/xxx/
```
建议先执行：
```text
python export_trajectory.py \
  --root "results/xxx" \
  --dry-run
```
--dry-run 只检查有哪些轨迹，以及它们会被识别为 before / after / unknown，不会写入文件。

确认无误后执行：
```text
python export_trajectory.py \
  --root "results/xxx"
```
脚本会自动创建：
```text
results/xxx/trajectory_timelines/
├── before/
├── after/
├── unknown/
└── trajectory_timeline_index.json
```
其中：

original-skill → before/
method-skill   → after/

脚本优先根据 executor_request.json、result.json 和 benchmark_result.json 中的运行条件判断 Before / After。

请把所有模型运行轨迹转换完成之后把文件夹上传上来
