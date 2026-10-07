# Verifier-only validation evidence - reserves-at-risk-calc

- Selected Agent rollout: reserves-at-risk-calc-opus47-manual-round-1-r001
- Validation class: verifier-only-pass
- Verification basis: round-1-verifier-only-r002; rar-confidence-consistency-v1
- Verifier-only model calls: 0
- Registry validation status: agent-validated via separately revised verifier confidence contract

The raw Agent trajectory/result is preserved unchanged in repaired_run/. These files record the separate verifier-contract replay/recovery used by the Claude Gold registry. They are not rewritten into the raw benchmark result.

Gold limitation: 原版3/5保留；5/5仅指rar-confidence-consistency-v1，独立验证95%单侧分位数与舍入（并保留原1.65参考约定），一致计算下游期望，其余断言及容差不变。错误置信水平与原SQRT(3)负例仍拒绝。verifier修订不计Skill修复。latest与模板2025M9截止存在歧义；模型使用Python数值cross-check，交付计算为Excel公式，但不能声称完全遵守Excel-only程序约束。单次候选通过不能证明唯一因果。
