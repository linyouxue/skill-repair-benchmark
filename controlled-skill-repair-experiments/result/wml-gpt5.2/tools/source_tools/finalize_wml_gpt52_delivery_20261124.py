"""Refresh delivery, run official collection/export, and check requirements."""
from pathlib import Path
from collections import Counter
import csv,hashlib,importlib.util,json,shutil,subprocess,sys
BASE=Path(__file__).resolve().parent
OUT=BASE/'wml-gpt52-completion-20261124'
ROOT=BASE.parent/'results/wml-gpt5.2-controlled55'
DATA=Path('/Users/king/Downloads/03_论文科研/skill-repair-controlled-datasets-20261020')
PY='/Users/king/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3'
def load(p):return json.loads(p.read_text())
def save(p,j):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(j,ensure_ascii=False,indent=2))
def module(name,p):
 s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def main():
 subprocess.run([PY,str(BASE/'audit_wml_completion_20261124.py')],check=True)
 subprocess.run([PY,str(BASE/'package_wml_gpt52_completion_20261124.py')],check=True)
 # Export uses the supplied renderer, with documented controlled-layout discovery.
 command=[PY,str(ROOT/'tools/export_trajectory.py'),'--root',str(ROOT)]
 for suffix,name in [(['--dry-run'],'trajectory-export-dry-run.log'),([], 'trajectory-export.log')]:
  with (ROOT/'reports'/name).open('w') as f:subprocess.run(command+suffix,stdout=f,stderr=subprocess.STDOUT,check=True)
 collection=ROOT/'reports/official_collection.json'
 if collection.exists():
  history=ROOT/'reports/collection_history';history.mkdir(exist_ok=True);n=len(list(history.glob('*.json')))+1;collection.rename(history/f'collection-{n:03d}.json')
 with (ROOT/'reports/official-collect.log').open('w') as f:subprocess.run([PY,str(DATA/'tools/runner.py'),'collect','--runs',str(ROOT/'experiments'),'--out',str(collection)],stdout=f,stderr=subprocess.STDOUT,check=True)
 safe=module('safe',Path('/private/tmp/controlled55-strict-20261123/method/safe_controlled_eval.py'))
 selected=load(ROOT/'selection_manifest.json');repairs=[r for r in selected if r['group']=='repairs'];controls=[r for r in selected if r['group']=='controls'];score=list(csv.DictReader((ROOT/'reports/score_template.csv').open()));index=load(ROOT/'trajectory_timelines/trajectory_timeline_index.json');proof=[]
 for row in repairs:
  name=row['experiment_id'];result=load(ROOT/row['selected_packaged_result']);expected=safe.bundle_manifest(ROOT/row['candidate_bundle']);record=load(ROOT/'experiments/repair'/name/'RUN_RECORD.json');inputroot=ROOT/'inputs'/name;inputhash=load(inputroot/'INPUT_SHA256.json')
  expected_input=inputhash.get('files',inputhash)
  inputcheck=isinstance(expected_input,dict) and all((inputroot/path).is_file() and hashlib.sha256((inputroot/path).read_bytes()).hexdigest()==h for path,h in expected_input.items() if isinstance(h,str))
  proof.append({'experiment_id':name,'status':row['status'],'full_skill_bundle_present':expected['preloaded_skill_count']>0,'bundle_matches_actual_preload':expected['skill_bundle_sha256']==result['executor']['skill_bundle_sha256'],'loaded_skill_context_observed':result['executor'].get('skill_context_preload_matches_expected') is True,'input_files_match_export_manifest':inputcheck,'formal_reward_matches':result['rewards']['reward']==row['reward'],'candidate_and_diagnosis_retained':all((ROOT/'evidence/repair'/name/f).exists() for f in ['response.json','api_usage.json','wml_diagnosis.json']),'run_record_agent_model_match':record['model']==result['executor']['model']})
 save(ROOT/'reports/controlled22_package_check.json',proof)
 reuse=load(OUT/'UNHINTED_REUSE_AUDIT.json');supp=load(OUT/'UNHINTED_SUPPLEMENT_AUDIT.json');new=load(OUT/'NEW_ATTEMPT_AUDIT.json');catalog=load(DATA/'datasets/catalog.json');expected={t['trial_id'] for t in catalog['trials']}
 totals=Counter(r['condition'] for r in repairs);ct=Counter(r['status'] for r in repairs);cc=Counter(r['status'] for r in controls);tokens=load(ROOT/'reports/repair_usage.json')
 checks={'exact_22_official_trials':len(repairs)==22 and {r['experiment_id'] for r in repairs}==expected,'5_location_12_single_5_multiple':totals=={'location_hint':5,'leave_one_out':12,'all_faults':5},'all_22_execution_valid':all(r['status'] in ['valid_pass','valid_fail'] for r in repairs),'all_22_bundle_input_preload_checks':all(all(v for k,v in p.items() if k not in ['experiment_id','status']) for p in proof),'official_template_22_rows':len(score)==22,'target_and_gold_preservation_labels_present':all(r['target_semantically_repaired'] in ['true','false'] and r['non_target_gold_preserved'] in ['true','false','not_applicable'] for r in score),'AI_review_attributed_honestly':all('AI-assisted' in r['reviewer'] and 'not independent human' in r['reviewer'] for r in score),'five_historical_unhinted_bundles_retained':all((ROOT/'unhinted-reuse/zenmux-gpt5.2'/t/'repaired_skill').exists() for t in ['dialogue-parser','data-to-d3','flink-query','manufacturing-equipment-maintenance','pddl-airport-planning']),'historical_unhinted_files_match_published_blobs':load(OUT/'unhinted_local_published_integrity.json')['all_verified'],'five_tasks_have_clean_historical_or_authorized_supplement':sum(r['status'] in ['valid_pass','valid_fail'] for r in reuse)==4 and supp['selected'] is not None,'historical_dialogue_anomaly_preserved':next(r for r in reuse if r['task_id']=='dialogue-parser')['status']=='invalid','shared_controls_33_valid':len(controls)==33 and all(r['status'] in ['valid_pass','valid_fail'] for r in controls),'all_new_attempts_finished':all(r['finished'] for r in new) and supp['finished'],'all_timeline_jsonl_parse':sum(r['parse_error_count'] for r in index['tasks'])==0,'all_rendered_timelines_exist':all((ROOT/r['output']).is_file() for r in index['tasks']),'D3_user_authorized_compatibility_only':load(OUT/'VERIFIER_COMPATIBILITY_CHECK.json')['authorized_change_only'],'WML_two_stage_provenance_44_calls':tokens['trials']==22 and tokens['calls']==44}
 source='work/controlled55-wml-gpt52-final-20261123';audit='work/controlled55-strict-audit-20261123'
 summary={'controlled':{'total':22,'valid':ct['valid_pass']+ct['valid_fail'],'passed':ct['valid_pass'],'failed':ct['valid_fail'],'conditions':dict(totals),'target_semantically_repaired':sum(r['target_semantically_repaired']=='true' for r in score),'other_Gold_preserved':sum(r['non_target_gold_preserved']=='true' for r in score),'leave_one_out_trials':12},'shared_controls':{'total':33,'valid':cc['valid_pass']+cc['valid_fail'],'passed':cc['valid_pass'],'failed':cc['valid_fail']},'unhinted':{'tasks':5,'historical_valid':4,'historical_passed':sum(r['status']=='valid_pass' for r in reuse),'historical_failed':sum(r['status']=='valid_fail' for r in reuse),'historical_flagged':'dialogue-parser','supplemental_dialogue_status':supp['selected']['status'] if supp['selected'] else None,'supplemental_dialogue_reward':supp['selected']['reward'] if supp['selected'] else None,'supplement_is_cross_endpoint':True},'trajectory_markdown_count':index['trajectory_count'],'repair_model_calls':44,'requirements_all_met':all(checks.values()),'checks':checks,'original_attempt_locations':[str((BASE.parent/source).resolve()),str((BASE.parent/audit).resolve()),str(OUT.resolve())],'remaining_evidence_limits':['Some historical task output archives do not exist; no files reconstructed. Runtime verifier and trace evidence used where applicable.','AI-assisted semantic review, not independent human sign-off.','Zenmux unhinted and Tatumass controlled runs are separately labelled; not an endpoint-controlled randomized comparison.','D3 SVG verifier compatibility v1 is versioned; original scores and outputs preserved.']}
 save(ROOT/'reports/FINAL_DELIVERY_CHECK.json',summary)
 save(ROOT/'evidence/VERIFIER_COMPATIBILITY_CHECK.json',load(OUT/'VERIFIER_COMPATIBILITY_CHECK.json'))
 report=['# WML GPT-5.2 交付说明','',f"22 条受控修复：{ct['valid_pass']} 通过，{ct['valid_fail']} 失败，均有可采用的执行评分证据。5 条位置提示、12 条单点待修、5 条多点待修齐全。",'',f"共享对照：{cc['valid_pass']} 通过，{cc['valid_fail']} 失败，{cc['valid_pass']+cc['valid_fail']}/33 有效。",'',
 '5 题无提示原题记录已按分工复用。4 条历史执行未发现所列异常；dialogue-parser 原历史记录虽得 1 分，但末尾工具 JSON 文本化，已保留异常标注，并按用户许可用 Tatumass GPT‑5.2、相同冻结修后 Skill、60 次预算补充验证。补充验证正常通过，三份产物实际导出。它与原 Zenmux 记录分开保存，不伪称同端点重跑。','',
 f"语义复核：{sum(r['target_semantically_repaired']=='true' for r in score)}/22 条目标修复成立；{sum(r['non_target_gold_preserved']=='true' for r in score)}/12 条留一实验保留其他 Gold。此为已标注的 AI 辅助复核，不能称作独立人工签字。任务通过不代表 Skill 缺陷一定修好。",'',
 'D3 verifier 只做了用户授权的 SVG 文本读取兼容修正，断言和奖励公式不变；修正版通过参考验收，位置提示修后运行奖励 1。D3 完整 Gold 的模型运行若失败，作为有效执行失败单独解释；参考解法通过证明环境可验收，但不能保证模型每次使用 Gold Skill 都成功。','',
 '原始尝试、异常记录和旧分数未覆盖；本轮新 attempt 路径在 evidence/ATTEMPT_PLAN.json 与 INFRASTRUCTURE_RETRY_PLAN.json。全部历史 raw attempts 仍位于 FINAL_DELIVERY_CHECK.json 列出的本机归档根目录。此交付目录包含选定执行及部分先前选定记录，不伪称已复制全部 raw attempts。','',
 '完整目录验证与限制见 reports/FINAL_DELIVERY_CHECK.json；官方模板见 reports/score_template.csv；官方 runner 的收集输出见 reports/official_collection.json；模型运行 Markdown 和自动索引见 trajectory_timelines/。','',
 '历史归档缺失的任务产物不从模型文字、评分 JSON 或 Gold 重建。此工作完成了分工清单的结果整理，不等同于此前更严格的“所有历史产物全部重新打开”条件已经满足。','',
 '当前检查：','',*['- '+k+': '+str(v) for k,v in checks.items()]]
 (ROOT/'reports/DELIVERY_REPORT.md').write_text('\n'.join(report))
 # Preserve the exact orchestration scripts for reproduction without secrets.
 for name in ['complete_wml_gpt52_20261124.py','audit_wml_completion_20261124.py','package_wml_gpt52_completion_20261124.py','finalize_wml_gpt52_delivery_20261124.py','validate_wml_unhinted_dialogue_20261124.py','retry_wml_d3_startup_20261124.py']:
  shutil.copy2(BASE/name,ROOT/'tools'/name)
 print('FINAL_DELIVERY',json.dumps({'all_checks':all(checks.values()),'failed_checks':[k for k,v in checks.items() if not v],'controlled':summary['controlled'],'shared_controls':summary['shared_controls'],'unhinted':summary['unhinted']},ensure_ascii=False),flush=True)
 if not all(checks.values()):raise SystemExit(2)
 manifest={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in ROOT.rglob('*') if p.is_file() and p.name!='PACKAGE_SHA256.json' and not p.name.endswith('.copy-in-progress')}
 save(ROOT/'PACKAGE_SHA256.json',manifest)
if __name__=='__main__':main()
