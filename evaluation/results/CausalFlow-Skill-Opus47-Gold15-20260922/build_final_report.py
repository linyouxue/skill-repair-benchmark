"""Reproduce final audit-aware metrics offline; never executes an LLM or a rollout."""
import copy
import csv
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SUPPORTED_MATRIX = '--supported-matrix' in sys.argv
OUT = ROOT / ('final-review-supported-matrix' if SUPPORTED_MATRIX else 'final-review')
OUT.mkdir(exist_ok=True)
def local_path(p):
    text = str(p).replace('\\', '/')
    marker = '/causalflow_runs/opus47-gold15-20260922/'
    return ROOT / text.split(marker, 1)[1] if marker in text else Path(p)

def read(p):
    return json.loads(local_path(p).read_text(encoding='utf-8-sig'))
def write(p, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
def score(tp, fp, fn):
    return dict(tp=tp, fp=fp, fn=fn, precision=tp/(tp+fp) if tp+fp else None,
                recall=tp/(tp+fn) if tp+fn else None, f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None)
def pct(x):
    return 'N/A' if x is None else f'{x:.2%}'
def files(p):
    return {f.relative_to(p).as_posix(): f.read_bytes() for f in p.rglob('*') if f.is_file()}

state = read(ROOT/'batch_state.json')
assert state['gold_evaluation'] == 'complete'
assert all(r['phase'] == 'finished' for r in state['tasks'].values())
submission = read(ROOT/'submission/submission.json')
manifest = read(ROOT/'manifest.json')
baseline = {t['task_id']: t for t in manifest['tasks']}
overrides = read(ROOT/'final-execution-audit-overrides.json')['tasks']
gold_response_hash = hashlib.sha256((ROOT/'gold-evaluation/judge_responses.json').read_bytes()).hexdigest()
protected = read(ROOT/'recovery-history/20260923-flink-verifier-root-recovery/recovery.json')['protected_sha256']
assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest() == v for p,v in protected.items()), 'Paid/frozen evidence changed'

registry = {k: submission[k] for k in ('method_id','benchmark_version')}
registry['tasks'] = []
rows = []
for sub in submission['tasks']:
    tid = sub['task_id']
    assert baseline[tid]['status'] == 'FAIL'
    run = local_path(state['tasks'][tid]['result_path']).parent
    result = read(run/'benchmark_result.json')
    raw = read(run/'result.json')
    selected = run/'benchmark_result.json'
    if SUPPORTED_MATRIX and tid == 'fix-build-agentops':
        selected = ROOT/'verifier-recovery-agentops-supported-matrix-20260923/benchmark_result.json'
        result = read(selected)
        assert result['execution_ok'] and result['protocol_revision'] == 'agentops-supported-python-v1'
        assert result['task_passed'] is not None and result['verifier_matrix_complete']
        outcome = 'PASS' if result['task_passed'] else 'FAIL'
    elif tid in overrides:
        assert result['rollout_id'] == overrides[tid]['rollout_id']
        selected = OUT/'executor-audit-overrides'/tid/'benchmark_result.json'
        corrected = copy.deepcopy(result)
        corrected.update(execution_ok=False, task_passed=None, reward=None,
                         error=overrides[tid]['reason'], error_category=overrides[tid]['category'],
                         verifier_error=overrides[tid]['reason'], verifier_error_category=overrides[tid]['category'],
                         audit_source_benchmark_result=str(run/'benchmark_result.json'))
        write(selected, corrected)
        write(selected.parent/'executor_request.json', read(run/'executor_request.json'))
        outcome = 'INFRA_ERROR'
    else:
        assert result['execution_ok'] and result['task_passed'] is not None
        assert not any(result.get(k) for k in ('error','verifier_error','export_error'))
        outcome = 'PASS' if result['task_passed'] else 'FAIL'
    registry['tasks'].append({'task_id':tid,'benchmark_result':str(selected)})
    adapter = read(ROOT/'generation'/tid/'adapter_result.json')
    method = read(ROOT/'causalflow'/tid/'result.json')['summary']
    original = files(ROOT/'originals'/tid/'skills')
    final = files(ROOT/'submission'/sub['repaired_bundle'])
    deployed = files(run/'inputs/skills')
    assert original.keys() == final.keys(), 'Incomplete bundle'
    assert final == deployed, 'Deployed bundle differs'
    assert not sub['diagnoses'] and not adapter['updated_files'] and original == final
    rows.append(dict(task_id=tid, outcome=outcome, run_id=result['rollout_id'], result_path=str(selected),
        bundle_files=len(final), bundle_changed=False, n_skill_invocations=raw.get('n_skill_invocations',0),
        skill_exposure_verified=result['skill_exposure_verified'], method=method, adapter_status=adapter['status'],
        input_reconstructed=tid=='python-scala-translation', agent_iterations=result['agent_iterations']))
assert len(rows) == 15
write(OUT/'executor-results.json',registry)
scorer = ROOT.parents[1]/'scripts/evaluate_skill_diagnosis_repair.py'
assert scorer.is_file()
if (OUT/'gold-v1.4').exists():
    # Preserve earlier offline reports; the scorer requires a fresh output directory.
    import datetime
    previous = OUT/('gold-v1.4-history-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    assert previous.resolve().parent == OUT.resolve()
    (OUT/'gold-v1.4').rename(previous)
cmd = [sys.executable,str(scorer),'--gold',str(ROOT/'gold.subset.json'),
       '--submission',str(ROOT/'submission/submission.json'),'--judge-responses',str(ROOT/'gold-evaluation/judge_responses.json'),
       '--executor-results',str(OUT/'executor-results.json'),'--output',str(OUT/'gold-v1.4'),
       '--max-input-chars','2000000','--omit-temperature','--reasoning-effort','medium','--max-output-tokens','8192']
scored = subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
if scored.returncode:
    raise RuntimeError(scored.stderr or scored.stdout)
summary = read(OUT/'gold-v1.4/summary.json')
assert summary['status'] == 'complete' and summary['scored_task_count'] == 15
details = read(OUT/'gold-v1.4/details.json')
by_id = {t['task_id']:t for t in details['tasks']}
adjusted = copy.deepcopy(summary['metrics'])
for row in rows:
    task = by_id[row['task_id']]
    row['gold_defects'] = task['gold_defect_count']
    row['original_gold'] = task['metrics']
    row['outcome_adjusted'] = copy.deepcopy(task['metrics'])
    if row['outcome'] == 'PASS':
        for kind in ('diagnosis','repair'):
            row['outcome_adjusted'][kind] = score(row['gold_defects'],0,0)
        row['outcome_adjusted']['failed_gold_repair_count'] = 0
        row['outcome_adjusted']['harmful_extra_repair_count'] = 0
    tp = row['outcome_adjusted']['diagnosis']['tp']
    row['outcome_adjusted']['location_accuracy'] = task['metrics']['location_correct_count']/tp if tp else None
for kind in ('diagnosis','repair'):
    adjusted[kind] = score(*(sum(r['outcome_adjusted'][kind][k] for r in rows) for k in ('tp','fp','fn')))
adjusted['location_accuracy'] = adjusted['location_correct_count']/adjusted['diagnosis']['tp'] if adjusted['diagnosis']['tp'] else None
for key in ('failed_gold_repair_count','harmful_extra_repair_count'):
    adjusted[key] = sum(r['outcome_adjusted'][key] for r in rows)
counts = Counter(r['outcome'] for r in rows)
for outcome_name in ('PASS','FAIL','INFRA_ERROR'):
    counts.setdefault(outcome_name,0)
valid = counts['PASS']+counts['FAIL']
confidences = []
for t in details['tasks']:
    judgment=t['judgment']
    confidences += [x['confidence'] for k in ('diagnoses','repairs','extra_modifications') for x in judgment[k] if 'confidence' in x]
    confidences += [judgment['regression']['confidence']]
assert len(confidences) == summary['total_judgment_count']
method_counts={k:sum(r['method'][k] for r in rows) for k in ('causal_steps','crs_interventions_evaluated','repair_candidates_evaluated')}
method_counts['action_repair_success_tasks'] = sum(r['method']['local_repair_full_success'] for r in rows)
report = dict(method_id=submission['method_id'], task_count=15,gold_defect_count=32,
    execution_outcomes=dict(counts),valid_execution_count=valid,valid_execution_pass_rate=counts['PASS']/valid,
    planned_task_pass_fraction=counts['PASS']/15,valid_execution_coverage=valid/15,
    valid_execution_gold_defect_count=sum(r['gold_defects'] for r in rows if r['outcome'] in ('PASS','FAIL')),
    unverified_task_ids=[r['task_id'] for r in rows if r['outcome']=='INFRA_ERROR'],
    complete_bundles=15,substantively_modified_bundles=0,n_skill_invocations=sum(r['n_skill_invocations'] for r in rows),
    skill_body_exposure_task_count=sum(r['skill_exposure_verified'] for r in rows),
    original_gold=summary['metrics'],outcome_adjusted=adjusted,summary_metadata=summary,method_counts=method_counts,
    mean_confidence=sum(confidences)/len(confidences),min_confidence=min(confidences),
    override_rule='For valid F->P only: diagnosis and repair TP=all Gold defects, FP=FN=0; location original hits/new TP; independent judgments retained',
    new_judge_calls=0,retained_gold_responses_sha256=gold_response_hash,tasks=rows)
report['execution_protocol_note'] = ('AgentOps verifier matrix revised from py37-py312 to py38-py312; original protocol report retained in final-review.' if SUPPORTED_MATRIX else 'Original verifier matrix; AgentOps quarantined.')
write(OUT/'final-metrics.json',report)
table=[]
def add(label,a,b=None,note=''):
    table.append([label,str(a),str(a if b is None else b),note])
for kind,zh in [('diagnosis','诊断'),('repair','修复')]:
    for k in ('tp','fp','fn','precision','recall','f1'):
        a,b=summary['metrics'][kind][k],adjusted[kind][k]
        add(zh+' '+k.upper(),pct(a) if k in ('precision','recall','f1') else a,pct(b) if k in ('precision','recall','f1') else b)
for k,zh in [('location_correct_count','定位命中数'),('location_accuracy','Location accuracy'),
 ('diagnosis_task_count','诊断评分任务数'),('substantively_modified_bundles','实质修改bundle数'),('regressed_bundles','回归bundle数'),
 ('regression_count','回归缺陷数'),('regression_rate','内容回归率'),('failed_gold_repair_count','尝试但失败的Gold修复数'),
 ('harmful_extra_repair_count','有害额外修改数'),('possible_new_defect_count','疑似新缺陷数')]:
    a,b=summary['metrics'][k],adjusted[k]
    add(zh,pct(a) if k.endswith(('accuracy','rate')) else a,pct(b) if k.endswith(('accuracy','rate')) else b,
        '原定位命中/对应版本诊断TP' if k=='location_accuracy' else '独立内容判定保留')
for k in ('task_count','total_gold_defect_count','evaluated_task_count','evaluated_gold_defect_count','scored_task_count',
          'skipped_original_pass_task_count','skipped_gold_defect_count','skipped_original_pass_rate',
          'confidence_task_count','total_judgment_count','low_confidence_count','low_confidence_rate','review_item_count','blocking_review_count'):
    add(k,pct(summary[k]) if k.endswith('rate') else summary[k])
add('平均/最低置信度',f"{report['mean_confidence']:.4f} / {report['min_confidence']:.4f}")
with (OUT/'complete-metrics.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.writer(f);w.writerow(['指标','原Gold','F→P全TP','说明']);w.writerows(table)
lines=['# CausalFlow→Skill 最终汇总','',
 '全部worker已结束。15题、32 Gold缺陷均有内容裁判；执行验收为 '+str(counts['PASS'])+' PASS、'+str(counts['FAIL'])+' FAIL、'+str(counts['INFRA_ERROR'])+' INFRA_ERROR。不能宣称15题全部有效完成。','',
 f'有效执行通过率 **{counts["PASS"]}/{valid} = {pct(report["valid_execution_pass_rate"])}**；全15题已证实通过占比 {pct(report["planned_task_pass_fraction"])}；有效验收覆盖 {valid}/15题、{report["valid_execution_gold_defect_count"]}/32 Gold缺陷。内容裁判覆盖仍为15题32缺陷。','',
 '**15个完整bundle均与原Skill逐字节相同，提交诊断数和实际Skill修改数均为0。** 因此fresh通过不能归因于Skill内容修复；F→P全TP只是用户指定的替代统计，不能解释成裁判认定全部缺陷已诊断或修复。','',
 '| 指标 | 原Gold语义评分 | F→P全Gold缺陷TP、FP/FN清零 | 说明 |','|---|---:|---:|---|']
lines += ['| '+' | '.join(r)+' |' for r in table]
lines += ['', 'N/A表示分母为0。原定位0/0，不写成0%或100%；替代定位保留原命中，分母变为替代TP。内容回归0/0，无实质修改所以不适用。执行P→F回归率也不适用：本组均为历史原始失败任务。FN仍代表未解决Gold缺陷；“尝试但失败的修复”计数0不等于修复成功。','',
 '| 任务 | 执行结果 | Gold D | 原诊断/修复 TP-FP-FN | 替代诊断/修复 TP-FP-FN | 原生Skill调用 | 备注 |',
 '|---|---|---:|---|---|---:|---|']
for r in rows:
    a,b=r['original_gold']['diagnosis'],r['outcome_adjusted']['diagnosis']
    assert a == r['original_gold']['repair'] and b == r['outcome_adjusted']['repair']
    note='输入重建（同一汇总）' if r['input_reconstructed'] else ''
    if r['outcome']=='INFRA_ERROR':note='完整版本矩阵未有效验收；原始部分断言失败保留'
    if r['task_id']=='flink-query':note='r002；r001 Maven基础设施错误隔离；3项测试通过'
    if r['task_id']=='shock-analysis-supply':note='存在Playwright/Excel-only与harness能力不匹配限制'
    lines.append(f"| {r['task_id']} | {r['outcome']} | {r['gold_defects']} | {a['tp']}/{a['fp']}/{a['fn']} | {b['tp']}/{b['fp']}/{b['fn']} | {r['n_skill_invocations']} | {note} |")
lines += ['', '## 执行、方法及产物','',
 '| 项目 | 核验结果 |','|---|---|',
 '| 完整bundle / submission / Gold覆盖 | 15 / 15 / 15题32缺陷 |',
 f"| 原生 n_skill_invocations / 正文暴露 | {report['n_skill_invocations']}次（flink-query）；15/15有正文注入证据 |",
 f"| 干预总数 / 因果步骤 / 候选命令修复 | {method_counts['crs_interventions_evaluated']} / {method_counts['causal_steps']} / {method_counts['repair_candidates_evaluated']} |",
 f"| CausalFlow行动修复成功任务 | {method_counts['action_repair_success_tasks']}（data-to-d3、seismic-phase-picking） |",
 '| 单次Skill转写模型调用 | 2题；13题无causal steps，按适配代码原样导出，无转写模型调用 |',
 '| Skill诊断 / 实际修改 | 0 / 0；2次转写也返回空诊断和空修改 |',
 '| 原始轨迹重跑 / 本次新增Gold调用 | 0 / 0；30个既有两阶段裁判响应全部保留 |',
 '| 方法关系 | 行动重放成功与Skill fresh rollout通过是不同结果；本实验是CausalFlow→Skill适配版 |',
 '', '## 未完成有效验收及限制','',
 '- `fix-build-agentops`：原tox要求py37，而原脚本固定LangChain依赖要求Python≥3.8.1；补PATH后的verifier-only恢复在原240秒时限超时，无reward。原py310–312的断言失败为部分证据，完整矩阵按INFRA_ERROR隔离。更改版本矩阵或依赖固定版本属于协议变更，未擅自修改。',
 '- `shock-analysis-supply`：实际失败有折旧率数量级错误证据，但任务要求Playwright/Excel-only，基础工具harness不能完整匹配；不将其泛称为毫无环境限制的纯模型能力结论。',
 '- `python-scala-translation`：使用经用户同意的误脱敏代码重建输入；原日志保留，不声称全部输入无损重放。',
 '- `flink-query` r001已隔离。r002冻结Skill不变，实际workspace在verifier前导出；不是从文字轨迹重建。',
 '', '## 配置、证据与复算','',
 'Opus方法/转写/fresh：`anthropic/claude-opus-4.7`，max_tokens=32768；temperature、reasoning effort、thinking字段均未显式传入，不能把服务端默认值写成确定数值。fresh预算JPG=65，其余60。',
 'Gold：GPT-5.5 medium，max_output_tokens=8192，temperature省略，confidence阈值0.8/warn_only；内容回归判定。既有prompt v2.1响应离线由scoring v1.4复算；F→P覆盖单独存储，原Gold不修改。','',
 '- `final-metrics.json`：逐题、两版全指标、执行覆盖及原始证据路径。',
 '- `complete-metrics.csv`：完整指标对照表。',
 '- `gold-v1.4/`：原Gold响应离线复算，人工隔离结果以明确来源的executor覆盖副本接入。',
 '- `../final-audit-a.json`、`../final-audit-b.json`、`../final-audit-flink-r002.json`：轨迹及verifier人工审计。',
 '- `../final-execution-audit-overrides.json`：AgentOps隔离依据；runner原始结果保持不变。',
 '- `../verifier-recovery-agentops-20260923/`：真实补丁恢复、原脚本与依赖冲突证据。',
 '- `../recovery-history/20260923-flink-verifier-root-recovery/`：旧失败及方法/Gold未改证据。',
 '', '复算：使用本机WSL Python运行 `build_final_report.py`。只读既有实验输入，输出本目录；不会调用模型、重跑实验或覆盖原Gold。','']
if SUPPORTED_MATRIX:
    lines[0] = '# CausalFlow→Skill 最终汇总（AgentOps 验收环境修订版）'
    lines = [line.replace('不能宣称15题全部有效完成。', '全部15题已获得有效PASS/FAIL；AgentOps使用明确修订的py38–py312验收矩阵，原六版本矩阵结果另行保留。') for line in lines]
    for index,line in enumerate(lines):
        if line.startswith('- `fix-build-agentops`：'):
            lines[index] = '- `fix-build-agentops`：用户要求修复已披露的基础设施/协议冲突后，验收矩阵从py37–py312修订为py38–py312；Python 3.7无法安装原固定LangChain依赖。五个受支持版本均执行真实原测试，源码、模型patch和断言未改。仅重跑verifier，无模型或Gold调用。不能把此结果称为原六版本协议的纯缓存修复；原报告保存在`../final-review/`。'
        elif line.startswith('| fix-build-agentops |'):
            lines[index] = line[:-2]+'验收矩阵修订为py38–py312；五环境真实测试 |'
    lines += ['','修订证据：`../verifier-recovery-agentops-supported-matrix-20260923/`；复算时运行 `build_final_report.py --supported-matrix`。','']
(OUT/'FINAL-REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
assert hashlib.sha256((ROOT/'gold-evaluation/judge_responses.json').read_bytes()).hexdigest()==gold_response_hash
write(OUT/'report-provenance.json',{'scorer':str(scorer),'scorer_sha256':hashlib.sha256(scorer.read_bytes()).hexdigest(),
    'offline_command':cmd,'judge_response_sha256':gold_response_hash,'new_api_calls':0,'manual_execution_overrides':str(ROOT/'final-execution-audit-overrides.json'),
    'recovered_verifier':str(ROOT/'verifier-recovery-agentops-supported-matrix-20260923/benchmark_result.json') if SUPPORTED_MATRIX else None})
print(json.dumps({k:report[k] for k in ('execution_outcomes','valid_execution_pass_rate','outcome_adjusted','method_counts','mean_confidence','min_confidence')},ensure_ascii=False,indent=2))
