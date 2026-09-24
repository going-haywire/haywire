"""Node templates and authoring targets, over the fully loaded library system."""

import ast
import inspect
import time
from pathlib import Path

import pytest

from haywire.core.authoring import (
    AuthoringTarget,
    NodeFields,
    authoring_targets,
    default_fields,
    is_clone_source,
    plan_node,
    write_node,
)
from haywire.core.registry.base import FileChangeEvent, FileEventType

from .conftest import FakeLibraries

pytestmark = pytest.mark.integration

_TEMPLATE_KEY = "haywire-core:node:DataNodeTemplate"


@pytest.fixture
def factory(library_system):
    from haywire.core.node.factory import NodeFactory

    return library_system.injector.get(NodeFactory)


def _template_classes(factory):
    return [
        factory.node_registry.get(info.identity.registry_key)
        for infos in factory.list_templates().values()
        for info in infos
    ]


# ── templates ────────────────────────────────────────────────────────────────


def test_a_template_is_hidden_from_the_menu_and_search(factory):
    menu_keys = {
        info.identity.registry_key for infos in factory.get_menu_structure().values() for info in infos
    }
    search_keys = {info.identity.registry_key for info in factory.search_nodes("data")}
    assert _TEMPLATE_KEY not in menu_keys
    assert _TEMPLATE_KEY not in search_keys


def test_a_template_is_listed_by_list_templates(factory):
    templates = factory.list_templates()
    keys = {info.identity.registry_key for infos in templates.values() for info in infos}
    assert _TEMPLATE_KEY in keys
    assert all(info.identity.template for infos in templates.values() for info in infos)


def test_template_true_implies_hidden():
    from haywire.core.node import BaseNode, node

    @node(template=True)
    class _T(BaseNode):
        pass

    assert _T.class_identity.hidden is True


def test_a_template_is_absent_from_the_generated_docs(library_system):
    from haywire_studio.packaging.docs.extract import extract_library
    from haywire_studio.packaging.docs.render import render_quickref

    doc = extract_library(library_system, "haywire-core")
    assert "DataNodeTemplate" not in render_quickref(doc)


def test_every_template_holds_the_template_contract(factory):
    """Absolute imports only, and no module-level names besides imports and the template itself."""
    for cls in _template_classes(factory):
        source_file = inspect.getsourcefile(cls)
        assert source_file is not None
        tree = ast.parse(Path(source_file).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert node.level == 0, f"{cls.__name__}: relative import"
        for stmt in tree.body:
            is_docstring = isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant)
            is_import = isinstance(stmt, (ast.Import, ast.ImportFrom))
            is_template = isinstance(stmt, ast.ClassDef)
            assert is_docstring or is_import or is_template, f"{cls.__name__}: module-level {stmt!r}"


def test_a_template_clone_needs_no_free_names_or_links(factory, library_system, target, dst_identity):
    libraries = FakeLibraries(dst_identity, delegate=library_system.get_library_registry())
    for cls in _template_classes(factory):
        plan = plan_node(cls, default_fields(cls), target, libraries)
        assert plan.refusal is None, plan.refusal
        assert plan.free_names == []
        assert plan.linked_additions == []


def test_a_template_clone_instantiates_and_passes_its_testrun(
    factory, library_system, target, dst_identity, dst_library
):
    from haywire.core.graph.base import BaseGraph
    from haywire.core.graph.scheduler import SyncScheduler

    cls = factory.node_registry.get(_TEMPLATE_KEY)
    libraries = FakeLibraries(dst_identity, delegate=library_system.get_library_registry())
    plan = plan_node(cls, default_fields(cls), target, libraries)
    write_node(plan, dst_library)

    registry = factory.node_registry
    event = FileChangeEvent(str(plan.path), FileEventType.CREATED, dst_identity, time.time())
    registry.event_dispatcher(event)
    graph = BaseGraph("clone", validation_scheduler=SyncScheduler())
    try:
        wrapper = graph.create_node_wrapper(plan.registry_key)
        assert wrapper is not None
        assert type(wrapper.node).__name__ == "MyDataNode"
        assert wrapper.node.on_testrun() == (True, None)
    finally:
        graph.cleanup()
        plan.path.unlink()
        registry.event_dispatcher(
            FileChangeEvent(str(plan.path), FileEventType.DELETED, dst_identity, time.time())
        )
    assert registry.get(plan.registry_key) is None


# ── clone sources ────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "key",
    [
        "haywire-core:node:RerouteNode",
        "haywire-core:node:GraphNode",
        "haywire-core:node:MacroNode",
        "haywire-core:node:SubgraphInputNode",
        _TEMPLATE_KEY,
    ],
)
def test_framework_role_nodes_and_templates_are_not_clone_sources(factory, key):
    cls = factory.node_registry.get(key)
    assert cls is not None, key
    assert not is_clone_source(cls)


def test_an_ordinary_node_is_a_clone_source(factory):
    assert is_clone_source(factory.node_registry.get("haybale-testing:node:TestAddFloatNode"))


def test_a_clone_of_another_library_links_it(factory, library_system, target, dst_identity):
    cls = factory.node_registry.get("haybale-testing:node:SettingsNode")
    libraries = FakeLibraries(dst_identity, delegate=library_system.get_library_registry())
    fields = NodeFields(label="Adder", class_name="Adder", menu="m")
    plan = plan_node(cls, fields, target, libraries)
    assert plan.refusal is None, plan.refusal
    assert "haybale_testing" in plan.linked_additions


# ── authoring targets ────────────────────────────────────────────────────────


@pytest.mark.parametrize("registry_name", ["NodeRegistry", "MacroRegistry"])
def test_targets_are_editable_libraries_that_registered_the_kind_folder(library_system, registry_name):
    from haywire.core.macro.registry import MacroRegistry
    from haywire.core.node.registry import NodeRegistry

    registry_cls: type = {"NodeRegistry": NodeRegistry, "MacroRegistry": MacroRegistry}[registry_name]
    library_registry = library_system.get_library_registry()
    registry = library_system.injector.get(registry_cls)

    targets = authoring_targets(library_system, registry_cls)
    assert targets, "the repo's editable barn libraries are targets"
    registered = {identity.name for identity in registry._folder_to_library.values()}
    for target in targets:
        assert isinstance(target, AuthoringTarget)
        assert library_registry.get_library_install_type(target.library_id).is_editable()
        assert target.library_id in registered
    assert "haywire-core" not in {t.library_id for t in targets}, "builtin is not editable"


def test_the_project_library_sorts_first(library_system, project_root):
    from haywire.core.node.registry import NodeRegistry

    targets = authoring_targets(library_system, NodeRegistry, project_root)
    assert targets[0].is_project_library
    assert [t.is_project_library for t in targets] == sorted(
        (t.is_project_library for t in targets), reverse=True
    )


def test_targets_report_whether_the_library_is_watched(library_system):
    from haywire.core.node.registry import NodeRegistry

    library_registry = library_system.get_library_registry()
    for target in authoring_targets(library_system, NodeRegistry):
        library = library_registry.get_library(target.library_id)
        assert target.is_watched == library.is_watched
