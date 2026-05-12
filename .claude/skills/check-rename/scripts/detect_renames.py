#!/usr/bin/env python3
"""Detect symbol renames between HEAD and the working tree.

Strategy
--------
A rename is inferred when:
  1. A named declaration (def, class, class-body field, module-level constant,
     or function parameter) is present in HEAD but absent in the working tree, AND
  2. A same-shaped declaration with a similar name appears in the working tree
     that wasn't there before.

For each removed name we score added candidates by Levenshtein similarity
and structural proximity (same kind / same parent).

We also detect renamed files via `git status --porcelain -z` (R-status).

Output is JSON on stdout so the calling skill can parse it and present the
findings to the user.

Scope of search for "remnants":
    tests/   barn/   docs/
Skipped: packages/ (IDE handles these reliably) and .venv, node_modules, etc.

Remnant context tagging
-----------------------
For attribute renames (class-body fields), each remnant carries a `context`
label so the calling skill can separate likely-real hits from noise:

  - "attribute_access"  — line contains `.old_field` syntax
  - "kwarg"             — line contains `old_field=` inside a call to the class
  - "prose_near_class"  — the class name appears within ±5 lines (docs/strings)
  - "plain"             — bare word-boundary match, no syntactic shape nearby

For non-attribute renames (function/class/method/constant/parameter), the
context is always "plain" — those names are distinctive enough on their own.
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

# ---------------------------------------------------------------------------
# Tuning knobs
# ---------------------------------------------------------------------------

SEARCH_DIRS = ["tests", "barn", "docs"]
SIMILARITY_THRESHOLD = 0.45  # min Levenshtein ratio to consider a rename pairing
MIN_SYMBOL_LEN = 3  # ignore single/double-char names (e.g. `x`, `_i`)
PROSE_CONTEXT_LINES = 5  # how far above/below to scan for a class-name mention
SKIP_BUILTIN_NAMES = {
    "__init__",
    "__enter__",
    "__exit__",
    "__repr__",
    "__str__",
    "__hash__",
    "__eq__",
    "__call__",
    "setUp",
    "tearDown",
    "setup_method",
    "teardown_method",
}
SKIP_PARAM_NAMES = {"self", "cls", "args", "kwargs"}


@dataclass
class RenameCandidate:
    old: str
    new: str | None
    file: str
    kind: str  # "function" | "class" | "method" | "attribute" | "constant" | "parameter" | "file"
    parent: str | None  # for attributes: the class name; for parameters: the function qualified name
    confidence: float  # 0..1


@dataclass
class Remnant:
    file: str
    line: int
    snippet: str
    context: str = "plain"  # see module docstring


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def run_git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return ""
    return result.stdout


def changed_py_files() -> list[str]:
    """Return paths of .py files modified or added vs HEAD (tracked changes only)."""
    out = run_git("diff", "--name-only", "HEAD", "--diff-filter=AM")
    files = [p for p in out.splitlines() if p.endswith(".py")]
    # Also include untracked .py files (in case user hasn't `git add`-ed yet).
    untracked = run_git("ls-files", "--others", "--exclude-standard")
    files.extend(p for p in untracked.splitlines() if p.endswith(".py"))
    return sorted(set(files))


def renamed_files() -> list[tuple[str, str]]:
    """Return (old_path, new_path) pairs for git-detected file renames."""
    out = run_git("status", "--porcelain=v1")
    pairs: list[tuple[str, str]] = []
    for line in out.splitlines():
        m = re.match(r"^R[ MD]\s+(\S.*?) -> (\S.*)$", line)
        if m:
            pairs.append((m.group(1).strip(), m.group(2).strip()))
    out = run_git("diff", "--name-status", "-M", "HEAD")
    for line in out.splitlines():
        parts = line.split("\t")
        if parts and parts[0].startswith("R") and len(parts) >= 3:
            pairs.append((parts[1], parts[2]))
    seen = set()
    deduped: list[tuple[str, str]] = []
    for pair in pairs:
        if pair not in seen:
            seen.add(pair)
            deduped.append(pair)
    return deduped


def file_at_head(path: str) -> str | None:
    """Return file contents at HEAD, or None if the file didn't exist there."""
    result = subprocess.run(
        ["git", "show", f"HEAD:{path}"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout


# ---------------------------------------------------------------------------
# AST extraction
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Symbol:
    name: str
    kind: str  # "function" | "class" | "method" | "attribute" | "constant" | "parameter"
    parent: str | None  # enclosing class (for method/attribute) or qualified function (for parameter)
    lineno: int


def _assign_targets(node: ast.stmt) -> list[str]:
    """Return target names for an assignment-shaped node (AnnAssign or Assign)."""
    names: list[str] = []
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        names.append(node.target.id)
    elif isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name):
                names.append(target.id)
    return names


def _extract_params(func: ast.FunctionDef | ast.AsyncFunctionDef, parent_qual: str) -> list[Symbol]:
    """Return Symbol entries for the function's parameters (excluding self/cls/args/kwargs)."""
    syms: list[Symbol] = []
    a = func.args
    arg_lists = [a.posonlyargs, a.args, a.kwonlyargs]
    for arg_list in arg_lists:
        for arg in arg_list:
            if arg.arg in SKIP_PARAM_NAMES:
                continue
            syms.append(Symbol(arg.arg, "parameter", parent_qual, arg.lineno))
    # vararg / kwarg are usually called *args/**kwargs — skip per SKIP_PARAM_NAMES
    if a.vararg and a.vararg.arg not in SKIP_PARAM_NAMES:
        syms.append(Symbol(a.vararg.arg, "parameter", parent_qual, a.vararg.lineno))
    if a.kwarg and a.kwarg.arg not in SKIP_PARAM_NAMES:
        syms.append(Symbol(a.kwarg.arg, "parameter", parent_qual, a.kwarg.lineno))
    return syms


def extract_symbols(src: str) -> set[Symbol]:
    """Extract:
    - top-level functions/classes (function, class)
    - methods on top-level classes (method)
    - class-body annotated/plain assignments (attribute)
    - module-level annotated/plain assignments (constant)
    - parameter names on top-level functions and methods (parameter)
    """
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return set()

    symbols: set[Symbol] = set()

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            symbols.add(Symbol(node.name, "function", None, node.lineno))
            symbols.update(_extract_params(node, parent_qual=node.name))
        elif isinstance(node, ast.ClassDef):
            symbols.add(Symbol(node.name, "class", None, node.lineno))
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    symbols.add(Symbol(child.name, "method", node.name, child.lineno))
                    symbols.update(_extract_params(child, parent_qual=f"{node.name}.{child.name}"))
                elif isinstance(child, (ast.AnnAssign, ast.Assign)):
                    for name in _assign_targets(child):
                        symbols.add(Symbol(name, "attribute", node.name, child.lineno))
        elif isinstance(node, (ast.AnnAssign, ast.Assign)):
            for name in _assign_targets(node):
                symbols.add(Symbol(name, "constant", None, node.lineno))

    return symbols


# ---------------------------------------------------------------------------
# Rename inference
# ---------------------------------------------------------------------------


def levenshtein_ratio(a: str, b: str) -> float:
    """Return similarity ratio in [0, 1]. 1.0 = identical."""
    if a == b:
        return 1.0
    if not a or not b:
        return 0.0
    n, m = len(a), len(b)
    prev = list(range(m + 1))
    for i in range(1, n + 1):
        cur = [i] + [0] * m
        for j in range(1, m + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            cur[j] = min(cur[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost)
        prev = cur
    distance = prev[m]
    return 1.0 - distance / max(n, m)


def pair_renames(removed: set[Symbol], added: set[Symbol]) -> list[tuple[Symbol, Symbol | None, float]]:
    """Pair each removed symbol to its most likely added counterpart.

    Two-pass algorithm:
      1. Structural unique-pair: when exactly one removed and one added of the
         same (kind, parent) exist, pair them regardless of name similarity.
         This catches semantic renames like `payload → binding_id` where the
         strings share no letters but the slot is unambiguous.
      2. Similarity pass: remaining removals score by Levenshtein ratio against
         remaining additions of the same kind, with a same-parent bonus.
         Parameters require same parent (cross-function param pairing is hopeless).

    A removed symbol may end up unpaired (returns None partner)."""
    pairs: list[tuple[Symbol, Symbol | None, float]] = []
    candidates = list(added)

    # Filter out symbols we never report on.
    def reportable(s: Symbol) -> bool:
        return len(s.name) >= MIN_SYMBOL_LEN and s.name not in SKIP_BUILTIN_NAMES

    remaining_removed = [s for s in sorted(removed, key=lambda s: s.name) if reportable(s)]

    # Pass 1: unique-slot structural pairing.
    # Group both removed and added by (kind, parent); when both groups have
    # exactly one entry, they must be each other's rename.
    def slot_key(s: Symbol) -> tuple[str, str | None]:
        return (s.kind, s.parent)

    removed_by_slot: dict[tuple[str, str | None], list[Symbol]] = {}
    for s in remaining_removed:
        removed_by_slot.setdefault(slot_key(s), []).append(s)
    added_by_slot: dict[tuple[str, str | None], list[Symbol]] = {}
    for s in candidates:
        added_by_slot.setdefault(slot_key(s), []).append(s)

    structurally_paired: set[Symbol] = set()
    for slot, olds in removed_by_slot.items():
        news = added_by_slot.get(slot, [])
        if len(olds) == 1 and len(news) == 1:
            old, new = olds[0], news[0]
            if old.name == new.name:
                continue  # not actually a rename
            ratio = levenshtein_ratio(old.name, new.name)
            # Confidence: blend similarity with structural certainty.
            # Pure structural certainty when slot is unambiguous is high; we
            # report a floor of 0.6 even for low-similarity name pairs.
            conf = max(0.6, ratio + 0.15)
            conf = min(conf, 1.0)
            pairs.append((old, new, conf))
            structurally_paired.add(old)
            candidates.remove(new)

    # Pass 2: similarity-based pairing for the rest.
    for old in remaining_removed:
        if old in structurally_paired:
            continue
        best: tuple[Symbol, float] | None = None
        for new in candidates:
            if new.name == old.name:
                continue
            if new.kind != old.kind:
                continue
            if old.kind == "parameter" and new.parent != old.parent:
                continue
            ratio = levenshtein_ratio(old.name, new.name)
            if new.parent == old.parent:
                ratio += 0.15
            ratio = min(ratio, 1.0)
            if best is None or ratio > best[1]:
                best = (new, ratio)
        if best and best[1] >= SIMILARITY_THRESHOLD:
            pairs.append((old, best[0], best[1]))
            candidates.remove(best[0])
        else:
            pairs.append((old, None, 0.0))

    return pairs


# ---------------------------------------------------------------------------
# Remnant search
# ---------------------------------------------------------------------------


def _iter_search_files(repo_root: Path):
    for sub in SEARCH_DIRS:
        root = repo_root / sub
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if any(part in {"__pycache__", ".pytest_cache", ".mypy_cache"} for part in path.parts):
                continue
            if path.suffix not in (".py", ".md", ".toml", ".txt", ".rst"):
                continue
            yield path


def find_remnants(name: str, repo_root: Path) -> list[Remnant]:
    """Word-boundary scan for `name` across SEARCH_DIRS. Used for non-attribute kinds."""
    remnants: list[Remnant] = []
    regex = re.compile(rf"\b{re.escape(name)}\b")

    for path in _iter_search_files(repo_root):
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for i, line in enumerate(text.splitlines(), start=1):
            if regex.search(line):
                remnants.append(
                    Remnant(
                        file=str(path.relative_to(repo_root)),
                        line=i,
                        snippet=line.strip()[:200],
                    )
                )
    return remnants


def find_attribute_remnants(class_name: str, old_field: str, repo_root: Path) -> list[Remnant]:
    """Context-aware scan for `class.field` renames.

    A line with a `\\b<old_field>\\b` match is only surfaced if there is
    evidence linking it to `class_name`:

      - The class name appears within ±PROSE_CONTEXT_LINES, AND
      - One of these patterns is true on the line:
        - "attribute_access"  : contains `.<old_field>` (any dotted access)
        - "kwarg"             : contains `<old_field>=` (likely keyword arg)
        - "prose_near_class"  : just a bare mention (docs/strings)

    Files that don't mention `class_name` at all are skipped entirely —
    that's where most of the false-positive noise comes from (unrelated
    code that happens to use the same field/parameter name).
    """
    remnants: list[Remnant] = []
    word = re.compile(rf"\b{re.escape(old_field)}\b")
    attr_access = re.compile(rf"\.{re.escape(old_field)}\b")
    kwarg = re.compile(rf"\b{re.escape(old_field)}\s*=")
    class_word = re.compile(rf"\b{re.escape(class_name)}\b")

    for path in _iter_search_files(repo_root):
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        lines = text.splitlines()
        class_lines = {i for i, line in enumerate(lines) if class_word.search(line)}
        if not class_lines:
            # File has no mention of the class — skip entirely. Renames of
            # unrelated `<old_field>` symbols in other code don't concern us.
            continue

        for i, line in enumerate(lines):
            if not word.search(line):
                continue
            lo = max(0, i - PROSE_CONTEXT_LINES)
            hi = min(len(lines), i + PROSE_CONTEXT_LINES + 1)
            near_class = any(j in class_lines for j in range(lo, hi))
            if not near_class:
                # Same file, but this occurrence isn't tied to the class.
                continue
            if attr_access.search(line):
                ctx = "attribute_access"
            elif kwarg.search(line):
                ctx = "kwarg"
            else:
                ctx = "prose_near_class"
            remnants.append(
                Remnant(
                    file=str(path.relative_to(repo_root)),
                    line=i + 1,
                    snippet=line.strip()[:200],
                    context=ctx,
                )
            )
    return remnants


def codebase_count(name: str, repo_root: Path) -> int:
    """Total word-boundary occurrences of `name` across all .py files."""
    regex = re.compile(rf"\b{re.escape(name)}\b")
    count = 0
    for path in repo_root.rglob("*.py"):
        if any(part in {".venv", "node_modules", "__pycache__"} for part in path.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        count += len(regex.findall(text))
    return count


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def detect_in_file(path: str, repo_root: Path) -> list[RenameCandidate]:
    """Detect renames inside a single file."""
    before = file_at_head(path)
    if before is None:
        return []
    try:
        after = (repo_root / path).read_text(encoding="utf-8")
    except OSError:
        return []

    before_syms = extract_symbols(before)
    after_syms = extract_symbols(after)

    # A "removal" is a (name, kind, parent) triple gone from the after set.
    # We key by (name, kind, parent) so that e.g. an attribute and a function
    # with the same name don't accidentally cancel.
    def key(s: Symbol) -> tuple[str, str, str | None]:
        return (s.name, s.kind, s.parent)

    before_keys = {key(s) for s in before_syms}
    after_keys = {key(s) for s in after_syms}

    removed = {s for s in before_syms if key(s) not in after_keys}
    added = {s for s in after_syms if key(s) not in before_keys}

    if not removed:
        return []

    candidates: list[RenameCandidate] = []
    for old, new, score in pair_renames(removed, added):
        candidates.append(
            RenameCandidate(
                old=old.name,
                new=new.name if new else None,
                file=path,
                kind=old.kind,
                parent=old.parent,
                confidence=round(score, 2) if new else 0.0,
            )
        )

    return candidates


def main() -> int:
    repo_root = Path(run_git("rev-parse", "--show-toplevel").strip() or ".").resolve()

    results: dict = {
        "symbol_renames": [],
        "file_renames": [],
        "search_scope": SEARCH_DIRS,
        "repo_root": str(repo_root),
    }

    # File renames first.
    for old_path, new_path in renamed_files():
        old_module = re.sub(r"\.py$", "", old_path).replace("/", ".")
        for prefix in ("packages.haywire-core.src.", "packages.haywire-studio.src.", "barn."):
            if old_module.startswith(prefix):
                old_module = old_module[len(prefix) :]
        remnants = find_remnants(old_module, repo_root)
        substring_hits: list[Remnant] = []
        for sub in SEARCH_DIRS:
            root = repo_root / sub
            if not root.is_dir():
                continue
            for p in root.rglob("*"):
                if not p.is_file() or p.suffix not in (".py", ".md", ".toml"):
                    continue
                try:
                    text = p.read_text(encoding="utf-8")
                except (UnicodeDecodeError, OSError):
                    continue
                for i, line in enumerate(text.splitlines(), start=1):
                    if old_path in line or re.sub(r"\.py$", "", old_path) in line:
                        substring_hits.append(Remnant(str(p.relative_to(repo_root)), i, line.strip()[:200]))
        results["file_renames"].append(
            {
                "old_path": old_path,
                "new_path": new_path,
                "old_module": old_module,
                "module_remnants": [asdict(r) for r in remnants],
                "path_remnants": [asdict(r) for r in substring_hits],
            }
        )

    # Symbol renames.
    for path in changed_py_files():
        for cand in detect_in_file(path, repo_root):
            if cand.kind == "attribute" and cand.parent:
                remnants = find_attribute_remnants(cand.parent, cand.old, repo_root)
            else:
                remnants = find_remnants(cand.old, repo_root) if cand.old else []
            remnants = [r for r in remnants if r.file != cand.file]
            results["symbol_renames"].append(
                {
                    "old": cand.old,
                    "new": cand.new,
                    "file": cand.file,
                    "kind": cand.kind,
                    "parent": cand.parent,
                    "confidence": cand.confidence,
                    "remnants": [asdict(r) for r in remnants],
                }
            )

    json.dump(results, sys.stdout, indent=2)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
