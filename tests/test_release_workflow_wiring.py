from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
REMOVED_UPSTREAM_WORKFLOWS = {
    "integration-final-review.yml",
    "integration-light.yml",
    "integration-scope.yml",
    "internal-preview-release.yml",
    "manifest-parity.yml",
    "public-release.yml",
}


def test_upstream_release_workflows_are_not_shipped() -> None:
    present = {path.name for path in WORKFLOWS.glob("*.yml")}

    assert REMOVED_UPSTREAM_WORKFLOWS.isdisjoint(present)
    assert present == {"test.yml"}


def test_remaining_workflows_cannot_publish_to_pypi() -> None:
    offenders = [
        path.relative_to(REPO_ROOT).as_posix()
        for path in WORKFLOWS.glob("*.yml")
        if "uv publish" in path.read_text(encoding="utf-8")
    ]

    assert offenders == []
