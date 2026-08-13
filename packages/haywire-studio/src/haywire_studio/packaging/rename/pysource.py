"""Python self-reference rewriting.

Two things are mechanically rewritable:

* **Imports** — the AST proves a name is a module path.
* **Registry-key literals** — ``"haybale-foo:widget:X"`` has an unambiguous
  grammar, so a string starting ``<old-dist>:`` and matching it is certainly
  a key. ``barn/haybale-example/haybale_example/types/specs.py:9`` does
  exactly this; left unpatched the widget silently fails to resolve.

Everything else is REPORTED and left alone. A literal like
``~/.haywire/db/haybale_foo/`` is genuinely wrong after a rename, but the
data it names has not moved, so rewriting it would make it lie differently.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from .graphs import is_registry_key
from .model import FileChange, Occurrence


def _import_line_numbers(source: str, old_module: str) -> set[int]:
    """1-based line numbers of import statements naming *old_module*.

    Relative imports (``level > 0``) carry no module name and are skipped.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()

    lines: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == old_module or alias.name.startswith(old_module + "."):
                    lines.add(node.lineno)
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # relative — nothing to rewrite
                continue
            module = node.module or ""
            if module == old_module or module.startswith(old_module + "."):
                lines.add(node.lineno)
    return lines


def _import_name_pattern(old_module: str) -> re.Pattern[str]:
    """Match *old_module* as a whole dotted-path head, not a prefix of a longer name.

    Boundaries: start/end of string, whitespace, ``,``, ``;``, and ``.`` all count —
    everything a comma/semicolon-joined or dotted import can legally place next to a
    module name. An identifier character (letter/digit/underscore) on either side means
    it's part of a longer name (``haybale_foobar``) and must not match.
    """
    return re.compile(rf"(?<![\w.]){re.escape(old_module)}(?![\w])")


def _rewrite_import_line(line: str, old_module: str, new_module: str) -> str:
    """Replace every whole-name occurrence of *old_module* in an import line.

    Handles comma-joined (``import a, old_module, b``), semicolon-joined
    (``import old_module; import os``), dotted (``old_module.sub``), and aliased
    (``old_module as x``) forms alike — a single word-boundary-anchored substitution
    rather than positional string patterns, so it can't miss a valid syntax shape.
    """
    return _import_name_pattern(old_module).sub(new_module, line)


def _key_literal_pattern(old_dist: str) -> re.Pattern[str]:
    """Match a quoted string literal beginning ``<old_dist>:``."""
    return re.compile(rf"(['\"])({re.escape(old_dist)}:[^'\"]*)\1")


def _rewrite_key_literals(source: str, old_dist: str, new_dist: str) -> tuple[str, int]:
    """Rewrite quoted registry-key literals belonging to *old_dist*."""
    count = 0

    def _sub(match: re.Match[str]) -> str:
        nonlocal count
        quote, value = match.group(1), match.group(2)
        if not is_registry_key(value):
            return match.group(0)
        count += 1
        return f"{quote}{new_dist}{value[len(old_dist) :]}{quote}"

    return _key_literal_pattern(old_dist).sub(_sub, source), count


def rewrite_source(
    source: str, old_dist: str, new_dist: str, old_module: str, new_module: str
) -> tuple[str, int]:
    """Rewrite imports and registry-key literals. Returns ``(text, count)``."""
    lines = source.splitlines(keepends=True)
    count = 0

    for lineno in _import_line_numbers(source, old_module):
        index = lineno - 1
        if index >= len(lines):
            continue
        rewritten = _rewrite_import_line(lines[index], old_module, new_module)
        if rewritten != lines[index]:
            lines[index] = rewritten
            count += 1

    text, key_hits = _rewrite_key_literals("".join(lines), old_dist, new_dist)
    return text, count + key_hits


def scan_prose(source: str, old_module: str, old_dist: str) -> list[int]:
    """1-based line numbers mentioning the old name that nothing rewrites."""
    import_lines = _import_line_numbers(source, old_module)
    pattern = _key_literal_pattern(old_dist)

    reported: list[int] = []
    for lineno, line in enumerate(source.splitlines(), start=1):
        if lineno in import_lines:
            continue
        if old_module not in line and old_dist not in line:
            continue
        stripped = pattern.sub("", line)
        if old_module in stripped or old_dist in stripped:
            reported.append(lineno)
    return reported


def plan_python(
    roots: list[Path], old_dist: str, new_dist: str, old_module: str, new_module: str
) -> tuple[list[FileChange], list[Occurrence]]:
    """Compute Python changes without writing."""
    changes: list[FileChange] = []
    prose: list[Occurrence] = []

    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.glob("**/*.py")):
            if "__pycache__" in path.parts:
                continue
            try:
                source = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if old_module not in source and old_dist not in source:
                continue

            _, count = rewrite_source(source, old_dist, new_dist, old_module, new_module)
            if count:
                changes.append(FileChange(path=path, kind="python", count=count))

            all_lines = source.splitlines()
            for lineno in scan_prose(source, old_module, old_dist):
                prose.append(Occurrence(path=path, line=lineno, text=all_lines[lineno - 1].strip()))

    return changes, prose


def apply_python(
    changes: list[FileChange], old_dist: str, new_dist: str, old_module: str, new_module: str
) -> None:
    """Rewrite each planned Python file on disk."""
    for change in changes:
        source = change.path.read_text(encoding="utf-8")
        rewritten, _ = rewrite_source(source, old_dist, new_dist, old_module, new_module)
        change.path.write_text(rewritten, encoding="utf-8")
