# hui.icon Registry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `AppIcons` class to `elements.py` so callers can write `hui.icon.canvas` instead of raw `"grid_on"` strings.

**Architecture:** Single `AppIcons` class with `Final[str]` attributes added to `elements.py` after the internal style constants block. Module-level alias `icon = AppIcons` at the bottom of the file makes `hui.icon.*` work. No migrations, no new files.

**Tech Stack:** Python, `typing.Final`

---

### Task 1: Add `AppIcons` to `elements.py`

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/elements.py`

- [ ] **Step 1: Add `Final` to the existing `typing` import**

In [elements.py:27](packages/haywire-core/src/haywire/ui/elements.py#L27), the import reads:

```python
from typing import Any, Callable, Optional, Sequence, TYPE_CHECKING
```

Change it to:

```python
from typing import Any, Callable, Final, Optional, Sequence, TYPE_CHECKING
```

- [ ] **Step 2: Add the `AppIcons` class after the style constants block**

Insert after line 46 (after the `_TRANSITION_BG` constant, before the `_LIST_HOVER_CLASS` line), adding a blank line before and after:

```python
# ──────────────────────────────────────────────────────────────────────────────
# Semantic Icon Registry
# ──────────────────────────────────────────────────────────────────────────────


class AppIcons:
    """
    Semantic icon names for Haywire UI concepts.

    Each Material icon string appears at most once — one icon, one concept.
    Use via the module-level alias:  hui.icon.canvas, hui.icon.edge, etc.

    Raw Material icon reference: https://fonts.google.com/icons?icon.set=Material%20Icons
    """

    # ── Scope tabs (Properties sidebar) ──────────────────────────────────────
    app:           Final[str] = "settings"          # application-wide settings
    execution:     Final[str] = "play_circle"       # execution behaviour
    canvas:        Final[str] = "grid_on"           # canvas & nodes scope
    debug:         Final[str] = "bug_report"        # debug / dev tools
    graph:         Final[str] = "polyline"          # active graph info
    node:          Final[str] = "wysiwyg"           # selected node properties
    node_settings: Final[str] = "tune"              # node settings (requires bags)
    edge:          Final[str] = "cable"             # selected edge info

    # ── Canvas sub-panels ────────────────────────────────────────────────────
    canvas_grid:       Final[str] = "grid_4x4"          # grid display settings
    canvas_node_skins: Final[str] = "format_shapes"     # node dimensions / typography
    canvas_zoom_pan:   Final[str] = "settings_overscan" # pan / zoom behaviour
    canvas_minimap:    Final[str] = "map"               # minimap visibility / position

    # ── Node panel sections ──────────────────────────────────────────────────
    node_info:   Final[str] = "info"         # node identity / metadata
    node_ports:  Final[str] = "device_hub"   # port list
    node_status: Final[str] = "check_circle" # validation / runtime status

    # ── Graph ────────────────────────────────────────────────────────────────
    haystack: Final[str] = "account_tree"  # multi-graph file browser

    # ── Library / editor tabs ────────────────────────────────────────────────
    library_browser:   Final[str] = "widgets"     # library browser editor
    library_component: Final[str] = "description" # component detail editor
    library_docs:      Final[str] = "menu_book"   # component documentation tab
    library_source:    Final[str] = "code"         # component source tab
    library_view:      Final[str] = "visibility"   # component preview tab

    # ── App panels ───────────────────────────────────────────────────────────
    theme: Final[str] = "palette"  # theme / appearance settings

    # ── Actions ──────────────────────────────────────────────────────────────
    add:     Final[str] = "add"           # add / create
    delete:  Final[str] = "delete"        # remove / destroy
    copy:    Final[str] = "content_copy"  # duplicate / copy to clipboard
    paste:   Final[str] = "content_paste" # paste
    refresh: Final[str] = "refresh"       # reload / revalidate
    save:    Final[str] = "save"          # persist to disk
    edit:    Final[str] = "edit"          # open for editing
    reset:   Final[str] = "restart_alt"   # reset to default / restart

    # ── Status (forward-looking) ─────────────────────────────────────────────
    ok:      Final[str] = "task_alt" # generic success / pass
    error:   Final[str] = "error"    # error state
    warning: Final[str] = "warning"  # warning state
```

- [ ] **Step 3: Add the module-level alias at the bottom of `elements.py`**

Append after the last line of the file:

```python

# ──────────────────────────────────────────────────────────────────────────────
# Module-level aliases
# ──────────────────────────────────────────────────────────────────────────────

icon = AppIcons
"""Semantic icon registry. Use as ``hui.icon.canvas``, ``hui.icon.edge``, etc."""
```

- [ ] **Step 4: Verify type checking passes**

```bash
cd /Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo
uv run mypy packages/haywire-core/src/
```

Expected: no new errors.

- [ ] **Step 5: Verify the full test suite still passes**

```bash
uv run pytest -m "not integration" -q
```

Expected: all tests pass, same count as before.

- [ ] **Step 6: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/elements.py
git commit -m "feat: add hui.icon semantic icon registry to elements.py"
```
