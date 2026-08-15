"""Farmhand tool visibility follows the caller's tier."""

from typing import Any, cast
from unittest.mock import MagicMock

from haywire.core.access import AccessTier


def _tool(name: str, access: AccessTier):
    from haywire.core.farmhand.identity import FarmhandIdentity

    cls = cast(Any, type(name, (), {}))
    cls.class_identity = FarmhandIdentity(
        registry_id=name, registry_key=f"k:{name}", label=name, instructions="i", access=access
    )
    cls.input_schema = classmethod(lambda c: {"type": "object", "properties": {}})
    return cls


def test_tier_for_tools_filters_by_caller_tier():
    from haywire_studio.farmhand.host import tools_for_tier

    tools = {
        "read": _tool("read", AccessTier.VIEW),
        "write": _tool("write", AccessTier.EDIT),
        "install": _tool("install", AccessTier.ADMIN),
    }
    assert sorted(tools_for_tier(tools, AccessTier.VIEW)) == ["read"]
    assert sorted(tools_for_tier(tools, AccessTier.EDIT)) == ["read", "write"]
    assert sorted(tools_for_tier(tools, AccessTier.ADMIN)) == ["install", "read", "write"]


def test_tool_without_identity_access_defaults_to_view():
    from haywire_studio.farmhand.host import tools_for_tier

    cls = type("Bare", (), {})
    assert tools_for_tier({"bare": cls}, AccessTier.VIEW) == ["bare"]


def test_caller_tier_reads_the_principal_off_the_asgi_scope(monkeypatch):
    from haywire.core.access import access_resolver, set_access_resolver
    from haywire_studio.farmhand.host import caller_tier
    from haywire_studio.auth.gate import PRINCIPAL_SCOPE_KEY

    previous = access_resolver()
    try:
        set_access_resolver(lambda name: AccessTier.EDIT if name == "builder" else AccessTier.VIEW)
        request = MagicMock()
        request.scope = {PRINCIPAL_SCOPE_KEY: "builder"}
        assert caller_tier(request) is AccessTier.EDIT
    finally:
        set_access_resolver(previous)


def test_caller_tier_with_no_request_is_admin_when_auth_is_off():
    from haywire.core.access import access_resolver, set_access_resolver
    from haywire_studio.farmhand.host import caller_tier

    previous = access_resolver()
    try:
        set_access_resolver(None)
        assert caller_tier(None) is AccessTier.ADMIN
    finally:
        set_access_resolver(previous)
