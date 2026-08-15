"""IPAllowlistMiddleware: synthetic ASGI scopes, no live server needed."""

import asyncio

import pytest

from haywire_studio.network.ip_filter import IPAllowlistMiddleware

pytestmark = pytest.mark.unit


class _Recorder:
    """Fake downstream ASGI app that records whether it was invoked."""

    def __init__(self):
        self.called = False

    async def __call__(self, scope, receive, send):
        self.called = True
        if scope["type"] == "websocket":
            await send({"type": "websocket.accept"})
        else:
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"ok"})


def _receive():
    async def _inner():
        return {"type": "http.request"}

    return _inner


def _make_scope(scope_type="http", client=None, headers=None, path="/"):
    scope = {"type": scope_type, "path": path, "headers": headers or []}
    if client is not None:
        scope["client"] = client
    return scope


def _run(middleware, scope):
    """Drive the middleware and collect every message sent."""
    sent: list[dict] = []

    async def send(message):
        sent.append(message)

    asyncio.run(middleware(scope, _receive(), send))
    return sent


def _xff_headers(value: str):
    return [(b"x-forwarded-for", value.encode("latin-1"))]


# --- lifespan -----------------------------------------------------------


def test_lifespan_scope_passes_through_untouched():
    inner = _Recorder()
    middleware = IPAllowlistMiddleware(inner, allowed_ranges=[])
    scope = {"type": "lifespan"}

    async def send(message):
        pass

    async def receive():
        return {"type": "lifespan.startup"}

    asyncio.run(middleware(scope, receive, send))
    assert inner.called


# --- loopback is unconditional -------------------------------------------


def test_http_loopback_peer_empty_allowlist_passes_through():
    inner = _Recorder()
    middleware = IPAllowlistMiddleware(inner, allowed_ranges=[])
    scope = _make_scope(client=("127.0.0.1", 12345))

    sent = _run(middleware, scope)

    assert inner.called
    assert sent[0]["status"] == 200


def test_http_loopback_peer_non_matching_allowlist_passes_through():
    inner = _Recorder()
    middleware = IPAllowlistMiddleware(inner, allowed_ranges=["203.0.113.0/24"])
    scope = _make_scope(client=("127.0.0.1", 12345))

    sent = _run(middleware, scope)

    assert inner.called
    assert sent[0]["status"] == 200


# --- websocket ------------------------------------------------------------


def test_websocket_in_range_peer_passes_through():
    inner = _Recorder()
    middleware = IPAllowlistMiddleware(inner, allowed_ranges=["192.168.1.0/24"])
    scope = _make_scope(scope_type="websocket", client=("192.168.1.5", 5555))

    sent = _run(middleware, scope)

    assert inner.called
    assert sent[0]["type"] == "websocket.accept"


def test_websocket_out_of_range_peer_closes_1008_inner_never_called():
    inner = _Recorder()
    middleware = IPAllowlistMiddleware(inner, allowed_ranges=["192.168.1.0/24"])
    scope = _make_scope(scope_type="websocket", client=("203.0.113.9", 5555))

    sent = _run(middleware, scope)

    assert not inner.called
    assert sent == [{"type": "websocket.close", "code": 1008}]


# --- http reject ------------------------------------------------------------


def test_http_out_of_range_peer_is_403_inner_never_called():
    inner = _Recorder()
    middleware = IPAllowlistMiddleware(inner, allowed_ranges=["192.168.1.0/24"])
    scope = _make_scope(client=("203.0.113.9", 5555))

    sent = _run(middleware, scope)

    assert not inner.called
    assert sent[0]["type"] == "http.response.start"
    assert sent[0]["status"] == 403
    assert sent[1]["type"] == "http.response.body"


def test_client_none_is_rejected():
    inner = _Recorder()
    middleware = IPAllowlistMiddleware(inner, allowed_ranges=["0.0.0.0/0"])
    scope = _make_scope(client=None)

    sent = _run(middleware, scope)

    assert not inner.called
    assert sent[0]["status"] == 403


def test_websocket_client_none_closes_1008_not_403():
    """The reject helper must branch on scope type, not just on the reason
    for rejection — a None client on a websocket scope must still close
    with 1008, not send an HTTP response frame."""
    inner = _Recorder()
    middleware = IPAllowlistMiddleware(inner, allowed_ranges=["0.0.0.0/0"])
    scope = _make_scope(scope_type="websocket", client=None)

    sent = _run(middleware, scope)

    assert not inner.called
    assert sent == [{"type": "websocket.close", "code": 1008}]


def test_malformed_peer_ip_is_rejected():
    inner = _Recorder()
    middleware = IPAllowlistMiddleware(inner, allowed_ranges=["0.0.0.0/0"])
    scope = _make_scope(client=("not-an-ip", 1234))

    sent = _run(middleware, scope)

    assert not inner.called
    assert sent[0]["status"] == 403


def test_malformed_peer_ip_logs_warning(caplog):
    inner = _Recorder()
    middleware = IPAllowlistMiddleware(inner, allowed_ranges=["0.0.0.0/0"])
    scope = _make_scope(client=("not-an-ip", 1234))

    with caplog.at_level("WARNING", logger="haywire_studio.network.ip_filter"):
        _run(middleware, scope)

    assert any("not-an-ip" in record.message for record in caplog.records)


# --- X-Forwarded-For --------------------------------------------------------


def test_xff_present_peer_not_trusted_proxy_is_ignored():
    """Peer is NOT in trusted_proxies -> XFF must not be consulted; the
    direct peer (out of range) determines the outcome."""
    inner = _Recorder()
    middleware = IPAllowlistMiddleware(
        inner,
        allowed_ranges=["203.0.113.0/24"],  # matches the XFF-claimed IP, not the peer
        trusted_proxies=["10.0.0.0/8"],
    )
    scope = _make_scope(
        client=("198.51.100.7", 5555),  # untrusted peer, out of allowed_ranges
        headers=_xff_headers("203.0.113.5"),
    )

    sent = _run(middleware, scope)

    assert not inner.called
    assert sent[0]["status"] == 403


def test_xff_present_peer_in_trusted_proxies_uses_rightmost_untrusted():
    """Peer IS a trusted proxy. Chain: client, proxy2, proxy1 (proxy1 is the
    closest hop, appended last / rightmost). trusted_proxies covers 10.0.0.0/8;
    real client 203.0.113.5 is outside it and must be picked."""
    inner = _Recorder()
    middleware = IPAllowlistMiddleware(
        inner,
        allowed_ranges=["203.0.113.0/24"],
        trusted_proxies=["10.0.0.0/8"],
    )
    scope = _make_scope(
        client=("10.0.0.1", 5555),  # trusted proxy is the direct peer
        headers=_xff_headers("203.0.113.5, 10.0.0.2, 10.0.0.1"),
    )

    sent = _run(middleware, scope)

    assert inner.called
    assert sent[0]["status"] == 200


def test_xff_chain_all_trusted_falls_back_to_peer():
    """Every entry in the XFF chain is itself a trusted proxy: no untrusted
    hop exists, so we fall back to the direct peer for the allow check."""
    inner = _Recorder()
    middleware = IPAllowlistMiddleware(
        inner,
        allowed_ranges=["10.0.0.0/8"],  # matches the peer itself
        trusted_proxies=["10.0.0.0/8"],
    )
    scope = _make_scope(
        client=("10.0.0.1", 5555),
        headers=_xff_headers("10.0.0.3, 10.0.0.2"),
    )

    sent = _run(middleware, scope)

    assert inner.called
    assert sent[0]["status"] == 200


def test_xff_empty_trusted_proxies_ignores_header_even_if_present():
    """trusted_proxies is empty -> XFF must never be consulted, even though
    the header is present and would otherwise resolve to an allowed IP."""
    inner = _Recorder()
    middleware = IPAllowlistMiddleware(
        inner,
        allowed_ranges=["203.0.113.0/24"],
        trusted_proxies=(),
    )
    scope = _make_scope(
        client=("198.51.100.7", 5555),  # not in allowed_ranges
        headers=_xff_headers("203.0.113.5"),
    )

    sent = _run(middleware, scope)

    assert not inner.called
    assert sent[0]["status"] == 403


def test_xff_rightmost_untrusted_skips_multiple_trusted_hops():
    """Chain has two trusted hops on the right before the real client."""
    inner = _Recorder()
    middleware = IPAllowlistMiddleware(
        inner,
        allowed_ranges=["198.51.100.0/24"],
        trusted_proxies=["10.0.0.0/8"],
    )
    scope = _make_scope(
        client=("10.0.0.9", 5555),
        headers=_xff_headers("198.51.100.42, 10.0.0.5, 10.0.0.9"),
    )

    sent = _run(middleware, scope)

    assert inner.called
    assert sent[0]["status"] == 200


# --- constructor ------------------------------------------------------------


def test_invalid_cidr_in_allowed_ranges_raises_value_error():
    with pytest.raises(ValueError, match="does not appear"):
        IPAllowlistMiddleware(_Recorder(), allowed_ranges=["not-a-cidr"])


def test_invalid_cidr_in_trusted_proxies_raises_value_error():
    with pytest.raises(ValueError, match="does not appear"):
        IPAllowlistMiddleware(_Recorder(), allowed_ranges=[], trusted_proxies=["also-not-a-cidr"])


def test_ranges_parsed_once_in_constructor():
    """Mutating the source iterable after construction must not affect an
    already-built middleware — ranges are parsed once, not lazily re-read."""
    ranges = ["192.168.1.0/24"]
    middleware = IPAllowlistMiddleware(_Recorder(), allowed_ranges=ranges)
    ranges.append("10.0.0.0/8")

    assert len(middleware.allowed_ranges) == 1
