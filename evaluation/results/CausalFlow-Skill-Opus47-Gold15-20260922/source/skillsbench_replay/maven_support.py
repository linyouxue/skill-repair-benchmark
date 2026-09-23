"""Prepare Maven dependencies without replaying task commands or task source.

Only the original pom.xml enters the disposable cache-population container.
Every replay receives a private copy of the repository; project build outputs
and task data are never cached or mounted by this module.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from xml.sax.saxutils import escape


def proxy_settings(proxy_url: str) -> str:
    parsed = urlsplit(proxy_url)
    if parsed.scheme != 'http' or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Maven cache requires a credential-free HTTP proxy URL')
    host = parsed.hostname
    if host in {'127.0.0.1', 'localhost', '::1'}:
        host = 'host.docker.internal'
    return (
        '<settings xmlns="http://maven.apache.org/SETTINGS/1.0.0"><proxies>'
        '<proxy><id>causalflow-cache</id><active>true</active><protocol>http</protocol>'
        f'<host>{escape(host)}</host><port>{parsed.port or 80}</port>'
        '<nonProxyHosts>localhost|127.0.0.1</nonProxyHosts></proxy>'
        '</proxies></settings>\n'
    )


def _identity(task_dir: Path, image: str) -> dict:
    pom = task_dir / 'environment/workspace/pom.xml'
    return {
        'task_id': task_dir.name,
        'pom_sha256': hashlib.sha256(pom.read_bytes()).hexdigest(),
        'image_id': subprocess.check_output(
            ['docker', 'image', 'inspect', '--format', '{{.Id}}', image], text=True
        ).strip(),
        'repository_source': 'https://repo.maven.apache.org/maven2',
        'contains_task_source_or_outputs': False,
    }


def central_gateway(proxy_url: str):
    """Maven uses plain HTTP locally; curl handles upstream Central TLS.

    This forwards only Maven Central GET/HEAD paths, never arbitrary URLs.
    It avoids the observed Java TLS handshake failures without changing bytes.
    """
    class CentralHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if not self.path.startswith('/') or '..' in self.path or '?' in self.path:
                self.send_error(400)
                return
            url = 'https://repo.maven.apache.org/maven2' + self.path
            for attempt in range(3):
                try:
                    # curl negotiates HTTP/2 and enforces a total transfer
                    # limit; urllib's socket timeout allowed truncated large
                    # JAR transfers to linger for many minutes.
                    fetched = subprocess.run(
                        ['curl', '--fail', '--silent', '--show-error',
                         '--connect-timeout', '10', '--max-time', '75',
                         '--proxy', proxy_url, '--write-out', '\n%{http_code}', url],
                        capture_output=True, timeout=80, check=False)
                    content, _, status = fetched.stdout.rpartition(b'\n')
                    if status in (b'404', b'400'):
                        self.send_error(int(status))
                        return
                    if fetched.returncode or status != b'200':
                        raise OSError(f'Central transfer failed: curl={fetched.returncode}, HTTP={status!r}')
                    self.send_response(200)
                    self.send_header('Content-Length', str(len(content)))
                    self.end_headers()
                    if self.command != 'HEAD':
                        self.wfile.write(content)
                    return
                except BrokenPipeError:
                    return
                except (OSError, TimeoutError, subprocess.TimeoutExpired):
                    pass
                if attempt < 2:
                    time.sleep(1 + attempt)
            self.send_error(502, 'Maven Central download failed')

        do_HEAD = do_GET

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(('0.0.0.0', 0), CentralHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def validate_normal_commands(task_dir: Path, image: str, target: Path) -> None:
    """Prove default settings work with network disabled and no -s/-o flag."""
    script = '''set -eu
mkdir -p /tmp/cache-probe/src/main/java /root/.m2/repository
cp -a /cache/. /root/.m2/repository/
cp /input/pom.xml /tmp/cache-probe/pom.xml
printf 'public class CacheProbe { public static void main(String[] args) {} }\\n' > /tmp/cache-probe/src/main/java/CacheProbe.java
cd /tmp/cache-probe
mvn -q -DskipTests package
mvn -q dependency:build-classpath -Dmdep.outputFile=/tmp/cp.txt
test -s /tmp/cp.txt
'''
    command = ['docker', 'run', '--rm', '--network', 'none', '--user', '0',
               '--entrypoint', '/bin/bash', '--cpus', '2', '--memory', '2g',
               '-v', f'{target / "repository"}:/cache:ro',
               '-v', f'{task_dir / "environment/workspace/pom.xml"}:/input/pom.xml:ro',
               image, '-lc', script]
    with (target / 'default-settings-probe.log').open('w', encoding='utf-8') as log:
        result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                                timeout=180, check=False)
    if result.returncode:
        raise RuntimeError('Maven default-settings probe failed; cache is not ready')


def repository_archive(target: Path) -> Path:
    archive = target / 'repository.tar.gz'
    with tarfile.open(archive, 'w:gz') as tar:
        for child in sorted((target / 'repository').iterdir()):
            tar.add(child, arcname=child.name)
    return archive


def prepare_maven_support(task_dir: Path, image: str, cache_root: Path,
                          *, proxy_url: str | None = None, timeout: int = 2400) -> Path:
    """Return a validated cache directory, downloading only on cache miss.

    This is infrastructure preparation, not an agent rollout. No task source,
    Skill, verifier or Gold data enters the disposable probe container.
    """
    task_dir, cache_root = Path(task_dir).resolve(), Path(cache_root).resolve()
    if task_dir.name != 'flink-query':
        raise ValueError('Maven support is scoped to flink-query')
    expected = _identity(task_dir, image)
    target = cache_root / 'flink-query'
    marker = target / 'ready.json'
    if marker.exists():
        ready = json.loads(marker.read_text())
        if ready.get('identity') != expected or not ready.get('offline_probe_passed'):
            raise ValueError('Maven cache identity differs; use a new cache directory')
        if not (target / 'repository').is_dir():
            raise ValueError('Validated Maven cache repository is missing')
        if not ready.get('default_settings_network_disabled_probe_passed'):
            validate_normal_commands(task_dir, image, target)
            ready['default_settings_network_disabled_probe_passed'] = True
            ready['archive'] = str(repository_archive(target))
            marker.write_text(json.dumps(ready, indent=2) + '\n', encoding='utf-8')
        return target
    target.mkdir(parents=True, exist_ok=True)
    (target / 'repository').mkdir(exist_ok=True)
    proxy = proxy_url or os.environ.get('HTTPS_PROXY') or os.environ.get('HTTP_PROXY')
    if not proxy:
        raise ValueError('An explicit HTTP proxy is required for Maven preparation')
    proxy_settings(proxy)  # Validate without persisting credentials.
    gateway = central_gateway(proxy)
    gateway_url = f'http://host.docker.internal:{gateway.server_port}'
    (target / 'settings.xml').write_text(
        '<settings><mirrors><mirror><id>central</id><mirrorOf>central</mirrorOf>'
        f'<url>{gateway_url}</url></mirror></mirrors></settings>\n', encoding='utf-8')
    # This tiny unrelated class exercises the exact packaging plugins while
    # keeping benchmark Java code and generated answers outside the cache.
    script = '''set -eu
mkdir -p /tmp/cache-probe/src/main/java
cp /input/pom.xml /tmp/cache-probe/pom.xml
printf 'public class CacheProbe { public static void main(String[] args) {} }\n' > /tmp/cache-probe/src/main/java/CacheProbe.java
cd /tmp/cache-probe
mvn -U -B -ntp -s /cache/settings.xml -Dmaven.repo.local=/cache/repository -DskipTests package dependency:build-classpath -Dmdep.outputFile=/tmp/cache-classpath.txt
rm -rf /tmp/cache-probe/target
mvn -o -B -ntp -s /cache/settings.xml -Dmaven.repo.local=/cache/repository -DskipTests package dependency:build-classpath -Dmdep.outputFile=/tmp/cache-classpath-offline.txt
'''
    command = ['docker', 'run', '--rm', '--user', '0', '--entrypoint', '/bin/bash',
               '--cpus', '2', '--memory', '2g',
               '-v', f'{target}:/cache',
               '-v', f'{task_dir / "environment/workspace/pom.xml"}:/input/pom.xml:ro',
               image, '-lc', script]
    try:
        with (target / 'prepare.log').open('a', encoding='utf-8') as log:
            result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                                    timeout=timeout, check=False)
    finally:
        gateway.shutdown()
        gateway.server_close()
    if result.returncode:
        raise RuntimeError(f'Maven cache preparation failed ({result.returncode}); see {target / "prepare.log"}')
    files = [p for p in (target / 'repository').rglob('*') if p.is_file()]
    if not any(p.suffix == '.jar' for p in files):
        raise RuntimeError('Maven cache contains no dependency JARs')
    validate_normal_commands(task_dir, image, target)
    archive = repository_archive(target)
    marker.write_text(json.dumps({'identity': expected, 'offline_probe_passed': True,
                                 'default_settings_network_disabled_probe_passed': True,
                                 'archive': str(archive),
                                 'repository_file_count': len(files),
                                 'repository_bytes': sum(p.stat().st_size for p in files)},
                                indent=2) + '\n', encoding='utf-8')
    return target


def replay_mount_and_setup(cache_dir: Path) -> tuple[list[str], str]:
    """Return Docker mounts and root setup to run before dropping to agent.

    Mount args contain only Maven repository files. The copy is deliberately
    writable/private: original Maven commands may update their own metadata.
    """
    cache_dir = Path(cache_dir).resolve()
    ready = json.loads((cache_dir / 'ready.json').read_text())
    if (not ready.get('offline_probe_passed')
            or not ready.get('default_settings_network_disabled_probe_passed')
            or not (cache_dir / 'repository').is_dir()):
        raise ValueError('Maven cache has not passed its offline probe')
    mount = ['-v', f'{cache_dir / "repository"}:/causalflow-maven-repository:ro']
    setup = ('mkdir -p /home/agent/.m2/repository || exit 125\n'
             'cp -a /causalflow-maven-repository/. /home/agent/.m2/repository/ || exit 125\n'
             'chown -R agent:agent /home/agent/.m2 || exit 125\n')
    return mount, setup


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task-dir', type=Path, required=True)
    parser.add_argument('--image', required=True)
    parser.add_argument('--cache-root', type=Path, required=True)
    parser.add_argument('--proxy-url')
    args = parser.parse_args()
    print(prepare_maven_support(args.task_dir, args.image, args.cache_root,
                                proxy_url=args.proxy_url))
