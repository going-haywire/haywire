"""Reusable CodeMirror code-intelligence aspect.

Attaches jedi-backed completion + hover documentation to any ``ui.codemirror``
element by injecting CodeMirror autocomplete + hoverTooltip extensions that call
an editor-agnostic HTTP provider. ALL CodeMirror-specific knowledge lives here:
jedi-kind -> CM completion ``type``, the ``boost`` sort policy, markdown -> HTML
doc rendering, and the ``hw-cm-doc`` panel class. The provider returns only plain
data in jedi's own vocabulary.

The completion/hover sources read the editor's live language and no-op unless it
is in ``language_filter`` (default ``("Python",)``), so this is safe to attach to
a polymorphic editor that also opens TOML/JSON/Markdown/plain-text files.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

import markdown2

if TYPE_CHECKING:
    from nicegui import ui

# break-on-newline keeps the line structure of plain-text Python docstrings
# (Args:/Returns:/bullets on their own lines); code-friendly stops underscores
# in identifiers (as_inlet) being parsed as emphasis.
_MD_EXTRAS = ["fenced-code-blocks", "tables", "code-friendly", "break-on-newline"]


def _jedi_kind_to_cm_type(kind: str) -> str:
    """Map a jedi ``Completion.type`` string to a CodeMirror completion type."""
    return {
        "function": "function",
        "class": "class",
        "module": "namespace",
        "instance": "variable",
        "keyword": "keyword",
        "property": "property",
        "param": "variable",
        "path": "text",
        "statement": "variable",
    }.get(kind, "text")


def _boost(name: str) -> int:
    """CodeMirror sort hint: public > private > dunder."""
    if name.startswith("__"):
        return -2
    if name.startswith("_"):
        return -1
    return 1


def _render_doc_html(signature: str | None, docstring: str | None) -> str:
    """Render a signature + docstring into highlighted HTML for the doc panel.

    The signature is wrapped in a fenced Python block so markdown2's
    fenced-code-blocks extra (with pygments) highlights it; the docstring is
    rendered as markdown prose.
    """
    parts: list[str] = []
    if signature:
        parts.append(f"```python\n{signature}\n```")
    if docstring:
        parts.append(docstring)
    if not parts:
        return ""
    return markdown2.markdown("\n\n".join(parts), extras=_MD_EXTRAS)


def attach_code_intelligence(
    editor: "ui.codemirror",
    *,
    completion_url: str = "/api/code-intel/complete",
    info_url: str = "/api/code-intel/info",
    hover_url: str = "/api/code-intel/hover",
    language_filter: Sequence[str] = ("Python",),
    path: str | None = None,
) -> None:
    """Placeholder — real implementation added in Task 4."""
    raise NotImplementedError
