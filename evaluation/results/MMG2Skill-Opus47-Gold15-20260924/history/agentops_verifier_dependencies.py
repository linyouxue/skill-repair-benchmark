"""Prepare dependencies only after the agent exits, outside the unchanged verifier timer."""
import json,os,shlex
from pathlib import Path
async def prepare(env,output):
    versions=['3.11.8','3.8.18','3.9.18','3.10.13','3.12.2']
    paths=':'.join('/opt/hostedtoolcache/Python/'+v+'/x64/bin' for v in versions)
    proxy=os.environ['BENCHMARK_EXECUTOR_VERIFIER_HTTP_PROXY']
    command='set -eu\n'+''.join('export '+k+'='+shlex.quote(proxy)+'\n' for k in ['HTTP_PROXY','HTTPS_PROXY','http_proxy','https_proxy'])
    command+=f'''export PATH={paths}:/root/.local/bin:/usr/local/bin:/usr/bin:/bin
export TOX_WORK_DIR=/opt/mmg-agentops-verifier-tox VIRTUALENV_NO_PERIODIC_UPDATE=1
cat > /tmp/agentops-pip-constraints.txt <<'EOF'
langchain==0.0.352
langchain-core==0.1.23
EOF
export PIP_CONSTRAINT=/tmp/agentops-pip-constraints.txt PIP_INDEX_URL=https://pypi.org/simple
unset PIP_EXTRA_INDEX_URL
/opt/hostedtoolcache/Python/3.11.8/x64/bin/python -m pip install tox
cd /home/github/build/failed/AgentOps-AI/agentops
/opt/hostedtoolcache/Python/3.11.8/x64/bin/python -m tox -e py38,py39,py310,py311,py312 --notest
cd /home/github/build
uv init --python 3.10
uv add pytest==8.4.1
uv add pytest-json-ctrf==0.3.5
uv add unidiff==0.7.5
'''
    result=await env.exec(command,user='root',timeout_sec=1800)
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    (output/'agentops-dependency-preparation.json').write_text(json.dumps({'return_code':result.return_code,'stdout':result.stdout,'stderr':result.stderr,'tests_run':False,'verifier_timeout_sec':240},indent=2)+'\n')
    assert result.return_code==0,'AgentOps verifier dependency preflight failed; no automatic model retry'
