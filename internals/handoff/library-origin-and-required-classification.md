# A second "origin" axis for installed libraries, and where Required still falls short

Raised 2026-08-04 while fixing two related marketplace bugs: `builtin` (a
framework-owned library) could be disabled through the UI even though nothing
about that makes sense, and separately, the Update button could silently
no-op (see `fix(marketplace): pin the Update button's install spec to the
target version` and `fix(marketplace): stop stale library state after
uninstall/share`, both landed on master the same day). The Required-badge gap
got a narrow fix (below); the broader classification idea it surfaced is
scoped out here.

## What landed already (narrow fix, same day)

`is_required()` in `library_browser_editor.py` (~line 517) now also returns
`True` when:

- `lib.install_type is InstallType.FOLDER` — framework-owned (currently only
  `builtin`, from `packages/haywire-core/src/haywire/barn/builtin/__init__.py`).
- `is_project_library(lib, marketplace_path)` is `True` — this workspace's own
  `barn/*` library (the function already existed in
  `_overview_edit_dialog.py:24`, used to gate the Edit-vs-Uninstall button
  split at `library_overview_editor.py:456`).

This closes the *UI* gap (the purple "Required" badge, and the Disable
button's block message) using existing primitives — no new `InstallType`
value, no new field. `disable_library()` itself (`registry.py:251`) is still
unprotected at the registry layer; see "Loose end" below.

## The idea that got deferred: origin as a second axis

`InstallType` (`install_type.py:8`) has three values — `REGULAR`, `EDITABLE`,
`FOLDER` — and conflates two different questions:

1. **Install mechanism**: was `__file__` found inside site-packages
   (`REGULAR`), outside it via a pip `-e` install (`EDITABLE`), or was it
   never pip-installed at all, just scanned off a folder path (`FOLDER`)?
   Detected in `discovery.py:143` (`_detect_install_type`), purely by path.
2. **Origin**: did the code come from PyPI, a git remote, or is it this
   project's own source under `barn/`?

Only axis 1 is represented today. Axis 2 exists piecemeal:

- `Haybale.source` (`marketstall/types.py:27`, `"pypi"` / `"git"` / implicitly
  `"local"`) carries origin — but only for libraries that have a **catalog
  entry** (came through the marketplace / a `haywire share` publish). An
  `EDITABLE` library discovered via a bare pip entry point with no matching
  `Haybale` row (e.g. someone ran `pip install -e ../some-other-repo` outside
  the marketplace flow entirely) has no `source` to read at all.
- `is_project_library()` (`_overview_edit_dialog.py:24`) answers "is this
  under `workspace_root/barn`" by a path check, independently of `Haybale`.
- `project_local_libraries()` (`haybale_studio/farmhands/_helpers.py:37`) is a
  THIRD, broader definition again — "every `EDITABLE` install," regardless of
  whether it's under this workspace's `barn/` at all. Its own docstring says
  so explicitly: Farmhand may write to an editable install "regardless of
  whether its path sits under the current workspace root." This is
  deliberate for Farmhand's actual need (source-write access), but it means
  "project-local" currently has two different working definitions in the
  codebase that happen to overlap for the common case and diverge for the
  uncommon one (an editable install of someone else's library, symlinked in
  from outside `barn/`).

The user's proposed model (2026-08-04 conversation) is the cross-product of
the two axes, restricted to the combinations that actually occur:

| install mechanism | origin | badge(s) |
|---|---|---|
| folder | — (n/a) | `[folder]` |
| editable | pip | `[editable] [pip]` |
| editable | git | `[editable] [git]` |
| editable | local | `[editable] [local]` |
| regular | git | `[git]` |
| regular | pip | `[pip]` |

The Library Detail view would show both badges (mechanism + origin) instead
of the current single `install_type.name.lower()` tag
(`library_overview_editor.py:390`, one of `editable`/`regular`/`folder`).

## Why this needs its own design pass, not a bolt-on

- **Where does "origin" get computed, and by whom?** `_detect_install_type`
  (`discovery.py`) is a `@classmethod` with no workspace context — it only
  sees a filesystem path relative to site-packages. Distinguishing `local`
  from a general `editable`+`git`/`editable`+`pip` requires knowing the
  *workspace root*, which the core discovery/registry layer doesn't have
  today (by design — `LibraryRegistry` is workspace-agnostic; workspace root
  is a marketplace/studio-layer concept, threaded in via `context.app`).
  Plumbing it down into discovery is a real architectural decision, not a
  one-line add.
- **Reconciling the three existing "is this local/project" definitions**
  above (`Haybale.source`, `is_project_library`, `project_local_libraries`)
  needs to happen as part of this, or a fourth, slightly-different definition
  gets added on top.
- **Every existing `install_type.name in (...)` / `is_editable()` call site**
  needs auditing for whether it should also match a new classification, or
  deliberately exclude it. At minimum: the Uninstall-button gate
  (`library_overview_editor.py:479`, `("REGULAR", "EDITABLE")` — must keep
  excluding local), `is_editable()` itself (`install_type.py:15` — must keep
  including local, since local libraries are obviously still author-editable
  and Farmhand-writable).

None of this is hard, but it's a distinct scope from the Required-badge fix
that prompted the conversation, and deserves its own inquisition rather than
riding in on a bugfix.

## Loose end from the narrow fix: `disable_library()` itself is unprotected

`LibraryRegistry.disable_library()` (`registry.py:251`) has no `InstallType`
check — it will happily disable `builtin` or a project-local library if
called directly. Today the only callers are the two marketplace UI editors
(`library_overview_editor.py`, `_overview_actions.py`) — no Farmhand tool
currently exposes `disable_library` (`grep -rl disable_library barn/ packages/`
excluding tests turns up no `farmhands/` hit), so this is not currently
reachable outside the UI this session just fixed. But the UI-only fix is a
convention, not an enforced invariant: the next caller (a Farmhand tool, a
CLI script, a test helper) has nothing stopping it from disabling `builtin`
live. If/when the origin-axis work above lands, `disable_library()` should
probably refuse (return `False`, or raise) for `FOLDER` and local-origin
libraries at the registry layer — the same authority-not-just-UI principle
`remove_library()`'s `sys.modules` ejection already follows.
