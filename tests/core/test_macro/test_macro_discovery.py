"""Macros are discoverable through ``NodeFactory`` alongside node classes.

The menu, search and the key listing read both registries, so a macro is
offered like any other component. Placing one — ``get_node`` returning a
``MacroNode`` — is not here: that needs the placement class.
"""

import json

import pytest

pytestmark = pytest.mark.integration

_INPUT = "haywire-core:node:SubgraphInputNode"
_OUTPUT = "haywire-core:node:SubgraphOutputNode"


def _identity(folder_path="/lib"):
    from haywire.core.library.identity import LibraryIdentity

    return LibraryIdentity(label="testlib", name="testlib", folder_path=folder_path, module_name="testlib")


def _document(description=""):
    return {
        "format_version": 1,
        "meta": {"description": description},
        "nodes": {
            "n0": {"node_id": "n0", "registry_key": _INPUT, "position": [0, 0]},
            "n1": {"node_id": "n1", "registry_key": _OUTPUT, "position": [0, 0]},
        },
        "edges": {},
        "variables": {},
        "props": {},
        "subgraphs": {},
    }


@pytest.fixture
def factory_with_a_macro(tmp_path, library_system):
    """A NodeFactory over the real node registry plus a one-macro registry."""
    from haywire.core.macro.registry import MacroRegistry
    from haywire.core.node.factory import NodeFactory

    (tmp_path / "Blur.hwm").write_text(json.dumps(_document(description="Softens an image")))
    macro_registry = MacroRegistry()
    macro_registry.add_folder(str(tmp_path), _identity(str(tmp_path)))

    node_registry = library_system.get_node_registry()
    return NodeFactory(node_registry, macro_registry)


def test_the_macro_appears_in_the_menu_under_its_library(factory_with_a_macro):
    menu = factory_with_a_macro.get_menu_structure()

    assert "testlib/macros" in menu
    assert [info.identity.label for info in menu["testlib/macros"]] == ["Blur"]


def test_the_menu_still_holds_node_classes(factory_with_a_macro):
    """Both registries are read, not one instead of the other."""
    menu = factory_with_a_macro.get_menu_structure()

    assert len(menu) > 1
    assert any(path != "testlib/macros" for path in menu)


def test_a_macro_is_found_by_label(factory_with_a_macro):
    results = factory_with_a_macro.search_nodes("blur")

    assert [info.identity.registry_key for info in results] == ["testlib:macro:Blur"]


def test_a_macro_is_found_by_description(factory_with_a_macro):
    results = factory_with_a_macro.search_nodes("softens")

    assert [info.identity.registry_key for info in results] == ["testlib:macro:Blur"]


def test_the_macro_key_is_listed(factory_with_a_macro):
    assert "testlib:macro:Blur" in factory_with_a_macro.list_all_nodes()


def test_node_info_resolves_for_a_macro_key(factory_with_a_macro):
    info = factory_with_a_macro.get_node_info("testlib:macro:Blur")

    assert info is not None
    assert info.identity.label == "Blur"
    assert info.library.name == "testlib"


def test_a_factory_without_a_macro_registry_still_works(library_system):
    """The macro registry is optional; every existing caller passes one argument."""
    from haywire.core.node.factory import NodeFactory

    factory = NodeFactory(library_system.get_node_registry())

    assert factory.get_menu_structure()
    assert factory.get_node_info("testlib:macro:Blur") is None
    assert not [k for k in factory.list_all_nodes() if ":macro:" in k]


def test_a_hidden_macro_is_not_offered(tmp_path, library_system):
    """list_visible_names is what the menu reads, for macros as for nodes."""
    from haywire.core.macro.registry import MacroRegistry
    from haywire.core.node.factory import NodeFactory

    (tmp_path / "Blur.hwm").write_text(json.dumps(_document()))
    macro_registry = MacroRegistry()
    macro_registry.add_folder(str(tmp_path), _identity(str(tmp_path)))
    template = macro_registry.template("testlib:macro:Blur")
    assert template is not None
    template.identity.hidden = True

    factory = NodeFactory(library_system.get_node_registry(), macro_registry)

    assert "testlib/macros" not in factory.get_menu_structure()
    assert factory.search_nodes("blur") == []
