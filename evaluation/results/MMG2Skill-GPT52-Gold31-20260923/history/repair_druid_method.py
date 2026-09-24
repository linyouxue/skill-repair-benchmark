"""Approved MMG method only; fresh rollout is dispatched to PKU separately."""
import experiment as e
tid='fix-druid-loophole-cve'
e.cf_module().ensure_openrouter_key()
task=next(t for t in e.read(e.ROOT/'manifest.json')['tasks'] if t['task_id']==tid)
e.repair(task)
e.progress(tid,'waiting_remote_fresh',execution_host='pku-server',method_complete=True)
