// Diagnosis S0 -> native DSH repair -> real probe, repeated at most five times.
// SkillHone's unmodified Tracker, runRepair and runBenchmark own native records.
import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {fileURLToPath, pathToFileURL} from 'node:url';

export function repairChain({s0, repairAndEvaluate, persist, maximum = 5, history = []}) {
  const rounds = [...history];
  let previous = rounds.at(-1) ?? s0;
  let best = rounds.toSorted((a,b)=>b.score-a.score)[0];
  if (best?.score === 1) return {rounds, best, stopped_by:'candidate-passed'};
  for (let round = rounds.length + 1; round <= maximum; round++) {
    persist({status:'running', phase:'repair', current_round:round, planned_repair_rounds:maximum, s0, rounds, best});
    const candidate = repairAndEvaluate(previous, round, rounds);
    const record = {round, ...candidate};
    rounds.push(record);
    if (!best || candidate.score > best.score) best = record;
    persist({status:'running', phase:'round-complete', current_round:round, planned_repair_rounds:maximum, s0, rounds, best});
    if (candidate.score === 1) return {rounds, best, stopped_by:'candidate-passed'};
    previous = record;
  }
  return {rounds, best, stopped_by:'five-repairs'};
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const [upstream, root, resumeFlag] = process.argv.slice(2);
  if (!upstream || !root) throw new Error('Provide fixed SkillHone checkout and prepared private root');
  const here = path.dirname(fileURLToPath(import.meta.url));
  const python = '/home/linyuanjing/.venvs/skill-repair-benchmark-a16/bin/python';
  const helper = path.join(here, 'jpg_diagnosis_campaign_20261031.py');
  const stateFile = path.join(root, 'campaign-state.json');
  const resuming = resumeFlag === '--resume-probe';
  if (fs.existsSync(stateFile) && !resuming) throw new Error('Inspect actual state and resume explicitly; never restart paid rounds blindly');
  if (resuming && !fs.existsSync(path.join(root,'recovered-probe.json'))) throw new Error('No actual scored checkpoint recovery to resume');
  const {Tracker} = await import(pathToFileURL(path.join(upstream, 'dist/core/tracker.js')));
  const {runRepair} = await import(pathToFileURL(path.join(upstream, 'dist/core/harness.js')));
  const {runBenchmark} = await import(pathToFileURL(path.join(upstream, 'dist/core/benchmark.js')));
  const skill = path.join(root, 'skill');
  const tracker = new Tracker(skill, path.join(root, 'state'));
  const json = (name, value) => fs.writeFileSync(name, JSON.stringify(value, null, 2) + '\n', {mode:0o600});
  const run = (program, args, cwd = root) => {
    const result = spawnSync(program, args, {cwd, env:process.env, encoding:'utf8', maxBuffer:16*1024*1024});
    if (result.status !== 0) throw new Error(`Host operation failed (${path.basename(program)} ${args[0]}), exit ${result.status}`);
    return result.stdout.trim();
  };
  const host = (...args) => JSON.parse(run(python, [helper, args[0], root, ...args.slice(1)]));
  let state;
  const persist = value => {state = {...value, controller_pid:process.pid, updated_at:new Date().toISOString()}; json(stateFile, state);};
  let lineage = 'main';
  const s0 = JSON.parse(fs.readFileSync(path.join(root, 's0.json'), 'utf8'));
  try {
    let history = [];
    if (resuming) {
      const saved = JSON.parse(fs.readFileSync(stateFile,'utf8'));
      if (saved.current_round !== 1 || saved.rounds?.length) throw new Error('This resume handles only the verified interrupted first probe');
      const native = JSON.parse(fs.readFileSync(path.join(root,'rounds/round-1/repair.json'),'utf8'));
      const probe = JSON.parse(fs.readFileSync(path.join(root,'recovered-probe.json'),'utf8'));
      if (!probe.traces?.[0]?.execution_ok || !Number.isFinite(probe.score)) throw new Error('Recovered probe is not a valid native score');
      tracker.git(['checkout',native.branch]);
      if (tracker.git(['rev-parse','HEAD']) !== native.commit) throw new Error('Original repaired candidate changed before recovery');
      const issue = Number(native.run.issue_number);
      const pr = tracker.createPr({title:`JPG repair 1: original reward ${probe.score}`,head:native.branch,base:'main',issueNumber:issue,
        body:`Actual original session resumed after WSL shutdown, within cumulative 65 steps. Reward ${probe.score}. First DSH candidate retained; no new repair, merge or push.`});
      tracker.upsertWiki('jpg-diagnosis-s0-round-1','JPG training round 1 recovered',
        `Historical S0 ${s0.score}; actual candidate probe ${probe.score}. Native checkpoint recovery; commit ${native.commit}.`,issue,Number(pr.number));
      json(path.join(root,'rounds/round-1/probe.json'),probe);
      if (probe.score < 1) host('failure',probe.id,path.join(root,'feedback/round-1'));
      history = [{round:1,score:probe.score,branch:native.branch,commit:native.commit,probe,
        issue,run:tracker.runRecord(String(native.run.id)),pr:Number(pr.number),vision:native.vision}];
      lineage = native.branch;
      tracker.git(['checkout','main']);
      persist({status:'running',phase:'round-complete',current_round:1,planned_repair_rounds:5,
        s0,rounds:history,best:history[0],checkpoint_recovery_source:probe.source_result});
    }
    const chain = repairChain({s0, persist, history,
      repairAndEvaluate(previous, round, history) {
        const roundDir = path.join(root, 'rounds', `round-${round}`);
        fs.mkdirSync(roundDir, {recursive:true});
        const issue = tracker.createIssue(`JPG diagnosis-driven repair ${round}`,
          `Training observation: ${previous.score}. ${round === 1 ? 'S0 is the published historical diagnosis, with offline-derived field feedback, not a fresh baseline.' : 'Use the preceding actual failed original-task probe and its complete model-visible trajectory.'} `
          + `Repair round ${round} of at most five. Only existing Skill bodies may change. Original and group2 confirmation evaluations cannot select candidates.`).issue;
        const branch = `skillhone/diagnosis-s0-round-${round}`;
        tracker.git(['branch', branch, lineage]);
        const workspace = path.join(roundDir, 'skill');
        run('git', ['clone', '--quiet', '--no-hardlinks', '--single-branch', '--branch', branch, skill, workspace]);
        run('git', ['remote', 'remove', 'origin'], workspace);
        run('git', ['config', 'user.name', 'Local SkillHone experiment'], workspace);
        run('git', ['config', 'user.email', 'local@invalid'], workspace);
        if (round > 1) fs.cpSync(path.join(root, 'feedback', `round-${round-1}`), path.join(workspace, '.git/iteration-feedback'), {recursive:true});
        const record = tracker.startRun(Number(issue.number), 'deepseek-harness-diagnosis-repair', branch);
        const audit = path.join(roundDir, 'dsh-image-audit.jsonl');
        process.env.JPG_DSH_IMAGE_AUDIT = audit;
        const inheritedOptions = process.env.NODE_OPTIONS;
        process.env.NODE_OPTIONS = `${inheritedOptions ?? ''} --import=${pathToFileURL(path.join(here,'dsh_image_audit_20261031.mjs')).href}`.trim();
        const prompt = `You are the native SkillHone repair worker for local Issue #${issue.number}. Work only in ${workspace}. `
          + `This is repair round ${round}/5. The host has supplied a real failed training observation, score ${previous.score}. `
          + (round === 1 ? 'S0 is the complete published diagnosis under training-context/diagnosis. The old original binary reward was 0; its later permitted field feedback is 40/44. Do not confuse it with a new evaluation. '
            : 'The most recent real failure is under .git/iteration-feedback/index.json, with complete model-visible ACP, LLM and ATIF streams, the actual Excel when present and allowed field feedback. Use that failure, plus the original published diagnosis. ')
          + 'Read TRAINING.md, the original task, all five original Skill documents and the diagnosis index. Read the complete relevant evidence streams without pretending an omitted/truncated stream was read. '
          + 'Use native read_image to inspect the actual original receipt pixels, especially images implicated by field failures; image file paths and base64 text are not visual evidence. '
          + 'Diagnose why the actual execution went wrong, then make a focused generalizable improvement to the existing skills/**/SKILL.md bodies. '
          + 'Keep YAML frontmatter and every other file byte-for-byte intact. Do not add scripts, references, tests, EXPLORATION.md or receipt-specific answers. '
          + 'Do not execute the complete OCR task, invoke an evaluator, access other directories, query current or past Eval results, inspect verifiers/oracles, or view group_02/other held-out inputs. '
          + 'Do not invoke SkillHone or manipulate its Issue/Run/PR/Wiki records. Do not spawn subagents. No merge or push. '
          + 'Commit only the permitted Skill-body changes on the current branch and leave a clean tree. The host will run OpenHands and score the actual task after you finish. '
          + `Prior training-only decision history: ${JSON.stringify(history.map(r=>({round:r.round,score:r.score,branch:r.branch})))}`;
        json(path.join(roundDir, 'repair-input.json'), {round, source_observation:previous, branch, workspace,
          prior_training_history:history.map(r=>({round:r.round,score:r.score,commit:r.commit})),
          original_diagnosis:true, held_out_feedback:false, prompt});
        let code;
        try { code = tracker.protectAuditTrail(() => runRepair(prompt, workspace, tracker.home, String(record.log_path))); }
        finally {
          if (inheritedOptions === undefined) delete process.env.NODE_OPTIONS; else process.env.NODE_OPTIONS = inheritedOptions;
          delete process.env.JPG_DSH_IMAGE_AUDIT;
        }
        if (code !== 0) {tracker.finishRun(String(record.id), 'failed'); throw new Error(`Native DSH repair failed in round ${round}; inspect retained session/log, exit ${code}`);}
        if (run('git', ['status','--porcelain'], workspace)) throw new Error('Native DSH left an uncommitted candidate');
        const before = tracker.git(['rev-parse', branch]);
        const commit = run('git', ['rev-parse','HEAD'], workspace);
        if (commit === before) throw new Error('Native DSH produced no committed Skill change');
        host('validate', workspace);
        const vision = host('image-audit', roundDir);
        json(path.join(roundDir,'repair.json'), {round,branch,commit,run:record,vision});
        if (!vision.actual_image_send_verified) throw new Error('Native DSH repair finished without verified actual image send/response; inspect before evaluating');
        tracker.git(['fetch','--quiet',workspace,commit]);
        tracker.git(['update-ref',`refs/heads/${branch}`,tracker.git(['rev-parse','FETCH_HEAD']),before]);
        tracker.git(['checkout',branch]);
        const finished = tracker.finishRun(String(record.id),'completed');
        persist({...state, phase:'probe', current_round:round, current_candidate:{branch,commit}, first_round_image_verified:round===1?true:state.first_round_image_verified});
        const candidate = runBenchmark(tracker,'probe');
        json(path.join(roundDir,'probe.json'),candidate);
        const pr = tracker.createPr({title:`JPG repair ${round}: original reward ${candidate.score}`,head:branch,base:lineage,
          issueNumber:Number(issue.number),body:`Published diagnosis S0 or preceding actual training failure → isolated native DSH repair → real OpenHands probe. Reward ${candidate.score}. No merge or push. See retained repair/image/probe artifacts.`});
        const wiki = tracker.upsertWiki(`jpg-diagnosis-s0-round-${round}`,`JPG training round ${round}`,
          `Previous observation ${previous.score}; candidate ${candidate.score}. Commit ${commit}. Actual DSH image request/response verified. Only training feedback used. No merge or push.`,Number(issue.number),Number(pr.number));
        if (Number(candidate.score) < 1) host('failure',String(candidate.id),path.join(root,'feedback',`round-${round}`));
        lineage = branch;
        tracker.git(['checkout','main']);
        return {score:Number(candidate.score),branch,commit,probe:candidate,issue:Number(issue.number),run:finished,pr:Number(pr.number),wiki,vision};
      }});
    tracker.git(['checkout',chain.best.branch]);
    const selection = {commit:chain.best.commit,branch:chain.best.branch,score:chain.best.score,round:chain.best.round,
      stopped_by:chain.stopped_by,selected_from:'development-candidates-only',frozen_at:new Date().toISOString(),
      additional_original_evaluations:2,group_02_evaluations:3,automatic_merge:false};
    json(path.join(root,'selection.json'),selection);
    fs.writeFileSync(path.join(root,'selected-skill.diff'),tracker.git(['diff','main',chain.best.commit,'--','skills']));
    const archive = spawnSync('git',['archive','--format=zip',`--output=${path.join(root,'selected-skill-bundle.zip')}`,chain.best.commit,'skills'],{cwd:skill});
    if (archive.status !== 0) throw new Error('Could not export selected complete Skill bundle');
    persist({...state,phase:'original-confirmation',selection});
    const original = host('final','original');
    persist({...state,phase:'group_02-generalization',original_confirmation:original});
    const group = host('final','group_02');
    persist({...state,status:'complete',phase:'complete',group_02:group,completed_at:new Date().toISOString()});
  } catch(error) {
    persist({...state,status:'needs-infrastructure-recovery',error_type:error.name,error_message:error.message});
    process.exitCode=1;
  } finally {tracker.close();}
}
