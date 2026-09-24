"""Approved single-round MMG2Skill no-tutorial SkillsBench adaptation."""
from __future__ import annotations
import argparse, asyncio, dataclasses, fcntl, hashlib, importlib.util, json, os, re, shutil, subprocess, sys, time, traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parent
PROJECT=ROOT.parents[1]
SOURCE=ROOT/'source/MMG2Skill_SkillsBench25_diagnosis'
CF=PROJECT/'causalflow_runs/opus47-gold15-20260922'
METHOD='mmg2skill-opus47-gold15-20260924'
MODEL='anthropic/claude-opus-4.7'
sys.path[:0]=[str(SOURCE),str(CF/'source'),str(CF/'.deps')]
def read(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def now(): return datetime.now(timezone.utc).isoformat()
def write(p,obj):
    p=Path(p); p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_suffix(p.suffix+'.tmp'); tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); tmp.replace(p)
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path); mod=importlib.util.module_from_spec(spec); sys.modules[name]=mod; spec.loader.exec_module(mod); return mod
def cf_module():
    cf=load('_cf_runtime',CF/'experiment.py')
    cf.ROOT=ROOT; cf.METHOD=METHOD; cf.MODEL=MODEL
    return cf
def progress(tid,phase,**kwargs):
    p=ROOT/'task_state'/f'{tid}.json'; row=read(p) if p.exists() else {'task_id':tid}
    row.update(phase=phase,updated_at=now(),worker_pid=os.getpid(),**kwargs); write(p,row)
    print(now(),tid,phase,flush=True)

class ProviderFailure(BaseException):
    """Must not be silently swallowed into success by upstream fallback paths."""

class RecordedClient:
    def __init__(self,directory):
        from openai import OpenAI
        self.directory=Path(directory); self.index=0
        self.client=OpenAI(api_key=os.environ['OPENROUTER_API_KEY'],base_url='https://openrouter.ai/api/v1',timeout=600,max_retries=0)
    def chat(self,messages,max_tokens,temperature=None):
        self.index+=1
        path=self.directory/f'call-{self.index:03d}'
        request={'model':MODEL,'messages':messages,'max_tokens':max_tokens}
        if temperature is not None: request['temperature']=temperature
        req=path.with_suffix('.request.json'); response=path.with_suffix('.response.json'); pending=path.with_suffix('.pending.json')
        if req.exists():
            if read(req)!=request: raise ProviderFailure('Refusing changed checkpoint request')
        else: write(req,request)
        if response.exists(): reply=read(response)
        else:
            if pending.exists(): raise ProviderFailure('Uncertain prior provider request; manual reconciliation required')
            write(pending,{'started_at':now()})
            try:
                reply=self.client.chat.completions.create(**request).model_dump(exclude_none=True)
                write(response,reply)
            except Exception as exc:
                write(path.with_suffix('.error.json'),{'type':type(exc).__name__,'error':str(exc),'time':now()})
                raise ProviderFailure(str(exc)) from exc
        choice=reply['choices'][0]
        content=choice['message'].get('content')
        if not content or choice.get('finish_reason')!='stop':
            raise ProviderFailure('Incomplete provider response preserved; no automatic second attempt')
        return content

def original_skills(task):
    import yaml
    from anything2skill.parser.data_types import Skill, Skills
    result=[]; mapping={}
    for rel in task['skill_files']:
        text=(Path(task['original_bundle'])/rel).read_text(encoding='utf-8')
        m=re.match(r'^---\s*\n(.*?)\n---[^\S\n]*\n',text,re.S)
        metadata=yaml.safe_load(m.group(1)) if m else {}
        metadata=metadata or {}
        name=str(metadata.get('name') or Path(rel).parent.name)
        assert name not in mapping, f'Duplicate Skill name: {name}'
        mapping[name]=(rel,text,m.end() if m else 0)
        result.append(Skill(name=name,description=str(metadata.get('description','')),content=text[m.end():].strip() if m else text.strip()))
    return Skills(task_id=task['task_id'],instruction='',skills=result),mapping

def overlay_bundle(task,refined,mapping):
    names=[s.name for s in refined.skills]
    assert len(set(names))==len(names) and set(names)==set(mapping), 'Refiner must preserve exact existing Skill identities'
    dest=ROOT/'submission/tasks'/task['task_id']/'skills'
    if not dest.exists(): shutil.copytree(task['original_bundle'],dest)
    changed=[]
    import yaml
    for skill in refined.skills:
        rel,text,offset=mapping[skill.name]
        before=next(s for s in original_skills(task)[0].skills if s.name==skill.name)
        if skill.content.strip()==before.content.strip() and skill.description.strip()==before.description.strip(): continue
        # Keep unrelated frontmatter fields and all supporting files. Only model-returned
        # body/description may change; names/paths are never accepted as new paths.
        if offset:
            front=text[:offset]
            if skill.description.strip()!=before.description.strip():
                metadata=yaml.safe_load(front.split('---',2)[1]); metadata['description']=skill.description
                front='---\n'+yaml.safe_dump(metadata,allow_unicode=True,sort_keys=False)+'---\n'
            content=front+'\n'+skill.content.rstrip()+'\n'
        else: content=skill.content.rstrip()+'\n'
        (dest/rel).write_text(content,encoding='utf-8'); changed.append(rel)
    source=Path(task['original_bundle'])
    assert {p.relative_to(source) for p in source.rglob('*') if p.is_file()}=={p.relative_to(dest) for p in dest.rglob('*') if p.is_file()}
    assert all(p.read_bytes()==(dest/p.relative_to(source)).read_bytes() for p in source.rglob('*') if p.is_file() and p.name!='SKILL.md')
    return changed

def repair(task):
    from anything2skill.reviser.analyzer import ReviserAnalyzer
    from anything2skill.reviser.refiner import ReviserRefiner
    from anything2skill.reviser.data_types import RootCauseAnalysis
    adapter=load('_packaged_trace',SOURCE/'experiments/skillsbench_cf25/run_diagnosis.py')
    tid=task['task_id']; inputs=ROOT/'inputs'/tid; out=ROOT/'generation'/tid
    if (out/'adapter_result.json').exists(): return
    instruction=(inputs/'instruction.txt').read_text(encoding='utf-8')
    kit=adapter.TextObservationKit()
    if (out/'analysis.json').exists(): rc=RootCauseAnalysis(**read(out/'analysis.json'))
    else:
        progress(tid,'analysis')
        analyzer=ReviserAnalyzer(RecordedClient(out/'analysis_calls'),kit,chunk_size=15,max_tokens=32768,temperature=None,response_char_limit=32768,rolling_summary_char_limit=32768)
        rc=analyzer.analyze(str(inputs/'traj.jsonl'),instruction,str(inputs),audit_dir=str(out))
        assert rc.raw_xml and rc.outcome_assessment in {'likely_success','uncertain','likely_failure'}, 'Invalid Analyzer result; raw response retained'
        write(out/'analysis.json',dataclasses.asdict(rc))
        (out/'root_cause.xml').write_text(rc.raw_xml,encoding='utf-8')
    progress(tid,'refine')
    skills,mapping=original_skills(task); skills.instruction=instruction
    refiner=ReviserRefiner(RecordedClient(out/'refine_calls'),kit,max_tokens=32768,temperature=None,include_tutorial_in_refine=False)
    refined=refiner.refine(skills,rc,None,instruction,history=[])
    assert refined is not skills, 'Unparseable Refiner response; upstream fallback is not a completed repair'
    # Native extractor splits body H1s and fenced Python comments into fake skills.
    # Reparse the exact same paid response using its explicit name/description envelopes.
    from runtime_fixes import parse_existing_skills
    response=read(out/'refine_calls/call-001.response.json')['choices'][0]['message']['content']
    refined.skills=parse_existing_skills(response,mapping)
    changed=overlay_bundle(task,refined,mapping)
    # Upstream Analyzer localizes trajectory turns, not Skill files. Do not invent
    # Skill locations from Gold or changed files; empty locations get no credit.
    diagnoses=[{'prediction_id':f'MMG-{i:03d}','description':f"{issue.get('cause','')}\nEvidence: {issue.get('evidence','')}\nTrajectory location: {issue.get('where','')}",'locations':[]} for i,issue in enumerate(rc.issues,1)]
    row={'task_id':tid,'diagnoses':diagnoses,'repaired_bundle':f'tasks/{tid}/skills'}
    write(out/'adapter_result.json',{'status':'complete','submission_row':row,'updated_files':changed,'source_run':task['run_path'],'location_policy':'native trajectory locations retained in description; no inferred Skill location','include_tutorial_in_refine':False})

async def fresh(task):
    tid=task['task_id']; cf=cf_module()
    if tid=='reserves-at-risk-calc':
        from runtime_fixes import ensure_reserves_initial_image
        progress(tid,'environment_preflight')
        proof=ensure_reserves_initial_image(ROOT,cf)
        original_read=cf.read
        cf.read=lambda p: proof if Path(p)==ROOT/'infra-cache/reserves-at-risk-calc/prebuilt-image.json' else original_read(p)
    old=cf.fresh_runtime(tid)
    cwd=Path('/home/linyuanjing/.cache/skillrepair')/METHOD/tid; cwd.mkdir(parents=True,exist_ok=True); os.chdir(cwd)
    recovery=read(ROOT/'recovery_queue.json') if (ROOT/'recovery_queue.json').exists() else {}
    rid=recovery.get(tid,{}).get('fresh_rollout_id',f'{tid}-mmg2skill-opus47-r001')
    progress(tid,'fresh_rollout',fresh_rollout_id=rid)
    import benchflow.agents.install as agent_install
    prepare_cached=agent_install.prepare_openhands_runtime_cache
    async def require_cached_runtime(env):
        assert os.environ.get('BENCHMARK_EXECUTOR_OPENHANDS_RUNTIME_ARCHIVE'), 'Local pinned OpenHands archive required'
        metadata=await prepare_cached(env)
        assert metadata, 'Local pinned OpenHands runtime was not activated'
        write(ROOT/'runs'/METHOD/rid/'local-openhands-runtime.json',{'archive':os.environ['BENCHMARK_EXECUTOR_OPENHANDS_RUNTIME_ARCHIVE'],'metadata':metadata,'activated_at':now()})
        return metadata
    agent_install.prepare_openhands_runtime_cache=require_cached_runtime
    import benchflow.rollout_planes as planes
    harden=planes.DefaultRolloutPlanes.harden_before_verify
    async def archive_before_verify(self,env,task,sandbox_user,*,workspace):
        dest=ROOT/'runs'/METHOD/rid/'artifacts/workspace-before-verifier.tar.gz'
        dest.parent.mkdir(parents=True,exist_ok=True)
        from runtime_fixes import snapshot_command
        # Packaging has its own watchdog; the original verifier timeout is unchanged.
        packed=await env.exec(snapshot_command(workspace),user='root',timeout_sec=1800)
        write(dest.parent/'snapshot-export.json',{'workspace':str(workspace),'return_code':packed.return_code,'stderr':packed.stderr,'stdout':packed.stdout})
        await env.download_file('/tmp/mmg-before-verifier.tar.gz',dest)
        assert packed.return_code in (0,1), 'Real artifact snapshot export failed; partial archive preserved'
        assert dest.is_file() and dest.stat().st_size>0
        await harden(self,env,task,sandbox_user,workspace=workspace)
        if tid=='fix-build-agentops':
            from agentops_verifier_dependencies import prepare
            await prepare(env,dest.parent)
    if tid!='flink-query': planes.DefaultRolloutPlanes.harden_before_verify=archive_before_verify
    old.base.install_cross_process_docker_start_lock(); old.base.DockerSandbox.set_build_concurrency(1)
    os.environ['LLM_MAX_OUTPUT_TOKENS']='32768'; os.environ.pop('LLM_REASONING_EFFORT',None)
    executor=old.original_executor(tasks_root=read(ROOT/'manifest.json')['tasks_root'],jobs_root=ROOT/'runs',model='openrouter/'+MODEL,reasoning_effort=None,protocol='skillrepair-v1',experimental_text_only_retry_limit=1)
    result=await executor.run_async(task_id=tid,method_id=METHOD,stage='mmg2skill-validation',rollout_id=rid,condition='method-skill',skill_bundle=ROOT/'submission/tasks'/tid/'skills')
    write(ROOT/'worker_results'/f'{tid}.json',result.to_dict())
    p=ROOT/'runs'/METHOD/rid/'benchmark_result.json'; r=read(p)
    valid=r.get('execution_ok') is True and r.get('task_passed') is not None and not any(r.get(k) for k in ('error','verifier_error','export_error'))
    progress(tid,'finished',rollout=('PASS' if r['task_passed'] else 'FAIL') if valid else 'INFRA_ERROR',result_path=str(p))

def worker(tid):
    from runtime_environment import ensure_runtime_environment
    ensure_runtime_environment()
    task=next(t for t in read(ROOT/'manifest.json')['tasks'] if t['task_id']==tid)
    try:
        cf_module().ensure_openrouter_key()
        repair(task)
        recovery=read(ROOT/'recovery_queue.json') if (ROOT/'recovery_queue.json').exists() else {}
        rp=ROOT/'runs'/METHOD/recovery.get(tid,{}).get('fresh_rollout_id',f'{tid}-mmg2skill-opus47-r001')
        assert not rp.exists(), 'Existing fresh attempt must be reconciled, never restarted automatically'
        asyncio.run(fresh(task))
    except (Exception,ProviderFailure) as exc:
        progress(tid,'error',rollout='NOT_RUN',error=f'{type(exc).__name__}: {exc}'); traceback.print_exc(); raise SystemExit(1)

def preflight(probe=False):
    from anything2skill.reviser.refiner import ReviserRefiner
    from anything2skill.reviser.data_types import RootCauseAnalysis
    from anything2skill.parser.data_types import Skills,Skill
    from types import SimpleNamespace
    # Regression: tutorial=None must refine when disabled, and reject when required.
    class Toy:
        def chat(self,**kwargs): return '# test\n> test description\n\nKeep original text.\n'
    s=Skills('toy','toy',[Skill('test','test description','Original')])
    r=ReviserRefiner(Toy(),SimpleNamespace(reviser_guidance=''),include_tutorial_in_refine=False).refine(s,RootCauseAnalysis(),None,'toy')
    assert r is not s and r.skills[0].name=='test'
    try: ReviserRefiner(Toy(),SimpleNamespace(reviser_guidance=''),include_tutorial_in_refine=True).refine(s,RootCauseAnalysis(),None,'toy')
    except ValueError: pass
    else: raise AssertionError('Missing required tutorial accepted')
    cf=cf_module(); old=cf.previous().runtime()
    manifest=read(ROOT/'manifest.json'); specs=[]
    digest=load('_mmg_frozen_inputs',ROOT/'prepare.py').digest
    for task in manifest['tasks']:
        assert digest(Path(task['original_bundle']))==task['original_bundle_sha256']
        original_skills(task)
        spec=old.base.parse_task_spec(Path(manifest['tasks_root'])/task['task_id'])
        specs.append({'task_id':task['task_id'],'memory_mb':spec.memory_mb,'cpus':spec.cpus,'exclusive':spec.exclusive})
    for p in (os.environ['BENCHMARK_EXECUTOR_OPENHANDS_RUNTIME_ARCHIVE'],old.infra_support.PYTHON_ARCHIVE,old.infra_support.UV_ARCHIVE,old.infra_support.CRYPTO_WHEEL): assert Path(p).is_file(), str(p)
    write(ROOT/'preflight.json',{'time':now(),'tasks':specs,'bundle_matches':15,'no_tutorial_regression':'passed','runtime_archives':'present','model_probe':False})
    if probe:
        cf.ensure_openrouter_key()
        text=RecordedClient(ROOT/'preflight-model').chat([{'role':'user','content':'Reply only OK. This is an API connectivity probe.'}],128)
        p=read(ROOT/'preflight.json');p['model_probe']=bool(text); write(ROOT/'preflight.json',p)
    print('Preflight complete',flush=True)

def external_worker_specs():
    result=[]
    for batch in ROOT.parent.iterdir():
        if batch==ROOT or not (batch/'batch_state.json').exists():continue
        state=read(batch/'batch_state.json')
        specs={s['task_id']:s for s in read(batch/'preflight.json')['tasks']}
        for tid,row in state['tasks'].items():
            pid=row.get('worker_pid')
            try:cmd=Path(f'/proc/{pid}/cmdline').read_bytes()
            except OSError:continue
            if str(batch/'experiment.py').encode() in cmd and b'--worker' in cmd and tid.encode() in cmd:
                result.append(specs[tid])
    return result

async def controller(resume_queue=False):
    from runtime_environment import ensure_runtime_environment
    ensure_runtime_environment()
    lock=(ROOT/'controller.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    assert read(ROOT/'preflight.json')['model_probe']
    cf_module().ensure_openrouter_key()
    manifest=read(ROOT/'manifest.json');specs={s['task_id']:s for s in read(ROOT/'preflight.json')['tasks']}
    assert len(manifest['tasks'])==15 and 'fix-druid-loophole-cve' not in specs
    if (ROOT/'batch_state.json').exists():
        assert resume_queue,'Use explicit recovery'
        state=read(ROOT/'batch_state.json');state['resumed_at']=now()
    else:state={'status':'running','started_at':now(),'gold_evaluation':'waiting_all_workers','tasks':{t['task_id']:{'phase':'pending'} for t in manifest['tasks']}}
    live={};logs={}
    class AdoptedWorker:
        def __init__(self,pid,tid):self.pid=pid;self.tid=tid
        def poll(self):
            try:cmd=Path(f'/proc/{self.pid}/cmdline').read_bytes()
            except OSError:return 0
            return None if str(ROOT/'experiment.py').encode() in cmd and b'--worker' in cmd and self.tid.encode() in cmd else 0
    if resume_queue:
        recovery=read(ROOT/'recovery_queue.json')
        for tid,row in state['tasks'].items():
            pid=row.get('worker_pid')
            if pid and AdoptedWorker(pid,tid).poll() is None:live[tid]=AdoptedWorker(pid,tid)
            elif tid in recovery and not (row.get('phase')=='finished' and row.get('rollout') in ('PASS','FAIL')):
                row.update(phase='pending',recovery_reason=recovery[tid]['reason'])
    pending=sorted([t for t in manifest['tasks'] if t['task_id'] not in live and state['tasks'][t['task_id']]['phase'] in ('pending','blocked_disk')],key=lambda t:(specs[t['task_id']]['exclusive'],specs[t['task_id']]['memory_mb'],t['task_id']))
    write(ROOT/'batch.pid',os.getpid())
    while pending or live:
        for tid,proc in list(live.items()):
            p=ROOT/'task_state'/f'{tid}.json'
            if p.exists():state['tasks'][tid].update(read(p))
            if proc.poll() is not None:
                if state['tasks'][tid].get('phase') not in ('finished','error'):state['tasks'][tid].update(phase='error',rollout='NOT_RUN',error='Worker exited')
                if tid in logs:logs.pop(tid).close()
                live.pop(tid)
        # Shared dispatch lock protects simultaneous MMG launch decisions. This batch
        # counts genuine /proc workers in the older GPT batch, including its recoveries.
        with Path('/tmp/mmg2skill-resource-dispatch.lock').open('a') as dispatch:
            fcntl.flock(dispatch,fcntl.LOCK_EX)
            external=external_worker_specs();occupied=external+[specs[t] for t in live]
            holds=read(ROOT/'dispatch_holds.json') if (ROOT/'dispatch_holds.json').exists() else {}
            eligible=[t for t in pending if t['task_id'] not in holds]
            limits=read(ROOT/'dispatch_limits.json') if (ROOT/'dispatch_limits.json').exists() else {}
            local_limit=min(3,limits.get('max_local_workers',3))
            if eligible and len(occupied)<local_limit:
                task=eligible[0];tid=task['task_id'];spec=specs[tid]
                total_mem=int(re.search(r'MemTotal:\s+(\d+)',Path('/proc/meminfo').read_text()).group(1))//1024
                fits=spec['memory_mb']<=min(total_mem,11264) and spec['memory_mb']+sum(s['memory_mb'] for s in occupied)<=11264
                exclusive_ok=not occupied or (not spec['exclusive'] and not any(s['exclusive'] for s in occupied))
                if fits and exclusive_ok and shutil.disk_usage('/mnt/c').free>=15*1024**3:
                    path=ROOT/'worker_logs'/f'{tid}.log';path.parent.mkdir(exist_ok=True)
                    log=path.open('ab',buffering=0)
                    proc=subprocess.Popen([sys.executable,str(ROOT/'experiment.py'),'--worker',tid],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,start_new_session=True)
                    live[tid]=proc;logs[tid]=log;pending.remove(task);state['tasks'][tid].update(phase='starting',worker_pid=proc.pid)
            state['updated_at']=now();write(ROOT/'batch_state.json',state)
        if pending or live:await asyncio.sleep(5)
    valid=all(r.get('phase')=='finished' and r.get('rollout') in ('PASS','FAIL') for r in state['tasks'].values())
    state.update(status='ready_for_execution_audit' if valid else 'blocked_incomplete_validation',gold_evaluation='awaiting_execution_audit' if valid else 'waiting_valid_execution',finished_at=now())
    write(ROOT/'batch_state.json',state)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--worker');parser.add_argument('--preflight',action='store_true');parser.add_argument('--probe',action='store_true');parser.add_argument('--run',action='store_true');parser.add_argument('--resume-queue',action='store_true');args=parser.parse_args()
    if args.worker:worker(args.worker)
    elif args.preflight:preflight(args.probe)
    elif args.run or args.resume_queue:asyncio.run(controller(args.resume_queue))
    else:parser.error('select --preflight, --run or --worker')
