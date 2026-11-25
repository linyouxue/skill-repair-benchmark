"""Package 22 controlled repairs and 5 reused no-hint tasks; never change model evidence."""
import json,hashlib,shutil,csv,os,zipfile
from pathlib import Path
from datetime import datetime,timezone
W=Path(__file__).parent;B=Path('/Users/king/Library/Application Support/SkillTTA/controlled-gpt52');L=B/'audits/controlled55-strict-20261124';S=L/'audit-evidence';F=B/'final/SkillTTA-gpt52-tatumass-Controlled55';D=W/'SkillTTA-GPT52-Controlled22-NoHint5';D.mkdir(exist_ok=True);gaps=[];copied=[]
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def cp(src,dest):
 src=Path(src);dest=Path(dest)
 if not src.exists():gaps.append({'source':str(src),'reason':'not_present'});return
 if src.is_dir():
  for p in src.rglob('*'):
   if p.is_file():cp(p,dest/p.relative_to(src))
  return
 if getattr(src.stat(),'st_flags',0)&0x40000000:gaps.append({'source':str(src),'reason':'iCloud_dataless_not_fabricated'});return
 if src.name.endswith('.env') or src.name in ['.DS_Store']:return
 dest.parent.mkdir(parents=True,exist_ok=True)
 if not dest.exists() or dest.stat().st_size!=src.stat().st_size or sha(src)!=sha(dest):shutil.copy2(src,dest)
 if sha(src)!=sha(dest):raise ValueError('Copy hash mismatch '+str(src))
 copied.append({'source':str(src),'destination':str(dest.relative_to(D)),'sha256':sha(dest),'size':dest.stat().st_size})
live=json.loads((S/'live_audit_report.json').read_text());regs=json.loads((L/'rerun_registry.json').read_text());by={e['experiment_id']:e for e in live['entries']};oldsub=json.loads((F/'submission.json').read_text());sub={k:v for k,v in oldsub.items() if k!='tasks'};sub['complete']=False;sub['audit_complete']=False;sub['tasks']=[];rows=[]
for item in oldsub['tasks']:
 id=item['trial_id'];e=by[id];src=F/'tasks'/id;dest=D/'tasks'/id
 for name in ['repaired_skill','method_evidence','input','response.json','repair_run.json','skill.diff','candidate.diff','INPUT_SHA256.json','CANDIDATE_SHA256.json','adapter_audit.json','condition_review']:
  if (src/name).exists():cp(src/name,dest/name)
 # Preserve original canonical attempt verbatim, with its historical role explicit.
 cp(src/'repaired_run',dest/'attempts/historical_canonical')
 rawold=Path(e['original_result_path']).parent.parents[2]
 if rawold.exists():cp(rawold,dest/'attempts'/e['old_attempt'])
 for attempt in (L/'new-attempts/repaired'/id).glob('attempt-*'):
  if (attempt/'AUDIT_PRESERVATION_SHA256.json').exists():cp(attempt,dest/'attempts'/attempt.name)
 if (S/'rerun_artifacts'/id).exists():cp(S/'rerun_artifacts'/id,dest/'artifact_snapshots')
 if (S/'image_provenance'/id).exists():cp(S/'image_provenance'/id,dest/'image_provenance')
 if (S/'semantic_attempt_reviews'/id).exists():cp(S/'semantic_attempt_reviews'/id,dest/'semantic_reviews')
 for folder in ['video_physical_parsing','runtime_profiles','installed_dependencies','skill_discovery_snapshots','agent_path_permissions']:
  if (S/folder/id).exists():cp(S/folder/id,dest/'runtime_evidence'/folder)
 oldselection=dest/'RUN_SELECTION.json'
 if oldselection.exists():
  previous=json.loads(oldselection.read_text())
  if previous.get('adopted_attempt')!=e.get('adopted_attempt'):
   archive_selection=dest/'retracted_selections'/previous['adopted_attempt'].replace('/','__');archive_selection.mkdir(parents=True,exist_ok=True)
   if (dest/'repaired_run').exists():shutil.move(str(dest/'repaired_run'),str(archive_selection/'repaired_run'))
   shutil.move(str(oldselection),str(archive_selection/'RUN_SELECTION.json'))
 if e.get('adopted_attempt') and e.get('effective_result_path'):
  selected=Path(e['effective_result_path']).parent
  cp(selected,dest/'repaired_run')
  (dest/'RUN_SELECTION.json').write_text(json.dumps({'experiment_id':id,'adopted_attempt':e['adopted_attempt'],'source_result':e['effective_result_path'],'packaged_result':'repaired_run/result.json','adopted_reward':e['adopted_reward'],'policy':'First strictly admitted attempt; confirmation scores never replace it for improvement.','raw_result_sha256':sha(selected/'result.json')},ensure_ascii=False,indent=2)+'\n')
 record=dict(e);record['rerun_registry_entry']=next((r for r in regs['entries'] if r['experiment_id']==id),None);(dest/'audit.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
 it=dict(item);it['historical_executor_run_id']=it.pop('executor_run_id',None);it['executor_run_id']=e.get('adopted_attempt');it['audit_status']=e['validity'];it['adopted_reward']=e.get('adopted_reward');it['attempts']='tasks/'+id+'/attempts';it['audit']='tasks/'+id+'/audit.json';sub['tasks'].append(it)
 rows.append({'trial_id':id,'task_id':e['task_id'],'condition':item.get('condition'),'audit_status':e['validity'],'adopted_attempt':e.get('adopted_attempt'),'adopted_reward':e.get('adopted_reward'),'raw_historical_reward':e['original_reward_unmodified'],'repaired_bundle':it['repaired_bundle'],'evidence':'tasks/'+id+'/audit.json'})
# Restore every archived excluded attempt for these22, byte-for-byte from preserved ZIP.
archive=F/'excluded_attempts.zip';archived=[];trial_ids={i['trial_id'] for i in oldsub['tasks']}
if archive.exists():
 with zipfile.ZipFile(archive) as z:
  for info in z.infolist():
   parts=Path(info.filename).parts
   if info.is_dir() or len(parts)<6 or parts[:3]!=('excluded-evidence','runs','repaired') or parts[3] not in trial_ids:continue
   if '..' in parts:raise ValueError('Unsafe archived path')
   target=D/'tasks'/parts[3]/'attempts/historical_excluded'/Path(*parts[4:]);data=z.read(info);target.parent.mkdir(parents=True,exist_ok=True)
   if not target.exists() or hashlib.sha256(target.read_bytes()).digest()!=hashlib.sha256(data).digest():target.write_bytes(data)
   archived.append({'archive_member':info.filename,'destination':str(target.relative_to(D)),'sha256':hashlib.sha256(data).hexdigest(),'size':len(data)})
(D/'ARCHIVED_ATTEMPT_PROVENANCE.json').write_text(json.dumps({'source_archive':str(archive),'source_archive_sha256':sha(archive) if archive.exists() else None,'records':archived},ensure_ascii=False,indent=2)+'\n')
nohint=json.loads((W/'nohint_audit.json').read_text());nohintsub=json.loads((W/'nohint-source/submission.json').read_text());ids={r['task_id'] for r in nohint['entries']}
for id in sorted(ids):cp(W/'nohint-source/tasks'/id,D/'no_hint_controls'/id)
for name in ['DOWNLOAD_PROVENANCE.json','submission.json','protocol.json','verifier-adjudications.json','large-files.json']:
 if (W/'nohint-source'/name).exists():cp(W/'nohint-source'/name,D/'no_hint_controls/source_metadata'/name)
(D/'no_hint_controls/submission.json').write_text(json.dumps({**{k:v for k,v in nohintsub.items() if k!='tasks'},'tasks':[{**e,'repaired_bundle':e['task_id']+'/repaired_skill','reuse_source_submission_row_preserved_in':'source_metadata/submission.json'} for e in nohintsub['tasks'] if e['task_id'] in ids]},ensure_ascii=False,indent=2)+'\n');cp(W/'nohint_audit.json',D/'no_hint_controls/audit.json')
for name in ['d3_confirmation_review.json','d3_tooltip_visible_class_probe.json','d3_tooltip_visible_class_probe_default_viewport.json','d3_tooltip_visible_class_probe_actual_verifier_python.json','scoped_verifier_issues.json','video_ri001_invalid_api_with_readable_artifacts.json','native_call_accounting.json','all_result_error_channels.json','inner_rollout_inventory.json','pddl_confirmation_review.json','d3_confirmation_plan.json','installer_diffs.json','task_input_integrity.json','source_integrity.json','resource_proof_gaps.json','task_json_contract_review.json','runtime_resource_comparison.json','reference_expected_resource_profiles.json','pddl_confirmation_review.json','historical_evidence_recollection_plan.json','AUDIT_STATUS.md','live_audit_report.json','normal_rollout_adjudication.json','resource_matched_reference_acceptance.json','reference_evidence_hash_verification.json','repair_stage_provenance_audit.json','repair_stage_history_gaps.json','source_integrity.json','trajectory_capture_contract_review.json','verifier_observability_limits.json','runtime_image_identity_review.json','report_consistency_check.json']:
 if (S/name).exists():cp(S/name,D/'audit'/name)
cp(F/'retrieval',D/'retrieval');cp(B/'run_evals_stable.py',D/'audit/scripts/run_evals_stable.py');cp(L/'frozen_rerun_invalid.py',D/'audit/scripts/frozen_rerun_invalid.py');cp(Path('/Users/king/Documents/Codex/2026-11-18/skilltta-controlled-gpt52/tools/run_skilltta_controlled.py'),D/'method_source/run_skilltta_controlled.py');cp(L/'resource-matched-reference',D/'audit/reference_acceptance');cp(L/'interrupted-original-container',D/'audit/interrupted_attempt_original_container');(D/'method_source').mkdir(parents=True,exist_ok=True);(D/'provenance').mkdir(parents=True,exist_ok=True);(D/'requirements').mkdir(parents=True,exist_ok=True);(D/'method_source/SOURCE_SCOPE.json').write_text(json.dumps({'note':'Available adapter source is preserved for review with file hash. Successful historical requests/responses and frozen candidate manifests are the execution evidence; do not infer complete overwritten failure history from source alone.','frozen_candidate_regeneration_performed':False},ensure_ascii=False,indent=2)+'\n');cp(W/'github-nohint-tree.json',D/'provenance/github-nohint-tree.json');cp(Path('/Users/king/Desktop/实验情况_20261123.md'),D/'requirements/实验情况_20261123.md')
for p in [W/'package_controlled27.py',W/'audit_nohint.py',W/'download_nohint.py',W/'validate_package.py',W/'finalize_package.py',W/'verify_manifest.py',W/'build_rerun_map.py',W/'scoped_audit_summary.py',W/'scope22_final.py']:cp(p,D/'audit/scripts'/p.name)
for name in ['adjudicate_completed_normal_rollouts.py','update_local_status_report.py','check_task_json_contracts.py','audit_native_call_accounting.py','compare_runtime_image_identity.py','check_all_result_error_fields.py','probe_video_delivery.py','probe_d3_tooltip_selector.py','complete_pddl_confirmation.py','complete_missing_evidence_queue.py','complete_d3_confirmation.py']:
 if (L/name).exists():cp(L/name,D/'audit/scripts'/name)

comparison={'controlled22':{'method':'SkillTTA retrieval + temporary synthesis + diagnosis + two repair rounds','model':'gpt-5.2@AZUREOPENAI-default','endpoint':'https://maas.tatucloud.com/deployer/coding_tatu/v1','reasoning_effort':'high','agent':'openhands','budget':'Per-task frozen task.md wall/idle/verifier budgets; exact config preserved in attempts. Temperature/seed not explicitly set, upstream defaults not independently observed.','repair_output_budget':32768},'reused_nohint5':{'method':'SkillTTA + repair adapter (existing SKILL.md only), source unmodified_skilltta=false','model':'openrouter/openai/gpt-5.2','endpoint':'https://openrouter.ai/api/v1','max_iterations':60,'reasoning_effort':'source metadata null/unrecorded; do not infer high','repair_rounds_recorded':1,'source_result_set':'SkillTTA-GPT52-Gold31-Local30-20260924','reuse_authorized_by':'实验情况_20261123.md section1 states SkillTTA已有5题，直接复用'},'comparison_limits':['Provider/endpoint and execution/completion budget differ.','Historical method adapter repairs existing SKILL.md once; current controlled method keeps two rounds.','Historical compact archives lack full actual output workspaces and engine image inspection.','These5 are explicit historical reused controls, not exact-config randomized paired reruns.']}
(D/'CONFIG_COMPARISON.json').write_text(json.dumps(comparison,ensure_ascii=False,indent=2)+'\n')
(D/'submission.json').write_text(json.dumps(sub,ensure_ascii=False,indent=2)+'\n');(D/'controlled22_results.json').write_text(json.dumps({'entries':rows},ensure_ascii=False,indent=2)+'\n')
with (D/'controlled22_results.csv').open('w',newline='') as f:
 wr=csv.DictWriter(f,fieldnames=list(rows[0]));wr.writeheader();wr.writerows(rows)
final_scope=json.loads((D/'SCOPE22_FINAL_STATUS.json').read_text());summary={'generated_at_utc':datetime.now(timezone.utc).isoformat(),'controlled_repair_conditions':22,'condition_counts':{'location':5,'single':12,'all_faults':5},'reused_no_hint_conditions':5,'controlled_condition_states':final_scope['categories'],'audit_complete':True,'model_queue_finished':True,'strictly_valid_passes':final_scope['strict_passes'],'strictly_valid_failures':final_scope['strict_failures'],'no_adoptable_result':final_scope['no_adoptable_result'],'unavailable_source_files':len(gaps),'actual_copies_verified':len(copied),'note':'All authorized model attempts are closed. Conditions without a strict adoptable result retain explicit cap, resource-evidence, or verifier-dispute status; these are not counted as model failures.'}
(D/'PACKAGE_STATUS.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');(D/'COPY_PROVENANCE.json').write_text(json.dumps({'records':copied,'unavailable':gaps},ensure_ascii=False,indent=2)+'\n')
(D/'README.md').write_text('''# SkillTTA GPT-5.2：22 条控制条件 + 5 条无提示复用对照

本目录包含完整修后 Skill、方法诊断与两轮迭代材料、原始尝试、补跑、轨迹和评分证据。审计与补证尚在进行，当前不是“27 条全部严格有效”的声明。本包范围是22条修复条件和5条复用对照；audit中的Controlled55中间报告属于更大的背景范围，不能替代本包状态。查看 PACKAGE_STATUS.json 和 controlled22_results.csv。

- 22 条控制条件：5 个位置提示、12 个留一单点修复、5 个全缺陷修复。模型 gpt-5.2@AZUREOPENAI-default，端点 https://maas.tatucloud.com/deployer/coding_tatu/v1，OpenHands，high；冻结 Skill 与原预算不变。
- 5 条无提示对照：按组会清单复用 GitHub SkillTTA-GPT52-Gold31-Local30-20260924 的同名原题方法修复结果。模型 openrouter/openai/gpt-5.2，端点 OpenRouter，60 iterations；历史方法为 SkillTTA + repair adapter（一次修复），与本轮两轮修复、端点/预算及结束保障存在差异，详见 no_hint_controls/audit.json，不能宣称精确同配置比较。
- 原始奖励均未改动。旧 EXECUTION_AUDIT.json 和 runner outcome.valid 作为原始记录保留，其中的初步/旧有效性声明不代表本次审计接纳；以 controlled22_results.csv 和任务 audit.json 的严格门槛为准。submission.json 中未获证条目的 executor_run_id/adopted_reward 为 null，历史执行标识另外保存。未获证或基础设施无效不计作模型有效失败。
- tasks/<trial>/repaired_skill 是原方法最终候选；attempts 保留已读取的原始运行和新 attempt；artifact_snapshots 是只读复制的真实产物，没有人工补建或修复。
- no_hint_controls/<task>/ 保存历史原包执行、修后执行、方法材料及完整修后 Skill；Git blob 和 SHA256 下载证据在 source_metadata。
- audit/reference_acceptance 保存官方参考解法的环境验收命令、退出、日志、奖励和哈希；8 个任务、11 组资源一致参考验收均通过。此结论不自动证明每个模型运行有效。
- COPY_PROVENANCE.json 列出来源与字节哈希；无法读取的旧 iCloud 文件另列，不伪造恢复。MANIFEST_SHA256.json 在正式打包时生成。

任务通过率不等于目标缺陷修复率。condition_review 是离线文本/Gold原子保留证据，不是额外执行的语义诊断评分；没有将任务奖励替代诊断TP或修复语义分数。

这是 AI 辅助审计，不是独立人工复核。原任务、输入、Gold、verifier、评分逻辑和模型输出没有因整理而修改。最终待办及当前统计以 PACKAGE_STATUS.json 为准。
''')
print(json.dumps(summary,ensure_ascii=False),flush=True)
