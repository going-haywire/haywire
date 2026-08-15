---
status: planned
slice: 3 of 6
feature: studio-authentication
adr: docs/adr/0027-studio-authentication.md
previous: 2026-08-15-auth-2-roster-cli.md
next: 2026-08-15-auth-4-gated-surfaces.md
---

# Slice 3 — The gate and login — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make authentication real — a pure-ASGI gate that admits a valid cookie or a valid bearer token and rejects everything else on both `http` and `websocket`, a plain-HTTP login page, principal binding onto `SessionContext`, session eviction, and optional TLS.

**Architecture:** One middleware on the root ASGI app, installed in `HaywireApp.run()` beside `_install_ip_allowlist`. Login is a plain FastAPI route pair returning self-contained HTML — **not** a NiceGUI page, because a NiceGUI login handler runs over the websocket, which would force `/_nicegui_ws/` open to unauthenticated clients and swallow the gate.

**Tech Stack:** Python 3.12 stdlib (`hmac`, `hashlib`, `base64`, `json`, `secrets`), FastAPI routes on `nicegui.app`, pure-ASGI middleware. No new dependencies.

## Chain position

- **Previous slice:** `2026-08-15-auth-2-roster-cli.md` — provides `load_roster`, `Roster`, `Principal`, `authenticate`, `RosterCache`, `install_resolver`.
- **Next slice:** `2026-08-15-auth-4-gated-surfaces.md` — consumes `ctx.principal` being populated and the resolver being installed.
- **This is the first slice that changes runtime behaviour** — but only when the roster says `enabled: true`. With auth off, `HaywireApp.run()` installs nothing and every path is byte-identical to today.

## Chain protocol

1. **Task 0** re-affirms current state and reconciles against Slice 2's Drift Log before any implementation.
2. **The final task** fills in this document's Drift Log and flips `status:` to `implemented`.
3. A slice that finds the plan wrong **edits the plan** and records why.

## Global Constraints

- Line length 109; `ruff check` **and** `ruff format --check` must both pass.
- `uv run mypy` must pass for every path in the CLAUDE.md mypy command.
- **No new runtime dependencies.**
- **The gate must be pure-ASGI.** Never a `BaseHTTPMiddleware` subclass — it would never see `scope["type"] == "websocket"` and would let the entire UI through. See ADR 0026's headline section.
- **The signer must:** sign the whole payload including the expiry; validate expiry from the *signed* payload, never from the cookie's `Max-Age`; use `hmac.compare_digest`; encode unambiguously (base64url JSON, not delimiter-joined fields).
- **The unauthenticated surface is exactly `GET /login` and `POST /login`.** Nothing else. Not `/_nicegui_ws/`, not `/_nicegui/*`, not `/api/code-intel/*`.
- Cookie flags: `HttpOnly; SameSite=Lax; Path=/`, plus `Secure` **only** under real TLS.

---

### Task 0: Affirm current state and reconcile Slice 2 drift

- [ ] **Step 1: Confirm Slice 2 landed**

```bash
grep -n "^status:" docs/superpowers/plans/2026-08-15-auth-2-roster-cli.md
```

Expected: `status: implemented`.

- [ ] **Step 2: Read Slice 2's Drift Log and Delivered sections.** If names or signatures differ from what this plan assumes, **edit this plan now** and note the correction in this plan's Drift Log.

- [ ] **Step 3: Verify the Slice 2 surface**

```bash
uv run python -c "
from haywire_studio.auth.roster import load_roster, Roster, Principal
from haywire_studio.auth.operations import authenticate
from haywire_studio.auth.live import RosterCache, install_resolver
print('ok')
"
```

Expected: `ok`

- [ ] **Step 4: Re-read the three files this slice modifies** and confirm the line references still hold:
  - `packages/haywire-studio/src/haywire_studio/app.py` — `run()` picks `host` from `NetworkSettings` and calls `_install_ip_allowlist`; `create_ui()` defines `main_page()` with **no parameters**.
  - `packages/haywire-studio/src/haywire_studio/farmhand/host.py` — `mount()` builds `allowed_origins` with a hardcoded `http://`.
  - `packages/haywire-studio/src/haywire_studio/network/settings.py` — `NetworkSettings` has five settings.

- [ ] **Step 5: Confirm baseline clean**

```bash
uv run ruff check packages/haywire-studio/src/ && uv run mypy packages/haywire-studio/src/
```

---

### Task 1: Cookie signing

**Files:**
- Create: `packages/haywire-studio/src/haywire_studio/auth/cookies.py`
- Test: `tests/auth/test_cookies.py`

**Interfaces:**
- Produces: `COOKIE_NAME = "haywire_session"`, `secret_path() -> Path`, `load_or_create_secret(path=None) -> bytes`, `rotate_secret(path=None) -> bytes`, `sign_session(principal: str, *, secret: bytes, days: int, now: float | None = None) -> str`, `verify_session(token: str, *, secret: bytes, now: float | None = None) -> str | None`.

- [ ] **Step 1: Write the failing test**

Create `tests/auth/test_cookies.py`:

```python
"""HMAC-signed session cookie. The signature is the whole boundary — test it hard."""

import base64
import json
import stat

import pytest

from haywire_studio.auth.cookies import (
    load_or_create_secret,
    rotate_secret,
    sign_session,
    verify_session,
)

SECRET = b"0" * 32
OTHER = b"1" * 32


def test_round_trip():
    assert verify_session(sign_session("alice", secret=SECRET, days=30), secret=SECRET) == "alice"


def test_wrong_secret_rejects():
    assert verify_session(sign_session("alice", secret=SECRET, days=30), secret=OTHER) is None


def test_tampered_payload_rejects():
    token = sign_session("alice", secret=SECRET, days=30)
    payload_b64, signature = token.split(".")
    payload = json.loads(base64.urlsafe_b64decode(payload_b64 + "=="))
    payload["p"] = "root"
    forged = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    assert verify_session(f"{forged}.{signature}", secret=SECRET) is None


def test_expired_token_rejects():
    token = sign_session("alice", secret=SECRET, days=1, now=1000.0)
    assert verify_session(token, secret=SECRET, now=1000.0 + 2 * 86400) is None


def test_unexpired_token_accepts():
    token = sign_session("alice", secret=SECRET, days=30, now=1000.0)
    assert verify_session(token, secret=SECRET, now=1000.0 + 86400) == "alice"


def test_days_zero_never_expires():
    token = sign_session("alice", secret=SECRET, days=0, now=1000.0)
    assert verify_session(token, secret=SECRET, now=1000.0 + 10_000 * 86400) == "alice"


def test_expiry_cannot_be_extended_without_the_secret():
    """The expiry is inside the signed payload — re-signing is the only way to change it."""
    token = sign_session("alice", secret=SECRET, days=1, now=1000.0)
    payload_b64, signature = token.split(".")
    payload = json.loads(base64.urlsafe_b64decode(payload_b64 + "=="))
    payload["exp"] = 10**12
    forged = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    assert verify_session(f"{forged}.{signature}", secret=SECRET) is None


@pytest.mark.parametrize(
    "token",
    ["", ".", "a.b", "no-dot", "....", "!!!.???", "a.b.c"],
)
def test_malformed_tokens_reject_without_raising(token):
    assert verify_session(token, secret=SECRET) is None


def test_principal_with_a_dot_survives_the_round_trip():
    """Payload is base64url JSON, not delimiter-joined fields — separators in names are safe."""
    assert verify_session(sign_session("a.b|c", secret=SECRET, days=30), secret=SECRET) == "a.b|c"


# --- secret file ------------------------------------------------------


def test_secret_is_created_at_0600(tmp_path):
    path = tmp_path / "session_secret"
    secret = load_or_create_secret(path)
    assert len(secret) == 32
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_secret_is_stable_across_calls(tmp_path):
    path = tmp_path / "session_secret"
    assert load_or_create_secret(path) == load_or_create_secret(path)


def test_rotate_replaces_the_secret(tmp_path):
    path = tmp_path / "session_secret"
    first = load_or_create_secret(path)
    second = rotate_secret(path)
    assert first != second
    assert load_or_create_secret(path) == second


def test_rotating_invalidates_every_existing_cookie(tmp_path):
    path = tmp_path / "session_secret"
    secret = load_or_create_secret(path)
    token = sign_session("alice", secret=secret, days=30)
    assert verify_session(token, secret=rotate_secret(path)) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/auth/test_cookies.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'haywire_studio.auth.cookies'`

- [ ] **Step 3: Write the implementation**

Create `packages/haywire-studio/src/haywire_studio/auth/cookies.py`:

```python
"""The signed session cookie (ADR 0027).

This signature is the single artifact standing between an anonymous HTTP
request and full access to the studio, so the rules below are not style
preferences:

* **The whole payload is signed, expiry included.** Validation reads the expiry
  out of the *signed* payload — never from the cookie's ``Max-Age``, which the
  client controls and can simply omit.
* **``hmac.compare_digest``**, never ``==``.
* **base64url JSON, not delimiter-joined fields.** ``alice|admin`` splits
  ambiguously the moment a principal name contains the separator.
* **The cookie carries identity, never authority.** No tier in the payload — the
  tier is read live from the roster, which is what makes removing a principal an
  actual revocation rather than a request (ADR 0027).

Rotating the secret invalidates every issued cookie at once. That is the
"log everyone out" lever.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from pathlib import Path

COOKIE_NAME = "haywire_session"
SECRET_FILENAME = "session_secret"
SECRET_BYTES = 32


def secret_path() -> Path:
    """``~/.haywire/session_secret`` — beside the roster, same 0600 discipline."""
    return Path.home() / ".haywire" / SECRET_FILENAME


def load_or_create_secret(path: Path | None = None) -> bytes:
    """Read the signing secret, generating it on first use."""
    target = path or secret_path()
    if target.exists():
        data = target.read_bytes()
        if len(data) >= SECRET_BYTES:
            return data
    return rotate_secret(target)


def rotate_secret(path: Path | None = None) -> bytes:
    """Generate and persist a fresh secret, invalidating every issued cookie."""
    target = path or secret_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    secret = secrets.token_bytes(SECRET_BYTES)
    tmp = target.with_name(f".{target.name}.tmp")
    tmp.write_bytes(secret)
    tmp.chmod(0o600)
    tmp.replace(target)
    return secret


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def sign_session(principal: str, *, secret: bytes, days: int, now: float | None = None) -> str:
    """Build ``<base64url-payload>.<base64url-signature>``.

    ``days=0`` means never expires — the kiosk case, where a show machine that
    reboots at 6am must not land on a login screen with nobody around.
    """
    issued = int(now if now is not None else time.time())
    payload = {"p": principal, "iat": issued, "exp": 0 if days == 0 else issued + days * 86400}
    payload_b64 = _b64encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signature = hmac.new(secret, payload_b64.encode("ascii"), hashlib.sha256).digest()
    return f"{payload_b64}.{_b64encode(signature)}"


def verify_session(token: str, *, secret: bytes, now: float | None = None) -> str | None:
    """Return the principal name, or ``None`` for any failure.

    Never raises: a malformed cookie is a rejection, not a 500 inside middleware
    that runs before every request in the process.
    """
    try:
        payload_b64, signature_b64 = token.split(".")
    except ValueError:
        return None

    try:
        expected = hmac.new(secret, payload_b64.encode("ascii"), hashlib.sha256).digest()
        if not hmac.compare_digest(_b64decode(signature_b64), expected):
            return None
        payload = json.loads(_b64decode(payload_b64))
    except Exception:
        return None

    principal = payload.get("p")
    expires = payload.get("exp")
    if not isinstance(principal, str) or not principal or not isinstance(expires, int):
        return None

    if expires != 0 and (now if now is not None else time.time()) >= expires:
        return None

    return principal
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/auth/test_cookies.py -v`
Expected: PASS, 20 tests.

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-studio/src/haywire_studio/auth/cookies.py tests/auth/test_cookies.py
git commit -m "feat(auth): HMAC-signed session cookie with signed expiry"
```

---

### Task 2: The gate

**Files:**
- Create: `packages/haywire-studio/src/haywire_studio/auth/gate.py`
- Test: `tests/auth/test_gate.py`

**Interfaces:**
- Consumes: Task 1, Slice 2's `RosterCache`.
- Produces: `AuthGateMiddleware(app, *, cache: RosterCache, secret: bytes)` — pure-ASGI callable; `EXEMPT_PATHS: frozenset[str]`; `PRINCIPAL_SCOPE_KEY = "haywire_principal"`; `last_seen() -> dict[str, float]`; `record_seen(name: str) -> None`.

- [ ] **Step 1: Write the failing test**

Create `tests/auth/test_gate.py`:

```python
"""The gate — pure-ASGI, cookie OR bearer, http AND websocket."""

import pytest

from haywire.core.access import AccessTier
from haywire_studio.auth.cookies import COOKIE_NAME, sign_session
from haywire_studio.auth.gate import PRINCIPAL_SCOPE_KEY, AuthGateMiddleware
from haywire_studio.auth.live import RosterCache
from haywire_studio.auth.operations import add_agent, add_user, enable_auth
from haywire_studio.auth.roster import Roster, save_roster

SECRET = b"0" * 32
STRONG = "Correct-Horse9"


@pytest.fixture
def path(tmp_path):
    return tmp_path / "auth.json"


@pytest.fixture
def enabled_roster(path):
    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    enable_auth("alice", STRONG, path=path)
    return path


class _Recorder:
    """Inner ASGI app that records whether it was reached and with what scope."""

    def __init__(self):
        self.reached = False
        self.scope = None

    async def __call__(self, scope, receive, send):
        self.reached = True
        self.scope = scope
        if scope["type"] == "http":
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"ok"})


async def _call(gate, scope):
    sent = []

    async def _send(message):
        sent.append(message)

    async def _receive():
        return {"type": "http.request"}

    await gate(scope, _receive, _send)
    return sent


def _http(path="/", headers=None, method="GET"):
    return {
        "type": "http",
        "method": method,
        "path": path,
        "headers": headers or [],
        "client": ("127.0.0.1", 5000),
        "scheme": "http",
    }


def _ws(path="/_nicegui_ws/", headers=None):
    return {"type": "websocket", "path": path, "headers": headers or [], "client": ("127.0.0.1", 5000)}


def _gate(path, inner=None):
    return AuthGateMiddleware(inner or _Recorder(), cache=RosterCache(path), secret=SECRET)


# --- pass-through when auth is disabled -------------------------------


@pytest.mark.anyio
async def test_disabled_roster_lets_everything_through(path):
    save_roster(Roster(enabled=False), path)
    inner = _Recorder()
    await _call(_gate(path, inner), _http("/"))
    assert inner.reached is True


# --- lifespan ---------------------------------------------------------


@pytest.mark.anyio
async def test_lifespan_always_passes_through(enabled_roster):
    inner = _Recorder()
    await _call(_gate(enabled_roster, inner), {"type": "lifespan"})
    assert inner.reached is True


# --- exemptions -------------------------------------------------------


@pytest.mark.anyio
@pytest.mark.parametrize("route", ["/login"])
async def test_login_is_reachable_unauthenticated(enabled_roster, route):
    inner = _Recorder()
    await _call(_gate(enabled_roster, inner), _http(route))
    assert inner.reached is True


@pytest.mark.anyio
@pytest.mark.parametrize("route", ["/", "/_nicegui_ws/", "/_nicegui/3.13.0/static/x.js", "/api/code-intel/hover"])
async def test_everything_else_is_gated(enabled_roster, route):
    inner = _Recorder()
    await _call(_gate(enabled_roster, inner), _http(route))
    assert inner.reached is False


# --- cookie -----------------------------------------------------------


@pytest.mark.anyio
async def test_valid_cookie_admits_and_stamps_the_scope(enabled_roster):
    inner = _Recorder()
    cookie = f"{COOKIE_NAME}={sign_session('alice', secret=SECRET, days=30)}"
    await _call(_gate(enabled_roster, inner), _http("/", [(b"cookie", cookie.encode())]))
    assert inner.reached is True
    assert inner.scope[PRINCIPAL_SCOPE_KEY] == "alice"


@pytest.mark.anyio
async def test_cookie_for_a_removed_principal_is_rejected(enabled_roster):
    """Revocation: the cookie is still cryptographically valid; the roster is authority."""
    inner = _Recorder()
    cookie = f"{COOKIE_NAME}={sign_session('ghost', secret=SECRET, days=30)}"
    await _call(_gate(enabled_roster, inner), _http("/", [(b"cookie", cookie.encode())]))
    assert inner.reached is False


@pytest.mark.anyio
async def test_cookie_signed_with_another_secret_is_rejected(enabled_roster):
    inner = _Recorder()
    cookie = f"{COOKIE_NAME}={sign_session('alice', secret=b'9' * 32, days=30)}"
    await _call(_gate(enabled_roster, inner), _http("/", [(b"cookie", cookie.encode())]))
    assert inner.reached is False


# --- bearer -----------------------------------------------------------


@pytest.mark.anyio
async def test_valid_bearer_token_admits(enabled_roster):
    agent = add_agent("builder", AccessTier.EDIT, path=enabled_roster)
    inner = _Recorder()
    headers = [(b"authorization", f"Bearer {agent.token}".encode())]
    await _call(_gate(enabled_roster, inner), _http("/mcp", headers))
    assert inner.reached is True
    assert inner.scope[PRINCIPAL_SCOPE_KEY] == "builder"


@pytest.mark.anyio
async def test_unknown_bearer_token_is_rejected(enabled_roster):
    inner = _Recorder()
    headers = [(b"authorization", b"Bearer nope")]
    await _call(_gate(enabled_roster, inner), _http("/mcp", headers))
    assert inner.reached is False


@pytest.mark.anyio
async def test_workspace_scoped_agent_rejected_in_another_workspace(enabled_roster, tmp_path):
    agent = add_agent("builder", AccessTier.EDIT, workspace="/other/project", path=enabled_roster)
    inner = _Recorder()
    gate = AuthGateMiddleware(
        inner,
        cache=RosterCache(enabled_roster),
        secret=SECRET,
        workspace_root=str(tmp_path),
    )
    headers = [(b"authorization", f"Bearer {agent.token}".encode())]
    await _call(gate, _http("/mcp", headers))
    assert inner.reached is False


@pytest.mark.anyio
async def test_unscoped_agent_works_in_any_workspace(enabled_roster, tmp_path):
    agent = add_agent("builder", AccessTier.EDIT, path=enabled_roster)
    inner = _Recorder()
    gate = AuthGateMiddleware(
        inner, cache=RosterCache(enabled_roster), secret=SECRET, workspace_root=str(tmp_path)
    )
    headers = [(b"authorization", f"Bearer {agent.token}".encode())]
    await _call(gate, _http("/mcp", headers))
    assert inner.reached is True


# --- websocket --------------------------------------------------------


@pytest.mark.anyio
async def test_websocket_without_cookie_is_closed_not_passed(enabled_roster):
    inner = _Recorder()
    sent = await _call(_gate(enabled_roster, inner), _ws())
    assert inner.reached is False
    assert sent[0]["type"] == "websocket.close"
    assert sent[0]["code"] == 1008


@pytest.mark.anyio
async def test_websocket_with_valid_cookie_passes(enabled_roster):
    inner = _Recorder()
    cookie = f"{COOKIE_NAME}={sign_session('alice', secret=SECRET, days=30)}"
    await _call(_gate(enabled_roster, inner), _ws(headers=[(b"cookie", cookie.encode())]))
    assert inner.reached is True


# --- rejection shape --------------------------------------------------


@pytest.mark.anyio
async def test_browser_navigation_is_redirected_to_login(enabled_roster):
    sent = await _call(_gate(enabled_roster), _http("/", [(b"accept", b"text/html")]))
    assert sent[0]["status"] == 303
    assert (b"location", b"/login") in sent[0]["headers"]


@pytest.mark.anyio
async def test_non_browser_request_gets_401_json(enabled_roster):
    sent = await _call(_gate(enabled_roster), _http("/api/code-intel/hover", method="POST"))
    assert sent[0]["status"] == 401


# --- last seen --------------------------------------------------------


@pytest.mark.anyio
async def test_admitted_request_records_last_seen(enabled_roster):
    from haywire_studio.auth.gate import last_seen

    last_seen().clear()
    agent = add_agent("builder", AccessTier.EDIT, path=enabled_roster)
    headers = [(b"authorization", f"Bearer {agent.token}".encode())]
    await _call(_gate(enabled_roster), _http("/mcp", headers))
    assert "builder" in last_seen()
```

- [ ] **Step 2: Add the anyio backend fixture if missing**

Check `tests/conftest.py` for an `anyio_backend` fixture. If absent, add to `tests/auth/conftest.py`:

```python
import pytest


@pytest.fixture
def anyio_backend():
    return "asyncio"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/auth/test_gate.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'haywire_studio.auth.gate'`

- [ ] **Step 4: Write the implementation**

Create `packages/haywire-studio/src/haywire_studio/auth/gate.py`:

```python
"""The authentication gate (ADR 0027).

**Pure-ASGI, not BaseHTTPMiddleware.** NiceGUI's entire UI runs over Socket.IO
at ``/_nicegui_ws/``; a ``BaseHTTPMiddleware`` subclass only ever sees
``scope["type"] == "http"``, so it would gate the login page and let every
subsequent websocket frame — the whole application — through unfiltered. This
mirrors ``network/ip_filter.py``, which is pure-ASGI for exactly the same
reason. If you are about to "simplify" this into a Starlette middleware class:
don't. See ADR 0026.

**One gate, two credentials.** ``/mcp`` is mounted *inside* this same ASGI app,
so a root-level wrapper covers it whether or not that was intended. Rather than
carving it out — which would make the boundary's correctness depend on
``FarmhandSettings.require_auth`` staying True — the gate accepts a valid
session cookie *or* a valid agent bearer token. ``BearerTokenMiddleware`` stays
mounted underneath as defence in depth.

**A websocket is one scope.** ASGI calls the app once per connection; the whole
connection lifetime then happens inside that call. So this check runs at the
handshake and never again for that socket. That makes it free, and it means the
gate cannot revoke a socket it has already admitted — revocation reaches live
sessions by push, from ``eviction.py``.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from haywire_studio.auth.cookies import COOKIE_NAME, verify_session
from haywire_studio.auth.live import RosterCache

logger = logging.getLogger(__name__)

#: Reachable without any credential. Exactly two routes, both plain HTTP.
#: Adding anything here widens the unauthenticated surface — in particular,
#: never add ``/_nicegui_ws/`` or any ``/_nicegui/`` asset path.
EXEMPT_PATHS = frozenset({"/login"})

#: Where the resolved principal name is stashed for downstream consumers —
#: the NiceGUI page handler (which binds it onto SessionContext) and the
#: Farmhand handlers (which filter the tool list by its tier).
PRINCIPAL_SCOPE_KEY = "haywire_principal"

_LAST_SEEN: dict[str, float] = {}


def last_seen() -> dict[str, float]:
    """principal name → monotonic timestamp of their most recent admitted request.

    Drives agent presence in the TopBar. For a browser principal an open socket
    is the better liveness signal; for an agent this is the only one, because
    MCP traffic is request-shaped and its ``ping`` is an optional protocol
    message.
    """
    return _LAST_SEEN


def record_seen(name: str) -> None:
    _LAST_SEEN[name] = time.monotonic()


class AuthGateMiddleware:
    """Admit a valid cookie or a valid bearer token; reject everything else."""

    def __init__(
        self,
        app,
        *,
        cache: RosterCache,
        secret: bytes,
        workspace_root: str = "",
    ) -> None:
        self.app = app
        self._cache = cache
        self._secret = secret
        self._workspace_root = str(Path(workspace_root).resolve()) if workspace_root else ""

    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            await self.app(scope, receive, send)
            return

        roster = self._cache.roster()
        if not roster.enabled:
            await self.app(scope, receive, send)
            return

        if scope.get("path", "") in EXEMPT_PATHS:
            await self.app(scope, receive, send)
            return

        principal = self._resolve_principal(scope, roster)
        if principal is None:
            await self._reject(scope, send)
            return

        scope[PRINCIPAL_SCOPE_KEY] = principal
        record_seen(principal)
        await self.app(scope, receive, send)

    # -- credential resolution ------------------------------------------

    def _resolve_principal(self, scope, roster) -> str | None:
        token = self._bearer_token(scope)
        if token:
            agent = roster.find_by_token(token)
            if agent is not None and self._workspace_allows(agent):
                return agent.name
            logger.warning("Rejecting unknown or out-of-scope bearer token from %s", scope.get("client"))
            return None

        raw = self._cookie(scope, COOKIE_NAME)
        if not raw:
            return None

        name = verify_session(raw, secret=self._secret)
        if name is None:
            return None

        # The cookie proves identity. The roster is authority: a principal
        # removed since the cookie was issued is refused here, which is what
        # makes "remove" an actual revocation.
        if roster.find(name) is None:
            logger.warning("Rejecting cookie for unknown principal %r", name)
            return None
        return name

    def _workspace_allows(self, agent) -> bool:
        """An agent with no ``workspace`` works anywhere; a scoped one only at home."""
        if not agent.workspace or not self._workspace_root:
            return not agent.workspace
        return str(Path(agent.workspace).resolve()) == self._workspace_root

    @staticmethod
    def _header(scope, name: bytes) -> str:
        for key, value in scope.get("headers", []):
            if key == name:
                return value.decode("latin-1")
        return ""

    def _bearer_token(self, scope) -> str:
        auth = self._header(scope, b"authorization")
        prefix = "Bearer "
        return auth[len(prefix) :].strip() if auth.startswith(prefix) else ""

    def _cookie(self, scope, name: str) -> str:
        raw = self._header(scope, b"cookie")
        for part in raw.split(";"):
            key, _, value = part.strip().partition("=")
            if key == name:
                return value
        return ""

    # -- rejection ------------------------------------------------------

    async def _reject(self, scope, send) -> None:
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return

        # A browser navigating to a page should land on the login form; anything
        # else (fetch, curl, an MCP client) gets a machine-readable 401 rather
        # than an HTML redirect it cannot follow usefully.
        accept = self._header(scope, b"accept")
        if scope.get("method") == "GET" and "text/html" in accept:
            await send(
                {
                    "type": "http.response.start",
                    "status": 303,
                    "headers": [(b"location", b"/login"), (b"content-length", b"0")],
                }
            )
            await send({"type": "http.response.body", "body": b""})
            return

        body = json.dumps({"error": "unauthorized"}).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/auth/test_gate.py -v`
Expected: PASS, 20 tests.

- [ ] **Step 6: Commit**

```bash
git add packages/haywire-studio/src/haywire_studio/auth/gate.py tests/auth/test_gate.py tests/auth/conftest.py
git commit -m "feat(auth): pure-ASGI gate accepting cookie or bearer on http and websocket"
```

---

### Task 3: Login routes

**Files:**
- Create: `packages/haywire-studio/src/haywire_studio/auth/login.py`
- Test: `tests/auth/test_login.py`

**Interfaces:**
- Consumes: Tasks 1–2, Slice 2's `authenticate`.
- Produces: `register_login_routes(*, cache: RosterCache, secret: bytes, app=None) -> None`, `login_page_html(error: str = "") -> str`, `LOGIN_FAILURE_DELAY_SECONDS = 1.0`.

- [ ] **Step 1: Write the failing test**

Create `tests/auth/test_login.py`:

```python
"""GET/POST /login — plain FastAPI, no NiceGUI, so the socket stays gated."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from haywire.core.access import AccessTier
from haywire_studio.auth import login as login_module
from haywire_studio.auth.cookies import COOKIE_NAME, verify_session
from haywire_studio.auth.live import RosterCache
from haywire_studio.auth.login import login_page_html, register_login_routes
from haywire_studio.auth.operations import add_user, enable_auth

SECRET = b"0" * 32
STRONG = "Correct-Horse9"


@pytest.fixture
def path(tmp_path):
    target = tmp_path / "auth.json"
    add_user("alice", STRONG, AccessTier.ADMIN, path=target)
    enable_auth("alice", STRONG, path=target)
    return target


@pytest.fixture
def client(path, monkeypatch):
    monkeypatch.setattr(login_module, "LOGIN_FAILURE_DELAY_SECONDS", 0.0)
    app = FastAPI()
    register_login_routes(cache=RosterCache(path), secret=SECRET, app=app)
    return TestClient(app)


def test_get_login_returns_html(client):
    response = client.get("/login")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "<form" in response.text


def test_login_page_is_self_contained(client):
    """No external hosts, no NiceGUI assets — the gate exempts only /login itself."""
    body = client.get("/login").text
    assert "http://" not in body.replace('action="/login"', "")
    assert "/_nicegui" not in body


def test_successful_post_sets_the_cookie_and_redirects(client):
    response = client.post(
        "/login", data={"username": "alice", "password": STRONG}, follow_redirects=False
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert verify_session(response.cookies[COOKIE_NAME], secret=SECRET) == "alice"


def test_cookie_is_httponly_samesite_lax_and_not_secure_over_http(client):
    response = client.post(
        "/login", data={"username": "alice", "password": STRONG}, follow_redirects=False
    )
    header = response.headers["set-cookie"]
    assert "HttpOnly" in header
    assert "SameSite=lax" in header.lower().replace("samesite=lax", "SameSite=lax")
    assert "Secure" not in header


def test_wrong_password_returns_401_html_with_no_cookie(client):
    response = client.post("/login", data={"username": "alice", "password": "nope"})
    assert response.status_code == 401
    assert COOKIE_NAME not in response.cookies
    assert "form" in response.text


def test_unknown_user_returns_401(client):
    response = client.post("/login", data={"username": "ghost", "password": STRONG})
    assert response.status_code == 401


def test_error_message_does_not_reveal_whether_the_user_exists(client):
    unknown = client.post("/login", data={"username": "ghost", "password": STRONG}).text
    wrong = client.post("/login", data={"username": "alice", "password": "nope"}).text
    assert unknown == wrong


def test_logout_clears_the_cookie(client):
    client.post("/login", data={"username": "alice", "password": STRONG})
    response = client.post("/logout", follow_redirects=False)
    assert response.status_code == 303
    assert "Max-Age=0" in response.headers["set-cookie"] or 'haywire_session=""' in response.headers[
        "set-cookie"
    ]


def test_html_escapes_the_error_text():
    assert "<script>" not in login_page_html("<script>alert(1)</script>")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/auth/test_login.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'haywire_studio.auth.login'`

- [ ] **Step 3: Write the implementation**

Create `packages/haywire-studio/src/haywire_studio/auth/login.py`:

```python
"""``GET /login`` and ``POST /login`` — plain FastAPI, deliberately not NiceGUI.

A NiceGUI login page would run its submit handler *server-side over the
websocket*, so unauthenticated clients would need ``/_nicegui_ws/`` open in
order to log in — the exact transport carrying the entire application. The
exemption would swallow the gate. Plain HTTP keeps the unauthenticated surface
to these two routes.

Consequence: this is the one place in the codebase that hardcodes colours
instead of using ``--hw-*`` tokens, because the theme system, ``hui`` and every
NiceGUI element only exist after the socket connects. The values below are
lifted from the dark workbench theme so the page does not look foreign.
"""

from __future__ import annotations

import asyncio
import html
import logging

from fastapi import Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from haywire_studio.auth.cookies import COOKIE_NAME, sign_session
from haywire_studio.auth.live import RosterCache
from haywire_studio.auth.operations import authenticate

logger = logging.getLogger(__name__)

#: Fixed delay on a failed attempt. A speed bump, not a defence — with the
#: password policy in force, online guessing is already infeasible, and account
#: lockout is a self-denial-of-service vector (anyone who can reach /login could
#: lock out the admin trying to fix a show).
LOGIN_FAILURE_DELAY_SECONDS = 1.0

#: Deliberately identical for "no such user" and "wrong password", so the page
#: cannot be used to enumerate the roster.
_GENERIC_ERROR = "Incorrect username or password."


def login_page_html(error: str = "") -> str:
    """The whole login page: one file, no external requests, no scripts."""
    banner = (
        f'<p class="error">{html.escape(error)}</p>' if error else ""
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Haywire — Sign in</title>
<style>
  :root {{ color-scheme: dark; }}
  body {{
    margin: 0; min-height: 100vh; display: grid; place-items: center;
    background: #17191c; color: #d8dbe0;
    font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  }}
  form {{
    background: #1e2126; border: 1px solid #2c3037; border-radius: 8px;
    padding: 2rem; width: min(22rem, 90vw); display: grid; gap: 1rem;
  }}
  h1 {{ margin: 0 0 .5rem; font-size: 1.25rem; font-weight: 600; }}
  label {{ display: grid; gap: .35rem; font-size: .8rem; color: #9aa0aa; }}
  input {{
    background: #14161a; border: 1px solid #2c3037; border-radius: 4px;
    padding: .55rem .7rem; color: #d8dbe0; font-size: .95rem;
  }}
  input:focus {{ outline: 2px solid #4a9eff; outline-offset: 0; }}
  button {{
    background: #4a9eff; border: 0; border-radius: 4px; padding: .6rem;
    color: #0d0f12; font-size: .95rem; font-weight: 600; cursor: pointer;
  }}
  .error {{ margin: 0; color: #ff6b6b; font-size: .85rem; }}
</style>
</head>
<body>
<form method="post" action="/login">
  <h1>Haywire</h1>
  {banner}
  <label>Username<input name="username" autocomplete="username" autofocus required></label>
  <label>Password<input name="password" type="password" autocomplete="current-password" required></label>
  <button type="submit">Sign in</button>
</form>
</body>
</html>
"""


def register_login_routes(*, cache: RosterCache, secret: bytes, app=None) -> None:
    """Register ``/login`` (GET, POST) and ``/logout`` (POST) on ``app``.

    ``app`` defaults to ``nicegui.app``; tests pass a bare FastAPI instance.
    """
    if app is None:
        from nicegui import app as nicegui_app

        app = nicegui_app

    @app.get("/login", response_class=HTMLResponse)
    async def _login_form() -> HTMLResponse:
        return HTMLResponse(login_page_html())

    @app.post("/login")
    async def _login_submit(
        request: Request,
        username: str = Form(""),
        password: str = Form(""),
    ):
        principal = authenticate(username, password, path=cache.path)
        if principal is None:
            logger.warning("Failed login for %r from %s", username, request.client)
            if LOGIN_FAILURE_DELAY_SECONDS:
                await asyncio.sleep(LOGIN_FAILURE_DELAY_SECONDS)
            return HTMLResponse(login_page_html(_GENERIC_ERROR), status_code=401)

        days = cache.roster().session_days
        response = RedirectResponse("/", status_code=303)
        response.set_cookie(
            COOKIE_NAME,
            sign_session(principal.name, secret=secret, days=days),
            max_age=None if days == 0 else days * 86400,
            httponly=True,
            samesite="lax",
            # Only under real TLS: an unconditional Secure flag would make the
            # cookie silently unusable on loopback HTTP, which is how the studio
            # is normally run.
            secure=request.url.scheme == "https",
            path="/",
        )
        return response

    @app.post("/logout")
    async def _logout():
        response = RedirectResponse("/login", status_code=303)
        response.delete_cookie(COOKIE_NAME, path="/")
        return response
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/auth/test_login.py -v`
Expected: PASS, 9 tests.

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-studio/src/haywire_studio/auth/login.py tests/auth/test_login.py
git commit -m "feat(auth): plain-HTTP login and logout routes"
```

---

### Task 4: Session eviction

**Files:**
- Create: `packages/haywire-studio/src/haywire_studio/auth/eviction.py`
- Test: `tests/auth/test_eviction.py`

**Interfaces:**
- Consumes: `SessionManager` from core.
- Produces: `evict_principal(session_manager, name: str) -> int`, `evict_all(session_manager) -> int`.

**Why push and not polling:** the gate runs once per websocket connection, so it cannot revoke an open socket. Removing a principal walks the live sessions and evicts theirs. Demotion needs no push at all — `ctx.can_edit()` reads live authority, so the next action already sees it.

- [ ] **Step 1: Write the failing test**

Create `tests/auth/test_eviction.py`:

```python
"""Push-based revocation for already-open sockets."""

from unittest.mock import MagicMock

from haywire_studio.auth.eviction import evict_all, evict_principal


def _session(principal):
    session = MagicMock()
    session.context.principal = principal
    return session


def _manager(sessions):
    manager = MagicMock()
    manager.active_sessions = sessions
    return manager


def test_evicts_only_the_named_principals_sessions():
    manager = _manager({"s1": _session("alice"), "s2": _session("bob")})
    assert evict_principal(manager, "alice") == 1
    manager.remove_session.assert_called_once_with("s1")


def test_evicts_every_session_of_one_principal():
    manager = _manager({"s1": _session("alice"), "s2": _session("alice")})
    assert evict_principal(manager, "alice") == 2
    assert manager.remove_session.call_count == 2


def test_unknown_principal_evicts_nothing():
    manager = _manager({"s1": _session("alice")})
    assert evict_principal(manager, "ghost") == 0
    manager.remove_session.assert_not_called()


def test_a_failing_session_does_not_abort_the_others():
    good, bad = _session("alice"), _session("alice")
    manager = _manager({"bad": bad, "good": good})
    manager.remove_session.side_effect = [RuntimeError("boom"), None]
    assert evict_principal(manager, "alice") == 1
    assert manager.remove_session.call_count == 2


def test_evict_all_removes_every_session():
    manager = _manager({"s1": _session("alice"), "s2": _session("bob"), "s3": _session(None)})
    assert evict_all(manager) == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/auth/test_eviction.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

Create `packages/haywire-studio/src/haywire_studio/auth/eviction.py`:

```python
"""Push-based revocation (ADR 0027).

A websocket is one ASGI scope, checked once at the handshake, so the gate
cannot revoke a socket it has already admitted. Removing a principal therefore
walks the live sessions and tears down theirs.

Demotion deliberately has no counterpart here: ``ctx.can_edit()`` reads live
authority, so a demoted principal's next action is already refused and the
affordances stop rendering on the next redraw. Evicting them would throw
someone out mid-work for a change that did not need it.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def evict_principal(session_manager, name: str) -> int:
    """Tear down every live session belonging to ``name``. Returns how many were evicted.

    Per-session failures are logged and skipped — one wedged session must not
    leave the rest of a removed principal's sessions alive.
    """
    victims = [
        session_id
        for session_id, session in list(session_manager.active_sessions.items())
        if getattr(session.context, "principal", None) == name
    ]

    evicted = 0
    for session_id in victims:
        try:
            session_manager.remove_session(session_id)
            evicted += 1
        except Exception:
            logger.warning("Failed to evict session %s for principal %r", session_id[:8], name, exc_info=True)

    if evicted:
        logger.info("Evicted %d session(s) for removed principal %r", evicted, name)
    return evicted


def evict_all(session_manager) -> int:
    """Tear down every live session — the "log everyone out" half of a secret rotation."""
    evicted = 0
    for session_id in list(session_manager.active_sessions.keys()):
        try:
            session_manager.remove_session(session_id)
            evicted += 1
        except Exception:
            logger.warning("Failed to evict session %s", session_id[:8], exc_info=True)
    return evicted
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/auth/test_eviction.py -v`
Expected: PASS, 5 tests.

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-studio/src/haywire_studio/auth/eviction.py tests/auth/test_eviction.py
git commit -m "feat(auth): push-based session eviction on principal removal"
```

---

### Task 5: TLS settings

**Files:**
- Modify: `packages/haywire-studio/src/haywire_studio/network/settings.py`
- Test: `tests/farmhand/test_network_settings_unit.py` (extend)

**Interfaces:**
- Produces: `NetworkSettings.ssl_certfile`, `NetworkSettings.ssl_keyfile` (both `STRING`, default `""`).

- [ ] **Step 1: Write the failing test**

Append to `tests/farmhand/test_network_settings_unit.py`:

```python
def test_tls_settings_default_to_empty():
    settings = NetworkSettings()
    assert settings.ssl_certfile == ""
    assert settings.ssl_keyfile == ""
```

- [ ] **Step 2: Run it**

Run: `uv run pytest tests/farmhand/test_network_settings_unit.py -v`
Expected: FAIL — `AttributeError: ssl_certfile`

- [ ] **Step 3: Add the settings**

Append to the `NetworkSettings` class body in `packages/haywire-studio/src/haywire_studio/network/settings.py`:

```python
    ssl_certfile = setting[STRING](
        "",
        label="TLS Certificate",
        description=(
            "Path to a TLS certificate file. Set together with the key to serve HTTPS "
            "directly — a self-signed pair is adequate on a LAN. Leave both empty for plain "
            "HTTP. Read once at startup; restart to apply."
        ),
        category="advanced",
    )
    ssl_keyfile = setting[STRING](
        "",
        label="TLS Private Key",
        description=(
            "Path to the private key matching the TLS certificate. Both must be set, or "
            "neither. Read once at startup; restart to apply."
        ),
        category="advanced",
    )
```

- [ ] **Step 4: Run it**

Run: `uv run pytest tests/farmhand/test_network_settings_unit.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-studio/src/haywire_studio/network/settings.py tests/farmhand/test_network_settings_unit.py
git commit -m "feat(network): add ssl_certfile/ssl_keyfile settings"
```

---

### Task 6: Wire the gate into `HaywireApp`

**Files:**
- Modify: `packages/haywire-studio/src/haywire_studio/app.py`
- Modify: `packages/haywire-studio/src/haywire_studio/farmhand/host.py`
- Test: `tests/auth/test_app_wiring.py`

**Interfaces:**
- Produces: `HaywireApp._install_auth(port: int) -> None`; `main_page(request: Request)` binding `ctx.principal`.

- [ ] **Step 1: Write the failing test**

Create `tests/auth/test_app_wiring.py`:

```python
"""HaywireApp wiring — gate installed only when the roster says so; TLS passthrough."""

import pytest

from haywire.core.access import AccessTier
from haywire_studio.auth.operations import add_user, enable_auth
from haywire_studio.auth.roster import Roster, save_roster

STRONG = "Correct-Horse9"


@pytest.fixture
def enabled(tmp_path):
    path = tmp_path / "auth.json"
    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    enable_auth("alice", STRONG, path=path)
    return path


@pytest.fixture
def disabled(tmp_path):
    path = tmp_path / "auth.json"
    save_roster(Roster(enabled=False), path)
    return path


def test_ssl_kwargs_empty_when_no_cert_configured():
    from haywire_studio.app import _ssl_kwargs

    assert _ssl_kwargs("", "") == {}


def test_ssl_kwargs_populated_when_both_set(tmp_path):
    from haywire_studio.app import _ssl_kwargs

    cert, key = tmp_path / "c.pem", tmp_path / "k.pem"
    cert.write_text("x")
    key.write_text("y")
    assert _ssl_kwargs(str(cert), str(key)) == {"ssl_certfile": str(cert), "ssl_keyfile": str(key)}


def test_ssl_kwargs_exits_when_only_one_is_set(tmp_path):
    from haywire_studio.app import _ssl_kwargs

    cert = tmp_path / "c.pem"
    cert.write_text("x")
    with pytest.raises(SystemExit):
        _ssl_kwargs(str(cert), "")


def test_ssl_kwargs_exits_when_a_file_is_missing(tmp_path):
    from haywire_studio.app import _ssl_kwargs

    with pytest.raises(SystemExit):
        _ssl_kwargs(str(tmp_path / "nope.pem"), str(tmp_path / "nope.key"))


def test_farmhand_origins_use_https_when_tls_is_on():
    from haywire_studio.farmhand.host import _origin_scheme

    assert _origin_scheme(tls=True) == "https"
    assert _origin_scheme(tls=False) == "http"
```

- [ ] **Step 2: Run it**

Run: `uv run pytest tests/auth/test_app_wiring.py -v`
Expected: FAIL — `ImportError: cannot import name '_ssl_kwargs'`

- [ ] **Step 3: Add `_ssl_kwargs` to `app.py`**

Add near the bottom of `packages/haywire-studio/src/haywire_studio/app.py`, before `run_app`:

```python
def _ssl_kwargs(certfile: str, keyfile: str) -> dict[str, str]:
    """Build the uvicorn TLS kwargs, or exit with a clear message.

    NiceGUI's ``ui.run(**kwargs)`` forwards these to uvicorn and recognises the
    pair explicitly — it uses them to build the ``https://`` URL for the
    ``show=True`` auto-open browser. So HTTPS needs no patching, only a
    passthrough.

    Exactly one of the pair is always a misconfiguration: silently serving plain
    HTTP when the operator believes TLS is on would leak every session cookie on
    the wire. Fail loudly at startup instead, matching ``_install_ip_allowlist``.
    """
    if not certfile and not keyfile:
        return {}

    if bool(certfile) != bool(keyfile):
        print(
            "ERROR: Haywire cannot start — incomplete TLS configuration.\n"
            "  Set BOTH 'ssl_certfile' and 'ssl_keyfile' under Network settings, or neither."
        )
        raise SystemExit(1)

    for label, value in (("ssl_certfile", certfile), ("ssl_keyfile", keyfile)):
        if not Path(value).is_file():
            print(f"ERROR: Haywire cannot start — {label} does not point at a file: {value}")
            raise SystemExit(1)

    return {"ssl_certfile": certfile, "ssl_keyfile": keyfile}
```

- [ ] **Step 4: Add `_origin_scheme` to `farmhand/host.py`**

Add at module level in `packages/haywire-studio/src/haywire_studio/farmhand/host.py`:

```python
def _origin_scheme(*, tls: bool) -> str:
    """The scheme the MCP DNS-rebinding check should expect for its own origin.

    ``allowed_origins`` used to hardcode ``http://``. Under TLS that makes /mcp
    reject its own origin, because the browser or client sends ``https://``.
    """
    return "https" if tls else "http"
```

Then in `mount()`, replace the hardcoded origin construction. Change the signature to accept the flag:

```python
    def mount(self, port: int, app_target: Any = None, *, tls: bool = False) -> None:
```

and inside the `restrict_to_loopback` branch, replace:

```python
            allowed_origins = [f"http://127.0.0.1:{port}", f"http://localhost:{port}"]
```

with:

```python
            scheme = _origin_scheme(tls=tls)
            allowed_origins = [f"{scheme}://127.0.0.1:{port}", f"{scheme}://localhost:{port}"]
```

Leave the `public_hostname` block adding both `http://` and `https://` forms as it is — it already covers both because a fronting proxy's scheme is unknowable from here.

- [ ] **Step 5: Add `_install_auth` to `HaywireApp`**

Add as a method on `HaywireApp` in `packages/haywire-studio/src/haywire_studio/app.py`:

```python
    def _install_auth(self) -> bool:
        """Install the gate, the login routes and the tier resolver, if enabled.

        Returns whether authentication is on. Everything here is skipped when the
        roster says disabled, so an auth-off install runs exactly the code it ran
        before this feature existed.
        """
        from nicegui import app as nicegui_app

        from haywire_studio.auth.cookies import load_or_create_secret
        from haywire_studio.auth.gate import AuthGateMiddleware
        from haywire_studio.auth.live import RosterCache, install_resolver
        from haywire_studio.auth.login import register_login_routes
        from haywire_studio.auth.roster import RosterError

        cache = RosterCache()
        try:
            roster = cache.roster()
        except RosterError as exc:
            print(f"ERROR: Haywire cannot start — the roster is unreadable.\n  {exc}")
            raise SystemExit(1) from exc

        if not roster.enabled:
            return False

        if not roster.admins():
            print(
                "ERROR: Haywire cannot start — authentication is enabled but no admin exists.\n"
                "  Run 'haywire auth disable', add an admin with 'haywire user add <name> "
                "--tier admin', then 'haywire auth enable'."
            )
            raise SystemExit(1)

        secret = load_or_create_secret()
        install_resolver(cache)
        register_login_routes(cache=cache, secret=secret)
        nicegui_app.add_middleware(
            AuthGateMiddleware,
            cache=cache,
            secret=secret,
            workspace_root=self.workspace_root,
        )
        self._auth_cache = cache
        print(f"🔒 Authentication enabled — {len(roster.principals)} principal(s)")
        return True
```

- [ ] **Step 6: Call it from `run()` and pass TLS through**

In `HaywireApp.run()`, replace the body between `settings = NetworkSettings()` and `ui.run(...)` with:

```python
        settings = NetworkSettings()
        port = settings.port
        host = "0.0.0.0" if settings.expose_to_network else "127.0.0.1"
        ssl_kwargs = _ssl_kwargs(settings.ssl_certfile, settings.ssl_keyfile)

        # Install the gate BEFORE the Farmhand mount so the root wrapper covers
        # /mcp too — one boundary, not a boundary with a documented hole beside it.
        auth_enabled = self._install_auth()

        self.setup_farmhand(port, tls=bool(ssl_kwargs))

        if settings.expose_to_network:
            self._install_ip_allowlist(settings)
            if not auth_enabled:
                logger.warning(
                    "Network: the studio is exposed beyond loopback with authentication OFF. "
                    "Anyone who can reach it is a full operator. Run 'haywire auth enable' to "
                    "require a login."
                )
            if not ssl_kwargs:
                logger.warning(
                    "Network: serving plain HTTP beyond loopback — session cookies and "
                    "passwords travel unencrypted and a captured cookie is a valid cookie. "
                    "Set ssl_certfile/ssl_keyfile, or terminate TLS at a reverse proxy."
                )

        try:
            ui.run(
                host=host,
                port=port,
                show=open_browser,
                title="Haywire",
                reload=False,
                **ssl_kwargs,
            )
```

And update `setup_farmhand` to accept and forward the flag:

```python
    def setup_farmhand(self, port: int, *, tls: bool = False) -> None:
        """Mount the Farmhand MCP server if enabled (flag read once; restart to apply)."""
        from haywire_studio.farmhand.host import FarmhandHost
        from haywire_studio.farmhand.settings import FarmhandSettings

        if not FarmhandSettings().enabled:
            logging.getLogger(__name__).info("Farmhand: disabled by settings (farmhand.enabled = false)")
            return
        self.farmhand_host = FarmhandHost(self.library_service, self.workspace_root)
        self.farmhand_host.mount(port, tls=tls)
```

- [ ] **Step 7: Bind the principal onto `SessionContext`**

In `create_ui()`, give the page handler a `request` parameter and set `principal` right after the session is created:

```python
    def create_ui(self):
        """Register NiceGUI page routes."""

        @ui.page("/", title="Haywire")
        def main_page(request: Request):
            from haywire.ui.app.shell import AppShell
            from haywire.ui.editor.registry import EditorTypeRegistry
            from nicegui import context

            print(f"Creating UI for session: {context.client.id[:8]}")

            editor_registry = self.library_service.injector.get(EditorTypeRegistry)

            haywire_session = self.session_manager.create_session(
                project_state=self,
                workspace_manager=self.workspace_manager,
            )

            # The gate already verified the credential and stashed the principal
            # on the ASGI scope; `request.scope` IS that same dict. None means
            # authentication is off, which resolves to ADMIN.
            haywire_session.context.principal = request.scope.get(PRINCIPAL_SCOPE_KEY)
```

Add the imports at the top of `app.py`:

```python
from fastapi import Request

from haywire_studio.auth.gate import PRINCIPAL_SCOPE_KEY
```

- [ ] **Step 8: Run the wiring test**

Run: `uv run pytest tests/auth/test_app_wiring.py -v`
Expected: PASS, 5 tests.

- [ ] **Step 9: Run the Farmhand suite — `mount()` changed signature**

Run: `uv run pytest tests/farmhand/ -v`
Expected: PASS. `tls` is keyword-only with a default, so existing call sites are unaffected; if any test asserts on `allowed_origins`, confirm it still expects `http://`.

- [ ] **Step 10: Commit**

```bash
git add packages/haywire-studio/src/haywire_studio/app.py packages/haywire-studio/src/haywire_studio/farmhand/host.py tests/auth/test_app_wiring.py
git commit -m "feat(auth): install gate, login routes and resolver in HaywireApp; TLS passthrough"
```

---

### Task 7: End-to-end smoke test

**Files:**
- Test: `tests/auth/test_end_to_end.py`

- [ ] **Step 1: Write the test**

```python
"""The whole gate, end to end, against a real ASGI app."""

import pytest
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from fastapi.testclient import TestClient

from haywire.core.access import AccessTier
from haywire_studio.auth import login as login_module
from haywire_studio.auth.gate import AuthGateMiddleware
from haywire_studio.auth.live import RosterCache
from haywire_studio.auth.login import register_login_routes
from haywire_studio.auth.operations import add_user, enable_auth

SECRET = b"0" * 32
STRONG = "Correct-Horse9"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(login_module, "LOGIN_FAILURE_DELAY_SECONDS", 0.0)
    path = tmp_path / "auth.json"
    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    enable_auth("alice", STRONG, path=path)

    app = FastAPI()

    @app.get("/")
    async def _index():
        return PlainTextResponse("studio")

    cache = RosterCache(path)
    register_login_routes(cache=cache, secret=SECRET, app=app)
    app.add_middleware(AuthGateMiddleware, cache=cache, secret=SECRET)
    return TestClient(app), path


def test_anonymous_navigation_redirects_to_login(client):
    api, _ = client
    response = api.get("/", headers={"accept": "text/html"}, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_login_then_reach_the_studio(client):
    api, _ = client
    api.post("/login", data={"username": "alice", "password": STRONG})
    assert api.get("/").text == "studio"


def test_removing_the_principal_locks_out_an_existing_cookie(client):
    api, path = client
    api.post("/login", data={"username": "alice", "password": STRONG})
    assert api.get("/").status_code == 200

    from haywire_studio.auth.operations import add_user as add, remove_principal

    add("root", STRONG + "z", AccessTier.ADMIN, path=path)
    remove_principal("alice", path=path)

    response = api.get("/", headers={"accept": "text/html"}, follow_redirects=False)
    assert response.status_code == 303


def test_logout_then_locked_out(client):
    api, _ = client
    api.post("/login", data={"username": "alice", "password": STRONG})
    api.post("/logout")
    response = api.get("/", headers={"accept": "text/html"}, follow_redirects=False)
    assert response.status_code == 303
```

- [ ] **Step 2: Run it**

Run: `uv run pytest tests/auth/test_end_to_end.py -v`
Expected: PASS, 4 tests.

- [ ] **Step 3: Commit**

```bash
git add tests/auth/test_end_to_end.py
git commit -m "test(auth): end-to-end gate, login, revocation"
```

---

### Task 8: Manual verification

- [ ] **Step 1: Confirm auth-off is unchanged**

```bash
uv run haywire --no-browser
```

Expected: starts normally, no `🔒` banner, `http://127.0.0.1:8124/` loads the studio with no login. Quit.

- [ ] **Step 2: Enable auth and confirm the gate**

```bash
uv run haywire user add tester --tier admin      # enter a policy-compliant password
uv run haywire auth enable                        # enter tester + that password
uv run haywire --no-browser
```

Then, in a second terminal:

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8124/
curl -s -o /dev/null -w "%{http_code}\n" -H "Accept: text/html" http://127.0.0.1:8124/
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8124/login
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://127.0.0.1:8124/api/code-intel/hover
```

Expected: `401`, `303`, `200`, `401`.

- [ ] **Step 3: Confirm the browser flow**

Open `http://127.0.0.1:8124/` — expect the login page, sign in, expect the studio. Confirm the websocket connects (the UI is interactive, not a frozen shell).

- [ ] **Step 4: Restore your machine**

```bash
uv run haywire auth disable
```

- [ ] **Step 5: Record anything that did not behave as described** in the Drift Log.

---

### Task 9: Quality gate

- [ ] **Step 1:** `uv run ruff check . && uv run ruff format --check .`
- [ ] **Step 2:** full mypy command from CLAUDE.md
- [ ] **Step 3:**

```bash
uv run pytest -m "not browser and not perf" -q > /tmp/slice3.log 2>&1; echo "exit=$?"
grep -E "^FAILED|^ERROR" /tmp/slice3.log
```

- [ ] **Step 4:** browser tests, since `main_page` changed signature

```bash
uv run pytest tests/ui/harness/ -q > /tmp/slice3-browser.log 2>&1; echo "exit=$?"
```

- [ ] **Step 5:** commit fixes

---

### Task 10 (final): Record delivery and drift

- [ ] **Step 1: Fill in the Drift Log** — one line per deviation, or "No drift." explicitly.
- [ ] **Step 2: Record in Delivered** the exact names Slice 4 needs: `PRINCIPAL_SCOPE_KEY`, `last_seen()`, `record_seen()`, `evict_principal()`, and confirmation that `ctx.principal` is populated.
- [ ] **Step 3: Flip `status:` to `implemented`.**
- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/plans/2026-08-15-auth-3-gate-login.md
git commit -m "docs(plan): slice 3 complete — gate and login"
```

---

## Delivered

*(Filled in by the final task.)*

## Drift Log

*(Filled in by the final task. One line per deviation, or the words "No drift.")*
