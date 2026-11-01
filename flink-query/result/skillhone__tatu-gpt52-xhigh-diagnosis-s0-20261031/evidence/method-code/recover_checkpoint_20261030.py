"""Resume the retained PDDL native session through the shared executor."""
import asyncio
import hashlib
import inspect
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

import baseline_gpt52_tatu_20261029 as baseline

ROOT = baseline.DEFAULT_ROOT
IN_POOL = os.environ.get("BENCHFLOW_RECOVERY_IN_POOL") == "1"
RESERVATION = Path(os.environ.get("BENCHFLOW_RECOVERY_RESERVATION_PATH", str(ROOT/"recovery-reservation.json")))
if not RESERVATION.resolve().is_relative_to(ROOT.resolve()):
    raise ValueError("Recovery reservation must stay in this campaign root")


def checkpoint_target(spec):
    task_id, group, repeat = spec["slot"].rsplit("-", 2)
    if task_id not in baseline.TASKS or group not in baseline.GROUPS or repeat not in ("r01", "r02", "r03"):
        raise ValueError("Checkpoint target is outside the authorized input plan")
    match = re.fullmatch(re.escape(spec["slot"]) + r"-a(\d{2})", spec["source"])
    if not match or not re.fullmatch(r"[0-9a-f]{12,64}", spec["container"]) or not re.fullmatch(r"[0-9a-f]{32}", spec["session"]):
        raise ValueError("Checkpoint identity does not match its original slot")
    return dict(spec, task_id=task_id, group=group, attempt=int(match.group(1)))


TARGET = checkpoint_target(json.loads(os.environ.get("BENCHFLOW_RECOVERY_SPEC", "null")) or {
    "slot":"pddl-airport-planning-group_01-r01", "source":"pddl-airport-planning-group_01-r01-a02",
    "container":"be1b46b3fa0a", "session":"004677694a4146909edb043e55a7969b"})
SLOT, SOURCE = TARGET["slot"], TARGET["source"]
_sequence = 1
while ((ROOT / "runs/official-tatu-gpt52" / (SOURCE + f"-checkpoint-{_sequence:02d}")).exists()
       or (ROOT / "slots" / (SOURCE + f"-checkpoint-{_sequence:02d}.json")).exists()):
    _sequence += 1
CONTINUATION = SOURCE + f"-checkpoint-{_sequence:02d}"
CONTAINER, SESSION = TARGET["container"], TARGET["session"]


def checkpoint_chat_model(model):
    if not model.startswith("openai/"):
        raise RuntimeError("Checkpoint routing requires the existing OpenAI-compatible proxy alias")
    return model.removesuffix("-responses-bridge")


def configure_segment_runtime(runtime, *, prior, remaining):
    if prior < 0 or remaining <= 0 or prior + remaining != 60:
        raise ValueError("Recovery segment must use exactly the unspent part of the original 60 steps")
    # This module constant is used only by the host ACP metadata validator.
    # The shared executor/request/config retain their logical 60-step budget;
    # the native continuation truthfully reports the smaller segment cap.
    runtime.MAX_PARENT_ITERATIONS_PER_STEP = remaining


def save_checkpoint_evidence(evidence):
    if not IN_POOL:
        baseline.save(ROOT / "checkpoint-recovery.json", evidence)
    run = ROOT / "runs/official-tatu-gpt52" / CONTINUATION
    if run.is_dir():
        baseline.save(run / "checkpoint-recovery.json", evidence)


def checkpoint_metadata():
    running = subprocess.check_output(["docker", "inspect", CONTAINER, "--format", "{{.State.Running}}"], text=True).strip()
    if running != "true":
        subprocess.run(["docker", "start", CONTAINER], check=True, stdout=subprocess.DEVNULL)
    code = """from pathlib import Path
import hashlib,json
p=Path('/home/agent/.openhands/conversations')/SESSION
events=[json.loads(f.read_text()) for f in sorted((p/'events').glob('event-*.json'))]
responses={e['llm_response_id'] for e in events if e.get('llm_response_id')}
errors=sum(e.get('kind')=='ConversationErrorEvent' for e in events)
guards=sum(e.get('kind')=='MessageEvent' and e.get('llm_message',{}).get('role')=='user' and '[Benchmark executor text-only guard]' in json.dumps(e) for e in events)
c=Path('/logs/agent/checkpoint-parent-counter.json')
counter=json.loads(c.read_text()) if c.exists() else {}
prior=max(len(responses)+errors,int(counter.get('total_started',0)))
h=hashlib.sha256()
for f in sorted((p/'events').glob('event-*.json')):h.update(f.name.encode());h.update(f.read_bytes())
print(json.dumps({'session_id':SESSION,'event_count':len(events),'successful_parent_responses':len(responses),'failed_parent_steps':errors,'persisted_parent_counter':counter.get('total_started'),'prior_parent_iterations':prior,'prior_guard_uses':guards,'events_sha256':h.hexdigest(),'base_state_sha256':hashlib.sha256((p/'base_state.json').read_bytes()).hexdigest()}))
""".replace("/SESSION", "/" + repr(SESSION)).replace("'session_id':SESSION", "'session_id':" + repr(SESSION))
    output = subprocess.check_output(["docker", "exec", CONTAINER, "python3", "-c", code], text=True)
    return json.loads(output)


def worker():
    while True:
        state = baseline.load(ROOT / "state.json")
        live = 0
        for item in state.get("slots",{}).values():
            path = Path(f"/proc/{item.get('pid')}/stat")
            if item.get("status")=="running" and (not IN_POOL or item.get("pid")!=os.getpid()) and path.exists() and path.read_text().split(") ",1)[1].split()[0]!="Z":
                live += 1
        if live < 3:
            break
        time.sleep(5)
    baseline.register_provider()
    os.environ.update(baseline.environment())
    baseline.install_hooks(ROOT)
    from benchflow.acp.client import ACPClient
    from benchflow.acp import runtime
    import benchflow.rollout_planes as planes
    from benchflow.sandbox.docker import DockerSandbox
    from benchmark_executor import BenchmarkExecutor
    import benchflow.agents.install as agent_install
    from benchflow.agents import openhands_runtime_cache as cache

    async def reuse_pinned_runtime(sandbox):
        code = (
            "from pathlib import Path; from importlib.metadata import version; "
            f"assert Path({cache.OPENHANDS_RUNTIME_MARKER!r}).read_text().strip()=={cache.expected_runtime_marker()!r}; "
            "assert version('openhands-sdk')=='1.28.1'; assert version('openhands-tools')=='1.28.1'"
        )
        import shlex
        checked = await sandbox.exec(
            "/opt/benchflow/uv-tools/openhands/bin/python -c " + shlex.quote(code),
            user="root", timeout_sec=30)
        if checked.return_code:
            raise RuntimeError("Retained runtime no longer matches pinned OpenHands identity")
        return {"mode":"retained-pinned-runtime","archive":baseline.ARCHIVE.name}

    agent_install.prepare_openhands_runtime_cache = reuse_pinned_runtime

    metadata = checkpoint_metadata()
    used = metadata["prior_parent_iterations"]
    remaining = 60 - used
    if not 0 < remaining <= 60 or metadata["prior_guard_uses"] > 1:
        raise RuntimeError("Checkpoint budget requires inspection before live continuation")
    configure_segment_runtime(runtime, prior=used, remaining=remaining)
    evidence = dict(metadata, original_rollout=SOURCE, continuation_rollout=CONTINUATION,
                    parent_budget=60, remaining_parent_iterations=remaining,
                    remaining_guard_uses=1-metadata["prior_guard_uses"],
                    injected_user_messages=0, retained_container_id=CONTAINER,
                    started_at=baseline.now())
    save_checkpoint_evidence(evidence)

    async def reuse_start(sandbox, force_build):
        sandbox.session_id = SOURCE
        state = subprocess.check_output(["docker", "inspect", CONTAINER, "--format", "{{.State.Running}}"], text=True).strip()
        if state != "true":
            subprocess.run(["docker", "start", CONTAINER], check=True, stdout=subprocess.DEVNULL)
        check = await sandbox.exec("test -f /home/agent/.openhands/conversations/" + SESSION + "/base_state.json", user="root", timeout_sec=10)
        if check.return_code:
            raise RuntimeError("Retained container has lost the original checkpoint")

    DockerSandbox.start = reuse_start
    # The preserved container is bound to the original rollout's logs; normal
    # executor downloads collect verifier/artifacts into the continuation folder.
    DockerSandbox.is_mounted = property(lambda sandbox: False)

    async def load_original_session(client, cwd="/app", mcp_servers=None):
        return await client.session_load(SESSION, cwd=cwd, mcp_servers=mcp_servers)

    ACPClient.session_new = load_original_session
    original_connect = runtime.connect_acp

    async def connect_checkpoint(*args, **kwargs):
        bound = inspect.signature(original_connect).bind(*args, **kwargs)
        sandbox = bound.arguments["env"]
        await sandbox.upload_file(baseline.HERE / "openhands_checkpoint_hook.py", "/opt/benchflow/bin/openhands_checkpoint_hook.py")
        patch_code = """from pathlib import Path
p=Path('/opt/benchflow/bin/openhands-benchmark-executor')
s=p.read_text()
old='    install_adapter()'+chr(10)
new='    from openhands_checkpoint_hook import install_resume'+chr(10)+'    install_resume()'+chr(10)+old
assert s.count(old)==1
if 'from openhands_checkpoint_hook import install_resume' not in s:p.write_text(s.replace(old,new,1))
"""
        import shlex
        changed = await sandbox.exec("python3 -c " + shlex.quote(patch_code), user="root", timeout_sec=10)
        if changed.return_code:
            raise RuntimeError("Could not install the isolated checkpoint prompt hook")
        agent_env = dict(bound.arguments["agent_env"])
        agent_env["LLM_MODEL"] = checkpoint_chat_model(agent_env["LLM_MODEL"])
        evidence.update(client_model_alias=agent_env["LLM_MODEL"],
                        upstream_protocol="native SDK chat-completions, no Responses conversion",
                        upstream_model="gpt-5.2")
        save_checkpoint_evidence(evidence)
        agent_env.update(BENCHFLOW_RECOVERY_SESSION_ID=SESSION,
                         BENCHFLOW_RECOVERY_PRIOR_ITERATIONS=str(used),
                         BENCHFLOW_RECOVERY_EVENT_COUNT=str(metadata["event_count"]),
                         BENCHMARK_EXECUTOR_MAX_ITERATIONS=str(remaining),
                         BENCHFLOW_OPENHANDS_TEXT_ONLY_RETRY_LIMIT=str(1-metadata["prior_guard_uses"]))
        bound.arguments["agent_env"] = agent_env
        return await original_connect(**bound.arguments)

    runtime.connect_acp = planes.connect_acp = connect_checkpoint
    reservation = baseline.load(RESERVATION)
    for key in ("error_type", "result_json", "finished_at"):
        reservation.pop(key, None)
    reservation.update(status="running", pid=os.getpid(), remaining_parent_iterations=remaining,
                       continuation_rollout_id=CONTINUATION, source_checkpoint=metadata, updated_at=baseline.now())
    baseline.save(RESERVATION, reservation)
    executor = BenchmarkExecutor(tasks_root=ROOT / "tasks" / TARGET["group"], jobs_root=ROOT / "runs",
        model="tatu/gpt-5.2", reasoning_effort="xhigh", experimental_text_only_retry_limit=1)
    result = executor.run(task_id=TARGET["task_id"], condition="original-skill",
                          method_id="official-tatu-gpt52", stage=TARGET["group"], rollout_id=CONTINUATION)
    archive = result.artifacts.task_artifacts_dir / "pre-verifier-workspace.tar.gz"
    iterations = result.agent_iterations
    if iterations is not None and iterations > remaining:
        raise RuntimeError("Continuation exceeded the remaining parent budget")
    original_row = baseline.load(ROOT / "slots" / (SOURCE + ".json"))
    row = {"slot":SLOT,"attempt":TARGET["attempt"],"rollout_id":CONTINUATION,"resumed_from_rollout_id":SOURCE,
        "finished_at":baseline.now(),"execution_ok":result.execution_ok,
        "reward":result.reward,"task_passed":result.task_passed,"model":result.model,
        "provider_protocol":result.provider_protocol,"provider_base_url":result.provider_base_url,
        "agent_iterations":used+iterations if iterations is not None else None,
        "prior_parent_iterations":used,"continuation_parent_iterations":iterations,
        "parent_iteration_budget":60,"provider_requests":result.provider_requests,
        "original_provider_requests":original_row.get("provider_requests"),
        "termination_reason":result.termination_reason,"error_category":result.error_category,
        "verifier_error_category":result.verifier_error_category,"estimated_cost_usd":result.cost_usd,
        "original_estimated_cost_usd":original_row.get("estimated_cost_usd"),
        "estimated_cost_scope":"continuation result reported; original separately retained; no asserted sum",
        "actual_provider_cost_usd":None,"actual_provider_cost_cny":None,
        "n_skill_invocations":result.skill_exposure.native_skill_invocations,
        "skill_preload_verified":result.skill_exposure.verified,
        "workspace_archive_exists":archive.is_file(),
        "workspace_archive_bytes":archive.stat().st_size if archive.is_file() else None,
        "result_json":str(result.artifacts.result_json),"checkpoint_provenance":str(ROOT / "runs/official-tatu-gpt52" / CONTINUATION / "checkpoint-recovery.json")}
    if archive.is_file():
        row["workspace_archive_sha256"] = hashlib.sha256(archive.read_bytes()).hexdigest()
    baseline.save(ROOT / "slots" / (CONTINUATION + ".json"), row)
    successful = result.execution_ok and archive.is_file()
    evidence.update(finished_at=baseline.now(),execution_ok=successful,result_json=row["result_json"],
                    continuation_parent_iterations=iterations,total_parent_iterations=row["agent_iterations"])
    save_checkpoint_evidence(evidence)
    reservation.update(status="complete" if successful else "failed", finished_at=baseline.now(), result_json=row["result_json"])
    baseline.save(RESERVATION, reservation)
    print(json.dumps({"slot":SLOT,"checkpoint_continuation":True,"execution_ok":successful,
                      "reward":result.reward,"prior_iterations":used,"new_iterations":iterations}))


def queued_worker():
    import fcntl
    queue_path = ROOT / ("checkpoint-queue-" + SOURCE + ".json")
    with queue_path.with_suffix(".lock").open("a") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        while baseline.active_recovery(ROOT):
            time.sleep(5)
        if any(x.get("slot")==SLOT and x.get("execution_ok") and x.get("workspace_archive_exists")
               for x in (baseline.load(p) for p in (ROOT/"slots").glob("*.json"))):
            baseline.save(queue_path, {"slot":SLOT,"status":"already-valid","finished_at":baseline.now()})
            return
        baseline.save(ROOT / "recovery-reservation.json", {
            "slot":SLOT,"status":"preparing","pid":os.getpid(),"source_rollout":SOURCE,
            "container_id":CONTAINER,"continuation_rollout_id":CONTINUATION,
            "created_at":baseline.now(),"max_parallel_including_recovery":3})
        baseline.save(queue_path, {"slot":SLOT,"status":"running","pid":os.getpid(),"started_at":baseline.now()})
        worker()
        baseline.save(queue_path, {"slot":SLOT,"status":baseline.load(ROOT/"recovery-reservation.json")["status"],
                                  "pid":os.getpid(),"finished_at":baseline.now()})


def batch_worker(manifest_path):
    """Use one recovery lane for several verified checkpoints, one at a time."""
    import fcntl
    manifest_path = Path(manifest_path)
    with manifest_path.with_suffix(".lock").open("a") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        if baseline.active_recovery(ROOT):
            raise RuntimeError("Another recovery owns the lane")
        record = baseline.load(manifest_path)
        targets = [checkpoint_target(x) for x in record["targets"]]
        record.update(status="running", pid=os.getpid(), slots={}, started_at=baseline.now())
        baseline.save(manifest_path, record)

        def valid(slot):
            return any(x.get("slot")==slot and x.get("execution_ok") and x.get("workspace_archive_exists")
                       for x in (baseline.load(p) for p in (ROOT/"slots").glob("*.json")))

        for spec in targets:
            slot = spec["slot"]
            if valid(slot):
                record["slots"][slot] = {"status":"already-valid"}
                continue
            baseline.save(ROOT/"recovery-reservation.json", {
                "slot":slot,"status":"preparing","pid":os.getpid(),"container_id":spec["container"],
                "source_rollout":spec["source"],"batch_manifest":str(manifest_path),
                "max_parallel_including_recovery":3,"created_at":baseline.now()})
            env = dict(os.environ, BENCHFLOW_RECOVERY_SPEC=json.dumps(spec))
            with (ROOT/"checkpoint-recovery.log").open("ab") as stream:
                child = subprocess.Popen([str(baseline.PYTHON),str(Path(__file__).resolve()),"--worker"],
                    cwd=baseline.EXECUTOR,env=env,stdin=subprocess.DEVNULL,
                    stdout=stream,stderr=subprocess.STDOUT)
            record["slots"][slot] = {"status":"running","pid":child.pid,"source_rollout":spec["source"]}
            baseline.save(manifest_path, record)
            code = child.wait()
            record["slots"][slot].update(status="complete" if valid(slot) else "needs-infrastructure-recovery",
                                          returncode=code)
            baseline.save(manifest_path, record)
        success = all(x["status"] in {"complete","already-valid"} for x in record["slots"].values())
        record.update(status="complete" if success else "needs-infrastructure-recovery",finished_at=baseline.now())
        baseline.save(manifest_path, record)
        path = ROOT/"recovery-reservation.json"
        if path.exists():
            reservation = baseline.load(path)
            if reservation.get("batch_manifest")==str(manifest_path):
                reservation.update(status="complete" if success else "failed",finished_at=baseline.now())
                baseline.save(path, reservation)


if __name__ == "__main__":
    if "--batch-worker" in sys.argv:
        batch_worker(Path(sys.argv[sys.argv.index("--batch-worker")+1]))
    elif "--worker" in sys.argv or "--queued-worker" in sys.argv:
        try:
            queued_worker() if "--queued-worker" in sys.argv else worker()
        except Exception as exc:
            item = baseline.load(RESERVATION)
            if item.get("pid") == os.getpid():
                item.update(status="failed",finished_at=baseline.now(),error_type=type(exc).__name__)
                baseline.save(RESERVATION, item)
            raise
    else:
        state = baseline.load(ROOT / "state.json")
        pid = state["controller_pid"]
        source = dict(item.split(b"=",1) for item in Path(f"/proc/{pid}/environ").read_bytes().split(b"\0") if b"=" in item)
        env = dict(os.environ)
        for name in ("TATU_API_KEY", "TATU_CONFIRMED_PROXY", "TATU_VERIFIER_PROXY"):
            if name.encode() in source:
                env[name] = source[name.encode()].decode()
        assert env.get("TATU_API_KEY")
        if "--batch" in sys.argv:
            path = Path(sys.argv[sys.argv.index("--batch")+1])
            record = baseline.load(path)
            old = Path(f"/proc/{record.get('pid')}/stat")
            if old.exists() and old.read_text().split(") ",1)[1].split()[0]!="Z":
                raise RuntimeError("This checkpoint batch already has a live supervisor")
            if baseline.active_recovery(ROOT):
                raise RuntimeError("Inspect the existing reserved recovery first")
            with (ROOT/"checkpoint-recovery.log").open("ab") as stream:
                child = subprocess.Popen([str(baseline.PYTHON),str(Path(__file__).resolve()),"--batch-worker",str(path)],
                    cwd=baseline.EXECUTOR,env=env,stdin=subprocess.DEVNULL,stdout=stream,
                    stderr=subprocess.STDOUT,start_new_session=True)
            record.update(pid=child.pid,status="queued",queued_at=baseline.now())
            baseline.save(path, record)
            print(json.dumps({"checkpoint_batch_pid":child.pid,"manifest":str(path),"key_saved":False}))
            raise SystemExit(0)
        queue_path = ROOT / ("checkpoint-queue-" + SOURCE + ".json")
        queue = baseline.load(queue_path) if queue_path.exists() else {}
        old_stat = Path(f"/proc/{queue.get('pid')}/stat")
        if old_stat.exists() and old_stat.read_text().split(") ",1)[1].split()[0]!="Z":
            raise RuntimeError("This checkpoint already has a live queued recovery")
        reservation = baseline.load(ROOT / "recovery-reservation.json")
        queued = baseline.active_recovery(ROOT)
        if queued and reservation.get("slot")==SLOT:
            raise RuntimeError("The original checkpoint already has an active recovery")
        for key in ("error_type", "result_json", "finished_at"):
            reservation.pop(key, None)
        reservation.update(status="preparing", continuation_rollout_id=CONTINUATION,
                           remaining_parent_iterations=None, updated_at=baseline.now())
        if not queued:
            baseline.save(ROOT / "recovery-reservation.json", reservation)
        with (ROOT / "checkpoint-recovery.log").open("ab") as stream:
            child = subprocess.Popen([str(baseline.PYTHON),str(Path(__file__).resolve()),"--queued-worker" if queued else "--worker"],
                cwd=baseline.EXECUTOR,env=env,stdin=subprocess.DEVNULL,stdout=stream,
                stderr=subprocess.STDOUT,start_new_session=True)
        if queued:
            baseline.save(queue_path, {"slot":SLOT,"status":"queued","pid":child.pid,
                                      "source_rollout":SOURCE,"created_at":baseline.now()})
        else:
            reservation = baseline.load(ROOT / "recovery-reservation.json")
            reservation.update(pid=child.pid, slot=SLOT, source_rollout=SOURCE, container_id=CONTAINER,
                               updated_at=baseline.now())
            baseline.save(ROOT / "recovery-reservation.json", reservation)
        print(json.dumps({"checkpoint_worker_pid":child.pid,"queued":bool(queued),"slot":SLOT,"key_saved":False}))
