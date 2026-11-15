"""Rewrite a library's haywire imports onto the Author API (ADR 0084).

Run from the repo root with the project's Python:

    .venv/bin/python workbench/playground/author_api_codemod.py [--write] <library dir> ...

For every ``from haywire.<internal> import name`` it moves each name that
``haywire.api`` or ``haywire.api.workbench`` exports as the same object to that
module, and ``from haywire.ui import elements as hui`` to
``from haywire.api.workbench import hui``. Names the Author API lacks stay on
their internal import and are listed at the end. The import lines of Markdown
pages under the directory are rewritten the same way, one line per statement: each needs a decision (export,
or rewrite the user). Without ``--write`` nothing is changed. Run
``ruff check --fix --select I`` and ``ruff format`` on the library afterwards.
"""

import ast
import collections
import importlib
import pathlib
import re
import sys

import haywire.api as component
import haywire.api.workbench as workbench

API = {"haywire.api": component, "haywire.api.workbench": workbench}

#: Names core renamed when the Author API was introduced: (module, old name) -> new name.
RENAMED = {
    ("haywire.barn.builtin.surfaces", "Barns"): "BarnsSurface",
    ("haywire.core.volumes", "location_of"): "volume_location",
    ("haywire.core.volumes", "resolve"): "resolve_volume_path",
}


def target_of(module: str, name: str) -> str | None:
    """The Author API module exporting ``module.name`` as the same object, or ``None``."""
    if module == "haywire.ui" and name == "elements":
        return "haywire.api.workbench"
    try:
        source = importlib.import_module(module)
        obj = getattr(source, name)
    except (ImportError, AttributeError):
        return None
    for api_name, api in API.items():
        if name in api.__all__ and getattr(api, name) is obj:
            return api_name
    return None


def rewrite(path: pathlib.Path, write: bool, left: dict) -> int:
    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")
    moved = 0
    renamed: dict[str, str] = {}
    nodes = [n for n in ast.walk(ast.parse(text)) if isinstance(n, ast.ImportFrom)]
    for node in sorted(nodes, key=lambda n: n.lineno, reverse=True):
        module = node.module or ""
        if node.level or not module.startswith("haywire.") or module.startswith("haywire.api"):
            continue
        groups: dict[str, list[str]] = collections.defaultdict(list)
        for alias in node.names:
            name = RENAMED.get((module, alias.name), alias.name)
            if name != alias.name and alias.asname is None:
                renamed[alias.name] = name
            target = target_of(module, name)
            if target and module == "haywire.ui" and name == "elements":
                # `hui` is the exported name; keep any other alias the file uses.
                spelled = "hui" if alias.asname in (None, "hui") else f"hui as {alias.asname}"
                if alias.asname is None:
                    target = None  # bare `elements` is used by that name in the file
            else:
                spelled = name if alias.asname is None else f"{name} as {alias.asname}"
            if target is None:
                spelled = name if alias.asname is None else f"{name} as {alias.asname}"
                left[(module, name)].add(str(path))
            groups[target or module].append(spelled)
        if set(groups) == {module}:
            continue
        moved += sum(len(v) for k, v in groups.items() if k != module)
        indent = lines[node.lineno - 1][: node.col_offset]
        new = [f"{indent}from {mod} import {', '.join(names)}" for mod, names in sorted(groups.items())]
        lines[node.lineno - 1 : node.end_lineno] = new
    if moved and write:
        out = merge("\n".join(lines))
        for old, new in renamed.items():
            out = re.sub(rf"\b{re.escape(old)}\b", new, out)
        path.write_text(out, encoding="utf-8")
    return moved


def _order(spelled: str) -> tuple[int, str]:
    name = spelled.split(" as ")[0]
    return (0 if name.isupper() else 1 if name[0].isupper() else 2, name)


def _spelled(node: ast.ImportFrom) -> set[str]:
    return {a.name if a.asname is None else f"{a.name} as {a.asname}" for a in node.names}


def merge(text: str) -> str:
    """Tidy a file's Author API imports.

    Imports of one Author API module that are siblings in a block become one
    statement. An import inside a function moves up into the module-level
    import of the same module, when the file has one and the function keeps
    another statement.
    """
    lines: list[str | None] = list(text.split("\n"))
    tree = ast.parse(text)

    def drop(node: ast.ImportFrom) -> None:
        for i in range(node.lineno - 1, node.end_lineno or node.lineno):
            lines[i] = None

    def put(node: ast.ImportFrom, names: set[str]) -> None:
        drop(node)
        indent = " " * node.col_offset
        lines[node.lineno - 1] = f"{indent}from {node.module} import {', '.join(sorted(names, key=_order))}"

    top: dict[str, tuple[ast.ImportFrom, set[str]]] = {}
    for module in API:
        nodes = [n for n in tree.body if isinstance(n, ast.ImportFrom) and n.module == module]
        if nodes:
            top[module] = (nodes[0], set().union(*map(_spelled, nodes)))
            for node in nodes[1:]:
                drop(node)

    for owner in ast.walk(tree):
        if owner is tree:
            continue
        for field in ("body", "orelse", "finalbody"):
            block = getattr(owner, field, None)
            if not isinstance(block, list):
                continue
            imports = [n for n in block if isinstance(n, ast.ImportFrom) and n.module in API]
            is_function = isinstance(owner, (ast.FunctionDef, ast.AsyncFunctionDef)) and field == "body"
            hoistable = [n for n in imports if n.module in top] if is_function else []
            if hoistable and len(block) > len(hoistable):
                for node in hoistable:
                    top[node.module][1].update(_spelled(node))
                    drop(node)
                imports = [n for n in imports if n not in hoistable]
            for module in API:
                nodes = [n for n in imports if n.module == module]
                if nodes:
                    for node in nodes[1:]:
                        drop(node)
                    put(nodes[0], set().union(*map(_spelled, nodes)))

    for node, names in top.values():
        put(node, names)
    return "\n".join(line for line in lines if line is not None)


MD_IMPORT = re.compile(
    r"^(?P<indent>[ \t>]*)from (?P<module>haywire\.[\w.]+) import (?P<names>\([^)]*\)|[^\n(]+)$",
    re.MULTILINE,
)


MD_API_RUN = re.compile(
    r"^(?P<indent>[ \t>]*)from (?P<module>haywire\.api(?:\.workbench)?) import (?P<names>[^\n(#]+)\n"
    r"(?:(?P=indent)from (?P=module) import [^\n(#]+\n)+",
    re.MULTILINE,
)


def _md_line(indent: str, module: str, names: list[str]) -> str:
    """One import statement, wrapped in parentheses when it passes 88 columns."""
    ordered = sorted(set(names), key=_order)
    line = f"{indent}from {module} import {', '.join(ordered)}"
    if len(line) <= 88:
        return line
    inner = "".join(f"{indent}    {name},\n" for name in ordered)
    return f"{indent}from {module} import (\n{inner}{indent})"


def _join_run(match: re.Match) -> str:
    """Consecutive imports of one Author API module become one statement."""
    names = [
        n.strip()
        for line in match[0].rstrip("\n").split("\n")
        for n in line.split(" import ", 1)[1].split(",")
        if n.strip()
    ]
    return _md_line(match["indent"], match["module"], names) + "\n"


def rewrite_markdown(path: pathlib.Path, write: bool, left: dict) -> int:
    """Rewrite the ``from haywire.<internal> import ...`` lines of a Markdown page."""
    moved = 0

    def replace(match: re.Match) -> str:
        nonlocal moved
        module = match["module"]
        if module.startswith("haywire.api"):
            return match[0]
        raw = match["names"]
        comment = ""
        if "\n" not in raw:
            raw, _, comment = raw.partition("#")
        # A statement over several lines loses its per-line comments.
        body = " ".join(line.partition("#")[0] for line in raw.split("\n"))
        names = [n.strip() for n in body.strip("() ").split(",") if n.strip()]
        groups: dict[str, list[str]] = collections.defaultdict(list)
        for spelled in names:
            name = spelled.split(" as ")[0].strip()
            target = target_of(module, name)
            if target and name == "elements" and module == "haywire.ui":
                spelled = "hui"
            if target is None:
                left[(module, name)].add(str(path))
            groups[target or module].append(spelled)
        if set(groups) == {module}:
            return match[0]
        moved += sum(len(v) for k, v in groups.items() if k != module)
        tail = f"  # {comment.strip()}" if comment else ""
        return "\n".join(_md_line(match["indent"], mod, n) + tail for mod, n in sorted(groups.items()))

    text = path.read_text(encoding="utf-8")
    new = MD_API_RUN.sub(_join_run, MD_IMPORT.sub(replace, text))
    if moved and write:
        path.write_text(new, encoding="utf-8")
    return moved


def main() -> None:
    args = [a for a in sys.argv[1:] if a != "--write"]
    write = "--write" in sys.argv
    left: dict = collections.defaultdict(set)
    for root in args:
        base = pathlib.Path(root)
        moved = sum(rewrite(p, write, left) for p in sorted(base.rglob("*.py")))
        moved += sum(rewrite_markdown(p, write, left) for p in sorted(base.rglob("*.md")))
        print(f"{root}: {moved} names {'moved' if write else 'would move'}")
    if left:
        print("\nNot in the Author API:")
        for (module, name), files in sorted(left.items()):
            print(f"  {module}.{name}  ({len(files)} files)")


if __name__ == "__main__":
    main()
