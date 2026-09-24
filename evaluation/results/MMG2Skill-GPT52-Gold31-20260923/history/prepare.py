"""Freeze actual GPT-5.2 inputs; never execute the packaged 25-task experiment."""
import hashlib, importlib.util, json, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[1]
SOURCE = ROOT / 'source/MMG2Skill_SkillsBench25_diagnosis'
ARCHIVE = PROJECT.parent / '.codex-staging/skillaxe-causalflow-publish/evaluation/results/GPT52-AllTasks-RepresentativeRuns-20260916'
sys.path.insert(0, str(SOURCE))
spec = importlib.util.spec_from_file_location('packaged_adapter', SOURCE / 'experiments/skillsbench_cf25/run_diagnosis.py')
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)

def read(p): return json.loads(p.read_text(encoding='utf-8'))
def write(p, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
def digest(root):
    h = hashlib.sha256()
    for p in sorted(root.rglob('*'), key=lambda p:p.relative_to(root).as_posix()):
        if p.is_file():
            name=p.relative_to(root).as_posix().encode(); body=p.read_bytes()
            h.update(len(name).to_bytes(8,'big')); h.update(name)
            h.update(len(body).to_bytes(8,'big')); h.update(body)
    return h.hexdigest()

if __name__ == '__main__':
    assert not (ROOT/'manifest.json').exists(), 'Already frozen'
    goldpath=PROJECT/'manual_annotation_runs/gold_repairs/evaluation/gold.json'
    gold=read(goldpath)
    assert len(gold['tasks'])==31
    tasks=[]
    for g in gold['tasks']:
        tid=g['task_id']; selected=ARCHIVE/'tasks'/tid/'selected_run'
        outcome=None
        with (selected/'trajectory/acp_trajectory.jsonl').open() as f:
            for line in f:
                row=json.loads(line)
                if row.get('type')=='agent_iteration_outcome': outcome=row
        assert outcome and outcome.get('skill_bundle_sha256'), tid
        expected=outcome['skill_bundle_sha256'].removeprefix('sha256:')
        candidates=[Path('/home/linyuanjing/skillsbench-v1.1/tasks')/tid/'environment/skills', goldpath.parent/g['original_bundle'], selected/'inputs/skills']
        bundle=next((p for p in candidates if p.is_dir() and digest(p)==expected),None)
        assert bundle, f'No genuine bundle matching historical injection: {tid}'
        dest=ROOT/'originals'/tid/'skills'
        if not dest.exists(): shutil.copytree(bundle,dest)
        assert digest(dest)==expected
        prepared=ROOT/'inputs'/tid
        prepared.mkdir(parents=True,exist_ok=True)
        prompts=read(selected/'prompts.json')
        (prepared/'instruction.txt').write_text('\n\n'.join(prompts),encoding='utf-8')
        if not (prepared/'traj.jsonl').exists(): meta=adapter.convert_trace(selected/'trajectory/acp_trajectory.jsonl',prepared,32768)
        else: meta=read(prepared/'metadata.json')
        meta.update(source_run=str(selected),source_bundle=str(bundle),original_bundle_sha256=expected)
        write(prepared/'metadata.json',meta)
        tasksource=Path('/home/linyuanjing/skillsbench-v1.1/tasks')/tid
        assert (tasksource/'task.md').is_file()
        tasksroot=Path('/home/linyuanjing/skillgen-jobs/mmg2skill-gpt52-gold31-20260923/tasks')
        target=tasksroot/tid
        if not target.exists(): shutil.copytree(tasksource,target)
        # Freeze genuine historical skills for both executor and semantic judge.
        g['original_bundle']=str(dest)
        tasks.append({'task_id':tid,'original_bundle':str(dest),'source_bundle':str(bundle),'original_bundle_sha256':expected,'run_path':str(selected),'approximate_turns':meta['approximate_turns'],'skill_files':[p.relative_to(dest).as_posix() for p in sorted(dest.rglob('SKILL.md'))]})
    write(ROOT/'gold.full.json',gold)
    write(ROOT/'manifest.json',{'method_id':'mmg2skill-gpt52-gold31-20260923','benchmark_version':gold['benchmark_version'],'tasks_root':str(tasksroot),'tasks':tasks})
    write(ROOT/'protocol.json',{'approved':'2026-09-23 Q1=A; Q2-Q4 recommended','method':'MMG2Skill Analyzer + Refiner, no-tutorial SkillsBench adaptation','upstream_commit':'c12d8b1e8998ed76bad2ab85425959f44ca085b8','model':'openai/gpt-5.2','provider':'OpenRouter','reasoning_effort':'omitted','original_skill':'reuse historical GPT-5.2; 31/31 injected bundle digests match','repair_rounds':1,'chunk_size':15,'analysis_max_tokens':32768,'refine_max_tokens':32768,'observation_char_limit':32768,'response_char_limit':32768,'rolling_summary_char_limit':32768,'context_limit_provenance':'full-method configs/config.yaml; packaged 25-task diagnosis-only defaults not used','include_tutorial_in_refine':False,'fresh_iterations':60,'jpg_iterations':65,'max_workers':3,'judge':'openai/gpt-5.5 medium after all workers terminate','gold_variant':'keep semantic Gold and separate F->P all defects TP, FP/FN=0; localization original hits/new TP','gold_input_to_method':False,'usd_cap':None})
    print('Frozen 31 genuine trajectories and matching complete bundles; defects',sum(len(t['defects']) for t in gold['tasks']))
