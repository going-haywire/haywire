"""Every shipped Farmhand tool declares a deliberate tier."""

import pytest

from haywire.core.access import AccessTier

ADMIN_TOOLS = {
    "scaffold_component",
    "write_component_source",
    "dismiss_errors",
    "install_library",
    "uninstall_library",
}

EDIT_TOOLS = {
    "add_node",
    "connect",
    "remove_elements",
    "move_nodes",
    "set_property",
    "set_metadata",
    "promote_setting",
    "demote_setting",
    "undo",
    "redo",
    "create_graph",
    "open_graph",
    "save_graph",
    "rename_graph",
    "close_graph",
    "start_graph",
    "stop_graph",
    "dry_run_install",
}

VIEW_TOOLS = {
    "status",
    "list_components",
    "describe_component",
    "list_libraries",
    "get_errors",
    "list_graphs",
    "query_graph",
    "inspect_node",
    "compile_graph",
    "read_component_source",
    "verify_component",
    "list_available",
    "refresh",
    "get_library_docs",
    "affinity",
    "block",
    "echo",
    "fail",
}


def _tool_map():
    from haywire.core.di.config import create_library_system_service  # noqa: F401

    pytest.importorskip("haybale_studio")
    from haywire.core.farmhand import FarmhandRegistry  # noqa: F401

    # Import the tool modules directly rather than booting a library system.
    import haybale_graph_editor.farmhands.editor_tools as editor_tools
    import haybale_haystack.farmhands.graph_tools as graph_tools
    import haybale_marketplace.farmhands.catalog_tools as catalog_tools
    import haybale_marketplace.farmhands.install_tools as install_tools
    import haybale_studio.farmhands.authoring as authoring
    import haybale_studio.farmhands.catalog as catalog
    import haybale_studio.farmhands.errors as errors
    import haybale_studio.farmhands.status as status
    import haybale_testing.farmhands.affinity_tool as affinity_tool
    import haybale_testing.farmhands.blocking_tool as blocking_tool
    import haybale_testing.farmhands.echo_tool as echo_tool
    import haybale_testing.farmhands.fail_tool as fail_tool

    modules = [
        editor_tools,
        graph_tools,
        catalog_tools,
        install_tools,
        authoring,
        catalog,
        errors,
        status,
        affinity_tool,
        blocking_tool,
        echo_tool,
        fail_tool,
    ]
    found = {}
    for module in modules:
        for obj in vars(module).values():
            identity = getattr(obj, "class_identity", None)
            if identity is not None and hasattr(identity, "instructions"):
                found[identity.registry_id] = identity
    return found


@pytest.mark.integration
def test_write_tools_require_admin():
    identities = _tool_map()
    for registry_id, identity in identities.items():
        if registry_id in ADMIN_TOOLS:
            assert identity.access is AccessTier.ADMIN, f"{registry_id} should be admin"


@pytest.mark.integration
def test_edit_tools_require_edit():
    identities = _tool_map()
    for registry_id, identity in identities.items():
        if registry_id in EDIT_TOOLS:
            assert identity.access is AccessTier.EDIT, f"{registry_id} should be edit"


@pytest.mark.integration
def test_view_tools_are_view():
    identities = _tool_map()
    for registry_id, identity in identities.items():
        if registry_id in VIEW_TOOLS:
            assert identity.access is AccessTier.VIEW, f"{registry_id} should be view"


@pytest.mark.integration
def test_every_tool_is_classified():
    """Every discovered tool must appear in exactly one of the tier buckets above —
    catches a shipped tool nobody looked at when annotating."""
    identities = _tool_map()
    known = ADMIN_TOOLS | EDIT_TOOLS | VIEW_TOOLS
    unclassified = set(identities) - known
    assert not unclassified, f"tools not classified in this test: {unclassified}"


@pytest.mark.integration
def test_no_shipped_tool_is_left_at_the_default_by_accident():
    """Every tool must have been looked at — VIEW is fine, but only deliberately."""
    identities = _tool_map()
    assert identities, "no farmhand identities discovered — fix the import list in this test"
