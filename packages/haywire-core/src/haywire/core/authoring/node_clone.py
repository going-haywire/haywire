"""Writing a new node class into a library: plan first, then one write.

:func:`plan_node` answers what file a clone of a node class would become and
why it might be refused, without touching disk. :func:`write_node` performs
the single mutating step. A Node template is cloned the same way as any other
node class.

The source is copied as Python text, rewritten through its AST: relative
imports become absolute, the class is renamed, and its ``@node(...)`` call is
rewritten from :class:`NodeFields`. A module declaring one ``@node`` class is
copied whole; from a module declaring several, only the class and the
module's imports are copied, and other module-level names it uses are
imported from the source module.
"""

from __future__ import annotations

import ast
import builtins
import importlib.util
import inspect
import json
import keyword
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Protocol

from haywire.core.library.dep_detect import HaywireLibrarySource
from haywire.core.library.utils import NODE, reg_key

from .deps import linked_additions
from .targets import AuthoringTarget

if TYPE_CHECKING:
    from haywire.core.library.base import BaseLibrary
    from haywire.core.library.identity import LibraryIdentity
    from haywire.core.node import BaseNode
    from haywire.core.node.info import NodeInfo


class AuthoringLibraries(HaywireLibrarySource, Protocol):
    """What :func:`plan_node` reads about installed libraries. Satisfied by ``LibraryRegistry``."""

    def get_library_identity(self, library_registry_name: str) -> "LibraryIdentity": ...


class KeyLookup(Protocol):
    """Anything answering whether a registry key is taken. Satisfied by ``NodeRegistry``."""

    def has(self, registry_key: str) -> bool: ...


#: ``@node`` keywords the wizard writes from :class:`NodeFields`.
_OWNED_KEYWORDS = ("label", "description", "menu", "search_tags")

#: ``@node`` keywords a clone never inherits from its source.
_DROPPED_KEYWORDS = ("registry_id", "template", "hidden", "deprecation_warning")

#: Filename fragments the folder scan skips (see ``FolderScanMixin.folder_scan_for_pyfiles``).
_DEV_FRAGMENTS = ("dev_", "_dev")

_FALLBACK_CLASS_NAME = "MyNode"

CopyMode = Literal["whole", "extract"]


@dataclass
class NodeFields:
    """The identity a new node class is written with.

    ``class_name`` is also the node's registry id and, in snake case, its
    file name.
    """

    label: str
    class_name: str
    menu: str
    search_tags: list[str] = field(default_factory=list)
    description: str = ""


@dataclass
class NodePlan:
    """What cloning one node class would write, and why it might be refused.

    Read-only: holding a plan changes nothing on disk. ``refusal`` being set
    means :func:`write_node` will raise rather than write.

    ``rewritten_imports`` pairs each relative import's source text with its
    absolute replacement. ``free_names`` are the module-level names an
    extracted class uses, imported from ``source_module``.
    ``linked_additions`` are the libraries the new file imports that the
    target does not yet list in ``linked_libraries``.
    """

    path: Path
    registry_key: str
    module_name: str
    library_id: str
    source_module: str
    source_class: str
    source: str = ""
    mode: CopyMode = "whole"
    rewritten_imports: list[tuple[str, str]] = field(default_factory=list)
    free_names: list[str] = field(default_factory=list)
    linked_additions: list[str] = field(default_factory=list)
    refusal: str | None = None


# ─────────────────────────────────────────────────────────────────────────────
# Names
# ─────────────────────────────────────────────────────────────────────────────


def suggest_class_name(label: str) -> str:
    """Turn a label into a PascalCase class name that passes :func:`class_name_refusal`.

    ``"Blur filter"`` becomes ``"BlurFilter"``. Accents are folded and
    anything that is not a letter or digit separates words. A label that
    yields nothing usable gives ``"MyNode"``.
    """
    folded = unicodedata.normalize("NFKD", label).encode("ascii", "ignore").decode("ascii")
    words = [w for w in re.split(r"[^A-Za-z0-9]+", folded) if w]
    candidate = "".join(w[0].upper() + w[1:] for w in words)
    match = re.search(r"[A-Za-z]", candidate)
    candidate = candidate[match.start() :] if match else ""
    candidate = candidate[:1].upper() + candidate[1:]
    return candidate if class_name_refusal(candidate) is None else _FALLBACK_CLASS_NAME


def module_stem(class_name: str) -> str:
    """The file stem a class is written to: ``BlurFilter`` gives ``blur_filter``."""
    stem = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", class_name)
    stem = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", stem)
    return stem.lower()


def class_name_refusal(class_name: str) -> str | None:
    """Why ``class_name`` cannot name a node class, or ``None`` if it can."""
    if not class_name:
        return "Enter a class name."
    if not class_name.isidentifier() or keyword.iskeyword(class_name) or not class_name.isascii():
        return (
            "A class name must be a Python identifier: letters, digits and '_', not starting with a digit."
        )
    if any(fragment in module_stem(class_name) for fragment in _DEV_FRAGMENTS):
        return (
            f"'{module_stem(class_name)}.py' would not register: files whose name contains "
            f"'dev_' or '_dev' are skipped by the library scan."
        )
    return None


def default_fields(source_cls: "type[BaseNode]") -> NodeFields:
    """The fields the wizard opens with for ``source_cls``, read from its resolved identity.

    A clone's label is ``"<source label> Copy"``; a template's is
    ``"My <template label>"``.
    """
    identity = source_cls.class_identity
    label = f"My {identity.label}" if identity.template else f"{identity.label} Copy"
    return NodeFields(
        label=label,
        class_name=suggest_class_name(label),
        menu=identity.menu,
        search_tags=list(identity.search_tags),
        description=identity.description,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Clone sources
# ─────────────────────────────────────────────────────────────────────────────


def is_clone_source(source_cls: Any) -> bool:
    """Whether ``source_cls`` may be cloned from a selected node.

    Excluded: framework role nodes (error, reroute, Graph-node, macro
    placement, Subgraph boundaries), hidden nodes (templates included), and
    classes whose source cannot be read. A deprecated node may be cloned.
    """
    identity = getattr(source_cls, "class_identity", None)
    if identity is None or identity.hidden or identity.template:
        return False
    if any(value for name, value in vars(identity).items() if name.startswith("_is_")):
        return False
    return _readable_source_file(source_cls) is not None


def list_clone_sources(node_infos: "list[NodeInfo]", resolve: Any) -> "list[NodeInfo]":
    """Filter visible node infos down to the classes :func:`is_clone_source` accepts.

    Args:
        node_infos: Candidates, typically every entry of the add-node menu.
        resolve: Callable mapping a registry key to its class or ``None``,
            such as ``NodeRegistry.get``.
    """
    sources = []
    for info in node_infos:
        if info.is_macro:
            continue
        cls = resolve(info.identity.registry_key)
        if cls is not None and is_clone_source(cls):
            sources.append(info)
    return sources


def _readable_source_file(source_cls: Any) -> Path | None:
    try:
        inspect.getsource(source_cls)
        source_file = inspect.getsourcefile(source_cls)
    except (OSError, TypeError):
        return None
    return Path(source_file) if source_file else None


# ─────────────────────────────────────────────────────────────────────────────
# Planning
# ─────────────────────────────────────────────────────────────────────────────


def plan_node(
    source_cls: "type[BaseNode]",
    fields: NodeFields,
    target: AuthoringTarget,
    libraries: AuthoringLibraries,
    *,
    registry: KeyLookup | None = None,
) -> NodePlan:
    """Describe the file a clone of ``source_cls`` would become in ``target``.

    Reads the source file and never writes. Refusals are carried on the plan:
    unreadable source, an invalid class name, a registry key already taken, a
    file already at the path, or an empty label.

    Args:
        source_cls: The node class or Node template to copy.
        fields: The new class's identity.
        target: The library to write into; the file goes directly in its
            ``nodes/`` folder.
        libraries: The installed libraries, for the target's identity and for
            deciding which imports are haywire libraries.
        registry: Answers whether the new key is taken. Without it the key is
            not checked.

    Returns:
        The plan. Inspect ``refusal`` before writing.

    Example::

        fields = default_fields(source_cls)
        fields.label, fields.class_name = "Blur", "Blur"
        plan = plan_node(source_cls, fields, target, library_registry, registry=node_registry)
        if plan.refusal is None:
            write_node(plan, library_registry.get_library(plan.library_id))
    """
    identity = libraries.get_library_identity(target.library_id)
    stem = module_stem(fields.class_name) if fields.class_name else ""
    path = target.folder / f"{stem}.py"
    plan = NodePlan(
        path=path,
        registry_key=reg_key(target.library_id, NODE, fields.class_name),
        module_name=_module_name_for(path, identity),
        library_id=target.library_id,
        source_module=source_cls.__module__,
        source_class=source_cls.__name__,
    )

    refusal = _field_refusal(fields, plan, registry)
    if refusal is not None:
        plan.refusal = refusal
        return plan

    source_file = _readable_source_file(source_cls)
    if source_file is None:
        plan.refusal = f"The source of {source_cls.__name__} cannot be read."
        return plan

    try:
        _rewrite(plan, source_file.read_text(encoding="utf-8"), fields)
    except _CloneError as exc:
        plan.refusal = str(exc)
        return plan

    plan.linked_additions = linked_additions(plan.source, identity, libraries)
    return plan


def _field_refusal(fields: NodeFields, plan: NodePlan, registry: KeyLookup | None) -> str | None:
    if not fields.label.strip():
        return "Enter a label."
    refusal = class_name_refusal(fields.class_name)
    if refusal is not None:
        return refusal
    if registry is not None and registry.has(plan.registry_key):
        return f"A node '{plan.registry_key}' is already registered."
    if plan.path.exists():
        return f"'{plan.path.name}' already exists in this library."
    return None


def _module_name_for(path: Path, identity: "LibraryIdentity") -> str:
    """The dotted module name the registry resolves ``path`` to, as ``resolve_module_name`` does."""
    try:
        rel = path.resolve().relative_to(Path(identity.folder_path).resolve())
    except (ValueError, OSError):
        return f"{identity.module_name}.{path.stem}"
    return ".".join([identity.module_name, *rel.parts[:-1], rel.stem])


# ─────────────────────────────────────────────────────────────────────────────
# Source rewriting
# ─────────────────────────────────────────────────────────────────────────────


class _CloneError(Exception):
    """A source that cannot be cloned; its message is the plan's refusal."""


@dataclass
class _Edit:
    start: int
    end: int
    text: str


class _Text:
    """Source text addressable by the AST's (line, UTF-8 column) positions."""

    def __init__(self, text: str) -> None:
        self.text = text
        self._line_starts = [0]
        for line in text.splitlines(keepends=True):
            self._line_starts.append(self._line_starts[-1] + len(line))
        self._lines = text.splitlines(keepends=True)

    def offset(self, lineno: int, col: int) -> int:
        line = self._lines[lineno - 1] if lineno - 1 < len(self._lines) else ""
        return self._line_starts[lineno - 1] + len(line.encode("utf-8")[:col].decode("utf-8", "ignore"))

    def span(self, node: ast.AST) -> tuple[int, int]:
        start = self.offset(node.lineno, node.col_offset)  # type: ignore[attr-defined]
        end = self.offset(node.end_lineno, node.end_col_offset)  # type: ignore[attr-defined]
        return start, end

    def line_start(self, lineno: int) -> int:
        return self._line_starts[lineno - 1]

    def line_end(self, lineno: int) -> int:
        return self._line_starts[lineno] if lineno < len(self._line_starts) else len(self.text)


def _node_decorator(cls_def: ast.ClassDef) -> ast.Call | None:
    """The class's ``@node(...)`` call, or ``None``."""
    for deco in cls_def.decorator_list:
        if isinstance(deco, ast.Call):
            func = deco.func
            if (isinstance(func, ast.Name) and func.id == "node") or (
                isinstance(func, ast.Attribute) and func.attr == "node"
            ):
                return deco
    return None


def _rewrite(plan: NodePlan, text: str, fields: NodeFields) -> None:
    """Fill ``plan.source``, ``mode``, ``rewritten_imports`` and ``free_names`` from the source text."""
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        raise _CloneError(f"The source of {plan.source_class} does not parse: {exc}") from exc

    node_classes = [n for n in tree.body if isinstance(n, ast.ClassDef) and _node_decorator(n) is not None]
    cls_def = next((n for n in node_classes if n.name == plan.source_class), None)
    if cls_def is None:
        raise _CloneError(f"{plan.source_class} is not declared with @node at the top of its module.")
    decorator = _node_decorator(cls_def)
    assert decorator is not None

    src = _Text(text)
    package = plan.source_module.rpartition(".")[0]
    plan.mode = "whole" if len(node_classes) == 1 else "extract"

    edits: list[_Edit] = []
    edits.append(_Edit(*src.span(decorator), _decorator_text(decorator, fields, text)))
    edits.extend(_rename_edits(cls_def, src, plan.source_class, fields.class_name))

    if plan.mode == "whole":
        edits.extend(_import_edits(tree, src, package, plan))
        edits = _drop_overlaps(edits)
        plan.source = _apply(text, edits, 0, len(text))
    else:
        import_stmts = [
            n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom)) or _is_type_checking(n)
        ]
        for stmt in import_stmts:
            edits.extend(_import_edits(stmt, src, package, plan))
        edits.extend(_import_edits(cls_def, src, package, plan))
        edits = _drop_overlaps(edits)

        plan.free_names = _free_names(tree, cls_def, import_stmts)
        parts = [_py_str(f"{fields.label}, cloned from {plan.source_module}.{plan.source_class}.") + "\n\n"]
        parts.extend(
            _apply(text, edits, src.line_start(s.lineno), src.line_end(s.end_lineno or s.lineno))
            for s in import_stmts
        )
        if plan.free_names:
            parts.append(f"from {plan.source_module} import {', '.join(plan.free_names)}\n")
        class_start = src.line_start(cls_def.decorator_list[0].lineno)
        parts.append("\n\n")
        parts.append(_apply(text, edits, class_start, src.line_end(cls_def.end_lineno or cls_def.lineno)))
        plan.source = "".join(parts)

    plan.source = plan.source.rstrip() + "\n"
    try:
        ast.parse(plan.source)
    except SyntaxError as exc:  # pragma: no cover — a rewrite bug, not a user error
        raise _CloneError(f"The rewritten source does not parse: {exc}") from exc


def _is_type_checking(stmt: ast.stmt) -> bool:
    if not isinstance(stmt, ast.If):
        return False
    test = stmt.test
    return (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (
        isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
    )


def _import_edits(root: ast.AST, src: _Text, package: str, plan: NodePlan) -> list[_Edit]:
    """Edits turning every relative ``from`` import under ``root`` into an absolute one."""
    edits = []
    for node in ast.walk(root):
        if not (isinstance(node, ast.ImportFrom) and node.level > 0):
            continue
        absolute = importlib.util.resolve_name("." * node.level + (node.module or ""), package)
        before = src.text[slice(*src.span(node))]
        after = ast.unparse(ast.ImportFrom(module=absolute, names=node.names, level=0))
        plan.rewritten_imports.append((before, after))
        edits.append(_Edit(*src.span(node), after))
    return edits


def _rename_edits(cls_def: ast.ClassDef, src: _Text, old: str, new: str) -> list[_Edit]:
    """Edits renaming the class and every reference to its own name inside it."""
    edits = []
    header_start = src.offset(cls_def.lineno, cls_def.col_offset)
    match = re.compile(rf"class\s+({re.escape(old)})\b").search(src.text, header_start)
    if match is not None:
        edits.append(_Edit(match.start(1), match.end(1), new))
    for node in ast.walk(cls_def):
        if isinstance(node, ast.Name) and node.id == old:
            edits.append(_Edit(*src.span(node), new))
        elif isinstance(node, ast.Constant) and node.value == old:
            start, end = src.span(node)
            quote = src.text[start]
            if quote in "\"'":  # a plain literal, not a prefixed or implicitly joined one
                edits.append(_Edit(start, end, f"{quote}{new}{quote}"))
    return edits


def _decorator_text(call: ast.Call, fields: NodeFields, text: str) -> str:
    """The rewritten ``node(...)`` call: owned fields first, then the other keywords as written."""
    func = ast.get_source_segment(text, call.func) or "node"
    lines = [
        f"label={_py_str(fields.label)}",
        f"description={_py_str(fields.description)}",
        f"menu={_py_str(fields.menu)}",
        f"search_tags=[{', '.join(_py_str(t) for t in fields.search_tags)}]",
    ]
    for kw in call.keywords:
        if kw.arg in _OWNED_KEYWORDS or kw.arg in _DROPPED_KEYWORDS:
            continue
        segment = ast.get_source_segment(text, kw)
        if segment is None:  # pragma: no cover — every keyword carries a position
            segment = ast.unparse(kw)
        lines.append(segment)
    body = "".join(f"    {line},\n" for line in lines)
    return f"{func}(\n{body})"


def _py_str(value: str) -> str:
    """A double-quoted Python string literal for ``value``."""
    return json.dumps(value, ensure_ascii=False)


def _free_names(tree: ast.Module, cls_def: ast.ClassDef, import_stmts: list[ast.stmt]) -> list[str]:
    """Module-level names the class uses that are neither imports nor its own, sorted."""
    # Keywords the decorator rewrite replaces or drops are not copied, so their names are not used.
    decorator = _node_decorator(cls_def)
    replaced = {
        id(n)
        for kw in (decorator.keywords if decorator is not None else [])
        if kw.arg in _OWNED_KEYWORDS or kw.arg in _DROPPED_KEYWORDS
        for n in ast.walk(kw)
    }
    loaded = {
        n.id
        for n in ast.walk(cls_def)
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and id(n) not in replaced
    }

    bound: set[str] = {cls_def.name}
    for node in ast.walk(cls_def):
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            bound.add(node.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node is not cls_def:
            bound.add(node.name)
        elif isinstance(node, ast.arg):
            bound.add(node.arg)

    imported: set[str] = set()
    for stmt in import_stmts:
        for node in ast.walk(stmt):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    imported.add(alias.asname or alias.name.split(".")[0])

    module_bindings: set[str] = set()
    for stmt in tree.body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            module_bindings.add(stmt.name)
        elif isinstance(stmt, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
            for target in targets:
                module_bindings.update(n.id for n in ast.walk(target) if isinstance(n, ast.Name))

    free = (loaded - bound - imported - set(dir(builtins))) & module_bindings
    return sorted(free)


def _drop_overlaps(edits: list[_Edit]) -> list[_Edit]:
    """Keep the first edit of any overlapping pair, in list order (the decorator rewrite wins)."""
    kept: list[_Edit] = []
    for edit in edits:
        if all(edit.end <= k.start or edit.start >= k.end for k in kept):
            kept.append(edit)
    return kept


def _apply(text: str, edits: list[_Edit], start: int, end: int) -> str:
    """``text[start:end]`` with the edits that fall inside it applied."""
    inside = sorted((e for e in edits if e.start >= start and e.end <= end), key=lambda e: e.start)
    out, cursor = [], start
    for edit in inside:
        out.append(text[cursor : edit.start])
        out.append(edit.text)
        cursor = edit.end
    out.append(text[cursor:end])
    return "".join(out)


# ─────────────────────────────────────────────────────────────────────────────
# Writing
# ─────────────────────────────────────────────────────────────────────────────


def link_libraries(library: "BaseLibrary", names: list[str]) -> list[str]:
    """Add ``names`` to the library's ``linked_libraries`` and refresh its identity in place.

    The refresh is synchronous, so a module the watcher registers afterwards
    tracks the new libraries for hot reload.

    Returns:
        The names actually added.

    Raises:
        HaybaleTomlError: The library's ``haybale.toml`` is missing or a name
            is not a module name.
    """
    from haywire.core.library.haybale_toml import union_linked_libraries

    if not names:
        return []
    added = union_linked_libraries(Path(library.identity.folder_path), names)
    if added:
        library._reload_metadata()
    return added


def write_node(plan: NodePlan, library: "BaseLibrary") -> Path:
    """Write the planned node file. The only step that touches disk.

    First adds ``plan.linked_additions`` to the library's ``haybale.toml`` and
    refreshes its identity, then writes the ``.py`` (creating the folder if
    needed). Registration is the file watcher's; see ``RegistrationWatch``.

    Raises:
        ValueError: The plan carries a refusal.
        FileExistsError: A file appeared at the path since the plan was made.
        HaybaleTomlError: ``haybale.toml`` could not be updated.

    Returns:
        The path written.
    """
    if plan.refusal is not None:
        raise ValueError(f"This node cannot be written: {plan.refusal}")
    if plan.path.exists():
        raise FileExistsError(f"'{plan.path}' already exists.")

    link_libraries(library, plan.linked_additions)

    plan.path.parent.mkdir(parents=True, exist_ok=True)
    with open(plan.path, "x", encoding="utf-8") as handle:
        handle.write(plan.source)
    return plan.path
