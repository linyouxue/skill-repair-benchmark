"""Run the frozen evaluator once after execution review, checkpointing every response."""
import fcntl
import hashlib
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from experiment import cf_module, load, now, read, write
from runtime_environment import ensure_runtime_environment


def main():
    lock = (ROOT / 'gold-review.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    gate = read(ROOT / 'final-review/execution-audit-gate.json')
    assert gate['approved_for_semantic_evaluation'] is True
    state = read(ROOT / 'batch_state.json')
    assert len(state['tasks']) == 15
    assert all(t['phase'] == 'finished' for t in state['tasks'].values())
    output = ROOT / 'gold-evaluation'
    assert not output.exists(), 'Existing Gold output must be reconciled; never repeat the batch.'
    ensure_runtime_environment()
    cf_module().ensure_openrouter_key()
    import openai
    from openai.types.chat import ChatCompletion
    real_client = openai.OpenAI
    cache = ROOT / 'gold-api-checkpoints'
    cache.mkdir(exist_ok=True)

    class RecordedJudge:
        def __init__(self, **kwargs):
            self.client = real_client(**kwargs)
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

        def create(self, **parameters):
            digest = hashlib.sha256(json.dumps(parameters, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            base = cache / digest
            req = base.with_suffix('.request.json')
            response = base.with_suffix('.response.json')
            pending = base.with_suffix('.pending.json')
            if req.exists():
                assert read(req) == parameters
            else:
                write(req, parameters)
            if response.exists():
                return ChatCompletion.model_validate(read(response))
            assert not pending.exists(), 'Uncertain prior request: reconcile before any resend.'
            write(pending, {'started_at': now(), 'request_sha256': digest})
            try:
                result = self.client.chat.completions.create(**parameters)
                write(response, result.model_dump(exclude_none=True))
                print(now(), 'judge_response_saved', digest, result.id, flush=True)
                return result
            except Exception as exc:
                write(base.with_suffix('.error.json'), {'type': type(exc).__name__, 'error': str(exc), 'at': now()})
                raise

        def close(self):
            self.client.close()

    openai.OpenAI = RecordedJudge
    evaluator = load('_frozen_mmg_gold_evaluator', ROOT / 'evaluate_skill_diagnosis_repair.py')
    args = [
        '--gold', str(ROOT / 'gold.subset.json'),
        '--submission', str(ROOT / 'submission/submission.json'),
        '--output', str(output), '--max-input-chars', '2000000',
        '--execute', '--judge-model', 'openai/gpt-5.5', '--omit-temperature',
        '--reasoning-effort', 'medium', '--max-output-tokens', '8192', '--timeout', '240',
    ]
    write(ROOT / 'gold-review-launch.json', {'started_at': now(), 'pid': os.getpid(), 'arguments': args, 'execution_audit_gate': str(ROOT / 'final-review/execution-audit-gate.json')})
    state.update(status='semantic_evaluation', gold_evaluation='running', gold_pid=os.getpid())
    write(ROOT / 'batch_state.json', state)
    rc = evaluator.main(args)
    summary = read(output / 'summary.json') if (output / 'summary.json').exists() else {}
    complete = rc == 0 and summary.get('status') == 'complete'
    state = read(ROOT / 'batch_state.json')
    state.update(status='ready_for_final_report' if complete else 'gold_review_required', gold_evaluation='complete' if complete else 'needs_review' if rc == 1 else 'error', gold_exit_code=rc, gold_finished_at=now())
    write(ROOT / 'batch_state.json', state)
    print(now(), 'gold_exit', rc, flush=True)
    return rc


if __name__ == '__main__':
    raise SystemExit(main())
