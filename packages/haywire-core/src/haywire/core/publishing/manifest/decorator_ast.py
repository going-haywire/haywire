"""Read `@library(...)` fields out of a library's source, without importing it.

`haywire share` and the CI feed generator both run against a checkout where
nothing is installed, so they cannot read `cls.class_identity`. They parse the
source instead — and they parse it *here*, once.

AST rather than regex, for two reasons the regex readers this replaces
demonstrated: a pattern anchored on one quote style silently no-ops against the
other (barn libraries are `ruff format`ted to double quotes), and the list
reader converted `_` to `-` on every value because it was written for dependency
names, which quietly mangles anything else.

Only literal values are readable. A computed one is reported absent rather than
guessed: an absent field is a state every caller already handles, whereas a
wrong one propagates into a published feed.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class DecoratorFields:
    """What `@library(...)` declares. Defaults mirror the decorator's own."""

    id: str = ""
    label: str = ""
    linked_libraries: list[str] = field(default_factory=list)
    on_reload: str = "none"
    os: list[str] = field(default_factory=list)
    examples_path: str = ""
    tests_path: str = ""
    file_watcher: bool = False


def _as_str(node: ast.expr | None) -> str | None:
    """The string literal's value, or None for anything non-literal."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _as_str_list(node: ast.expr | None) -> list[str] | None:
    """A list of string literals, or None if any element is not one."""
    if not isinstance(node, ast.List):
        return None
    out: list[str] = []
    for element in node.elts:
        value = _as_str(element)
        if value is None:
            return None
        out.append(value)
    return out


def _as_bool(node: ast.expr | None) -> bool | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, bool):
        return node.value
    return None


def _library_call(tree: ast.Module) -> ast.Call | None:
    """The first `@library(...)` call decorating a class, or None."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            func = decorator.func
            if isinstance(func, ast.Name) and func.id == "library":
                return decorator
    return None


def read_decorator(init_py: Path) -> DecoratorFields:
    """Read *init_py*'s `@library(...)` declaration.

    Returns all-defaults when the file is missing, unparseable, or has no
    decorated class — a framework package has no `Library` class, and a
    read-only drift report must not crash on a library with a syntax error.
    """
    try:
        source = init_py.read_text(encoding="utf-8")
    except OSError:
        return DecoratorFields()

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return DecoratorFields()

    call = _library_call(tree)
    if call is None:
        return DecoratorFields()

    kwargs = {kw.arg: kw.value for kw in call.keywords if kw.arg is not None}
    defaults = DecoratorFields()

    def _str(name: str, fallback: str) -> str:
        value = _as_str(kwargs.get(name))
        return fallback if value is None else value

    def _list(name: str) -> list[str]:
        value = _as_str_list(kwargs.get(name))
        return [] if value is None else value

    file_watcher = _as_bool(kwargs.get("file_watcher"))

    return DecoratorFields(
        id=_str("id", defaults.id),
        label=_str("label", defaults.label),
        linked_libraries=_list("linked_libraries"),
        on_reload=_str("on_reload", defaults.on_reload),
        os=_list("os"),
        examples_path=_str("examples_path", defaults.examples_path),
        tests_path=_str("tests_path", defaults.tests_path),
        file_watcher=defaults.file_watcher if file_watcher is None else file_watcher,
    )
