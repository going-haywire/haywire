# PanelRedrawCoordinator Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract the ~120 lines of panel-subscription machinery out of `PropertiesEditor` into a standalone, unit-testable `PanelRedrawCoordinator` service.

**Architecture:** A new framework-level service in `haywire-core` owns the complete "keep my panel redraw subscriptions correct" responsibility: it subscribes to every signal type that display panels declare via `redraw_on=`, re-subscribes when the panel catalog changes (install / uninstall / hot-reload), and tears everything down on cleanup. It collaborates only with `PanelRegistry`, the session signal bus, a `focus_provider` callable, and an `on_redraw` callback — no studio knowledge. `PropertiesEditor` keeps registry *resolution* (the part that can fail) and delegates all *subscription* work to the coordinator.

**Tech Stack:** Python 3, NiceGUI editor/panel framework, `haywire.core.session.signals` typed pub/sub bus, `pytest`, `ruff`, `mypy`. Package manager: `uv`.

---

## Background: what is being moved

`PropertiesEditor` (`barn/haybale-studio/haybale_studio/editors/properties_editor.py`) is today the **only** Focus-driven panel host. It carries 7 private methods (lines ~100–219) that manage two distinct subscription surfaces:

1. **Per-signal bus subscriptions** — for each `redraw_on=` signal type declared by a display panel, subscribe a closure that calls `wrapper.redraw()`. Unsubscribe handles held in `self._panel_bus_unsubscribes`.
2. **Registry lifecycle channel** — `add_batch_event_subscriber(...)` on the `PanelRegistry`, so that when the panel catalog changes the editor recomputes surface #1. Tracked by `self._attached_panel_registry`.

These two surfaces are **one machine**: the lifecycle channel exists *only* to drive reconciliation of the per-signal subs. The extraction moves the entire machine into `PanelRedrawCoordinator`.

### Collaborator API reference (read before writing code)

- **Subscribe to a signal:** `unsub = session.subscribe(signal_type, handler)` where `handler: Callable[[Signal], None]`. Returns an unsubscribe handle; calling it twice is a safe no-op. Source: `packages/haywire-core/src/haywire/core/session/session.py:101`.
- **Publish (tests only):** `session.publish(SignalInstance())`. Source: `session.py:77`.
- **Registry: union of redraw signals for a focus:** `registry.get_redraw_signals_for_focus(focus) -> Set[type[Signal]]`. Source: `packages/haywire-core/src/haywire/ui/panel/registry.py:152`.
- **Registry: lifecycle channel:** `registry.add_batch_event_subscriber(cb)` / `registry.remove_batch_event_subscriber(cb)` where `cb: Callable[[list[LifeCycleEvent]], None]` (`LifeCycleBatchCallback`). Idempotent add (no double-register). Source: `packages/haywire-core/src/haywire/core/registry/base.py:888,905`. Test-only fire: `registry._notify_batch_event_subscribers()`.
- **`LifeCycleBatchCallback`** = `Callable[[list[LifeCycleEvent]], None]`. Source: `packages/haywire-core/src/haywire/core/registry/lifecycle_event.py:233`.
- **Focus type:** `haywire.ui.panel.focus.Focus`. Editor's existing focus computation: `PropertiesEditor._compute_toolbar_focuses(registry) -> list[type[Focus]]` (sorts `registry.get_display_focuses()` by `Focus.order`). This becomes the `focus_provider` passed to the coordinator.

### Design decisions locked in (from the design interview)

- **Name** is `PanelRedrawCoordinator` (NOT `PanelRedrawSubscriber` — "subscriber" is a reserved term in this codebase meaning a Signal *listener*; this class coordinates several). No glossary entry, no ADR.
- **Location**: code in `packages/haywire-core/src/haywire/ui/panel/redraw_coordinator.py`; tests in `tests/ui/panel/test_redraw_coordinator.py`.
- **Constructor**: `(registry, session, on_redraw, focus_provider)`. Construction is **inert** — no subscriptions happen until `start()`.
- **Ownership**: coordinator owns BOTH subscription surfaces. The editor's `_attach_panel_registry`, `_detach_panel_registry`, `_on_panel_registry_event`, `_subscribe_panel_event_handlers`, `_rebuild_panel_event_subscriptions`, `_make_panel_redraw_closure`, `_unsubscribe_panel_event_handlers` are all deleted.
- **Editor gate**: `draw()` uses `if self._coordinator is None:` to wire on first draw. Editor keeps registry *resolution* + its error handling (absent / missing / raises). On a resolution failure `_coordinator` stays `None` so the next redraw retries — preserving today's behaviour.
- **Goal**: testability + readability. Reuse is latent, not a claimed driver.

---

## File Structure

- **Create:** `packages/haywire-core/src/haywire/ui/panel/redraw_coordinator.py` — the `PanelRedrawCoordinator` service. One responsibility: maintain panel redraw subscriptions for one editor instance.
- **Create:** `tests/ui/panel/test_redraw_coordinator.py` — wrapper-free unit tests for the coordinator (fake registry + lambda focus-provider + counter callback).
- **Modify:** `packages/haywire-core/src/haywire/ui/panel/__init__.py` — export `PanelRedrawCoordinator`.
- **Modify:** `barn/haybale-studio/haybale_studio/editors/properties_editor.py` — delete the 7 subscription methods + 2 fields, add `self._coordinator`, rewrite `draw()` gate and `cleanup()`.
- **Modify:** `tests/ui/properties_editor/test_event_bus_migration.py` — rewrite the editor-shaped tests to assert through the `_coordinator` seam / behaviour; remove the tests that became pure coordinator units (now covered in the new file).

---

## Pre-flight: establish a clean baseline

- [ ] **Step 0: Confirm the area is clean before touching it**

Run:
```bash
uv run ruff check packages/haywire-core/src/haywire/ui/panel/ barn/haybale-studio/haybale_studio/editors/properties_editor.py
uv run mypy packages/haywire-core/src/ barn/haybale-studio/haybale_studio/
uv run pytest tests/ui/panel/ tests/ui/properties_editor/ -q
```
Expected: all clean / all pass. If anything fails here, STOP and raise it with the user — the codebase is supposed to be error-free per CLAUDE.md, and a pre-existing failure must not be attributed to this work.

---

## Task 1: Create `PanelRedrawCoordinator` (inert construction + start + cleanup)

**Files:**
- Create: `packages/haywire-core/src/haywire/ui/panel/redraw_coordinator.py`
- Test: `tests/ui/panel/test_redraw_coordinator.py`

This task builds the coordinator's core: inert construction, `start()` (wires per-signal subs + the lifecycle channel), and `cleanup()` (tears both down). Reconciliation-on-catalog-change is verified in Task 2 against the same class.

- [ ] **Step 1: Write the failing test — construction is inert**

Create `tests/ui/panel/test_redraw_coordinator.py`:

```python
"""Unit tests for PanelRedrawCoordinator.

The coordinator owns an editor's panel-driven redraw subscriptions:
per-signal bus subscriptions (one per redraw_on signal type declared by
display panels of the editor's focuses) plus the panel registry's batch
lifecycle channel used to reconcile that set on catalog change.

These tests exercise the coordinator directly with fakes — no
EditorWrapper, no real Session — which is the whole point of the
extraction.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import haywire.core.graph.editor  # noqa: F401 — circular-import guard (see CLAUDE.md)

from haywire.core.session.signals import Signal
from haywire.ui.panel.redraw_coordinator import PanelRedrawCoordinator


# --- Fakes -----------------------------------------------------------------


@dataclass(frozen=True)
class _SigA(Signal):
    pass


@dataclass(frozen=True)
class _SigB(Signal):
    pass


class _FakeFocus:
    """Stand-in Focus class. The coordinator only uses identity / passes it
    straight to registry.get_redraw_signals_for_focus, so any object works."""

    id = "fake-focus"


class _FakeSession:
    """Records subscribe() calls and lets tests fire a signal type."""

    def __init__(self) -> None:
        self.handlers: dict[type, list[Callable]] = {}
        self.unsub_calls = 0

    def subscribe(self, signal_type, handler):
        self.handlers.setdefault(signal_type, []).append(handler)

        def _unsub():
            self.unsub_calls += 1
            self.handlers.get(signal_type, []).remove(handler)

        return _unsub

    def fire(self, signal_type) -> None:
        for h in list(self.handlers.get(signal_type, [])):
            h(signal_type())


class _FakeRegistry:
    """Records batch-subscriber wiring and returns a fixed signal union."""

    def __init__(self, signals_by_focus: dict | None = None) -> None:
        self._signals_by_focus = signals_by_focus or {}
        self.batch_subscribers: list[Callable] = []

    def get_redraw_signals_for_focus(self, focus):
        return set(self._signals_by_focus.get(focus, set()))

    def add_batch_event_subscriber(self, cb) -> None:
        if cb not in self.batch_subscribers:
            self.batch_subscribers.append(cb)

    def remove_batch_event_subscriber(self, cb) -> None:
        if cb in self.batch_subscribers:
            self.batch_subscribers.remove(cb)

    def notify(self) -> None:
        for cb in list(self.batch_subscribers):
            cb([])


def _make_coordinator(registry, session):
    redraws: list[int] = []
    focus = _FakeFocus()
    coord = PanelRedrawCoordinator(
        registry=registry,
        session=session,
        on_redraw=lambda: redraws.append(1),
        focus_provider=lambda: [focus],
    )
    return coord, redraws, focus


# --- Tests -----------------------------------------------------------------


def test_construction_is_inert():
    """Constructing the coordinator must not subscribe to anything."""
    registry = _FakeRegistry({})
    session = _FakeSession()
    coord, _redraws, _focus = _make_coordinator(registry, session)

    assert session.handlers == {}
    assert registry.batch_subscribers == []
    del coord
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/ui/panel/test_redraw_coordinator.py::test_construction_is_inert -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'haywire.ui.panel.redraw_coordinator'`.

- [ ] **Step 3: Write the coordinator (inert ctor + start + cleanup)**

Create `packages/haywire-core/src/haywire/ui/panel/redraw_coordinator.py`:

```python
# packages/haywire-core/src/haywire/ui/panel/redraw_coordinator.py

from __future__ import annotations

import logging
from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from haywire.core.session.session import Session
    from haywire.core.session.signals import Signal
    from haywire.ui.panel.focus import Focus
    from haywire.ui.panel.registry import PanelRegistry

logger = logging.getLogger(__name__)


class PanelRedrawCoordinator:
    """Owns one editor instance's panel-driven redraw subscriptions.

    A Focus-driven panel host (today only PropertiesEditor) wants to
    redraw whenever any display panel of its current focuses declares,
    via ``@panel(..., redraw_on=(...))``, that it cares about a signal —
    and to keep that subscription set correct as the panel catalog
    changes (install / uninstall / hot-reload).

    This coordinator owns BOTH surfaces of that machine:

    1. Per-signal bus subscriptions: one ``session.subscribe`` per signal
       type in the union of ``redraw_on`` across the host's focuses. Each
       fires ``on_redraw`` (the host re-mounts its panels).
    2. The panel registry's batch lifecycle channel: reconciles surface
       (1) whenever the catalog changes.

    Construction is inert. Call :meth:`start` to wire everything and
    :meth:`cleanup` to tear it down. Owned by the host editor; not shared.
    """

    def __init__(
        self,
        registry: "PanelRegistry",
        session: "Session",
        on_redraw: Callable[[], None],
        focus_provider: Callable[[], list[type["Focus"]]],
    ) -> None:
        """Construct (inert — no subscriptions until ``start``).

        Args:
            registry: PanelRegistry to query for ``redraw_on`` unions and
                to attach to for catalog-change reconciliation.
            session: Session whose signal bus carries the redraw signals.
            on_redraw: Called (no args) when a subscribed signal fires.
            focus_provider: Returns the host's current focus list. Called
                on every (re)build so the host stays the single source of
                truth for "which focuses do I show".
        """
        self._registry = registry
        self._session = session
        self._on_redraw = on_redraw
        self._focus_provider = focus_provider
        self._unsubscribes: list[Callable[[], None]] = []
        self._attached = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Attach to the registry lifecycle channel and build the
        per-signal subscription set. Idempotent attach; safe to call once
        per coordinator instance."""
        if not self._attached:
            try:
                self._registry.add_batch_event_subscriber(self._on_registry_event)
                self._attached = True
            except Exception as exc:
                logger.warning(f"PanelRedrawCoordinator: registry attach raised: {exc}")
        self._rebuild()

    def cleanup(self) -> None:
        """Drop all per-signal subscriptions and detach from the registry
        lifecycle channel. Safe to call multiple times."""
        self._unsubscribe_all()
        if self._attached:
            try:
                self._registry.remove_batch_event_subscriber(self._on_registry_event)
            except Exception as exc:
                logger.warning(f"PanelRedrawCoordinator: registry detach raised: {exc}")
            self._attached = False

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _rebuild(self) -> None:
        """Drop current per-signal subs and re-subscribe to the union of
        ``redraw_on`` signals across the host's current focuses."""
        self._unsubscribe_all()
        signal_types: set[type["Signal"]] = set()
        try:
            for focus in self._focus_provider():
                signal_types |= self._registry.get_redraw_signals_for_focus(focus)
        except Exception as exc:
            logger.warning(f"PanelRedrawCoordinator: get_redraw_signals_for_focus raised: {exc}")
            return
        if not signal_types:
            return
        handler = self._make_redraw_handler()
        for signal_type in signal_types:
            self._unsubscribes.append(self._session.subscribe(signal_type, handler))

    def _make_redraw_handler(self) -> Callable[["Signal"], None]:
        """Closure subscribed to every redraw signal. The panel author
        already declared the intent via ``redraw_on=``; the handler just
        asks the host to redraw."""

        def _on_signal(signal: "Signal") -> None:
            del signal  # forwarded, not inspected
            self._on_redraw()

        return _on_signal

    def _unsubscribe_all(self) -> None:
        """Call every held unsubscribe handle, then clear. Idempotent."""
        for unsub in self._unsubscribes:
            try:
                unsub()
            except Exception as exc:
                logger.warning(f"PanelRedrawCoordinator: unsubscribe raised: {exc}")
        self._unsubscribes.clear()

    def _on_registry_event(self, events: list) -> None:
        """Reconcile on any catalog change, then ask the host to redraw.

        We don't inspect the event list: any event might change the union
        (a panel registers / unregisters / reloads with a different
        ``redraw_on=``). Drop all subs and recompute. The catalog change
        can mean new signal types appeared, so the current rendered state
        may be stale — ask for a redraw too."""
        del events  # consumed by the LifeCycleBatchCallback interface
        self._rebuild()
        self._on_redraw()
```

- [ ] **Step 4: Run the inert-construction test**

Run: `uv run pytest tests/ui/panel/test_redraw_coordinator.py::test_construction_is_inert -v`
Expected: PASS.

- [ ] **Step 5: Add start / cleanup tests**

Append to `tests/ui/panel/test_redraw_coordinator.py`:

```python
def test_start_subscribes_to_union_of_redraw_signals():
    """start() subscribes one handler per signal type in the union."""
    registry = _FakeRegistry()
    session = _FakeSession()
    coord, redraws, focus = _make_coordinator(registry, session)
    registry._signals_by_focus = {focus: {_SigA, _SigB}}

    coord.start()

    assert set(session.handlers.keys()) == {_SigA, _SigB}
    # The coordinator attached exactly one bound-method callback to the
    # registry lifecycle channel.
    assert len(registry.batch_subscribers) == 1
    assert getattr(registry.batch_subscribers[0], "__self__", None) is coord


def test_subscribed_signal_fires_on_redraw():
    """Publishing a subscribed signal type invokes on_redraw."""
    registry = _FakeRegistry()
    session = _FakeSession()
    coord, redraws, focus = _make_coordinator(registry, session)
    registry._signals_by_focus = {focus: {_SigA}}

    coord.start()
    session.fire(_SigA)

    assert redraws == [1]


def test_unsubscribed_signal_does_not_fire_redraw():
    """A signal type nobody declared must not be subscribed."""
    registry = _FakeRegistry()
    session = _FakeSession()
    coord, redraws, focus = _make_coordinator(registry, session)
    registry._signals_by_focus = {focus: {_SigA}}

    coord.start()
    session.fire(_SigB)

    assert redraws == []


def test_start_with_empty_union_makes_no_subscriptions():
    """No redraw_on signals → no per-signal subs (but still attaches the
    lifecycle channel, so a later catalog change can add some)."""
    registry = _FakeRegistry({})
    session = _FakeSession()
    coord, _redraws, _focus = _make_coordinator(registry, session)

    coord.start()

    assert session.handlers == {}
    assert len(registry.batch_subscribers) == 1


def test_cleanup_drops_subs_and_detaches():
    """cleanup() unsubscribes every per-signal handle and detaches the
    lifecycle channel."""
    registry = _FakeRegistry()
    session = _FakeSession()
    coord, _redraws, focus = _make_coordinator(registry, session)
    registry._signals_by_focus = {focus: {_SigA, _SigB}}

    coord.start()
    assert session.unsub_calls == 0

    coord.cleanup()

    assert session.unsub_calls == 2
    assert session.handlers == {}
    assert registry.batch_subscribers == []


def test_cleanup_is_idempotent():
    """Calling cleanup twice must not raise or double-unsubscribe."""
    registry = _FakeRegistry()
    session = _FakeSession()
    coord, _redraws, focus = _make_coordinator(registry, session)
    registry._signals_by_focus = {focus: {_SigA}}

    coord.start()
    coord.cleanup()
    coord.cleanup()  # must be a no-op

    assert session.unsub_calls == 1
    assert registry.batch_subscribers == []
```

- [ ] **Step 6: Run all Task 1 tests**

Run: `uv run pytest tests/ui/panel/test_redraw_coordinator.py -v`
Expected: 6 PASS (`test_construction_is_inert`, `test_start_subscribes_to_union_of_redraw_signals`, `test_subscribed_signal_fires_on_redraw`, `test_unsubscribed_signal_does_not_fire_redraw`, `test_start_with_empty_union_makes_no_subscriptions`, `test_cleanup_drops_subs_and_detaches`, `test_cleanup_is_idempotent`).

- [ ] **Step 7: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/panel/redraw_coordinator.py tests/ui/panel/test_redraw_coordinator.py
git commit -m "feat(panel): add PanelRedrawCoordinator with start/cleanup lifecycle

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Reconciliation on catalog change + resilience

**Files:**
- Modify: `tests/ui/panel/test_redraw_coordinator.py` (add tests only)
- (No production change expected — `_on_registry_event` and the try/except guards already exist from Task 1. If a test fails, fix `redraw_coordinator.py`.)

- [ ] **Step 1: Write the reconciliation + resilience tests**

Append to `tests/ui/panel/test_redraw_coordinator.py`:

```python
def test_catalog_change_rebuilds_subscriptions_and_redraws():
    """Firing the registry lifecycle channel recomputes the union and
    redraws once. Start with an empty union, then 'install' a panel that
    declares _SigA."""
    registry = _FakeRegistry({})
    session = _FakeSession()
    coord, redraws, focus = _make_coordinator(registry, session)

    coord.start()
    assert session.handlers == {}
    session.fire(_SigA)
    assert redraws == []

    # 'Install': the union now includes _SigA. Fire the lifecycle channel.
    registry._signals_by_focus = {focus: {_SigA}}
    registry.notify()

    assert redraws == [1]  # the reconciliation itself redrew once
    redraws.clear()

    # Now _SigA publishes reach the coordinator.
    session.fire(_SigA)
    assert redraws == [1]


def test_rebuild_drops_stale_subscriptions():
    """A catalog change that removes a signal from the union must
    unsubscribe the stale per-signal handle."""
    registry = _FakeRegistry()
    session = _FakeSession()
    coord, _redraws, focus = _make_coordinator(registry, session)
    registry._signals_by_focus = {focus: {_SigA, _SigB}}

    coord.start()
    assert set(session.handlers.keys()) == {_SigA, _SigB}

    # 'Uninstall' the panel that declared _SigB.
    registry._signals_by_focus = {focus: {_SigA}}
    registry.notify()

    assert set(session.handlers.keys()) == {_SigA}


def test_registry_query_raising_degrades_gracefully():
    """If get_redraw_signals_for_focus raises, the coordinator logs and
    leaves zero subscriptions rather than propagating."""

    class _RaisingRegistry(_FakeRegistry):
        def get_redraw_signals_for_focus(self, focus):
            raise RuntimeError("intentional bad query")

    registry = _RaisingRegistry()
    session = _FakeSession()
    coord, _redraws, _focus = _make_coordinator(registry, session)

    coord.start()  # must not raise

    assert session.handlers == {}
```

- [ ] **Step 2: Run the new tests**

Run: `uv run pytest tests/ui/panel/test_redraw_coordinator.py -v -k "catalog_change or drops_stale or query_raising"`
Expected: 3 PASS. (If `test_catalog_change_rebuilds_subscriptions_and_redraws` fails because no redraw fired on `notify()`, verify `_on_registry_event` calls `self._on_redraw()` after `self._rebuild()`.)

- [ ] **Step 3: Run the full coordinator suite + type-check the new file**

Run:
```bash
uv run pytest tests/ui/panel/test_redraw_coordinator.py -v
uv run ruff check packages/haywire-core/src/haywire/ui/panel/redraw_coordinator.py
uv run mypy packages/haywire-core/src/haywire/ui/panel/redraw_coordinator.py
```
Expected: all PASS / clean.

- [ ] **Step 4: Commit**

```bash
git add tests/ui/panel/test_redraw_coordinator.py
git commit -m "test(panel): cover PanelRedrawCoordinator reconciliation and resilience

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Export `PanelRedrawCoordinator` from the panel package

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/panel/__init__.py`

- [ ] **Step 1: Write the failing import test**

Append to `tests/ui/panel/test_redraw_coordinator.py`:

```python
def test_coordinator_is_exported_from_panel_package():
    """PanelRedrawCoordinator is importable from the package root, like
    PanelRegistry and Focus."""
    from haywire.ui.panel import PanelRedrawCoordinator as Exported

    assert Exported is PanelRedrawCoordinator
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/ui/panel/test_redraw_coordinator.py::test_coordinator_is_exported_from_panel_package -v`
Expected: FAIL with `ImportError: cannot import name 'PanelRedrawCoordinator' from 'haywire.ui.panel'`.

- [ ] **Step 3: Add the export**

In `packages/haywire-core/src/haywire/ui/panel/__init__.py`, add the import after the `from .registry import PanelRegistry` line:

```python
from .registry import PanelRegistry
from .redraw_coordinator import PanelRedrawCoordinator
```

And add `"PanelRedrawCoordinator"` to `__all__` (after `"PanelRegistry"`):

```python
    "PanelRegistry",
    "PanelRedrawCoordinator",
    "panel",
```

- [ ] **Step 4: Run it to verify it passes**

Run: `uv run pytest tests/ui/panel/test_redraw_coordinator.py::test_coordinator_is_exported_from_panel_package -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/panel/__init__.py tests/ui/panel/test_redraw_coordinator.py
git commit -m "feat(panel): export PanelRedrawCoordinator from panel package

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Wire `PropertiesEditor` to use the coordinator; delete the old machinery

**Files:**
- Modify: `barn/haybale-studio/haybale_studio/editors/properties_editor.py`

This is the destructive-but-mechanical task: delete 7 methods + 2 fields, add `self._coordinator`, rewrite the `draw()` gate and `cleanup()`. The editor KEEPS `_panel_registry` (registry resolution), `_compute_toolbar_focuses` (toolbar still needs it, and it becomes the `focus_provider`), and everything below `_build_layout`.

- [ ] **Step 1: Update imports and `__init__` fields**

In `barn/haybale-studio/haybale_studio/editors/properties_editor.py`:

Add the coordinator import alongside the other panel imports (after `from haywire.ui.panel.host_rendering import ...`):

```python
from haywire.ui.panel.redraw_coordinator import PanelRedrawCoordinator
```

Replace the two subscription-state fields in `__init__`. Remove this block:

```python
        # Panel-driven event-bus unsubscribe handles. Populated in
        # _subscribe_panel_event_handlers (first draw()), reconciled in
        # _on_panel_registry_event on catalog change, drained in cleanup.
        self._panel_bus_unsubscribes: list[Callable[[], None]] = []

        # PanelRegistry this editor is subscribed to (lifecycle batch channel),
        # held so cleanup / reconciliation can detach. None before first draw().
        self._attached_panel_registry: PanelRegistry | None = None
```

with:

```python
        # Panel-driven redraw subscriptions, fully owned by the coordinator.
        # Constructed lazily on first draw() once a panel registry resolves;
        # stays None when no registry is reachable (so each redraw retries).
        self._coordinator: PanelRedrawCoordinator | None = None
```

- [ ] **Step 2: Replace the entire subscription section with `draw()` + `cleanup()`**

Delete the whole block from the `# Panel-contributed event-bus subscriptions` comment header (just above `_subscribe_panel_event_handlers`, ~line 90) down to and including `_on_panel_registry_event` (~line 219) — i.e. these 7 methods: `_subscribe_panel_event_handlers`, `_rebuild_panel_event_subscriptions`, `_make_panel_redraw_closure`, `_unsubscribe_panel_event_handlers`, `_attach_panel_registry`, `_detach_panel_registry`, `_on_panel_registry_event`.

Then replace the existing `draw()` and `cleanup()` (and the `--8<--` markers around them) with:

```python
    # ------------------------------------------------------------------
    # Panel-driven redraw subscriptions
    # ------------------------------------------------------------------
    #
    # Delegated wholesale to a PanelRedrawCoordinator (haywire.ui.panel).
    # The editor only owns registry *resolution* — the part that can fail
    # on a stubbed / non-studio context. Once a registry resolves, the
    # coordinator owns every subscription (per-signal redraw subs + the
    # registry lifecycle channel) and its own teardown.

    def draw(self, context: SessionContext, container: Element) -> None:
        self._container = container
        self._context = context
        # First draw of this instance: resolve the panel registry and hand
        # it to a coordinator. Subsequent redraws re-enter draw() but skip
        # this because _coordinator is already set. If no registry resolves
        # (stubbed context, non-studio host, lookup raises) _coordinator
        # stays None and the next redraw retries — same as the pre-extraction
        # behaviour. Hot-reload discards the instance; the next instance's
        # first draw() builds a fresh coordinator against the current registry.
        if self._coordinator is None:
            registry = self._resolve_panel_registry(context)
            if registry is not None:
                self._coordinator = PanelRedrawCoordinator(
                    registry=registry,
                    session=context.session,
                    on_redraw=self.wrapper.redraw,
                    focus_provider=lambda: self._compute_toolbar_focuses(registry),
                )
                self._coordinator.start()
        self._build_layout(context)

    def _resolve_panel_registry(self, context: SessionContext) -> PanelRegistry | None:
        """Resolve the panel registry for subscription wiring, or None.

        Returns None (no panel-driven redraws) when the session's context
        does not expose a panel registry chain: AttributeError along
        ``context.app.library_service.get_panel_registry()`` (stubbed
        context / non-studio host) is treated as absent; any other
        exception is logged and also treated as absent.
        """
        try:
            registry = self._panel_registry(context)
        except AttributeError:
            return None
        except Exception as exc:
            logger.warning(f"PropertiesEditor: resolving panel registry raised: {exc}")
            return None
        return registry

    def cleanup(self) -> None:
        """Tear down panel-driven redraw subscriptions on instance removal.

        Called by the framework on permanent removal and during hot-reload
        (before the new instance is built). Delegates to the coordinator,
        which drops every subscription and detaches from the registry
        lifecycle channel.
        """
        if self._coordinator is not None:
            self._coordinator.cleanup()
            self._coordinator = None
```

NOTE on the `--8<--` markers: the original file wraps `draw()`/`cleanup()` between `# --8<-- [start:editor_example]` (line 27) and `# --8<-- [end:editor_example]` (line 245), which a docs page snippets in. Keep both markers — place `# --8<-- [end:editor_example]` immediately after the new `cleanup()` so the docs snippet still bounds the editor-interface region. Verify the docs build in Step 6.

- [ ] **Step 3: Remove the now-unused `Callable` import if orphaned**

The `_make_panel_redraw_closure` return type used `Callable`. After deletion, check whether `Callable` is still referenced (the `lambda` in `draw()` does not need it). Run:

```bash
uv run ruff check barn/haybale-studio/haybale_studio/editors/properties_editor.py
```

If ruff reports `F401` unused-import for `Callable`, remove it from the `from typing import Any, Callable, TYPE_CHECKING` line (leaving `Any, TYPE_CHECKING`). Likewise if the `Signal` TYPE_CHECKING import is now unused, remove it. Re-run ruff until clean.

- [ ] **Step 4: Type-check the editor**

Run: `uv run mypy barn/haybale-studio/haybale_studio/editors/properties_editor.py`
Expected: clean (`Success: no issues found`). If mypy complains that `context.session` has no `subscribe`, that is fine — the coordinator's constructor is typed against `Session`, and `context.session` is a `Session`; no editor-side annotation change is needed.

- [ ] **Step 5: Smoke-run the existing editor test file (expected: some failures)**

Run: `uv run pytest tests/ui/properties_editor/test_event_bus_migration.py -q`
Expected: FAILURES — this is intentional and fixed in Task 5. The failures will reference the deleted `_subscribe_panel_event_handlers`, `_panel_bus_unsubscribes`, `_attached_panel_registry`, `_on_panel_registry_event`. Note them; do NOT fix the editor to satisfy them.

- [ ] **Step 6: Verify the docs snippet still builds**

Run: `uv run mkdocs build --strict 2>&1 | tail -20`
Expected: build succeeds. If it errors on the `editor_example` snippet section, confirm both `--8<--` markers are present and correctly ordered in `properties_editor.py`.

- [ ] **Step 7: Commit**

```bash
git add barn/haybale-studio/haybale_studio/editors/properties_editor.py
git commit -m "refactor(properties-editor): delegate panel redraw subs to PanelRedrawCoordinator

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: Rewrite the editor test file against the new seam

**Files:**
- Modify: `tests/ui/properties_editor/test_event_bus_migration.py`

Per the design split: pure subscription-mechanics tests are now covered in `test_redraw_coordinator.py` and are DELETED here; the genuinely editor-shaped tests are REWRITTEN to assert through the `_coordinator` seam / behaviour, calling the new wiring path (`editor.draw(...)` or a direct first-draw call) instead of the deleted `_subscribe_panel_event_handlers`.

The existing helper `_make_properties_editor_wrapper(session)` builds a real `EditorWrapper` and instantiates the editor without calling `draw()`. The new first-draw wiring lives in `draw()`, which needs a `container`. To wire subscriptions in a test without a full NiceGUI render, call the resolution + coordinator construction the same way `draw()` does. Add a small test helper.

- [ ] **Step 1: Add a wiring helper and update the module docstring**

In `tests/ui/properties_editor/test_event_bus_migration.py`, replace the module docstring's bullet list with one that reflects the new responsibilities (the editor resolves the registry and owns a coordinator; subscription mechanics are tested in `tests/ui/panel/test_redraw_coordinator.py`). Then add this helper after `_make_properties_editor_wrapper`:

```python
def _wire_coordinator(editor, context) -> None:
    """Drive the editor's first-draw subscription wiring without a full
    NiceGUI render.

    ``PropertiesEditor.draw()`` resolves the panel registry and, on
    success, constructs + starts a PanelRedrawCoordinator. We replicate
    exactly that gate here so tests can exercise subscription behaviour
    without building the two-column layout.
    """
    editor._context = context
    registry = editor._resolve_panel_registry(context)
    if registry is not None and editor._coordinator is None:
        from haywire.ui.panel import PanelRedrawCoordinator

        editor._coordinator = PanelRedrawCoordinator(
            registry=registry,
            session=context.session,
            on_redraw=editor.wrapper.redraw,
            focus_provider=lambda: editor._compute_toolbar_focuses(registry),
        )
        editor._coordinator.start()
```

- [ ] **Step 2: Keep the registry-helper and legacy-surface tests as-is**

These two tests do not touch deleted internals and stay unchanged:
`test_properties_editor_panel_registry_helper_returns_app_registry` and
`test_properties_editor_no_longer_carries_legacy_signal_surface`.

- [ ] **Step 3: DELETE the tests now covered as coordinator units**

Remove these four tests entirely (their behaviour is verified directly against `PanelRedrawCoordinator` in `tests/ui/panel/test_redraw_coordinator.py`):
- `test_selection_moved_triggers_wrapper_redraw_via_panel_redraw_on`
- `test_unregistered_panel_events_do_not_redraw`
- `test_editor_attaches_to_panel_registry_lifecycle_channel`
- `test_catalog_change_rebuilds_subscriptions_and_triggers_redraw`

- [ ] **Step 4: REWRITE the editor-shaped tests against behaviour / the `_coordinator` seam**

Replace `test_cleanup_drops_panel_subs_and_detaches_from_registry`, `test_hot_reload_of_properties_editor_triggers_cleanup`, and the three registry-chain-absent/raises tests with these. They assert observable behaviour (redraw fires / stops) and the `_coordinator is None` gate, not deleted privates:

```python
def test_editor_redraws_on_panel_signal_after_first_draw():
    """End-to-end through the editor seam: after wiring, publishing a
    signal a registered panel cares about redraws the wrapper."""
    panel_registry = PanelRegistry()
    panel_registry._register_class(NodeSettingsPanel, _FAKE_LIBRARY_IDENTITY)
    session = _make_session_with_panel_registry(panel_registry)

    wrapper = _make_properties_editor_wrapper(session)
    editor = wrapper.instance
    assert editor is not None

    redraws: list = []
    wrapper.set_redraw_callback(lambda w: redraws.append(w))

    _wire_coordinator(editor, session.context)
    session.publish(SelectionMoved())

    assert redraws == [wrapper]


def test_cleanup_stops_redraws_and_clears_coordinator():
    """After cleanup, a previously-subscribed signal no longer redraws,
    and the coordinator reference is cleared."""
    panel_registry = PanelRegistry()
    panel_registry._register_class(NodeSettingsPanel, _FAKE_LIBRARY_IDENTITY)
    session = _make_session_with_panel_registry(panel_registry)

    wrapper = _make_properties_editor_wrapper(session)
    editor = wrapper.instance
    assert editor is not None

    redraws: list = []
    wrapper.set_redraw_callback(lambda w: redraws.append(w))

    _wire_coordinator(editor, session.context)
    assert editor._coordinator is not None

    editor.cleanup()
    assert editor._coordinator is None

    session.publish(SelectionMoved())
    assert redraws == []
    # Coordinator detached from the registry's lifecycle channel too.
    assert editor._on_panel_registry_event not in panel_registry._batch_event_subscribers \
        if hasattr(editor, "_on_panel_registry_event") else True


def test_hot_reload_triggers_cleanup_and_stops_redraws():
    """A CLASS_RELOADED event on the wrapper calls instance.cleanup() on
    the old instance, after which its subscriptions no longer redraw."""
    panel_registry = PanelRegistry()
    panel_registry._register_class(NodeSettingsPanel, _FAKE_LIBRARY_IDENTITY)
    session = _make_session_with_panel_registry(panel_registry)

    wrapper = _make_properties_editor_wrapper(session)
    editor = wrapper.instance
    assert editor is not None

    redraws: list = []
    wrapper.set_redraw_callback(lambda w: redraws.append(w))

    _wire_coordinator(editor, session.context)
    assert editor._coordinator is not None

    class _ReloadedPropertiesEditor(PropertiesEditor):
        pass

    reload_event = LifeCycleEvent(
        event_type=LifeCycleEventType.CLASS_RELOADED,
        registry_key=PropertiesEditor.class_identity.registry_key,
        affected_class=_ReloadedPropertiesEditor,
        library_identity=_FAKE_LIBRARY_IDENTITY,
    )
    wrapper._on_lifecycle_event(reload_event)

    # Old instance was cleaned up: its subscriptions no longer fire.
    assert editor._coordinator is None
    redraws.clear()
    session.publish(SelectionMoved())
    assert redraws == []


def test_no_coordinator_when_chain_returns_none():
    """get_panel_registry() returning None → no coordinator, no crash."""
    session = _make_session_with_panel_registry(None)

    wrapper = _make_properties_editor_wrapper(session)
    editor = wrapper.instance
    assert editor is not None

    _wire_coordinator(editor, session.context)
    assert editor._coordinator is None


def test_no_coordinator_when_chain_is_missing():
    """A context whose app lacks library_service → no coordinator."""
    session = Session(
        project_state=MagicMock(),
        workspace_manager=MagicMock(),
        session_manager=MagicMock(),
    )
    session.context.app = SimpleNamespace()

    wrapper = _make_properties_editor_wrapper(session)
    editor = wrapper.instance
    assert editor is not None

    _wire_coordinator(editor, session.context)
    assert editor._coordinator is None


def test_no_coordinator_when_get_panel_registry_raises():
    """get_panel_registry() raising is treated as 'absent' — logged, no
    coordinator, no propagation."""
    library_service = SimpleNamespace(
        get_panel_registry=MagicMock(side_effect=RuntimeError("intentional bad lookup"))
    )
    session = Session(
        project_state=MagicMock(),
        workspace_manager=MagicMock(),
        session_manager=MagicMock(),
    )
    session.context.app = SimpleNamespace(library_service=library_service)

    wrapper = _make_properties_editor_wrapper(session)
    editor = wrapper.instance
    assert editor is not None

    _wire_coordinator(editor, session.context)  # must not raise
    assert editor._coordinator is None
```

NOTE: in `test_cleanup_stops_redraws_and_clears_coordinator` the final assertion guards on `hasattr` because `_on_panel_registry_event` no longer exists on the editor — the simpler, robust check is "redraws stop", which the test already makes. You may delete that trailing `assert ... if hasattr(...)` line entirely; it is kept only to show the channel-detach intent. Prefer deleting it for clarity.

- [ ] **Step 5: Run the rewritten editor test file**

Run: `uv run pytest tests/ui/properties_editor/test_event_bus_migration.py -v`
Expected: all PASS (2 unchanged + 6 rewritten = 8 tests).

- [ ] **Step 6: Commit**

```bash
git add tests/ui/properties_editor/test_event_bus_migration.py
git commit -m "test(properties-editor): assert panel redraws through coordinator seam

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: Full verification

**Files:** none (verification only)

- [ ] **Step 1: Lint + format (matches CI — both required)**

Run:
```bash
uv run ruff check .
uv run ruff format --check .
```
Expected: both clean. If `ruff format --check` reports drift, run `uv run ruff format .`, review the diff, and `git commit -m "style: ruff format"`.

- [ ] **Step 2: Type-check the full set of packages (matches CI)**

Run:
```bash
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-TEST_A/haybale_test_a/
```
Expected: `Success: no issues found`.

- [ ] **Step 3: Full test suite**

Run: `uv run pytest`
Expected: all pass, no new failures vs. the Step 0 baseline. Pay attention to anything in `tests/ui/` and any hot-reload / library-system integration tests.

- [ ] **Step 4: Final confirmation**

Confirm:
- `PropertiesEditor` no longer contains `_subscribe_panel_event_handlers`, `_rebuild_panel_event_subscriptions`, `_make_panel_redraw_closure`, `_unsubscribe_panel_event_handlers`, `_attach_panel_registry`, `_detach_panel_registry`, `_on_panel_registry_event`, `_panel_bus_unsubscribes`, or `_attached_panel_registry`.

Run: `grep -nE "_panel_bus_unsubscribes|_attached_panel_registry|_subscribe_panel_event_handlers|_rebuild_panel_event_subscriptions|_make_panel_redraw_closure|_unsubscribe_panel_event_handlers|_attach_panel_registry|_detach_panel_registry|_on_panel_registry_event" barn/haybale-studio/haybale_studio/editors/properties_editor.py`
Expected: no output (all removed).

- [ ] **Step 5: No commit needed unless Step 1 produced a format commit.** Done.

---

## Self-Review Notes (for the executor)

- **Spec coverage:** Task 1 = inert ctor + start/cleanup; Task 2 = reconciliation + resilience; Task 3 = export; Task 4 = editor rewrite + delete 7 methods/2 fields + `_coordinator is None` gate + registry-resolution-keeps-error-handling; Task 5 = test split (delete coordinator-unit tests, rewrite editor-shaped tests); Task 6 = full CI-parity verification. All six design decisions (name, location, inert ctor, both-surfaces ownership, editor gate, test split) are realised.
- **Type consistency:** the coordinator's public surface is exactly `__init__(registry, session, on_redraw, focus_provider)`, `start()`, `cleanup()`. Internal helpers `_rebuild`, `_make_redraw_handler`, `_unsubscribe_all`, `_on_registry_event` are referenced consistently across Tasks 1–2. The editor uses `_resolve_panel_registry` (new), `_compute_toolbar_focuses` (existing), `_panel_registry` (existing).
- **Known environment note:** plan is being written on branch `master` with no dedicated worktree. The executor / handoff step should create an isolated worktree before Task 1 if working-tree isolation is desired.
