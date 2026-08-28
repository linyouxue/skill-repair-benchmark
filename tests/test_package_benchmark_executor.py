from __future__ import annotations

import os
import stat
import subprocess
import zipfile
from pathlib import Path

import pytest

from tools import package_benchmark_executor as packager


def test_release_zip_uses_git_index_modes_for_permissions(
    tmp_path: Path, monkeypatch
) -> None:
    """Guards the ZIP-mode delivery fix built on commit aadad44acf27."""
    repo = tmp_path / "repo"
    executable = repo / "bin" / "run.sh"
    executable_python = repo / "bin" / "tool.py"
    regular = repo / "README.md"
    untracked = repo / "local-addon.py"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"#!/bin/sh\r\nexit 0\r\n")
    executable_python.write_bytes(b"#!/usr/bin/env python3\r\nprint('ok')\r\n")
    regular.write_bytes(b"release notes\r\n")
    untracked.write_text("VALUE = 1\n", encoding="utf-8")

    subprocess.run(["git", "init", "--quiet"], cwd=repo, check=True)
    subprocess.run(
        ["git", "add", "--", "bin/run.sh", "bin/tool.py", "README.md"],
        cwd=repo,
        check=True,
    )
    subprocess.run(
        [
            "git",
            "update-index",
            "--chmod=+x",
            "--",
            "bin/run.sh",
            "bin/tool.py",
        ],
        cwd=repo,
        check=True,
    )
    monkeypatch.setattr(packager, "ROOT", repo)

    files = packager._source_files()
    output = tmp_path / "release.zip"
    packager._write_archive(output, files, packager._git_index_modes())

    with zipfile.ZipFile(output) as archive:
        infos = {info.filename: info for info in archive.infolist()}
        executable_body = archive.read("benchmark-executor/bin/run.sh")
        executable_python_body = archive.read("benchmark-executor/bin/tool.py")
        regular_body = archive.read("benchmark-executor/README.md")

    expected_permissions = {
        "benchmark-executor/bin/run.sh": 0o755,
        "benchmark-executor/bin/tool.py": 0o755,
        "benchmark-executor/README.md": 0o644,
        "benchmark-executor/local-addon.py": 0o644,
    }
    assert infos.keys() == expected_permissions.keys()
    for name, permissions in expected_permissions.items():
        info = infos[name]
        mode = (info.external_attr >> 16) & 0xFFFF
        assert info.create_system == 3
        assert stat.S_ISREG(mode)
        assert stat.S_IMODE(mode) == permissions
    assert executable_body == b"#!/bin/sh\nexit 0\n"
    assert executable_python_body == b"#!/usr/bin/env python3\nprint('ok')\n"
    assert regular_body == b"release notes\r\n"


def test_release_gate_rejects_crlf_shebang(tmp_path: Path) -> None:
    output = tmp_path / "invalid.zip"
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr(
            "benchmark-executor/bin/tool.py",
            b"#!/usr/bin/env python3\nprint('ok')\r\n",
        )

    with pytest.raises(RuntimeError, match="CRLF in script"):
        packager._validate_archive(output)


@pytest.mark.skipif(os.name == "nt", reason="requires Linux shebang execution")
def test_release_zip_script_runs_directly_on_linux(
    tmp_path: Path, monkeypatch
) -> None:
    repo = tmp_path / "repo"
    probe = repo / "bin" / "probe.sh"
    probe.parent.mkdir(parents=True)
    probe.write_bytes(b"#!/bin/sh\r\nprintf 'release-gate-ok\\n'\r\n")
    subprocess.run(["git", "init", "--quiet"], cwd=repo, check=True)
    subprocess.run(["git", "add", "--", "bin/probe.sh"], cwd=repo, check=True)
    subprocess.run(
        ["git", "update-index", "--chmod=+x", "--", "bin/probe.sh"],
        cwd=repo,
        check=True,
    )
    monkeypatch.setattr(packager, "ROOT", repo)

    output = tmp_path / "release.zip"
    packager._write_archive(
        output, packager._source_files(), packager._git_index_modes()
    )
    extracted = tmp_path / "extracted"
    with zipfile.ZipFile(output) as archive:
        info = archive.getinfo("benchmark-executor/bin/probe.sh")
        archive.extract(info, extracted)
    extracted_probe = extracted / info.filename
    extracted_probe.chmod(stat.S_IMODE((info.external_attr >> 16) & 0xFFFF))

    completed = subprocess.run(
        [extracted_probe],
        cwd=tmp_path,
        env={},
        check=True,
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert completed.stdout == "release-gate-ok\n"
    assert completed.stderr == ""
