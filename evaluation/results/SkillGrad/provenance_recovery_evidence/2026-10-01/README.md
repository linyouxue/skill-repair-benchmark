# GPT-5.2 provenance and recovery evidence (2026-10-01)

This directory archives frozen, authoritative provenance and infrastructure-recovery evidence produced after archive commit `978f3fe208893f036f2c78cdce2aa324312671f9` for:

- `fix-build-google-auto`
- `simpo-code-reproduction`

The archive cutoff is `2026-10-01T14:01:04Z`. The canonical snapshot at that cutoff reports 27 finalized tasks and records both selected tasks as `blocked_infra`. This archive is evidence-only: it does not change canonical task state, task or verifier semantics, BenchmarkExecutor behavior, the repair algorithm, or the experiment protocol.

## fix-build-google-auto

- Rebaseline admission is documented in `policy/`.
- The task source is pinned to commit `301a62086cc39a9aca9098fcae40cc500242b823`.
- The task digest is `sha256:a71d138003aa4c28222d6877e0dd65c3ddfbd9f407d5878fd0a235a32e9df8a4`.
- The original Skill bundle is `sha256:8616f01f52ed20c0f9a93589f91bb709c98156c6531cbb1f15d38d6c8df50c4c`.
- The exact image is `sha256:f76d3a0e4fd4cf7a32b0c44a94053eed200dd5752bc99cec074b4bb519edd716`.
- Fresh protocol-v2 attempt `fix-build-google-auto-formal-1-1e337086ad9b` remains `infrastructure_invalid`; it is not a valid failure.
- The exact image uses glibc 2.31 while runtime components require `GLIBC_2.33` and/or `GLIBC_2.34`. See `fix-build-google-auto/glibc-audit/glibc-compatibility-audit.json`.
- The historical protocol-v1 S0 is preserved at its original location and remains marked invalid. It is not replaced by this evidence.

## simpo-code-reproduction

- The trajectory-reuse exception remains exactly: `s0_trajectory_reused=true`, `s0_verifier_valid=false`, and `recovery_exception=trajectory_reuse_after_verifier_failure`.
- The S1 frozen bundle is `sha256:b90853da023da064b388d722c0666786d180d6eee890c0b953483345629bf613`.
- Recovery provenance pins Python 3.10.19, uv 0.9.7, and `torch-2.1.2+cpu-cp310-cp310-linux_x86_64.whl` with SHA256 `bf3ca897f8c7c218dd6c4b1cc5eec57b4f4e71106b0b8120e92f5fdaf4acf6cd`.
- Two `--network=none`, zero-model smoke runs passed.
- Formal retry `simpo-code-reproduction-formal-2-cb81cf56fa6a` retains method trajectory evidence but remains `infrastructure_invalid` because the verifier timed out after 900 seconds. It is not a valid failure.
- The later zero-model verifier-timeout forensic replay was still running at the archive cutoff and is intentionally excluded until frozen.

## Binary policy

Docker image bodies, Python and uv runtime archives, the PyTorch wheel body, and package caches are not stored here. Their exact versions, filenames, origins, digests, build metadata, and recovery manifests are retained. See `large-artifacts-skipped.json` and `SHA256SUMS`.
