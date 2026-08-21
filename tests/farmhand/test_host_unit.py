"""Host mechanics that need no transport: capability advertisement, tool table, error format."""

from typing import Any, cast

import pytest

from haywire.core.farmhand import FarmhandError
from haywire.core.signals import (
    AgentConnected,
    GraphDataMutated,
    RosterChanged,
    SignalDispatcher,
    SignalPeer,
)
from haywire_studio.farmhand.host import FarmhandHost, _FarmhandServer, _format_tool_error
from haywire_studio.security.document import SecurityDocument

pytestmark = pytest.mark.unit


def test_initialization_options_advertise_tools_list_changed():
    # A capability is only present once its handler is registered (SDK gates on
    # request_handlers), so register the tools handler the way the host does.
    server = _FarmhandServer("farmhand")

    @server.list_tools()
    async def _list_tools():
        return []

    options = server.create_initialization_options()
    assert options.capabilities.tools.listChanged is True
    # resources/prompts capabilities appear once their handlers are registered
    # (resources: Task 14). The NotificationOptions carry the listChanged flags
    # so those capabilities advertise True as soon as the handler is added.


def test_format_tool_error_stable_code_no_traceback():
    err = FarmhandError("graph_not_found", "No open graph 'x'", ids={"binding_id": "x"})
    text = _format_tool_error(err)
    assert "[graph_not_found]" in text
    assert "No open graph 'x'" in text
    assert "binding_id=x" in text
    assert "Traceback" not in text


def test_format_tool_error_appends_help_line_when_present():
    err = FarmhandError(
        "graph_not_found",
        "No open graph 'x'",
        ids={"binding_id": "x"},
        help="Run haystack_list_graphs to see open graphs.",
    )
    text = _format_tool_error(err)
    # The [code] prefix is unchanged, so clients matching on it keep working.
    assert "[graph_not_found]" in text
    # The hint lands on its own line, greppable without parsing the prose.
    assert "\nhelp: Run haystack_list_graphs to see open graphs." in text


def test_format_tool_error_omits_help_line_when_absent():
    err = FarmhandError("save_failed", "Saving failed")
    text = _format_tool_error(err)
    assert "help:" not in text


def test_format_tool_error_wraps_unexpected_exceptions():
    text = _format_tool_error(ValueError("boom"))
    assert "[internal]" in text
    assert "boom" in text
    assert "Traceback" not in text


def test_tool_table_seed_and_evict():
    from haywire.core.farmhand import Farmhand, FarmhandRegistry, ToolAnnotations
    from haywire.core.farmhand.identity import FarmhandIdentity
    from haywire.core.library.identity import LibraryIdentity

    registry = FarmhandRegistry()

    class PingTool(Farmhand):
        async def run(self, ctx) -> dict:
            return {}

    PingTool.class_identity = FarmhandIdentity(
        registry_id="ping",
        registry_key="haybale-studio:farmhand:ping",
        label="Ping",
        description="",
        instructions="Ping.",
        class_name="PingTool",
        module=__name__,
        annotations=ToolAnnotations(),
    )
    PingTool.class_library = LibraryIdentity(
        label="Studio",
        version="0.1",
        folder_path="/tmp/studio",
        module_name="studio",
        name="haybale-studio",
    )
    registry._register_class(PingTool, PingTool.class_library)

    host = FarmhandHost.__new__(FarmhandHost)  # table mechanics only, no service needed
    host._tools = {}
    host._registry = registry
    host._seed_tools()
    assert host._tools == {"haybale-studio_ping": PingTool}

    host._remove_tool_by_key("haybale-studio:farmhand:ping")
    assert host._tools == {}


# ----------------------------------------------------------------------
# Roster freshness — signal-driven, replacing the old per-request stat-poll
# ----------------------------------------------------------------------


def _peer_host(dispatcher):
    """A FarmhandHost with only its peer half initialised.

    ``__new__`` skips the MCP/registry construction these tests do not need.
    """
    from haywire.core.signals import SignalPeer

    host = FarmhandHost.__new__(FarmhandHost)
    SignalPeer.__init__(host, dispatcher)
    host._loop = None
    host._known_principals = set()
    host.subscribe(RosterChanged, host._on_roster_changed)
    return host


def test_host_registers_itself_as_a_peer():
    dispatcher = SignalDispatcher()
    host = _peer_host(dispatcher)

    assert dispatcher.peers[host.peer_id] is host


def test_roster_changed_notifies_clients(monkeypatch):
    """A tier edit reaches the host with no agent traffic required."""
    dispatcher = SignalDispatcher()
    host = _peer_host(dispatcher)

    scheduled = []

    class _Loop:
        def is_running(self):
            return True

        def call_soon_threadsafe(self, fn):
            scheduled.append(fn)

    host._loop = _Loop()

    dispatcher.broadcast(RosterChanged())

    assert len(scheduled) == 1, "expected the notify to be marshalled onto the loop"


def test_roster_changed_before_the_loop_exists_is_a_noop():
    """No running loop means no connected client to notify."""
    dispatcher = SignalDispatcher()
    host = _peer_host(dispatcher)
    host._loop = None

    dispatcher.broadcast(RosterChanged())  # must not raise


def test_unrelated_signals_do_not_notify():
    """Exact-class bus dispatch — the host reacts to RosterChanged only."""
    dispatcher = SignalDispatcher()
    host = _peer_host(dispatcher)

    class _Loop:
        def is_running(self):
            return True

        def call_soon_threadsafe(self, fn):
            raise AssertionError("should not notify for an unrelated signal")

    host._loop = _Loop()

    dispatcher.broadcast(GraphDataMutated())


# ----------------------------------------------------------------------
# Agent presence
# ----------------------------------------------------------------------


def test_announce_principal_publishes_once_per_principal(monkeypatch):
    """Fires on first sight, not per request."""
    dispatcher = SignalDispatcher()
    host = _peer_host(dispatcher)
    observer = SignalPeer(dispatcher)

    seen: list[AgentConnected] = []
    observer.subscribe(AgentConnected, seen.append)

    monkeypatch.setattr(host, "_caller_principal", lambda: "scout")
    host._announce_principal()
    host._announce_principal()
    host._announce_principal()

    assert [s.principal for s in seen] == ["scout"]


def test_announce_principal_publishes_per_distinct_principal(monkeypatch):
    dispatcher = SignalDispatcher()
    host = _peer_host(dispatcher)
    observer = SignalPeer(dispatcher)

    seen: list[AgentConnected] = []
    observer.subscribe(AgentConnected, seen.append)

    for name in ("scout", "harvester", "scout"):
        monkeypatch.setattr(host, "_caller_principal", lambda n=name: n)
        host._announce_principal()

    assert [s.principal for s in seen] == ["scout", "harvester"]


def test_announce_principal_is_silent_when_auth_is_off(monkeypatch):
    """No principal to name, so nothing is announced."""
    dispatcher = SignalDispatcher()
    host = _peer_host(dispatcher)
    observer = SignalPeer(dispatcher)

    seen: list[AgentConnected] = []
    observer.subscribe(AgentConnected, seen.append)

    monkeypatch.setattr(host, "_caller_principal", lambda: None)
    host._announce_principal()

    assert seen == []


def test_announce_principal_never_raises_into_a_tool_call(monkeypatch):
    """Presence bookkeeping must not fail a working tool call."""
    dispatcher = SignalDispatcher()
    host = _peer_host(dispatcher)

    monkeypatch.setattr(host, "_caller_principal", lambda: "scout")

    def _boom(_signal):
        raise RuntimeError("subscriber exploded")

    SignalPeer(dispatcher).subscribe(AgentConnected, _boom)

    host._announce_principal()  # must not raise


class _FakeAppTarget:
    """Records what mount() wires up, without needing a real FastAPI/NiceGUI app."""

    def __init__(self):
        self.mounted: dict[str, object] = {}

    def mount(self, path: str, app) -> None:
        self.mounted[path] = app


def _bare_host(tmp_path) -> FarmhandHost:
    host = FarmhandHost.__new__(FarmhandHost)
    host._workspace_root = str(tmp_path)
    host._server = _FarmhandServer("farmhand")
    return host


def test_mount_installs_no_bearer_middleware(tmp_path):
    """ADR 0028: the root AuthGateMiddleware is the only credential check; mount()
    wires the bare ASGI app straight in, with nothing wrapping it."""
    host = _bare_host(tmp_path)
    target = _FakeAppTarget()
    document = SecurityDocument()
    host.mount(8082, document, app_target=target)
    mounted = target.mounted["/mcp"]
    assert mounted.__class__.__name__ != "BearerTokenMiddleware"
    assert not hasattr(mounted, "token")
    # No token file generated at all — nothing written under .haywire/.
    assert not (tmp_path / ".haywire" / "farmhand_token").exists()


def test_mount_disables_dns_rebinding_protection_when_loopback_unrestricted(tmp_path):
    host = _bare_host(tmp_path)
    target = _FakeAppTarget()
    document = SecurityDocument()
    document.farmhand.restrict_to_loopback = False
    host.mount(8082, document, app_target=target)
    assert cast(Any, host._session_manager).security_settings.enable_dns_rebinding_protection is False


def test_mount_keeps_dns_rebinding_protection_by_default(tmp_path):
    host = _bare_host(tmp_path)
    target = _FakeAppTarget()
    document = SecurityDocument()
    document.farmhand.restrict_to_loopback = True
    document.network.public_hostname = ""
    host.mount(8082, document, app_target=target)
    security = cast(Any, host._session_manager).security_settings
    assert security.enable_dns_rebinding_protection is True
    assert "127.0.0.1:8082" in security.allowed_hosts
    # Regression guard: empty public_hostname (default) must produce
    # byte-identical allowed_hosts/allowed_origins to the shipped behavior —
    # no extra entries leak in.
    assert security.allowed_hosts == ["127.0.0.1:8082", "localhost:8082", "127.0.0.1", "localhost"]
    assert security.allowed_origins == ["http://127.0.0.1:8082", "http://localhost:8082"]


def test_mount_extends_allowed_hosts_and_origins_with_public_hostname(tmp_path):
    host = _bare_host(tmp_path)
    target = _FakeAppTarget()
    document = SecurityDocument()
    document.farmhand.restrict_to_loopback = True
    document.network.public_hostname = "haywire.example.com"
    host.mount(8082, document, app_target=target)
    security = cast(Any, host._session_manager).security_settings
    # Existing loopback entries are untouched.
    assert security.allowed_hosts[:4] == ["127.0.0.1:8082", "localhost:8082", "127.0.0.1", "localhost"]
    # Bare hostname (no port given) gets both bare and port-qualified forms,
    # matching the dual-form convention used for the loopback entries.
    assert "haywire.example.com" in security.allowed_hosts
    assert "haywire.example.com:8082" in security.allowed_hosts
    # Both schemes allowed since this module can't know which the proxy terminates as.
    assert "http://haywire.example.com" in security.allowed_origins
    assert "https://haywire.example.com" in security.allowed_origins


def test_mount_public_hostname_with_explicit_port_not_doubled_up(tmp_path):
    host = _bare_host(tmp_path)
    target = _FakeAppTarget()
    document = SecurityDocument()
    document.farmhand.restrict_to_loopback = True
    document.network.public_hostname = "haywire.example.com:443"
    host.mount(8082, document, app_target=target)
    security = cast(Any, host._session_manager).security_settings
    assert "haywire.example.com:443" in security.allowed_hosts
    # No extra port-appended duplicate since the hostname already carries one.
    assert "haywire.example.com:443:8082" not in security.allowed_hosts
    assert security.allowed_hosts.count("haywire.example.com:443") == 1
    assert "http://haywire.example.com:443" in security.allowed_origins
    assert "https://haywire.example.com:443" in security.allowed_origins


def test_mount_public_hostname_ignored_when_loopback_unrestricted(tmp_path):
    host = _bare_host(tmp_path)
    target = _FakeAppTarget()
    document = SecurityDocument()
    document.farmhand.restrict_to_loopback = False
    document.network.public_hostname = "haywire.example.com"
    host.mount(8082, document, app_target=target)
    security = cast(Any, host._session_manager).security_settings
    assert security.enable_dns_rebinding_protection is False
    # public_hostname has no effect on this branch — DNS-rebinding protection
    # is off entirely, so there's nothing to extend.
    assert security.allowed_hosts == []
    assert security.allowed_origins == []


def test_connection_hint_returns_plain_command_when_auth_disabled(tmp_path):
    document = SecurityDocument()
    document.auth.enabled = False
    hint = FarmhandHost._connection_hint(8082, document, tls=False)
    assert hint == "claude mcp add --transport http farmhand http://127.0.0.1:8082/mcp"


def test_connection_hint_names_first_agent_token_when_auth_enabled(tmp_path):
    from haywire.core.access import AccessTier
    from haywire_studio.security.roster import Principal

    document = SecurityDocument()
    document.auth.enabled = True
    document.auth.principals.append(Principal(name="alice", kind="user", tier=AccessTier.ADMIN))
    document.auth.principals.append(
        Principal(name="bot", kind="agent", tier=AccessTier.EDIT, token="agenttoken")
    )
    hint = FarmhandHost._connection_hint(8082, document, tls=False)
    assert "agenttoken" in hint


def test_connection_hint_explains_missing_agent_when_auth_enabled(tmp_path):
    document = SecurityDocument()
    document.auth.enabled = True
    hint = FarmhandHost._connection_hint(8082, document, tls=False)
    assert "no agent principal exists" in hint
