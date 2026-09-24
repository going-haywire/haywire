"""studio_scaffold_component / studio_read_component_source /
studio_write_component_source / studio_verify_component.

Authoring is self-contained through Farmhand (no client filesystem access
assumed) and kind-generic. Writes are project-local-library-only; git is the
source-level undo. Hot-reload registers new/changed files (file_watcher=True
libraries) with zero further calls.
"""

from __future__ import annotations

import asyncio
import inspect
from pathlib import Path
from typing import Any

from haywire.core.access import AccessTier
from haywire.core.authoring import (
    DEFAULT_TIMEOUT_S,
    AuthoringTarget,
    RegistrationOutcome,
    RegistrationWatch,
    default_fields,
    link_libraries,
    linked_additions,
    plan_node,
    undeclared_imports,
    write_node,
)
from haywire.core.docs.canons import canon_uri
from haywire.core.errors.ledger import get_error_ledger
from haywire.core.library.registry import LibraryRegistry
from haywire.core.farmhand import (
    Farmhand,
    FarmhandContext,
    FarmhandError,
    ToolAnnotations,
    farmhand,
    truncation_note,
)

from ._helpers import (
    KIND_FOLDERS,
    kind_registry_map,
    library_folder,
    project_writable_libraries,
    resolve_component_class,
    resolve_target_library,
)

_GENERIC_TEMPLATE = '''"""{name} — scaffolded by Farmhand.

Kind: {kind}. Authoring reference: {canon_uri}
Replace this stub with a {kind} component per the canon; the library's
folder scan registers it automatically once the class is decorated.
"""
'''


def _template(kind: str, name: str) -> str:
    return _GENERIC_TEMPLATE.format(name=name, kind=kind, canon_uri=canon_uri(kind))


def _class_name(name: str) -> str:
    """``name`` as a class name: PascalCase kept, snake_case converted (``blur_filter``, ``BlurFilter``)."""
    if "_" in name or name.islower():
        return "".join(part[:1].upper() + part[1:] for part in name.split("_") if part)
    return name


_HELP_UNDECLARED = "`haywire share` declares undeclared imports."


def _registration_result(
    summary: str,
    path: Path,
    lib_id: str,
    outcome: RegistrationOutcome,
    linked_added: list[str],
    undeclared: list[str],
) -> dict:
    """The result shape shared by scaffold and write."""
    result: dict = {
        "summary": summary,
        "path": str(path),
        "library": lib_id,
        "registry_key": outcome.registry_key,
        "registration": outcome.status,
        "errors": [e.to_dict() for e in outcome.errors],
        "linked_libraries_added": linked_added,
        "undeclared_imports": undeclared,
    }
    hints = []
    if outcome.status == "timeout":
        hints.append(
            "Nothing registered in time. The library may not run a file watcher "
            "(file_watcher=True in @library); restart the studio to load the file."
        )
    elif outcome.status == "failed":
        hints.append("Fix the errors, then write the file again with studio_write_component_source.")
    if undeclared:
        hints.append(_HELP_UNDECLARED)
    if hints:
        result["help"] = " ".join(hints)
    return result


def _outcome_summary(outcome: RegistrationOutcome, path: Path) -> str:
    if outcome.status in ("added", "reloaded"):
        return f"{outcome.registry_key} {outcome.status} from {path}."
    if outcome.status == "failed":
        return f"{path} was written but failed to register ({len(outcome.errors)} errors)."
    return f"{path} was written; no registration was observed before the timeout."


async def _write_and_watch(
    registry: Any, module_name: str | None, registry_key: str | None, write: Any
) -> RegistrationOutcome:
    """Run ``write`` off the loop inside a :class:`RegistrationWatch` and return its outcome."""
    with RegistrationWatch(registry, get_error_ledger(), module_name, registry_key) as watch:
        await asyncio.to_thread(write)
        return await watch.result(DEFAULT_TIMEOUT_S)


async def _scaffold_node(ctx: FarmhandContext, lib_id: str, name: str, label: str | None) -> dict:
    """Clone the builtin Data template into ``lib_id`` and report what registered."""
    from haywire.barn.builtin.nodes.templates.data_node import DataNodeTemplate
    from haywire.core.node.registry import NodeRegistry

    library_registry = ctx.registry(LibraryRegistry)
    node_registry = ctx.registry(NodeRegistry)
    library = library_registry.get_library(lib_id)
    if library is None:  # pragma: no cover — resolve_target_library only returns registered ids
        raise FarmhandError("library_not_found", f"No library '{lib_id}' is registered.")

    fields = default_fields(DataNodeTemplate)
    fields.class_name = _class_name(name)
    fields.label = label or fields.class_name
    target = AuthoringTarget(
        library_id=lib_id,
        label=library.identity.label,
        folder=library_folder(ctx, lib_id) / KIND_FOLDERS["node"],
        is_project_library=True,
        is_watched=library.is_watched,
    )
    plan = plan_node(DataNodeTemplate, fields, target, library_registry, registry=node_registry)
    if plan.refusal is not None:
        code = "file_exists" if plan.path.exists() else "refused"
        raise FarmhandError(
            code,
            plan.refusal,
            ids={"path": str(plan.path), "registry_key": plan.registry_key},
            help="Pick another name=, or edit the existing file with studio_write_component_source.",
        )

    undeclared = undeclared_imports(plan.source, library.identity, library_registry)
    outcome = await _write_and_watch(
        node_registry, plan.module_name, plan.registry_key, lambda: write_node(plan, library)
    )
    return _registration_result(
        _outcome_summary(outcome, plan.path), plan.path, lib_id, outcome, plan.linked_additions, undeclared
    )


@farmhand(
    label="Scaffold component",
    description="Write a canon-conformant skeleton for a new component into a project-local library.",
    instructions="Write a canon-conformant skeleton for any component kind into a project-local "
    "library. kind=node clones the builtin Data node template: name= is the class name "
    "(snake_case is converted), label= defaults to it; the result reports the registry_key that "
    "actually registered and registration ('added' | 'failed' | 'timeout'). Other kinds get a "
    "stub to fill in. Read the kind's canon first — find it via the farmhand://docs/_manifest "
    "index (e.g. components/nodes/node-canon.md).",
    registry_id="scaffold_component",
    annotations=ToolAnnotations(),
    access=AccessTier.ADMIN,
)
class StudioScaffoldComponentTool(Farmhand):
    async def run(
        self,
        ctx: FarmhandContext,
        kind: str,
        name: str,
        library: str | None = None,
        label: str | None = None,
    ) -> dict:
        if kind not in KIND_FOLDERS:
            raise FarmhandError(
                "bad_kind", f"kind must be one of {sorted(KIND_FOLDERS)}", ids={"kind": kind}
            )
        lib_id = resolve_target_library(ctx, library)
        if kind == "node":
            return await _scaffold_node(ctx, lib_id, name, label)
        folder = library_folder(ctx, lib_id) / KIND_FOLDERS[kind]
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{name}.py"
        if path.exists():
            raise FarmhandError(
                "file_exists",
                f"{path} already exists.",
                ids={"path": str(path)},
                help=(
                    f"Pick another name=, or edit the existing file with "
                    f"studio_write_component_source registry_key={lib_id}:{kind}:{name}."
                ),
            )
        path.write_text(_template(kind, name), encoding="utf-8")
        expected_key = f"{lib_id}:{kind}:{name}"
        return {
            "summary": f"Scaffolded {expected_key} at {path}.",
            "path": str(path),
            "expected_registry_key": expected_key,
            "next": "Edit via studio_write_component_source, then studio_verify_component.",
        }


_SOURCE_LINE_CAP = 400
"""Lines returned by default. Most component files fit well under this; the cap
exists so one call on a large module cannot blow the caller's context. Line
numbering stays absolute, so a windowed read can be cited and edited directly."""


@farmhand(
    label="Read component source",
    description="Line-numbered source of any installed component.",
    instructions="Line-numbered source of any installed component. Returns the first "
    f"{_SOURCE_LINE_CAP} lines by default; pass offset= to window further in, or full=true "
    "for the entire file. Truncated results say so in the summary and report total_lines.",
    registry_id="read_component_source",
    annotations=ToolAnnotations(read_only_hint=True),
    access=AccessTier.VIEW,
)
class StudioReadComponentSourceTool(Farmhand):
    async def run(
        self,
        ctx: FarmhandContext,
        registry_key: str,
        offset: int = 0,
        limit: int = _SOURCE_LINE_CAP,
        full: bool = False,
    ) -> dict:
        cls = resolve_component_class(ctx, registry_key)
        path = Path(inspect.getfile(cls))
        lines = path.read_text(encoding="utf-8").splitlines()
        total = len(lines)

        window = lines[offset:] if full else lines[offset : offset + limit]
        # Absolute line numbers: a windowed read stays quotable against the file.
        numbered = "\n".join(f"{offset + i + 1}\t{line}" for i, line in enumerate(window))

        summary = f"{registry_key}: {total} lines at {path}."
        result: dict = {
            "summary": summary,
            "registry_key": registry_key,
            "path": str(path),
            "total_lines": total,
            "source": numbered,
        }
        note = truncation_note(len(window), total, offset)
        if note:
            end = offset + len(window)
            result["summary"] = f"{summary}{note}"
            result["help"] = (
                f"Run studio_read_component_source registry_key={registry_key!r} offset={end} "
                f"for the next lines, or full=true for the whole file."
            )
        return result


@farmhand(
    label="Write component source",
    description="Full-source write into a project-local library only.",
    instructions="Full-source write into a project-local library only. Haywire libraries the source "
    "imports are added to the library's linked_libraries first; the file watcher then registers "
    "or hot-reloads it, and the result reports registration ('added' | 'reloaded' | 'failed' | "
    "'timeout'), the observed registry_key, ledger errors, linked_libraries_added and "
    "undeclared_imports (pyproject declarations `haywire share` will ask for). Follow with "
    "studio_verify_component.",
    registry_id="write_component_source",
    annotations=ToolAnnotations(destructive_hint=True),
    access=AccessTier.ADMIN,
)
class StudioWriteComponentSourceTool(Farmhand):
    async def run(
        self,
        ctx: FarmhandContext,
        source: str,
        registry_key: str | None = None,
        library: str | None = None,
        kind: str | None = None,
        filename: str | None = None,
    ) -> dict:
        if registry_key is not None:
            cls = resolve_component_class(ctx, registry_key)
            path = Path(inspect.getfile(cls))
            lib_id = registry_key.split(":")[0]
            if lib_id not in project_writable_libraries(ctx):
                raise FarmhandError(
                    "not_project_library",
                    f"'{lib_id}' is not project-local; Farmhand only writes project-local sources.",
                    ids={"registry_key": registry_key},
                    help=(
                        "Run studio_list_libraries to see which libraries are writable, "
                        "or copy this component into a project-local library first."
                    ),
                )
        else:
            if kind not in KIND_FOLDERS or not filename:
                raise FarmhandError(
                    "bad_arguments",
                    "Pass either registry_key=, or library=/kind=/filename= for a new file.",
                )
            lib_id = resolve_target_library(ctx, library)
            path = library_folder(ctx, lib_id) / KIND_FOLDERS[kind] / filename
        component_kind = registry_key.split(":")[1] if registry_key is not None else kind
        assert component_kind is not None
        library_registry = ctx.registry(LibraryRegistry)
        target_library = library_registry.get_library(lib_id)
        identity = library_registry.get_library_identity(lib_id)
        registry: Any = ctx.registry(kind_registry_map()[component_kind])

        # Linked registration first, so the module registers under the refreshed scopes.
        additions = linked_additions(source, identity, library_registry)
        linked_added = link_libraries(target_library, additions) if target_library is not None else []
        undeclared = undeclared_imports(source, identity, library_registry)

        module_name: str | None = None
        watch_key = registry_key
        if hasattr(registry, "resolve_module_name"):
            module_name = registry.resolve_module_name(path, identity.folder_path, identity.module_name)
        elif watch_key is None:
            # A document registry keys a file by its stem and has no module.
            watch_key = f"{lib_id}:{component_kind}:{path.stem}"

        def _write() -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(source, encoding="utf-8")

        outcome = await _write_and_watch(registry, module_name, watch_key, _write)
        summary = f"Wrote {len(source.splitlines())} lines to {path}. {_outcome_summary(outcome, path)}"
        return _registration_result(summary, path, lib_id, outcome, linked_added, undeclared)


@farmhand(
    label="Verify component",
    description="Staged verification that a component registers and runs cleanly.",
    instructions="Staged verification: registered -> (nodes) trial instantiation -> on_testrun(); "
    "error-ledger entries from the failing stage are attached.",
    registry_id="verify_component",
    annotations=ToolAnnotations(read_only_hint=True),
    access=AccessTier.VIEW,
)
class StudioVerifyComponentTool(Farmhand):
    async def run(self, ctx: FarmhandContext, registry_key: str) -> dict:
        ledger = get_error_ledger()
        start_seq = ledger.current_seq
        result: dict = {"registry_key": registry_key, "registered": False, "stage_reached": "none"}

        resolve_component_class(ctx, registry_key)  # raises component_not_found if absent
        result["registered"] = True
        result["stage_reached"] = "registered"

        if registry_key.split(":")[1] == "node":
            from haywire.core.graph.base import BaseGraph
            from haywire.core.graph.scheduler import SyncScheduler

            graph = BaseGraph("verify", validation_scheduler=SyncScheduler())
            try:
                wrapper = graph.create_node_wrapper(registry_key)
                if wrapper is None:
                    raise FarmhandError(
                        "instantiation_failed",
                        f"Trial NodeWrapper instantiation failed for '{registry_key}'.",
                        ids={"registry_key": registry_key},
                    )
                result["stage_reached"] = "instantiated"
                ok, message = wrapper.node.on_testrun()
                result["stage_reached"] = "testrun"
                result["testrun_ok"] = ok
                if message:
                    result["testrun_message"] = message
            finally:
                graph.cleanup()

        errors = ledger.query(since_seq=start_seq, limit=20)
        # The ledger holds live HaywireException objects; serialize to dicts at
        # this MCP boundary.
        result["errors"] = [e.to_dict() for e in errors.entries]
        result["summary"] = (
            f"{registry_key}: verified through stage '{result['stage_reached']}' "
            f"({len(errors.entries)} ledger entries)."
        )
        return result
