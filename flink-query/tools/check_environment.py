"""Build the Flink image, then compile and run a probe offline as root and agent."""
import argparse
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
PROBE = """import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;
public class DependencyProbe {
    public static void main(String[] args) throws Exception {
        StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();
        env.setParallelism(1);
        env.fromElements("flink-environment-ok").print();
        env.execute("environment-check");
    }
}
"""


def check(image: str) -> None:
    command = """set -euo pipefail
useradd -m -s /bin/bash agent
for user in root agent; do
    work=/tmp/flink-probe-$user
    mkdir -p "$work/src/main/java"
    cp /app/workspace/pom.xml "$work/pom.xml"
    cp /tmp/DependencyProbe.java "$work/src/main/java/DependencyProbe.java"
    chown -R "$user:$user" "$work"
    runuser -u "$user" -- bash -ec 'cd "$1"; mvn --offline --batch-mode clean package -q; /opt/flink/bin/flink run -t local -c DependencyProbe target/LongestSessionPerJob-jar-with-dependencies.jar' bash "$work"
done
"""
    # stdin carries only the synthetic source, with no task answers or model calls.
    shell = "cat > /tmp/DependencyProbe.java\n" + command
    result = subprocess.run(
        ["docker", "run", "--rm", "--network", "none", "--cpus", "4", "--memory", "4g",
         "--hostname", "flink-environment-check", "--add-host", "flink-environment-check:127.0.0.1",
         "-i", "--entrypoint", "bash", image, "-ec", shell],
        input=PROBE, text=True, capture_output=True, timeout=600,
    )
    if result.returncode or result.stdout.count("flink-environment-ok") != 2:
        raise RuntimeError(f"Offline environment check failed\n{result.stdout}\n{result.stderr}")
    print("root and agent both compiled and ran Flink without network access or external Maven volumes")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="flink-query-verified:local")
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument("--maven-repository-url")
    args = parser.parse_args()
    if not args.skip_build:
        build = ["docker", "build", "-t", args.image]
        if args.maven_repository_url:
            build += ["--build-arg", "MAVEN_REPOSITORY_URL=" + args.maven_repository_url]
        subprocess.run([*build, str(ROOT / "environment")], check=True)
    check(args.image)
