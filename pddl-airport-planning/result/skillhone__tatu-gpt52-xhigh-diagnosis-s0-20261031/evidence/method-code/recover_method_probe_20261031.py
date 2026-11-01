"""Continue one explicitly inspected SkillHone probe in its retained native session."""
import inspect
import getpass
import io
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tarfile
import fcntl
import time

import adapter
from pddl_flink_lane_20261031 import lane

HERE=Path(__file__).resolve().parent
SHARED=Path('/home/linyuanjing/pddl-flink-skillhone-gpt52-20261031')


def recovery_directory(spec):
    root=Path(spec['root'])
    if spec.get('final_phase'):
        phase=spec['final_phase'];repeat=spec['repeat']
        if phase not in ('original','group_01','group_02','group_03') or repeat not in range(1,3 if phase=='original' else 4):
            raise ValueError('Unknown frozen final slot')
        return root/'final-evaluations'/phase/f'recovery-repeat-{repeat}'
    return root/f'rounds/round-{spec["round"]}'


def resume_final_if_ready(spec):
    root=Path(spec['root']);phase=spec['final_phase']
    if phase in ('group_01','group_03'):
        return  # The separate rolling extension collects these canonical responses.
    stage=root/'final-evaluations'/phase
    if not all((stage/f'repeat-{n}.response.json').exists() for n in range(1,3 if phase=='original' else 4)):
        return
    with (root/'final-stage-resume.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        state=adapter.read_json(root/'campaign-state.json')
        def alive(pid):
            p=Path(f'/proc/{pid}/stat')
            return p.exists() and p.read_text().split(') ')[1].split()[0] not in ('Z','X')
        receipt=root/'final-stage-resume.json'
        if alive(state['controller_pid']) or (receipt.exists() and alive(adapter.read_json(receipt)['controller_pid'])):
            return
        expected='original-confirmation' if phase=='original' else 'group_02-generalization'
        if state['status']!='needs-infrastructure-recovery' or state['phase']!=expected:
            return
        node=HERE/'.runtime/node-v24.19.0-linux-x64/bin/node'
        with (root/'controller-final-resume.log').open('a') as log:
            child=subprocess.Popen([str(node),str(HERE/'pddl_flink_skillhone_iterations_20261031.mjs'),str(root),'--resume-final'],
                cwd=root,env=os.environ,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        adapter.write_json(receipt,{'controller_pid':child.pid,'completed_phase':phase,'new_repair_calls':0,
            'selection_changed':False,'reused_valid_final_responses':True})


def checkpoint(spec):
    root=Path(spec['root']);source=Path(spec['source_run'])
    final=bool(spec.get('final_phase'));rd=recovery_directory(spec)
    allowed=root/'final-evaluations'/spec['final_phase']/'jobs/skillhone' if final else root/'state/projects'
    if root.parent!=SHARED or spec['task']!=root.name or not source.is_relative_to(allowed):
        raise ValueError('Checkpoint is outside the explicitly authorized method campaign')
    repair=adapter.read_json(root/'selection.json' if final else root/f'rounds/round-{spec["round"]}/repair.json')
    if adapter.git(root/'skill','rev-parse','HEAD')!=repair['commit'] or repair['commit']!=spec['candidate_commit']:
        raise ValueError('Original candidate changed before checkpoint recovery')
    config=adapter.read_json(source/'config.json');result=adapter.read_json(source/'result.json')
    request=adapter.read_json(rd.parent/f'repeat-{spec["repeat"]}.request.json' if final else source.parents[2]/(source.name+'.request.json'))
    task_dir=root/'final-eval/tasks'/spec['final_phase']/spec['task'] if final and spec['final_phase']!='original' else root/'eval/tasks/probe'/spec['task']
    if (not result.get('error') or config['task_path']!=spec['task']
        or request['task_dir']!=str(task_dir)
        or request['rollout_id']!=source.name or request['parent_iterations']!=60
        or request['model']!='tatu/gpt-5.2' or request['reasoning_effort']!='xhigh'):
        raise ValueError('This source is not the inspected interrupted original probe')
    data=subprocess.check_output(['docker','cp',f'{spec["container"]}:/home/agent/.openhands/conversations','-'])
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        session=spec['session']
        state=json.load(tar.extractfile(f'conversations/{session}/base_state.json'))
        if str(state['id']).replace('-','')!=session:raise ValueError('Original ACP session identity mismatch')
        events=[json.load(tar.extractfile(m)) for m in tar.getmembers()
            if f'/{session}/events/event-' in m.name and m.isfile()]
    responses=len({e['llm_response_id'] for e in events if e.get('llm_response_id')})
    errors=sum(e.get('kind')=='ConversationErrorEvent' for e in events)
    guards=sum(e.get('kind')=='MessageEvent' and e.get('source')=='environment'
        and e.get('llm_message',{}).get('role')=='user'
        and '[Benchmark executor text-only guard]' in json.dumps(e) for e in events)
    counter=source/'agent/checkpoint-parent-counter.json'
    used=max(responses+errors,int(adapter.read_json(counter).get('total_started',0)) if counter.exists() else 0,
        int((result.get('agent_result') or {}).get('iterations_used') or 0))
    if not 0<used<60 or guards>1:raise ValueError('Inspect exhausted/inconsistent original parent budget')
    return {'session':session,'event_count':len(events),'successful_parent_responses':responses,
        'failed_parent_steps':errors,'prior_parent_iterations':used,'remaining':60-used,'guard_used':guards,
        'source_run':str(source),'candidate_commit':repair['commit'],'container':spec['container']}


def execute(spec):
    root=Path(spec['root']);rd=recovery_directory(spec);rd.mkdir(parents=True,exist_ok=True)
    final=bool(spec.get('final_phase'))
    response=rd.parent/f'repeat-{spec["repeat"]}.response.json' if final else rd/'recovered-probe.json'
    if response.exists():raise RuntimeError('Already scored; do not regenerate this slot')
    config=adapter.read_json(root/'eval/campaign.json');metadata=checkpoint(spec)
    sys.path.insert(0,str(Path(config['executor_root'])/'src'));os.chdir(config['executor_root'])
    import baseline_gpt52_tatu_20261029 as baseline
    baseline.EXECUTOR=Path(config['executor_root']);baseline.register_provider()
    os.environ.update(baseline.environment());baseline.install_hooks(SHARED)
    from benchflow.acp import runtime
    from benchflow.acp.client import ACPClient
    import benchflow.rollout_planes as planes
    from benchflow.sandbox.docker import DockerSandbox
    import benchflow.agents.install as installation
    from benchflow.agents import openhands_runtime_cache as cache
    from benchmark_executor import BenchmarkExecutor
    remaining=metadata['remaining'];runtime.MAX_PARENT_ITERATIONS_PER_STEP=remaining
    assert metadata['prior_parent_iterations']+remaining==60
    original_connect=runtime.connect_acp;signature=inspect.signature(original_connect)

    async def pinned_runtime(sandbox):
        code=('from pathlib import Path; from importlib.metadata import version; '
            f'assert Path({cache.OPENHANDS_RUNTIME_MARKER!r}).read_text().strip()=={cache.expected_runtime_marker()!r}; '
            "assert version('openhands-sdk')=='1.28.1'; assert version('openhands-tools')=='1.28.1'")
        result=await sandbox.exec('/opt/benchflow/uv-tools/openhands/bin/python -c '+shlex.quote(code),user='root',timeout_sec=25)
        if result.return_code:raise RuntimeError('Retained OpenHands runtime identity mismatch')
        return {'mode':'retained-pinned-runtime','archive':baseline.ARCHIVE.name}
    installation.prepare_openhands_runtime_cache=pinned_runtime

    async def retained_start(sandbox,force_build):
        sandbox.session_id=Path(spec['source_run']).name
        # An /app archive cannot restore the native SDK session after an error.
        # Keep this retained session until its actual outcome is accepted.
        sandbox._keep_containers=True
        subprocess.run(['docker','start',spec['container']],check=True,stdout=subprocess.DEVNULL)
        check=await sandbox.exec(f'test -f /home/agent/.openhands/conversations/{spec["session"]}/base_state.json',user='root',timeout_sec=10)
        if check.return_code:raise RuntimeError('Retained container lost its native checkpoint')
        # Only the existing native counter may need its writer restored after export.
        writable=await sandbox.exec('if test -f /logs/agent/checkpoint-parent-counter.json; then chown agent /logs/agent/checkpoint-parent-counter.json; fi',user='root',timeout_sec=10)
        if writable.return_code:raise RuntimeError('Cannot restore native checkpoint counter writer')
        proxy=await sandbox.exec("python3 -c \"import socket; s=socket.create_connection(('host.docker.internal',7890),timeout=5);s.close()\"",user='root',timeout_sec=10)
        if proxy.return_code:raise RuntimeError('Retained verifier proxy TCP preflight failed')
        metadata['proxy_tcp_preflight']=True
    DockerSandbox.start=retained_start
    DockerSandbox.is_mounted=property(lambda sandbox:False)

    async def load_original(client,cwd='/app',mcp_servers=None):
        return await client.session_load(spec['session'],cwd=cwd,mcp_servers=mcp_servers)
    ACPClient.session_new=load_original

    async def connect(*args,**kwargs):
        bound=signature.bind(*args,**kwargs);sandbox=bound.arguments['env']
        await sandbox.upload_file(HERE/'openhands_checkpoint_hook.py','/opt/benchflow/bin/openhands_checkpoint_hook.py')
        code=("from pathlib import Path;p=Path('/opt/benchflow/bin/openhands-benchmark-executor');s=p.read_text();"
            "old='    install_adapter()'+chr(10);assert s.count(old)==1;"
            "new='    from openhands_checkpoint_hook import install_resume'+chr(10)+'    install_resume()'+chr(10)+old;"
            "p.write_text(s if 'from openhands_checkpoint_hook import install_resume' in s else s.replace(old,new,1))")
        patched=await sandbox.exec('python3 -c '+shlex.quote(code),user='root',timeout_sec=15)
        if patched.return_code:raise RuntimeError('Cannot install native checkpoint hook')
        env=dict(bound.arguments['agent_env'])
        if not env['LLM_MODEL'].startswith('openai/'):raise RuntimeError('Unexpected Tatu native model alias')
        env['LLM_MODEL']=env['LLM_MODEL'].removesuffix('-responses-bridge')
        env.update(BENCHFLOW_RECOVERY_SESSION_ID=spec['session'],
            BENCHFLOW_RECOVERY_EVENT_COUNT=str(metadata['event_count']),
            BENCHFLOW_RECOVERY_PRIOR_ITERATIONS=str(metadata['prior_parent_iterations']),
            BENCHMARK_EXECUTOR_MAX_ITERATIONS=str(remaining),
            BENCHFLOW_OPENHANDS_TEXT_ONLY_RETRY_LIMIT=str(1-metadata['guard_used']))
        bound.arguments['agent_env']=env
        return await original_connect(**bound.arguments)
    runtime.connect_acp=planes.connect_acp=connect
    sequence=1;source=Path(spec['source_run']).name
    jobs=rd/'jobs' if final else root/'probe-recovery'
    while (jobs/'skillhone'/f'{source}-checkpoint-{sequence:02d}').exists():sequence+=1
    rollout=f'{source}-checkpoint-{sequence:02d}'
    evidence={**metadata,'parent_budget':60,'remaining_guard_uses':1-metadata['guard_used'],
        'injected_user_messages':0,'worker_pid':os.getpid(),'continuation_rollout':rollout,
        'protocol':'native SDK Chat on the same Tatu GPT-5.2 route, no Responses round-trip'}
    adapter.write_json(rd/f'probe-checkpoint-{sequence:02d}.json',evidence)
    task_root=root/'final-eval/tasks'/spec['final_phase'] if final and spec['final_phase']!='original' else root/'eval/tasks/probe'
    executor=BenchmarkExecutor(tasks_root=task_root,jobs_root=jobs,
        model='tatu/gpt-5.2',reasoning_effort='xhigh',experimental_text_only_retry_limit=1)
    result=executor.run(task_id=spec['task'],condition='method-skill',skill_bundle=root/'skill/skills',
        method_id='skillhone',stage=f'frozen-{spec["final_phase"]}-r{spec["repeat"]}-native-checkpoint' if final else f'round-{spec["round"]}-native-checkpoint',rollout_id=rollout)
    if result.agent_iterations is not None and result.agent_iterations>remaining:
        raise RuntimeError('Continuation exceeded unspent original parent budget')
    row={'reward':result.reward,'passed':result.task_passed is True,'execution_ok':result.execution_ok,
        'result_json':str(result.artifacts.result_json),'prior_parent_iterations':metadata['prior_parent_iterations'],
        'continuation_parent_iterations':result.agent_iterations,
        'total_parent_iterations':metadata['prior_parent_iterations']+result.agent_iterations if result.agent_iterations is not None else None,
        'parent_budget':60,'n_skill_invocations':result.skill_exposure.native_skill_invocations,
        'skill_preload_verified':result.skill_exposure.verified,'cost_usd':result.cost_usd,
        'original_result_json':str(Path(spec['source_run'])/'result.json'),
        'cost_scope':'continuation estimate only; original usage/errors retained separately',
        'actual_provider_cost_usd':None}
    adapter.write_json(Path(result.artifacts.result_json).parent/'checkpoint-recovery.json',{**evidence,'result':row})
    adapter.write_json(rd/f'probe-checkpoint-{sequence:02d}-result.json',row)
    archive=Path(result.artifacts.result_json).parent/'artifacts/pre-verifier-workspace.tar.gz'
    if not result.execution_ok or result.reward is None or not archive.is_file():
        raise RuntimeError('Checkpoint needs actual result/error inspection; never restart repair or original probe blindly')
    if final:
        row.update(agent_iterations=row['total_parent_iterations'],parent_iterations=60,
            execution_budget_scope='shared-default',source_kind='real_native_checkpoint_recovery',
            used_for_selection=False)
        adapter.write_json(response,row)
        adapter.write_json(rd/'recovered-final.json',row)
        resume_final_if_ready(spec)
        print(json.dumps({'task':spec['task'],'final_checkpoint_scored':True,'phase':spec['final_phase'],
            'repeat':spec['repeat'],'reward':result.reward,'prior':metadata['prior_parent_iterations']}))
        return
    probe={'id':f'round-{spec["round"]}-recovered-probe','score':result.reward,'n_total':1,
        'n_passed':int(result.task_passed is True),'traces':[row],'source_kind':'real_native_checkpoint_recovery',
        'source_result':row['result_json']}
    adapter.write_json(rd/'recovered-probe.json',probe)
    node=HERE/'.runtime/node-v24.19.0-linux-x64/bin/node'
    with (rd/'controller-after-probe.log').open('w') as log:
        child=subprocess.Popen([str(node),str(HERE/'pddl_flink_skillhone_iterations_20261031.mjs'),str(root),'--resume-probe'],
            cwd=root,env=os.environ,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    adapter.write_json(rd/'controller-after-probe-launch.json',{'pid':child.pid,'source':str(rd/'recovered-probe.json'),'new_repair_calls':0})
    print(json.dumps({'task':spec['task'],'checkpoint_scored':True,'reward':result.reward,'prior':metadata['prior_parent_iterations']}))


def launch(spec_files):
    def alive(pid):
        try:return Path(f'/proc/{pid}/stat').read_text().split(') ')[1].split()[0] not in ('Z','X')
        except FileNotFoundError:return False
    plans=[]
    for file in spec_files:
        spec=adapter.read_json(file);root=Path(spec['root']);rd=recovery_directory(spec);final=bool(spec.get('final_phase'))
        state=adapter.read_json(root/'campaign-state.json')
        if not final and (alive(state['controller_pid']) or (state.get('recovery_pid') and alive(state['recovery_pid']))):
            raise RuntimeError('A controller/recovery worker is already alive')
        if not final and (state['status']!='needs-infrastructure-recovery' or state['phase']!='probe'):
            raise RuntimeError('Inspect the actual probe state before launch')
        if final:
            original=adapter.read_json(rd.parent/f'repeat-{spec["repeat"]}.response.launch.json')
            if alive(original['pid']):raise RuntimeError('Original final worker is still alive')
        response=rd.parent/f'repeat-{spec["repeat"]}.response.json' if final else rd/'recovered-probe.json'
        if response.exists():raise RuntimeError('Slot already recovered; resume controller only')
        for prior in rd.glob('probe-checkpoint-launch-*.json'):
            if alive(adapter.read_json(prior)['pid']):raise RuntimeError('Original checkpoint worker is still alive')
        metadata=checkpoint(spec)
        number=1
        while (rd/f'probe-checkpoint-launch-{number:02d}.json').exists():number+=1
        plans.append((Path(file),spec,root,rd,state,metadata,number))
    preflight=adapter.read_json(SHARED/'provider-preflight.json')
    if preflight['status']!=200 or not preflight['model_present']:raise RuntimeError('Verified original Tatu route evidence is missing')
    key=os.environ.get('TATU_API_KEY') or getpass.getpass('Current Tatu key (hidden input): ')
    node=HERE/'.runtime/node-v24.19.0-linux-x64/bin/node'
    env=dict(os.environ);env.update(TATU_API_KEY=key,TATU_CONFIRMED_PROXY='http://127.0.0.1:7890',
        TATU_VERIFIER_PROXY='http://host.docker.internal:7890',HTTP_PROXY='http://127.0.0.1:7890',HTTPS_PROXY='http://127.0.0.1:7890',
        NODE_USE_ENV_PROXY='1',SKILLHONE_SHARED_ROOT=str(SHARED),SKILLHONE_ALLOW_EXECUTION='1',
        BENCHMARK_MODEL='tatu/gpt-5.2',BENCHMARK_REASONING_EFFORT='xhigh',LLM_MAX_OUTPUT_TOKENS='16384',
        PYTHONDONTWRITEBYTECODE='1',NO_PROXY='localhost,127.0.0.1,::1,host.docker.internal',PATH=str(node.parent)+':'+env.get('PATH',''))
    launched=[]
    for file,spec,root,rd,state,metadata,number in plans:
        if not spec.get('final_phase'):
            adapter.write_json(rd/f'probe-interruption-{number:02d}.json',state)
        with (rd/f'probe-checkpoint-worker-{number:02d}.log').open('w') as log:
            child=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),str(file)],cwd=HERE,env=env,
                stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        receipt={'pid':child.pid,'spec':str(file),'source_checkpoint':metadata,'new_repair_calls':0,'new_user_task_messages':0}
        adapter.write_json(rd/f'probe-checkpoint-launch-{number:02d}.json',receipt)
        if not spec.get('final_phase'):
            state.update(status='running',recovery_pid=child.pid,recovery_source=str(file))
            state.pop('error_type',None);state.pop('error_message',None);adapter.write_json(root/'campaign-state.json',state)
        launched.append({'task':spec['task'],'pid':child.pid,'prior':metadata['prior_parent_iterations'],'remaining':metadata['remaining']})
    print(json.dumps({'launched':launched,'new_generation_probes':0,'new_repair_calls':0}))


if __name__=='__main__' and sys.argv[1]=='--await-final':
    spec=adapter.read_json(Path(sys.argv[2]));stage=recovery_directory(spec).parent
    while not all((stage/f'repeat-{n}.response.json').exists() for n in range(1,3 if spec['final_phase']=='original' else 4)):
        time.sleep(10)
    resume_final_if_ready(spec)
elif __name__=='__main__' and sys.argv[1]=='--launch':
    launch([Path(x) for x in sys.argv[2:]])
elif __name__=='__main__':
    spec=adapter.read_json(Path(sys.argv[1]))
    try:
        identity=spec['task']+(f'-frozen-{spec["final_phase"]}-r{spec["repeat"]}-checkpoint' if spec.get('final_phase') else f'-round-{spec["round"]}-checkpoint')
        with lane(identity):
            execute(spec)
    except Exception as error:
        if spec.get('final_phase'):
            adapter.write_json(recovery_directory(spec)/'checkpoint-error.json',{'error_type':type(error).__name__,
                'error_message':str(error),'worker_pid':os.getpid()})
            raise
        root=Path(spec['root']);state=adapter.read_json(root/'campaign-state.json')
        state.update(status='needs-infrastructure-recovery',phase='probe',recovery_pid=os.getpid(),
            error_type=type(error).__name__,error_message=str(error))
        adapter.write_json(root/'campaign-state.json',state)
        raise
