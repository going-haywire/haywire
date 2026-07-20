"""Baseline studio_* tools, driven directly (no MCP transport)."""

import asyncio

import pytest

from haywire.core.farmhand import FarmhandContext, FarmhandError

pytestmark = pytest.mark.integration


def run_tool(tool_cls, **kwargs):
    return asyncio.run(tool_cls().run(FarmhandContext(), **kwargs))


@pytest.fixture(autouse=True)
def _ambient(library_system, tmp_path):
    """All baseline tools resolve services from the ambient DI context.

    library_system wires the injector but not the ambient workspace_root (that
    is HaywireApp's job in the real app), so set it here. It points at an empty
    tmp dir so no folder-installed library counts as "project-local" — the
    barn libraries live under the repo root, which would otherwise make them
    project-local writable targets in these tests.
    """
    from haywire.core.di import context as di_context

    previous = di_context._workspace_root
    di_context.set_workspace_root(str(tmp_path))
    yield
    di_context._workspace_root = previous


def test_status_reports_basics():
    from haybale_studio.farmhands.status import StudioStatusTool

    result = run_tool(StudioStatusTool)
    assert "workspace_root" in result
    assert result["enabled_libraries"] >= 1
    assert result["protocol_version"] == "2025-11-25"


def test_list_libraries_paginates():
    from haybale_studio.farmhands.catalog import StudioListLibrariesTool

    result = run_tool(StudioListLibrariesTool, limit=1, offset=0)
    assert result["total"] >= 1
    assert len(result["libraries"]) == 1
    row = result["libraries"][0]
    assert {"id", "label", "version", "enabled"} <= set(row)


def test_list_components_filters_by_library_and_kind():
    from haybale_studio.farmhands.catalog import StudioListComponentsTool

    result = run_tool(StudioListComponentsTool, library="testing", kind="node")
    assert result["total"] >= 1
    assert all(k.startswith("testing:node:") for k in [c["registry_key"] for c in result["components"]])


def test_describe_component_returns_identity_and_doc():
    from haybale_studio.farmhands.catalog import (
        StudioDescribeComponentTool,
        StudioListComponentsTool,
    )

    listing = run_tool(StudioListComponentsTool, library="testing", kind="node", limit=1)
    key = listing["components"][0]["registry_key"]
    result = run_tool(StudioDescribeComponentTool, registry_key=key)
    assert result["registry_key"] == key
    assert "label" in result


def test_describe_unknown_component_is_stable_error():
    from haybale_studio.farmhands.catalog import StudioDescribeComponentTool

    with pytest.raises(FarmhandError) as exc_info:
        run_tool(StudioDescribeComponentTool, registry_key="nope:node:missing")
    assert exc_info.value.code == "component_not_found"


def test_read_component_source_is_line_numbered():
    from haybale_studio.farmhands.authoring import StudioReadComponentSourceTool
    from haybale_studio.farmhands.catalog import StudioListComponentsTool

    listing = run_tool(StudioListComponentsTool, library="testing", kind="node", limit=1)
    key = listing["components"][0]["registry_key"]
    result = run_tool(StudioReadComponentSourceTool, registry_key=key)
    assert result["source"].splitlines()[0].startswith("1\t")
    assert result["path"].endswith(".py")


def test_write_component_source_rejects_non_project_library():
    from haybale_studio.farmhands.authoring import StudioWriteComponentSourceTool

    with pytest.raises(FarmhandError) as exc_info:
        run_tool(
            StudioWriteComponentSourceTool,
            library="testing",  # barn test library is not a project-local library target
            kind="node",
            filename="hacked.py",
            source="print('no')",
        )
    assert exc_info.value.code in ("not_project_library", "no_project_library")


def test_scaffold_requires_a_project_library():
    from haybale_studio.farmhands.authoring import StudioScaffoldComponentTool

    with pytest.raises(FarmhandError) as exc_info:
        run_tool(StudioScaffoldComponentTool, kind="node", name="my_node")
    assert exc_info.value.code == "no_project_library"  # test workspace has none -> haywire init hint
    assert "haywire init" in exc_info.value.message


def test_verify_component_ok_for_registered_node():
    from haybale_studio.farmhands.authoring import StudioVerifyComponentTool
    from haybale_studio.farmhands.catalog import StudioListComponentsTool

    listing = run_tool(StudioListComponentsTool, library="testing", kind="node", limit=1)
    key = listing["components"][0]["registry_key"]
    result = run_tool(StudioVerifyComponentTool, registry_key=key)
    assert result["registered"] is True
    assert result["stage_reached"] in ("registered", "instantiated", "testrun")


def test_get_errors_returns_ledger_page():
    from haybale_studio.farmhands.errors import StudioGetErrorsTool

    from haywire.core.errors.haywire_exception import HaywireException

    HaywireException.create("baseline tool test error").log()
    result = run_tool(StudioGetErrorsTool)
    assert result["total"] >= 1
    assert "cursor" in result
    assert "first_retained_seq" in result


def test_registry_holds_exactly_nine_studio_tools(library_system):
    from haywire.core.farmhand import FarmhandRegistry

    registry = library_system.injector.get(FarmhandRegistry)
    studio_keys = {k for k in registry.list_names() if k.startswith("studio:farmhand:")}
    assert studio_keys == {
        "studio:farmhand:status",
        "studio:farmhand:list_libraries",
        "studio:farmhand:list_components",
        "studio:farmhand:describe_component",
        "studio:farmhand:scaffold_component",
        "studio:farmhand:read_component_source",
        "studio:farmhand:write_component_source",
        "studio:farmhand:verify_component",
        "studio:farmhand:get_errors",
    }
