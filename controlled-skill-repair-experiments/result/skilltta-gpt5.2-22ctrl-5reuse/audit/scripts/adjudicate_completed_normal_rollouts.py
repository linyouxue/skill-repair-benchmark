"""Admission gates for provisionally normal model rollouts from actual retained evidence.
Never edits tasks, verifiers, model outputs or rewards; no score-based selection.
"""
import json,gzip,hashlib,re
from pathlib import Path
L=Path(__file__).parent.resolve();S=L/'audit-evidence';O=Path('/Users/king/Documents/Codex/2026-11-24/controlled55-strict-audit');B=Path('/Users/king/Library/Application Support/SkillTTA/controlled-gpt52');a=json.loads((B/'active-execution.json').read_text());original={r['experiment_id']:r for r in json.loads((S/'initial_audit.json').read_text())['entries']};reg=json.loads((O/'rerun_registry.json').read_text());images=json.loads((S/'runtime_image_identity_review.json').read_text())['records'];resource=json.loads((S/'resource_matched_reference_acceptance.json').read_text());out=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def stream(p):
 if not p.exists():p=p.with_suffix(p.suffix+'.gz')
 with (gzip.open(p,'rt') if p.suffix=='.gz' else p.open()) as f:return [json.loads(l) for l in f if l.strip()]
def read(p):return json.loads(p.read_text())
def normalize_config(c):
 fields=['agent','model','environment','sandbox_user','skill_mode','skill_source','include_task_skills','timeout_sec','agent_idle_timeout_sec','concurrency','loop','sandbox_setup_timeout','agent_install_timeout','task_digest','agent_env','scenes']
 return {k:c.get(k) for k in fields}
for row in reg['entries']:
 for link in row['new_attempts']:
  if not link.get('outcome',{}).get('valid'):continue
  id=row['experiment_id'];attempt=link['new_attempt'];old=original[id];logical=Path(link['outcome']['result_file']);root=L/'new-attempts'/row['kind']/id/attempt;j=root/'jobs'/logical.parent.parent.name/logical.parent.name
  if not (root/'AUDIT_PRESERVATION_SHA256.json').exists():continue
  result=read(j/'result.json');meta=read(root/'RUN_RECORD.json');prepared=Path(a['prepared_root'] if row['kind']=='repaired' else a['prepared_controls_root'])/id;cfg=normalize_config(read(j/'config.json'));oldcfg=normalize_config(read(Path(old['formal_result']).parent/'config.json'));diff={k:{'old':oldcfg.get(k),'new':cfg.get(k)} for k in cfg if oldcfg.get(k)!=cfg.get(k)};checks={};checks['same_frozen_execution_config']=not diff;checks['prepared_manifest_unchanged']=meta.get('prepared_sha256')==sha(prepared/'PREPARED_SHA256.json');actualskills={str(p.relative_to(prepared/'skills')):sha(p) for p in (prepared/'skills').rglob('*') if p.is_file()};checks['source_skill_bundle_matches_record']=actualskills==meta.get('source_skill_hashes');checks['specified_model_endpoint']=cfg['model']=='vllm/gpt-5.2@AZUREOPENAI-default' and cfg['agent_env'].get('LLM_BASE_URL')=='https://maas.tatucloud.com/deployer/coding_tatu/v1'
  llm=stream(j/'trajectory/llm_trajectory.jsonl');es=stream(j/'trajectory/acp_trajectory.jsonl');tools={e.get('tool_call_id'):e for e in es if e.get('type')=='tool_call'};messages=[e for e in es if e.get('type')=='agent_message'];final=messages[-1].get('text','') if messages else '';bad=[];unmatched=[]
  for i,x in enumerate(llm):
   resp=x.get('response',{});body=resp.get('body',{})
   if resp.get('status_code')!=200 or body.get('error') or body.get('status') in ['failed','incomplete','cancelled']:bad.append(i)
   for call in body.get('output',[]):
    if call.get('type')!='function_call' or call.get('call_id') in tools:continue
    try:args=json.loads(call.get('arguments','{}'))
    except:args={}
    if call.get('name')=='finish' and args.get('message') and args['message'] in final:continue
    unmatched.append({'request':i,'call_id':call.get('call_id'),'name':call.get('name')})
  checks['recorded_callbacks_no_errors']=bool(llm) and not bad;checks['recorded_high_and_model_consistent']=all(x['request']['body'].get('model')=='gpt-5.2@AZUREOPENAI-default' and x['request']['body'].get('reasoning_effort')=='high' for x in llm);checks['native_call_results_complete']=not unmatched and all(e.get('status') in ['completed','failed'] and e.get('content') for e in tools.values());checks['formal_and_trace_tool_counts_match']=len(tools)==result.get('n_tool_calls');checks['formal_result_error_free']=not any(result.get(k) for k in ['error','verifier_error','export_error','partial_trajectory','api_error_info','suspected_api_error_info','agent_timeout_info','idle_timeout_info','transport_error_info','verifier_timeout_info','sandbox_startup_info']);checks['unique_formal_result_within_selected_rollout']=len(list(j.glob('result.json')))==1
  test=read(j/'verifier/ctrf.json');su=test['results']['summary'];reward=result['rewards']['reward'];expected=round(su['passed']/su['tests'],3) if row['task_id']=='dialogue-parser' else float(su['failed']==0);checks['structured_verifier_completed_and_reward_reproducible']=su['tests']>0 and len(test['results']['tests'])==su['tests'] and expected==reward;checks['resource_matched_official_reference_passed']=resource.get('all_passed',False) and len(resource['records'])==11;expected_test_counts={r['test_summary']['tests'] for r in resource['records'] if r['task_id']==row['task_id']};checks['formal_verifier_check_count_matches_official_reference']=su['tests'] in expected_test_counts and su.get('pending',0)==0 and su.get('other',0)==0
  expected_name_sets=[]
  for reference in resource['records']:
   if reference['task_id']!=row['task_id']:continue
   refctrf=L/'resource-matched-reference'/(reference['task_id']+'__'+reference['actual_runtime_image_id'].split(':')[-1][:12])/'verifier/ctrf.json'
   if refctrf.exists():expected_name_sets.append({t.get('name','').split('::')[-1] for t in read(refctrf)['results']['tests']})
  checks['formal_verifier_check_names_match_official_reference']={t.get('name','').split('::')[-1] for t in test['results']['tests']} in expected_name_sets

  img=[x for x in images if x['id']==id and x['attempt']==attempt and x['rollout']==j.name];checks['actual_initial_image_layers_and_config_match']=bool(img) and all(x.get('same_initial_filesystem_and_functional_config') for x in img)
  # Base-image equality is not proof of actual cgroup limits.
  profile=S/'runtime_profiles'/id/attempt/j.name/'RESOURCE_PROFILE.json';actual_profile=read(profile) if profile.exists() and not getattr(profile.stat(),'st_flags',0)&0x40000000 else None
  if not actual_profile:
   for rec in read(S/'runtime_resource_comparison.json').get('records',[]):
    if rec.get('role')=='actual_model_runtime' and rec.get('id')==id and rec.get('attempt')==attempt:actual_profile=rec;break
  expected_resource=next((r for r in read(S/'reference_expected_resource_profiles.json')['records'] if r['task']==row['task_id']),None);res=(actual_profile or {}).get('resources',{});expected_env=(expected_resource or {}).get('environment',{});cpu=res.get('NanoCpus',0)/1e9 if res.get('NanoCpus') else (res.get('CpuQuota',0)/res.get('CpuPeriod',1) if res.get('CpuQuota',0)>0 else None);memory=expected_env.get('memory_mb',0)*1024*1024
  checks['actual_container_cpu_memory_swap_proven']=bool(actual_profile) and cpu==expected_env.get('cpus') and res.get('Memory')==memory and res.get('MemorySwap')==2*memory

  snaps=[]
  for p in (S/'rerun_artifacts'/id/attempt).rglob('SNAPSHOT.json'):
   if getattr(p.stat(),'st_flags',0)&0x40000000:continue
   d=read(p)
   if p.parents[1].name!=j.name:continue
   if d.get('acp_sha256_at_collection')==sha(j/'trajectory/acp_trajectory.jsonl'):snaps.append((p,d))
  checks['actual_skill_files_match_frozen_bundle']=bool(snaps) and any(d.get('skill_hash_exit')==0 and d.get('skill_hashes')==actualskills for _,d in snaps);checks['snapshot_matches_completed_trajectory']=bool(snaps) and any(d.get('acp_sha256_at_collection')==sha(j/'trajectory/acp_trajectory.jsonl') for _,d in snaps)
  semantic=S/'semantic_attempt_reviews'/id/(attempt+'.json');sem=read(semantic) if semantic.exists() and not getattr(semantic.stat(),'st_flags',0)&0x40000000 else {};checks['write_and_ending_semantics_reviewed']=sem.get('required_artifact_write_and_ending_confirmed',False);checks['semantic_review_matches_final_acp_sha256']=sem.get('trajectory_sha256')==sha(j/'trajectory/acp_trajectory.jsonl');checks['no_unperformed_required_final_action']=not bool(re.search(r'\b(?:I[’\']ll|I will|Next I|Let me|I[’\']m going to|I am going to)\b',final,re.I)) or sem.get('promise_disposition')=='optional_nonrequired';checks['no_independent_verifier_defect']=not sem.get('independent_verifier_defect',False)
  artifact=[]
  for sp,d in snaps:
   for v in d['artifacts']:
    if v['copy_exit']!=0:artifact.append({'source':v['source_path'],'exists':False});continue
    p=Path(v['destination']);paths=[p] if p.is_file() else [x for x in p.rglob('*') if x.is_file()]
    for f in paths:
     r={'source':v['source_path'],'path':str(f),'size':f.stat().st_size,'sha256':sha(f),'exists':True}
     try:
      if f.suffix=='.json':r.update(parser='json.loads',parseable=True);json.loads(f.read_text())
      elif f.suffix=='.py':import ast;ast.parse(f.read_text());r.update(parser='ast.parse',parseable=True)
      elif f.suffix in ['.txt','.java']:f.read_text();r.update(parser='UTF8 decode; domain parser/compiler tests separate',parseable=True)
      elif f.suffix=='.jar':import zipfile;z=zipfile.ZipFile(f);r.update(parser='ZIP CRC',parseable=z.testzip() is None);z.close()
      elif f.suffix=='.mp4':
       proof=S/'video_physical_parsing'/id/(attempt+'.json');v=read(proof) if proof.exists() else {};r.update(parser='ffprobe actual read-only MP4',parseable=v.get('exit_code')==0 and v.get('sha256')==r['sha256'] and bool((v.get('output') or {}).get('streams')),proof=str(proof),probe_format=(v.get('output') or {}).get('format'),probe_streams=[x.get('codec_type') for x in (v.get('output') or {}).get('streams',[])])
      elif f.suffix=='.html':
       from html.parser import HTMLParser
       html=HTMLParser();html.feed(f.read_text());html.close();r.update(parser='Python HTMLParser UTF8 tokenization; browser/task checks separate',parseable=f.stat().st_size>0)
      elif f.suffix=='.js':
       import subprocess,shutil
       node=shutil.which('node');q=subprocess.run([node,'--check',str(f)],capture_output=True,text=True,timeout=30) if node else None;r.update(parser='node --check syntax; browser behavior checked by official verifier',parseable=q is not None and q.returncode==0,syntax_exit=q.returncode if q else None,syntax_stderr=q.stderr if q else 'Node not available')
      elif f.suffix=='.css':
       import sys
       sys.path.insert(0,str(L/'audit-parser-dependencies'))
       import tinycss2
       parsed=tinycss2.parse_stylesheet(f.read_text(),skip_comments=True,skip_whitespace=True);errors=[str(x) for x in parsed if x.type=='error'];r.update(parser='tinycss2 stylesheet tokenizer; visual semantics official verifier',parseable=not errors,css_errors=errors)
      elif f.suffix=='.csv':
       import csv
       with f.open(newline='') as cf:cr=csv.reader(cf);header=next(cr);count=sum(1 for line in cr)
       r.update(parser='csv.reader UTF8 full traversal',parseable=bool(header) and count>0,columns=header,data_rows=count)
      elif f.suffix=='.svg':
       import xml.etree.ElementTree as ET
       rootxml=ET.parse(f);r.update(parser='XML ElementTree',parseable=rootxml.getroot().tag.endswith('svg'))
      elif f.suffix=='.dot':r.update(parser='Prior physical Graphviz validation record',parseable=True,proof=str(S/'physical_artifact_review.json'))
      else:r.update(parseable=False,parser='pending format-specific parser')
     except Exception as ex:r.update(parseable=False,parse_error=repr(ex))
     artifact.append(r)
  requiredreadable=bool(artifact) and all(v.get('exists') and v.get('parseable') for v in artifact)
  if row['task_id']=='flink-query':
   # Program's runtime output is generated DURING verifier, not required at agent final.
   artifact=[v for v in artifact if not (v.get('source')=='/app/workspace/out.txt' and not v.get('exists'))];runtime=list((S/'flink_evidence'/id/attempt/j.name).glob('runtime__out.txt.json'));runtimeproof=[read(p) for p in runtime];requiredreadable=all(v.get('exists') and v.get('parseable') for v in artifact) and bool(runtimeproof) and all(p.get('is_file') and p.get('lines')==p.get('tuple_format_lines') for p in runtimeproof);pom=[read(p) for p in (S/'flink_evidence'/id/attempt/j.name).glob('*__pom.xml.json')];checks['actual_pom_unchanged']=bool(pom) and all(p['pom_unchanged'] for p in pom)
  if not requiredreadable and sem.get('artifact_format_failure_explained'):
   # A physically retained but parser-rejected submitted artifact can be a valid task-format failure.
   # This gate means parser review completed; it never relabels failed parses as successes.
   requiredreadable=bool(artifact) and all(v.get('exists') and v.get('size',0)>0 and v.get('parser') for v in artifact) and any(v.get('parseable') is False for v in artifact)
  checks['required_artifact_actual_readability_reviewed']=requiredreadable
  # Old two cases have isolated unchanged-verifier replay; new cases use actual exec_exit stream.
  replay=next((a.get('verifier_replay') for r in read(S/'audit_report.json')['entries'] for a in r.get('new_attempt_reviews',[]) if a.get('id')==id and a.get('new_attempt')==attempt),None);exits=[]
  eventfile=S/'verifier_exec_events.jsonl'
  if eventfile.exists():
   for line in eventfile.read_text().splitlines():
    try:d=json.loads(line)
    except:continue
    if d.get('id')==id and d.get('attempt')==attempt and d.get('event')=='verifier_exec_die' and d.get('actual_verifier_invocation'):exits.append(d)
  checks['verifier_exit_or_same_output_replay_evidence']=bool(exits) or bool(replay and replay.get('reward_matches_original') and replay.get('verifier_exit_code')==0)
  valid=all(checks.values());out.append({'id':id,'kind':row['kind'],'old_outer_attempt':row['old_attempt'],'outer_attempt':attempt,'rollout':j.name,'effective_attempt_id':attempt+'/'+j.name,'strict_valid_run':valid,'raw_reward':reward,'adopted_reward':reward if valid else None,'checks':checks,'pending_or_failed_gates':[k for k,v in checks.items() if not v],'config_difference':diff,'actual_image_evidence':img,'actual_resource_profile':actual_profile,'expected_resources':expected_resource,'semantic_review':sem,'actual_artifact_parses':artifact,'snapshot_selection':'Only snapshots whose recorded ACP hash equals the completed selected rollout; earlier partial snapshots retained separately, never mixed into a synthetic bundle.','raw_result':str(j/'result.json'),'original_logical_result':str(logical),'acp_path':str(j/'trajectory/acp_trajectory.jsonl'),'llm_path':str(j/'trajectory/llm_trajectory.jsonl'),'verifier_log':str(j/'verifier/test-stdout.txt'),'verifier_log_sha256':sha(j/'verifier/test-stdout.txt'),'failed_checks':[t for t in test['results']['tests'] if t.get('status')=='failed'],'recorded_api_faults':bad,'unmatched_native_calls':unmatched,'verifier_actual_exit_records':exits,'verifier_replay_metadata':replay,'wire_capture_limitation':str(S/'trajectory_capture_contract_review.json'),'classification':'valid_pass' if valid and reward==1 else ('valid_failure' if valid else 'not_admitted'), 'PDDL_confirmation_pending':row['task_id']=='pddl-airport-planning' and not ((S/'pddl_confirmation_review.json').exists() and read(S/'pddl_confirmation_review.json').get('confirmation_complete')),'no_task_output_score_or_verifier_modified':True})
(S/'normal_rollout_adjudication.json').write_text(json.dumps({'entries':out,'strict_valid_normal_runs':sum(r['strict_valid_run'] for r in out),'note':'AI-assisted, not independent human review. Configured model/budgets checked; unlogged wire fields and proxy upstream model identity not independently attested. Exact image proof is INITIAL image only. PDDL confirmation tracked separately before final experiment adoption.'},ensure_ascii=False,indent=2)+'\n');print([(r['id'],r['outer_attempt'],r['strict_valid_run'],r['pending_or_failed_gates']) for r in out])
