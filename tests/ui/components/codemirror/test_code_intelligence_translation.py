"""Unit tests for the element-side CodeMirror translation helpers."""

from __future__ import annotations

import haywire.core.graph.editor  # noqa: F401  (import-order guard per CLAUDE.md)

from haywire.ui.components.codemirror.code_intelligence import (
    _jedi_kind_to_cm_type,
    _boost,
    _render_doc_html,
)


def test_jedi_kind_maps_known_types():
    assert _jedi_kind_to_cm_type("function") == "function"
    assert _jedi_kind_to_cm_type("class") == "class"
    assert _jedi_kind_to_cm_type("module") == "namespace"
    assert _jedi_kind_to_cm_type("instance") == "variable"


def test_jedi_kind_unknown_falls_back_to_text():
    assert _jedi_kind_to_cm_type("nonsense") == "text"


def test_boost_orders_public_over_private_over_dunder():
    assert _boost("add") == 1
    assert _boost("_internal") == -1
    assert _boost("__dunder__") == -2


def test_render_doc_html_wraps_signature_in_python_codeblock():
    html = _render_doc_html("add(spec) -> DataPort", "Add a port.")
    # signature becomes a fenced python block -> pygments codehilite wrapper
    assert "codehilite" in html
    assert "Add a port." in html


def test_render_doc_html_empty_returns_empty_string():
    assert _render_doc_html(None, None) == ""


def test_render_doc_html_preserves_docstring_line_structure():
    # break-on-newline keeps Args:/bullets on their own lines
    doc = "Summary.\n\nArgs:\n    spec: the spec\n- bullet one\n- bullet two"
    html = _render_doc_html(None, doc)
    assert "<br" in html  # single newlines became <br/>


def test_render_doc_html_does_not_italicize_underscored_identifiers():
    # code-friendly extra: as_inlet must NOT become as<em>inlet
    html = _render_doc_html(None, "Uses FLOAT.as_inlet() here.")
    assert "as_inlet" in html
    assert "as<em>inlet" not in html
