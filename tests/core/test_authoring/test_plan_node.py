"""Planning a node clone: the read-only half of the New Node pipeline.

``plan_node`` reads a node class's source and answers what file its clone
would become. These tests drive it over fixture modules (see ``conftest.py``)
and check the rewritten text by parsing it, not by string equality, so they
hold across formatting.
"""

import ast

import pytest

from haywire.core.authoring import (
    NodeFields,
    class_name_refusal,
    default_fields,
    module_stem,
    plan_node,
    suggest_class_name,
)

pytestmark = [pytest.mark.unit, pytest.mark.core]


def _fields(label="Blur", class_name="BlurNode", **kw) -> NodeFields:
    return NodeFields(
        label=label,
        class_name=class_name,
        menu=kw.pop("menu", "mine"),
        search_tags=kw.pop("search_tags", ["t"]),
        description=kw.pop("description", "d"),
    )


def _decorator_keywords(source: str, class_name: str) -> dict[str, str]:
    tree = ast.parse(source)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name)
    call = next(d for d in cls.decorator_list if isinstance(d, ast.Call))
    return {kw.arg or "**": ast.get_source_segment(source, kw.value) or "" for kw in call.keywords}


def _relative_imports(source: str) -> list[ast.ImportFrom]:
    return [n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.ImportFrom) and n.level > 0]


# ── names ────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("label", "expected"),
    [("Blur filter", "BlurFilter"), ("  3d  mesh", "DMesh"), ("Élan vital", "ElanVital"), ("!!!", "MyNode")],
)
def test_a_class_name_derives_from_the_label(label, expected):
    assert suggest_class_name(label) == expected


@pytest.mark.parametrize(
    ("name", "stem"), [("BlurFilter", "blur_filter"), ("XMLNode", "xml_node"), ("A", "a")]
)
def test_the_file_stem_is_the_snake_cased_class_name(name, stem):
    assert module_stem(name) == stem


@pytest.mark.parametrize("name", ["", "1Node", "my-node", "class", "Nöde"])
def test_an_invalid_class_name_is_refused(name):
    assert class_name_refusal(name) is not None


@pytest.mark.parametrize("name", ["DevTools", "BlurDev", "MyDevice"])
def test_a_class_name_whose_file_the_scan_skips_is_refused(name):
    refusal = class_name_refusal(name)
    assert refusal is not None
    assert "would not register" in refusal


def test_default_fields_come_from_the_resolved_identity(src_modules):
    _single, multi = src_modules
    fields = default_fields(multi.ChildNode)
    assert fields.label == "Child Copy"
    assert fields.class_name == "ChildCopy"
    # Inherited from ParentNode's decorator, never stated on ChildNode's own.
    assert fields.menu == "src/family"
    assert fields.search_tags == ["family"]


# ── a module declaring one node is copied whole ─────────────────────────────


def test_a_single_class_module_is_copied_whole(src_modules, target, libraries):
    single, _multi = src_modules
    plan = plan_node(single.SingleNode, _fields(), target, libraries)

    assert plan.refusal is None
    assert plan.mode == "whole"
    assert plan.path == target.folder / "blur_node.py"
    assert plan.registry_key == "dst:node:BlurNode"
    assert plan.module_name == "haybale_dst.nodes.blur_node"
    assert plan.free_names == []
    assert '"""A module declaring one node."""' in plan.source


def test_relative_imports_are_rewritten_at_top_level_and_inside_methods(src_modules, target, libraries):
    single, _multi = src_modules
    plan = plan_node(single.SingleNode, _fields(), target, libraries)

    assert _relative_imports(plan.source) == []
    assert "from haybale_src.helpers import SCALE" in plan.source
    assert "from haybale_src import helpers" in plan.source
    assert dict(plan.rewritten_imports) == {
        "from ..helpers import SCALE": "from haybale_src.helpers import SCALE",
        "from .. import helpers": "from haybale_src import helpers",
    }


def test_the_class_and_references_to_it_are_renamed(src_modules, target, libraries):
    single, _multi = src_modules
    plan = plan_node(single.SingleNode, _fields(), target, libraries)

    assert "class BlurNode(BaseNode):" in plan.source
    assert "super(BlurNode, self)" in plan.source
    assert "SingleNode" not in plan.source


def test_the_decorator_states_the_four_fields_and_drops_what_a_clone_never_inherits(
    src_modules, target, libraries
):
    single, _multi = src_modules
    fields = _fields(label='Say "hi"', menu="a/b", search_tags=["x", "y"], description="line1\nline2")
    plan = plan_node(single.SingleNode, fields, target, libraries)

    kws = _decorator_keywords(plan.source, "BlurNode")
    assert set(kws) == {"label", "description", "menu", "search_tags", "node_type"}
    assert ast.literal_eval(kws["label"]) == 'Say "hi"'
    assert ast.literal_eval(kws["description"]) == "line1\nline2"
    assert ast.literal_eval(kws["menu"]) == "a/b"
    assert ast.literal_eval(kws["search_tags"]) == ["x", "y"]
    # A keyword the wizard does not own survives as written.
    assert kws["node_type"] == "NodeType.DATA"


def test_the_class_docstring_is_copied_as_written(src_modules, target, libraries):
    single, _multi = src_modules
    plan = plan_node(single.SingleNode, _fields(), target, libraries)
    assert '"""Outputs SCALE."""' in plan.source


def test_planning_writes_nothing(src_modules, target, libraries):
    single, _multi = src_modules
    before = sorted(p.name for p in target.folder.iterdir())
    plan_node(single.SingleNode, _fields(), target, libraries)
    assert sorted(p.name for p in target.folder.iterdir()) == before


# ── a module declaring several nodes is extracted ───────────────────────────


def test_a_multi_class_module_extracts_the_class_and_imports(src_modules, target, libraries):
    _single, multi = src_modules
    plan = plan_node(multi.ChildNode, _fields(), target, libraries)

    assert plan.refusal is None
    assert plan.mode == "extract"
    tree = ast.parse(plan.source)
    classes = [n.name for n in tree.body if isinstance(n, ast.ClassDef)]
    # Neither the sibling it subclasses nor the unrelated ones are copied.
    assert classes == ["BlurNode"]
    assert any(isinstance(n, ast.If) for n in tree.body), "the TYPE_CHECKING block is kept"
    assert "UNUSED" not in plan.source


def test_module_level_names_the_class_uses_are_imported_from_the_source_module(
    src_modules, target, libraries
):
    _single, multi = src_modules
    plan = plan_node(multi.ChildNode, _fields(), target, libraries)

    assert plan.free_names == ["LIMIT", "ParentNode"]
    assert "from haybale_src.nodes.multi import LIMIT, ParentNode" in plan.source


def test_a_helper_function_and_a_constant_are_free_names(src_modules, target, libraries):
    _single, multi = src_modules
    plan = plan_node(multi.ParentNode, _fields(), target, libraries)
    assert plan.free_names == ["LIMIT", "_Base", "_helper"]


def test_inherited_menu_and_tags_are_stated_explicitly(src_modules, target, libraries):
    _single, multi = src_modules
    plan = plan_node(multi.ChildNode, default_fields(multi.ChildNode), target, libraries)

    kws = _decorator_keywords(plan.source, "ChildCopy")
    assert ast.literal_eval(kws["menu"]) == "src/family"
    assert ast.literal_eval(kws["search_tags"]) == ["family"]


def test_a_string_annotation_of_the_class_is_renamed(src_modules, target, libraries):
    _single, multi = src_modules
    plan = plan_node(multi.ChildNode, _fields(), target, libraries)
    assert '-> "BlurNode"' in plan.source


def test_template_and_hidden_are_dropped(src_modules, target, libraries):
    _single, multi = src_modules
    plan = plan_node(multi.TemplatedNode, _fields(), target, libraries)
    kws = _decorator_keywords(plan.source, "BlurNode")
    assert "template" not in kws
    assert "hidden" not in kws


# ── refusals ─────────────────────────────────────────────────────────────────


class _Taken:
    def __init__(self, *keys):
        self._keys = set(keys)

    def has(self, registry_key: str) -> bool:
        return registry_key in self._keys


def test_a_key_already_registered_is_refused(src_modules, target, libraries):
    single, _multi = src_modules
    plan = plan_node(single.SingleNode, _fields(), target, libraries, registry=_Taken("dst:node:BlurNode"))
    assert plan.refusal is not None
    assert "already registered" in plan.refusal


def test_an_existing_file_is_refused(src_modules, target, libraries):
    single, _multi = src_modules
    (target.folder / "blur_node.py").write_text("")
    plan = plan_node(single.SingleNode, _fields(), target, libraries)
    assert plan.refusal is not None
    assert "already exists" in plan.refusal


@pytest.mark.parametrize("class_name", ["", "1Bad", "DevNode"])
def test_an_unusable_class_name_is_refused(src_modules, target, libraries, class_name):
    single, _multi = src_modules
    plan = plan_node(single.SingleNode, _fields(class_name=class_name), target, libraries)
    assert plan.refusal is not None
    assert plan.source == ""


def test_an_empty_label_is_refused(src_modules, target, libraries):
    single, _multi = src_modules
    plan = plan_node(single.SingleNode, _fields(label="  "), target, libraries)
    assert plan.refusal == "Enter a label."


def test_unreadable_source_is_refused(target, libraries):
    from haywire.core.node import BaseNode, node

    namespace: dict = {"BaseNode": BaseNode, "node": node}
    exec("@node(label='X')\nclass Ghost(BaseNode):\n    pass\n", namespace)
    plan = plan_node(namespace["Ghost"], _fields(), target, libraries)
    assert plan.refusal is not None
    assert "cannot be read" in plan.refusal
