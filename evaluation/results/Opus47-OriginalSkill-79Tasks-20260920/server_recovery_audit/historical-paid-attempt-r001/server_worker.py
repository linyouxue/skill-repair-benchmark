"""One isolated server attempt, using the current local batch worker unchanged."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
BATCH = ROOT / 'batches/opus47-openrouter-v1.1-20260919'
sys.path.insert(0, str(BATCH))
import run_batch as runner
import infra_support
import benchflow.providers.litellm_runtime as runtime
import benchflow.rollout_planes as planes

runner.base.TASKS_ROOT = ROOT / 'tasks'
runner.base.RUNS_ROOT = ROOT / 'runs'
runner.base.WORKER_CWD = ROOT / 'worker-cwd'
runner.base.DOCKER_START_LOCK_PATH = ROOT / 'docker-start.lock'
infra_support.PYTHON_ARCHIVE = ROOT / 'cache/opus47-agent-python312.tar.gz'
infra_support.UV_ARCHIVE = ROOT / 'cache/uv-0.9.7-linux-x86_64.tar.gz'
infra_support.OUTPUT_PATHS['fix-druid-loophole-cve'] = ['/root/patches']
# This existing rootless daemon permits host-loopback access via slirp.
# Keep the provider listener private to the host loopback interface.
runtime._host_bind_address = lambda environment: '127.0.0.1'
runtime._docker_host_address = lambda: '10.0.2.2'
original_setup = planes.setup_sandbox_user
async def setup(env, sandbox_user, workspace, *, timeout_sec=120):
    return await original_setup(env, sandbox_user, workspace, timeout_sec=900)
planes.setup_sandbox_user = setup
original_deploy = planes.deploy_skills
async def deploy(env, task_path, skills_dir, agent_cfg, sandbox_user, agent_cwd, skills_sandbox_dir=None):
    # A reused baseline does not include the temporary Dockerfile's injected COPY.
    # Upload the exact frozen skill bundle, then keep the original fidelity checks.
    assert skills_dir is not None
    await env.upload_dir(Path(skills_dir), skills_sandbox_dir or '/skills')
    return await original_deploy(env, task_path, skills_dir, agent_cfg, sandbox_user, agent_cwd, skills_sandbox_dir=skills_sandbox_dir)
planes.deploy_skills = deploy
original_create = planes.DefaultRolloutPlanes.create_environment
def create(self, *args, **kwargs):
    env = original_create(self, *args, **kwargs)
    env.task_env_config = env.task_env_config.model_copy(update={
        'docker_image': json.loads((ROOT/'server_execution.json').read_text())['baseline_image_id']
    })
    env._env_vars.prebuilt_image_name = env.task_env_config.docker_image
    return env
planes.DefaultRolloutPlanes.create_environment = create
original_compose = runner.base.DockerSandbox._run_docker_compose_command
async def compose(self, command, *args, **kwargs):
    command = list(command)
    # The baseline image is shared with other experiments and must be retained.
    if command and command[0] == 'down' and '--rmi' in command:
        index = command.index('--rmi')
        del command[index:index+2]
    return await original_compose(self, command, *args, **kwargs)
runner.base.DockerSandbox._run_docker_compose_command = compose

if '--check' in sys.argv:
    print('Pinned batch worker imported; server-only paths and baseline configured.')
else:
    args = argparse.Namespace(task_id='fix-druid-loophole-cve',
        rollout_id='fix-druid-loophole-cve-opus47-original-skill-server-r001-recovery003',
        worker_output=str(ROOT/'worker-result.json'), worker_nonce='opus47-server-20260920-r001',
        text_only_retry_limit=1)
    (ROOT/'worker.pid').write_text(str(os.getpid()))
    try:
        asyncio.run(runner.run_attempt_worker(args))
    finally:
        (ROOT/'worker.pid').unlink(missing_ok=True)
