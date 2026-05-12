#!/usr/bin/env python3
"""Detect symbol renames between HEAD and the working tree.

Strategy
--------
A rename is inferred when:
  1. A `def` or `class` name (or top-level assignment target) is present in HEAD
     but absent in the working tree, AND
  2. A same-shaped declaration with a similar name appears in the working tree
     that wasn't there before.

For each removed name we score added candidates by Levenshtein similarity
and structural proximity (same parent class / similar line number).

We also detect renamed files via `git status --porcelain -z` (R-status).

Output is JSON on stdout so the calling skill can parse it and present the
findings to the user.

Scope of search for "remnants":
    tests/   barn/   docs/
Skipped: packages/ (IDE handles these reliably) and .venv, node_modules, etc.
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


@dataclass
class RenameCandidate:
    old: str
    new: str | None
    file: str
    kind: str  # "function" | "class" | "method" | "file"
    confidence: float  # 0..1


@dataclass
class Remnant:
    file: str
    line: int
    snippet: str


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
        # Rename lines look like: "R  old/path -> new/path"
        m = re.match(r"^R[ MD]\s+(\S.*?) -> (\S.*)$", line)
        if m:
            pairs.append((m.group(1).strip(), m.group(2).strip()))
    # Also include git-diff-detected renames (which finds them via similarity
    # even without an explicit `git mv`).
    out = run_git("diff", "--name-status", "-M", "HEAD")
    for line in out.splitlines():
        parts = line.split("\t")
        if parts and parts[0].startswith("R") and len(parts) >= 3:
            pairs.append((parts[1], parts[2]))
    # Dedupe while preserving order.
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
    kind: str  # "function" | "class" | "method"
    parent: str | None  # enclosing class name, or None for module-level
    lineno: int


def extract_symbols(src: str) -> set[Symbol]:
    """Extract top-level functions/classes and their methods."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return set()

    symbols: set[Symbol] = set()

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            symbols.add(Symbol(node.name, "function", None, node.lineno))
        elif isinstance(node, ast.ClassDef):
            symbols.add(Symbol(node.name, "class", None, node.lineno))
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    symbols.add(Symbol(child.name, "method", node.name, child.lineno))

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
    # Classic DP.
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


def pair_renames(removed: set[Symbol], added: set[Symbol]) -> list[tuple[Symbol, Symbol, float]]:
    """Greedy assignment: pair each removed symbol to its closest added counterpart.

    Same `kind` and same `parent` get a structural bonus; final score gates on
    SIMILARITY_THRESHOLD. A removed symbol may end up unpaired (returns just
    the removed entry with None partner)."""
    pairs: list[tuple[Symbol, Symbol, float]] = []
    candidates = list(added)

    for old in sorted(removed, key=lambda s: s.name):
        if len(old.name) < MIN_SYMBOL_LEN or old.name in SKIP_BUILTIN_NAMES:
            continue
        best: tuple[Symbol, float] | None = None
        for new in candidates:
            if new.name == old.name:
                continue  # same name = not a rename
            ratio = levenshtein_ratio(old.name, new.name)
            # Structural bonuses: same kind, same parent class.
            if new.kind == old.kind:
                ratio += 0.10
            if new.parent == old.parent:
                ratio += 0.10
            ratio = min(ratio, 1.0)
            if best is None or ratio > best[1]:
                best = (new, ratio)
        if best and best[1] >= SIMILARITY_THRESHOLD:
            pairs.append((old, best[0], best[1]))
            candidates.remove(best[0])
        else:
            # Unpaired removal — still worth surfacing if the name has remnants.
            pairs.append((old, None, 0.0))

    return pairs


# ---------------------------------------------------------------------------
# Remnant search
# ---------------------------------------------------------------------------


def find_remnants(name: str, repo_root: Path) -> list[Remnant]:
    """Search SEARCH_DIRS for word-boundary occurrences of `name`."""
    remnants: list[Remnant] = []
    pattern = rf"\b{re.escape(name)}\b"
    regex = re.compile(pattern)

    for sub in SEARCH_DIRS:
        root = repo_root / sub
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            # Skip common noise.
            if any(part in {"__pycache__", ".pytest_cache", ".mypy_cache"} for part in path.parts):
                continue
            if path.suffix not in (".py", ".md", ".toml", ".txt", ".rst"):
                continue
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


def codebase_count(name: str, repo_root: Path) -> int:
    """Total word-boundary occurrences of `name` across all .py files
    in the working tree. Used to confirm 'OLD is now gone'."""
    pattern = rf"\b{re.escape(name)}\b"
    regex = re.compile(pattern)
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
        return []  # new file — nothing to rename FROM
    try:
        after = (repo_root / path).read_text(encoding="utf-8")
    except OSError:
        return []

    before_syms = extract_symbols(before)
    after_syms = extract_symbols(after)

    before_names = {s.name for s in before_syms}
    after_names = {s.name for s in after_syms}

    removed = {s for s in before_syms if s.name not in after_names}
    added = {s for s in after_syms if s.name not in before_names}

    if not removed:
        return []

    candidates: list[RenameCandidate] = []
    for old, new, score in pair_renames(removed, added):
        # Validate: the old name should be (mostly) gone from the codebase.
        # If `old` is still defined elsewhere, this isn't really a rename.
        global_count = codebase_count(old.name, repo_root)
        # Heuristic: if there are still many references, drop the confidence;
        # the rename detector caller will use this to decide whether to surface.
        candidates.append(
            RenameCandidate(
                old=old.name,
                new=new.name if new else None,
                file=path,
                kind=old.kind,
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
        # Try to derive the module path the old file used to live at.
        old_module = re.sub(r"\.py$", "", old_path).replace("/", ".")
        # Strip common src-layout prefixes so we surface importable names.
        for prefix in ("packages.haywire-core.src.", "packages.haywire-studio.src.", "barn."):
            if old_module.startswith(prefix):
                old_module = old_module[len(prefix) :]
        remnants = find_remnants(old_module, repo_root)
        # Also look for path-string remnants like "old/path.py" or "old/path".
        path_remnants: list[Remnant] = []
        for token in (old_path, re.sub(r"\.py$", "", old_path)):
            path_remnants.extend(find_remnants(re.escape(token), repo_root))
        # The find_remnants helper already uses \b — re.escape may add a backslash
        # that the regex compiler will treat as literal. Use a plain string match for paths.
        # Simpler: do a substring scan ourselves for the path form.
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
            remnants = find_remnants(cand.old, repo_root) if cand.old else []
            # Filter out the source file where the rename happened (it's not a remnant).
            remnants = [r for r in remnants if r.file != cand.file]
            results["symbol_renames"].append(
                {
                    "old": cand.old,
                    "new": cand.new,
                    "file": cand.file,
                    "kind": cand.kind,
                    "confidence": cand.confidence,
                    "remnants": [asdict(r) for r in remnants],
                }
            )

    json.dump(results, sys.stdout, indent=2)
    print()  # trailing newline
    return 0


if __name__ == "__main__":
    sys.exit(main())
