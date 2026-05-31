# Docstring & Comment Audit — Reconnaissance Pass

Read-only findings. No source files were modified. All quotes are verbatim
(trimmed to the relevant lines). File:line references use the in-tree paths.

## Summary

### Surface-area counts (sampled)

- Python files in `packages/haywire-core/src/`: **217**
- Python files in `packages/haywire-studio/src/`: **7**
- Python files in `barn/`: **166** (across 9 haybale libraries)
- Approximate total: **390** Python files (matches `.codemap/INDEX.md`'s ~280 est. + tests/scripts).
- Docstring count (rough grep `"""` in `packages/haywire-core/src/haywire`): **3190** triple-quote occurrences ≈ ~1.5k docstrings.
- Public classes in `packages/haywire-core/src/haywire`: **154** top-level `class ` definitions.

Sampling strategy: read 25+ representative files spanning every module in
`.codemap/INDEX.md` — core/node, core/graph, core/library, core/di, core/types,
core/settings, core/state, core/session, core/session/signals, core/errors,
core/registry, core/execution, core/marketstall, ui/panel, ui/editor,
ui/components/graph, haywire-studio app, haybale-core/__init__, haybale-core
nodes, haybale-haystack persistence, haybale-marketplace library_manager,
haybale-studio properties_editor. Plus targeted greps for taxonomy patterns
(historical language, docs/spec references, TODOs, "legacy/backward-compat",
phase/step markers).

### Docstring format detected

- **Primary:** Google-style sections (`Args:`, `Returns:`, `Raises:`, `Yields:`,
  `Examples:`) — used in most node, editor, panel, and core API methods.
- **Secondary:** Sphinx/RST (`.. code-block:: python`, `:meth:`, `:class:`,
  `:mod:`, NumPy-style `Parameters ---- name : type` blocks) — used in
  `packages/haywire-core/src/haywire/core/settings/descriptor.py`
  (NumPy block) and several `ui/editor`/`session` files (`:meth:` refs).
- **Tertiary:** Plain prose module docstrings at the top of most files.
- **Mixed** within single classes is common (e.g. `BaseEditor.draw` uses
  `Args:`, but the class-level docstring uses `:mod:` refs). Cleanup must
  preserve whichever convention each file already uses — do not normalize
  across the tree.

### Top 3 verbosity patterns (ranked by frequency)

1. **Multi-paragraph "Design Philosophy" / "Usage" sections that narrate
   architecture inside a docstring** (D1/H2). Examples: `Editor` class
   docstring in `graph/editor.py` lines 1-12 and 33-40; `BasePanel` example
   block in `ui/panel/base.py` lines 28-46; `BaseEditor.__init__` lines 64-73.
2. **Inline historical / "now / previously / legacy" breadcrumbs** (D2/C1).
   Pervasive in `marketstall/*` (spec-rename references), `errors/__init__.py`,
   `node/behavior.py:93`, `barn/haybale-haystack/*` ("vs the legacy Haystack").
3. **Cross-file references to docs/insights/spec sections** (D4). Found in 15+
   files: `state/base.py`, `state/__init__.py`, `state/data_namespace.py`,
   `session/protocols.py`, `session/context.py`, all of
   `core/marketstall/*` ("spec §X"), `library/identity.py`,
   `barn/haybale-haystack/state/haystack_state.py`,
   `barn/haybale-graph-editor/state/edit_state.py`,
   `barn/haybale-studio/state/__init__.py`.

---

## Findings

Each row: file:line — taxonomy code — one-line description — disposition.
A representative offending snippet appears below the table for each code.

### D1 — Implementation detail in docstring, irrelevant to a consumer

| Location | Description | Disposition |
|---|---|---|
| `packages/haywire-core/src/haywire/core/graph/editor.py:1-12` | Module header narrates upstream/downstream callback design rather than describing what consumers do with `Editor`. | SHORTEN to one-sentence purpose; move design notes to comment or delete. |
| `packages/haywire-core/src/haywire/core/graph/editor.py:33-40` | Class docstring describes "abstracts away the complexity of managing the graph, history, and node factory together. Uses simple callbacks for change notifications rather than complex events." — pure implementation reflection. | SHORTEN. |
| `packages/haywire-core/src/haywire/core/node/base.py:36-46` | `NodeData` docstring lists internal capabilities ("Unified port storage…Dynamic port reconfiguration…Section organization") that are usage-irrelevant — consumers care which methods exist, not the internal categorization. | SHORTEN to one-line purpose. |
| `packages/haywire-core/src/haywire/core/types/port.py:30-52` | `DataPort` docstring includes "Key simplification: Field is created by type.create_field(), not factory" and "Hierarchical access:" walk-through of internal type tracking. | SHORTEN — keep "unified port for inlets and outlets, direction set by is_inlet"; drop the rest. |
| `packages/haywire-core/src/haywire/core/types/enums.py:34-53` | `StoreStrategy` docstring contains an "Example:" *and* a "Caveat:" explaining bitwise behavior the type itself shows. | SHORTEN — caveat can stay as comment if non-obvious. |
| `packages/haywire-core/src/haywire/core/di/context.py:1-22` | Module docstring explains why module-level globals (not ContextVar) — internal motivation. | MOVE-TO-COMMENT (this is genuinely non-evident; see Judgment Calls). |
| `packages/haywire-core/src/haywire/core/execution/vm.py:1-10` | "The VM is responsible for: …" multi-bullet narration of internal responsibilities. | SHORTEN. |
| `packages/haywire-core/src/haywire/core/session/signals/bus.py:24-35` (excerpt above this read window: "Sync only. Handlers are plain callables; coroutines are not awaited. Aligns with today's sync signal-callback semantics and avoids the NiceGUI async slot-stack footgun.") | "Aligns with today's…" is internal rationale. | MOVE-TO-COMMENT. |

Verbatim sample (D1):
```python
# packages/haywire-core/src/haywire/core/graph/editor.py:1-12
"""
Editor - High-level graph manipulation interface with simple callback notifications

This class provides a clean, semantic API for graph operations while using
simple callbacks for change notifications. It wraps the graph, history manager,
and node factory to provide convenient methods for graph manipulation.

Design Philosophy:
- Simple callback-based notifications for graph changes (upstream: graph → UI)
- Complex event system remains for UI interactions (downstream: UI → graph)
- Clean separation between business logic and presentation layer
"""
```

```python
# packages/haywire-core/src/haywire/core/node/base.py:36-46
class NodeData:
    """
    Node data management with unified port collection and dynamic reconfiguration.

    Provides:
    - Unified port storage (inlets and outlets in single dict)
    - Dynamic port reconfiguration (rejig context manager)
    - Hierarchical grouping (nested groups with context managers)
    - Section organization (for property panels)
    - Clean API for port access
    """
```

---

### D2 — Design decision / historical breadcrumb

| Location | Description | Disposition |
|---|---|---|
| `packages/haywire-core/src/haywire/core/errors/__init__.py:1-8` | "The unified HaywireException class replaces the old HaywireError/HaywireException split. For backward compatibility, HaywireError is kept…" | DELETE (history). Replace with one sentence describing what the module exports today. |
| `packages/haywire-core/src/haywire/core/errors/utils.py:1-6` | "This module is maintained for backward compatibility. New code should use HaywireException methods directly." | DELETE or replace with a re-export note. |
| `packages/haywire-core/src/haywire/core/marketstall/__init__.py:1-3` | "Replaces the legacy haywire.core.marketplace + marketplace_runtime + marketplace_errors". | DELETE — purely historical. |
| `packages/haywire-core/src/haywire/core/marketstall/types.py:3-7` | "The Haybale dataclass replaces the legacy MarketplaceEntry. Adds the `os` field from §2.1; same shape otherwise. Subscription dataclasses … gain the `blocked` array introduced for the first-install safety modal …" | DELETE the "replaces / gain / introduced" framing; KEEP a minimal "Haybale: one row in [[haybales]]". |
| `packages/haywire-core/src/haywire/core/marketstall/types.py:18` | `"""One entry from a [[haybales]] section. Renamed from MarketplaceEntry."""` | SHORTEN — remove "Renamed from MarketplaceEntry". |
| `packages/haywire-core/src/haywire/core/node/behavior.py:92-93` | Comment header `# COMPUTED PROPERTIES - For backward compatibility and convenience` | DELETE the "backward compatibility" half. |
| `packages/haywire-core/src/haywire/core/node/__init__.py:44` | `# Dataclasses (legacy)` | FLAG — either rename + drop the comment, or remove if truly dead. |
| `packages/haywire-core/src/haywire/core/node/base.py:205` | `- DataPort instance (backward compatibility)` inside `add()` accepted-input list. | DELETE or SHORTEN — if the dual form is still supported, document the supported form only; if not, remove. |
| `packages/haywire-core/src/haywire/core/node/base.py:1309` | `- Missing fields keep their default values (backward compatibility)` | SHORTEN — describe behavior without "backward compatibility". |
| `packages/haywire-studio/src/haywire_studio/config.py:38` | `# `markets` (not the legacy `marketplaces`)` | DELETE — describe what is, not what was. |
| `packages/haywire-core/src/haywire/ui/console_bridge.py:69-73` | Two `"""Deprecated no-op. Use register_log_with_polling instead."""` / `"""Deprecated no-op."""` | FLAG — if truly deprecated and unused, delete the methods entirely. |
| `barn/haybale-marketplace/haybale_marketplace/library_manager.py:358` | `"""Deprecated alias for install(). Use install() directly."""` | FLAG — delete the alias if no callers. |
| `barn/haybale-haystack/haybale_haystack/persistence.py:10`, `:27`, `:93`, `:161` | Multiple "vs the legacy Haystack" / "compatible with haywire-studio's legacy Haystack.save_haystack" / "Unlike the legacy Haystack.load_haystack…". | DELETE the historical comparisons; describe current TOML schema only. |
| `barn/haybale-haystack/haybale_haystack/state/haystack_state.py:9-16`, `:182-188` | Module docstring "Three structural changes vs the legacy Haystack" + "Behavioral parity with legacy …" + "Mirrors the three concerns from the legacy Haystack". | DELETE the historical framing. |
| `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/context_menu.py:124` | "Replaces several entries from the legacy metadata dict". | DELETE. |
| `barn/haybale-haystack/haybale_haystack/editors/haystack_editor.py:121` | "without the legacy on_focus → emit GraphDataMutated catch-up trick." | DELETE. |
| `barn/haybale-haystack/haybale_haystack/editors/haystack_editor.py:807` | "The legacy …" | DELETE. |
| `barn/haybale-studio/haybale_studio/editors/properties_editor.py:86-90` | Comment: `# NB: held as a flat list of handles for now — same shape as the original wrapper-side implementation. Migrating to per-panel redraw will keep these per-(panel_class, event_type) …` | DELETE — historical + speculative (also D5). |
| `barn/haybale-studio/haybale_studio/editors/properties_editor.py:183-188` | Docstring paragraph "Future per-panel-redraw optimisation hooks in here … Today it forwards to ``wrapper.redraw()`` for the same behaviour the framework previously provided." | DELETE — both D2 and D5. |
| `packages/haywire-core/src/haywire/ui/app/icon_slot.py:81` | `# Mirror the original visual: left=login+mirror-when-visible; right=login+mirror-when-hidden.` | SHORTEN — drop "the original"; describe current visual. |
| `packages/haywire-core/src/haywire/ui/app/icon_slot.py:131` | `"""Whether to apply scaleX(-1) to the fold icon, matching the original UX."""` | SHORTEN — drop "the original UX". |
| `packages/haywire-core/src/haywire/ui/app/slot.py:74` | `* The editor instance of a previously-active wrapper is kept in its …` | KEEP if accurate state machine; otherwise SHORTEN ("previously-active" is fine if it denotes a state, not history). |
| `packages/haywire-core/src/haywire/ui/widget/binding.py:251` | `This is the property update logic that was previously in DataField.` | DELETE. |
| `packages/haywire-core/src/haywire/core/settings/registry.py:125` | `"""Register FrameworkSettings subclasses queued before this registry was created."""` | KEEP — "before this registry was created" is current behavior, not history. |
| `packages/haywire-core/src/haywire/core/settings/settings.py:146` | `"""Remove a previously registered callback."""` | KEEP — "previously registered" is state, not history. |
| `packages/haywire-core/src/haywire/ui/widget/factory.py:44` | `Remove a previously added customer callback…` | KEEP. |
| `barn/haybale-testing/haybale_testing/panels/test_session_state_panel.py:6` | Module docstring references "that previously produced two distinct class objects (one captured by…)" | FLAG — historical incident note; if it documents a regression-test rationale it can stay as a comment. See Judgment Calls. |

Verbatim sample (D2):
```python
# packages/haywire-core/src/haywire/core/errors/__init__.py:1-8
"""
Error handling utilities package.

The unified HaywireException class replaces the old HaywireError/HaywireException split.
For backward compatibility, HaywireError is kept but should not be used in new code.

Use HaywireException.from_exception() or HaywireException.create() directly.
"""
```

```python
# barn/haybale-haystack/haybale_haystack/state/haystack_state.py:9-16
Three structural changes vs the legacy Haystack:
  ...
Behavioral parity with legacy ``haywire_studio.haystack.Haystack`` is
intended for ...
```

```python
# barn/haybale-studio/haybale_studio/editors/properties_editor.py:86-90
        # NB: held as a flat list of handles for now — same shape as the
        # original wrapper-side implementation. Migrating to per-panel
        # redraw will keep these per-(panel_class, event_type) so a single
        # event publish can target only the panels that asked for it.
        self._panel_bus_unsubscribes: list[Callable[[], None]] = []
```

---

### D3 — Prose usage description that should be a code example

| Location | Description | Disposition |
|---|---|---|
| `packages/haywire-core/src/haywire/core/library/decorator.py:16-72` | The `@library` docstring spends ~50 lines on "Args:" list before showing usage; usage block is at the end. The Args list itself is partially redundant with `LibraryIdentity` (which is the underlying dataclass). | SHORTEN Args list to required + most-common 3; keep the existing minimal/common/full code examples; remove the per-arg defaults narration. |
| `packages/haywire-core/src/haywire/core/settings/descriptor.py:39-166` | The `setting` class docstring is a 120-line NumPy-style parameter manual. Each parameter has 3-8 lines of prose. | CONVERT-TO-CODE-EXAMPLE for the most-used parameters; SHORTEN per-param prose to a one-line rule each; the surface area is large enough that some prose is justified — but not 8 lines per arg. |
| `packages/haywire-core/src/haywire/core/library/base.py:22-29` | `BaseLibrary` docstring uses an "Usage:" prose paragraph instead of code. | CONVERT-TO-CODE-EXAMPLE. |
| `packages/haywire-core/src/haywire/core/session/session_manager.py:25-33` | `SessionManager` class docstring has "Usage:" with code-shaped lines but not in a code block. | KEEP (already close); ensure formatting is `.. code-block::` or fenced. |

Verbatim sample (D3):
```python
# packages/haywire-core/src/haywire/core/library/base.py:22-29
    """
    Abstract base class for all libraries

    Usage:

    Libraries that extend this class **must** be named 'Library'
    and be decorated with the @library decorator.
    """
```

---

### D4 — Reference to docs or other files

| Location | Description | Disposition |
|---|---|---|
| `packages/haywire-core/src/haywire/core/library/identity.py:28-29` | `# Post-install requirements (author-declared; default False). # See: docs/reference/glossary.md → "Post-install requirements".` | DELETE the docs reference (and keep the one-line "Post-install requirements (author-declared)"). |
| `packages/haywire-core/src/haywire/core/state/__init__.py:1` | `"""Library-owned runtime state — see docs/architecture/session-and-state/session-and-state-arch.md."""` | DELETE the doc ref; keep "Library-owned runtime state." |
| `packages/haywire-core/src/haywire/core/state/base.py:10, 76, 121` | Three identical-shaped `See docs/architecture/session-and-state/session-and-state-arch.md` tails. | DELETE all three. |
| `packages/haywire-core/src/haywire/core/state/data_namespace.py:15` | `See docs/architecture/session-and-state/session-and-state-arch.md §2.3.` | DELETE. |
| `packages/haywire-core/src/haywire/core/session/protocols.py:34`, `session/context.py:20, 69` | Same pattern. | DELETE. |
| `barn/haybale-graph-editor/haybale_graph_editor/state/edit_state.py:25` | Same pattern. | DELETE. |
| `barn/haybale-studio/haybale_studio/state/__init__.py:3` | Same pattern. | DELETE. |
| **All of `core/marketstall/*`** | Every file headers references "spec §X" (~30 occurrences across `__init__.py`, `cache.py`, `errors.py`, `helpers.py`, `parsing.py`, `platform.py`, `refresh.py`, `subscribe.py`, `types.py`, `url_resolution.py`, `host_providers/*.py`). | FLAG — there is a spec at `internals/specs/marketstall-distribution.md`. See Judgment Calls — these are *load-bearing* references for non-trivial behavior. Recommendation: keep at most one top-level pointer per package, delete the per-symbol section refs. |
| `packages/haywire-core/src/haywire/ui/modals/install_safety_modal.py:1, 83` | `"""Install safety modal — spec §7.4 first-install confirmation."""` and `# … (see .insights/feedback_nicegui_async.md` | DELETE spec ref in module docstring; the `.insights/` ref in the comment may earn its place (Judgment Calls). |
| `packages/haywire-core/src/haywire/ui/editor/base.py:5-9` | `:mod:` reference to `haywire.core.session.handlers` × 2 | KEEP — these are Sphinx cross-references that resolve in the rendered API docs, not external `docs/` paths. |
| `barn/haybale-marketplace/haybale_marketplace/editors/library_overview_editor.py:1435` | `# _install_package works. See .insights/feedback_nicegui_async.md.` | KEEP — `.insights/` is the established trap-doc location per CLAUDE.md. |

Verbatim sample (D4):
```python
# packages/haywire-core/src/haywire/core/marketstall/refresh.py:1-12
"""Refresh pipeline — spec §8.

Filter functions (apply_ignores, apply_blocked, apply_heaps_shadow,
apply_first_come_first_served) are pure transformations over Haybale lists.
The `refresh()` orchestrator composes them with the HTTP cache layer.

Conflict-resolution order (spec §8.2):
  1. apply_blocked per subscription (hide rejected names)
  2. apply_ignores per subscription (skip names with another preferred source)
  3. apply_heaps_shadow across the combined candidate list
  4. apply_first_come_first_served as the deterministic safety net
"""
```

```python
# packages/haywire-core/src/haywire/core/state/base.py:75-77
    See docs/architecture/session-and-state/session-and-state-arch.md.
    """
```

---

### D5 — Speculative / future-extension remark

| Location | Description | Disposition |
|---|---|---|
| `packages/haywire-core/src/haywire/core/session/signals/bus.py:65-68` | `If cross-thread emission becomes a requirement, revisit at that point (and probably wrap with ``call_soon_threadsafe`` on the ``Session`` layer rather than complicating the bus itself).` | DELETE per cleanup goals ("no speculative remarks"). |
| `packages/haywire-core/src/haywire/core/state/data_namespace.py:12` | `lookup — no caching. Phase 2 reactive auto-tracking will subscribe …` | DELETE the "Phase 2 …" sentence. |
| `packages/haywire-core/src/haywire/core/session/context.py:99` | `# fields are available, in case a future signal-field initializer reads …` | SHORTEN — drop "in case a future". |
| `packages/haywire-core/src/haywire/core/session/signals/descriptor.py:53` | `# Log at debug for observability if a future cycle introduces a real …` | SHORTEN — drop "if a future cycle introduces". |
| `barn/haybale-studio/haybale_studio/editors/properties_editor.py:183-188` | (also D2) "Future per-panel-redraw optimisation hooks in here…" | DELETE. |
| `barn/haybale-studio/haybale_studio/editors/properties_editor.py:191` | `del event  # forwarded, not inspected (yet)` | SHORTEN — drop "(yet)". |
| `packages/haywire-core/src/haywire/core/marketstall/host_providers/__init__.py:17-18` | `# BitbucketProvider() — deferred; see spec §5.2` and `# GiteaProvider()  — deferred; see spec §5.2` | FLAG — these are dead placeholder lines; consider deleting both. |
| `packages/haywire-core/src/haywire/core/types/port.py:513` | `TODO: Not shure if this approach is correct` | FLAG — typo + open question; either resolve or remove. |
| `packages/haywire-core/src/haywire/core/node/base.py:1103` | `TODO: what shall we do on validation failure? Raise exception?` | FLAG — open question in a docstring; resolve or remove. |
| `packages/haywire-core/src/haywire/core/node/base.py:65-66` | `# TODO: CallbackSystem` followed by `"""event nodes store here the event subscription"""` | FLAG — orphan TODO; if no plan, delete. |

Verbatim sample (D5):
```python
# packages/haywire-core/src/haywire/core/session/signals/bus.py:60-68
    Not thread-safe by design — all session work runs on the NiceGUI event
    loop's main thread. If cross-thread emission becomes a requirement,
    revisit at that point (and probably wrap with ``call_soon_threadsafe``
    on the ``Session`` layer rather than complicating the bus itself).
```

---

### D6 — Over-long explanation reducible to a terse do/don't

| Location | Description | Disposition |
|---|---|---|
| `packages/haywire-core/src/haywire/core/node/base.py:200-237` | `add()` docstring (38 lines) — accepts, automatic actions, raises, three multi-line examples. The "PortSpec dict vs DataPort instance" line is internal; the auto-assignment list is internal mechanism. | SHORTEN: keep "Add a port. Returns the DataPort." + one code example. Drop "When given a PortSpec, instantiates the port with wrapper reference available immediately - no race condition!" (internal). |
| `packages/haywire-core/src/haywire/core/node/base.py:282-319` | `group()` docstring (37 lines, two large example blocks). | SHORTEN to one example. |
| `packages/haywire-core/src/haywire/core/node/base.py:333-364` | `section()` docstring (31 lines, two examples). | SHORTEN. |
| `packages/haywire-core/src/haywire/core/node/base.py:425-462` | `rejig()` docstring with three RST `.. code-block::` examples. | SHORTEN — one example suffices. |
| `packages/haywire-core/src/haywire/core/node/base.py:148-178` | `cache` and `store` properties each have multi-paragraph "Use for X / Use for Y" bullet lists + example. | SHORTEN both to one line + tiny example. |
| `packages/haywire-core/src/haywire/ui/editor/base.py:31-59` | `BaseEditor` class docstring narrates "Editor instances are lazily created and cached — when two browser windows are open, each session has its own…" + "Subclasses must implement:" + "Class attributes (set by @editor decorator):" | SHORTEN — remove the implementation narration; abstract methods document themselves. |
| `packages/haywire-core/src/haywire/ui/editor/base.py:76-100` | `on_focus` docstring (24 lines covering trigger conditions + lifecycle + design rationale). | SHORTEN; move "Runs before draw() on the newly-activated wrapper" to a one-line note. |
| `packages/haywire-core/src/haywire/core/session/session_manager.py:69-91` | `remove_session` docstring narrates ordering rationale "Order: session.cleanup() runs first … This way a panel/editor that reads ctx.data[X] during its own cleanup still sees the instance." | SHORTEN — keep "Clean up and remove a session by ID. Args: session_id." Move ordering note to a comment beside the actual ordering. |
| `barn/haybale-core/haybale_core/nodes/for_loop.py:86-107` | `worker` docstring includes "The VM will: 1. Call worker… 2. Get loop_body outlet… 3. Execute loop body flow…" — internal VM behavior, irrelevant to node authors copying this as a template. | DELETE the VM walk-through. |
| `barn/haybale-marketplace/haybale_marketplace/library_manager.py:54-70`, `:128-137` | `_write_install_to_pyproject` and `_apply_os_to_pyproject` docstrings include "Spec rows:" and "Spec §2.1 rules:" multi-line lists. | SHORTEN per file convention. |
| `packages/haywire-core/src/haywire/core/state/base.py:84-93` | `__init__` docstring on `AppState` spends 8 lines explaining super().__init__() requirement. | SHORTEN to one terse "Subclasses overriding __init__ must call super().__init__()." |

Verbatim sample (D6):
```python
# packages/haywire-core/src/haywire/core/node/base.py:200-237 (excerpt)
    def add(self, spec: "dict[Any, Any] | PortSpec") -> DataPort:
        """
        Add a port (inlet or outlet) to the node with automatic hierarchy tracking.

        Accepts either:
        - PortSpec dict (from FLOAT.as_inlet(), etc.) - instantiates port
        - DataPort instance (backward compatibility)

        When given a PortSpec, instantiates the port with wrapper reference
        available immediately - no race condition!

        This method automatically:
        - Assigns the port to the current group (if in a group context)
        - Assigns the port to the current section (if in a section context)
        - Assigns a display order
        - Preserves connections if replacing an existing port (during reconfiguration)
        - Unflags the port if in a rejig context
        ...
```

---

### C1 — Comment over-long or narrating removed / previous code

| Location | Description | Disposition |
|---|---|---|
| `packages/haywire-core/src/haywire/core/di/config.py:392-410` | `# Phase 1 — subscribe BEFORE the enable loop …` / `# Phase 2 — subscribe AFTER the enable loop, then catch up on every …` | SHORTEN — drop "Phase 1"/"Phase 2" labels; keep the cause-and-effect ("subscribe BEFORE so CLASS_ADDED events are caught"). |
| `packages/haywire-core/src/haywire/core/registry/base.py:548, 561` | `# Step 1: Reload non-managed helper modules first` / `# Step 2: …` | KEEP — these are sequence labels on actual sequential steps. Consider trimming the noun prose. |
| `packages/haywire-core/src/haywire/core/marketstall/refresh.py:226-301` | Seven `# Step N: …` headers across one function. | KEEP — sequence-labeling a 75-line procedure earns its place. |
| `packages/haywire-core/src/haywire/core/node/base.py:60-67` | `# TODO: CallbackSystem` + `"""event nodes store here the event subscription"""` adjacent to `self.event_subscription = None` | FLAG — orphan TODO + a docstring assigned to a runtime attribute (no effect). |
| `packages/haywire-core/src/haywire/core/library/identity.py:18-24` | 7-line comment explaining why dependencies must be specified for hot-reload. | KEEP — this is a non-evident architectural note. Could SHORTEN. |
| `barn/haybale-studio/haybale_studio/editors/properties_editor.py:79-90, 92-97, 111-124` | Three multi-paragraph "why we do this here" comment blocks (15+ lines each) inside class body. | SHORTEN to one terse line each — most of the prose is design-doc level. |
| `barn/haybale-studio/haybale_studio/editors/properties_editor.py:138-140` | `# No panel registry reachable on this context — editor runs / # without panel-driven redraws.` | KEEP — short, explains a silent return. |
| `packages/haywire-core/src/haywire/core/types/port.py:60-149` | Almost every dataclass field has a triple-quoted "field docstring" describing it. These are NOT real docstrings (Python ignores triple-quoted strings after dataclass fields), they read as inline narration. | FLAG — pattern decision: keep the field-comment style or migrate to `# comment` + drop the strings. Many strings here ("Internal flag…", "Active linked EdgeWrapper instances. Used for pipe building.") are pure internal narration. |
| `packages/haywire-core/src/haywire/ui/components/graph/canvas.py:42-46` | Comment explaining why `zoom-pan-state` events broadcast on `document` and why this id is needed (cross-canvas event isolation). | KEEP — non-evident, references a real bug class. |
| `packages/haywire-core/src/haywire/core/marketstall/refresh.py:7-11` (also D4) | `Conflict-resolution order (spec §8.2):` followed by a 4-line numbered list. | KEEP the numbered list (it's behavior); DELETE "(spec §8.2)". |

Verbatim sample (C1):
```python
# packages/haywire-core/src/haywire/core/types/port.py:60-78 (selected)
    _data: DataField = field(init=False, repr=False, metadata={"serialize": False})
    """DataField instance storing port data (set in __post_init__)"""

    # Type tracking
    type_cls: type[IType] | None = field(default=None, metadata={"serialize": False})
    """The type class (FLOAT, ArrayType, etc.)"""

    _linked_edges: dict[str, EdgeWrapper] = field(
        default_factory=dict, repr=False, metadata={"serialize": False}
    )
    """Active linked EdgeWrapper instances. Used for pipe building."""
```

---

### H1 — Module header referencing an implementation plan

| Location | Description | Disposition |
|---|---|---|
| `packages/haywire-core/src/haywire/core/marketstall/__init__.py:1` | `"""Marketstall distribution runtime — spec internals/specs/marketstall-distribution.md."""` | SHORTEN — drop the path. |
| `packages/haywire-core/src/haywire/core/marketstall/types.py:6` | "data-layer only in this plan, wired through the UI in slice 5." | DELETE — "plan / slice 5" is implementation-plan vocabulary. |
| `packages/haywire-core/src/haywire/ui/modals/install_safety_modal.py:1` | `"""Install safety modal — spec §7.4 first-install confirmation."""` | SHORTEN — drop "spec §7.4". |
| `packages/haywire-core/src/haywire/core/marketstall/url_resolution.py:1`, `subscribe.py:1`, `cache.py:1`, `platform.py:1`, `parsing.py:1`, `refresh.py:1`, `helpers.py:1`, `errors.py:1`, `host_providers/__init__.py:1`, `host_providers/{base,github,gitlab,config}.py:1` | Every marketstall sub-module headers with `— spec §X.Y`. | FLAG / SHORTEN — see Judgment Calls. |
| `packages/haywire-core/src/haywire/ui/app/slot.py:311` | `"""... so the multi-instance migration surfaces …"""` (excerpt) | SHORTEN — drop "multi-instance migration"; describe the warning condition only. |

Verbatim sample (H1):
```python
# packages/haywire-core/src/haywire/core/marketstall/types.py:1-7
"""Marketstall runtime dataclasses — spec §2 and §14.

The Haybale dataclass replaces the legacy MarketplaceEntry. Adds the `os` field
from §2.1; same shape otherwise. Subscription dataclasses for [[markets]] and
[[stalls]] gain the `blocked` array introduced for the first-install safety
modal (§7.4); data-layer only in this plan, wired through the UI in slice 5.
"""
```

---

### H2 — Module header narrating architecture that belongs in the docs

| Location | Description | Disposition |
|---|---|---|
| `packages/haywire-core/src/haywire/core/graph/editor.py:1-12` | Module header includes "Design Philosophy:" + 3 bullets describing upstream/downstream callback architecture. | SHORTEN to one sentence; design notes belong in `docs/architecture/`. |
| `packages/haywire-core/src/haywire/core/di/context.py:1-22` | 22-line module header explaining ambient context, why-globals, and Usage examples. | KEEP-and-SHORTEN — the "why module-level globals" line is a real, non-evident decision worth a brief note. The Usage block can shrink to one read/write example. |
| `packages/haywire-core/src/haywire/core/execution/vm.py:1-10` | "The VM is responsible for: 5 bullets" — architectural responsibilities, not user-facing API. | SHORTEN. |
| `packages/haywire-core/src/haywire/core/state/base.py:1-11` | Module docstring "A library author **never directly subclasses `LibraryState`**. They pick one of the concrete scope bases…" + "The mental rule is one line: *scope = base class*." | SHORTEN — collapse to one or two sentences; the class docstrings can carry the rest. |
| `packages/haywire-core/src/haywire/core/settings/descriptor.py:1-25` | 25-line module header on the descriptor's two operating modes + "Convenience factories". | SHORTEN — the per-class docstrings already cover modes. |
| `packages/haywire-core/src/haywire/core/marketstall/refresh.py:1-12` | Module header lists "Conflict-resolution order" as a numbered architectural narration. | SHORTEN — keep the list (behavior), drop "spec §8.2" + the framing. |
| `packages/haywire-core/src/haywire/core/session/session_manager.py:1-9` | Multi-paragraph module header narrating Session model. | SHORTEN. |
| `packages/haywire-studio/src/haywire_studio/app.py:1-13` | Multi-paragraph module header narrating per-session shells, library registry sharing, haystack lifecycle. | SHORTEN — promote to a single sentence; the haystack-lifecycle note is more belongs-in-docs. |
| `barn/haybale-haystack/haybale_haystack/persistence.py:1-30` | 30-line module header narrating TOML schema, notes, "do NOT switch to tomli without updating all callers" rule. | SHORTEN — the schema is the data; keep a brief reference and the toml-package rule (genuinely load-bearing). |

Verbatim sample (H2):
```python
# packages/haywire-core/src/haywire/core/execution/vm.py:1-10
"""
Haywire Virtual Machine - Executes control and data flows.

The VM is responsible for:
- Navigating control flow based on runtime decisions
- Managing execution stacks (done, loopback)
- Evaluating localized data flows
- Managing execution context
- Detecting infinite loops
"""
```

---

## Positive exemplars

Docstrings that already match the target style. Use these as the look-and-feel
reference for the cleanup pass.

1. **`packages/haywire-core/src/haywire/core/types/enums.py:1-30`** — `FlowType`,
   `PortType` enums: short class docstrings + bullet-per-member, no narration.
   ```python
   class FlowType(Enum):
       """
       Type of data flow through a port.

       - NONE: Configuration port (no flow, not a pin)
       - CONTROL: Execution flow (determines when nodes execute)
       - DATA: Data flow (passes values between nodes)
       - CALLBACK: Callback registration (event nodes declare interest)
       """
   ```

2. **`packages/haywire-core/src/haywire/core/library/base.py:53-87`** — single-line
   property/method docstrings ("Check if the library is currently enabled",
   "Enable the library and register its components"). Terse, accurate, no padding.

3. **`packages/haywire-core/src/haywire/core/graph/editor.py:156-166`** —
   `get_node_wrapper`, `list_node_wrappers`, `get_available_node_regkeys`:
   one-liners that describe what the method returns. The kind of docstrings
   the rest of the file should look like.

4. **`packages/haywire-core/src/haywire/ui/panel/base.py:57-68`** — `poll` and
   `draw` of `BasePanel`: terse hooks, one sentence each.

5. **`packages/haywire-core/src/haywire/core/node/behavior.py:97-119`** — the
   `is_control_node` / `is_data_node` / `is_event_node` / etc. property
   docstrings. One line, mirrors the parenthetical of the implementation.

6. **`packages/haywire-core/src/haywire/core/types/port.py:91-105`** —
   `__hash__`, `is_config`, `is_outlet`, `is_inlet`: one-liner docstrings that
   match the method's actual behavior.

7. **`packages/haywire-core/src/haywire/core/marketstall/refresh.py:69-78`** —
   `apply_ignores`: one-sentence summary + one-sentence "why" ("the user picked
   another source for these names at conflict-resolution time"). Drop the
   "Per spec §8.2" prefix and this is the model for the whole file.

8. **`packages/haywire-core/src/haywire/core/types/enums.py:5-12`** — see #1
   (same shape worth calling out).

9. **`packages/haywire-core/src/haywire/core/session/session_manager.py:95-107`**
   — `get_session`, `active_sessions`, `session_count`: clean one-liners.

10. **`packages/haywire-core/src/haywire/core/library/identity.py:18-24`** —
    *the comment* above `dependencies` (not a docstring): genuinely
    non-evident architectural note about hot-reload + `isinstance` checks.
    A good model for the "implementation reflection in comment, not docstring"
    rule.

---

## Judgment calls / proposed rules

These are decisions the cleanup prompt must resolve before applying findings.

### J1 — `core/marketstall/*` "spec §X" references

Every file in `core/marketstall/` and its `host_providers/` subpackage carries
one or more `spec §X.Y` references. The pointed-to document
(`internals/specs/marketstall-distribution.md`) is the source of truth for
this subsystem's behavior — it is referenced not for backstory but for
*rule provenance*. Removing all of them would erase that traceability.

**Question:** do you want to (a) strip all spec references and rely on
git/code review for traceability, (b) keep one top-level pointer per package
(in `__init__.py`) and strip the rest, or (c) keep them but require they
appear only on rules / data shapes (e.g. "blocked names; persisted only via
file edit") and never on procedural narration?

Recommended default: **(b)**.

### J2 — `.insights/` references

CLAUDE.md establishes `.insights/` as the canonical home for trap notes.
Cross-references like `barn/haybale-marketplace/.../library_overview_editor.py:1435`
(`# … See .insights/feedback_nicegui_async.md.`) point readers to a real bug
class. These should arguably KEEP, in tension with the D4 "no references to
docs or other files" rule.

**Question:** Is `.insights/` considered "the docs" for D4 purposes (=> strip),
or is it part of the source tree's own commentary (=> keep)?

Recommended default: **keep `.insights/` references in comments only (not
docstrings)**. The reference is a trap-evasion signal for the next reader.

### J3 — Triple-quoted "field docstrings" on dataclass attributes

`core/types/port.py`, `core/node/behavior.py`, and several `marketstall/types.py`
classes use the pattern `field_name: T = field(...); """description"""`. Python
ignores these strings at runtime; tooling like Sphinx-autodoc picks some up but
inconsistently. They effectively act as comments with `"""` syntax.

**Question:** do you want a project rule preferring `# comment` over `"""docstring"""`
for non-method module-level / class-attribute commentary, or keep the existing
pattern?

Recommended default: **keep the existing pattern but apply the same content
rules** (no D1/D2/D5 content); many of these strings (`"""Internal flag to track
if port link has structurally changed"""`) read like the comments they
effectively are and should be SHORTENED in place.

### J4 — Deprecated stubs (`console_bridge.py`, `library_manager.py`)

Three methods carry `"""Deprecated no-op."""` / `"""Deprecated alias for X."""`.
The cleanup goal says no historical breadcrumbs, but a deprecated public
function's docstring naming its replacement is *consumer-relevant* if external
callers might still exist.

**Question:** are these symbols still part of the public API surface (=>
keep the deprecation line), or can they be deleted outright (=> delete the
symbol)?

Recommended default: **verify zero in-tree callers, then delete the symbol
entirely**.

### J5 — TODOs / open questions inside docstrings

Three cases: `node/base.py:1103` (`TODO: what shall we do on validation
failure?`), `types/port.py:513` (`TODO: Not shure if this approach is
correct`), `node/base.py:65` (`# TODO: CallbackSystem`).

**Question:** general rule for TODOs — leave in place (current practice),
move to an issue tracker, or strip them?

Recommended default: **strip TODOs from docstrings (D5); leave terse `# TODO:`
comments alone but consider an issue link if known**.

### J6 — Examples vs prose in `setting` descriptor docstring

`core/settings/descriptor.py:39-166` is a 120-line parameter manual that
behaves as the de facto API reference for the most-used framework symbol. Some
prose is justified — the question is how much.

**Question:** convert to a code-example-driven docstring (one example per
parameter family) + a one-line per-parameter rule, or keep the NumPy-style
manual but trim each entry to 1-2 lines?

Recommended default: **trim per-parameter prose to 1-2 lines; keep the
top-level class example; remove parameters that just restate the type.**

### J7 — Regression-test rationale in test files

`barn/haybale-testing/haybale_testing/panels/test_session_state_panel.py:6`
references "that previously produced two distinct class objects" — this is
historical, but for a regression test it's the *reason the test exists*.

**Question:** for test files, do "regression-for-X" history docstrings stay
(they explain the test's reason for being) or go (per D2)?

Recommended default: **allow regression-test history**, since the assertion
itself doesn't carry the rationale. The cleanup prompt should call this out
as an exception to D2.

### Proposed additional rules

- **R1 — `:mod:` / `:meth:` / `:class:` Sphinx cross-references are allowed**;
  they resolve in the rendered API docs. The D4 ban applies to *out-of-tree*
  doc paths (`docs/`, `internals/`).
- **R2 — Preserve per-file docstring style.** Files in `core/settings/` use
  NumPy `Parameters ----`; files in `core/node/` use Google `Args:`; do not
  normalize across the tree.
- **R3 — Method docstrings on `@property` getters should be one line** (this
  is already the norm in `behavior.py`; deviations in `node/base.py` cache/store
  should be SHORTENED to match).
- **R4 — Dataclass field "docstrings" follow the same content rules.** Length
  cap: one short line. If you find yourself writing two lines, switch to a
  `# comment` above the field.

---

## Project vocabulary & style notes

Terms with specific meanings in-repo (use these verbatim, do not paraphrase):

- **Haybale** — both the cataloged unit ("a haybale") and the dataclass
  representing one. Replaces the older `MarketplaceEntry` (don't reintroduce
  the old term, but also don't narrate the rename).
- **Marketstall** — the package distribution runtime
  (`core/marketstall/`). The user-facing concept is "marketplace" (file:
  `marketplace.toml`). "Marketstall" is the runtime layer that reads it.
- **Library** — five distinct meanings; canonical glossary at
  `docs/reference/glossary.md`. Avoid reintroducing the meaning by paraphrase.
- **Pin** / **Port** — *pin* is the user-visible canvas concept; *port* is
  the engine-side `DataPort`. Editor and engine layers should not blur them.
- **Flow** — has two senses: "control flow" / "data flow" (the dual-flow
  model) and the runtime `Flow` object the VM executes.
- **Editor** vs **Panel** — Editor is the slot-mounted UI module; Panel is
  the contributor mounted *inside* an editor. Different base classes.
- **Settings** / **shadow** / **watch** — the reactive descriptor system.
  `shadow()` = writable mirror, `watch()` = read-only mirror. Don't reword.
- **AppState** vs **SessionState** — concrete bases of `LibraryState`. Authors
  pick a scope by base class; the scope is *not* declared elsewhere.
- **Hot-reload** / **dependency** — `@library(dependencies=[...])` takes
  Python package names, not the library `id`. The hot-reload trap is
  load-bearing; the comment in `library/identity.py:18-24` should survive cleanup.
- **Rejig** — context manager for dynamic port reconfiguration on a node.
- **Haystack** vs **GraphEntry** — Haystack is a named set of open graphs;
  GraphEntry is one entry inside it.

House style observations:

- Module headers usually open with a one-line summary in the form
  `"Component — short purpose."` or `"Component - short purpose"` (em-dash or
  hyphen; mixed). No strong preference is enforced.
- Most `@node` / `@library` / `@panel` / `@editor` docstrings demonstrate
  usage with a code snippet rather than prose — extend this.
- Decorators are documented on the decorator function, not on the resulting
  class. Preserve this.
- ASCII art / box-drawing characters (`━`, `┃`, `┓`, `┛`) appear in
  `BasePanel` example — house style permits but is rare; don't propagate.
- Long argument lists are sometimes split into `# ----` banner comments
  (`core/node/base.py:71-110`) — preserve where they aid navigation.
