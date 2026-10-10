# QuTiP Open-System Steady-State and Wigner Workflow

## Purpose
Reusable procedure for building composite open quantum system Liouvillians (e.g., cavity coupled to many spins), computing their steady state efficiently, and emitting phase-space (Wigner) artifacts whose axis order and normalization match a verifier's declared schema. Focuses on decision points that change execution, not QuTiP tutorials.

## When to Use
Trigger when the task requires: (a) a steady state of an open system whose Hilbert space is large enough that naive tensor construction or default solvers may stall, (b) permutationally symmetric or local-identical dissipation on N identical subsystems, or (c) producing Wigner-function arrays or CSVs on a specified grid. Do not use this skill for pure unitary dynamics, single-qubit toy problems, or tasks where no steady state or phase-space output is required.

## Procedure
- Discover the contract. Read the task statement and any provided scripts to extract: (i) exact output paths, (ii) grid vectors (xvec, pvec) and expected array shape, (iii) axis convention (does rows index x or p?), (iv) normalization convention, (v) parameter values. If any item is unspecified, record it as unknown and prefer QuTiP defaults; do not invent conventions.
- Choose the Hilbert space construction via this decision table:
- Losses are local-identical or collective-symmetric on N identical spins -> use `qutip.piqs` Dicke basis. Build spin Liouvillian with `piqs.Dicke(N, ...).liouvillian()`. Compose with cavity via `super_tensor(cavity_liouv, spin_liouv)` (or reversed to match ptrace indexing you plan to use).
- Losses break permutation symmetry, or N is tiny (<= 4) -> build full tensor space with `tensor` and standard `liouvillian(H, c_ops)`.
- Record the composite subsystem dimension list; you will need it for `ptrace`.
- Compute the steady state with bounded solver escalation:
- First try `steadystate(L, method='iterative-gmres', use_precond=True, use_rcm=True, use_wbm=True)` for medium Liouvillians.
- If it fails or stalls past a self-imposed time budget, fall back to `method='power'` with the same preconditioning, then `method='direct'` only for small systems. Do not use `direct` on large composite Liouvillians.
- Log which method succeeded.
- Reduce to the subsystem for Wigner. Use `rho.ptrace(cavity_index)` where `cavity_index` matches the order used in step 2. Verify `rho_cav.tr()` is close to 1; renormalize only if the task permits.
- Compute Wigner on the declared grid:
- Prefer `wigner(rho_cav, xvec, pvec, method='clenshaw')` for accuracy on moderate Fock cutoffs.
- If using `method='fft'`, remember it returns a tuple `(W, vec)`; unpack explicitly.
- Confirm array shape against `(len(pvec), len(xvec))` or `(len(xvec), len(pvec))` as QuTiP returns, and transpose only if the task's axis convention requires it.
- Post-write schema check (execution anchor). After writing each CSV, reload it with the same library the verifier likely uses (e.g., `numpy.loadtxt` or `pandas.read_csv`) and assert: shape matches the declared grid, axis order matches the task convention, and the discrete integral `W.sum() * dx * dp` is approximately 1 (or whatever normalization the task declares). Print each assertion result before finalizing.
- Finalize only after all post-write checks pass. If any check fails, fix the specific mismatch (transpose, renormalize, re-order grid) rather than regenerating silently.

## Constraints / Pitfalls
- Do not assume Wigner axis order; QuTiP's `wigner(rho, xvec, yvec)` returns an array indexed consistently with its documentation, but verifiers may expect rows=p or rows=x. Confirm via the task description or a reloaded shape assertion before writing.
- `wigner(..., method='fft')` returns a tuple; `method='clenshaw'` and the default return an array. Mixing these causes shape errors.
- Never build a `2**N` spin tensor space when PIQS applies; it will stall `steadystate` for N beyond ~6.
- Do not use `steadystate(method='direct')` on large Liouvillians; it allocates dense matrices.
- Keep Fock cutoff `N_cav` just large enough that increasing it does not change expectation values beyond a small tolerance; document the chosen cutoff.
- Discover output paths from the task; do not hard-code paths, parameter values, or grid sizes.
- Do not emit non-ASCII characters in code, filenames, or logs.
- If a solver or write step fails, apply one bounded fallback (next solver method, or transpose/renormalize) and re-run only the smallest affected check; do not restart the whole pipeline silently.