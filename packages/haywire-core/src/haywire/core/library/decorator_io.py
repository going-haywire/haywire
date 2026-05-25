"""Text-level rewriters for the ``@library(...)`` decorator.

These helpers operate on the raw source of a library's ``__init__.py`` —
no AST, no import of the library itself, just regex on the decorator call.
Used by both the marketplace Edit dialog (runtime UI) and ``haywire share``
(CLI author tooling); the helpers themselves are generic and live in core
so neither side has to import the other.
"""

from __future__ import annotations

import re


def _set_decorator_list_field(content: str, field: str, values: list[str]) -> str:
    """Replace or insert a list field inside the @library(...) decorator.

    If the field already exists on a single line (e.g. ``tags=['a', 'b'],``),
    it is replaced in-place.  If it is absent (scaffolded libraries don't
    include tags/dependencies) it is inserted just before ``file_watcher=``,
    or before the closing ``)`` of the decorator as a fallback.
    """
    value_repr = repr(values)  # e.g. "['testing', 'development']"
    # Match the existing field line: optional leading whitespace, field=[ … ],?
    pattern = rf"([ \t]+{re.escape(field)}=)\[[^\]]*\],?"
    if re.search(pattern, content):
        return re.sub(pattern, rf"\g<1>{value_repr},", content)
    # Not present — insert before file_watcher= if it exists
    insert_line = f"    {field}={value_repr},\n"
    if "    file_watcher=" in content:
        return content.replace("    file_watcher=", insert_line + "    file_watcher=", 1)
    # Fallback: insert before the closing )\nclass line
    replacement = f"\n    {field}={value_repr}," + r"\g<1>"
    return re.sub(r"(\n\)\nclass )", replacement, content, count=1)
