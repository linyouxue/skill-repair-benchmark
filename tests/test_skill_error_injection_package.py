import hashlib
import json
from pathlib import Path

PACKAGE_ROOT = Path("benchmarks/skill-error-injection")


def test_published_skill_error_cases_are_complete() -> None:
    """Ensure the published case set contains seven minimal file overlays."""

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
        case_root = PACKAGE_ROOT / "cases" / case["case_id"]
        overlay = case_root / "overlay"
        declared = {item["path"]: item["sha256"] for item in case["files"]}
        observed = {
            path.relative_to(overlay).as_posix()
            for path in overlay.rglob("*")
            if path.is_file()
        }

        assert len(declared) == 1
        assert observed == set(declared)
        assert not any(path.is_symlink() for path in overlay.rglob("*"))
        for relative, expected_sha256 in declared.items():
            body = (overlay / relative).read_bytes()
            assert f"sha256:{hashlib.sha256(body).hexdigest()}" == expected_sha256
        assert not any(path.is_file() for path in (case_root / "skills").rglob("*"))
        assert not (case_root / "ground_truth").exists()
