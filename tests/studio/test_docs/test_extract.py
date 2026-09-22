import json

import pytest
from haywire.core.di.config import create_library_system_service
from haywire_studio.packaging.docs.extract import _record_from_class, extract_library


@pytest.fixture(scope="module")
def service(project_root):
    svc = create_library_system_service(
        workspace_root=str(project_root),
        enable_file_watching=False,
        watch_settings=False,
    )
    return svc


@pytest.mark.integration
def test_extract_collects_components_with_identity(service):
    doc = extract_library(service, "haybale-testing")
    assert doc.library_id == "haybale-testing"
    assert doc.components, "testing library should expose components"
    for rec in doc.components:
        assert rec.registry_key.split(":")[0] == "haybale-testing"
        assert rec.kind in {
            "node",
            "macro",
            "type",
            "adapter",
            "widget",
            "skin",
            "setting",
            "theme",
            "panel",
            "editor",
            "state",
            "farmhand",
        }
        assert isinstance(rec.label, str)


@pytest.mark.integration
def test_extract_farmhand_carries_input_schema(service):
    doc = extract_library(service, "haybale-testing")
    farmhands = [r for r in doc.components if r.kind == "farmhand"]
    if farmhands:
        assert "input_schema" in farmhands[0].extra


@pytest.mark.integration
def test_nodes_carry_ports_from_instance(service):
    doc = extract_library(service, "haybale-testing")
    nodes = [r for r in doc.components if r.kind == "node" and not r.hidden]
    assert nodes, "testing should expose visible nodes"
    # At least one node should declare at least one port once instantiated.
    assert any(n.ports for n in nodes)
    for n in nodes:
        for p in n.ports:
            assert p.direction in ("inlet", "outlet", "config")


_INPUT = "haywire-core:node:SubgraphInputNode"
_OUTPUT = "haywire-core:node:SubgraphOutputNode"


@pytest.fixture
def documented_macro(tmp_path, service):
    """One macro registered under ``haybale-testing``, removed again after.

    The registry is a singleton on the service, so the folder is removed to
    keep the key out of the module-scoped service the other tests share.
    """
    from haywire.core.library.identity import LibraryIdentity
    from haywire.core.macro.registry import MacroRegistry
    from haywire_studio.packaging.docs.extract import service_registry

    document = {
        "format_version": 1,
        "meta": {"description": "Blurs a frame."},
        "nodes": {
            "b_in": {"node_id": "b_in", "registry_key": _INPUT, "position": [0, 0]},
            "b_out": {"node_id": "b_out", "registry_key": _OUTPUT, "position": [200, 0]},
        },
        "edges": {},
        "variables": {},
        "props": {},
        "subgraphs": {},
    }
    (tmp_path / "Blur.hwm").write_text(json.dumps(document))

    identity = LibraryIdentity(
        label="Testing",
        name="haybale-testing",
        folder_path=str(tmp_path),
        module_name="haybale_testing",
    )
    registry = service_registry(service, MacroRegistry)
    registry.add_folder(str(tmp_path), identity)
    try:
        yield "haybale-testing:macro:Blur"
    finally:
        registry.remove_folder(str(tmp_path), identity)


@pytest.mark.integration
def test_a_macro_is_documented_like_a_node(service, documented_macro):
    """Decision 19: a macro is documented by its interface, not by a docstring."""
    doc = extract_library(service, "haybale-testing")
    macros = [r for r in doc.components if r.kind == "macro"]
    assert [m.registry_key for m in macros] == [documented_macro]

    macro = macros[0]
    assert macro.label == "Blur"
    assert macro.description == "Blurs a frame."
    assert macro.menu == "macros/Testing"
    # The template is an instance, so it carries no class docstring to inherit.
    assert macro.docstring == ""


class _FakeIdentity:
    """Bare identity stand-in — _record_from_class only reads via getattr."""


class _BaseWithDocstring:
    """This is the base class's own docstring."""

    class_identity = _FakeIdentity()


class _SubclassWithoutDocstring(_BaseWithDocstring):
    class_identity = _FakeIdentity()


class _SubclassWithOwnDocstring(_BaseWithDocstring):
    """This subclass has its own docstring."""

    class_identity = _FakeIdentity()


def test_record_from_class_does_not_inherit_ancestor_docstring():
    """A subclass with no docstring of its own must not silently pick up
    an ancestor's docstring via MRO (inspect.getdoc's behavior) — that
    would fabricate documentation that was never actually written for it."""
    rec = _record_from_class("node", "lib:node:sub", _SubclassWithoutDocstring)
    assert rec.docstring == ""


def test_record_from_class_uses_own_docstring_when_present():
    rec = _record_from_class("node", "lib:node:base", _BaseWithDocstring)
    assert rec.docstring == "This is the base class's own docstring."

    rec_sub = _record_from_class("node", "lib:node:subown", _SubclassWithOwnDocstring)
    assert rec_sub.docstring == "This subclass has its own docstring."
