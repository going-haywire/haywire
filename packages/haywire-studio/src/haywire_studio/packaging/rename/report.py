"""Rendering rename plans for the terminal."""

from __future__ import annotations

from .model import FileChange, KeyMapPlan, RenamePlan


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


def render_key_map_plan(plan: KeyMapPlan, *, verbose: bool = False) -> str:
    """Render a key-map plan: per-entry counts, drift, and what the mode leaves alone."""
    lines: list[str] = ["", f"Rename by key map  {plan.map_path}", ""]

    if plan.blockers:
        lines.append("  BLOCKED")
        lines.append("")
        for blocker in plan.blockers:
            lines.append(f"  ✗ {blocker.message}")
            if blocker.remedy:
                lines += [f"      {line}" for line in blocker.remedy.splitlines()]
            lines.append("")
        return "\n".join(lines)

    lines += ["  ✓ Working tree clean", "  ✓ Write access confirmed", ""]

    found = [rename for rename in plan.renames if plan.key_counts.get(rename.old)]
    missing = [rename for rename in plan.renames if not plan.key_counts.get(rename.old)]
    old_width = max((len(rename.old) for rename in found), default=0)
    new_width = max((len(rename.new) for rename in found), default=0)
    lines.append(f"  {len(found)} of {len(plan.renames)} map entr(ies) found in graphs")
    for rename in found:
        lines.append(
            f"      {rename.old:<{old_width}}  →  {rename.new:<{new_width}}  "
            f"{plan.key_counts[rename.old]} key(s) in {plan.key_graphs[rename.old]} graph(s)"
        )
    if missing:
        lines.append(f"  {len(missing)} entr(ies) not found in any graph")
        if verbose:
            lines += [f"      {rename.old}" for rename in missing]
    lines.append("")

    line = _files_line("Graphs", plan.graph_changes)
    if line:
        lines.append(line)
        if verbose:
            lines += [f"      {c.path}  ({c.count})" for c in plan.graph_changes]
    lines.append(f"  {'Descriptive copies':<18} {plan.copies} (class_name, registry_id, module)")
    lines.append("")

    if plan.unrecognized:
        lines.append(f"  ⚠ {len(plan.unrecognized)} unrecognized occurrence(s) of an old key — not patched")
        if verbose:
            for occurrence in plan.unrecognized:
                lines.append(f"      {occurrence.path}  {occurrence.text}")
        else:
            lines.append("      (re-run with --verbose to inspect)")
        lines.append("")

    lines += [
        "  Not rewritten: Python sources, tests and docs. Rename the classes in code",
        "  yourself, then look for string references the IDE missed (in the haywire",
        "  repo: /check-rename).",
        "",
    ]
    return "\n".join(lines)
