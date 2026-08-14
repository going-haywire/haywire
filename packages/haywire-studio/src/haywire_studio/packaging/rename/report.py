"""Rendering a RenamePlan for the terminal."""

from __future__ import annotations

from .model import FileChange, RenamePlan


def _files_line(label: str, changes: list[FileChange]) -> str:
    if not changes:
        return ""
    total = sum(change.count for change in changes)
    noun = "file" if len(changes) == 1 else "files"
    return f"  {label:<18} {total} change(s) in {len(changes)} {noun}"


def render_plan(plan: RenamePlan, *, verbose: bool = False) -> str:
    lines: list[str] = [
        "",
        f"Rename  {plan.old_dist}  →  {plan.new_dist}",
        f"        module  {plan.old_module} → {plan.new_module}",
        "",
    ]

    if plan.blockers:
        lines.append("  BLOCKED")
        lines.append("")
        for blocker in plan.blockers:
            lines.append(f"  ✗ {blocker.message}")
            if blocker.remedy:
                lines += [f"      {line}" for line in blocker.remedy.splitlines()]
            lines.append("")
        return "\n".join(lines)

    lines += [
        "  ✓ Working tree clean",
        "  ✓ No blocking collisions",
        "  ✓ Write access confirmed",
        "",
    ]

    for label, changes in (
        ("Library config", plan.toml_changes),
        ("Python sources", plan.python_changes),
        ("Graphs", plan.graph_changes),
        ("Dependents", plan.dependent_changes),
    ):
        line = _files_line(label, changes)
        if line:
            lines.append(line)
            if verbose:
                lines += [f"      {c.path}  ({c.count})" for c in changes]

    lines.append("")

    if plan.unrecognized:
        lines.append(
            f"  ⚠ {len(plan.unrecognized)} unrecognized occurrence(s) of "
            f'"{plan.old_dist}"/"{plan.old_module}" — not patched'
        )
        if verbose:
            for occurrence in plan.unrecognized:
                where = f":{occurrence.line}" if occurrence.line else ""
                lines.append(f"      {occurrence.path}{where}  {occurrence.text}")
        else:
            lines.append("      (re-run with --verbose to inspect)")
        lines.append("")

    for warning in plan.warnings:
        lines.append(f"  ⚠ {warning.message}")
        if warning.remedy:
            lines.append(f"      {warning.remedy}")
        lines.append("")

    return "\n".join(lines)
