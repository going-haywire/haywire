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
    yield svc


@pytest.mark.integration
def test_extract_collects_components_with_identity(service):
    doc = extract_library(service, "testing")
    assert doc.library_id == "testing"
    assert doc.components, "testing library should expose components"
    for rec in doc.components:
        assert rec.registry_key.split(":")[0] == "testing"
        assert rec.kind in {
            "node",
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
    doc = extract_library(service, "testing")
    farmhands = [r for r in doc.components if r.kind == "farmhand"]
    if farmhands:
        assert "input_schema" in farmhands[0].extra


@pytest.mark.integration
def test_nodes_carry_ports_from_instance(service):
    doc = extract_library(service, "testing")
    nodes = [r for r in doc.components if r.kind == "node" and not r.hidden]
    assert nodes, "testing should expose visible nodes"
    # At least one node should declare at least one port once instantiated.
    assert any(n.ports for n in nodes)
    for n in nodes:
        for p in n.ports:
            assert p.direction in ("inlet", "outlet", "config")


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
