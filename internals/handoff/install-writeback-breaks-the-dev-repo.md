---
name: install-writeback-breaks-the-dev-repo
description: Handoff — installing a marketplace version over an editable install silently replaces it; landing site identified, fix not implemented
metadata:
  type: project
  status: open
---

# Installing over an editable install silently replaces it

Found 2026-08-03 while exercising the new install flow against the haywire
repo itself. Not caused by the flow — `_sync_install_to_pyproject` has always
done this — but easy to hit now that installing is pleasant.

The trigger is specific to a dev checkout, but the underlying question is not:
**what should installing a marketplace version of something already installed
editable actually do?**

## What happened

In this repo, `haybale-visiongraph` is normally installed editable against a
sibling checkout, so the author's IDE edits are live:

```sh
uv pip install -e /Volumes/.../haywire/haybale-visiongraph/barn/haybale-visiongraph
```

`barn/haybale-visiongraph` is a gitignored symlink to that checkout, and the
workspace `exclude` list deliberately keeps it out of `uv.lock` (see the
comment on `[tool.uv.workspace] exclude`).

Installing `haybale-visiongraph` from the marketplace UI did two things:

1. **Replaced the editable install with a git checkout.** Confirmed after the
   fact — `direct_url.json` now reads
   `{"url": "…haybale-visiongraph.git", "vcs_info": {"requested_revision":
   "v0.0.20"}}` and the module imports from `site-packages`, not the symlink.
   Live editing is silently gone; the symlink still exists, which makes this
   hard to notice.
2. **Wrote an unresolvable dependency into the workspace root
   `pyproject.toml`:**

```toml
[project]
dependencies = ["haybale-visiongraph~=0.0.20"]

[tool.uv.sources.haybale-visiongraph]
git = "https://github.com/going-haywire/haybale-visiongraph.git"
tag = "v0.0.20"
subdirectory = "barn/haybale-visiongraph"
```

After which every `uv run` in the repo fails:

```
error: Requirements ... git+…haybale-visiongraph.git@v0.0.20
#subdirectory=../../../../../../../../Volumes/Ddrive/.../barn/haybale-core
```

Note the mangled `subdirectory` — a stack of `../` ending in an absolute path
pointing at **haybale-core**, not visiongraph. We write a plain relative
`barn/haybale-visiongraph`; what uv resolved it to is not obviously derivable
from that, so this half may be a uv bug rather than ours and is worth
reproducing in isolation.

This broke the repo's own test suite: `tests/test_docs_json_flag.py` and
`tests/test_share_cli.py` shell out to `uv run haywire …`, which exits 2 with
empty stdout. Reverting the five lines fixed both.

## The general question underneath

Installing/uninstalling visiongraph through the UI is **not a requirement** —
it is a dev-machine special case. But "install the published version of a
library I currently have installed editable" is not special at all; it is what
any library author hits the moment they have their own library checked out and
also visible in the marketplace.

Today that path is silent and lossy: the editable install disappears, nothing
in the UI mentions it, and the only evidence is that the author's changes stop
taking effect.

The install flow's `checked` step is the natural place to surface this. It
already lists collateral upgrades from `dry_run`; an editable install being
replaced is exactly the same class of consequence, and the flow's whole design
premise is that consequences are shown before the mutating step.

`InstallType.EDITABLE` is already the framework's answer to "is this library
being edited in place" — it gates the source editor and Farmhand's write tool
— so the check is available:

```python
registry.get_library_install_type(library_id) is InstallType.EDITABLE
```

## Where this now lands (written after the install flow shipped)

The stepped install flow exists as of `885e6bc5`, so this no longer needs new
UI — only a field, a check, and a paragraph of panel copy.

**The check belongs in `InstallFlow.advance_from_selected`**, alongside the
`dry_run` call, in
`barn/haybale-marketplace/haybale_marketplace/editors/_install_flow/_state.py`.
That method is already the flow's one read-only probe, and it already returns
its findings for the `checked` panel to render.

Two pieces of wiring, both small:

1. **`InstallSource` needs one more method.** The protocol currently exposes
   `dry_run`, `install` and `get_installed_version`. Add something like
   `get_install_type(dist_name) -> str` and implement it on
   `ManagerInstallSource` (in the same package's `chrome.py`) as
   `manager.registry.get_library_install_type(...)`. Note the registry keys by
   **library_id**, not distribution name — `ManagerUninstallSource` in
   `_uninstall_flow/chrome.py` hit the same mismatch and is worth copying from.
   Its adapter also shows the enum→str translation the protocol wants.
2. **A field on the flow**, e.g. `replaces_editable: bool`, set in the same
   method and rendered by `_panel_checked` next to the collateral-upgrade list.

The panel already has the right shape for it: `_panel_checked` renders a
warning row with `--hw-warning` when `removals` is non-empty. An editable
replacement is the same class of consequence and can reuse that treatment.

**Do not block.** Per the inform-vs-block rule the flow already follows, this
is inform + explicit confirm — the Install button on `checked` is the gate.
The one exception in that flow (a framework conflict) blocks because uv's
resolver has already refused; nothing refuses here.

Two facts worth carrying into the fix:

- The venv change is **not undone by reverting `pyproject.toml`**. Restoring a
  dev machine needs the `uv pip install -e …` line from the section below, and
  the surviving symlink makes the breakage easy to miss.
- Whatever text the panel shows should say the source folder survives — that
  is the same wording the uninstall flow already uses for EDITABLE libraries
  (`_uninstall_flow/_state.py`, the warning appended in
  `advance_from_confirm`).

## Open questions

1. **Warn, or block?** By the project's own inform-vs-block rule (see
   docs/architecture/design/stepper-arch.md), this is inform + explicit
   confirm: replacing an editable install is legitimate — sometimes it is
   exactly what the author wants — but it must not be silent.
2. **Should write-back skip excluded workspace paths?** There is precedent:
   `_sync_install_to_pyproject` already no-ops for heaps under `barn/`,
   because the workspace glob covers them. A library whose path is inside an
   *excluded* workspace directory arguably deserves the same treatment.
3. **Is the mangled `subdirectory` ours or uv's?** Reproduce standalone before
   assuming a fix belongs on our side.
4. **Should write-back be visible at all?** It happens silently inside
   `install()`. The flow's `done` step could report "added to pyproject.toml",
   and arguably let the author decline — it is a reproducibility convenience,
   not part of installing.

## Restoring a dev machine after hitting this

```sh
git checkout -- pyproject.toml uv.lock
uv pip install -e /path/to/haybale-visiongraph/barn/haybale-visiongraph
```

The second line matters: reverting the file does not undo the venv change, and
the symlink still being present makes it look as though nothing broke.

## Relevant code

- `barn/haybale-marketplace/haybale_marketplace/library_manager.py`
  — `_sync_install_to_pyproject`, `_write_install_to_pyproject`,
  `_parse_git_install_spec`
- `packages/haywire-core/src/haywire/core/library/install_type.py`
  — `InstallType.EDITABLE`, the existing "is this edited in place" authority
- Root `pyproject.toml` — `[tool.uv.workspace] exclude` explains the symlink

## Note

The comment-preservation fix works here: the bad write went through
`edit_toml` and added lines without touching any of the file's 47 comments.
The damage is the *content* of the write, not the write mechanism.
