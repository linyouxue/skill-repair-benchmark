"""Resolve the unchanged task POM during image build for root and new users."""
from pathlib import Path
import os
import shutil
import subprocess
from xml.sax.saxutils import escape


project = Path("/tmp/flink-maven")
settings = Path("/etc/maven/settings.xml")
repository = os.environ.get("MAVEN_REPOSITORY_URL", "https://repo.huaweicloud.com/repository/maven/")
settings.write_text(
    '<settings xmlns="http://maven.apache.org/SETTINGS/1.0.0">'
    '<mirrors><mirror><id>central</id><mirrorOf>*</mirrorOf>'
    f'<url>{escape(repository)}</url></mirror></mirrors>'
    '<offline>false</offline></settings>\n',
    encoding="utf-8",
)
probe = project / "src/main/java/DependencyProbe.java"
probe.parent.mkdir(parents=True)
probe.write_text("public class DependencyProbe {}\n", encoding="utf-8")
subprocess.run(
    ["mvn", "--batch-mode", "--no-transfer-progress", "clean", "package", "-q"],
    cwd=project,
    check=True,
)
settings.write_text(settings.read_text().replace("<offline>false</offline>", "<offline>true</offline>"))
shutil.copytree("/root/.m2", "/etc/skel/.m2", dirs_exist_ok=True)
shutil.rmtree(project)
