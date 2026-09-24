"""Preserve pre-model bootstrap failures and resume frozen methods with launch.sh."""
import hashlib,json,os,shutil,signal,subprocess,time
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parent
METHOD='mmg2skill-opus47-gold15-20260924'
def read(p):return json.loads(p.read_text())
def write(p,x):p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n');tmp.replace(p)
assert read(ROOT/'launch-environment-check.json')['status']=='passed'
stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
archive=ROOT/'recovery-history'/f'{stamp}-launch-environment-recovery'
archive.mkdir(parents=True)
state=read(ROOT/'batch_state.json');queue=read(ROOT/'recovery_queue.json')
affected=[]
for tid in ('fix-build-agentops','flink-query'):
 if queue.get(tid,{}).get('fresh_rollout_id')==f'{tid}-mmg2skill-opus47-r002':continue
 source=ROOT/'runs'/METHOD/f'{tid}-mmg2skill-opus47-r001'
 if not (source/'benchmark_result.json').exists():continue
 r=read(source/'benchmark_result.json')
 if r.get('error')!='Local pinned OpenHands archive required':continue
 assert not r.get('provider_requests') and r.get('cost_usd') in (None,0)
 for trace in (source/'trajectory').glob('*llm*'):
  assert not trace.read_text().strip(),'Cannot retry if any model request exists'
 assert read(ROOT/'generation'/tid/'adapter_result.json')['status']=='complete'
 assert state['tasks'][tid].get('rollout')=='INFRA_ERROR'
 affected.append((tid,source))
assert affected,'No matching pre-model failure to requeue'
pid=int((ROOT/'batch.pid').read_text());cmd=Path(f'/proc/{pid}/cmdline').read_bytes()
assert str(ROOT/'experiment.py').encode() in cmd and b'--worker' not in cmd
os.kill(pid,signal.SIGTERM)
for _ in range(100):
 try:
  if not Path(f'/proc/{pid}/cmdline').read_bytes():break
 except OSError:break
 time.sleep(.1)
else:raise RuntimeError('Controller did not exit')
state=read(ROOT/'batch_state.json');write(archive/'batch_state.json',state);write(archive/'recovery_queue.json',queue)
for tid,source in affected:
 dest=archive/tid;dest.mkdir()
 for name in ('benchmark_result.json','result.json','executor_request.json'):
  if (source/name).exists():shutil.copy2(source/name,dest/name)
 for name,src in [('task_state.json',ROOT/'task_state'/f'{tid}.json'),('worker.log',ROOT/'worker_logs'/f'{tid}.log')]:
  if src.exists():shutil.copy2(src,dest/name)
 hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in list((ROOT/'generation'/tid).rglob('*.response.json'))+list((ROOT/'submission/tasks'/tid/'skills').rglob('*')) if p.is_file()}
 write(dest/'frozen-method-bundle.json',hashes)
 rid=f'{tid}-mmg2skill-opus47-r002';assert not (ROOT/'runs'/METHOD/rid).exists()
 reason='Direct controller resume omitted approved launch.sh environment. Archive/explicit proxy/PYTHONPATH restored and checked without model calls; original attempt failed at runtime install before fresh model. Reuse completed method and bundle.'
 queue[tid]={'fresh_rollout_id':rid,'reason':reason,'archive':str(dest)}
 row=read(ROOT/'task_state'/f'{tid}.json');row.update(phase='pending',rollout='NOT_RUN',fresh_rollout_id=rid,recovery_reason=reason);row.pop('result_path',None)
 write(ROOT/'task_state'/f'{tid}.json',row);state['tasks'][tid]=row
write(ROOT/'recovery_queue.json',queue);write(ROOT/'batch_state.json',state)
write(ROOT/'dispatch_holds.json',{})
write(archive/'recovery.json',{'affected':[t for t,_ in affected],'new_model_calls':0,'original_runs_unchanged':True,'approved_launcher':str(ROOT/'launch.sh')})
subprocess.run(['bash',str(ROOT/'launch.sh'),'--resume-queue'],check=True)
print(json.dumps({'archive':str(archive),'requeued':[t for t,_ in affected]}))
