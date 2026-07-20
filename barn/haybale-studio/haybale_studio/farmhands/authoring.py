"""studio_scaffold_component / studio_read_component_source /
studio_write_component_source / studio_verify_component.

Authoring is self-contained through Farmhand (no client filesystem access
assumed) and kind-generic. Writes are project-local-library-only; git is the
source-level undo. Hot-reload registers new/changed files (file_watcher=True
libraries) with zero further calls.
"""

from __future__ import annotations

import inspect
from pathlib import Path

from haywire.core.errors.ledger import get_error_ledger
from haywire.core.farmhand import (
    Farmhand,
    FarmhandContext,
    FarmhandError,
    ToolAnnotations,
    farmhand,
)

from ._helpers import (
    KIND_FOLDERS,
    library_folder,
    project_local_libraries,
    resolve_component_class,
    resolve_target_library,
)

_NODE_TEMPLATE = '''"""{name} — scaffolded by Farmhand. Authoring reference: farmhand://docs/canon/nodes"""

from haywire.core.node import BaseNode, NodeType, node
from haywire.barn.builtin.types import FLOAT


@node(label="{label}", description="TODO", menu="Custom", node_type=NodeType.DATA)
class {class_name}(BaseNode):
    def init(self):
        self.add(FLOAT.as_inlet("x"))
        self.add(FLOAT.as_outlet("result"))

    def worker(self, context, x: float = 0.0) -> None:
        self.out("result", x)
'''

_GENERIC_TEMPLATE = '''"""{name} — scaffolded by Farmhand.

Kind: {kind}. Authoring reference: farmhand://docs/canon/{canon_area}
Replace this stub with a {kind} component per the canon; the library's
folder scan registers it automatically once the class is decorated.
"""
'''


def _template(kind: str, name: str) -> str:
    class_name = "".join(part.capitalize() for part in name.split("_"))
    if kind == "node":
        return _NODE_TEMPLATE.format(name=name, label=class_name, class_name=class_name)
    return _GENERIC_TEMPLATE.format(name=name, kind=kind, canon_area=KIND_FOLDERS[kind])


@farmhand(
    label="Scaffold component",
    description="Write a canon-conformant skeleton for any component kind into a project-local "
    "library; returns the path and expected registry key. Read farmhand://docs/canon/{kind} first.",
    registry_id="scaffold_component",
    annotations=ToolAnnotations(),
)
class StudioScaffoldComponentTool(Farmhand):
    async def run(self, ctx: FarmhandContext, kind: str, name: str, library: str | None = None) -> dict:
        if kind not in KIND_FOLDERS:
            raise FarmhandError(
                "bad_kind", f"kind must be one of {sorted(KIND_FOLDERS)}", ids={"kind": kind}
            )
        lib_id = resolve_target_library(ctx, library)
        folder = library_folder(ctx, lib_id) / KIND_FOLDERS[kind]
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{name}.py"
        if path.exists():
            raise FarmhandError("file_exists", f"{path} already exists.", ids={"path": str(path)})
        path.write_text(_template(kind, name), encoding="utf-8")
        expected_key = f"{lib_id}:{kind}:{name}"
        return {
            "summary": f"Scaffolded {expected_key} at {path}.",
            "path": str(path),
            "expected_registry_key": expected_key,
            "next": "Edit via studio_write_component_source, then studio_verify_component.",
        }


@farmhand(
    label="Read component source",
    description="Line-numbered source of any installed component.",
    registry_id="read_component_source",
    annotations=ToolAnnotations(read_only_hint=True),
)
class StudioReadComponentSourceTool(Farmhand):
    async def run(self, ctx: FarmhandContext, registry_key: str) -> dict:
        cls = resolve_component_class(ctx, registry_key)
        path = Path(inspect.getfile(cls))
        lines = path.read_text(encoding="utf-8").splitlines()
        numbered = "\n".join(f"{i + 1}\t{line}" for i, line in enumerate(lines))
        return {
            "summary": f"{registry_key}: {len(lines)} lines at {path}.",
            "registry_key": registry_key,
            "path": str(path),
            "source": numbered,
        }


@farmhand(
    label="Write component source",
    description="Full-source write into a project-local library only. Existing components are "
    "hot-reloaded by the file watcher; follow with studio_verify_component.",
    registry_id="write_component_source",
    annotations=ToolAnnotations(destructive_hint=True),
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
            if lib_id not in project_local_libraries(ctx):
                raise FarmhandError(
                    "not_project_library",
                    f"'{lib_id}' is not project-local; Farmhand only writes project-local sources.",
                    ids={"registry_key": registry_key},
                )
        else:
            if kind not in KIND_FOLDERS or not filename:
                raise FarmhandError(
                    "bad_arguments",
                    "Pass either registry_key=, or library=/kind=/filename= for a new file.",
                )
            lib_id = resolve_target_library(ctx, library)
            path = library_folder(ctx, lib_id) / KIND_FOLDERS[kind] / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
        return {
            "summary": f"Wrote {len(source.splitlines())} lines to {path} (hot-reload will pick it up).",
            "path": str(path),
            "library": lib_id,
        }


@farmhand(
    label="Verify component",
    description="Staged verification: registered -> (nodes) trial instantiation -> on_testrun(); "
    "error-ledger entries from the failing stage are attached.",
    registry_id="verify_component",
    annotations=ToolAnnotations(read_only_hint=True),
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

            graph = BaseGraph("farmhand_verify", "verify", validation_scheduler=SyncScheduler())
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
