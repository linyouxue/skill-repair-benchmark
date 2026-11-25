"""Freeze a reviewable local directory+ZIP only after all scoped reruns terminate."""
import subprocess,sys,json,hashlib,zipfile
from pathlib import Path
from datetime import datetime,timezone
W=Path(__file__).parent;D=W/'SkillTTA-GPT52-Controlled22-NoHint5';L=Path('/Users/king/Library/Application Support/SkillTTA/controlled-gpt52/audits/controlled55-strict-20261124');S=L/'audit-evidence'
reg=json.loads((L/'rerun_registry.json').read_text());scoped=[e for e in reg['entries'] if e['kind']=='repaired'];assert not any(e['status'] in ['running','awaiting_reference_gate','blocked_reference_not_passed'] for e in scoped),'Model queue still active';d3=next(e for e in scoped if e['experiment_id']=='location-data-to-d3');assert len(d3['new_attempts'])==2 and d3['new_attempts'][-1]['status']=='closed','D3 confirmation not complete'
q=subprocess.run([sys.executable,str(L/'preserve_new_attempts.py')],cwd='/private/tmp');assert q.returncode==0,'Closed attempt preservation failed'
for row in scoped:
 for attempt in row['new_attempts']:
  m=L/'new-attempts/repaired'/row['experiment_id']/attempt['new_attempt']/'AUDIT_PRESERVATION_SHA256.json'
  assert m.exists() and json.loads(m.read_text()).get('verified'),'Missing verified raw attempt backup '+row['experiment_id']+'/'+attempt['new_attempt']
for name in ['package_controlled27.py','build_rerun_map.py','scoped_audit_summary.py']:
 q=subprocess.run([sys.executable,str(W/name)],cwd=W);assert q.returncode==0,name

exporter=Path('/Users/king/Documents/Codex/skill-repair-benchmark-main-upload-latest/evaluation/results/export_trajectory.py')
for dry in [True,False]:
 log=D/'audit'/('trajectory_export_dry_run.log' if dry else 'trajectory_export.log')
 with log.open('wb') as f:q=subprocess.run([sys.executable,str(exporter),'--root',str(D),*(['--dry-run'] if dry else [])],stdout=f,stderr=subprocess.STDOUT)
 assert q.returncode==0,'Trajectory export failed'
q=subprocess.run([sys.executable,str(W/'validate_package.py')],cwd=W);assert q.returncode==0
validation=json.loads((D/'PACKAGE_VALIDATION.json').read_text());assert validation['package_structure_passed'],validation['package_structure_errors']
rows=json.loads((D/'controlled22_results.json').read_text())['entries'];pending=[r['trial_id'] for r in rows if r['audit_status'] in ['rerun_or_adjudication_pending','valid_failure_confirmation_pending']];status=json.loads((D/'PACKAGE_STATUS.json').read_text());assert not pending,'Scoped semantic review still pending'
status.update(audit_complete=True,audit_scope='Controlled22 terminal adjudication plus5 historical-reuse coverage/limitations; not all55 controls',historical_nohint_independent_strict_certification=False,model_queue_finished=True,scoped_audit_pending=pending,audit_workflow_complete=not pending,all_results_strictly_valid=all(r['audit_status'] in ['valid_pass','valid_failure'] for r in rows),strict_passes=sum(r['audit_status']=='valid_pass' for r in rows),strict_failures=sum(r['audit_status']=='valid_failure' for r in rows),unresolved_or_invalid_conditions=sum(r['audit_status'] not in ['valid_pass','valid_failure'] for r in rows),historical_nohint_reuse_count=5)
(D/'PACKAGE_STATUS.json').write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n')
lines=['# 结果与审计状态','',f"22条控制条件，5条无提示历史复用。模型队列已结束；逐项复核待办：{len(pending)}。严格有效通过{status['strict_passes']}，严格有效失败{status['strict_failures']}，其余{status['unresolved_or_invalid_conditions']}条为无有效结果、证据不足或verifier争议。有效结果不等于通过；未获证条目不进入模型有效失败数。",'', '|实验ID|状态|采用attempt|采用奖励|原历史奖励（未直接采用）|','|---|---|---|---:|---:|']
for r in rows:lines.append(f"|{r['trial_id']}|{r['audit_status']}|{r.get('adopted_attempt') or '—'}|{r.get('adopted_reward') if r.get('adopted_reward') is not None else '—'}|{r['raw_historical_reward']}|")
lines+=['','无提示5题来源、原分和配置差异见 no_hint_controls/audit.json。历史5题原分为1通过4未通过；缺完整历史工作区及镜像证据，不能把它们升级为本轮严格有效结果。','', '所有原始尝试均保留在 attempts、historical_excluded 和审计来源记录中；8个不可读旧iCloud来源文件在COPY_PROVENANCE明确列出，未伪造恢复。部分中断尝试实际文件从保留容器只读取得，另见audit/interrupted_attempt_original_container。','', 'D3确认006官方9/10检查通过，tooltip仅因缺.visible类名被判失败；只读实际verifier解释器/默认viewport探针确认opacity=1且ticker/name/sector可见，ETF隐藏，单列verifier选择器争议，未改分且未替换首次005的JS格式失败。','', '诊断/修复成功阶段88个请求响应的哈希已核验；其中2个条件的较早失败HTTP响应未完整保存，方法完整失败调用历史不能补造。','', '任务输入、Gold、verifier测试及评分未因本次补跑/整理而修改；已有环境安装入口修订另见audit/installer_diffs.json。','', '轨迹由原export_trajectory.py导出，index未手改；原始运行缺展示条件元数据时会归入unknown，真实条件以tasks/<trial>/audit.json和RUN_RECORD为准，未编造executor_request。']
(D/'RESULTS.md').write_text('\n'.join(lines)+'\n');readme=(D/'README.md').read_text();readme=readme.replace('审计与补证尚在进行，当前不是“27 条全部严格有效”的声明。','模型补跑队列已结束；有效结果、无有效结果及证据缺口分别登记，当前不是“27 条全部严格有效”的声明。');(D/'README.md').write_text(readme)
# Hash every delivered byte except self-referential hash manifest.
manifest={}
for p in sorted(D.rglob('*')):
 if not p.is_file() or p.name=='MANIFEST_SHA256.json':continue
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 manifest[str(p.relative_to(D))]=h.hexdigest()
(D/'MANIFEST_SHA256.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n');archive=W/(D.name+'.zip');tmp=archive.with_suffix('.zip.tmp')
with zipfile.ZipFile(tmp,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
 for p in sorted(D.rglob('*')):
  if p.is_file():z.write(p,str(Path(D.name)/p.relative_to(D)))
with zipfile.ZipFile(tmp) as z:assert z.testzip() is None
h=hashlib.sha256()
with tmp.open('rb') as f:
 for b in iter(lambda:f.read(1048576),b''):h.update(b)
tmp.replace(archive);archive.with_suffix('.zip.sha256').write_text(h.hexdigest()+'  '+archive.name+'\n');print(json.dumps({'directory':str(D),'archive':str(archive),'bytes':archive.stat().st_size,'files':len(manifest)+1,'sha256':h.hexdigest(),'status':status},ensure_ascii=False),flush=True)
