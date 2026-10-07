# Verifier-only validation evidence - azure-bgp-oscillation-route-leak

- Selected Agent rollout: azure-bgp-oscillation-route-leak-opus47-manual-round-2-r001
- Validation class: verifier-only-pass
- Verification basis: round-2-verifier-only-r001; azure-origin-validation-v1
- Verifier-only model calls: 0
- Registry validation status: agent-validated via separately revised origin-validation verifier contract

The raw Agent trajectory/result is preserved unchanged in repaired_run/. These files record the separate verifier-contract replay/recovery used by the Claude Gold registry. They are not rewritten into the raw benchmark result.

Gold limitation: 原21/22保留；22/22仅azure-origin-validation-v1，依据公开origin与RFC6811纠正唯一错误标签。其他断言不变。保留题面stop-advertising与Skill mitigation抽象冲突，不宣称实际控制面改变。原模型RPKI判断本已正确，verifier修订不计Skill缺陷。单次通过不证明唯一因果。
