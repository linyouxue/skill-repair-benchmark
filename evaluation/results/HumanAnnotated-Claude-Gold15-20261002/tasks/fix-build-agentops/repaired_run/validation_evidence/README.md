# Verifier-only validation evidence - fix-build-agentops

- Selected Agent rollout: fix-build-agentops-opus47-manual-round-2-r001
- Validation class: verifier-only-pass
- Verification basis: round-2-verifier-only-r001; agentops-supported-python-v1
- Verifier-only model calls: 0
- Registry validation status: agent-validated via verifier-only supported-matrix recovery

The raw Agent trajectory/result is preserved unchanged in repaired_run/. These files record the separate verifier-contract replay/recovery used by the Claude Gold registry. They are not rewritten into the raw benchmark result.

Gold limitation: 仅修订支持矩阵py38–py312通过，不是原六版本协议原样通过。py37与原verifier固定LangChain依赖最低Python>=3.8.1冲突；矩阵/PATH/依赖预置/输出隔离为独立verifier修复，原版保留，评分断言不变，正式计时仍240s。模型实际保持session guard而恢复历史时间戳顺序；修复前隔离测试出现初始化属性缺失，未见修复后的隔离重测，不能宣称所有初始化问题解决。单次候选通过不证明唯一因果。
