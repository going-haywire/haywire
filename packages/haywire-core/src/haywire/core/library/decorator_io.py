"""Text-level rewriters for the ``@library(...)`` decorator.

These helpers operate on the raw source of a library's ``__init__.py`` —
no AST, no import of the library itself, just regex on the decorator call.
Used by both the marketplace Edit dialog (runtime UI) and ``haywire share``
(CLI author tooling); the helpers themselves are generic and live in core
so neither side has to import the other.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal


def norm_dep(name: str) -> str:
    """Normalize a dep name to a comparable form (underscores, lowercase).

    Shared by ``haywire share``'s drift detection/union logic and
    :func:`merge_decorator_list_field`'s union mode, so both sides agree on
    when two dependency spellings (``haybale-core`` vs. ``haybale_core``)
    name the same thing.
    """
    return re.sub(r"[-_.]+", "_", name).lower()


def _get_decorator_list_field(content: str, field: str) -> list[str]:
    """Read the declared string values of a list field in the decorator source.

    Mirrors :func:`_set_decorator_list_field`'s pattern-matching so reads and
    writes agree on where the field lives. Returns ``[]`` if the field is
    absent. Values are converted from module form (underscores) to pip
    package form (hyphens) — matching the historical
    ``_read_library_dependencies`` reader this generalizes, since decorator
    ``dependencies=[...]`` entries are module names but are compared and
    reported as pip package names elsewhere in the share pipeline.
    """
    match = re.search(rf"{re.escape(field)}\s*=\s*\[([^\]]*)\]", content, re.DOTALL)
    if not match:
        return []
    raw = re.findall(r"['\"]([^'\"]+)['\"]", match.group(1))
    return [v.replace("_", "-") for v in raw]


def merge_decorator_list_field(
    init_file: Path, field: str, values: list[str], *, mode: Literal["union", "replace"]
) -> None:
    """Rewrite a list field in ``init_file``'s ``@library(...)`` decorator, on disk.

    Owns the read -> decide new value -> :func:`_set_decorator_list_field` ->
    write dance that both ``haywire_studio.packaging.share.apply_drift_fix`` and
    ``haywire_studio.packaging.share.pipeline.pipeline.SharePipeline.apply_drift_replace``
    used to each implement independently.

    ``mode="union"``: *values* are the entries to add — normalized via
    :func:`norm_dep` and merged with whatever the file currently declares
    (deduplicated by normalized form), preserving existing declarations.
    This is the additive semantics ``apply_drift_fix`` needs.

    ``mode="replace"``: *values* is the complete new field value, written
    as-is (sorted by the caller beforehand if desired). This is the
    destructive semantics ``apply_drift_replace`` needs.

    Does not check ``init_file.exists()`` — callers that need to skip a
    missing file (or translate the resulting ``OSError`` into a
    domain-specific error) do so around this call.
    """
    content = init_file.read_text()
    if mode == "union":
        current = _get_decorator_list_field(content, field)
        current_norm = {norm_dep(d) for d in current}
        new_list = list(current)
        for candidate in values:
            if norm_dep(candidate) not in current_norm:
                new_list.append(candidate)
        new_value = sorted(new_list)
    else:
        new_value = sorted(values)
    content = _set_decorator_list_field(content, field, new_value)
    init_file.write_text(content)


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
