# GPT-5.2 31-task SkillOpt rerun with evidence fixes

This is a clean, isolated rerun of the 31 GPT-5.2 baseline tasks using the
latest local SkillOpt adapter code. The legacy run is preserved unchanged.

Configuration: three workers, diagnosis N=3, edit budget L=4, repair rounds
R=2, strict bounded-edit `content` validation with up to three format attempts,
two infrastructure gate attempts, and a 3600-second OpenHands installation
allowance. Both optimizer and candidate gate use the 360 API GPT-5.2 route.

Diagnosis receives actual baseline and prior-round agent trajectories plus
structured verifier failures. Every exact diagnosis/merge/rewrite request and
full response, candidate Skill bundle, gate execution, verifier result, and
keep/revert/invalid decision is retained.

There is no independent validation or final-test split. Candidate selection is
a same-task gate and must not be interpreted as a leakage-free generalization
estimate.
