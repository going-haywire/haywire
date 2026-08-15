---
status: implemented
slice: 1 of 6
feature: studio-authentication
adr: docs/adr/0027-studio-authentication.md
previous: none — this is the first slice
next: 2026-08-15-auth-2-roster-cli.md
---

# Slice 1 — Core access vocabulary — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give `haywire-core` the vocabulary to express access tiers — `AccessTier`, a principal name on `SessionContext`, and `can_view()/can_edit()/can_admin()/can_access()` — with a resolver hook the studio fills in later, defaulting to full access so nothing changes for existing installs.

**Architecture:** A new `haywire.core.access` package holding an enum, a module-level resolver hook, and nothing else — no files, no crypto, no ASGI. `SessionContext` gains one plain field and four methods. Core must own this vocabulary because `@panel(access=…)` and `@editor(access=…)` are core decorators (Slice 4); a studio-owned enum would make core import studio, which is a cycle.

**Tech Stack:** Python 3.12, `enum.StrEnum`, pytest. No new dependencies.

## Chain position

- **Previous slice:** none.
- **Next slice:** `2026-08-15-auth-2-roster-cli.md` consumes `AccessTier` and `set_access_resolver`.
- **This slice is behaviour-neutral.** With no resolver installed, every principal resolves to `ADMIN`. Nothing in the running studio changes.

## Chain protocol (applies to every slice in this feature)

1. **Task 0 of every slice** re-affirms the current state of the codebase and reconciles the plan against the previous slice's **Drift Log**. Do not start implementing until Task 0 is complete and any plan corrections are written into this document.
2. **The final task of every slice** fills in this document's **Drift Log** and flips the front-matter `status:` to `implemented`.
3. A slice that discovers the plan is wrong **edits the plan** and records why in the Drift Log. Silent deviation is the failure mode this protocol exists to prevent.

## Global Constraints

- Line length 109 (`ruff`); both `uv run ruff check .` and `uv run ruff format --check .` must pass — CI runs both.
- `uv run mypy` must pass for every path in the CLAUDE.md mypy command.
- **No new runtime dependencies anywhere in this feature.** Stdlib only (ADR 0027).
- `haywire-core` must not import from `haywire_studio` or any `haybale-*` library.
- Tiers are cumulative: `admin ⊃ edit ⊃ view`.
- Default when authentication is not configured is **`ADMIN` for everybody** — existing loopback installs must be unaffected.

---

### Task 0: Affirm current state

**Files:**
- Read: `docs/adr/0027-studio-authentication.md`
- Read: `packages/haywire-core/src/haywire/core/session/context.py`

- [x] **Step 1: Confirm the baseline is clean**

```bash
uv run ruff check packages/haywire-core/src/haywire/core/
uv run mypy packages/haywire-core/src/
```

Expected: no errors. If there are pre-existing errors, stop and raise with the user — CLAUDE.md requires an interactive fix session, not a silent workaround.

- [x] **Step 2: Confirm `haywire.core.access` does not already exist**

```bash
ls packages/haywire-core/src/haywire/core/access 2>&1
```

Expected: `No such file or directory`. If it exists, this slice has already been partly run — read it and reconcile before continuing.

- [x] **Step 3: Confirm `SessionContext` still has the shape this plan assumes**

Read `packages/haywire-core/src/haywire/core/session/context.py`. It must have a "Plain fields (non-reactive)" annotation block (`session_id`, `app`, `session`, `app_data`, `data`) and an `__init__` ending with `_seed_signal_fields(self)`. If the shape differs, correct Task 3 of this plan before implementing it.

- [x] **Step 4: Previous-slice drift**

None — this is the first slice. Proceed.

---

### Task 1: `AccessTier` enum and the identity lookup

**Files:**
- Create: `packages/haywire-core/src/haywire/core/access/__init__.py`
- Create: `packages/haywire-core/src/haywire/core/access/tier.py`
- Test: `tests/core/test_access/__init__.py`, `tests/core/test_access/test_tier.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `AccessTier` (StrEnum with members `VIEW="view"`, `EDIT="edit"`, `ADMIN="admin"`), `AccessTier.rank -> int`, `AccessTier.satisfies(required: AccessTier) -> bool`, `required_access(cls: type) -> AccessTier`.

**Why `required_access` lives here and not at each call site:** Slice 4 gates three
different surfaces — panels, editors and Farmhand tools — and all three answer the same
question ("what tier does this class demand?") the same way. Written three times it is
three chances to get the missing-identity fallback wrong, in three files that are never
read together. Defined once here, the *rule* is single even though Slice 4's enforcement
*points* deliberately differ.

- [x] **Step 1: Write the failing test**

Create `tests/core/test_access/__init__.py` as an empty file, then `tests/core/test_access/test_tier.py`:

```python
"""AccessTier — cumulative three-tier access vocabulary (ADR 0027)."""

import pytest

from haywire.core.access import AccessTier


def test_values_are_the_wire_strings():
    assert AccessTier.VIEW == "view"
    assert AccessTier.EDIT == "edit"
    assert AccessTier.ADMIN == "admin"


def test_constructed_from_string():
    assert AccessTier("edit") is AccessTier.EDIT


def test_unknown_string_raises():
    with pytest.raises(ValueError):
        AccessTier("superuser")


def test_ranks_are_ordered():
    assert AccessTier.VIEW.rank < AccessTier.EDIT.rank < AccessTier.ADMIN.rank


@pytest.mark.parametrize(
    "held,required,expected",
    [
        (AccessTier.ADMIN, AccessTier.VIEW, True),
        (AccessTier.ADMIN, AccessTier.EDIT, True),
        (AccessTier.ADMIN, AccessTier.ADMIN, True),
        (AccessTier.EDIT, AccessTier.VIEW, True),
        (AccessTier.EDIT, AccessTier.EDIT, True),
        (AccessTier.EDIT, AccessTier.ADMIN, False),
        (AccessTier.VIEW, AccessTier.VIEW, True),
        (AccessTier.VIEW, AccessTier.EDIT, False),
        (AccessTier.VIEW, AccessTier.ADMIN, False),
    ],
)
def test_satisfies_is_cumulative(held, required, expected):
    assert held.satisfies(required) is expected


# --- required_access ---------------------------------------------------


def test_required_access_reads_the_class_identity():
    from haywire.core.access import required_access

    identity = type("Identity", (), {"access": AccessTier.ADMIN})()
    cls = type("Thing", (), {"class_identity": identity})
    assert required_access(cls) is AccessTier.ADMIN


def test_required_access_defaults_to_view_without_a_class_identity():
    """Mid-hot-reload classes and test doubles must not become invisible."""
    from haywire.core.access import required_access

    assert required_access(type("Bare", (), {})) is AccessTier.VIEW


def test_required_access_defaults_to_view_when_identity_lacks_the_field():
    """Node/skin/widget identities have no access field — they are never gated."""
    from haywire.core.access import required_access

    identity = type("Identity", (), {"label": "x"})()
    cls = type("Thing", (), {"class_identity": identity})
    assert required_access(cls) is AccessTier.VIEW


def test_required_access_handles_a_none_identity():
    from haywire.core.access import required_access

    cls = type("Thing", (), {"class_identity": None})
    assert required_access(cls) is AccessTier.VIEW
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_access/test_tier.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'haywire.core.access'`

- [x] **Step 3: Write the implementation**

Create `packages/haywire-core/src/haywire/core/access/tier.py`:

```python
"""AccessTier — the three cumulative access levels (ADR 0027).

A StrEnum so the member *is* its wire string: it serializes into
``~/.haywire/auth.json`` and into ``@panel(access=...)`` declarations with no
conversion layer, exactly like ``SlotName`` does for slot names.

Cumulative: ``admin`` satisfies every check ``edit`` does, and ``edit``
satisfies every check ``view`` does. Ordering is expressed through
:meth:`satisfies` rather than by making this an IntEnum, so the wire values
stay strings and adding a tier later does not renumber anything.
"""

from __future__ import annotations

from enum import StrEnum


class AccessTier(StrEnum):
    """What a principal may reach. See ADR 0027 for what these do and do not guarantee."""

    VIEW = "view"
    EDIT = "edit"
    ADMIN = "admin"

    @property
    def rank(self) -> int:
        """Position in the cumulative order — higher includes lower."""
        return _RANKS[self]

    def satisfies(self, required: "AccessTier") -> bool:
        """True when holding this tier is enough to meet ``required``."""
        return self.rank >= required.rank


_RANKS: dict[AccessTier, int] = {
    AccessTier.VIEW: 0,
    AccessTier.EDIT: 1,
    AccessTier.ADMIN: 2,
}


def required_access(cls: type) -> AccessTier:
    """The tier a principal needs before ``cls`` may be shown or called.

    One definition for all three gated surfaces — panels, editors and Farmhand
    tools. Those surfaces enforce at different *points* (a panel is transient
    and filtered once; an editor binding is persisted and so is refused at
    admission as well), but they must not disagree about the *rule*.

    Falls back to VIEW — the most permissive tier — in two cases, both
    deliberate:

    * **No ``class_identity``.** A class caught mid-hot-reload, or a hand-built
      test double, would otherwise vanish from every surface at once. A missing
      identity is a framework hiccup, not a security assertion.
    * **An identity with no ``access`` field.** Node, skin, widget and theme
      identities have none by design (ADR 0027) — they are never gated, and
      asking this function about one must not raise.
    """
    identity = getattr(cls, "class_identity", None)
    return getattr(identity, "access", AccessTier.VIEW)
```

Create `packages/haywire-core/src/haywire/core/access/__init__.py`:

```python
"""Access vocabulary — the tier enum and the resolver hook the studio fills in.

Core owns this because ``@panel(access=...)`` / ``@editor(access=...)`` /
``@farmhand(access=...)`` are core decorators. Core deliberately knows nothing
about passwords, cookies, or ASGI — that lives in ``haywire_studio.auth``.
See ADR 0027.
"""

from haywire.core.access.tier import AccessTier, required_access

__all__ = ["AccessTier", "required_access"]
```

- [x] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/test_access/test_tier.py -v`
Expected: PASS, 16 tests.

- [x] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/access/ tests/core/test_access/
git commit -m "feat(access): add AccessTier and the shared required_access lookup"
```

---

### Task 2: Resolver hook

**Files:**
- Create: `packages/haywire-core/src/haywire/core/access/resolver.py`
- Modify: `packages/haywire-core/src/haywire/core/access/__init__.py`
- Test: `tests/core/test_access/test_resolver.py`

**Interfaces:**
- Consumes: `AccessTier` from Task 1.
- Produces: `set_access_resolver(fn: Callable[[str | None], AccessTier] | None) -> None`, `resolve_tier(principal: str | None) -> AccessTier`, `access_resolver() -> Callable | None`.

**Why a module-level global and not a `ContextVar`:** `.insights/project_di_context.md` records that `ContextVar` broke hot-reload here — a reload captured a different `ContextVar` instance than the rest of the app. The DI context uses module-level globals for the same reason. Follow that.

- [x] **Step 1: Write the failing test**

Create `tests/core/test_access/test_resolver.py`:

```python
"""The access resolver hook — studio installs it; core defaults to full access."""

import pytest

from haywire.core.access import AccessTier, access_resolver, resolve_tier, set_access_resolver


@pytest.fixture(autouse=True)
def _restore_resolver():
    """Snapshot/restore the module global — a leaked resolver breaks later tests."""
    previous = access_resolver()
    yield
    set_access_resolver(previous)


def test_defaults_to_admin_when_no_resolver_installed():
    set_access_resolver(None)
    assert resolve_tier("alice") is AccessTier.ADMIN
    assert resolve_tier(None) is AccessTier.ADMIN


def test_installed_resolver_is_consulted():
    set_access_resolver(lambda name: AccessTier.VIEW if name == "bob" else AccessTier.EDIT)
    assert resolve_tier("bob") is AccessTier.VIEW
    assert resolve_tier("alice") is AccessTier.EDIT


def test_resolver_is_called_every_time_not_cached():
    calls: list[str | None] = []

    def _resolver(name):
        calls.append(name)
        return AccessTier.EDIT

    set_access_resolver(_resolver)
    resolve_tier("alice")
    resolve_tier("alice")
    assert calls == ["alice", "alice"]


def test_resolver_raising_falls_back_to_view_not_admin():
    def _boom(name):
        raise RuntimeError("roster unreadable")

    set_access_resolver(_boom)
    assert resolve_tier("alice") is AccessTier.VIEW


def test_set_none_restores_the_default():
    set_access_resolver(lambda name: AccessTier.VIEW)
    set_access_resolver(None)
    assert resolve_tier("alice") is AccessTier.ADMIN
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_access/test_resolver.py -v`
Expected: FAIL — `ImportError: cannot import name 'resolve_tier'`

- [x] **Step 3: Write the implementation**

Create `packages/haywire-core/src/haywire/core/access/resolver.py`:

```python
"""The seam between core's access vocabulary and the studio's roster.

Core cannot read ``~/.haywire/auth.json`` — that is studio territory — but
``SessionContext.can_edit()`` has to answer *now*, from live authority, not
from something stamped onto the session at login (ADR 0027: "the cookie
carries identity; it never carries authority").

So the studio installs a resolver at startup and core calls it. With no
resolver installed — the default, and the state of every install that has not
enabled authentication — every principal resolves to ADMIN, so nothing
changes for existing users.

Module-level global rather than a ContextVar: see
``.insights/project_di_context.md`` — a ContextVar broke hot-reload because a
reload captured a different instance than the rest of the app. The DI context
made the same choice for the same reason.
"""

from __future__ import annotations

import logging
from typing import Callable, Optional

from haywire.core.access.tier import AccessTier

logger = logging.getLogger(__name__)

AccessResolver = Callable[[Optional[str]], AccessTier]

_resolver: Optional[AccessResolver] = None


def set_access_resolver(fn: Optional[AccessResolver]) -> None:
    """Install (or with ``None``, remove) the tier resolver.

    Called once by the studio when authentication is enabled. Passing ``None``
    restores the unauthenticated default of ADMIN-for-everybody — which is also
    what tests should do in teardown.
    """
    global _resolver
    _resolver = fn


def access_resolver() -> Optional[AccessResolver]:
    """The currently installed resolver, or ``None``. Mainly for snapshot/restore in tests."""
    return _resolver


def resolve_tier(principal: Optional[str]) -> AccessTier:
    """The tier ``principal`` holds *right now*.

    Returns ADMIN when no resolver is installed (authentication disabled).
    Returns VIEW — the least privilege, not the most — when an installed
    resolver raises: a roster that cannot be read must not hand out admin.
    """
    resolver = _resolver
    if resolver is None:
        return AccessTier.ADMIN
    try:
        return resolver(principal)
    except Exception:
        logger.warning("Access resolver raised for principal %r; denying to VIEW", principal, exc_info=True)
        return AccessTier.VIEW
```

Replace `packages/haywire-core/src/haywire/core/access/__init__.py` with:

```python
"""Access vocabulary — the tier enum and the resolver hook the studio fills in.

Core owns this because ``@panel(access=...)`` / ``@editor(access=...)`` /
``@farmhand(access=...)`` are core decorators. Core deliberately knows nothing
about passwords, cookies, or ASGI — that lives in ``haywire_studio.auth``.
See ADR 0027.
"""

from haywire.core.access.resolver import (
    AccessResolver,
    access_resolver,
    resolve_tier,
    set_access_resolver,
)
from haywire.core.access.tier import AccessTier, required_access

__all__ = [
    "AccessResolver",
    "AccessTier",
    "access_resolver",
    "required_access",
    "resolve_tier",
    "set_access_resolver",
]
```

- [x] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/test_access/ -v`
Expected: PASS, 21 tests.

- [x] **Step 5: Commit**

```bash
git add packages/haywire-core/src/haywire/core/access/ tests/core/test_access/
git commit -m "feat(access): add resolver hook defaulting to admin, denying to view on error"
```

---

### Task 3: `SessionContext` access methods

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/session/context.py`
- Test: `tests/core/test_session/test_context_access.py`

**Interfaces:**
- Consumes: `AccessTier`, `resolve_tier`, `set_access_resolver` from Tasks 1–2.
- Produces: `SessionContext.principal: Optional[str]` (plain field, `None` by default), and methods `can_access(required: AccessTier) -> bool`, `can_view() -> bool`, `can_edit() -> bool`, `can_admin() -> bool`.

- [x] **Step 1: Write the failing test**

Create `tests/core/test_session/test_context_access.py`:

```python
"""SessionContext access predicates — read live authority, never a stamped tier."""

from unittest.mock import MagicMock

import pytest

from haywire.core.access import AccessTier, access_resolver, set_access_resolver
from haywire.core.session.context import SessionContext


@pytest.fixture(autouse=True)
def _restore_resolver():
    previous = access_resolver()
    yield
    set_access_resolver(previous)


def _ctx() -> SessionContext:
    app = MagicMock()
    app.library_state_container = MagicMock()
    return SessionContext(session_id="s1", app=app)


def test_principal_defaults_to_none():
    assert _ctx().principal is None


def test_everything_allowed_when_no_resolver_installed():
    set_access_resolver(None)
    ctx = _ctx()
    assert ctx.can_view() is True
    assert ctx.can_edit() is True
    assert ctx.can_admin() is True


def test_view_principal_can_only_view():
    set_access_resolver(lambda name: AccessTier.VIEW)
    ctx = _ctx()
    ctx.principal = "bob"
    assert ctx.can_view() is True
    assert ctx.can_edit() is False
    assert ctx.can_admin() is False


def test_edit_principal_can_view_and_edit():
    set_access_resolver(lambda name: AccessTier.EDIT)
    ctx = _ctx()
    ctx.principal = "carol"
    assert ctx.can_view() is True
    assert ctx.can_edit() is True
    assert ctx.can_admin() is False


def test_can_access_takes_the_tier_as_data():
    set_access_resolver(lambda name: AccessTier.EDIT)
    ctx = _ctx()
    ctx.principal = "carol"
    assert ctx.can_access(AccessTier.VIEW) is True
    assert ctx.can_access(AccessTier.EDIT) is True
    assert ctx.can_access(AccessTier.ADMIN) is False


def test_the_principal_name_reaches_the_resolver():
    seen: list[str | None] = []
    set_access_resolver(lambda name: seen.append(name) or AccessTier.VIEW)
    ctx = _ctx()
    ctx.principal = "dave"
    ctx.can_edit()
    assert seen == ["dave"]


def test_demotion_takes_effect_without_touching_the_context():
    """The whole point of reading live: no re-login, no eviction, no stale tier."""
    tier = {"value": AccessTier.ADMIN}
    set_access_resolver(lambda name: tier["value"])
    ctx = _ctx()
    ctx.principal = "erin"
    assert ctx.can_admin() is True

    tier["value"] = AccessTier.VIEW
    assert ctx.can_admin() is False
    assert ctx.can_view() is True
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_session/test_context_access.py -v`
Expected: FAIL — `AttributeError: 'SessionContext' object has no attribute 'principal'`

- [x] **Step 3: Add the import and plain field**

In `packages/haywire-core/src/haywire/core/session/context.py`, add to the existing import block near the top (after the `from haywire.core.session.signals...` imports):

```python
from haywire.core.access import AccessTier, resolve_tier
```

Then in the "Plain fields (non-reactive)" annotation block, add `principal` after `data`:

```python
    # --- Plain fields (non-reactive) ---
    session_id: str
    app: "IProjectState"
    session: "Session"  # set by Session.__init__ immediately after construction
    app_data: "AppDataNamespace"
    data: "SessionDataNamespace"
    principal: Optional[str]  # set by the studio page handler; None when auth is off
```

And in `__init__`, set it before `_seed_signal_fields(self)`:

```python
        self.data = SessionDataNamespace(app.library_state_container, session_id)
        # None means "authentication is not in play for this session" — the
        # resolver then answers ADMIN. The studio's page handler sets this from
        # the verified cookie when authentication is enabled.
        self.principal = None
```

- [x] **Step 4: Add the four methods**

Append to the `SessionContext` class body, after `_signal_emit`:

```python
    # ------------------------------------------------------------------
    # Access (ADR 0027)
    # ------------------------------------------------------------------

    def can_access(self, required: AccessTier) -> bool:
        """Whether this session's principal currently holds at least ``required``.

        Reads live authority through the resolver on every call rather than a
        tier stamped at login, so removing or demoting a principal takes effect
        on their next action with no eviction and no re-login. Use this when the
        tier arrives as data (e.g. ``editor.class_identity.access``); use
        :meth:`can_view` / :meth:`can_edit` / :meth:`can_admin` when it is literal.
        """
        return resolve_tier(self.principal).satisfies(required)

    def can_view(self) -> bool:
        """True for every authenticated principal — the lowest tier."""
        return self.can_access(AccessTier.VIEW)

    def can_edit(self) -> bool:
        """True for ``edit`` and ``admin``. Gates every mutating affordance."""
        return self.can_access(AccessTier.EDIT)

    def can_admin(self) -> bool:
        """True for ``admin`` only. Gates roster management and destructive tools."""
        return self.can_access(AccessTier.ADMIN)
```

- [x] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_session/test_context_access.py -v`
Expected: PASS, 7 tests.

- [x] **Step 6: Verify no existing session behaviour regressed**

Run: `uv run pytest tests/core/test_session/ tests/ui/ -q -m "not browser"`
Expected: all pass. `principal` defaults to `None` and no resolver is installed, so every existing check resolves to ADMIN.

- [x] **Step 7: Commit**

```bash
git add packages/haywire-core/src/haywire/core/session/context.py tests/core/test_session/test_context_access.py
git commit -m "feat(access): add principal + can_view/can_edit/can_admin/can_access to SessionContext"
```

---

### Task 4: Quality gate

- [x] **Step 1: Lint and format**

```bash
uv run ruff check .
uv run ruff format --check .
```

Expected: both clean. If `format --check` reports drift, run `uv run ruff format .` and amend.

- [x] **Step 2: Type check**

```bash
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-marketplace/haybale_marketplace/ barn/haybale-share/haybale_share/ barn/haybale-graph-editor/haybale_graph_editor/ barn/haybale-haystack/haybale_haystack/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-TEST_A/haybale_test_a/ tests/
```

Expected: `Success: no issues found`.

- [x] **Step 3: Pre-commit test gate**

```bash
uv run pytest -m "not browser and not perf" -q > /tmp/slice1.log 2>&1; echo "exit=$?"
grep -E "^FAILED|^ERROR" /tmp/slice1.log
grep -E "passed|failed" /tmp/slice1.log | tail -1
```

Expected: `exit=0`, no FAILED/ERROR lines.

- [x] **Step 4: Commit any fixes**

```bash
git add -A && git commit -m "chore(access): lint/type fixes for slice 1"
```

---

### Task 5 (final): Record delivery and drift

- [x] **Step 1: Fill in the Drift Log below.** For every place the implementation differs from what this plan specified — a changed signature, a file in a different location, a test that had to be written differently, an assumption that turned out false — write one line: what the plan said, what was actually built, and why. **If there was no drift, write "No drift." explicitly.** An empty log is indistinguishable from an unfilled one.

- [x] **Step 2: Record the public surface Slice 2 will consume**, verbatim, in the Delivered section — so the next slice does not have to re-derive it.

- [x] **Step 3: Flip the front matter** `status: planned` → `status: implemented`.

- [x] **Step 4: Commit**

```bash
git add docs/superpowers/plans/2026-08-15-auth-1-core-access.md
git commit -m "docs(plan): slice 1 complete — core access vocabulary"
```

---

## Delivered

**`packages/haywire-core/src/haywire/core/access/tier.py`**
- `class AccessTier(StrEnum)` — members `VIEW = "view"`, `EDIT = "edit"`, `ADMIN = "admin"`
  - `AccessTier.rank -> int` — `VIEW=0, EDIT=1, ADMIN=2`
  - `AccessTier.satisfies(self, required: AccessTier) -> bool`
- `required_access(cls: type) -> AccessTier` — reads `cls.class_identity.access`, coerces it through `AccessTier(...)`, and falls back to `AccessTier.VIEW` in three cases: no `class_identity`, an identity with no `access` field, or an `access` value that isn't a valid tier (e.g. a typo'd raw string — logged as a warning, not raised).

**`packages/haywire-core/src/haywire/core/access/resolver.py`**
- `AccessResolver = Callable[[Optional[str]], AccessTier]`
- `set_access_resolver(fn: Optional[AccessResolver]) -> None`
- `access_resolver() -> Optional[AccessResolver]`
- `resolve_tier(principal: Optional[str]) -> AccessTier` — `AccessTier.ADMIN` when no resolver installed; `AccessTier.VIEW` when the installed resolver raises.

**`packages/haywire-core/src/haywire/core/access/__init__.py`** re-exports all of the above: `AccessResolver`, `AccessTier`, `access_resolver`, `required_access`, `resolve_tier`, `set_access_resolver`.

**`packages/haywire-core/src/haywire/core/session/context.py`** — `SessionContext` gained:
- `principal: Optional[str]` (plain field, defaults to `None` in `__init__`)
- `can_access(self, required: AccessTier) -> bool` — `resolve_tier(self.principal).satisfies(required)`, evaluated live on every call
- `can_view(self) -> bool`, `can_edit(self) -> bool`, `can_admin(self) -> bool`

**Tests:** `tests/core/test_access/test_tier.py` (19), `tests/core/test_access/test_resolver.py` (6), `tests/core/test_session/test_context_access.py` (7) — 32 new tests total.

**Commits (worktree `auth-1-core-access`, based on `master@5e5af0ac`):**
- `75a07db3` chore: fix pre-existing lint/type errors ahead of auth slice 1
- `a455a337` feat(access): add AccessTier and the shared required_access lookup
- `a9f6d9f5` feat(access): add resolver hook defaulting to admin, denying to view on error
- `5653f9d5` feat(access): add principal + can_view/can_edit/can_admin/can_access to SessionContext
- `b99f8263` docs(plan): slice 1 complete — core access vocabulary
- `c6a490b3` fix(access): coerce required_access's return, fix can_view docstring

## Drift Log

**Pre-existing repo baseline (discovered at Task 0 Step 1, not this slice's scope):** 3 mypy errors and 2 ruff errors existed on `master` before this slice started, all in files unrelated to access/session (`panel/render_utils.py`, `test_refresh_flow_ui.py`, `test_schema.py`, `network/settings.py`, `test_network_settings_unit.py`). Fixed interactively per user instruction (commit `75a07db3`) so Task 0's "confirm clean baseline" gate could pass honestly, rather than silently working around pre-existing failures. Not a deviation from this plan's own scope, but recorded because it happened inside this slice's session and the fixes are commits on this branch.

**Task 1:** the plan's own verbatim test code (`tests/core/test_access/test_tier.py`) violates two ruff rules already enabled in this repo: `PT011` (`pytest.raises(ValueError)` too broad without `match=`) and `PT006` (`pytest.mark.parametrize` id-arg should be a tuple, not a comma-string). Fixed by adding `match="superuser"` and changing the id-arg to `("held", "required", "expected")` — no behavior change, same 17 tests. Folded into the Task 1 commit (amended before any review), since the plan's Global Constraints require `ruff check .` clean and this is a straightforward reconciliation, not a design question.

**Task 4 (quality gate):** the repo-wide `uv run mypy` command surfaced one error the narrower per-task checks didn't catch: `tests/core/test_session/test_context_access.py:65` — the plan's verbatim `lambda name: seen.append(name) or AccessTier.VIEW` type-checks as `None | AccessTier` because `list.append()` returns `None` (the idiom is correct at runtime via short-circuit `or`, but mypy can't express that). Fixed by replacing the lambda with a small named `_resolver` function carrying an explicit `-> AccessTier` return type; same assertion, same 7 tests. Amended into the Task 3 commit (SHA changed from the version its task review approved, `5e2ba2e6`, to `5653f9d5`) — not re-sent through task review, since it's the same class of mechanical, behavior-preserving typing fix as the Task 1 ruff correction above.

**Task 2 review — false positive, not drift:** the Task 2 reviewer raised a Critical finding that `resolver.py`'s `logger.warning(...)` line exceeded the 109-character limit (claimed 110 chars). Verified directly: `uv run ruff check` and `uv run ruff format --check` both pass on the file, and the line is 108 characters. No code change was made; the finding was a reviewer arithmetic error, not a defect. Recorded here so a later reader of the review transcript doesn't mistake it for an unresolved issue.

**Final whole-branch review (Opus, `ad2ba3eee02c7c6a2`):** approved to merge, with one Important finding fixed post-review in commit `c6a490b3` — `required_access()` declared `-> AccessTier` but its two-arg `getattr` fallback returned `Any` uncoerced, so a raw string (e.g. `@panel(access="admin")`, which no identity dataclass validates) passed through and raised `AttributeError` on `.satisfies()` later, non-fail-closed. Verified directly before fixing:

    raw-string access -> 'admin' <class 'str'>  is AccessTier.ADMIN: False
    satisfies RAISED: AttributeError 'str' object has no attribute 'satisfies'

Fixed by coercing through `AccessTier(declared)`, catching `ValueError` and falling back to `VIEW` with a logged warning — consistent with the resolver's own fail-closed-to-VIEW philosophy. Zero consumers existed yet (verified by grep across `packages/` and `barn/`), so this was latent, not reachable, but Slice 2 (`roster-cli`) is exactly where `AccessTier` values start arriving from JSON on disk — the raw-string source this guards against — so it was fixed here rather than deferred. Also fixed per the same review: `can_view()`'s docstring claimed "True for every authenticated principal," which is inaccurate (it's an authorization check, not an authentication one, and is `True` for `principal=None` when no resolver is installed). Two contracts the reviewer flagged as untested are now pinned: `required_access` coercing/denying on a raw string, and `resolve_tier(None)` reaching an *installed* resolver with the `None` intact.

The reviewer's Minor note on plan Step-4/Step-2 "expected N tests" comments being stale (16/21 vs actual 17/22) is left as-is in the Task 1/Task 2 step text above — cosmetic, and the Delivered section here carries the accurate final counts.

No other drift. Every produced signature matches what Slice 2's brief (`2026-08-15-auth-2-roster-cli.md`) expects to consume (`AccessTier`, `set_access_resolver`).
