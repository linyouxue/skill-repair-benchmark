# SkillGrad MAIN31 combined finalized publication

This directory contains the effective SkillGrad MAIN31 finalized publication after combining trusted LOCAL and accepted SERVER results.

- Method: SkillGrad
- Effective submission task count: 19
- LOCAL finalized tasks: 17
- SERVER finalized tasks: 2
- LOCAL verifier outcomes: PASS = 5, FAIL = 12
- SERVER additions preserved: lab-unit-harmonization, dynamic-object-aware-egomotion
- Ownership conflict retained but excluded: paper-anonymizer-server-ownership-conflict.json

Energy and Drone use the latest LOCAL clean rerun canonical artifacts:

- nergy-unit-commitment: FAIL @ S5, final skill 5e84e0118cc00003182fa045b0361982f98bcb1050efda3dec51aa391d332a3
- drone-planning-control: PASS @ S4, final skill c815734d5e3f8e42300ac01b06db01dbabe780a5dbc6a080a8cdf04cf46a1fac

Each effective task directory contains:

`	ext
tasks/<task>/
├── repaired_skill/
├── original_run/
└── repaired_run/
`

Only publication allowlisted run evidence is included for run directories: xecutor_request.json, 
esult.json, enchmark_result.json, and 	rajectory/acp_trajectory.jsonl. Verifier/Gold/oracle/private evaluator artifacts, secrets, discarded chains, and polluted LOCAL historical chains are not included in the effective submission.

Root-level JSON summaries such as dialogue-parser.json, lab-unit-harmonization.json, server_additions_audit.json, and paper-anonymizer-server-ownership-conflict.json are retained as audit metadata. The effective task set is defined by submission.json and the regenerated trajectory timeline index.
