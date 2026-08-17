"""The gate — pure-ASGI, cookie OR bearer, http AND websocket."""

import pytest

from haywire.core.access import AccessTier
from haywire_studio.auth.cookies import COOKIE_NAME, sign_session
from haywire_studio.auth.gate import PRINCIPAL_SCOPE_KEY, AuthGateMiddleware
from haywire_studio.auth.live import RosterCache
from haywire_studio.auth.operations import add_agent, add_user, enable_auth
from haywire_studio.security.document import SecurityDocument, save_document
from haywire_studio.security.roster import Roster

SECRET = b"0" * 32
STRONG = "Correct-Horse9"


@pytest.fixture
def path(tmp_path):
    return tmp_path / "security.json"


@pytest.fixture
def enabled_roster(path):
    add_user("alice", STRONG, AccessTier.ADMIN, path=path)
    enable_auth("alice", STRONG, path=path)
    return path


class _Recorder:
    """Inner ASGI app that records whether it was reached and with what scope."""

    def __init__(self):
        self.reached = False
        self.scope: dict | None = None

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
    save_document(SecurityDocument(auth=Roster(enabled=False)), path)
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
@pytest.mark.parametrize(
    "route", ["/", "/_nicegui_ws/", "/_nicegui/3.13.0/static/x.js", "/api/code-intel/hover"]
)
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
    assert inner.scope is not None
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


@pytest.mark.anyio
async def test_session_cookie_is_found_across_multiple_cookie_headers(enabled_roster):
    """HTTP/2 (RFC 9113 §8.2.3) and some proxies may split Cookie across
    several header lines; a single-header read would silently drop the
    session cookie whenever it isn't first."""
    inner = _Recorder()
    cookie = f"{COOKIE_NAME}={sign_session('alice', secret=SECRET, days=30)}"
    headers = [(b"cookie", b"unrelated=1"), (b"cookie", cookie.encode())]
    await _call(_gate(enabled_roster, inner), _http("/", headers))
    assert inner.reached is True
    assert inner.scope is not None
    assert inner.scope[PRINCIPAL_SCOPE_KEY] == "alice"


# --- bearer -----------------------------------------------------------


@pytest.mark.anyio
async def test_valid_bearer_token_admits(enabled_roster):
    agent = add_agent("builder", AccessTier.EDIT, path=enabled_roster)
    inner = _Recorder()
    headers = [(b"authorization", f"Bearer {agent.token}".encode())]
    await _call(_gate(enabled_roster, inner), _http("/mcp", headers))
    assert inner.reached is True
    assert inner.scope is not None
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


@pytest.mark.anyio
async def test_bad_bearer_token_falls_back_to_a_valid_cookie(enabled_roster):
    """An explicit-but-wrong bearer token must not shadow a valid cookie —
    only a bad credential with nothing else to fall back on is a hard reject."""
    inner = _Recorder()
    cookie = f"{COOKIE_NAME}={sign_session('alice', secret=SECRET, days=30)}"
    headers = [(b"authorization", b"Bearer nope"), (b"cookie", cookie.encode())]
    await _call(_gate(enabled_roster, inner), _http("/", headers))
    assert inner.reached is True
    assert inner.scope is not None
    assert inner.scope[PRINCIPAL_SCOPE_KEY] == "alice"


@pytest.mark.anyio
async def test_bad_bearer_token_with_no_cookie_is_still_rejected(enabled_roster):
    inner = _Recorder()
    headers = [(b"authorization", b"Bearer nope")]
    await _call(_gate(enabled_roster, inner), _http("/", headers))
    assert inner.reached is False


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
