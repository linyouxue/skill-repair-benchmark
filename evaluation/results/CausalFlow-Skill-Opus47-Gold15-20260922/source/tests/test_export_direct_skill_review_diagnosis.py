from __future__ import annotations

from repro_wrappers.defects.export_direct_skill_review_diagnosis import convert_result


def test_convert_direct_review_to_common_diagnosis():
    source = {
        "schema": "causalflow.direct-skill-review-baseline.v1",
        "model": "openai/gpt-5.2",
        "verifier_blind": True,
        "predictions": [
            {
                "skill": "s",
                "file": "s/SKILL.md",
                "start_line": 2,
                "end_line": 2,
                "defect_type": "logic_error",
                "explanation": "wrong rule",
            }
        ],
        "accounting": {
            "seconds": 3.5,
            "cost_usd": 0.01,
            "usage": {"total_tokens": 123},
        },
    }

    diagnosis = convert_result(
        source,
        case_id="dsr-0123456789ab",
        method_id="direct-review",
        source_sha256="abc",
    )

    assert diagnosis["schema"] == "causalflow.skill-defect-diagnosis.v1"
    assert diagnosis["case_id"] == "dsr-0123456789ab"
    assert diagnosis["predictions"] == source["predictions"]
    assert diagnosis["accounting"] == {
        "diagnosis_seconds": 3.5,
        "diagnosis_cost_usd": 0.01,
        "diagnosis_tokens": 123,
    }
    assert diagnosis["source"]["sha256"] == "abc"
