"""JPG-only rollout wiring. No candidate Skill content is generated here."""
import inspect
import asyncio
import fcntl
import json
import os
from pathlib import Path
import shlex


def setup_worker():
    from benchflow.agents.providers import PROVIDERS, ProviderConfig
    from benchflow.acp import runtime
    from benchflow.sandbox.docker import DockerSandbox
    from benchflow.task.verifier_core import Verifier

    PROVIDERS["paratera"] = ProviderConfig(name="paratera",
        base_url="https://llmapi.paratera.com/v1", api_protocol="openai-completions",
        auth_type="api_key", auth_env="PARATERA_API_KEY")
    connect = runtime.connect_acp

    async def vision_connect(*args, **kwargs):
        sandbox = inspect.signature(connect).bind(*args, **kwargs).arguments["env"]
        await sandbox.upload_file(Path(__file__).with_name("openhands_jpg_vision_hook.py"),
                                  "/opt/benchflow/bin/openhands_jpg_vision_hook.py")
        code = (
            "from pathlib import Path; p=Path('/opt/benchflow/bin/openhands-benchmark-executor'); "
            "s=p.read_text(); old='    install_adapter()'+chr(10); "
            "new='    from openhands_jpg_vision_hook import install'+chr(10)+'    install()'+chr(10)+old; "
            "assert s.count(old)==1; p.write_text(s.replace(old,new,1))"
        )
        changed = await sandbox.exec("python3 -c " + shlex.quote(code), user="root", timeout_sec=15)
        if changed.return_code:
            raise RuntimeError("Could not activate JPG native vision wiring")
        return await connect(*args, **kwargs)

    verify = Verifier.verify
    stop = DockerSandbox.stop
    start = DockerSandbox.start

    async def locked_start(sandbox, *args, **kwargs):
        with Path(os.environ.get('BENCHFLOW_JPG_DOCKER_START_LOCK', '/tmp/skillhone-jpg-docker-start.lock')).open('a') as lock:
            await asyncio.to_thread(fcntl.flock, lock.fileno(), fcntl.LOCK_EX)
            try:
                return await start(sandbox, *args, **kwargs)
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    async def capture_and_verify(verifier):
        captured = await verifier._sandbox.exec(
            "mkdir -p /logs/artifacts && tar -czf /logs/artifacts/pre-verifier-workspace.tar.gz -C /app .",
            user="root", timeout_sec=120)
        if captured.return_code:
            raise RuntimeError("JPG pre-verifier archive failed")
        if not verifier._sandbox.is_mounted:
            await verifier._sandbox.download_file("/logs/artifacts/pre-verifier-workspace.tar.gz",
                verifier._rollout_paths.artifacts_dir / "pre-verifier-workspace.tar.gz")
        return await verify(verifier)

    async def preserve(sandbox, delete):
        archive = Path(sandbox._env_vars.host_artifacts_path) / "pre-verifier-workspace.tar.gz"
        if not archive.is_file():
            sandbox._keep_containers = True
        return await stop(sandbox, delete=False)

    runtime.connect_acp = vision_connect
    DockerSandbox.start = locked_start
    Verifier.verify = capture_and_verify
    DockerSandbox.stop = preserve
