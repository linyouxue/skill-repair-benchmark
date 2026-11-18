# Release evidence archives

The 23 original, lossless attempt archives are available as assets of the
[SkillGrad JPG generalization evidence release](https://github.com/linyouxue/skill-repair-benchmark/releases/tag/skillgrad-jpg-generalization-evidence-v1).
The release is tagged on commit `9218a6f57452dc6a2393f1cd57dd45972dcde81e`;
the evaluation data version is separately fixed at
`87e83a996d1fa33ea8380cb4a693ba077ef6574f`.

[`attempt_index.json`](attempt_index.json) maps each archive to its run ID,
start time, original Excel SHA-256, score source, and effective-run treatment.
Its exact copy is also a [release asset](https://github.com/linyouxue/skill-repair-benchmark/releases/download/skillgrad-jpg-generalization-evidence-v1/attempt_index.json)
with SHA-256 `99b3f293671da1dabe3f39f658de825fa9262824efd94c99b45c21ac56998dd9`.
Paths under `evidence/attempts/` in the index and run references name the
original archive locations. The corresponding downloadable files are listed
below; the repository does not contain LFS pointers for those archives.

Each archive preserves its original ACP and LLM request/response trajectories,
executor request and configuration, available result and verifier records,
provider usage, and any generated Excel. Nine counted original Excel files and
their score records are also directly available under `group_01/`, `group_02/`,
and `group_03/`. All 23 attempts remain in the index, including excluded and
later uncounted runs. GitHub's displayed SHA-256 for every release asset was
checked against this index; full remote downloads were not repeated.

| Group | Original archive (download) | Bytes | SHA-256 |
|---|---|---:|---|
| 01 | [g1-r1-native-650-007.tar.gz](https://github.com/linyouxue/skill-repair-benchmark/releases/download/skillgrad-jpg-generalization-evidence-v1/g1-r1-native-650-007.tar.gz) | 1242108012 | `5ce8e905711d1846c3e9f41c347609f5eeaaeaf4a58289a96895825ed0ded304` |
| 01 | [g1-r1-verifier-failure-006.tar.gz](https://github.com/linyouxue/skill-repair-benchmark/releases/download/skillgrad-jpg-generalization-evidence-v1/g1-r1-verifier-failure-006.tar.gz) | 251634219 | `6ee2a486e3b32d0912ddc74e23c9f27591760640f2284f134eddd739e4321382` |
| 01 | [g1-r2-missing-excel-verifier-failure.tar.gz](https://github.com/linyouxue/skill-repair-benchmark/releases/download/skillgrad-jpg-generalization-evidence-v1/g1-r2-missing-excel-verifier-failure.tar.gz) | 136829868 | `3b01024bea7b14b900e2c9f945261be41c3bb9c05a5527b2beb215232acb7f6b` |
| 01 | [g1-r2-native-450-003.tar.gz](https://github.com/linyouxue/skill-repair-benchmark/releases/download/skillgrad-jpg-generalization-evidence-v1/g1-r2-native-450-003.tar.gz) | 609874978 | `e5286b1e1be7e6d818b3c141de61aa38407f0f04282c029bd0a416a0e66d3480` |
| 01 | [g1-r3-native-675.tar.gz](https://github.com/linyouxue/skill-repair-benchmark/releases/download/skillgrad-jpg-generalization-evidence-v1/g1-r3-native-675.tar.gz) | 24523578 | `8830919e3e41f00d9dbc148debe5e5159a1f974857be2037cde23f5c6d8513b0` |
| 02 | [g2-r1-native-925-001.tar.gz](https://github.com/linyouxue/skill-repair-benchmark/releases/download/skillgrad-jpg-generalization-evidence-v1/g2-r1-native-925-001.tar.gz) | 975386792 | `4e68fe376b308bfb0514f0b1bcd2075fe47936b9f53614693d2622629b488c22` |
| 02 | [g2-r2-export-permission-failure-007.tar.gz](https://github.com/linyouxue/skill-repair-benchmark/releases/download/skillgrad-jpg-generalization-evidence-v1/g2-r2-export-permission-failure-007.tar.gz) | 561049464 | `92d2dd20c2d210a3695c101c1276c529df345dcfeaa1bda5289e592457f079ba` |
| 02 | [g2-r2-install-github-connection-failure-002.tar.gz](https://github.com/linyouxue/skill-repair-benchmark/releases/download/skillgrad-jpg-generalization-evidence-v1/g2-r2-install-github-connection-failure-002.tar.gz) | 60382 | `0d660005abf4d8600ab1365dfece8bcbb43c48439ddd7e89b8a5e1dacbd2cd02` |
| 02 | [g2-r2-install-github-reset-003.tar.gz](https://github.com/linyouxue/skill-repair-benchmark/releases/download/skillgrad-jpg-generalization-evidence-v1/g2-r2-install-github-reset-003.tar.gz) | 60375 | `4f59b4e9431daf26e1de59da385d8ea590e35b3dae92f61cd372bea237b059b1` |
| 02 | [g2-r2-install-timeout-004.tar.gz](https://github.com/linyouxue/skill-repair-benchmark/releases/download/skillgrad-jpg-generalization-evidence-v1/g2-r2-install-timeout-004.tar.gz) | 48621 | `a58db1212c636369cbaf613fa93d996a7dffbc8e337414cf8383cae5b0135665` |
| 02 | [g2-r2-native-950-008.tar.gz](https://github.com/linyouxue/skill-repair-benchmark/releases/download/skillgrad-jpg-generalization-evidence-v1/g2-r2-native-950-008.tar.gz) | 416687345 | `5ef725caa9cb012313f11ddd2ef894d526f699d7d398323eddcd8975b1708031` |
| 02 | [g2-r2-native-975-executor-finalize-error.tar.gz](https://github.com/linyouxue/skill-repair-benchmark/releases/download/skillgrad-jpg-generalization-evidence-v1/g2-r2-native-975-executor-finalize-error.tar.gz) | 444978458 | `dcff584962b2e98081eb468ba6e83b599a65235e8dfa6d6be3f3012cad923eea` |
| 02 | [g2-r2-reuse-acp-timeout-006.tar.gz](https://github.com/linyouxue/skill-repair-benchmark/releases/download/skillgrad-jpg-generalization-evidence-v1/g2-r2-reuse-acp-timeout-006.tar.gz) | 60211 | `792ab393fcb2a2362dce780a0fddb741be750628b314b8c2ab43f4e1fcd6eeb7` |
| 02 | [g2-r2-reuse-missing-curl-005.tar.gz](https://github.com/linyouxue/skill-repair-benchmark/releases/download/skillgrad-jpg-generalization-evidence-v1/g2-r2-reuse-missing-curl-005.tar.gz) | 59419 | `628bc6360ee2b3674b94373481a030f6819aedcc96e11906d6c7c2155000937e` |
| 02 | [g2-r3-native-950-002.tar.gz](https://github.com/linyouxue/skill-repair-benchmark/releases/download/skillgrad-jpg-generalization-evidence-v1/g2-r3-native-950-002.tar.gz) | 190311803 | `83b9b9ae29e2db170ba6c3a95a539b778db3e90c336caf6fc585339fbc57b603` |
| 02 | [g2-r3-verifier-infra-failure-no-result-json.tar.gz](https://github.com/linyouxue/skill-repair-benchmark/releases/download/skillgrad-jpg-generalization-evidence-v1/g2-r3-verifier-infra-failure-no-result-json.tar.gz) | 376530552 | `2e77413634d892326e38d0543cf105d0c35241f62a3b7ed691cdf03d37d5a806` |
| 03 | [g3-r1-install-failure-001.tar.gz](https://github.com/linyouxue/skill-repair-benchmark/releases/download/skillgrad-jpg-generalization-evidence-v1/g3-r1-install-failure-001.tar.gz) | 59362 | `0932ae0dffeac107e85819137415892c9b45b6ee0328f0da67c3a5f2b09aba0b` |
| 03 | [g3-r1-install-failure-002.tar.gz](https://github.com/linyouxue/skill-repair-benchmark/releases/download/skillgrad-jpg-generalization-evidence-v1/g3-r1-install-failure-002.tar.gz) | 59299 | `370980a22ce81c67e954fe277f231c97334df3b2ea4f9cda2e78894ed3795fdc` |
| 03 | [g3-r1-install-failure-003.tar.gz](https://github.com/linyouxue/skill-repair-benchmark/releases/download/skillgrad-jpg-generalization-evidence-v1/g3-r1-install-failure-003.tar.gz) | 59350 | `d3282bc9a1aff8118e06a44d7f709f2bf93b5af03c276e3ee07661a187a45486` |
| 03 | [g3-r1-native-775-004.tar.gz](https://github.com/linyouxue/skill-repair-benchmark/releases/download/skillgrad-jpg-generalization-evidence-v1/g3-r1-native-775-004.tar.gz) | 1066188145 | `473e72996ab31d94e0be9c0937c04bc67d6d4139edde29fff283a52d93f086e3` |
| 03 | [g3-r2-native-000-005.tar.gz](https://github.com/linyouxue/skill-repair-benchmark/releases/download/skillgrad-jpg-generalization-evidence-v1/g3-r2-native-000-005.tar.gz) | 673101256 | `9cb01922875cc984d63e0437583691508146ff63ba44f0946437fea9085c0627` |
| 03 | [g3-r2-verifier-failure-007.tar.gz](https://github.com/linyouxue/skill-repair-benchmark/releases/download/skillgrad-jpg-generalization-evidence-v1/g3-r2-verifier-failure-007.tar.gz) | 349862808 | `e1db06b01e649f37f81dabeb5cb6bae6fa044d7b568c32cdf35867cf5656fe30` |
| 03 | [g3-r3-native-725-006.tar.gz](https://github.com/linyouxue/skill-repair-benchmark/releases/download/skillgrad-jpg-generalization-evidence-v1/g3-r3-native-725-006.tar.gz) | 1632431352 | `f07e53b35b5e2c3cd92a26724d7d3fe45cc5c5943b1384d5350836734c030817` |

To verify a downloaded archive, compare its byte size and SHA-256 with this
table before extracting it. On Windows, `Get-FileHash -Algorithm SHA256 <file>`
prints the digest. The release's two auto-generated source-code archives are
not experiment evidence.
