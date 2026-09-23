"""Read-only dependency archives copied into a private agent home per run."""
import json
from pathlib import Path
import shlex

SPECS = {
    'seismic-phase-picking': ('weights.tar.gz', '/home/agent/.seisbench'),
    'python-scala-translation': ('coursier.tar.gz', '/home/agent/.cache/coursier'),
}


def dependency_archive(root: Path, task_id: str):
    filename, destination = SPECS[task_id]
    cache = root / task_id
    ready = json.loads((cache / 'ready.json').read_text())
    if ready.get('task_id') != task_id or ready.get('default_offline_probe_passed') is not True:
        raise ValueError(f'Unverified dependency cache: {task_id}')
    archive = cache / filename
    if not archive.is_file():
        raise FileNotFoundError(archive)
    return archive, destination


def activation_script(archive: str, destination: str):
    return (f'mkdir -p {shlex.quote(destination)} && '
            f'tar -xzf {shlex.quote(archive)} -C {shlex.quote(destination)} --no-same-owner && '
            f'chown -R agent:agent {shlex.quote(destination)}')


def replay_mount_and_setup(root: Path, task_id: str):
    archive, destination = dependency_archive(root, task_id)
    remote = '/causalflow-task-dependency-cache.tar.gz'
    return ['-v', f'{archive}:{remote}:ro'], activation_script(remote, destination) + ' || exit 125\n'
