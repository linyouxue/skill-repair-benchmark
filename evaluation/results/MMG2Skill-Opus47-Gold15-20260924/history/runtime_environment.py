"""Restore the approved launch.sh environment when a controller was resumed directly."""
import os
from pathlib import Path

def ensure_runtime_environment():
    root=Path(__file__).resolve().parent
    archive='/home/linyuanjing/.cache/benchmark-executor/openhands-cli/2df8a2835d3f1bd2f2eadf5a7a2e1ad0dfb0d271/openhands-runtime-linux-x86_64.tar.gz'
    host='http://127.0.0.1:7890';container='http://host.docker.internal:7890'
    no_proxy='localhost,127.0.0.1,::1,host.docker.internal,main'
    values={'BENCHMARK_EXECUTOR_OPENHANDS_RUNTIME_ARCHIVE':archive,
        'PYTHONPATH':':'.join((str(root/'source/MMG2Skill_SkillsBench25_diagnosis'),str(root.parents[1]/'causalflow_runs/opus47-gold15-20260922/.deps'),str(root.parents[2]/'skill-repair-benchmark/src'))),
        'HTTP_PROXY':host,'HTTPS_PROXY':host,'http_proxy':host,'https_proxy':host,
        'NO_PROXY':no_proxy,'no_proxy':no_proxy,'AIOHTTP_TRUST_ENV':'true',
        'BENCHMARK_EXECUTOR_CONTAINER_PROXY_URL':container,
        'BENCHMARK_EXECUTOR_CONTAINER_NO_PROXY':no_proxy,
        'BENCHMARK_EXECUTOR_BUILD_PROXY_URL':container,
        'BENCHMARK_EXECUTOR_BUILD_CONTROL_PROXY_URL':host,
        'BENCHMARK_EXECUTOR_UBUNTU_APT_MIRROR_HOST':'mirrors.tuna.tsinghua.edu.cn',
        'LLM_MAX_OUTPUT_TOKENS':'32768','PYTHONUNBUFFERED':'1'}
    for plane in ('INFRA','VERIFIER'):
        prefix=f'BENCHMARK_EXECUTOR_{plane}_'
        values.update({prefix+'PROXY_MODE':'explicit',prefix+'HTTP_PROXY':container,
            prefix+'HTTPS_PROXY':container,prefix+'NO_PROXY':no_proxy})
    # Match launch.sh's explicit exports, including its task-specific NO_PROXY.
    os.environ.update(values)
    assert Path(os.environ['BENCHMARK_EXECUTOR_OPENHANDS_RUNTIME_ARCHIVE']).is_file()
    os.environ.pop('LLM_REASONING_EFFORT',None)
    return values
