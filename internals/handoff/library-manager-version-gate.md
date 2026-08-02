
An ImportError in a testbed project. Root cause diagnosed as a stale-lockfile skew between two lockstep-released packages, not a repo bug:

- haywire-studio locked to 0.0.29 (pre API-rename)
- haywire-core locked to 0.0.31 (post-rename)
- The rename get_bridge → get_stdout_tee in console_bridge.py landed in a0198949 (2026-07-26), shipped in core 0.0.31. Studio 0.0.29's app.py still called the removed get_bridge → ImportError.
- uv sync didn't fix it because it installs from the existing lock and only re-resolves what's needed; bumping haybale-core/haybale-haystack to ~=0.0.31 pulled haywire-core forward but left haywire-studio's lock entry at 0.0.29 (still satisfied its own ~=0.0.28).


The problem

uv pip install <haybale-spec> (marketplace's install path, library_manager.py) resolves fresh against the requested spec's tree. Already-installed packages like haywire-studio are just reuse candidates — their declared Requires-Dist is not binding on the resolution. So a library update can silently downgrade/upgrade haywire-core out from under the running studio.

What was empirically tested (in the testbed venv)

┌──────────────────────────────────────────┬─────────────────────────────────────────────┐
│                 Approach                 │                   Result                    │
├──────────────────────────────────────────┼─────────────────────────────────────────────┤
│ Studio pins haywire-core~=0.0.31 (today) │ Silently plans downgrade to 0.0.30, no      │
│                                          │ warning                                     │
├──────────────────────────────────────────┼─────────────────────────────────────────────┤
│ Studio pins haywire-core==0.0.31 (exact) │ Still silently downgrades — exact pin does  │
│                                          │ nothing for pip-install path                │
├──────────────────────────────────────────┼─────────────────────────────────────────────┤
│ uv pip install -c constraints.txt with   │ ✅ Refused — "No solution found…            │
│ haywire-core==0.0.31                     │ unsatisfiable"                              │
└──────────────────────────────────────────┴─────────────────────────────────────────────┘

The recommended fix (proposed, not yet implemented)

Make library_manager.py's dry_run() / install() pass -c <constraints-file> pinning framework-owned packages (haywire-core, haywire-studio, nicegui, …) to their currently-installed exact versions before every haybale install. A conflict then makes uv's resolver fail → the existing RuntimeError → ui.notify(..., type="negative") path fires. So the "refuse to install, tell the user to update Studio first" UX reuses infrastructure that's already there; only the constraint + a better error message ("Update Haywire Studio first" instead of raw pip-resolver text) are new.

Two open items:
1. Authoritative list of "framework-owned, marketplace-must-not-bump" packages was never nailed down.
2. Separately, exact-pinning the studio→core edge is still worth doing — it fixes the uv sync/project-mode path (the original tester bug), but does nothing for the marketplace runtime install path.
