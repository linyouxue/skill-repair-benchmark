from pathlib import Path
import subprocess, json, datetime, os, traceback, hashlib

W = Path('/mnt/c/Users/linyuanjing/Desktop/skill论文')
P = W/'.codex-staging/s0-recovery-publish/evaluation/results/GPT52-S0-Recovery-20260928/tasks/fix-build-google-auto'
R = W/'SkillGen-benchmarking/expanded_original_skill_runs/gpt52-openrouter-v1.1-20260903/verifier_replays/google-auto-20260928'
R.mkdir(parents=True, exist_ok=True)
CONTAINER = 'gpt52-s0-google-auto-verifier-20260928'
IMAGE = 'gpt52-s0-google-auto-verifier:20260928'
state = {'kind':'verifier-only-reconstructed-workspace', 'model_calls':0,
         'source_run':'fix-build-google-auto-original-skill-v11x-20260903-r002',
         'original_workspace_recovered':False,
         'task_digest':'sha256:a71d138003aa4c28222d6877e0dd65c3ddfbd9f407d5878fd0a235a32e9df8a4',
         'container':CONTAINER,'started_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
def save():
    (R/'state.json').write_text(json.dumps(state,indent=2)+'\n')
def run(args, timeout=600, check=True):
    with (R/'commands.jsonl').open('a') as out:
        out.write(json.dumps(args)+'\n')
    result = subprocess.run(args,timeout=timeout)
    if check and result.returncode:
        raise RuntimeError(f'command exited {result.returncode}: {args[:3]}')
    return result.returncode
def dex(script, timeout=120):
    return run(['docker','exec',CONTAINER,'bash','-c',script],timeout)

(R/'worker.pid').write_text(str(os.getpid()))
save()
try:
    state['stage']='building_original_environment';save()
    run(['docker','build','--progress=plain','--pull=false',
         '--build-arg','HTTP_PROXY=http://host.docker.internal:7890',
         '--build-arg','HTTPS_PROXY=http://host.docker.internal:7890',
         '-t',IMAGE,str(P/'frozen_task/environment')],600)
    (R/'verifier').mkdir(exist_ok=True)
    state['stage']='reconstructing_from_original_exported_patch';save()
    args=['docker','run','-d','--name',CONTAINER,'--cpus','4','--memory','4g',
          '-e','REPO_ID=google/auto','-e','bugswarm_image_tag=google-auto-101506036',
          '-e','HTTP_PROXY=http://host.docker.internal:7890',
          '-e','HTTPS_PROXY=http://host.docker.internal:7890',
          '-e','http_proxy=http://host.docker.internal:7890',
          '-e','https_proxy=http://host.docker.internal:7890',
          '-e','NO_PROXY=localhost,127.0.0.1',
          '-e','MAVEN_OPTS=-Dhttp.proxyHost=host.docker.internal -Dhttp.proxyPort=7890 -Dhttps.proxyHost=host.docker.internal -Dhttps.proxyPort=7890 -Dhttps.protocols=TLSv1.2',
          '-v',str(P/'frozen_task/verifier')+':/verifier:ro',
          '-v',str(P/'frozen_task/verifier')+':/tests:ro',
          '-v',str(R/'verifier')+':/logs/verifier',
          '-v',str(P/'representative_run/verifier')+':/original-output:ro',
          '--entrypoint','sleep',IMAGE,'infinity']
    run(args)
    dex('set -e; cd /home/travis/build/failed/google/auto; git status --short; git rev-parse HEAD; git apply --check /original-output/diffs/google/auto/patch_1.diff; git apply /original-output/diffs/google/auto/patch_1.diff; cp /original-output/diffs/google/auto/patch_1.diff patch_1.diff; cp /original-output/failed_reasons.txt /home/travis/build/failed/failed_reasons.txt; git diff --stat')
    # Export restored source BEFORE verifier mutates/copies it; this is not an original saved workspace.
    dex('tar -C /home/travis -czf /tmp/reconstructed-workspace.tar.gz build/failed',300)
    run(['docker','cp',CONTAINER+':/tmp/reconstructed-workspace.tar.gz',str(R/'reconstructed-workspace.tar.gz')],300)
    state['workspace_sha256']=hashlib.sha256((R/'reconstructed-workspace.tar.gz').read_bytes()).hexdigest()
    # Maven settings are infrastructure, outside the evaluated source tree. The build script
    # copies passed_settings.xml over settings.xml, so update its proxy transport in place.
    dex("cp /home/travis/.m2/passed_settings.xml /tmp/passed_settings.before.xml; sed -i 's#<protocol>https</protocol>#<protocol>http</protocol>#g; s#<host>[^<]*</host>#<host>host.docker.internal</host>#g; s#<port>[^<]*</port>#<port>7890</port>#g' /home/travis/.m2/passed_settings.xml")
    state['infrastructure_change']='Maven HTTP CONNECT proxy at host.docker.internal:7890 via MAVEN_OPTS; existing proxy protocol/host/port in passed_settings.xml updated. Original verifier files unchanged.'
    state['stage']='running_original_verifier';save()
    rc=run(['docker','exec',CONTAINER,'timeout','900','bash','-c','cd /home/travis; bash /verifier/test.sh'],960,False)
    state['verifier_command_exit_code']=rc
    reward=R/'verifier/reward.txt'
    state['reward']=reward.read_text().strip() if reward.exists() else None
    state['stage']='finished' if reward.exists() and rc==0 else 'infrastructure_or_timeout'
except Exception as exc:
    state['stage']='infrastructure_failed';state['error']=str(exc);traceback.print_exc()
finally:
    state['finished_at']=datetime.datetime.now(datetime.timezone.utc).isoformat();save()
    # Keep the container and all evidence for inspection. No cleanup/prune.
