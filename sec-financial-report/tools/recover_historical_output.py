"""Recover recorded answers from actual write/read observations, without executing agent code."""
import ast
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
WRITE_ID = "call_7CIlF72VEUG1GsbNMw8SgmyS"
READ_ID = "call_kYqdWlPD6995DdI0yCZHVfc7"


def text(event):
    return event["content"][0]["content"]["text"]


def records(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from records(child)
    elif isinstance(value, list):
        for child in value:
            yield from records(child)


def main():
    acp_path = ROOT / "diagnosis/source_run/trajectory/acp_trajectory.jsonl"
    llm_path = ROOT / "diagnosis/source_run/trajectory/llm_trajectory.jsonl"
    acp = [json.loads(line) for line in acp_path.read_text(encoding="utf-8").splitlines()]
    llm = [json.loads(line) for line in llm_path.read_text(encoding="utf-8").splitlines()]
    write_index, write = next((i, r) for i, r in enumerate(acp) if r.get("tool_call_id") == WRITE_ID)
    read_index, read = next((i, r) for i, r in enumerate(acp) if r.get("tool_call_id") == READ_ID)
    assert write["status"] == read["status"] == "completed" and write_index < read_index
    clean_terminal = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text(write))
    assert "Exit code: 0" in clean_terminal
    script = re.search(r"python3 - <<'PY'\n(.*?)\nPY\n", clean_terminal, re.S).group(1)
    tree = ast.parse(script)
    literal = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == "answers" for t in n.targets))
    assert "with open('/root/answers.json','w') as f:" in script
    assert "json.dump(answers,f,indent=4)" in script
    read_lines = re.findall(r"^\s*(\d+)\t(.*)$", text(read), re.M)
    assert [int(n) for n, _ in read_lines] == list(range(1, 17))
    observed = "\n".join(line for _, line in read_lines)
    assert json.loads(observed) == literal
    assert observed == json.dumps(literal, indent=4)
    observations = [(i+1, r) for i, exchange in enumerate(llm)
                    for r in records(exchange["request"]["body"])
                    if r.get("type") == "function_call_output" and r.get("call_id") == READ_ID]
    assert observations
    assert all(r["output"] == text(read).removeprefix("Tool: file_editor\nResult:\n") for _, r in observations)
    calls = [(i+1, r) for i, exchange in enumerate(llm) for r in records(exchange["response"]["body"])
             if r.get("type") == "function_call" and r.get("call_id") in {WRITE_ID, READ_ID}]
    assert {r["call_id"] for _, r in calls} == {WRITE_ID, READ_ID}
    for _, r in calls:
        args = json.loads(r["arguments"])
        if r["call_id"] == WRITE_ID:
            assert args["command"].split("\n", 1)[1].rsplit("\nPY", 1)[0] == script
        else:
            assert args["command"] == "view" and args["path"] == "/root/answers.json"
    assert not any(r.get("type") == "tool_call" for r in acp[read_index+1:])
    recovered = observed.encode("utf-8")
    destination = ROOT / "diagnosis/recovered_output"
    destination.mkdir(exist_ok=True)
    path = destination / "answers.json"
    if path.exists() and path.read_bytes() != recovered:
        raise ValueError("Refusing to replace a different recovered output")
    path.write_bytes(recovered)
    provenance = {"run_id": "sec-financial-report-original-skill-server-r003",
        "recovery_kind": "original_write_command_and_actual_file_readback",
        "recovered_file": "diagnosis/recovered_output/answers.json", "bytes": len(recovered),
        "recovered_file_sha256": hashlib.sha256(recovered).hexdigest(),
        "independent_original_file_archive": False, "historical_original_file_hash_available": False,
        "semantic_contents_verified": True, "format_matches_recorded_json_dump": True,
        "source_commit": "bee9b0df5b04a300735e5009f5238f5d5c8aaf61",
        "acp": {"path": str(acp_path.relative_to(ROOT)).replace("\\", "/"),
                "sha256": hashlib.sha256(acp_path.read_bytes()).hexdigest(),
                "write_line": write_index+1, "write_tool_call_id": WRITE_ID,
                "read_line": read_index+1, "read_tool_call_id": READ_ID,
                "file_readback_line_numbers": [1, 16], "later_tool_calls": 0},
        "llm": {"path": str(llm_path.relative_to(ROOT)).replace("\\", "/"),
                "sha256": hashlib.sha256(llm_path.read_bytes()).hexdigest(),
                "write_response_lines": [i for i, r in calls if r["call_id"] == WRITE_ID],
                "read_response_lines": [i for i, r in calls if r["call_id"] == READ_ID],
                "read_observation_request_lines": [i for i, _ in observations]},
        "agent_code_executed": False, "answer_values_recomputed_or_corrected": False,
        "model_calls": 0}
    (destination / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"recovered_bytes": len(recovered), "readback_and_write_equal": True,
                      "llm_and_acp_observations_equal": True, "new_model_calls": 0}))


if __name__ == "__main__":
    main()
