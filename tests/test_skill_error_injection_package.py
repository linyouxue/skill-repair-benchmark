import json
from pathlib import Path

from benchflow.benchmark_executor import build_skill_bundle_manifest

PACKAGE_ROOT = Path("benchmarks/skill-error-injection")


def test_published_skill_error_cases_are_complete() -> None:
    """Ensure the published case set contains seven complete Skill bundles."""

    manifest = json.loads((PACKAGE_ROOT / "manifest.json").read_text(encoding="utf-8"))
    cases = manifest["cases"]

    assert manifest["schema"] == "skill-repair-benchmark.injected-skills.v1"
    assert len(cases) == 7
    assert len({case["case_id"] for case in cases}) == len(cases)
    assert {case["task_id"] for case in cases} == {
        "3d-scan-calc",
        "mario-coin-counting",
        "sec-financial-report",
    }

    for case in cases:
        skills_dir = PACKAGE_ROOT / case["skills_dir"]
        assert skills_dir.is_dir()
        assert list(skills_dir.rglob("SKILL.md"))
        assert not any(path.is_symlink() for path in skills_dir.rglob("*"))
        bundle = build_skill_bundle_manifest(skills_dir)
        assert f"sha256:{bundle.sha256}" == case["skill_bundle_sha256"]
        assert not (PACKAGE_ROOT / "cases" / case["case_id"] / "ground_truth").exists()
