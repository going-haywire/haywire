"""The New Node flow's state machine, free of NiceGUI calls.

Four steps, of which only the third mutates:

    source    a Node template or a node class to clone          -> Details
    details   label, class name, menu, tags, description, library -> Plan
    planned   the file that would be written, and any refusal   -> Create
    result    terminal: the registered key, or why it failed

Opened on a selected node, the flow starts at ``details`` with that node's
class as the source. The planned step is read-only: ``plan_node`` answers
what would be written without touching disk
(``.insights/project_stepper_flows.md``). Create writes the file and waits
for the file watcher to register it; the wizard never registers it itself.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Literal, Optional, Protocol

from haywire.core.authoring import (
    DEFAULT_TIMEOUT_S,
    AuthoringTarget,
    NodeFields,
    NodePlan,
    RegistrationOutcome,
    RegistrationWatch,
    class_name_refusal,
    default_fields,
    module_stem,
    plan_node,
    suggest_class_name,
    write_node,
)
from haywire.core.library.utils import NODE, reg_key
from haywire.core.node.info import NodeInfo, matches_query
from haywire.ui.components.popup import Popup
from haywire.ui.components.stepper import StepFlow

from .copy import STEP_TITLES, STEPS

if TYPE_CHECKING:
    from haywire.core.errors.ledger import ErrorLedger

logger = logging.getLogger(__name__)

SourceMode = Literal["template", "clone"]


class NewNodeHost(Protocol):
    """The slice of the editor the flow's result step drives."""

    def place(self, registry_key: str) -> None:
        """Add one node of ``registry_key`` to the graph, as one undoable action."""
        ...

    def reveal_component(self, registry_key: str) -> None:
        """Show the component's source in the source editor."""
        ...

    def open_file(self, path: Path) -> None:
        """Open ``path`` in the file editor."""
        ...


class NewNodeFlow(StepFlow):
    """Linear, resumable state machine for the New Node wizard.

    Args:
        host: Places the node and opens editors from the result step.
        targets: The libraries the node may be written into, best first.
        libraries: The installed libraries (a ``LibraryRegistry``): identities,
            haywire-library lookup for linked additions, and ``get_library``
            for the write.
        registry: The ``NodeRegistry``, for key checks and the registration watch.
        ledger: The error ledger a failed import is reported to.
        templates: Node templates grouped by library label, as
            ``NodeFactory.list_templates`` returns them.
        clone_sources: Node classes that may be cloned, as ``NodeInfo``.
        resolve: Maps a registry key to its node class, or ``None``.
        menu_paths: Existing menu paths, offered as menu choices.
        source_cls: The class to clone; the flow then starts at ``details``.
        timeout_s: How long Create waits for the registry's answer.
    """

    STEPS = STEPS
    STEP_TITLES = STEP_TITLES

    def __init__(
        self,
        *,
        host: NewNodeHost,
        targets: list[AuthoringTarget],
        libraries: Any,
        registry: Any,
        ledger: "ErrorLedger",
        templates: Optional[dict[str, list[NodeInfo]]] = None,
        clone_sources: Optional[list[NodeInfo]] = None,
        resolve: Callable[[str], Any] = lambda _key: None,
        menu_paths: Optional[list[str]] = None,
        source_cls: Any = None,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        popup: Optional[Popup] = None,
    ) -> None:
        super().__init__()
        self.host = host
        self.targets = targets
        self.libraries = libraries
        self.registry = registry
        self.ledger = ledger
        self.templates = templates or {}
        self.clone_sources = clone_sources or []
        self.resolve = resolve
        self.menu_paths = sorted(set(menu_paths or []))
        self.timeout_s = timeout_s
        self.popup = popup

        self.mode: SourceMode = "template"
        self.query: str = ""
        self.target: AuthoringTarget | None = targets[0] if targets else None

        self.source_cls: Any = None
        self.fields: NodeFields = NodeFields(label="", class_name="", menu="")
        self.class_name_edited = False

        self.plan: NodePlan | None = None
        self.outcome: RegistrationOutcome | None = None

        if source_cls is not None:
            self._set_source(source_cls)
            self.step = "details"

    # ── source ───────────────────────────────────────────────────────────────

    def source_rows(self) -> list[tuple[str, NodeInfo]]:
        """The rows the Source step lists for the current mode and query, as ``(group, info)``.

        Templates group by library, clone sources by menu path; both sort by
        group, then label.
        """
        if self.mode == "template":
            rows = [(library, info) for library, infos in self.templates.items() for info in infos]
        else:
            rows = [(info.identity.menu or "misc", info) for info in self.clone_sources]
        rows = [(group, info) for group, info in rows if matches_query(info, self.query)]
        return sorted(rows, key=lambda row: (row[0].lower(), row[1].identity.label.lower()))

    def pick(self, info: NodeInfo) -> bool:
        """Make ``info``'s class the source. Returns ``False`` when its class no longer resolves."""
        cls = self.resolve(info.identity.registry_key)
        if cls is None:
            self.error = f"'{info.identity.label}' is no longer registered."
            return False
        self._set_source(cls)
        return True

    def _set_source(self, source_cls: Any) -> None:
        self.source_cls = source_cls
        self.fields = default_fields(source_cls)
        self.class_name_edited = False
        self.plan = None

    async def advance_from_source(self) -> None:
        """Move to the details step once a source is picked."""
        self.retry()
        if self.source_cls is None:
            self.error = "Pick a template or a node to start from."
            return
        self.step = "details"

    # ── details ──────────────────────────────────────────────────────────────

    def set_label(self, label: str) -> None:
        """Set the label; the class name follows it until the user edits the class name."""
        self.fields.label = label
        if not self.class_name_edited:
            self.fields.class_name = suggest_class_name(label)

    def set_class_name(self, class_name: str) -> None:
        """Set the class name, which stops it following the label."""
        self.fields.class_name = class_name.strip()
        self.class_name_edited = True

    def set_target(self, library_id: str) -> None:
        self.target = next((t for t in self.targets if t.library_id == library_id), self.target)

    @property
    def file_name(self) -> str:
        """The file the class is written to, relative to the library (``nodes/blur_filter.py``)."""
        folder = self.target.folder.name if self.target is not None else "nodes"
        return f"{folder}/{module_stem(self.fields.class_name)}.py"

    @property
    def registry_key(self) -> str:
        """The key the new node registers under."""
        library_id = self.target.library_id if self.target is not None else ""
        return reg_key(library_id, NODE, self.fields.class_name)

    @property
    def details_refusal(self) -> str | None:
        """Why the details cannot be planned, or ``None``. For live validation."""
        if self.target is None:
            return "No library in this project can receive a node."
        if not self.fields.label.strip():
            return "Enter a label."
        refusal = class_name_refusal(self.fields.class_name)
        if refusal is not None:
            return refusal
        if self.registry.has(self.registry_key):
            return f"A node '{self.registry_key}' is already registered."
        if (self.target.folder / f"{module_stem(self.fields.class_name)}.py").exists():
            return f"'{self.file_name}' already exists in this library."
        return None

    async def advance_from_details(self) -> None:
        """Describe the file that would be written. Read-only."""
        self.retry()
        if self.target is None or self.source_cls is None:
            self.error = self.details_refusal or "Pick a template or a node to start from."
            return
        try:
            self.plan = await asyncio.to_thread(
                plan_node,
                self.source_cls,
                NodeFields(**vars(self.fields)),
                self.target,
                self.libraries,
                registry=self.registry,
            )
        except Exception as exc:  # noqa: BLE001 — surfaced inline, never swallowed
            self.fail(exc)
            return
        self.step = "planned"

    # ── planned ──────────────────────────────────────────────────────────────

    async def advance_from_planned(self) -> None:
        """Write the file and wait for the registry's answer. The mutating step."""
        self.retry()
        plan, target = self.plan, self.target
        if plan is None or target is None:  # pragma: no cover — unreachable via the flow
            self.error = "Nothing planned to create."
            return
        if plan.refusal is not None:
            self.error = plan.refusal
            return
        library = self.libraries.get_library(target.library_id)
        if library is None:
            self.error = f"The library '{target.label}' is no longer loaded."
            return

        try:
            with RegistrationWatch(self.registry, self.ledger, plan.module_name, plan.registry_key) as watch:
                await asyncio.to_thread(write_node, plan, library)
                self.outcome = await watch.result(self.timeout_s)
        except Exception as exc:  # noqa: BLE001 — surfaced inline, never swallowed
            self.fail(exc)
            return
        self.step = "result"

    # ── result ───────────────────────────────────────────────────────────────

    @property
    def succeeded(self) -> bool:
        """Whether the new node registered."""
        return self.outcome is not None and self.outcome.status in ("added", "reloaded")

    def place(self) -> None:
        """Add the new node to the graph."""
        if self.succeeded and self.outcome is not None and self.outcome.registry_key:
            self.host.place(self.outcome.registry_key)

    def edit(self) -> None:
        """Open the new node's source."""
        if self.succeeded and self.outcome is not None and self.outcome.registry_key:
            self.host.reveal_component(self.outcome.registry_key)

    def open_file(self) -> None:
        """Open the written file, for a node that did not register."""
        if self.plan is not None:
            self.host.open_file(self.plan.path)
