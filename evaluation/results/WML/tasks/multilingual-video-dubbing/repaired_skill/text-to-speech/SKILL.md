---

name: text-to-speech
description: "Practical mastering steps for TTS audio: cleanup, loudness normalization, alignment, and delivery specs."
---

# SKILL: TTS Audio Mastering

This skill focuses on producing clean, consistent, and delivery-ready TTS audio for video tasks. It covers speech cleanup, loudness normalization, segment boundaries, and export specs.

## 1. TTS Engine & Output Basics

Choose a TTS engine based on deployment constraints and quality needs:

* **Neural offline** (e.g., Kokoro): stable, high quality, no network dependency.
* **Cloud TTS** (e.g., Edge-TTS / OpenAI TTS): convenient, higher naturalness but network-dependent.
* **Formant TTS** (e.g., espeak-ng): for prototyping only; often less natural.

**Key rule:** Always confirm the **native sample rate** of the generated audio before resampling for video delivery.

**Quality gate (engine selection & fallback):**

- If the task requires **“human-level/high quality”** speech (or you expect a perceptual naturalness metric to be used), treat TTS as a **quality-critical dependency**, not a best-effort step.
- Prefer an engine path in this order:
  1. **High-quality offline neural TTS** (best when network access is unreliable/blocked).
  2. **Cloud neural TTS** (only if it’s available and stable in the environment).
  3. **Formant TTS** (e.g., espeak-ng) **only for prototyping/debugging**.
- If cloud TTS fails and you only have formant/robotic offline engines available, **do not proceed to “final delivery” as-is**. Instead:
  - Switch to / install / enable an offline neural TTS option available in the environment, **or**
  - Clearly mark the limitation and stop before generating “final” assets.

This prevents spending time on mastering/alignment that cannot fix a low-naturalness voice.

---

## 2. Speech Cleanup (Per Segment)

Apply lightweight processing to avoid common artifacts:

* **Rumble/DC removal:** high-pass filter around **20 Hz**
* **Harshness control:** optional low-pass around **16 kHz** (helps remove digital fizz)
* **Click/pop prevention:** short fades at boundaries (e.g., **50 ms** fade-in and fade-out)

Recommended FFmpeg pattern (example):

* Add filters in a single chain, and keep them consistent across segments.

---

## 3. Loudness Normalization

Target loudness depends on the benchmark/task spec. A common target is ITU-R BS.1770 loudness measurement:

* **Integrated loudness:** **-23 LUFS**
* **True peak:** around **-1.5 dBTP**
* **LRA:** around **11** (optional)

Recommended workflow:

1. **Measure loudness** using FFmpeg `ebur128` (or equivalent meter).
2. **Apply normalization** (e.g., `loudnorm`) as the final step after cleanup and timing edits.
3. If you adjust tempo/duration after normalization, re-normalize again.

**Pre-delivery perceptual QA (when “high quality” is required):**

- Before muxing into the video (and before writing the final report), run an **offline** perceptual naturalness check on each synthesized segment WAV using a local MOS/UTMOS-style predictor if available.
- Use a configurable pass criterion (e.g., `score >= threshold` when the task defines one). If a segment fails:
  - Iterate **at the synthesis layer**: change voice/model, adjust synthesis settings, or switch to a higher-quality engine.
  - Re-run cleanup + loudness normalization only after a quality-acceptable take is produced.
- Do **not** assume mastering (filters/normalization) can “fix” low-naturalness synthesis; it typically cannot.

---

## 4. Timing & Segment Boundary Handling

When stitching segment-level TTS into a full track:

* Match each segment to its target window as closely as possible.
* If a segment is shorter than its window, pad with silence.
* If a segment is longer, use gentle duration control (small speed change) or truncate carefully.
* Always apply boundary fades after padding/trimming to avoid clicks.

**Sync guideline:** keep end-to-end drift small (e.g., **<= 0.2s**) unless the task states otherwise.

Representative run result:
{"task_name": "multilingual-video-dubbing", "rollout_name": "multilingual-video-dubbing-original-skill-v11x-20260903-r001", "rewards": {"reward": 0.0}, "agent": "openhands", "agent_name": "OpenHands CLI ACP Agent", "model": "openrouter/openai/gpt-5.2", "skill_mode": "with-skill", "skill_source": "task_bundled", "requested_skills_dir": null, "effective_skills_dir": "/mnt/c/Users/linyuanjing/Desktop/skill论文/SkillGen-benchmarking/expanded_original_skill_runs/gpt52-openrouter-v1.1-20260903/runs/expanded-original-skill/multilingual-video-dubbing-original-skill-v11x-20260903-r001/inputs/skills", "skills_sandbox_dir": "/skills", "include_task_skills": true, "n_tool_calls": 20, "n_skill_invocations": 0, "n_prompts": 1, "agent_result": {"n_tool_calls": 20, "n_skill_invocations": 0, "n_prompts": 1, "n_input_tokens": 0, "n_output_tokens": 0, "n_cache_read_tokens": 0, "n_cache_creation_tokens": 0, "total_tokens": 712081, "cost_usd": 0.41228285, "usage_source": "provider_response", "price_source": "litellm", "executor": {"name": "benchmark-executor", "protocol_id": "skillrepair-v1", "protocol_version": 1, "benchflow_base_version": "v0.6.7", "benchflow_base_commit": "aadad44acf27f193df98f438443116d514f51fb8", "openhands_cli_commit": "2df8a2835d3f1bd2f2eadf5a7a2e1ad0dfb0d271", "openhands_sdk_version": "1.28.1", "openhands_tools_version": "1.28.1", "agent": "openhands", "model": "openrouter/openai/gpt-5.2", "provider_route": "openrouter", "provider_base_url": "https://openrouter.ai/api/v1", "provider_protocol": "openai-completions", "skill_exposure_mode": "persistent-agent-context-full-skill-md", "evaluation_condition": "original-skill", "max_parent_iterations_per_step": 60, "iteration_scope": "one OpenHands Conversation.run per BenchFlow execution Step", "wall_clock_is_safety_watchdog": true, "wall_clock_safety_timeout_sec": 21600, "idle_safety_timeout_sec": 3600, "llm_request_safety_timeout_sec": 3600, "delegation_disabled": true, "skill_context_preloaded": true, "skill_bundle_sha256": "sha256:c5b426d3523cd33fc85190c1a4c4613c20209d9b9e67ab23b6594295c96c8f29", "preloaded_skill_count": 6, "preloaded_skill_files": ["ffmpeg-audio-processing/SKILL.md", "ffmpeg-format-conversion/SKILL.md", "ffmpeg-media-info/SKILL.md", "ffmpeg-video-editing/SKILL.md", "ffmpeg-video-filters/SKILL.md", "text-to-speech/SKILL.md"], "skill_bundle_file_count": 6, "skill_bundle_bytes": 17725, "iteration_accounting_complete": true, "iteration_limit_reached": false, "iteration_limit_hits": 0, "stop_reason": "end_turn", "prompt_runs": [{"prompt_ordinal": 1, "stop_reason": "end_turn", "acp_stop_reason": "end_turn", "execution_status": "finished", "error_code": null, "iterations_used": 21, "max_iterations": 60, "skill_context_preloaded": true, "skill_bundle_sha256": "sha256:c5b426d3523cd33fc85190c1a4c4613c20209d9b9e67ab23b6594295c96c8f29", "preloaded_skill_count": 6}], "skill_context_preload_observed": true, "observed_skill_bundle_sha256": "sha256:c5b426d3523cd33fc85190c1a4c4613c20209d9b9e67ab23b6594295c96c8f29", "observed_preloaded_skill_count": 6, "skill_context_preload_matches_expected": true}, "stop_reason": "end_turn", "acp_stop_reason": "end_turn", "iterations_used": 21, "max_iterations_per_run": 60, "prompt_runs": [{"prompt_ordinal": 1, "stop_reason": "end_turn", "acp_stop_reason": "end_turn", "execution_status": "finished", "error_code": null, "iterations_used": 21, "max_iterations": 60, "skill_context_preloaded": true, "skill_bundle_sha256": "sha256:c5b426d3523cd33fc85190c1a4c4613c20209d9b9e67ab23b6594295c96c8f29", "preloaded_skill_count": 6}]}, "final_metrics": {"total_prompt_tokens": 0, "total_completion_tokens": 0, "total_cached_tokens": 0, "total_cost_usd": 0.41228285}, "trajectory_summary": {"steps": 24, "tool_call_steps": 20, "user_message_steps": 1, "agent_message_steps": 1, "agent_thought_steps": 1, "other_steps": 1, "event_type_counts": {"user_message": 1, "agent_thought": 1, "tool_call": 20, "agent_message": 1, "agent_iteration_outcome": 1}, "tool_call_status_counts": {"completed": 20}, "partial_trajectory": false, "trajectory_source": "acp"}, "usage_tracking": {"requested": "auto", "status": "enabled", "environment": "docker", "endpoint_kind": "host", "usage_source": "provider_response"}, "error": null, "error_category": null, "verifier_error": null, "verifier_error_category": null, "export_error": null, "idle_timeout_info": null, "agent_timeout_info": null, "sandbox_startup_info": null, "transport_error_info": null, "verifier_timeout_info": null, "api_error_info": null, "suspected_api_error_info": null, "partial_trajectory": false, "trajectory_source": "acp", "started_at": "2026-09-03 21:42:14.072289", "finished_at": "2026-09-03 22:12:52.600883", "timing": {"environment_setup": 1369.2, "agent_setup": 28.2, "agent_execution": 271.0, "verifier": 39.8, "total": 1838.5}, "scenes": [{"name": "default", "skills_dir": null, "roles": [{"name": "agent", "agent": "openhands", "model": "openrouter/openai/gpt-5.2", "reasoning_effort": null, "timeout_sec": null, "idle_timeout_sec": null, "skills_dir": null, "capabilities": null, "env_keys": []}], "turns": [{"role": "agent", "has_prompt": false}]}], "loop": {"strategy": "single-shot"}, "executor": {"name": "benchmark-executor", "protocol_id": "skillrepair-v1", "protocol_version": 1, "benchflow_base_version": "v0.6.7", "benchflow_base_commit": "aadad44acf27f193df98f438443116d514f51fb8", "openhands_cli_commit": "2df8a2835d3f1bd2f2eadf5a7a2e1ad0dfb0d271", "openhands_sdk_version": "1.28.1", "openhands_tools_version": "1.28.1", "agent": "openhands", "model": "openrouter/openai/gpt-5.2", "provider_route": "openrouter", "provider_base_url": "https://openrouter.ai/api/v1", "provider_protocol": "openai-completions", "skill_exposure_mode": "persistent-agent-context-full-skill-md", "evaluation_condition": "original-skill", "max_parent_iterations_per_step": 60, "iteration_scope": "one OpenHands Conversation.run per BenchFlow execution Step", "wall_clock_is_safety_watchdog": true, "wall_clock_safety_timeout_sec": 21600, "idle_safety_timeout_sec": 3600, "llm_request_safety_timeout_sec": 3600, "delegation_disabled": true, "skill_context_preloaded": true, "skill_bundle_sha256": "sha256:c5b426d3523cd33fc85190c1a4c4613c20209d9b9e67ab23b6594295c96c8f29", "preloaded_skill_count": 6, "preloaded_skill_files": ["ffmpeg-audio-processing/SKILL.md", "ffmpeg-format-conversion/SKILL.md", "ffmpeg-media-info/SKILL.md", "ffmpeg-video-editing/SKILL.md", "ffmpeg-video-filters/SKILL.md", "text-to-speech/SKILL.md"], "skill_bundle_file_count": 6, "skill_bundle_bytes": 17725, "iteration_accounting_complete": true, "iteration_limit_reached": false, "iteration_limit_hits": 0, "stop_reason": "end_turn", "prompt_runs": [{"prompt_ordinal": 1, "stop_reason": "end_turn", "acp_stop_reason": "end_turn", "execution_status": "finished", "error_code": null, "iterations_used": 21, "max_iterations": 60, "skill_context_preloaded": true, "skill_bundle_sha256": "sha256:c5b426d3523cd33fc85190c1a4c4613c20209d9b9e67ab23b6594295c96c8f29", "preloaded_skill_count": 6}], "skill_context_preload_observed": true, "observed_skill_bundle_sha256": "sha256:c5b426d3523cd33fc85190c1a4c4613c20209d9b9e67ab23b6594295c96c8f29", "observed_preloaded_skill_count": 6, "skill_context_preload_matches_expected": true}, "task_digest": "sha256:8947bde71c1cb7d9652daf827bd979e9f09d14b5e89941871d4cdc895646d81a", "sandbox_id": null}
