"""Launch only this task; API credentials arrive over encrypted SSH stdin."""
import json
import os
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parent
key = sys.stdin.read().strip()
assert key, 'Missing provider key'
if (root/'worker.pid').exists():
    pid = int((root/'worker.pid').read_text())
    assert not Path(f'/proc/{pid}').exists(), 'Worker is already running'
assert not (root/'worker-result.json').exists(), 'Attempt already finished; inspect before retry'
env = dict(os.environ)
for name in list(env):
    if name.lower().endswith('_proxy') or name in ('OPENAI_API_KEY','BENCHFLOW_PROVIDER_API_KEY','BENCHFLOW_PROVIDER_BASE_URL','DOCKER_CONTEXT'):
        env.pop(name, None)
env.update(OPENROUTER_API_KEY=key, PYTHONPATH=str(root/'executor/src'),
    PYTHONDONTWRITEBYTECODE='1', PYTHONUNBUFFERED='1',
    TMPDIR=str(root/'tmp'), XDG_CACHE_HOME=str(root/'cache-home'),
    UV_CACHE_DIR=str(root/'cache-home/uv'), DOCKER_HOST='unix:///run/user/1025/docker.sock',
    DOCKER_CONFIG=str(root/'docker-config'), LLM_MAX_OUTPUT_TOKENS='32768',
    BENCHMARK_EXECUTOR_OPENHANDS_RUNTIME_ARCHIVE=str(root/'cache/openhands-runtime-linux-x86_64.tar.gz'))
env.pop('LLM_REASONING_EFFORT', None)
host='http://127.0.0.1:17890'
container='http://10.0.2.2:17890'
no_proxy='localhost,127.0.0.1,::1,10.0.2.2,host.docker.internal,main'
env.update(HTTP_PROXY=host,HTTPS_PROXY=host,http_proxy=host,https_proxy=host,
    NO_PROXY=no_proxy,no_proxy=no_proxy,AIOHTTP_TRUST_ENV='true',
    BENCHMARK_EXECUTOR_CONTAINER_PROXY_URL=container,
    BENCHMARK_EXECUTOR_CONTAINER_NO_PROXY=no_proxy,
    BENCHMARK_EXECUTOR_BUILD_PROXY_URL=container,
    BENCHMARK_EXECUTOR_BUILD_CONTROL_PROXY_URL=host)
for plane in ['INFRA','VERIFIER']:
    env[f'BENCHMARK_EXECUTOR_{plane}_PROXY_MODE']='explicit'
    env[f'BENCHMARK_EXECUTOR_{plane}_HTTP_PROXY']=container
    env[f'BENCHMARK_EXECUTOR_{plane}_HTTPS_PROXY']=container
    env[f'BENCHMARK_EXECUTOR_{plane}_NO_PROXY']=no_proxy
with (root/'worker.log').open('ab',buffering=0) as log:
    p=subprocess.Popen(['/home/linyuanjing/benchflow_venv_312/bin/python',str(root/'server_worker.py')],
        cwd=root,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
    print(json.dumps({'dispatched_pid':p.pid,'rollout_id':'fix-druid-loophole-cve-opus47-original-skill-server-r001-recovery003'}))
