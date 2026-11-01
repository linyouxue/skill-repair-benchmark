"""Rebuild the published diagnosis input shape from one actual failed probe."""
import importlib.util
import json
from pathlib import Path
import shutil

import adapter

HERE=Path(__file__).resolve().parent


def load_formatter(task):
    package=HERE/'datasets'/task
    spec=importlib.util.spec_from_file_location('published_diagnosis_records',package/'tools/prepare_diagnosis.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    # Original common helper from repository commit 556fd216..., blob b8a191d3....
    common=importlib.util.spec_from_file_location('published_safe_diagnosis_helpers',HERE/'diagnosis-tools/published_prepare_diagnosis.py')
    helper=importlib.util.module_from_spec(common);common.loader.exec_module(helper)
    return module,helper


class CurrentFailure:
    def __init__(self,run):
        self.root=run;self.run_id=run.name

    def source(self,name,line=None,pointer=''):
        value={'kind':'actual_native_probe','file':'diagnosis/records/raw/current/'+name,
            'source_run':str(self.root),'pointer':pointer}
        if line is not None:value['line']=line
        return value

    def json(self,name):return adapter.read_json(self.root/name)

    def lines(self,name):
        for number,line in enumerate((self.root/name).read_text().splitlines(),1):
            if line.strip():yield number,json.loads(line)


def build(root,feedback,training):
    current=adapter.read_json(feedback/'index.json');run=Path(current['source_run'])
    if current['kind']!='actual_failed_original_probe' or not 0<=current['score']<1:
        raise ValueError('Only the most recent actual failed original probe may produce the next diagnosis')
    if not run.is_relative_to(root):raise ValueError('Failure belongs to another campaign')
    out=training/'diagnosis'
    if out.exists():raise FileExistsError('Do not overwrite diagnosis provenance')
    formatter,helper=load_formatter(root.name)
    records,(prompt,prompt_source),calls=formatter.prepare_records(CurrentFailure(run),helper)
    out.mkdir(parents=True)
    streams=[]
    for name,values in records.items():
        path=out/'records'/(name+'.jsonl');path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in values))
        streams.append({'name':name,'path':'diagnosis/records/'+path.name,'records':len(values)})
    # Preserve raw exchanges unchanged, including the interrupted source segment.
    segments=[('current',run)]
    recovery=run/'checkpoint-recovery.json'
    if recovery.exists():
        original=adapter.read_json(recovery).get('source_run')
        if original and Path(original)!=run:
            source=Path(original)
            if not source.is_relative_to(root):raise ValueError('Checkpoint source is outside this campaign')
            segments.insert(0,('before-checkpoint',source))
    raw=[]
    for label,source in segments:
        for name in ('trajectory/acp_trajectory.jsonl','trajectory/llm_trajectory.jsonl','trainer/atif.json'):
            target=out/'records/raw'/label/name;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(source/name,target)
            raw.append({'path':target.relative_to(training).as_posix(),'source_file':str(source/name),'bytes':target.stat().st_size})
    (out/'task_prompt.md').write_text(prompt)
    shutil.copyfile(feedback/'allowed_feedback.json',out/'outputs-feedback.tmp')
    (out/'outputs').mkdir();(out/'outputs-feedback.tmp').rename(out/'outputs/allowed_feedback.json')
    shutil.copyfile(feedback/'actual-training-workspace.tar.gz',out/'outputs/actual-training-workspace.tar.gz')
    native=adapter.read_json(run/'result.json')
    metadata={'source_run':str(run),'model':native['model'],'condition':'method-skill','reward':current['score'],
        'agent_iterations_in_native_segment':(native.get('agent_result')or{}).get('iterations_used'),
        'stop_reason':(native.get('agent_result')or{}).get('stop_reason'),'source_segments':raw,
        'task_prompt_source':prompt_source,'response_tool_call_counts':calls,'new_model_calls':0,
        'historical_s0_diagnosis_included':False,'verifier_source_or_reference_values_included':False}
    if recovery.exists():
        recovered=adapter.read_json(recovery)
        metadata['checkpoint_accounting']={k:recovered.get(k) for k in ('prior_parent_iterations','remaining','parent_budget','injected_user_messages')}
        metadata['checkpoint_accounting']['total_parent_iterations']=(recovered.get('result')or{}).get('total_parent_iterations')
    adapter.write_json(out/'outputs/execution_metadata.json',metadata)
    adapter.write_json(out/'outputs/output_inventory.json',{'status':'actual_pre_verifier_workspace_archived',
        'archive':'diagnosis/outputs/actual-training-workspace.tar.gz','source':str(feedback/'actual-training-workspace.tar.gz')})
    adapter.write_json(out/'inputs.json',{'task':'task.md','environment':'environment/',
        'files':[{'path':p.relative_to(training).as_posix(),'bytes':p.stat().st_size}
            for p in sorted((training/'environment').rglob('*')) if p.is_file()],
        'held_out_inputs_included':False})
    index={'schema_version':2,'task_id':root.name,'run_id':run.name,
        'source':{'kind':'latest_actual_failed_original_probe','source_run':str(run),'feedback':str(feedback/'index.json')},
        'task_prompt':'diagnosis/task_prompt.md','inputs':'diagnosis/inputs.json',
        'skills':{p.parent.name:'../skills/'+str(p.relative_to(root/'skill/skills')) for p in (root/'skill/skills').rglob('SKILL.md')},
        'outputs':{'feedback':'diagnosis/outputs/allowed_feedback.json','inventory':'diagnosis/outputs/output_inventory.json',
            'execution_metadata':'diagnosis/outputs/execution_metadata.json'},'streams':streams,'counts':{k:len(v) for k,v in records.items()},
        'raw_source_segments':raw,'historical_s0_diagnosis_included':False,'model_calls':0,'source_experiments_unchanged':True}
    adapter.write_json(out/'index.json',index)
    validation=formatter.validate(training)
    adapter.write_json(out/'validation.json',validation)
    (out/'README.md').write_text('本轮诊断输入仅来自最近一次真实原题失败。按index.json读取完整记录、原始分段和允许反馈；历史S0诊断未复制。此准备步骤不调用模型，原生SkillHone负责诊断与修复。\n')
    return {'diagnosis_index':str(out/'index.json'),'source_run':str(run),'score':current['score'],
        'validation':validation,'historical_s0_diagnosis_included':False,'model_calls':0}


def prepare_context(root,workspace,feedback):
    context=workspace.parent/'current-diagnosis-context'
    if context.exists():raise FileExistsError('Inspect retained repair context/session before another paid attempt')
    context.mkdir();shutil.copytree(workspace/'skills',context/'skills')
    training=context/'training-context';training.mkdir()
    shutil.copyfile(root/'skill/training-context/task.md',training/'task.md')
    shutil.copytree(root/'skill/training-context/environment',training/'environment')
    diagnosis=build(root,feedback,training)
    (context/'TRAINING.md').write_text('Read training-context/task.md, the original inputs in training-context/environment, all current Skill documents, and the complete current failure in training-context/diagnosis/index.json. Only existing SKILL.md bodies may change. Historical S0 is not part of this context. Do not inspect held-out inputs/results, verifiers, other directories or other experiments.\n')
    adapter.commit_repo(context)
    initial=adapter.git(context,'rev-parse','HEAD')
    adapter.git(context,'config','user.name','Local SkillHone experiment');adapter.git(context,'config','user.email','local@invalid')
    branch=adapter.git(workspace,'branch','--show-current')
    if branch!='main':adapter.git(context,'checkout','-b',branch)
    return context,{'input_commit':initial,'context':str(context),**diagnosis}


def import_candidate(root,context,initial,workspace):
    permitted={'skills/'+name for name in adapter.files(root/'eval/reference_skills') if Path(name).name=='SKILL.md'}
    changed=adapter.git(context,'diff','--name-only',initial,'--').splitlines()
    if any(name not in permitted for name in changed) or adapter.git(context,'ls-files','--others','--exclude-standard'):
        raise ValueError('Native repair changed isolated inputs or files outside Skill bodies')
    adapter.verify_bundle(context/'skills',root/'eval/reference_skills')
    for name in permitted:
        original=adapter.git(context,'show',initial+':'+name)
        actual=(context/name).read_text()
        if original.startswith('---\n') and not actual.startswith('---'+original.split('---',2)[1]+'---'):
            raise ValueError('Native repair changed Skill frontmatter')
    for name in permitted:shutil.copyfile(context/name,workspace/name)
    return {'native_input_commit':initial,'native_output_commit':adapter.git(context,'rev-parse','HEAD'),
        'candidate_content_edited_by_host':False,'native_skill_bytes_copied_without_rewriting':True}
