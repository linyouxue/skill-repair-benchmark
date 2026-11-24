"""Complete invalid WML GPT52 conditions with frozen candidates and versioned verifier."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
import difflib,hashlib,importlib.util,json,os,shutil,subprocess,sys

BASE=Path(__file__).resolve().parent
OUT=BASE/'wml-gpt52-completion-20261124'
OLD=BASE/'controlled55-strict-audit-20261123'
LOCAL=Path('/private/tmp/controlled55-strict-20261123')
DATA=Path('/Users/king/Downloads/03_论文科研/skill-repair-controlled-datasets-20261020')
PY='/Users/king/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3'
spec=importlib.util.spec_from_file_location('safe',LOCAL/'method/safe_controlled_eval.py')
safe=importlib.util.module_from_spec(spec);spec.loader.exec_module(safe)
def load(p):return json.loads(p.read_text())
def save(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def stamp():return datetime.now(timezone.utc).isoformat()
IDS=['single-manufacturing-equipment-maintenance-RI-002','location-data-to-d3','single-manufacturing-equipment-maintenance-RI-001__condition_baseline','flink-query__all_faults','data-to-d3__full_gold','data-to-d3__original']

def prepare(r):
    dest=OUT/'prepared'/r['experiment_id']
    if dest.exists():return dest
    command=[PY,str(DATA/'tools/runner.py')]
    if r['group']=='repairs':command+=['prepare-eval','--trial',r['experiment_id'],'--candidate',str(LOCAL/'recovered-candidates'/r['experiment_id'])]
    else:
        condition=r['experiment_id'].rsplit('__',1)[1]
        command+=['control','--task',r['task_id'],'--condition',condition]
        if condition=='condition_baseline':command+=['--trial',r['experiment_id'].rsplit('__',1)[0]]
    subprocess.run(command+['--out',str(dest)],check=True,capture_output=True)
    if r['task_id']=='data-to-d3':
        p=dest/'task/verifier/test_outputs.py';before=p.read_text();assert before.count('legend.first.inner_text().lower()')==1
        after=before.replace('legend.first.inner_text().lower()','(legend.first.text_content() or "").lower()');p.write_text(after)
        record=load(dest/'RUN.json');record['authorized_verifier_compatibility_change']={'version':'d3-svg-text-content-v1-20261124','authorization':'User explicitly approved on 20261124','file':'task/verifier/test_outputs.py','before_sha256':hashlib.sha256(before.encode()).hexdigest(),'after_sha256':sha(p),'change':'SVG-compatible text extraction only; assertions, task/Gold/inputs/reward unchanged','scoring_formula_unchanged':True}
        save(dest/'RUN.json',record);patch=OUT/'verifier-compatibility'/r['experiment_id']/'test_outputs.py.diff';patch.parent.mkdir(parents=True,exist_ok=True);patch.write_text(''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='official/test_outputs.py',tofile='d3-svg-text-content-v1/test_outputs.py')))
        save(dest/'PREPARED_SHA256.json',safe.tree_hashes(dest)|{})
        # Manifest excludes itself, just like official prepare().
        m=safe.tree_hashes(dest);m.pop('PREPARED_SHA256.json',None);save(dest/'PREPARED_SHA256.json',m)
    return dest

def qualify(task,image):
    out=OUT/'environment-acceptance'/task
    if (out/'acceptance.json').exists():assert load(out/'acceptance.json')['passed'];return
    ref=LOCAL/'reference'/task;stage=OUT/'reference-staging'/task
    shutil.copytree(ref/'verifier',stage/'verifier',dirs_exist_ok=True)
    oracle=ref/('oracle-dependency-offline' if task=='data-to-d3' else 'oracle')
    if task=='data-to-d3':
        p=stage/'verifier/test_outputs.py';s=p.read_text();assert s.count('legend.first.inner_text().lower()')==1;p.write_text(s.replace('legend.first.inner_text().lower()','(legend.first.text_content() or "").lower()'))
    out.mkdir(parents=True,exist_ok=True)
    inspect=subprocess.run(['docker','image','inspect',image,'--format','{{json .}}'],capture_output=True,text=True,check=True);identity=json.loads(inspect.stdout)
    command=['docker','run','--rm','--name','wml-completion-ref-'+task,'--network','none','--hostname','localhost']
    for source,target in [(stage/'verifier','/verifier'),(oracle,'/oracle'),(ref/'skills','/skills'),(out,'/logs/verifier')]:command+=['--mount',f'type=bind,src={source.resolve()},dst={target}'+(',readonly' if target!='/logs/verifier' else '')]
    command+=['--entrypoint','bash',image,'-lc','ln -s /verifier /tests; bash /oracle/solve.sh && bash /verifier/test.sh']
    log=out/'reference.log'
    with log.open('w') as f:q=subprocess.run(command,stdout=f,stderr=subprocess.STDOUT,timeout=1000)
    reward=float((out/'reward.txt').read_text());ctrf=load(out/'ctrf.json');passed=q.returncode==0 and reward==1
    save(out/'acceptance.json',{'task_id':task,'command':command,'exit_code':q.returncode,'reward':reward,'passed':passed,'image':image,'image_id':identity['Id'],'architecture':identity['Architecture'],'log':str(log),'log_sha256':sha(log),'ctrf_summary':ctrf['results']['summary'],'verifier_files':safe.tree_hashes(stage/'verifier')})
    assert passed,task
    print('REFERENCE_PASS',task,flush=True)

def main():
    OUT.mkdir(exist_ok=True);rows={r['experiment_id']:r for r in load(OLD/'AUDIT_RUNS.json')};plans=[]
    for name in IDS:prepare(rows[name])
    environments={e['task_id']:e for e in load(OLD/'environment_audit.json')}
    with ThreadPoolExecutor(max_workers=2) as pool:
        for f in as_completed([pool.submit(qualify,t,environments[t]['image']) for t in ['manufacturing-equipment-maintenance','data-to-d3','flink-query']]):f.result()
    keys={}
    for raw in (BASE.parent/'opus47-wml.env').read_text().splitlines():
        raw=raw.strip().removeprefix('export ')
        if '=' in raw:
            k,v=raw.split('=',1)
            if k.strip() in ['API_KEY','WML_API_KEY']:keys[k.strip()]=v.strip().strip('"').strip("'")
    key=keys.get('API_KEY',keys.get('WML_API_KEY'));assert key
    env=dict(os.environ,PYTHONPATH=str(LOCAL/'runtime'),TATUMASS_API_KEY=key,TATUMASS_BASE_URL='https://maas.tatucloud.com/deployer/coding_tatu/v1',NO_PROXY='127.0.0.1,localhost,host.docker.internal',no_proxy='127.0.0.1,localhost,host.docker.internal')
    # Copy immutable observational hook source so later editing cannot change launched attempts.
    hook=OUT/'bench_with_retention.py';shutil.copy2(OLD/'bench_with_retention.py',hook)
    export=OUT.parent/'export_controlled55_confirmation_artifacts.py';assert export.is_file()
    shim=OUT/'bench.sh';shim.write_text('#!/bin/sh\nset -eu\nexport PATH="'+str(LOCAL/'method/runtime-bin')+':$PATH"\nexec '+PY+' '+str(hook)+' "$@" --agent-env GIT_CONFIG_COUNT=1 --agent-env GIT_CONFIG_KEY_0=url.git://host.docker.internal:9418/extensions-git.insteadOf --agent-env GIT_CONFIG_VALUE_0=https://github.com/OpenHands/extensions\n');shim.chmod(0o755)
    for name in IDS:
        r=rows[name];old=Path(r['original_result_path']).parents[3];record=load(old/'RUN_RECORD.json');pre=load(old/'EXECUTION_PREFLIGHT.json');prepared=OUT/'prepared'/name
        assert safe.bundle_manifest(prepared/'skills')==pre['skill_bundle']
        prior=[Path(p) for p in r['confirmation_attempts']]+[old];index=max(int(p.name.rsplit('-',1)[1]) for p in prior)+1
        attempt=OUT/'attempts'/f'{name}-attempt-{index:03d}';assert not attempt.exists(),attempt
        cmd=[PY,str(LOCAL/'method/safe_controlled_eval.py'),'--prepared',str(prepared),'--jobs',str(attempt),'--agent',record['agent'],'--model',record['model'],'--method',record['method_id'],'--bench',str(shim)]
        dry=OUT/'preflight'/attempt.name
        drycmd=list(cmd);drycmd[drycmd.index('--jobs')+1]=str(dry)
        if not dry.exists():subprocess.run(drycmd+['--dry-run'],env=env,check=True,capture_output=True)
        newpre=load(dry/'EXECUTION_PREFLIGHT.json');assert newpre['skill_bundle']==pre['skill_bundle'];assert newpre['validated_prebuilt_image']==pre['validated_prebuilt_image']
        diffs={k:{'old':pre['staged_task_hashes'].get(k),'new':v} for k,v in newpre['staged_task_hashes'].items() if pre['staged_task_hashes'].get(k)!=v}
        assert set(diffs)==({'verifier/test_outputs.py'} if r['task_id']=='data-to-d3' else set()),diffs
        plans.append({'experiment_id':name,'task_id':r['task_id'],'group':r['group'],'old_attempts':[str(p) for p in prior],'new_attempt':str(attempt),'command':cmd,'model':record['model'],'base_url':env['TATUMASS_BASE_URL'],'parent_budget':60,'image':newpre['validated_prebuilt_image'],'skill_bundle':newpre['skill_bundle'],'task_hash_differences':diffs,'verifier_version':'d3-svg-text-content-v1-20261124' if r['task_id']=='data-to-d3' else 'unchanged-accepted-20261123','reason':'authorized verifier version change with matched D3 controls' if r['task_id']=='data-to-d3' else 'prior selected attempts invalid; one new completion attempt authorized by current goal','started_at':None,'finished_at':None})
    save(OUT/'ATTEMPT_PLAN.json',plans)
    def run(plan):
        plan['started_at']=stamp();save(OUT/'ATTEMPT_PLAN.json',plans);attempt=Path(plan['new_attempt']);attempt.parent.mkdir(exist_ok=True)
        with (attempt.parent/(attempt.name+'.launcher.log')).open('w') as log:q=subprocess.run(plan['command'],env=env,stdout=log,stderr=subprocess.STDOUT)
        plan['finished_at']=stamp();plan['exit_code']=q.returncode;save(attempt/'ATTEMPT_LINK.json',plan);save(OUT/'ATTEMPT_PLAN.json',plans);print('DONE',plan['experiment_id'],q.returncode,flush=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        for f in as_completed([pool.submit(run,p) for p in plans]):f.result()

if __name__=='__main__':main()
