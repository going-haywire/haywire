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

    result = run_tool(StudioListComponentsTool, library="haybale-testing", kind="node")
    assert result["total"] >= 1
    rows = result["components"]
    # Default row is identity only — description is the bulk of a large listing.
    assert all(set(row) == {"registry_key", "label"} for row in rows)
    assert all(row["registry_key"].startswith("haybale-testing:node:") for row in rows)

    detailed = run_tool(StudioListComponentsTool, library="haybale-testing", kind="node", detail=True)
    assert all(set(row) == {"registry_key", "label", "description"} for row in detailed["components"])


def test_list_components_search_matches_label_or_description():
    from haybale_studio.farmhands.catalog import StudioDescribeComponentTool, StudioListComponentsTool

    listing = run_tool(StudioListComponentsTool, library="haybale-testing", kind="node", limit=1)
    key = listing["components"][0]["registry_key"]
    label = run_tool(StudioDescribeComponentTool, registry_key=key)["label"]

    found = run_tool(StudioListComponentsTool, search=label)
    assert key in {row["registry_key"] for row in found["components"]}

    empty = run_tool(StudioListComponentsTool, search="zzz_no_component_should_match_this_zzz")
    assert empty["total"] == 0


def test_list_components_excludes_hidden_by_default():
    from haybale_studio.farmhands.catalog import StudioListComponentsTool

    visible = run_tool(StudioListComponentsTool, library="haywire-core", kind="node")
    keys = {row["registry_key"] for row in visible["components"]}
    assert "haywire-core:node:RerouteNode" not in keys

    with_hidden = run_tool(
        StudioListComponentsTool, library="haywire-core", kind="node", include_hidden=True
    )
    keys_with_hidden = {row["registry_key"] for row in with_hidden["components"]}
    assert "haywire-core:node:RerouteNode" in keys_with_hidden


def test_list_components_excludes_system_library_by_default():
    """__system__ is the derive_library_identity() fallback for unparented classes
    (e.g. FrameworkSettings); whether any are registered depends on which other
    settings modules already imported in this session, so assert the filtering
    guarantee rather than a specific key's presence.
    """
    from haybale_studio.farmhands.catalog import StudioListComponentsTool

    visible = run_tool(StudioListComponentsTool, limit=10_000)
    assert all(not row["registry_key"].startswith("__") for row in visible["components"])

    with_system = run_tool(StudioListComponentsTool, include_system=True, limit=10_000)
    assert len(with_system["components"]) >= len(visible["components"])


def test_describe_node_includes_live_ports():
    from haybale_studio.farmhands.catalog import (
        StudioDescribeComponentTool,
        StudioListComponentsTool,
    )

    listing = run_tool(StudioListComponentsTool, library="haybale-testing", kind="node", limit=1)
    key = listing["components"][0]["registry_key"]
    result = run_tool(StudioDescribeComponentTool, registry_key=key)
    assert "ports" in result
    assert isinstance(result["ports"], list)
    for p in result["ports"]:
        assert set(p) >= {"id", "direction", "data_type"}


def test_list_components_count_only_groups_by_library_and_kind():
    from haybale_studio.farmhands.catalog import StudioListComponentsTool

    result = run_tool(StudioListComponentsTool, library="haybale-testing", kind="node", count_only=True)
    assert "components" not in result
    assert result["counts"]["haybale-testing"]["node"] == result["total"]
    assert result["total"] >= 1


def test_list_components_truncated_result_gets_scoping_tip():
    """An unfiltered/wide call that overflows `limit` gets a scoping hint in
    `help` — the trigger is truncation (total > limit), not "no filters passed",
    so a legitimately small unfiltered query isn't nagged (see the sibling test).
    """
    from haybale_studio.farmhands.catalog import StudioListComponentsTool

    result = run_tool(StudioListComponentsTool, limit=1)
    assert result["total"] > 1
    assert "narrow this" in result["help"]
    assert "count_only=true" in result["help"]


def test_list_components_untruncated_result_has_no_tip():
    from haybale_studio.farmhands.catalog import StudioListComponentsTool

    result = run_tool(StudioListComponentsTool, library="haybale-testing", kind="node", limit=10_000)
    assert result["total"] <= 10_000
    # A complete result still gets a drill-down hint, but never the scoping nag.
    assert "narrow this" not in result.get("help", "")


def test_list_libraries_excludes_system_library_by_default():
    from haybale_studio.farmhands.catalog import StudioListLibrariesTool

    result = run_tool(StudioListLibrariesTool, limit=1000)
    assert all(not row["id"].startswith("__") for row in result["libraries"])


def test_describe_component_returns_identity_and_doc():
    from haybale_studio.farmhands.catalog import (
        StudioDescribeComponentTool,
        StudioListComponentsTool,
    )

    listing = run_tool(StudioListComponentsTool, library="haybale-testing", kind="node", limit=1)
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

    listing = run_tool(StudioListComponentsTool, library="haybale-testing", kind="node", limit=1)
    key = listing["components"][0]["registry_key"]
    result = run_tool(StudioReadComponentSourceTool, registry_key=key)
    assert result["source"].splitlines()[0].startswith("1\t")
    assert result["path"].endswith(".py")


def _a_component_key():
    from haybale_studio.farmhands.catalog import StudioListComponentsTool

    listing = run_tool(StudioListComponentsTool, library="haybale-testing", kind="node", limit=1)
    return listing["components"][0]["registry_key"]


def test_read_component_source_truncates_and_offers_the_full_escape_hatch():
    from haybale_studio.farmhands.authoring import StudioReadComponentSourceTool

    key = _a_component_key()
    # limit=2 forces truncation on any real component file.
    page = run_tool(StudioReadComponentSourceTool, registry_key=key, limit=2)
    assert len(page["source"].splitlines()) == 2
    # The caller learns the true size and how to get the rest.
    assert page["total_lines"] > 2
    assert "showing 1-2 of" in page["summary"]
    assert "full=true" in page["help"]

    full = run_tool(StudioReadComponentSourceTool, registry_key=key, full=True)
    assert len(full["source"].splitlines()) == full["total_lines"]
    assert "help" not in full  # nothing hidden -> no hint


def test_read_component_source_offset_window_keeps_absolute_line_numbers():
    from haybale_studio.farmhands.authoring import StudioReadComponentSourceTool

    key = _a_component_key()
    window = run_tool(StudioReadComponentSourceTool, registry_key=key, offset=2, limit=2)
    # Line 3 of the file must still be labelled 3, so the window stays quotable.
    assert window["source"].splitlines()[0].startswith("3\t")


# The write gate is `project_writable_libraries` / `resolve_target_library`. Test the
# gate DECISION directly rather than driving the full write tool: a real write lands
# in the target library's actual on-disk folder (library_folder resolves to the real
# barn path — there is no test isolation for it), which would litter a shared barn
# library with artifacts. The gate function is the unit that actually changed.


def test_editable_library_is_a_writable_target():
    """An editable (pip -e) barn library is authorable — that is the intent of -e.

    The barn/haybale-* libraries are editable installs, so the gate must accept
    them regardless of the workspace root.
    """
    from haybale_studio.farmhands._helpers import project_writable_libraries, resolve_target_library

    locals_ = project_writable_libraries(FarmhandContext())
    assert "haybale-testing" in locals_, f"editable library 'testing' should be writable, got {locals_}"
    # resolve_target_library returns it without raising the gate error.
    assert resolve_target_library(FarmhandContext(), "haybale-testing") == "haybale-testing"


def test_write_gate_rejects_unknown_library():
    """A library that is not an editable, in-repo install is rejected by name."""
    from haybale_studio.farmhands._helpers import resolve_target_library

    with pytest.raises(FarmhandError) as exc_info:
        resolve_target_library(FarmhandContext(), "__does_not_exist__")
    assert exc_info.value.code == "not_project_library"


def test_verify_component_ok_for_registered_node():
    from haybale_studio.farmhands.authoring import StudioVerifyComponentTool
    from haybale_studio.farmhands.catalog import StudioListComponentsTool

    listing = run_tool(StudioListComponentsTool, library="haybale-testing", kind="node", limit=1)
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


def test_dismiss_errors_removes_one_entry():
    from haybale_studio.farmhands.errors import StudioDismissErrorsTool, StudioGetErrorsTool

    from haywire.core.errors.haywire_exception import HaywireException
    from haywire.core.errors.ledger import get_error_ledger

    seq = HaywireException.create("dismiss-one test error").log().ledger_seq
    assert any(e.ledger_seq == seq for e in get_error_ledger().query(limit=10_000).entries)

    result = run_tool(StudioDismissErrorsTool, seq=seq)
    assert result["summary"] == f"Dismissed entry {seq}."
    # Entry is gone, but the monotonic cursor is untouched.
    assert not any(e.ledger_seq == seq for e in get_error_ledger().query(limit=10_000).entries)
    assert run_tool(StudioGetErrorsTool)["cursor"] >= seq


def test_dismiss_absent_seq_is_idempotent_noop():
    from haybale_studio.farmhands.errors import StudioDismissErrorsTool

    result = run_tool(StudioDismissErrorsTool, seq=999_999)
    assert result["summary"] == "No entry 999999 to dismiss."


def test_dismiss_all_clears_the_ledger():
    from haybale_studio.farmhands.errors import StudioDismissErrorsTool, StudioGetErrorsTool

    from haywire.core.errors.haywire_exception import HaywireException

    HaywireException.create("clear-all test error").log()
    run_tool(StudioDismissErrorsTool, all=True)
    assert run_tool(StudioGetErrorsTool)["total"] == 0


def test_dismiss_requires_exactly_one_target():
    from haybale_studio.farmhands.errors import StudioDismissErrorsTool

    # Neither seq nor all.
    with pytest.raises(FarmhandError) as exc_info:
        run_tool(StudioDismissErrorsTool)
    assert exc_info.value.code == "invalid_args"
    # Both seq and all.
    with pytest.raises(FarmhandError) as exc_info:
        run_tool(StudioDismissErrorsTool, seq=1, all=True)
    assert exc_info.value.code == "invalid_args"


def test_registry_holds_exactly_ten_studio_tools(library_system):
    from haywire.core.farmhand import FarmhandRegistry

    registry = library_system.injector.get(FarmhandRegistry)
    studio_keys = {k for k in registry.list_names() if k.startswith("haybale-studio:farmhand:")}
    assert studio_keys == {
        "haybale-studio:farmhand:status",
        "haybale-studio:farmhand:list_libraries",
        "haybale-studio:farmhand:list_components",
        "haybale-studio:farmhand:describe_component",
        "haybale-studio:farmhand:scaffold_component",
        "haybale-studio:farmhand:read_component_source",
        "haybale-studio:farmhand:write_component_source",
        "haybale-studio:farmhand:verify_component",
        "haybale-studio:farmhand:get_errors",
        "haybale-studio:farmhand:dismiss_errors",
    }
