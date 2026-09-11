#!/usr/bin/env python3
"""Find verbose docstrings and comments, and check that a diff changes only docs.

Usage::

    python docstring_audit.py scan [PATH ...] [--top N]
    python docstring_audit.py verify [PATH ...] [--base REF]

``scan`` lists docstrings and comment blocks that exceed the length guide or
contain phrasing the docs standard discourages, worst first. Flags are hints
for a human or agent to review, not verdicts.

``verify`` compares every changed Python file with ``REF`` (default ``HEAD``)
after removing docstrings and comments. Exits with status 1 if any code
changed.
"""
from __future__ import annotations

import argparse
import ast
import inspect
import io
import re
import subprocess
import sys
import tokenize
from dataclasses import dataclass
from pathlib import Path

# Maximum prose lines per docstring kind. Blank lines and indented literal
# blocks (examples) are not counted.
LIMITS = {"private": 5, "function": 10, "class": 20, "module": 25}
COMMENT_BLOCK_LIMIT = 4

PATTERNS = {
    "history": re.compile(
        r"\b(used to|previously|no longer|originally|formerly|was changed|"
        r"were changed|has been changed|the old |before this change|"
        r"now (?:uses|reads|returns|goes|lives|asks))",
        re.IGNORECASE,
    ),
    "argument": re.compile(
        r"\b(deliberately|intentionally|rather than|instead of|by accident|"
        r"honest(?:ly)?|rejected|the only place|nobody|nothing asks)\b",
        re.IGNORECASE,
    ),
}
CAPS_WORD = re.compile(r"(?<![\w.`\[])([A-Z][A-Z0-9_]+)(?![\w`(\[\]])")
CODE_SPAN = re.compile(r"``.*?``|`[^`]*`")
ACRONYMS = {
    "ADR", "API", "ASCII", "CLI", "CPU", "CSS", "CSV", "DB", "EOF", "FIXME",
    "GPU", "GUI", "HTML", "HTTP", "HTTPS", "ID", "IDE", "IDS", "IO", "IP",
    "ISO", "JSON", "MIME", "NOTE", "OK", "ORM", "OS", "PDF", "PNG", "RAM",
    "README", "RGB", "RGBA", "SDK", "SQL", "TCP", "TODO", "UDP", "UI", "URL",
    "UTC", "UTF", "UUID", "XML", "XXX", "YAML",
}
SKIP_COMMENT = re.compile(
    r"^#\s*(noqa|type:|pragma|fmt:|pylint:|mypy:|isort:|ruff:|-\*-|!)", re.IGNORECASE
)
SKIP_DIRS = {".git", ".venv", "venv", "env", "node_modules", "build", "dist",
             "__pycache__", "site-packages", ".tox", ".nox", ".mypy_cache"}


@dataclass
class Finding:
    path: str
    line: int
    what: str
    lines: int
    limit: int
    flags: list[str]

    @property
    def score(self) -> int:
        return max(0, self.lines - self.limit) + 3 * len(self.flags)

    def __str__(self) -> str:
        size = f"{self.lines} lines (limit {self.limit})"
        flags = f"  [{'; '.join(self.flags)}]" if self.flags else ""
        return f"{self.path}:{self.line}  {self.what}  {size}{flags}"


# ---------------------------------------------------------------- scan

def python_files(paths: list[str]) -> list[Path]:
    """Return the Python files under ``paths``, skipping virtualenvs and build output."""
    try:
        out = subprocess.run(
            ["git", "ls-files", "--", *(paths or ["."])],
            capture_output=True, text=True, check=True,
        ).stdout
        files = [Path(p) for p in out.splitlines() if p.endswith(".py")]
        if files:
            return files
    except (OSError, subprocess.CalledProcessError):
        pass
    found: list[Path] = []
    for root in (Path(p) for p in (paths or ["."])):
        candidates = [root] if root.is_file() else root.rglob("*.py")
        found += [f for f in candidates if not SKIP_DIRS & set(f.parts)]
    return found


def identifiers(tree: ast.AST) -> set[str]:
    """Return every name defined, imported, or referenced in ``tree``."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, ast.alias):
            names.add((node.asname or node.name).split(".")[-1])
    return names


def phrase_flags(text: str, known: set[str]) -> list[str]:
    """Return flags for discouraged phrasing in ``text``."""
    flags = []
    for name, pattern in PATTERNS.items():
        hits = sorted({m.group(0).strip().lower() for m in pattern.finditer(text)})
        if hits:
            flags.append(f"{name}: {', '.join(hits)}")
    prose = CODE_SPAN.sub("", text)
    caps = sorted({w for w in CAPS_WORD.findall(prose) if w not in known and w not in ACRONYMS})
    if caps:
        flags.append(f"caps: {', '.join(caps)}")
    return flags


def prose_lines(doc: str) -> list[str]:
    """Return the non-blank lines of ``doc`` outside code blocks.

    Both indented blocks (reST ``::`` and Markdown) and fenced Markdown blocks
    count as code.
    """
    prose, fence = [], None
    for ln in doc.splitlines():
        marker = ln.strip()[:3]
        if fence:
            if marker == fence:
                fence = None
            continue
        if marker in ("```", "~~~"):
            fence = marker
            continue
        if ln.strip() and not ln.startswith("    "):
            prose.append(ln)
    return prose


def scan_docstrings(path: str, tree: ast.AST, known: set[str]) -> list[Finding]:
    findings = []
    nodes = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
    for node in ast.walk(tree):
        if not isinstance(node, nodes):
            continue
        raw = ast.get_docstring(node, clean=False)
        if raw is None:
            continue
        doc = inspect.cleandoc(raw)
        if isinstance(node, ast.Module):
            kind, what = "module", "module"
        elif isinstance(node, ast.ClassDef):
            kind, what = "class", f"class {node.name}"
            if node.name.startswith("_"):
                kind = "private"
        else:
            dunder = node.name.startswith("__") and node.name.endswith("__")
            kind = "private" if node.name.startswith("_") and not dunder else "function"
            what = f"def {node.name}"
        prose = prose_lines(doc)
        flags = phrase_flags("\n".join(prose), known)
        limit = LIMITS[kind]
        if len(prose) > limit or flags:
            findings.append(Finding(path, node.body[0].lineno, what, len(prose), limit, flags))
    return findings


def scan_comments(path: str, source: str, known: set[str]) -> list[Finding]:
    """Group consecutive full-line comments into blocks and flag long or discouraged ones."""
    lines = source.splitlines()
    blocks: list[tuple[int, list[str]]] = []
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except (tokenize.TokenError, SyntaxError):
        return []
    for tok in tokens:
        if tok.type != tokenize.COMMENT or SKIP_COMMENT.match(tok.string):
            continue
        row = tok.start[0]
        full_line = lines[row - 1].strip().startswith("#")
        if full_line and blocks and blocks[-1][0] + len(blocks[-1][1]) == row:
            blocks[-1][1].append(tok.string)
        else:
            blocks.append((row, [tok.string]))
    findings = []
    for row, block in blocks:
        text = "\n".join(c.lstrip("#").strip() for c in block)
        if row <= 5 and re.search(r"copyright|license|spdx", text, re.IGNORECASE):
            continue
        flags = phrase_flags(text, known)
        if len(block) > COMMENT_BLOCK_LIMIT or flags:
            findings.append(Finding(path, row, "comment", len(block), COMMENT_BLOCK_LIMIT, flags))
    return findings


def cmd_scan(args: argparse.Namespace) -> int:
    parsed: list[tuple[str, str, ast.AST]] = []
    for f in python_files(args.paths):
        try:
            source = f.read_text(encoding="utf-8")
            parsed.append((str(f), source, ast.parse(source)))
        except (SyntaxError, UnicodeDecodeError, OSError) as exc:
            print(f"{f}: skipped ({exc.__class__.__name__})", file=sys.stderr)
    known = set().union(*(identifiers(t) for _, _, t in parsed)) if parsed else set()
    findings: list[Finding] = []
    for path, source, tree in parsed:
        findings += scan_docstrings(path, tree, known)
        findings += scan_comments(path, source, known)
    findings.sort(key=lambda f: (-f.score, f.path, f.line))
    shown = findings[: args.top] if args.top else findings
    for finding in shown:
        print(finding)
    files = len({f.path for f in findings})
    print(f"\n{len(findings)} findings in {files} of {len(parsed)} files"
          + (f" (showing {len(shown)})" if len(shown) < len(findings) else ""))
    return 0


# ---------------------------------------------------------------- verify

class _StripDocs(ast.NodeTransformer):
    """Remove bare string statements (docstrings and no-op strings)."""

    def visit_Expr(self, node: ast.Expr):
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            return None
        return self.generic_visit(node)


def _is_noop(stmt: ast.stmt) -> bool:
    return isinstance(stmt, ast.Pass) or (
        isinstance(stmt, ast.Expr)
        and isinstance(stmt.value, ast.Constant)
        and stmt.value.value is Ellipsis
    )


def code_fingerprint(source: str) -> str:
    """Return an AST dump of ``source`` that ignores docstrings and comments."""
    tree = _StripDocs().visit(ast.parse(source))
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if isinstance(body, list) and all(_is_noop(s) for s in body):
            node.body = [ast.Pass()]
    return ast.dump(tree, include_attributes=False)


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout


def cmd_verify(args: argparse.Namespace) -> int:
    root = Path(git("rev-parse", "--show-toplevel").strip())
    status = git("diff", "--name-status", "-M", args.base, "--", *(args.paths or ["."]))
    untracked = git("ls-files", "--others", "--exclude-standard", "--", *(args.paths or ["."]))
    failures, warnings, checked = [], [], 0

    for line in status.splitlines():
        parts = line.split("\t")
        code, old, new = parts[0][0], parts[1], parts[-1]
        if not new.endswith(".py"):
            continue
        if code == "D":
            failures.append(f"{old}: deleted")
            continue
        if code == "A":
            warnings.append(f"{new}: new file, not compared")
            continue
        try:
            before = code_fingerprint(git("show", f"{args.base}:{old}"))
            after = code_fingerprint((root / new).read_text(encoding="utf-8"))
        except SyntaxError as exc:
            failures.append(f"{new}: does not parse ({exc.msg}, line {exc.lineno})")
            continue
        checked += 1
        if before != after:
            failures.append(f"{new}: code changed, not just docstrings or comments")

    for path in untracked.splitlines():
        if path.endswith(".py"):
            warnings.append(f"{path}: untracked, not compared")

    for msg in warnings:
        print(f"warning: {msg}")
    for msg in failures:
        print(f"FAIL: {msg}")
    print(f"\nchecked {checked} changed file(s) against {args.base}: "
          + ("code unchanged" if not failures else f"{len(failures)} problem(s)"))
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    scan = sub.add_parser("scan", help="list verbose or flagged docstrings and comments")
    scan.add_argument("paths", nargs="*")
    scan.add_argument("--top", type=int, default=0, help="show only the N worst findings")
    verify = sub.add_parser("verify", help="check that only docstrings and comments changed")
    verify.add_argument("paths", nargs="*")
    verify.add_argument("--base", default="HEAD", help="git ref to compare with (default HEAD)")
    args = parser.parse_args()
    return cmd_scan(args) if args.command == "scan" else cmd_verify(args)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:  # output piped to head or similar
        sys.exit(0)
