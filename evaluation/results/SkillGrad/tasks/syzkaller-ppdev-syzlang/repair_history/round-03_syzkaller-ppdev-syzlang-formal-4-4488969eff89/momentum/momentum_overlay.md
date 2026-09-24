### [syzkaller-ppdev-syzlang] run produced no required deliverable files (empty output inventory)
- signal: failure
- pattern: deliverables-presence-check
- anchor: deliverables-gate-write-verify-required-output-files
- gap: Despite the existing L2 rule **“Deliverables gate: write + verify required output files”** (create/write each file; verify with `ls -l` + `sed`; “do not finalize until inventory matches”), the run still produced **no artifacts at all** and terminated with **MaxIterationsReached**. The misfire suggests the gate is being treated as an end-of-run check rather than an **early, blocking checkpoint**; the agent never created `/opt/syzkaller/sys/linux/dev_ppdev.txt` and `/opt/syzkaller/sys/linux/dev_ppdev.txt.const` even as minimal stubs.
- proposed_change: Strengthen the L2 deliverables gate (syzlang-ioctl-basics) to an explicit **“create stubs first”** rule: immediately `mkdir -p /opt/syzkaller/sys/linux` and write both required files with minimal valid boilerplate before any reasoning/build steps. Add a hard stop: if `ls -l` does not show both paths non-empty, do not proceed to `make descriptions`. Optionally add/point to a short L3 checklist used at task start and at finalization.

## WORKFLOW-THEMES

- (none this iteration)
