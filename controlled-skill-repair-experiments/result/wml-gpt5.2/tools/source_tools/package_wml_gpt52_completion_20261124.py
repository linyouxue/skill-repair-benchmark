"""Package 22 controlled WML repairs, shared controls, and 5 historical reuse records."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import csv,hashlib,importlib.util,json,os,shutil,subprocess
BASE=Path(__file__).resolve().parent
OUT=BASE/'wml-gpt52-completion-20261124'
OLD=BASE/'controlled55-strict-audit-20261123'
FROZEN=BASE/'controlled55-wml-gpt52-final-20261123'
LOCAL=Path('/private/tmp/controlled55-strict-20261123')
TARGET=BASE.parent/'results/wml-gpt5.2-controlled55'
IDS=['dialogue-parser','data-to-d3','flink-query','manufacturing-equipment-maintenance','pddl-airport-planning']
def load(p):return json.loads(p.read_text())
def save(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2))

def main():
 TARGET.mkdir(exist_ok=True);rows=load(OLD/'AUDIT_RUNS.json');new={r['experiment_id']:r for r in load(OUT/'NEW_ATTEMPT_AUDIT.json')};mapping=[];copies=[]
 def addtree(source,dest,exclude=()):
  for p in source.rglob('*'):
   if p.is_file() and not any(x in p.relative_to(source).parts for x in exclude):copies.append((p,dest/p.relative_to(source)))
 def addfile(source,dest):
  if source.exists():copies.append((source,dest))
 for r in rows:
  name=r['experiment_id'];group='repair' if r['group']=='repairs' else 'control';dest=TARGET/'experiments'/group/name
  selected=r['selected_result_path'];state=r['final_status'];verifier='accepted-original-20261123';reward=r['selected_reward']
  if name in new:
   if new[name]['selected']:
    n=new[name]['selected'];selected=n['result_path'];state=n['status'];reward=n['reward'];verifier=new[name]['verifier_version']
   else:selected=None;state='no_valid_result_after_new_completion' if new[name]['finished'] else 'completion_attempt_running';reward=None
  source_result=Path(selected) if selected else None
  if source_result:
   for previous in (dest/'jobs/selected').glob('*'):
    if previous.is_dir() and previous.name!=source_result.parent.name:
     archived=dest/'prior_selections'/previous.name
     archived.parent.mkdir(parents=True,exist_ok=True)
     if not archived.exists():previous.rename(archived)
   attempt=source_result.parents[3];addtree(source_result.parent,dest/'jobs/selected'/source_result.parent.name,exclude=('inputs',))
   for f in ['RUN_RECORD.json','EXECUTION_PREFLIGHT.json','EXECUTION_AUDIT.json','ATTEMPT_LINK.json','STRICT_AUDIT.json']:
    addfile(attempt/f,dest/f)
   source_task=next((attempt/'staged-task').iterdir());addfile(source_task/'task.md',dest/'task_metadata/task.md');addtree(source_task/'verifier',dest/'task_metadata/verifier')
  else:
   for previous in (dest/'jobs/selected').glob('*'):
    archived=dest/'prior_selections'/previous.name;archived.parent.mkdir(parents=True,exist_ok=True)
    if previous.is_dir() and not archived.exists():previous.rename(archived)
   oldrecord=dest/'RUN_RECORD.json'
   if oldrecord.exists():oldrecord.rename(dest/'PREVIOUS_RUN_RECORD.json')
  record=load(Path(r['original_result_path']).parents[3]/'RUN_RECORD.json')
  if group=='repair':
   addtree(LOCAL/'recovered-candidates'/name,TARGET/'evidence/repair'/name)
   addtree(LOCAL/'recovered-candidates'/name/'skills',TARGET/'skills'/name)
   addtree(FROZEN/'inputs'/name,TARGET/'inputs'/name)
   review=FROZEN/'semantic-review/evidence'/f'{name}.md';addfile(review,TARGET/'evidence/semantic-review'/f'{name}.md')
  mapping.append({'experiment_id':name,'task_id':r['task_id'],'group':r['group'],'condition':record['condition'],'trial_id':record.get('trial_id'),'status':state,'reward':reward,'verifier_version':verifier,'selected_source_result':str(source_result) if source_result else None,'selected_packaged_result':str((dest/'jobs/selected'/source_result.parent.name/'result.json').relative_to(TARGET)) if source_result else None,'candidate_bundle':f'skills/{name}' if group=='repair' else None,'original_result':r['original_result_path'],'prior_attempts':r['confirmation_attempts'],'new_attempt':new[name]['attempt'] if name in new else None,'model':r['model'],'endpoint':r['base_url'],'parent_budget':60})
 for tid in IDS:addtree(OUT/'unhinted-reuse'/tid,TARGET/'unhinted-reuse/zenmux-gpt5.2'/tid)
 supplement=load(OUT/'UNHINTED_SUPPLEMENT_AUDIT.json') if (OUT/'UNHINTED_SUPPLEMENT_AUDIT.json').exists() else None
 if supplement and supplement['selected']:
  selected=Path(supplement['selected']['result_path']);dest=TARGET/'unhinted-reuse/tatumass-gpt5.2-validation/dialogue-parser'
  addtree(selected.parent,dest/'repaired_run')
  addtree(OUT/'unhinted-reuse/dialogue-parser/repaired_skill',dest/'repaired_skill')
  addfile(selected.parents[3]/'RUN_RECORD.json',dest/'RUN_RECORD.json')
  addfile(selected.parents[3]/'ATTEMPT_LINK.json',dest/'ATTEMPT_LINK.json')
 for p in [OUT/'UNHINTED_SUPPLEMENT_PLAN.json',OUT/'UNHINTED_SUPPLEMENT_AUDIT.json',OUT/'INFRASTRUCTURE_RETRY_PLAN.json']:
  addfile(p,TARGET/'evidence'/p.name)
 for p in [OUT/'UNHINTED_REUSE_AUDIT.json',OUT/'unhinted_local_published_integrity.json',OUT/'NEW_ATTEMPT_AUDIT.json',OUT/'ATTEMPT_PLAN.json',OUT/'COMPLETION_SCOPE.json']:
  addfile(p,TARGET/'evidence'/p.name)
 addtree(OUT/'environment-acceptance',TARGET/'evidence/environment-acceptance');addtree(OUT/'verifier-compatibility',TARGET/'evidence/verifier-compatibility')
 for f in ['AUDIT_REPORT.md','AUDIT_SUMMARY.json','AUDIT_RUNS.json','historical_details.json','UNRESOLVED_FINDINGS.json','AUDIT_POLICY.json','historical_core_evidence_integrity.json','skill_condition_source_checks.json','reward_reproduction.json']:
  addfile(OLD/f,TARGET/'evidence/prior-audit'/f)
 for f in ['wml_adapter.py','run_all_repairs.py','prepare_all_candidates.py']:
  addfile(FROZEN/'recovered-method'/f,TARGET/'method'/f)
 addfile(Path('/Users/king/Downloads/03_论文科研/skill-repair-controlled-datasets-20261020/organizer/score_template.csv'),TARGET/'evidence/official_score_template_header.csv')
 save(TARGET/'selection_manifest.json',mapping)
 errors=[];done=[]
 def copy(pair):
  src,dst=pair;dst.parent.mkdir(parents=True,exist_ok=True)
  if dst.exists() and dst.stat().st_size==src.stat().st_size:
   # Retain only actual matching files when a package is refreshed.
   if hashlib.sha256(dst.read_bytes()).digest()==hashlib.sha256(src.read_bytes()).digest():return str(dst)
  temp=dst.with_name(dst.name+'.copy-in-progress')
  for _ in range(3):
   try:
    q=subprocess.run(['cp','-p',str(src),str(temp)],capture_output=True,timeout=15)
    if q.returncode==0 and temp.stat().st_size==src.stat().st_size:temp.replace(dst);return str(dst)
   except subprocess.TimeoutExpired:pass
   if temp.exists():temp.unlink()
  raise RuntimeError(str(src))
 with ThreadPoolExecutor(max_workers=10) as pool:
  futures={pool.submit(copy,c):c for c in copies}
  for f in as_completed(futures):
   try:done.append(f.result())
   except Exception as e:errors.append(str(e));print('COPY_ERROR',e,flush=True)
 save(OUT/'PACKAGE_COPY_STATUS.json',{'planned':len(copies),'copied':len(done),'errors':errors,'target':str(TARGET)})
 score=list(csv.DictReader((FROZEN/'reports/score_template.final.csv').open()));index={r['experiment_id']:r for r in mapping}
 for r in score:
  selected=index[r['experiment_id']];r['native_task_passed']='' if selected['reward'] is None else str(selected['reward']==1).lower();r['native_reward']='' if selected['reward'] is None else str(selected['reward']);r['evidence_path']='evidence/semantic-review/'+r['experiment_id']+'.md';r['reviewer']='Codex (AI-assisted semantic review; not independent human sign-off)'
  gold=index.get(r['task_id']+'__full_gold');r['positive_control_passed']='' if not gold or gold['reward'] is None else str(gold['reward']==1).lower()
  baseline=index.get(r['experiment_id']+'__condition_baseline') if r['condition']=='leave_one_out' else index.get(r['task_id']+'__original')
  r['condition_baseline_passed']='' if not baseline or baseline['reward'] is None else str(baseline['reward']==1).lower()
  r['notes']+=' | Execution selection refreshed on 20261124; verifier='+selected['verifier_version']+'; candidate and semantic labels unchanged. Native pass does not establish semantic repair.'
 (TARGET/'reports').mkdir(exist_ok=True)
 with (TARGET/'reports/score_template.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(score[0]));w.writeheader();w.writerows(score)
 reuse=load(OUT/'UNHINTED_REUSE_AUDIT.json') if (OUT/'UNHINTED_REUSE_AUDIT.json').exists() else []
 summary={'controlled_repair_entries':sum(r['group']=='repairs' for r in mapping),'controlled_valid_execution_entries':sum(r['group']=='repairs' and r['status'] in ['valid_pass','valid_fail'] for r in mapping),'controlled_passes':sum(r['group']=='repairs' and r['status']=='valid_pass' for r in mapping),'controlled_failures':sum(r['group']=='repairs' and r['status']=='valid_fail' for r in mapping),'shared_control_entries':sum(r['group']=='controls' for r in mapping),'unhinted_reuse_entries':len(reuse),'unhinted_statuses':[{k:r.get(k) for k in ['task_id','status','reward','issues']} for r in reuse],'semantic_review_type':'AI-assisted; no independent human sign-off','all_planned_new_runs_complete':all(r['finished'] for r in new.values()),'package_copy_errors':errors,'strict_archival_limit':'Historical files absent from source are not reconstructed. Task outputs are present only when original verifier retained them or new run exported them.','reused_configuration_difference':'Historical unhinted runs use zenmux/openai/gpt-5.2 and Zenmux endpoint; controlled runs use Tatumass GPT52. Never pool as same-config randomized causal comparison.'}
 summary['unhinted_historical_clean_results']=sum(r['status'] in ['valid_pass','valid_fail'] for r in reuse)
 summary['unhinted_dialogue_supplemental_validation']=({k:supplement['selected'].get(k) for k in ['status','reward','model','base_url','skill_hash']} if supplement and supplement['selected'] else None)
 summary['unhinted_tasks_with_clean_reuse_or_authorized_supplement']=summary['unhinted_historical_clean_results']+int(bool(supplement and supplement['selected']))
 summary['shared_controls_valid']=sum(r['group']=='controls' and r['status'] in ['valid_pass','valid_fail'] for r in mapping)
 save(TARGET/'summary.json',summary)
 (TARGET/'README.md').write_text('''# WML / GPT-5.2 / controlled experiments

本目录交付 22 条 WML 受控修复实验，33 条可跨方法复用的直接执行对照，以及 5 题按分工要求复用的历史无提示 WML 修复结果。先看 summary.json 与 selection_manifest.json；尚未完成的运行不能当成最终结果。

- skills/<trial>/：最终冻结、实际 rollout 使用的完整 WML 修后包。
- inputs/<trial>/、evidence/repair/<trial>/：隔离修复输入、WML 两阶段诊断与修复响应及用量。
- experiments/repair/<trial>/jobs/selected/<rollout>/：选定模型执行、verifier 与原始模型轨迹。
- experiments/control/<condition>/jobs/selected/<rollout>/：同配置直接执行对照，不能当成无提示 WML 修复。
- reports/score_template.csv：官方 22 行模板，保留目标修复/其他 Gold 保留的 AI 辅助复核标注；任务 pass/fail 不能替代语义评分。
- unhinted-reuse/zenmux-gpt5.2/<task>/：5 题已发布的历史无提示结果，保留原模型、端点、预算和轨迹；与 Tatumass 受控结果分开列示。
- unhinted-reuse/tatumass-gpt5.2-validation/dialogue-parser/：用户授权的冻结历史 Skill 补充执行验证；原 Zenmux 末尾异常仍保留，不改写为正常运行。
- evidence/environment-acceptance/、evidence/verifier-compatibility/：本轮参考验收、用户授权的 D3 SVG 兼容差异。D3 v1 与原 verifier 分数分开记录，任务、Gold 和输入未改。

历史所有尝试仍保留在 source work 目录及审计目录；selection_manifest.json 提供旧/新 attempt 和原文件路径。此整理不覆盖原记录，不从模型文字或评分 JSON 重建产物。历史归档不足和运行末尾的异常均如实披露在审计文件中。未声称这是独立人工复核。

无提示历史配置为 Zenmux GPT-5.2，受控配置为 Tatumass GPT-5.2，按分工复用，但不是严格同端点配对实验，不合并计算同配置修复收益。完整运行轨迹导出后见 trajectory_timelines/。
''')
 print('PACKAGED',summary,flush=True)
if __name__=='__main__':main()
