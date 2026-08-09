"""Reading label and sibling-library metadata out of a library's ``haybale.toml``.

Both functions used to regex the ``@library(...)`` call in ``__init__.py``. They
read the TOML now: the fields moved there, and a TOML parse cannot be defeated by
quoting, line wrapping, or a comment that happens to contain the field name — all
of which the regexes could be.

Lenient by design. Every caller here is building a *report* or a scaffold entry,
where a library that cannot be read should degrade to a fallback rather than
abort the run. The strict reader lives in
:mod:`haywire.core.library.haybale_toml` and is used at decoration time, where a
library that cannot name itself must not load.
"""

from __future__ import annotations

from pathlib import Path

from haywire.core.library.haybale_toml import read_haybale_toml_lenient


def _read_library_label(module_dir: Path, fallback: str) -> str:
    """The library's declared label, or *fallback* when it declares none."""
    return read_haybale_toml_lenient(module_dir).get("label") or fallback


def _read_library_dependencies(module_dir: Path) -> list[str]:
    """The library's ``linked_libraries``, as **pip** names.

    Declared as module names (``haybale_studio``); converted here to the
    distribution form (``haybale-studio``) because the callers — the marketplace
    install gate and the ``[[heaps]]`` writer — match against distribution names.
    """
    declared = read_haybale_toml_lenient(module_dir).get("linked_libraries") or []
    return [m.replace("_", "-") for m in declared]
