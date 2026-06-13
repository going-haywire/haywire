"""Unit tests for the jedi-backed code-intelligence provider helpers."""

from __future__ import annotations

import jedi

from haywire_studio.code_intelligence import _signature_and_doc, _completion_payload


def test_completion_payload_returns_plain_jedi_vocabulary():
    code = "import os\nos."
    script = jedi.Script(code)
    completions = script.complete(2, 3)
    payload = _completion_payload(completions, explicit=False)
    assert payload  # os has many attributes
    first = payload[0]
    # plain data only: name + kind + signature + docstring, NO type/boost/html
    assert set(first.keys()) == {"name", "kind", "signature", "docstring"}
    assert "<" not in first["docstring"]  # not HTML


def test_completion_payload_filters_dunders_when_not_explicit():
    code = "import os\nos."
    completions = jedi.Script(code).complete(2, 3)
    names = {c["name"] for c in _completion_payload(completions, explicit=False)}
    assert not any(n.startswith("__") for n in names)


def test_completion_payload_keeps_dunders_when_explicit():
    code = "import os\nos."
    completions = jedi.Script(code).complete(2, 3)
    names = {c["name"] for c in _completion_payload(completions, explicit=True)}
    assert any(n.startswith("__") for n in names)


def test_signature_and_doc_returns_plain_text():
    code = "def greet(name: str) -> str:\n    '''Say hello.'''\n    return name\ngreet"
    names = jedi.Script(code).help(4, 5)
    sig, doc = _signature_and_doc(names[0])
    assert "greet(name" in sig
    assert "Say hello." in doc
    assert "<" not in sig and "<" not in doc  # plain text, not HTML
