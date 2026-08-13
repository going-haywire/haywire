"""Resource families: component canons and installed-library docs."""

import pytest

pytestmark = pytest.mark.integration


def test_doc_resources_listed_and_readable(farmhand_call):
    async def scenario(session, init):
        listing = await session.list_resources()
        uris = [str(r.uri) for r in listing.resources]
        # The full tree ships one resource per file plus a manifest index.
        assert "farmhand://docs/_manifest" in uris
        assert "farmhand://docs/components/nodes/node-canon.md" in uris
        content = await session.read_resource("farmhand://docs/components/nodes/node-canon.md")
        return content

    content = farmhand_call(scenario)
    text = content.contents[0].text
    assert "worker" in text


def test_doc_manifest_resource_is_json_index(farmhand_call):
    async def scenario(session, init):
        content = await session.read_resource("farmhand://docs/_manifest")
        return content.contents[0].text

    import json

    manifest = json.loads(farmhand_call(scenario))
    paths = {entry["path"] for entry in manifest}
    assert "components/nodes/node-canon.md" in paths
    assert all("title" in entry for entry in manifest)


def test_library_overview_resource(farmhand_call):
    async def scenario(session, init):
        listing = await session.list_resources()
        uris = [str(r.uri) for r in listing.resources]
        assert "farmhand://library/haybale-testing/overview" in uris
        content = await session.read_resource("farmhand://library/haybale-testing/overview")
        return content.contents[0].text

    assert len(farmhand_call(scenario)) > 0


def test_resources_capability_advertises_list_changed(farmhand_call):
    async def scenario(session, init):
        return init

    init = farmhand_call(scenario)
    assert init.capabilities.resources.listChanged is True
