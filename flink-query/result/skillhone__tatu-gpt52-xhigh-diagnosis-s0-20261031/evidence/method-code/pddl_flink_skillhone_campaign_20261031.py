"""Host preparation/feedback and independent model workers, without candidates."""
import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
import getpass
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

import adapter
from pddl_flink_lane_20261031 import lane

HERE=Path(__file__).resolve().parent
UPSTREAM=HERE/'SkillHone'
NODE=HERE/'.runtime/node-v24.19.0-linux-x64/bin/node'
PYTHON=Path('/home/linyuanjing/.venvs/skill-repair-benchmark-a16/bin/python')
ROOT=Path('/home/linyuanjing/pddl-flink-skillhone-gpt52-20261031')
BASELINE=Path('/home/linyuanjing/pddl-flink-tatu-gpt52-20261029')
TASKS=('pddl-airport-planning','flink-query')
INSTALLED=Path('/home/linyuanjing/jpg-skillhone-diagnosis-s0-20261031/state/harness')


def command(args,cwd=None,env=None):
    return subprocess.check_output([str(x) for x in args],cwd=cwd,env=env,text=True).strip()


def prepare():
    if ROOT.exists():raise FileExistsError('Inspect existing campaign root; do not duplicate paid work')
    assert adapter.git(UPSTREAM,'rev-parse','HEAD')=='7e0ce7ce6e8239cb870822d3db5ff66c5ef644d1'
    assert adapter.git(HERE/'datasets','rev-parse','HEAD')=='556fd216287be7e58480ed5a6dd935ca3370e639'
    ROOT.mkdir();(ROOT/'lanes').mkdir();(ROOT/'lane-receipts').mkdir()
    import register
    for task in TASKS:
        root=ROOT/task;root.mkdir()
        existing=HERE/'campaigns'/task
        config=adapter.read_json(existing/'eval/campaign.json')
        assert adapter.git(existing/'skill','rev-parse','main')==config['seed_commit']
        command(['git','clone','--quiet','--no-hardlinks','--single-branch','--branch','main',existing/'skill',root/'skill'])
        adapter.git(root/'skill','remote','remove','origin')
        adapter.git(root/'skill','config','user.name','Local SkillHone experiment')
        adapter.git(root/'skill','config','user.email','local@invalid')
        evaluation=root/'eval';evaluation.mkdir()
        shutil.copytree(existing/'eval/reference_skills',evaluation/'reference_skills')
        shutil.copytree(BASELINE/'tasks/original'/task,evaluation/'tasks/probe'/task)
        shutil.copytree(BASELINE/'tasks/group_02'/task,root/'final-eval/tasks/group_02'/task)
        assert (evaluation/'tasks/probe'/task/'task.md').read_bytes()==(HERE/'datasets'/task/'task.md').read_bytes()
        assert adapter.verify_bundle(root/'skill/skills',evaluation/'reference_skills')==(1 if task.startswith('pddl') else 2)
        for f in ('probe.jsonl',):shutil.copy2(existing/'eval'/f,evaluation/f)
        config.update(executor_root=str(HERE.parent/'skill-repair-benchmark'),seed_commit=adapter.git(root/'skill','rev-parse','HEAD'),
            parent_iterations=60,repetitions=1,synthetic=False,allowed_splits=['probe'],reuse_probe_results=False,
            formal_model_and_repetitions_not_yet_selected=False)
        adapter.write_json(evaluation/'campaign.json',config)
        text=(HERE/'adapter.py').read_text()
        assert text.count('def worker(request_file, response_file):')==1
        text=text.replace('def worker(request_file, response_file):','def _underlying_worker(request_file, response_file):',1)
        marker='def run(evaluation, skill, split, output):'
        text=text.replace(marker,'def worker(request_file, response_file):\n    from pddl_flink_method_runtime_20261031 import run_worker\n    return run_worker(request_file, response_file, _underlying_worker)\n\n\n'+marker,1)
        (evaluation/'adapter.py').write_text(text)
        for name in ('pddl_flink_method_runtime_20261031.py','pddl_flink_lane_20261031.py','verifier_maven_proxy.py'):
            shutil.copy2(HERE/name,evaluation/name)
        shutil.copy2(HERE/'baseline_gpt52_tatu_20261029.py',evaluation/'baseline_runtime.py')
        adapter.commit_repo(evaluation)
        state=root/'state';(state/'harness').mkdir(parents=True)
        (state/'harness/node_modules').symlink_to(INSTALLED/'node_modules',target_is_directory=True)
        profile=state/'harness/home/profiles/headless';profile.mkdir(parents=True)
        for name in ('package.json','cordis.yml','pnpm-workspace.yaml'):
            shutil.copy2(INSTALLED/'home/profiles/headless'/name,profile/name)
        (profile/'cordis.patch.yml').write_text('''- id: llm-pi-ai
  config:
    providers:
      tatu:
        apiKeyEnv: TATU_API_KEY
        api: openai-completions
        baseURL: https://maas.tatucloud.com/v1
        reasoning: xhigh
        models:
          - id: gpt-5.2
            input: [text]
            contextWindow: 400000
            maxTokens: 16384
            reasoningEfforts:
              xhigh: xhigh
- id: agent-default-model
  config:
    provider: tatu
    model: gpt-5.2
''')
        (state/'harness/home/AGENTS.md').write_text(
            'This is a fresh isolated native SkillHone repair context. No Codex chat is supplied. '
            'Read TRAINING.md, original task/inputs, all current Skills and the diagnosis supplied in this isolated context. '
            'Only existing skills/**/SKILL.md bodies may change; preserve YAML frontmatter, all support, training and license files. '
            'No added scripts/tests/references, instance-specific answers, or hard-coded plans/job values. '
            'Round 1 uses published S0; later rounds use only the diagnosis rebuilt from the latest actual original-task failure. '
            'Never inspect Eval directories, verifiers/oracles, held-out groups or other experiments. '
            'Do not spawn subagents or invoke SkillHone, manipulate its records, merge or push.\n')
        feedback=adapter.read_json(root/'skill/training-context/diagnosis/outputs/allowed_feedback.json')
        adapter.write_json(root/'s0.json',{'kind':'published_historical_diagnosis','score':feedback['original_reward'],
            'historical_binary_reward':feedback['original_reward'],'current_item_accuracy':feedback['current_accuracy'],
            'not_a_new_baseline':True,'new_model_calls':0,'feedback':'training-context/diagnosis/outputs/allowed_feedback.json'})
        adapter.write_json(root/'preparation.json',{'task_id':task,'source_commit':config['source_commit'],'seed':config['seed_commit'],
            'model':'tatu/gpt-5.2','reasoning_effort':'xhigh','max_output_tokens':16384,'parent_iterations':60,
            'repair_rounds_max':5,'additional_original_runs':2,'group_02_runs':3,'global_execution_lanes':3,
            'held_out_available_to_repair':False,'check':adapter.check(evaluation,root/'skill')})
        register.cli(NODE,UPSTREAM,state,root/'skill','config','set','--merge','review','--trigger','queued')
        register.cli(NODE,UPSTREAM,state,root/'skill','benchmark','init','--eval-repo',str(evaluation),'--runner',register.runner(PYTHON))
    return {'prepared':True,'tasks':list(TASKS),'model_calls':0}


def validate(root,workspace):
    adapter.check(root/'eval',workspace)
    for source in (root/'eval/reference_skills').rglob('SKILL.md'):
        actual=workspace/'skills'/source.relative_to(root/'eval/reference_skills')
        text=source.read_text()
        if text.startswith('---\n') and not actual.read_text().startswith('---'+text.split('---',2)[1]+'---'):
            raise ValueError('Only Skill bodies may change')
    return {'candidate_scope_valid':True}


def failure(root,identifier,output):
    if identifier.startswith('round-') and identifier.endswith('-recovered-probe'):
        number=int(identifier.split('-')[1]);assert 1<=number<=5
        result=adapter.read_json(root/f'rounds/round-{number}/recovered-probe.json')
        assert result['id']==identifier and result['source_kind']=='real_native_checkpoint_recovery'
    else:
        matches=list((root/'state/projects').glob(f'*/benchmark/results/{identifier}.json'))
        if len(matches)!=1:raise ValueError('Cannot uniquely locate real original probe')
        result=adapter.read_json(matches[0])
    assert result['n_total']==1
    run=Path(result['traces'][0]['result_json']).parent
    output.mkdir(parents=True,exist_ok=False)
    names=['trajectory/acp_trajectory.jsonl','trajectory/llm_trajectory.jsonl','trainer/atif.json']
    for name in names:
        target=output/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(run/name,target)
    accuracy=adapter.read_json(run/'verifier/accuracy.json') if (run/'verifier/accuracy.json').exists() else {}
    ctrf=adapter.read_json(run/'verifier/ctrf.json') if (run/'verifier/ctrf.json').exists() else {}
    tests=ctrf.get('results',ctrf).get('tests',[])
    allowed={'reward':result['score'],'accuracy_scalars':{k:v for k,v in accuracy.items() if v is None or isinstance(v,(int,float,bool))},
        'tests':[{'name':x.get('name'),'status':x.get('status')} for x in tests], 'reference_values_or_verifier_source_included':False}
    adapter.write_json(output/'allowed_feedback.json',allowed)
    shutil.copy2(run/'artifacts/pre-verifier-workspace.tar.gz',output/'actual-training-workspace.tar.gz')
    adapter.write_json(output/'index.json',{'kind':'actual_failed_original_probe','source_run':str(run),
        'score':result['score'],'streams':names,'feedback':'allowed_feedback.json','actual_workspace':'actual-training-workspace.tar.gz',
        'new_model_calls':0})
    return {'failure_exported':True,'score':result['score']}


def repair(root,prompt,workspace,log,identity):
    round_input=adapter.read_json(prompt.parent/'repair-input.json')
    round_number=round_input['round']
    native_workspace=workspace;actual_prompt=prompt;context_metadata=None
    if round_number>1:
        from iteration_diagnosis_20261031 import prepare_context
        feedback=root/'feedback'/f'round-{round_number-1}'
        native_workspace,context_metadata=prepare_context(root,workspace,feedback)
        actual_prompt=prompt.parent/'repair-current-diagnosis-prompt.txt'
        text=(f'You are the native SkillHone repair worker for {root.name}, round {round_number}/5. '
            f'Work only in {native_workspace}. Read TRAINING.md, the original task and inputs, every current Skill, '
            'and the complete latest-failure diagnosis at training-context/diagnosis/index.json. '
            'This diagnosis was rebuilt from the immediately preceding actual failed original-task probe. '
            'Historical S0 diagnosis is not in this context; do not retrieve or reuse it. '
            'Diagnose this current failure and repair only existing skills/**/SKILL.md bodies. '
            'Preserve frontmatter and every support, input, diagnosis and license file byte-for-byte. '
            'Do not solve the task yourself, embed instance answers, add files/scripts/tests, run a full evaluator, '
            'inspect other directories/held-out material/verifiers/oracles, spawn agents, invoke SkillHone, merge or push. '
            'Commit only the permitted Skill changes and leave a clean tree.')
        actual_prompt.write_text(text)
        adapter.write_json(prompt.parent/'actual-repair-input.json',{'round':round_number,
            'protocol':'latest-failure-diagnosis-v2','supersedes_static_prompt':str(prompt),
            'actual_prompt_file':str(actual_prompt),'actual_prompt':text,'diagnosis':context_metadata,
            'historical_s0_diagnosis_included':False,'diagnosis_preparation_model_calls':0})
    with lane(identity) as fd:
        args=[str(NODE),str(HERE/'pddl_flink_skillhone_iterations_20261031.mjs'),'--native-repair',str(root),str(actual_prompt),str(native_workspace),str(log)]
        result=subprocess.run(args,cwd=native_workspace,pass_fds=(fd,),capture_output=True,text=True)
    outcome=repair_outcome(root,native_workspace,log,result.returncode)
    if context_metadata:
        from iteration_diagnosis_20261031 import import_candidate
        copied=import_candidate(root,native_workspace,context_metadata['input_commit'],workspace)
        outcome.update(copied,diagnosis=context_metadata,protocol='latest-failure-diagnosis-v2')
        adapter.write_json(workspace.parent/'repair-outcome.json',outcome)
    return outcome


def repair_outcome(root,workspace,log,exit_code=1):
    sessions=[]
    for file in (root/'state/harness/home/sessions').rglob('session.v4.jsonl.zstd'):
        value=json.loads(command([NODE,HERE/'dsh_session_metadata_20261031.mjs',file]))
        if value['cwd']==str(workspace):sessions.append(value)
    if len(sessions)!=1:raise RuntimeError('Cannot uniquely identify retained native repair session')
    session=sessions[0];reason=(session.get('terminal_reason') or {}).get('kind')
    timed_out='ETIMEDOUT' in log.read_text()
    if exit_code==0 and reason=='completed':outcome='completed'
    elif reason=='max-tokens':outcome='max-tokens'
    elif timed_out:outcome='native-20-minute-timeout'
    else:raise RuntimeError(f'Unclassified native DSH failure; retain session {session["session_id"]} for recovery')
    value={'native_repair_exit_code':exit_code,'stop_reason':outcome,'session':session,
        'evaluate_actual_retained_worktree':True,'new_model_calls_by_recovery':0,
        'repair_budget_reset':False,'source_log':str(log)}
    adapter.write_json(workspace.parent/'repair-outcome.json',value)
    return value


def final(root,phase):
    selected=adapter.read_json(root/'selection.json');assert adapter.git(root/'skill','rev-parse','HEAD')==selected['commit']
    task=adapter.read_json(root/'preparation.json')['task_id'];config=adapter.read_json(root/'eval/campaign.json')
    taskdir=root/'eval/tasks/probe'/task if phase=='original' else root/'final-eval/tasks/group_02'/task
    count=2 if phase=='original' else 3
    output=root/'final-evaluations'/phase;output.mkdir(parents=True,exist_ok=True)
    def execute(n):
        response=output/f'repeat-{n}.response.json'
        if response.exists():return adapter.read_json(response)
        request_file=output/f'repeat-{n}.request.json'
        if request_file.exists():raise RuntimeError('Unfinished final slot needs actual checkpoint/artifact recovery')
        request={'executor_root':config['executor_root'],'task_dir':str(taskdir),'task_id':task,'parent_iterations':60,
            'model':'tatu/gpt-5.2','reasoning_effort':'xhigh','jobs_root':str(output/'jobs'),
            'skill_bundle':str(root/'skill/skills'),'stage':f'frozen-{phase}-repeat-{n}',
            'rollout_id':f'{task}-frozen-{phase}-r{n}-{uuid.uuid4().hex[:8]}'}
        adapter.write_json(request_file,request)
        with (output/f'repeat-{n}.log').open('w') as stream:
            child=subprocess.Popen([str(PYTHON),str(root/'eval/adapter.py'),'_worker',str(request_file),str(response)],
                cwd=config['executor_root'],stdout=stream,stderr=subprocess.STDOUT)
            adapter.write_json(response.with_suffix('.launch.json'),{'pid':child.pid,'request':str(request_file)})
            status=child.wait()
        if status:raise RuntimeError(f'Final slot {n} needs infrastructure recovery; retain other independent results')
        return adapter.read_json(response)
    results=[];errors=[]
    with ThreadPoolExecutor(max_workers=3) as pool:
        for future in as_completed([pool.submit(execute,n) for n in range(1,count+1)]):
            try:results.append(future.result())
            except Exception as error:errors.append(type(error).__name__+': '+str(error))
    adapter.write_json(output/'summary.json',{'selected_commit':selected['commit'],'phase':phase,'n_expected':count,
        'n_valid':len(results),'results':results,'errors':errors,'used_for_selection':False})
    if errors:raise RuntimeError('Some final slots need infrastructure recovery; valid slots retained')
    return {'phase':phase,'n_valid':count,'mean_reward':sum(x['reward'] for x in results)/count}


def launch(resume=False):
    receipt=ROOT/('repair-recovery-launch.json' if resume else 'launch.json')
    if receipt.exists():raise RuntimeError('Existing launch requires inspection, not another controller')
    if resume:
        for task in TASKS:
            root=ROOT/task;saved=adapter.read_json(root/'campaign-state.json')
            assert saved['status']=='needs-infrastructure-recovery' and saved['phase']=='repair'
            assert saved['current_round']==1 and not saved['rounds']
            proc=Path(f'/proc/{saved["controller_pid"]}/stat')
            if proc.exists() and proc.read_text().split(') ')[1].split()[0] not in ('Z','X'):
                raise RuntimeError('Original controller is still alive')
            outcome=adapter.read_json(root/'rounds/round-1/repair-outcome.json')
            assert outcome['stop_reason'] in ('max-tokens','native-20-minute-timeout')
            validate(root,root/'rounds/round-1/skill')
    key=os.environ.get('TATU_API_KEY') or getpass.getpass('Current Tatu key (hidden input): ')
    env=dict(os.environ);env.update(TATU_API_KEY=key,TATU_CONFIRMED_PROXY='http://127.0.0.1:7890',
        TATU_VERIFIER_PROXY='http://host.docker.internal:7890',HTTP_PROXY='http://127.0.0.1:7890',HTTPS_PROXY='http://127.0.0.1:7890',
        NODE_USE_ENV_PROXY='1',SKILLHONE_SHARED_ROOT=str(ROOT),SKILLHONE_ALLOW_EXECUTION='1',BENCHMARK_MODEL='tatu/gpt-5.2',
        BENCHMARK_REASONING_EFFORT='xhigh',LLM_MAX_OUTPUT_TOKENS='16384',PYTHONDONTWRITEBYTECODE='1',
        NO_PROXY='localhost,127.0.0.1,::1,host.docker.internal',PATH=str(NODE.parent)+':'+env.get('PATH',''))
    code="const r=await fetch('https://maas.tatucloud.com/v1/models',{headers:{Authorization:'Bearer '+process.env.TATU_API_KEY}}); let v={};try{v=await r.json()}catch{};console.log(JSON.stringify({status:r.status,model_present:(v.data??[]).some(x=>x.id==='gpt-5.2'),generation_calls:0}));if(!r.ok||!(v.data??[]).some(x=>x.id==='gpt-5.2'))process.exit(2)"
    if resume:
        checked=adapter.read_json(ROOT/'provider-preflight.json')
        assert checked['status']==200 and checked['model_present']
    else:
        checked=json.loads(command([NODE,'--input-type=module','-e',code],cwd=ROOT,env=env))
        adapter.write_json(ROOT/'provider-preflight.json',checked)
    launches=[]
    for task in TASKS:
        root=ROOT/task
        with (root/('controller-repair-recovery.log' if resume else 'controller.log')).open('w') as stream:
            argv=[str(NODE),str(HERE/'pddl_flink_skillhone_iterations_20261031.mjs'),str(root)]
            if resume:argv.append('--resume-repair')
            child=subprocess.Popen(argv,
                cwd=root,env=env,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
        launches.append({'task':task,'pid':child.pid,'root':str(root)})
    adapter.write_json(receipt,{'controllers':launches,'model':'tatu/gpt-5.2','max_lanes':3,
        'credentials_persisted':False,'retained_repair_outputs':resume,'new_repair_calls':0 if resume else None})
    return {'launched':launches,'new_generation_probes':0}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action');p.add_argument('arguments',nargs='*');args=p.parse_args()
    if args.action=='prepare':value=prepare()
    elif args.action=='launch':value=launch()
    elif args.action=='resume-repair':value=launch(resume=True)
    else:
        root=Path(args.arguments[0]);rest=args.arguments[1:]
        if args.action=='validate':value=validate(root,Path(rest[0]))
        elif args.action=='failure':value=failure(root,rest[0],Path(rest[1]))
        elif args.action=='repair':value=repair(root,*(Path(x) for x in rest[:3]),rest[3])
        elif args.action=='repair-outcome':value=repair_outcome(root,Path(rest[0]),Path(rest[1]))
        elif args.action=='final':value=final(root,rest[0])
        else:raise ValueError(args.action)
    print(json.dumps(value,ensure_ascii=True))
