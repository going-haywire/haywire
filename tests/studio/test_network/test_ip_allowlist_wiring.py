"""HaywireApp._install_ip_allowlist: wiring IPAllowlistMiddleware into the
root ASGI app (Task 2b).

Covers:
  - middleware only installed when expose_to_network is on
  - invalid CIDR at startup refuses to start (SystemExit), not a silent skip
  - proxy warning fires only when expose_to_network is on and trusted_proxies
    is empty
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from haywire_studio.app import HaywireApp
from haywire_studio.network.ip_filter import IPAllowlistMiddleware

pytestmark = pytest.mark.unit


def _settings(
    *,
    expose_to_network: bool = True,
    allowed_remote_ranges: str = "",
    trusted_proxies: str = "",
    port: int = 8124,
):
    return SimpleNamespace(
        port=port,
        expose_to_network=expose_to_network,
        allowed_remote_ranges=allowed_remote_ranges,
        trusted_proxies=trusted_proxies,
    )


# --- installed only when expose_to_network is on --------------------------


def test_install_ip_allowlist_calls_add_middleware_with_parsed_ranges():
    settings = _settings(
        allowed_remote_ranges="192.168.1.0/24, 10.0.0.0/8",
        trusted_proxies="172.16.0.0/12",
    )

    with patch("haywire_studio.app.app") as mock_app:
        HaywireApp._install_ip_allowlist(settings)

    mock_app.add_middleware.assert_called_once_with(
        IPAllowlistMiddleware,
        allowed_ranges=["192.168.1.0/24", "10.0.0.0/8"],
        trusted_proxies=["172.16.0.0/12"],
    )


def test_run_installs_middleware_only_when_expose_to_network_true(monkeypatch):
    """Drive through run() itself (not just the helper) so the conditional
    gate in run() is exercised, not only _install_ip_allowlist's own logic."""
    instance = HaywireApp.__new__(HaywireApp)
    instance._is_shutting_down = True  # skip cleanup() path

    monkeypatch.setattr(instance, "create_ui", lambda: None)
    monkeypatch.setattr(instance, "setup_farmhand", lambda port: None)

    install_calls = []
    monkeypatch.setattr(
        HaywireApp, "_install_ip_allowlist", staticmethod(lambda settings: install_calls.append(settings))
    )

    with (
        patch("haywire_studio.network.settings.NetworkSettings") as MockSettings,
        patch("haywire_studio.app.ui") as mock_ui,
    ):
        MockSettings.return_value = _settings(expose_to_network=True)
        instance.run(open_browser=False)

    assert len(install_calls) == 1
    mock_ui.run.assert_called_once()
    assert mock_ui.run.call_args.kwargs["host"] == "0.0.0.0"


def test_run_skips_middleware_install_when_expose_to_network_false(monkeypatch):
    instance = HaywireApp.__new__(HaywireApp)
    instance._is_shutting_down = True

    monkeypatch.setattr(instance, "create_ui", lambda: None)
    monkeypatch.setattr(instance, "setup_farmhand", lambda port: None)

    install_calls = []
    monkeypatch.setattr(
        HaywireApp, "_install_ip_allowlist", staticmethod(lambda settings: install_calls.append(settings))
    )

    with (
        patch("haywire_studio.network.settings.NetworkSettings") as MockSettings,
        patch("haywire_studio.app.ui") as mock_ui,
    ):
        MockSettings.return_value = _settings(expose_to_network=False)
        instance.run(open_browser=False)

    assert install_calls == []
    mock_ui.run.assert_called_once()
    assert mock_ui.run.call_args.kwargs["host"] == "127.0.0.1"


# --- invalid CIDR refuses to start -----------------------------------------


def test_invalid_cidr_in_allowed_ranges_raises_system_exit(capsys):
    settings = _settings(allowed_remote_ranges="not-a-cidr")

    with patch("haywire_studio.app.app") as mock_app:
        with pytest.raises(SystemExit) as exc_info:
            HaywireApp._install_ip_allowlist(settings)
        # Must never install a middleware after a failed validation — that
        # would be a fail-open bug even if the exception below made the
        # error visible.
        mock_app.add_middleware.assert_not_called()

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "ERROR" in captured.out
    assert "network settings" in captured.out.lower()


def test_invalid_cidr_in_trusted_proxies_raises_system_exit():
    settings = _settings(trusted_proxies="also-not-a-cidr")

    with patch("haywire_studio.app.app") as mock_app:
        with pytest.raises(SystemExit):
            HaywireApp._install_ip_allowlist(settings)
        mock_app.add_middleware.assert_not_called()


def test_invalid_cidr_does_not_raise_raw_value_error():
    """The ValueError from the constructor must be caught and converted —
    never surface as a raw, unhandled traceback to the operator."""
    settings = _settings(allowed_remote_ranges="not-a-cidr")

    with patch("haywire_studio.app.app"):
        try:
            HaywireApp._install_ip_allowlist(settings)
            pytest.fail("expected SystemExit")
        except SystemExit:
            pass
        except ValueError:
            pytest.fail("raw ValueError leaked out instead of a clean SystemExit")


# --- proxy warning ----------------------------------------------------------


def test_proxy_warning_fires_when_trusted_proxies_empty(caplog):
    settings = _settings(trusted_proxies="")

    with patch("haywire_studio.app.app"), caplog.at_level("WARNING", logger="haywire_studio.app"):
        HaywireApp._install_ip_allowlist(settings)

    assert any("trusted_proxies is empty" in record.message for record in caplog.records)
    assert any("X-Forwarded-For" in record.message for record in caplog.records)


def test_no_proxy_warning_when_trusted_proxies_set(caplog):
    settings = _settings(trusted_proxies="172.16.0.0/12")

    with patch("haywire_studio.app.app"), caplog.at_level("WARNING", logger="haywire_studio.app"):
        HaywireApp._install_ip_allowlist(settings)

    assert not any("trusted_proxies is empty" in record.message for record in caplog.records)


def test_proxy_warning_does_not_fire_when_expose_to_network_false(monkeypatch, caplog):
    """The warning lives inside _install_ip_allowlist, which run() only calls
    when expose_to_network is True — assert that gating from run()'s side."""
    instance = HaywireApp.__new__(HaywireApp)
    instance._is_shutting_down = True

    monkeypatch.setattr(instance, "create_ui", lambda: None)
    monkeypatch.setattr(instance, "setup_farmhand", lambda port: None)

    with (
        patch("haywire_studio.network.settings.NetworkSettings") as MockSettings,
        patch("haywire_studio.app.ui"),
        patch("haywire_studio.app.app"),
        caplog.at_level("WARNING", logger="haywire_studio.app"),
    ):
        MockSettings.return_value = _settings(expose_to_network=False, trusted_proxies="")
        instance.run(open_browser=False)

    assert not any("trusted_proxies is empty" in record.message for record in caplog.records)


# --- end-to-end: the actual Starlette add_middleware wiring reaches websocket
# traffic through a mounted sub-app, mirroring NiceGUI's own mount pattern ---
#
# This drives the SAME add_middleware(IPAllowlistMiddleware, ...) call
# app.py makes, against a synthetic FastAPI app with a WebSocket sub-app
# mounted the way NiceGUI mounts its Socket.IO app
# (app.mount('/_nicegui_ws/', sio_app) in nicegui/nicegui.py). Uses a fresh
# FastAPI instance rather than the real nicegui.app singleton: mutating the
# shared global here would leak `user_middleware` across the test session
# with no teardown path (the existing _reset_nicegui_globals autouse fixture
# does not cover middleware state).


def _build_synthetic_nicegui_like_app():
    """A minimal FastAPI app with a mounted WebSocket sub-app, structurally
    identical (mount-then-middleware) to how nicegui.py wires its Socket.IO
    mount."""
    from fastapi import FastAPI
    from starlette.applications import Starlette
    from starlette.routing import WebSocketRoute
    from starlette.websockets import WebSocket

    async def ws_endpoint(websocket: WebSocket):
        await websocket.accept()
        await websocket.send_text("hello")
        await websocket.close()

    sub_app = Starlette(routes=[WebSocketRoute("/ws", ws_endpoint)])
    root = FastAPI()
    root.mount("/_nicegui_ws", sub_app)  # mirrors nicegui.py's mount call
    return root


def test_add_middleware_wiring_rejects_out_of_range_websocket_through_mount():
    """The real wiring: an out-of-range peer must never reach the mounted
    websocket endpoint — proves the middleware sits outside routing/mounting,
    not just that add_middleware was called with the right arguments."""
    from starlette.testclient import TestClient
    from starlette.websockets import WebSocketDisconnect

    root = _build_synthetic_nicegui_like_app()
    root.add_middleware(
        IPAllowlistMiddleware,
        allowed_ranges=["203.0.113.0/24"],
        trusted_proxies=[],
    )

    client = TestClient(root, client=("198.51.100.7", 12345))  # outside allowed_ranges

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/_nicegui_ws/ws") as ws:
            ws.receive_text()


def test_add_middleware_wiring_allows_in_range_websocket_through_mount():
    from starlette.testclient import TestClient

    root = _build_synthetic_nicegui_like_app()
    root.add_middleware(
        IPAllowlistMiddleware,
        allowed_ranges=["203.0.113.0/24"],
        trusted_proxies=[],
    )

    client = TestClient(root, client=("203.0.113.5", 12345))  # inside allowed_ranges

    with client.websocket_connect("/_nicegui_ws/ws") as ws:
        assert ws.receive_text() == "hello"


def test_add_middleware_wiring_allows_loopback_regardless_of_allowlist():
    """Loopback bypass (handled inside IPAllowlistMiddleware itself, Task 2a)
    must still be reachable through the real add_middleware wiring."""
    from starlette.testclient import TestClient

    root = _build_synthetic_nicegui_like_app()
    root.add_middleware(
        IPAllowlistMiddleware,
        allowed_ranges=["203.0.113.0/24"],  # loopback peer is NOT in this range
        trusted_proxies=[],
    )

    client = TestClient(root, client=("127.0.0.1", 12345))

    with client.websocket_connect("/_nicegui_ws/ws") as ws:
        assert ws.receive_text() == "hello"
