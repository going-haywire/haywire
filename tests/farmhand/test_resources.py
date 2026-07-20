"""Resource families: component canons and installed-library docs."""

import pytest

pytestmark = pytest.mark.integration


def test_canon_resources_listed_and_readable(farmhand_call):
    async def scenario(session, init):
        listing = await session.list_resources()
        uris = [str(r.uri) for r in listing.resources]
        assert "farmhand://docs/canon/nodes" in uris
        content = await session.read_resource("farmhand://docs/canon/nodes")
        return content

    content = farmhand_call(scenario)
    text = content.contents[0].text
    assert "worker" in text


def test_library_overview_resource(farmhand_call):
    async def scenario(session, init):
        listing = await session.list_resources()
        uris = [str(r.uri) for r in listing.resources]
        assert "farmhand://library/testing/overview" in uris
        content = await session.read_resource("farmhand://library/testing/overview")
        return content.contents[0].text

    assert len(farmhand_call(scenario)) > 0


def test_resources_capability_advertises_list_changed(farmhand_call):
    async def scenario(session, init):
        return init

    init = farmhand_call(scenario)
    assert init.capabilities.resources.listChanged is True
