---
status: planned
slice: 5 of 6
feature: studio-authentication
adr: docs/adr/0027-studio-authentication.md
previous: 2026-08-15-auth-4-gated-surfaces.md
next: none — last chained slice (2026-08-15-auth-6-clipboard-secure-context.md is independent)
---

# Slice 5 — Roster UI, account menu and presence — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the feature a face — an `account_circle` icon opening a panel-driven menu, a `RosterEditor` for managing principals, a StatusBar identity label, and TopBar presence chips for connected users and agents.

**Architecture:** The account menu reuses `BaseContextMenuProvider`, so its entries are access-filtered for free by Slice 4 and the menu refuses to open when nothing is visible. Core supplies the chrome (footer icon, StatusBar label, TopBar chips, `AccountFocus`); `haybale-studio` supplies the panels and the editor, because only a library can register components.

**Tech Stack:** NiceGUI 3.13, existing `hui` design-system elements, `Popup`, the session signal bus. No new dependencies.

## Chain position

- **Previous slice:** `2026-08-15-auth-4-gated-surfaces.md` — provides `access=` enforcement, without which `RosterEditor(access=admin)` would be visible to everyone.
- **Independent sibling:** `2026-08-15-auth-6-clipboard-secure-context.md` fixes `_copy_button`. **Land slice 6 before Task 4 here**, or the roster's token copy button will be dead on exactly the LAN deployment this feature targets.
- **Next slice:** none.

## Chain protocol

1. **Task 0** re-affirms current state and reconciles against Slice 4's Drift Log.
2. **The final task** fills in this document's Drift Log and flips `status:` to `implemented`.
3. A slice that finds the plan wrong **edits the plan** and records why.

## Global Constraints

- Line length 109; `ruff check` **and** `ruff format --check` must both pass.
- Full `mypy` command must pass.
- **UI rules are canonical in `docs/reference/design-guide.md`** — read it before writing any element. Use `--hw-*` tokens, never hardcoded colours (the login page from Slice 3 is the sole documented exception).
- **Use `hui.*` elements**, not raw `ui.*`, wherever an `hui` equivalent exists. Dialogs go through `hui.dialog_card()` — `.style()` colour does not reach Quasar pseudo-elements (`.insights/feedback_nicegui_dialog_theming.md`).
- **Click handlers must RETURN a coroutine, never schedule it** — `asyncio.ensure_future()` makes `ui.notify()` crash (`.insights/feedback_nicegui_async.md`).
- **`ui.input` emits `update:value`**, not `update:modelValue` (`.insights/project_nicegui_input_update_value_event.md`).
- The app must never depend on a barn library. `haybale-studio` may import `haywire-studio`.

---

### Task 0: Affirm current state and reconcile Slice 4 drift

- [ ] **Step 1:** confirm `grep -n "^status:" docs/superpowers/plans/2026-08-15-auth-4-gated-surfaces.md` says `implemented`.
- [ ] **Step 2:** read Slice 4's Drift Log + Delivered. If `_accessible_bindings`, `_editor_accessible` or `add_binding`'s signature differ from what this plan assumes, **edit this plan** and note it in this plan's Drift Log.
- [ ] **Step 3:** check whether Slice 6 has landed

```bash
grep -n "^status:" docs/superpowers/plans/2026-08-15-auth-6-clipboard-secure-context.md
```

If it says `planned`, either run Slice 6 first or accept that Task 4's copy button will not work over LAN HTTP — and record that choice in this plan's Drift Log.

- [ ] **Step 4:** read `docs/reference/design-guide.md` — tokens, spacing, the panel/dialog idiom.
- [ ] **Step 5:** re-read `packages/haywire-core/src/haywire/ui/app/shell.py` around the TopBar (~line 586) and StatusBar (~line 663) and confirm both are still rendered there.
- [ ] **Step 6:** `uv run ruff check . && uv run mypy` (full command) — baseline clean.

---

### Task 1: `PresenceChanged` signal and the presence source

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/session/signals/vocabulary.py`
- Create: `packages/haywire-studio/src/haywire_studio/auth/presence.py`
- Test: `tests/auth/test_presence.py`

**Interfaces:**
- Produces: `PresenceChanged` (a `cross_session = True` Signal, mirroring `ErrorLogged`); `PresenceEntry(name, kind, tier, sessions, last_seen_seconds)`; `collect_presence(session_manager, cache) -> list[PresenceEntry]`.

- [ ] **Step 1: Write the failing test**

Create `tests/auth/test_presence.py`:

```python
"""Presence — browser sessions from SessionManager, agents from the gate's last_seen."""

from unittest.mock import MagicMock

import pytest

from haywire.core.access import AccessTier
from haywire_studio.auth.live import RosterCache
from haywire_studio.auth.operations import add_agent, add_user, enable_auth
from haywire_studio.auth.presence import collect_presence

STRONG = "Correct-Horse9"


@pytest.fixture
def path(tmp_path):
    target = tmp_path / "auth.json"
    add_user("alice", STRONG, AccessTier.ADMIN, path=target)
    enable_auth("alice", STRONG, path=target)
    return target


def _manager(principals):
    sessions = {}
    for index, name in enumerate(principals):
        session = MagicMock()
        session.context.principal = name
        sessions[f"s{index}"] = session
    manager = MagicMock()
    manager.active_sessions = sessions
    return manager


def test_connected_user_appears(path):
    entries = collect_presence(_manager(["alice"]), RosterCache(path))
    assert [e.name for e in entries] == ["alice"]
    assert entries[0].kind == "user"
    assert entries[0].tier is AccessTier.ADMIN


def test_two_tabs_of_one_user_collapse_to_one_entry_with_a_count(path):
    entries = collect_presence(_manager(["alice", "alice"]), RosterCache(path))
    assert len(entries) == 1
    assert entries[0].sessions == 2


def test_disconnected_user_is_absent(path):
    assert collect_presence(_manager([]), RosterCache(path)) == []


def test_recently_seen_agent_appears(path, monkeypatch):
    import time

    add_agent("builder", AccessTier.EDIT, path=path)
    from haywire_studio.auth import gate

    gate.last_seen().clear()
    gate.last_seen()["builder"] = time.monotonic()

    entries = collect_presence(_manager([]), RosterCache(path))
    assert [e.name for e in entries] == ["builder"]
    assert entries[0].kind == "agent"


def test_long_idle_agent_drops_out(path):
    import time

    add_agent("builder", AccessTier.EDIT, path=path)
    from haywire_studio.auth import gate

    gate.last_seen().clear()
    gate.last_seen()["builder"] = time.monotonic() - 10_000

    assert collect_presence(_manager([]), RosterCache(path)) == []


def test_agent_last_seen_seconds_is_reported(path):
    import time

    add_agent("builder", AccessTier.EDIT, path=path)
    from haywire_studio.auth import gate

    gate.last_seen().clear()
    gate.last_seen()["builder"] = time.monotonic() - 42

    entry = collect_presence(_manager([]), RosterCache(path))[0]
    assert 40 <= entry.last_seen_seconds <= 60


def test_users_sort_before_agents(path):
    import time

    add_agent("builder", AccessTier.EDIT, path=path)
    from haywire_studio.auth import gate

    gate.last_seen().clear()
    gate.last_seen()["builder"] = time.monotonic()

    entries = collect_presence(_manager(["alice"]), RosterCache(path))
    assert [e.kind for e in entries] == ["user", "agent"]


def test_presence_changed_is_cross_session():
    from haywire.core.session.signals import PresenceChanged

    assert PresenceChanged.cross_session is True
```

- [ ] **Step 2: Run it**

Run: `uv run pytest tests/auth/test_presence.py -v`
Expected: FAIL — `ModuleNotFoundError: haywire_studio.auth.presence`

- [ ] **Step 3: Add the signal**

In `packages/haywire-core/src/haywire/core/session/signals/vocabulary.py`, next to `ErrorLogged`, add:

```python
class PresenceChanged(Signal):
    """Who is connected has changed — a session opened or closed.

    Cross-session like :class:`ErrorLogged`: every shell shows the same
    presence row, so a connect in one tab must refresh the others. Carries no
    payload; subscribers re-read the live presence rather than trusting a
    snapshot that may already be stale by the time it is delivered.
    """

    cross_session = True
```

Export it from `packages/haywire-core/src/haywire/core/session/signals/__init__.py` alongside `ErrorLogged`.

- [ ] **Step 4: Write the presence source**

Create `packages/haywire-studio/src/haywire_studio/auth/presence.py`:

```python
"""Who is currently connected (ADR 0027).

Two different liveness signals, deliberately not pretended to be the same:

* **Users** hold an open websocket, so ``SessionManager.active_sessions`` is
  authoritative. Multiple browser tabs collapse into one entry with a count.
* **Agents** transact over request-shaped MCP traffic with no persistent
  socket, so the gate's ``last_seen`` stamp is the only signal available.
  MCP's ``ping`` is an *optional* protocol message, so an agent that never
  pings would look offline — which is why the UI shows "last seen 40s ago"
  rather than a green dot. A relative timestamp cannot be wrong.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from haywire.core.access import AccessTier

from haywire_studio.auth.gate import last_seen
from haywire_studio.auth.live import RosterCache

#: An agent quieter than this drops out of the presence row.
AGENT_IDLE_TIMEOUT_SECONDS = 300.0


@dataclass(frozen=True)
class PresenceEntry:
    """One connected principal, ready to render."""

    name: str
    kind: str
    tier: AccessTier
    sessions: int = 0
    last_seen_seconds: float = 0.0


def collect_presence(session_manager, cache: RosterCache) -> list[PresenceEntry]:
    """Every principal currently present, users first."""
    roster = cache.roster()

    counts: dict[str, int] = {}
    for session in session_manager.active_sessions.values():
        name = getattr(session.context, "principal", None)
        if name:
            counts[name] = counts.get(name, 0) + 1

    users = [
        PresenceEntry(
            name=name,
            kind="user",
            tier=principal.tier if (principal := roster.find(name)) else AccessTier.VIEW,
            sessions=count,
        )
        for name, count in sorted(counts.items())
    ]

    now = time.monotonic()
    agents = []
    for name, stamp in sorted(last_seen().items()):
        principal = roster.find(name)
        if principal is None or not principal.is_agent:
            continue
        idle = now - stamp
        if idle > AGENT_IDLE_TIMEOUT_SECONDS:
            continue
        agents.append(
            PresenceEntry(name=name, kind="agent", tier=principal.tier, last_seen_seconds=idle)
        )

    return users + agents
```

- [ ] **Step 5: Publish the signal on session lifecycle**

In `packages/haywire-studio/src/haywire_studio/app.py`, publish after a session is created (in `main_page`, after `principal` is bound) and after one is removed (in `on_disconnect`, after `remove_session`):

```python
            from haywire.core.session.signals import PresenceChanged

            haywire_session.publish(PresenceChanged())
```

```python
        self.session_manager.remove_session(session_id)
        from haywire.core.session.signals import PresenceChanged

        self.session_manager.broadcast(PresenceChanged())
```

- [ ] **Step 6: Run it**

Run: `uv run pytest tests/auth/test_presence.py -v`
Expected: PASS, 8 tests.

- [ ] **Step 7: Commit**

```bash
git add packages/haywire-core/src/haywire/core/session/signals/ packages/haywire-studio/src/haywire_studio/auth/presence.py packages/haywire-studio/src/haywire_studio/app.py tests/auth/test_presence.py
git commit -m "feat(auth): PresenceChanged signal and presence collection"
```

---

### Task 2: `AccountFocus` and the account menu provider

**Files:**
- Modify: `packages/haywire-core/src/haywire/barn/builtin/focuses.py`
- Create: `packages/haywire-core/src/haywire/ui/app/account_menu.py`
- Test: `tests/ui/test_account_menu.py`

**Interfaces:**
- Produces: `AccountFocus` (id `"account"`); `AccountActions` Protocol with `logout()` and `reveal(editor_cls, binding_id, label)`; `AccountMenuProvider(BaseContextMenuProvider)` with `open(pos: tuple[float, float]) -> None`.

- [ ] **Step 1: Write the failing test**

Create `tests/ui/test_account_menu.py`:

```python
"""The account menu — a panel-driven context menu, so access filtering is free."""

from unittest.mock import MagicMock

from haywire.barn.builtin.focuses import AccountFocus
from haywire.ui.app.account_menu import AccountMenuProvider


def test_account_focus_id_is_stable():
    assert AccountFocus.id == "account"


def test_account_focus_is_always_available():
    assert AccountFocus.available(MagicMock()) is True


def test_open_queries_panels_for_the_account_focus(monkeypatch):
    provider = AccountMenuProvider(
        context=MagicMock(), session=MagicMock(), panel_registry=MagicMock()
    )
    seen = {}

    def _open_menu(action, focus, pos, on_close=None):
        seen["action"] = action
        seen["focus"] = focus
        seen["pos"] = pos

    monkeypatch.setattr(provider, "_open_menu", _open_menu)
    provider.open((10.0, 20.0))

    assert seen["focus"] is AccountFocus
    assert seen["pos"] == (10.0, 20.0)


def test_logout_navigates_the_client_to_the_logout_route():
    provider = AccountMenuProvider(
        context=MagicMock(), session=MagicMock(), panel_registry=MagicMock()
    )
    provider._open_popup = MagicMock()
    ran = []
    provider._run_js = lambda script: ran.append(script)

    provider.logout()

    assert "/logout" in ran[0]
    provider._open_popup.close.assert_called_once()


def test_reveal_publishes_a_reveal_signal_and_closes():
    session = MagicMock()
    provider = AccountMenuProvider(context=MagicMock(), session=session, panel_registry=MagicMock())
    provider._open_popup = MagicMock()

    marker = type("E", (), {})
    provider.reveal(marker, None, "Roster")

    assert session.publish.called
    provider._open_popup.close.assert_called_once()
```

- [ ] **Step 2: Run it**

Run: `uv run pytest tests/ui/test_account_menu.py -v`
Expected: FAIL — `ImportError: cannot import name 'AccountFocus'`

- [ ] **Step 3: Add `AccountFocus`**

Append to `packages/haywire-core/src/haywire/barn/builtin/focuses.py`:

```python
class AccountFocus(Focus):
    """The account menu behind the ``account_circle`` icon in the ACTION bar footer.

    Always available — the menu itself is access-filtered by
    ``visible_panels()``, and ``_open_menu`` refuses to open when nothing is
    visible. So a principal with no entries simply gets no menu, with no
    special case here.
    """

    id = "account"
    label = "Account"
    icon = "account_circle"
    order = 10

    @classmethod
    def available(cls, ctx) -> bool:
        return True
```

- [ ] **Step 4: Write the provider**

Create `packages/haywire-core/src/haywire/ui/app/account_menu.py`:

```python
"""The account menu provider (ADR 0027).

Reuses ``BaseContextMenuProvider`` rather than hand-rolling a popup, which buys
three things for free: entries are access-filtered by ``visible_panels()``, the
menu refuses to open when nothing is visible, and libraries can contribute their
own account entries by registering a panel against :class:`AccountFocus`.
"""

from __future__ import annotations

from typing import Any, Protocol, Tuple, runtime_checkable

from haywire.barn.builtin.focuses import AccountFocus
from haywire.ui.panel.context_menu_base import BaseContextMenuProvider


@runtime_checkable
class AccountActions(Protocol):
    """What an account-menu panel may ask the host to do."""

    def logout(self) -> None: ...

    def reveal(self, editor_cls: type, binding_id: Any, label: str) -> None: ...


class AccountMenuProvider(BaseContextMenuProvider):
    """Opens the account menu and satisfies :class:`AccountActions`."""

    def open(self, pos: Tuple[float, float]) -> None:
        """Show the menu at ``pos``, or nothing if this principal has no entries."""
        self._open_menu(AccountActions, AccountFocus, pos)

    # -- AccountActions -------------------------------------------------

    def logout(self) -> None:
        """POST to ``/logout`` so the server clears the cookie, then reload.

        A form POST rather than a link because the cookie is ``HttpOnly`` —
        the browser cannot clear it from JavaScript, only the server can.
        """
        self._run_js(
            "fetch('/logout', {method: 'POST'})"
            ".then(() => window.location.href = '/login')"
        )
        if self._open_popup is not None:
            self._open_popup.close()

    def reveal(self, editor_cls: type, binding_id: Any, label: str) -> None:
        from haywire.core.session.signals import Reveal

        self._session.publish(Reveal(editor=editor_cls, binding_id=binding_id, label=label))
        if self._open_popup is not None:
            self._open_popup.close()

    @staticmethod
    def _run_js(script: str) -> None:
        """Seam for tests — production goes straight to NiceGUI."""
        from nicegui import ui

        ui.run_javascript(script)
```

- [ ] **Step 5: Run it**

Run: `uv run pytest tests/ui/test_account_menu.py -v`
Expected: PASS, 5 tests.

- [ ] **Step 6: Commit**

```bash
git add packages/haywire-core/src/haywire/barn/builtin/focuses.py packages/haywire-core/src/haywire/ui/app/account_menu.py tests/ui/test_account_menu.py
git commit -m "feat(auth): AccountFocus and the panel-driven account menu provider"
```

---

### Task 3: Shell chrome — footer icon, StatusBar identity, TopBar presence

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/app/icon_slot.py`
- Modify: `packages/haywire-core/src/haywire/ui/app/shell.py`
- Test: `tests/ui/test_shell_account_chrome.py`

**Interfaces:**
- Produces: `IconSlot.set_footer(renderer: Callable[[], None] | None) -> None`; `AppShell._render_account_icon()`, `AppShell._render_identity_label()`, `AppShell._render_presence()`.

**Design note:** the footer is a general region that can hold more than one icon later (VS Code has user *and* settings), but only the account icon ships now.

- [ ] **Step 1: Write the failing test**

Create `tests/ui/test_shell_account_chrome.py`:

```python
"""Account chrome — the footer region, the identity label, the presence row."""

from unittest.mock import MagicMock

import pytest

from haywire.core.access import AccessTier


def test_icon_slot_has_a_footer_hook():
    from haywire.ui.app.icon_slot import IconSlot

    assert hasattr(IconSlot, "set_footer")


def test_footer_renderer_is_invoked_during_bar_render(monkeypatch):
    from haywire.ui.app.icon_slot import IconSlot

    session = MagicMock()
    session.context.can_access.return_value = True
    slot = IconSlot(session=session, name="action", registry=MagicMock())

    called = []
    slot.set_footer(lambda: called.append(True))
    slot._bindings = []
    slot._render_bar_contents()

    assert called == [True]


def test_identity_text_names_the_principal_and_tier():
    from haywire.ui.app.shell import identity_text

    assert identity_text("alice", AccessTier.ADMIN) == "alice · admin"


def test_identity_text_is_empty_when_auth_is_off():
    from haywire.ui.app.shell import identity_text

    assert identity_text(None, AccessTier.ADMIN) == ""


@pytest.mark.parametrize(
    "seconds,expected",
    [(5, "just now"), (65, "1m ago"), (3700, "1h ago")],
)
def test_last_seen_text(seconds, expected):
    from haywire.ui.app.shell import last_seen_text

    assert last_seen_text(seconds) == expected
```

- [ ] **Step 2: Run it**

Run: `uv run pytest tests/ui/test_shell_account_chrome.py -v`
Expected: FAIL.

- [ ] **Step 3: Add the footer region to `IconSlot`**

In `packages/haywire-core/src/haywire/ui/app/icon_slot.py`, add to `__init__` (or as a class attribute set lazily):

```python
        self._footer_renderer: Optional[Callable[[], None]] = None
```

Add the method:

```python
    def set_footer(self, renderer: Optional[Callable[[], None]]) -> None:
        """Install a renderer for the bar's footer region.

        Framework chrome that is not an editor tab — today just the account
        icon, deliberately shaped as a region rather than a single hook so a
        second icon (settings, in the VS Code idiom) does not need a new seam.
        Only the ACTION slot sets one.
        """
        self._footer_renderer = renderer
```

In `_render_bar_contents`, remove the early `return` when there are no bindings so the footer still renders, and call the footer at the end. Restructure the head of the method:

```python
        renderable = self._accessible_bindings()
        if renderable:
            ...  # existing tabs rendering, unchanged
        if self._footer_renderer is not None:
            ui.space()
            self._footer_renderer()
```

(Read the method as it stands after Slice 4 and make the minimal change: the existing `if not renderable: return` becomes a guard around the tabs block only.)

- [ ] **Step 4: Add the helpers and chrome to `AppShell`**

Add at module level in `packages/haywire-core/src/haywire/ui/app/shell.py`:

```python
def identity_text(principal: str | None, tier: "AccessTier") -> str:
    """StatusBar label — ``alice · admin``, or empty when authentication is off.

    This label is what makes the vanish-on-denial behaviour humane rather than
    mysterious: a principal who cannot see an editor has one place that explains
    why, instead of a padlock on every control (ADR 0027).
    """
    return f"{principal} · {tier.value}" if principal else ""


def last_seen_text(seconds: float) -> str:
    """Relative recency for an agent chip.

    Deliberately relative rather than a green dot: MCP's ``ping`` is optional,
    so a binary indicator can be wrong while "last seen 40s ago" cannot.
    """
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{int(seconds // 60)}m ago"
    return f"{int(seconds // 3600)}h ago"
```

Add the account icon render, called from wherever the ACTION slot is constructed:

```python
    def _render_account_icon(self) -> None:
        """The ``account_circle`` button in the ACTION bar footer."""
        from haywire.ui.app.account_menu import AccountMenuProvider

        provider = AccountMenuProvider(
            context=self._session.context,
            session=self._session,
            panel_registry=self._panel_registry,
        )
        self._account_menu = provider

        button = (
            ui.button(icon="account_circle")
            .props("flat round dense")
            .classes("hw-account-icon")
            .tooltip("Account")
        )
        button.on(
            "click",
            lambda event: provider.open(
                (event.args.get("clientX", 0), event.args.get("clientY", 0))
                if isinstance(event.args, dict)
                else (0, 0)
            ),
        )
```

and wire it after the ACTION slot exists:

```python
        self._slots[SlotName.ACTION].set_footer(self._render_account_icon)
```

Add the StatusBar label inside the existing StatusBar block:

```python
            from haywire.core.access import resolve_tier

            principal = self._session.context.principal
            label = identity_text(principal, resolve_tier(principal))
            if label:
                ui.label(label).classes("hw-text-muted text-xs px-2")
```

Add the presence row inside the existing TopBar block, subscribed to `PresenceChanged`:

```python
    def _render_presence(self) -> None:
        """Chips for every connected principal — users first, then agents.

        Visible to everyone, not admin-only: in a crew setting, knowing who else
        is connected is useful to all, and it discloses nothing beyond "these
        roster entries are online" to people already inside the trust boundary.
        """
        from haywire_studio.auth.live import RosterCache
        from haywire_studio.auth.presence import collect_presence

        # DI accessor, not self._session._session_manager — reaching into a
        # private attribute of Session would couple the shell to its internals.
        from haywire.core.di.context import get_session_manager

        self._presence_row.clear()
        with self._presence_row:
            for entry in collect_presence(get_session_manager(), RosterCache()):
                icon = "smart_toy" if entry.kind == "agent" else "person"
                detail = (
                    last_seen_text(entry.last_seen_seconds)
                    if entry.kind == "agent"
                    else (f"{entry.sessions} tabs" if entry.sessions > 1 else "connected")
                )
                with ui.row().classes("items-center gap-1 px-2 hw-presence-chip"):
                    ui.icon(icon).classes("text-xs")
                    ui.label(entry.name).classes("text-xs")
                ui.tooltip(f"{entry.tier.value} · {detail}")
```

**Import direction check:** `shell.py` is in `haywire-core` and this reaches into `haywire_studio`. That is backwards. **Do not import it at module level.** Import inside the method (as written above) and wrap in `try/except ImportError` so a headless/embedded `haywire-core` consumer with no studio installed still renders a shell:

```python
        try:
            from haywire_studio.auth.live import RosterCache
            from haywire_studio.auth.presence import collect_presence
        except ImportError:
            return
```

Record in the Drift Log if you find a cleaner seam — the honest alternative is a small provider callback the studio installs on the shell, which would be better and is worth doing if it costs less than an hour.

- [ ] **Step 5: Subscribe the presence row**

Where `AppShell` subscribes its other handlers, add:

```python
        self._unsubscribes.append(
            self._session.subscribe(PresenceChanged, lambda _s: self._render_presence())
        )
```

Follow the existing subscription/teardown idiom in `shell.py` exactly — read how `Reveal`/`Close` are wired and match it.

- [ ] **Step 6: Run the tests**

Run: `uv run pytest tests/ui/test_shell_account_chrome.py tests/ui/test_app_shell.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add packages/haywire-core/src/haywire/ui/app/ tests/ui/test_shell_account_chrome.py
git commit -m "feat(auth): account icon footer, identity label and presence chips"
```

---

### Task 4: The `RosterEditor` and account panels

**Files:**
- Create: `barn/haybale-studio/haybale_studio/editors/roster_editor.py`
- Create: `barn/haybale-studio/haybale_studio/panels/account/__init__.py`
- Create: `barn/haybale-studio/haybale_studio/panels/account/account.py`
- Modify: `barn/haybale-studio/haybale_studio/__init__.py`
- Test: `tests/studio/test_roster_editor.py`

**Interfaces:**
- Produces: `RosterEditor` (`@editor(access=AccessTier.ADMIN, opens='on_context', default_slot='edit')`); `LogoutPanel` (`access=VIEW`); `OpenRosterPanel` (`access=ADMIN`); `RotateSecretPanel` (`access=ADMIN`).

- [ ] **Step 1: Write the failing test**

Create `tests/studio/test_roster_editor.py`:

```python
"""RosterEditor and the account menu panels."""

import pytest

from haywire.core.access import AccessTier


def test_roster_editor_requires_admin():
    from haybale_studio.editors.roster_editor import RosterEditor

    assert RosterEditor.class_identity.access is AccessTier.ADMIN


def test_logout_panel_is_visible_to_everyone():
    from haybale_studio.panels.account.account import LogoutPanel

    assert LogoutPanel.class_identity.access is AccessTier.VIEW


def test_open_roster_panel_requires_admin():
    from haybale_studio.panels.account.account import OpenRosterPanel

    assert OpenRosterPanel.class_identity.access is AccessTier.ADMIN


def test_rotate_secret_panel_requires_admin():
    from haybale_studio.panels.account.account import RotateSecretPanel

    assert RotateSecretPanel.class_identity.access is AccessTier.ADMIN


def test_account_panels_target_the_account_focus():
    from haywire.barn.builtin.focuses import AccountFocus
    from haybale_studio.panels.account.account import LogoutPanel, OpenRosterPanel

    assert LogoutPanel.class_identity.focus is AccountFocus
    assert OpenRosterPanel.class_identity.focus is AccountFocus


def test_logout_panel_hidden_when_authentication_is_off():
    """With no principal there is nothing to log out of — the menu stays empty."""
    from unittest.mock import MagicMock

    from haybale_studio.panels.account.account import LogoutPanel

    ctx = MagicMock()
    ctx.principal = None
    assert LogoutPanel.poll(ctx) is False

    ctx.principal = "alice"
    assert LogoutPanel.poll(ctx) is True
```

- [ ] **Step 2: Run it**

Run: `uv run pytest tests/studio/test_roster_editor.py -v`
Expected: FAIL.

- [ ] **Step 3: Write the account panels**

Create `barn/haybale-studio/haybale_studio/panels/account/__init__.py` (empty) and `account.py`:

```python
"""Account-menu panels — behind the account_circle icon in the ACTION bar footer.

These are ordinary panels against ``AccountFocus``, so ``visible_panels()``
filters them by ``access=`` with no special case, and the menu does not open at
all when a principal has nothing in it.
"""

from __future__ import annotations

from haywire.barn.builtin.focuses import AccountFocus
from haywire.core.access import AccessTier
from haywire.ui import elements as hui
from haywire.ui.app.account_menu import AccountActions
from haywire.ui.panel.base import BasePanel
from haywire.ui.panel.decorator import panel


@panel(
    actions=AccountActions,
    focus=AccountFocus,
    label="Sign out",
    order=90,
    access=AccessTier.VIEW,
)
class LogoutPanel(BasePanel):
    """Ends this browser session. Hidden entirely when authentication is off."""

    actions: AccountActions

    @classmethod
    def poll(cls, ctx) -> bool:
        return ctx.principal is not None

    def draw(self, ctx, layout) -> None:
        with layout:
            hui.button("Sign out", icon=hui.icon.logout, on_click=self.actions.logout)


@panel(
    actions=AccountActions,
    focus=AccountFocus,
    label="Manage principals",
    order=10,
    access=AccessTier.ADMIN,
)
class OpenRosterPanel(BasePanel):
    """Opens the RosterEditor. Admin-only, so a view principal never sees it."""

    actions: AccountActions

    @classmethod
    def poll(cls, ctx) -> bool:
        return True

    def draw(self, ctx, layout) -> None:
        from haybale_studio.editors.roster_editor import RosterEditor

        with layout:
            hui.button(
                "Manage principals",
                icon="manage_accounts",
                on_click=lambda: self.actions.reveal(RosterEditor, None, "Principals"),
            )


@panel(
    actions=AccountActions,
    focus=AccountFocus,
    label="Sign everyone out",
    order=80,
    access=AccessTier.ADMIN,
)
class RotateSecretPanel(BasePanel):
    """Rotates the cookie signing secret and evicts every live session.

    The panic lever: one action that invalidates every issued cookie at once,
    for when a laptop goes missing rather than when one principal leaves.
    """

    actions: AccountActions

    @classmethod
    def poll(cls, ctx) -> bool:
        return ctx.principal is not None

    def draw(self, ctx, layout) -> None:
        with layout:
            hui.button("Sign everyone out", icon=hui.icon.logout, on_click=self._rotate)

    def _rotate(self) -> None:
        from haywire_studio.auth.cookies import rotate_secret
        from haywire_studio.auth.eviction import evict_all

        rotate_secret()
        evict_all(self._session_manager())
        self.actions.logout()

    @staticmethod
    def _session_manager():
        from haywire.core.di.context import get_session_manager

        return get_session_manager()
```

**Verified API notes** (checked while writing this plan — re-confirm if Slices 1–4 drifted):

- `hui.button(label, icon=..., on_click=...)` inside `with layout:` is the menu-item idiom. There is **no** `hui.menu_item`. Model these on `barn/haybale-studio/haybale_studio/panels/file_browser/menu/file.py`, which is the closest existing example.
- `hui.icon` is an icon-name namespace (`hui.icon.edit`). Confirm `hui.icon.logout` exists; if not, pass the raw Material name `"logout"`, which `hui.button` also accepts.
- `get_session_manager()` is published at `haywire/core/di/context.py:126`.
- `BasePanel.draw(self, ctx, layout)` — three parameters.

- [ ] **Step 4: Write the `RosterEditor`**

Create `barn/haybale-studio/haybale_studio/editors/roster_editor.py`:

```python
"""RosterEditor — add, remove, re-tier and re-key principals.

Admin-only, and reached through the account menu rather than a bar tab: it is a
standing list you open deliberately, not something tied to the current
selection. All mutations go through ``haywire_studio.auth.operations`` so the
UI and the CLI enforce exactly one set of rules.
"""

from __future__ import annotations

from haywire.core.access import AccessTier
from haywire.ui import elements as hui
from haywire.ui.editor.base import BaseEditor
from haywire.ui.editor.decorator import editor
from haywire_studio.auth.operations import (
    add_agent,
    add_user,
    remove_principal,
    set_password,
    set_tier,
)
from haywire_studio.auth.roster import RosterError, load_roster
from nicegui import ui


@editor(
    label="Principals",
    icon="manage_accounts",
    default_slot="edit",
    opens="on_context",
    description="Manage who may reach this studio",
    access=AccessTier.ADMIN,
)
class RosterEditor(BaseEditor):
    """The roster table plus add/remove/re-tier controls."""

    def draw(self, context, container) -> None:
        container.clear()
        with container:
            with ui.column().classes("w-full gap-4 p-4"):
                self._draw_roster()
                self._draw_add_form()

    # -- table ----------------------------------------------------------

    def _draw_roster(self) -> None:
        try:
            roster = load_roster()
        except RosterError as exc:
            hui.error_label(f"Roster unreadable: {exc}")
            return

        state = "enabled" if roster.enabled else "disabled"
        hui.section_label(f"Authentication is {state}")
        if not roster.enabled:
            ui.label(
                "Run 'haywire auth enable' with the studio stopped to require a login."
            ).classes("hw-text-muted text-xs")

        for principal in roster.principals:
            self._draw_row(principal)

    def _draw_row(self, principal) -> None:
        with ui.row().classes("w-full items-center gap-2 hw-panel p-2"):
            ui.icon("smart_toy" if principal.is_agent else "person")
            ui.label(principal.name).classes("font-medium")

            tier_select = ui.select(
                [tier.value for tier in AccessTier], value=principal.tier.value
            ).props("dense outlined")
            tier_select.on(
                "update:modelValue",
                lambda event, name=principal.name: self._set_tier(name, event.args),
            )

            if principal.is_agent:
                hui.code_snippet(principal.token)
            else:
                ui.button(icon="key", on_click=lambda name=principal.name: self._ask_password(name)).props(
                    "flat dense round"
                ).tooltip("Set password")

            ui.button(
                icon="delete", on_click=lambda name=principal.name: self._remove(name)
            ).props("flat dense round").tooltip("Remove")

    # -- mutations ------------------------------------------------------

    def _set_tier(self, name: str, value) -> None:
        try:
            set_tier(name, AccessTier(value))
        except (RosterError, ValueError) as exc:
            ui.notify(str(exc), type="negative")
            return
        ui.notify(f"{name} is now {value}")
        self.wrapper.redraw()

    def _remove(self, name: str) -> None:
        """Remove a principal and evict their live sessions immediately.

        Eviction is the half that makes this a revocation rather than a request:
        the gate cannot revoke an already-open websocket, so removal pushes.
        """
        from haywire.core.di.context import get_session_manager

        from haywire_studio.auth.eviction import evict_principal

        try:
            remove_principal(name)
        except RosterError as exc:
            ui.notify(str(exc), type="negative")
            return

        evicted = evict_principal(get_session_manager(), name)
        ui.notify(f"Removed {name} ({evicted} session(s) ended)")
        self.wrapper.redraw()

    def _ask_password(self, name: str) -> None:
        with hui.dialog_card() as dialog:
            field = ui.input("New password", password=True).classes("w-full")
            hui.dialog_actions(
                on_confirm=lambda: self._set_password(dialog, name, field.value),
                on_cancel=dialog.close,
            )
        dialog.open()

    def _set_password(self, dialog, name: str, value: str) -> None:
        try:
            set_password(name, value or "")
        except RosterError as exc:
            ui.notify(str(exc), type="negative")
            return
        dialog.close()
        ui.notify(f"Password updated for {name}")

    # -- add form -------------------------------------------------------

    def _draw_add_form(self) -> None:
        hui.section_label("Add a principal")
        with ui.row().classes("w-full items-end gap-2"):
            name = ui.input("Name").props("dense outlined")
            tier = ui.select([t.value for t in AccessTier], value=AccessTier.VIEW.value).props(
                "dense outlined"
            )
            kind = ui.select(["user", "agent"], value="user").props("dense outlined")
            password = ui.input("Password", password=True).props("dense outlined")
            ui.button(
                "Add",
                on_click=lambda: self._add(name.value, kind.value, tier.value, password.value),
            ).props("flat dense")

    def _add(self, name: str, kind: str, tier: str, password: str) -> None:
        try:
            if kind == "agent":
                agent = add_agent(name, AccessTier(tier))
                ui.notify(f"Created agent {agent.name} — copy its token from the list")
            else:
                add_user(name, password or "", AccessTier(tier))
                ui.notify(f"Created user {name}")
        except (RosterError, ValueError) as exc:
            ui.notify(str(exc), type="negative")
            return
        self.wrapper.redraw()
```

**Verified API notes** (checked while writing this plan):

- `hui.section_label`, `hui.error_label`, `hui.dialog_card` exist as used.
- The code block helper is **`hui.code_snippet`**, not `code_block`.
- The dialog button row is **`hui.dialog_actions(on_confirm=..., on_cancel=...)`**, not `confirm_row`.
- `BaseEditor` has **no** `redraw()`. It holds `self.wrapper` (`ui/editor/base.py:44`), and `EditorWrapper.redraw()` (`ui/editor/wrapper.py:210`) is the public path — hence `self.wrapper.redraw()` above.
- `BaseEditor.draw(self, context, container)` takes **three** parameters (`ui/editor/base.py:73`).

If any of these moved during Slices 1–4, substitute and record it in the Drift Log.

- [ ] **Step 5: Register both folders**

In `barn/haybale-studio/haybale_studio/__init__.py`, add the `panels/account` folder to the `PanelRegistry` scan and confirm `editors/` already picks up `roster_editor.py`. Follow the existing ordering comment — state before editors.

- [ ] **Step 6: Run the tests**

Run: `uv run pytest tests/studio/test_roster_editor.py -v`
Expected: PASS, 6 tests.

- [ ] **Step 7: Commit**

```bash
git add barn/haybale-studio/ tests/studio/test_roster_editor.py
git commit -m "feat(auth): RosterEditor and account-menu panels"
```

---

### Task 5: Manual verification in the running studio

- [ ] **Step 1: Set up two principals**

```bash
uv run haywire user add admin1 --tier admin
uv run haywire user add viewer1 --tier view
uv run haywire user add builder --agent --tier view
uv run haywire auth enable          # admin1 + password
uv run haywire --no-browser
```

- [ ] **Step 2: As `admin1`** — sign in and confirm: the `account_circle` icon appears at the bottom of the ACTION bar; clicking it shows *Manage principals*, *Sign everyone out*, *Sign out*; *Manage principals* opens the RosterEditor; the StatusBar reads `admin1 · admin`; the TopBar shows one chip.

- [ ] **Step 3: As `viewer1`** — in a private window, sign in and confirm: the account icon shows **only** *Sign out*; the RosterEditor is absent from every bar; the StatusBar reads `viewer1 · view`; both chips appear in the TopBar for both sessions.

- [ ] **Step 4: Live demotion** — as `admin1`, change `viewer1` to `edit`. Confirm `viewer1`'s next interaction reflects it without a re-login.

- [ ] **Step 5: Live revocation** — as `admin1`, remove `viewer1`. Confirm that window is thrown back to `/login` immediately, and the chip disappears from `admin1`'s TopBar.

- [ ] **Step 6: Agent presence** — connect an MCP client with the `builder` token and confirm a `smart_toy` chip appears with a *last seen* tooltip, and that the served tool list contains only `view`-tier tools.

- [ ] **Step 7: Restore**

```bash
uv run haywire auth disable
```

- [ ] **Step 8: Record every deviation in the Drift Log.**

---

### Task 6: Quality gate

- [ ] **Step 1:** `uv run ruff check . && uv run ruff format --check .`
- [ ] **Step 2:** full mypy command.
- [ ] **Step 3:**

```bash
uv run pytest -m "not browser and not perf" -q > /tmp/slice5.log 2>&1; echo "exit=$?"
grep -E "^FAILED|^ERROR" /tmp/slice5.log
```

- [ ] **Step 4:** full suite including browser tests — shell chrome changed:

```bash
uv run pytest -q > /tmp/slice5-all.log 2>&1; echo "exit=$?"
```

- [ ] **Step 5:** regenerate library docs, since `haybale-studio` gained components:

```bash
uv run haywire docs --all
```

- [ ] **Step 6:** commit fixes and regenerated docs.

---

### Task 7 (final): Record delivery and drift

- [ ] **Step 1: Fill in the Drift Log** — one line per deviation, or "No drift." explicitly. Call out specifically: which `hui` helper names were substituted, whether the `shell.py` → `haywire_studio` import direction was resolved with a provider callback or left as a guarded local import, and whether `IconSlot._render_bar_contents` needed more restructuring than the plan sketched.
- [ ] **Step 2: Update the ADR if the built shape differs from what it describes.** ADR 0027 is the durable record; this plan is scaffolding. If the account menu, presence, or roster UI ended up materially different, edit `docs/adr/0027-studio-authentication.md` to describe what exists.
- [ ] **Step 3: Update `docs/guides/network_config.md`** — it currently says authentication is "designed in ADR-0027". With this slice landed, the whole feature is built: rewrite that paragraph to point at how to enable it, and add a short section or a sibling guide covering `haywire user` / `haywire auth`.
- [ ] **Step 4: Flip `status:` to `implemented`.**
- [ ] **Step 5: Commit**

```bash
git add docs/
git commit -m "docs(plan): slice 5 complete — roster UI, account menu, presence"
```

---

## Delivered

*(Filled in by the final task.)*

## Drift Log

*(Filled in by the final task. One line per deviation, or the words "No drift.")*
