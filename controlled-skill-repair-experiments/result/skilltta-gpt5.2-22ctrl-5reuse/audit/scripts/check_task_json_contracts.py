"""Read-only strict JSON syntax and instruction field-shape checks, not new scoring."""
import json,hashlib,math
from pathlib import Path
L=Path(__file__).parent.resolve();S=L/'audit-evidence';out=[]
def strict_parse(p):
 duplicates=[]
 def pairs(xs):
  d={}
  for k,v in xs:
   if k in d:duplicates.append(k)
   d[k]=v
  return d
 def constant(v):raise ValueError('Non-standard JSON constant '+v)
 return json.loads(p.read_text(),parse_constant=constant,object_pairs_hook=pairs),duplicates
for root in (S/'rerun_artifacts').iterdir():
 if not root.is_dir():continue
 for attempt in root.iterdir():
  if not attempt.is_dir():continue
  for p in attempt.rglob('*.json'):
   if p.name=='SNAPSHOT.json' or getattr(p.stat(),'st_flags',0)&0x40000000:continue
   if p.name not in ['dialogue.json','answers.json','compression_report.json','q01.json','q02.json','q03.json','q04.json','q05.json']:continue
   d={'id':root.name,'attempt':attempt.name,'path':str(p),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'schema_findings':[]};findings=d['schema_findings']
   try:
    v,dup=strict_parse(p);d.update(strict_json_parseable=True,duplicate_keys=dup,top_type=type(v).__name__)
    if dup:findings.append('Duplicate object keys are ambiguous to JSON consumers')
    def require(obj,keys,label):
     if not isinstance(obj,dict):findings.append(label+' must be object');return
     missing=[k for k in keys if k not in obj]
     if missing:findings.append(label+' missing keys: '+','.join(missing))
    def records(keys,key):
     if not isinstance(v,list):findings.append('top-level must be array');return
     for i,item in enumerate(v):require(item,keys,'record'+str(i))
     ids=[item.get(key) for item in v if isinstance(item,dict)]
     if ids and all(isinstance(x,str) for x in ids) and ids!=sorted(ids):findings.append('Array must be sorted by '+key)
    if p.name=='dialogue.json':
     require(v,['nodes','edges'],'graph')
     if isinstance(v,dict):
      for group,keys in [('nodes',['id','text','speaker','type']),('edges',['from','to','text'])]:
       xs=v.get(group)
       if not isinstance(xs,list):findings.append(group+' must be array');continue
       for i,x in enumerate(xs):require(x,keys,group+str(i))
    elif p.name=='answers.json':
     require(v,['q1_answer','q2_answer','q3_answer','q4_answer'],'answers')
     if isinstance(v,dict):
      for k in ['q1_answer','q2_answer']:
       if k in v and (isinstance(v[k],bool) or not isinstance(v[k],(int,float))):findings.append(k+' must be numeric')
      for k,n in [('q3_answer',5),('q4_answer',3)]:
       if k in v and (not isinstance(v[k],list) or len(v[k])!=n or not all(isinstance(x,str) for x in v[k])):findings.append(k+' must contain '+str(n)+' strings')
    elif p.name=='q01.json':
     require(v,['ramp_rate_limit_c_per_s','violating_runs','max_ramp_by_run'],'q01')
     if isinstance(v,dict):
      if not isinstance(v.get('violating_runs'),list):findings.append('violating_runs must be array')
      runs=v.get('max_ramp_by_run')
      if isinstance(runs,dict):
       for run,x in runs.items():require(x,['tc_id','max_preheat_ramp_c_per_s'],run)
      else:findings.append('max_ramp_by_run must be object')
    elif p.name=='q02.json':records(['run_id','tc_id','tal_s','required_min_tal_s','required_max_tal_s','status'],'run_id')
    elif p.name=='q03.json':
     require(v,['failing_runs','min_peak_by_run'],'q03')
     if isinstance(v,dict):
      runs=v.get('min_peak_by_run')
      if isinstance(runs,dict):
       for run,x in runs.items():require(x,['tc_id','peak_temp_c','required_min_peak_c'],run)
      else:findings.append('min_peak_by_run must be object')
    elif p.name=='q04.json':records(['run_id','required_min_speed_cm_min','actual_speed_cm_min','meets'],'run_id')
    elif p.name=='q05.json':records(['board_family','best_run_id','runner_up_run_ids'],'board_family')
    elif p.name=='compression_report.json':
     require(v,['original_duration_seconds','compressed_duration_seconds','removed_duration_seconds','compression_percentage','segments_removed'],'video report')
     if isinstance(v,dict):
      for k in ['original_duration_seconds','compressed_duration_seconds','removed_duration_seconds','compression_percentage']:
       if k in v and (isinstance(v[k],bool) or not isinstance(v[k],(int,float))):findings.append(k+' must be numeric')
      seg=v.get('segments_removed')
      if not isinstance(seg,list):findings.append('segments_removed must be array')
      else:
       for i,x in enumerate(seg):require(x,['start','end','duration'],'segment'+str(i))
    d['required_field_shape_matches_instruction']=not findings
   except Exception as ex:d.update(strict_json_parseable=False,parse_error=repr(ex),required_field_shape_matches_instruction=False)
   out.append(d)
(S/'task_json_contract_review.json').write_text(json.dumps({'entries':out,'strict_parser':'json.loads rejects NaN/Infinity; duplicates separately flagged; no output rewrites','note':'Instruction field-shape checks, not replacement verifier/scoring. Failed content/shape does not automatically mean invalid infrastructure. Does not claim numeric/semantic correctness from mere schema match; compare original official tests and instruction ambiguities separately.'},ensure_ascii=False,indent=2)+'\n');print('JSON artifacts checked',len(out),'syntax failures',sum(not r['strict_json_parseable'] for r in out),'field findings',[(r['id'],r['attempt'],Path(r['path']).name,r['schema_findings']) for r in out if r.get('schema_findings')])
