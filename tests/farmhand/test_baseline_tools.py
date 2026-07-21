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
    is HaywireApp's job in the real app), so set it here to an empty tmp dir.
    Note: the write gate keys off install_type (editable), NOT the workspace
    root, so the barn/haybale-* editable libraries ARE writable targets here
    regardless of this path — that is the intent of an editable install.
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


# The write gate is `project_local_libraries` / `resolve_target_library`. Test the
# gate DECISION directly rather than driving the full write tool: a real write lands
# in the target library's actual on-disk folder (library_folder resolves to the real
# barn path — there is no test isolation for it), which would litter a shared barn
# library with artifacts. The gate function is the unit that actually changed.


def test_editable_library_is_a_writable_target():
    """An editable (pip -e) barn library is authorable — that is the intent of -e.

    The barn/haybale-* libraries are editable installs, so the gate must accept
    them regardless of the workspace root.
    """
    from haybale_studio.farmhands._helpers import project_local_libraries, resolve_target_library

    locals_ = project_local_libraries(FarmhandContext())
    assert "testing" in locals_, f"editable library 'testing' should be writable, got {locals_}"
    # resolve_target_library returns it without raising the gate error.
    assert resolve_target_library(FarmhandContext(), "testing") == "testing"


def test_write_gate_rejects_unknown_library():
    """A library that is not an editable, in-repo install is rejected by name."""
    from haybale_studio.farmhands._helpers import resolve_target_library

    with pytest.raises(FarmhandError) as exc_info:
        resolve_target_library(FarmhandContext(), "__does_not_exist__")
    assert exc_info.value.code == "not_project_library"


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
    # Entries cross the MCP boundary as JSON dicts (serialized from the live
    # HaywireException objects the ledger now holds), carrying seq + seen.
    entry = result["errors"][0]
    assert isinstance(entry, dict)
    assert "seq" in entry
    assert "seen" in entry
    assert "message" in entry


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
