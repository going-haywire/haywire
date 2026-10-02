"""Rewrite saved graphs and macros from the haybale-core EXEC and CALLBACK keys to the builtin ones.

One-off: delete this script once every saved graph in the repo has been rewritten.

``EXEC`` and ``CALLBACK`` moved from haybale-core to the builtin library, which
changed their registry keys, and each now has its own module. A saved port names
its type in its ``recipe`` and in the identity snapshot of its ``kwargs``; this
rewrites both, and the snapshot's ``module`` for the two moved classes only. A
file is written back in the exact JSON formatting it was read in, so a diff shows
only the changed values.

Usage::

    uv run python -m scripts.migrate_signal_type_keys --check graphs barn/haybale-example
    uv run python -m scripts.migrate_signal_type_keys graphs barn/haybale-example

Directories are searched for ``*.haywire`` and ``*.hwm`` files. Exit status: 0 when
nothing is left to rewrite, 1 when ``--check`` found old keys, 2 when a file's
formatting could not be reproduced (that file is left unchanged).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

OLD_TO_NEW_KEYS = {
    "haybale-core:type:EXEC": "haywire-core:type:EXEC",
    "haybale-core:type:CALLBACK": "haywire-core:type:CALLBACK",
}
OLD_MODULE = "haybale_core.types.specs"
NEW_MODULES = {
    "EXEC": "haywire.barn.builtin.types.exec",
    "CALLBACK": "haywire.barn.builtin.types.callback",
}
SUFFIXES = (".haywire", ".hwm")


class FormatNotReproducibleError(ValueError):
    """The file's JSON formatting matches none of the formats the app writes."""


def rewrite_document(doc: Any) -> int:
    """Rewrite old keys and the moved classes' module in place; return the number of values changed."""
    count = 0
    if isinstance(doc, dict):
        # BYTES, LIST and DICT share the old module and stay in haybale-core.
        if doc.get("module") == OLD_MODULE and doc.get("class_name") in NEW_MODULES:
            doc["module"] = NEW_MODULES[doc["class_name"]]
            count += 1
        for key, value in doc.items():
            if isinstance(value, str) and value in OLD_TO_NEW_KEYS:
                doc[key] = OLD_TO_NEW_KEYS[value]
                count += 1
            else:
                count += rewrite_document(value)
    elif isinstance(doc, list):
        for index, value in enumerate(doc):
            if isinstance(value, str) and value in OLD_TO_NEW_KEYS:
                doc[index] = OLD_TO_NEW_KEYS[value]
                count += 1
            else:
                count += rewrite_document(value)
    return count


def _dump(doc: Any, indent: int | None, ensure_ascii: bool, suffix: str) -> str:
    return json.dumps(doc, indent=indent, ensure_ascii=ensure_ascii) + suffix


def detect_format(text: str) -> tuple[int | None, bool, str] | None:
    """Return the ``(indent, ensure_ascii, trailing suffix)`` that reproduces *text* exactly, or ``None``.

    ``indent=None`` is the compact form a hand-written dump produces; the app
    itself always writes ``indent=2``.
    """
    doc = json.loads(text)
    for indent in (2, None):
        for ensure_ascii in (False, True):
            for suffix in ("", "\n"):
                if _dump(doc, indent, ensure_ascii, suffix) == text:
                    return indent, ensure_ascii, suffix
    return None


def migrate_file(path: Path, *, check: bool = False) -> int:
    """Rewrite *path* in place (unless *check*) and return the number of values changed.

    Raises:
        FormatNotReproducibleError: The file's formatting matches no format the app writes.
    """
    text = path.read_text(encoding="utf-8")
    fmt = detect_format(text)
    if fmt is None:
        raise FormatNotReproducibleError(f"{path}: formatting not reproducible, left unchanged")
    doc = json.loads(text)
    count = rewrite_document(doc)
    if count and not check:
        path.write_text(_dump(doc, *fmt), encoding="utf-8")
    return count


def _files(paths: list[str]) -> list[Path]:
    found: list[Path] = []
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            found.extend(sorted(p for p in path.rglob("*") if p.suffix in SUFFIXES))
        else:
            found.append(path)
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Rewrite saved graphs to the builtin EXEC and CALLBACK keys."
    )
    parser.add_argument("paths", nargs="+", help="graph/macro files or directories to search")
    parser.add_argument("--check", action="store_true", help="report old keys without writing")
    args = parser.parse_args(argv)

    found_old = False
    unreproducible = False
    for path in _files(args.paths):
        try:
            count = migrate_file(path, check=args.check)
        except FormatNotReproducibleError as error:
            print(error, file=sys.stderr)
            unreproducible = True
            continue
        if count:
            found_old = True
            print(f"{path}: {count} value(s) {'to rewrite' if args.check else 'rewritten'}")
    if unreproducible:
        return 2
    return 1 if args.check and found_old else 0


if __name__ == "__main__":
    sys.exit(main())
