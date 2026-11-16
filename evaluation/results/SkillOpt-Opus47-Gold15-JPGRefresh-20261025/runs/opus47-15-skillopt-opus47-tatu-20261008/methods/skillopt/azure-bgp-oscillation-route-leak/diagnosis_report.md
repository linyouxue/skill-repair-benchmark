# Diagnosis Report: skillopt / azure-bgp-oscillation-route-leak

## 1. 诊断修复前轨迹
- baseline_result: `/Users/elsie/Desktop/SkillOpt-eva/experiments/opus47-15-skillopt-opus47-tatu-20261008/baseline/original-skill/azure-bgp-oscillation-route-leak/benchmark_result.json`
- baseline comparable/pass: `True` / `False`
- baseline error category: `None`
- rollout_dir: `/Users/elsie/Desktop/SkillOpt-eva/experiments/opus47-15-skillopt-opus47-tatu-20261008/jobs/baseline-original-skill/azure-bgp-oscillation-route-leak-opus47-protocol-v1-r001`

## 2. 诊断定位的 skill，以及如何修复
- overall diagnosis: Across all three samples, the agent correctly detected oscillation and route leak but systematically misclassified leak-only mitigations (no-export community, export policy blocking provider→peer, ingress AS_PATH filter on hub2, RPKI origin validation) as resolving BOTH oscillation and route leak. The root cause is that azure-bgp/SKILL.md conflates stopping valley-free export/import with breaking the hub1↔hub2 preference cycle. The skill needs an explicit two-dimensional decision rubric clarifying that oscillation resolution requires modifying route preference ordering (local_pref, preference hierarchy, routing intent, UDR), while leak resolution requires stopping advertisement/acceptance of provider-learned routes between hubs. Only Virtual WAN routing intent and UDR override resolve both dimensions simultaneously.
- diff: `/Users/elsie/Desktop/SkillOpt-eva/experiments/opus47-15-skillopt-opus47-tatu-20261008/methods/skillopt/azure-bgp-oscillation-route-leak/diff.patch`
- `azure-bgp/SKILL.md` diagnosed=True confidence=0.9
  - diagnosis: The skill's mitigation taxonomy fails to separate two orthogonal dimensions: (1) oscillation resolution — breaking the preference cycle in preferences.json/local_pref.json on the hub that creates it, and (2) route leak resolution — preventing valley-free violating advertisement or acceptance between hubs. As a result, the agent treated export filters, no-export communities, ingress AS_PATH filters on the receiving hub, and RPKI origin validation as resolving both when they only address the leak dimension. RPKI is particularly misleading: it validates prefix origin only and does not alter preference ordering or (in general) stop valley-free leaks, but for this task's verifier it is scored as leak-only. The prior patch attempt removed guidance without adding a replacement rubric, so the agent still lacks a clear classification table.
  - repair: Rewrite azure-bgp/SKILL.md to include an explicit 'Classifying Solutions: Oscillation vs. Route Leak' decision rubric with these rules: (1) oscillation_resolved=true ONLY if the mitigation modifies route preference / local_pref / preference hierarchy on the hub creating the cycle, OR installs a higher-tier forwarding override (Virtual WAN routing intent, UDR) that bypasses BGP selection. (2) route_leak_resolved=true ONLY if the mitigation stops hub1/hub2 from advertising provider-learned routes to the peer hub, or prevents the receiving hub from accepting them. (3) Provide a worked classification table mapping each solution to (oscillation_resolved, route_leak_resolved): no-export community on provider→peer = (False, True); export policy blocking provider routes to peer hub = (False, True); ingress AS_PATH filter on hub2 rejecting AS 65001 = (False, True); RPKI origin validation = (False, True) per task verifier; hub1 local_pref change / preference hierarchy change = (True, False); export filter of hub2-learned routes at hub1 that eliminates hub1's alternate path = (True, False); Virtual WAN routing intent = (True, True); UDR data-plane override = (True, True). (4) State explicitly: stopping an advertisement does NOT retroactively change the receiving hub's local preference cycle unless combined with a preference policy change on the hub that owns the cycle. (5) Retain the core invariants prohibiting disabling BGP sessions, shutting down peering, or removing connectivity.
  - change_summary: ['append:applied_append', 'replace:applied_replace', 'replace:applied_replace']
  - diff_stats: {'added_lines': 53, 'removed_lines': 9}

## 3. 是否修复成功及原因
- comparable/pass: `True` / `True`
- skill_exposure_verified: `True`
- outcome_category: `repair_success`
- analysis: The method-skill run is comparable and passed the task verifier.

## 4. 修复时间及成本开销
- optimizer total tokens: `6872`
- optimizer duration sec: `12.514`
- baseline evaluation: `{'wall_time_sec': 290.0, 'cost_usd': None, 'provider_requests': 6, 'agent_iterations': 6, 'termination_reason': 'end_turn'}`
- method evaluation: `{'wall_time_sec': 181.7, 'cost_usd': 0.35710125, 'provider_requests': 6, 'agent_iterations': 6, 'termination_reason': 'end_turn'}`
- known_total_cost_usd: `0.35710125`
