import json, pathlib, collections, datetime, subprocess, sys, statistics

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / 'monitoring' / 'call-health-audit-20260924.json'
state = json.loads((ROOT / 'batch_state.json').read_text(encoding='utf-8'))
seen = set()
method = []
duplicates = []
for p in list(ROOT.glob('generation/**/*.response.json')) + list(ROOT.glob('recovery-history/**/*.response.json')):
    b = json.loads(p.read_text(encoding='utf-8'))
    rid = b.get('id')
    if rid in seen:
        duplicates.append(str(p.relative_to(ROOT))); continue
    seen.add(rid)
    method.append({'path':str(p.relative_to(ROOT)), 'id':rid, 'model':b.get('model'), 'usage':b.get('usage'), 'finish_reasons':[x.get('finish_reason') for x in b.get('choices',[])]})
fresh = []; runs = []; seen_fresh = set()
for p in sorted(ROOT.glob('runs/*/*/trajectory/llm_trajectory.jsonl')):
    rr = p.parents[1]
    events = []
    for line in p.read_text(encoding='utf-8').splitlines():
        x=json.loads(line); b=x.get('response',{}).get('body',{}) or {}; rid=b.get('id')
        if rid and rid in seen_fresh: continue
        if rid: seen_fresh.add(rid)
        e={'run':rr.name,'id':rid,'status':x.get('response',{}).get('status_code'),'model':x.get('metadata',{}).get('provider_model'),'request_model':x.get('request',{}).get('body',{}).get('model'), 'usage':b.get('usage'), 'response_status':b.get('status'), 'has_request_body': bool(x.get('request',{}).get('body')), 'has_response_body':bool(b)}
        events.append(e); fresh.append(e)
    runs.append({'run':rr.name,'requests':len(events),'http_status':dict(collections.Counter(e['status'] for e in events)), 'errors_recovered':[{'index':i,'status':e['status'],'later_http200':any(v['status']==200 for v in events[i+1:])} for i,e in enumerate(events) if e['status'] != 200]})

def totals(rows):
    usages=[x.get('usage') or {} for x in rows]
    return {'responses':len(rows),'models':dict(collections.Counter(x.get('model') for x in rows)), 'cost_usd':sum(u.get('cost',0) or 0 for u in usages), 'total_tokens':sum(u.get('total_tokens',0) or 0 for u in usages), 'prompt_tokens':sum(u.get('prompt_tokens',0) or 0 for u in usages), 'completion_tokens':sum(u.get('completion_tokens',0) or 0 for u in usages), 'cached_prompt_tokens':sum((u.get('prompt_tokens_details') or {}).get('cached_tokens',0) or 0 for u in usages), 'responses_with_prompt_split':sum('prompt_tokens' in u for u in usages), 'responses_with_cache_split':sum('cached_tokens' in (u.get('prompt_tokens_details') or {}) for u in usages), 'responses_with_cost':sum('cost' in u for u in usages), 'responses_with_usage':sum(bool(u) for u in usages)}

validator = ROOT.parents[2] / 'skill-repair-benchmark/.agents/skills/benchflow-experiment-review/scripts/validate_run_artifacts.py'
slots=[]
for task,s in state['tasks'].items():
    d={'task':task,'phase':s.get('phase'),'run':s.get('fresh_rollout_id'), 'latest_error':s.get('error')}
    if s.get('phase')=='finished':
        rr=ROOT/'runs/mmg2skill-gpt52-gold31-20260923'/s['fresh_rollout_id']
        b=json.loads((rr/'benchmark_result.json').read_text(encoding='utf-8')); r=json.loads((rr/'result.json').read_text(encoding='utf-8'))
        ar=r.get('agent_result') or {}; ex=ar.get('executor') or {}
        d.update({k:b.get(k) for k in ['execution_ok','error','verifier_error','export_error','protocol_evidence_valid','trajectory_complete','iteration_accounting_complete','skill_exposure_verified','agent_iterations','provider_requests','termination_reason']})
        d['n_skill_invocations']=r.get('n_skill_invocations'); d['skill_context_preload_observed']=ex.get('skill_context_preload_observed');d['skill_context_preload_matches_expected']=ex.get('skill_context_preload_matches_expected');d['verifier_proxy']=ex.get('verifier_proxy');d['max_iterations']=ex.get('max_parent_iterations_per_step')
        d['files']={str(p.relative_to(rr)):p.stat().st_size for p in [rr/'artifacts/workspace-before-verifier.tar.gz',rr/'verifier/test-stdout.txt',rr/'verifier/reward.txt',rr/'trajectory/acp_trajectory.jsonl',rr/'trajectory/llm_trajectory.jsonl',rr/'results.jsonl'] if p.is_file()}
        snapshot=rr/'artifacts/snapshot-export.json';d['snapshot']=json.loads(snapshot.read_text(encoding='utf-8')) if snapshot.exists() else None
        d['verifier_tail']=(rr/'verifier/test-stdout.txt').read_text(encoding='utf-8',errors='replace')[-2000:]
        cp=subprocess.run([sys.executable,str(validator),str(rr),'--json'],capture_output=True,text=True,encoding='utf-8',errors='replace')
        d['validator_exit']=cp.returncode
        if cp.returncode: d['validator_output']=cp.stdout[-5000:]+cp.stderr[-1000:]
        il=rr/'agent/install-stdout.txt';d['openhands_install_source']=il.open(encoding='utf-8',errors='replace').readline().strip()[:200] if il.exists() else None
    slots.append(d)

old28=[s for s in slots if s['task'] not in ['fix-druid-loophole-cve','fix-build-agentops','manufacturing-equipment-maintenance']]
iterations=[s.get('agent_iterations') for s in old28 if s.get('agent_iterations') is not None]
out={'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'cost_scope':'Unique locally saved method provider response IDs including archived invalid response, plus primary per-run LLM trajectory including failed infra attempts; excludes historical original-skill and preflight; not account balance or invoice.', 'phases':dict(collections.Counter(s['phase'] for s in slots)), 'gold':state.get('gold_evaluation'), 'method':totals(method),'fresh':totals(fresh),'fresh_http_status':dict(collections.Counter(x['status'] for x in fresh)), 'combined_recorded_cost_usd':totals(method)['cost_usd']+totals(fresh)['cost_usd'], 'method_duplicate_copies_excluded':duplicates,'original28':{'count':len(old28),'finished':sum(s['phase']=='finished' for s in old28),'validator_ok':sum(s.get('validator_exit')==0 for s in old28),'iterations_min':min(iterations),'iterations_median':statistics.median(iterations),'iterations_max':max(iterations),'iterations_sum':sum(iterations)},'slots':slots,'method_responses':method,'fresh_calls':fresh,'run_calls':runs}
OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in out.items() if k not in ['slots','method_responses','fresh_calls','run_calls']},ensure_ascii=True,indent=2))
