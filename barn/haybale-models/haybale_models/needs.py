"""The needs-list: which models the open graphs are missing.

:class:`NeedsWatcher` walks every open graph (Subgraph and macro interiors included) for
``MODEL_REF`` values that resolve to no local file, posts one graph notice per graph with
the total, and marks each affected card with a ``"model"`` warning. It re-walks a graph
(debounced, off the UI thread) when the graph validates and when the index, the download
queue or the catalog change.

Lock order (``.insights/project_execution_group_lock_order.md``): the watcher's own lock
guards its dicts only and is never held across a call into a graph, a node or the notice
store. Walks and posts run under ``_run_lock``, which no validation callback ever takes.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

from haywire.core.access import AccessTier
from haywire.core.models import ModelCatalogRegistry
from haywire.ui import elements as hui

from haybale_graph_editor.notices import GraphNotice
from haybale_models.consumer import KIND, MISSING_WARNING, preference_for
from haybale_models.download import DownloadJob, DownloadQueue
from haybale_models.keys import NEEDS_NOTICE
from haybale_models.matcher import Preference
from haybale_models.resolver import FetchSpec, ModelMissing, ResolvedModel, resolve
from haybale_models.state.models_view_state import ModelsViewState
from haybale_models.store.index import ModelIndex
from haybale_models.value.model_ref import ModelRef

if TYPE_CHECKING:
    from pathlib import Path

    from haywire.core.graph.base import BaseGraph
    from haywire.core.node.node_wrapper import NodeWrapper
    from haywire.core.session.context import SessionContext

    from haybale_graph_editor.state.graph_app_state import GraphAppState

logger = logging.getLogger(__name__)

DEBOUNCE_S = 0.2
"""Quiet time before a graph is re-walked."""

TEXT_THROTTLE_S = 1.0
"""Minimum seconds between two changes of a graph's progress text.

The haystack popup closes on any redraw signal, so progress must not post every tick.
"""

_ACTIVE = ("queued", "running")

ResolveFn = Callable[[ModelRef, Preference], ResolvedModel]


@dataclass(frozen=True)
class NeededModel:
    """One model a graph needs and does not have, from the first node that asks for it."""

    node_id: str
    port_id: str
    label: str
    spec: FetchSpec
    size: int | None
    node_ids: list[str] = field(default_factory=list)
    """Every node asking for this spec (``node_id`` is the first)."""


@dataclass
class NeedsReport:
    """The deduplicated missing models of one graph tree."""

    missing: list[NeededModel] = field(default_factory=list)
    total_bytes: int = 0
    """Sum of the known sizes."""
    unknown_size: int = 0
    """How many missing models have no known size."""
    nodes: list[NodeWrapper] = field(default_factory=list)
    """Every node holding a reference with no local file, fetchable or not."""


def format_size(size: int) -> str:
    """Return *size* in bytes as ``"12.0 MB"`` (decimal units)."""
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1000 or unit == "GB":
            return f"{int(value)} B" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1000
    return f"{value:.1f} GB"  # pragma: no cover


def _spec_size(spec: FetchSpec) -> int | None:
    if spec.resource is not None:
        return spec.resource.total_size
    return spec.ref.size if spec.ref is not None else None


def _spec_label(spec: FetchSpec) -> str:
    if spec.entry is not None:
        return str(spec.entry.name)
    if spec.ref is not None:
        return spec.ref.label or spec.ref.source or ""
    return ""


def tree(graph: BaseGraph) -> list[BaseGraph]:
    """Return *graph* and every Subgraph definition below it."""
    found = [graph]
    for definition in list(graph.subgraphs.values()):
        found.extend(tree(definition))
    return found


def collect_needs(graph: BaseGraph, resolve_fn: ResolveFn) -> NeedsReport:
    """Return the models *graph* and its interiors need and lack.

    Only ``MODEL_REF`` ports holding their own value count: a wired port gets its value
    from upstream and an empty one asks for nothing. Models are deduplicated by spec
    identity.
    """
    from haybale_models.types.model_ref import MODEL_REF

    report = NeedsReport()
    seen: dict[tuple[Any, ...], NeededModel] = {}
    for level in tree(graph):
        for wrapper in list(level.node_wrappers.values()):
            node = wrapper.node
            ports = getattr(node, "ports", None)
            if not ports:
                continue
            marked = False
            for port_id, port in list(ports.items()):
                if not (port.is_inlet() or port.is_config()):
                    continue
                if not (isinstance(port.type_cls, type) and issubclass(port.type_cls, MODEL_REF)):
                    continue
                if port.is_linked():
                    continue
                value = port.get_value()
                ref = value if isinstance(value, ModelRef) else ModelRef.from_dict(value or {})
                if ref.is_empty:
                    continue
                try:
                    preference = preference_for(node, port_id)
                except Exception:
                    logger.debug("model_preference of %s failed", wrapper.node_id, exc_info=True)
                    preference = [{}]
                try:
                    resolve_fn(ref, preference)
                except ModelMissing as missing:
                    if not marked:
                        report.nodes.append(wrapper)
                        marked = True
                    if not missing.wanted:
                        continue
                    spec = missing.wanted[0]
                    known = seen.get(spec.identity)
                    if known is not None:
                        if wrapper.node_id not in known.node_ids:
                            known.node_ids.append(wrapper.node_id)
                        continue
                    size = _spec_size(spec)
                    needed = NeededModel(
                        wrapper.node_id, port_id, _spec_label(spec), spec, size, [wrapper.node_id]
                    )
                    seen[spec.identity] = needed
                    report.missing.append(needed)
                    if size is None:
                        report.unknown_size += 1
                    else:
                        report.total_bytes += size
    return report


def _spec_files(spec: FetchSpec) -> list[tuple[str | None, tuple[str, ...]]]:
    """Return ``(sha256, sources)`` of every file of *spec*, to match download jobs."""
    if spec.resource is not None:
        bundle = spec.resource.is_bundle
        return [
            (
                f.sha256 or (None if bundle else spec.resource.sha256),
                f.urls or (() if bundle else spec.resource.urls),
            )
            for f in spec.resource.files
        ]
    if spec.ref is not None:
        return [(spec.ref.sha256, spec.ref.urls)]
    return []


def job_matches(job: DownloadJob, spec: FetchSpec) -> bool:
    """Return whether *job* downloads a file of *spec* (same digest, or same first source)."""
    for sha, sources in _spec_files(spec):
        if sha and job.sha256 == sha:
            return True
        if sources and job.sources[:1] == sources[:1]:
            return True
    return False


class _Models(Protocol):
    @property
    def index(self) -> ModelIndex: ...

    @property
    def queue(self) -> DownloadQueue: ...

    @property
    def catalog(self) -> ModelCatalogRegistry: ...

    @property
    def hf_cache(self) -> Path | None: ...


@dataclass
class _Watched:
    """One open graph under watch."""

    binding_id: str
    root: BaseGraph
    subs: dict[int, tuple[BaseGraph, Callable[[Any], None]]] = field(default_factory=dict)
    warned: dict[str, NodeWrapper] = field(default_factory=dict)
    text: str | None = None
    text_at: float = 0.0
    batch_total: int = 0
    """Most models missing at once since the current fetch began, for the ``i of n`` text."""
    action: Callable[[SessionContext], None] | None = None
    closed: bool = False
    """Set once the graph is no longer watched; no subscription is made afterwards."""
    lock: threading.Lock = field(default_factory=threading.Lock)
    """Serialises ``subs`` changes. Never taken from a validation callback."""


class NeedsWatcher:
    """Keeps the models notice and the card warnings of every open graph current.

    Create with the app's :class:`GraphAppState` and models state, call :meth:`start`,
    and :meth:`stop` on shutdown.
    """

    def __init__(
        self,
        graphs: GraphAppState,
        models: _Models,
        *,
        debounce_s: float = DEBOUNCE_S,
        throttle_s: float = TEXT_THROTTLE_S,
    ) -> None:
        self._graphs = graphs
        self._models = models
        self._debounce_s = debounce_s
        self._throttle_s = throttle_s
        self._lock = threading.Lock()
        self._run_lock = threading.Lock()
        self._watched: dict[int, _Watched] = {}
        self._reports: dict[str, NeedsReport] = {}
        self._timers: dict[str, threading.Timer] = {}
        self._deadlines: dict[str, float] = {}
        self._running = 0
        self._started = False

    # -- lifecycle ---------------------------------------------------------------

    def start(self) -> None:
        """Subscribe to graphs, index, queue and catalog; watch the graphs already open."""
        if self._started:
            return
        self._started = True
        self._graphs.add_graphs_listener(self._sync)
        self._models.index.add_listener(self._kick_all)
        self._models.queue.add_listener(self._kick_all)
        try:
            self._models.catalog.add_batch_event_subscriber(self._on_catalog)
        except Exception:
            logger.debug("catalog subscription unavailable", exc_info=True)
        self._sync()

    def stop(self) -> None:
        """Unsubscribe everything, cancel pending re-walks, retract our notices and warnings."""
        if not self._started:
            return
        self._started = False
        self._graphs.remove_graphs_listener(self._sync)
        self._models.index.remove_listener(self._kick_all)
        self._models.queue.remove_listener(self._kick_all)
        try:
            self._models.catalog.remove_batch_event_subscriber(self._on_catalog)
        except Exception:
            logger.debug("catalog unsubscription failed", exc_info=True)
        with self._lock:
            watched = list(self._watched.values())
            for w in watched:
                w.closed = True
            self._watched.clear()
            self._reports.clear()
            timers = list(self._timers.values())
            self._timers.clear()
            self._deadlines.clear()
        for timer in timers:
            timer.cancel()
        for w in watched:
            self._unsubscribe_all(w)
        # Taking the run lock waits out a walk in flight, so nothing posts after we return.
        with self._run_lock:
            for w in watched:
                self._graphs.retract_notice(w.binding_id, NEEDS_NOTICE)
                for wrapper in w.warned.values():
                    self._clear_own_warning(wrapper)
                w.warned = {}

    @staticmethod
    def _clear_own_warning(wrapper: NodeWrapper) -> None:
        """Drop our warning; the consumer's other "model" warnings stay."""
        if [x for x in wrapper.state.warnings if x.kind == KIND] == [MISSING_WARNING]:
            wrapper.replace_warnings(KIND, [])

    def latest_reports(self) -> dict[str, NeedsReport]:
        """Return the latest report of every open graph that misses models, keyed by binding id."""
        with self._lock:
            return dict(self._reports)

    def wait_idle(self, timeout: float = 5.0) -> bool:
        """Block until no re-walk is pending or running; ``False`` on timeout. For tests."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._lock:
                idle = not self._timers and not self._running
            if idle:
                return True
            time.sleep(0.01)
        return False

    # -- graph registry ----------------------------------------------------------

    def _sync(self) -> None:
        """Reconcile the watched graphs with the open containers."""
        current: dict[int, tuple[str, BaseGraph]] = {}
        for container in self._graphs.all_containers():
            graph = container.editor.graph
            if graph is not None:
                current[id(graph)] = (container.binding_id, graph)
        added: list[_Watched] = []
        removed: list[_Watched] = []
        with self._lock:
            for key in [k for k in self._watched if k not in current]:
                gone = self._watched.pop(key)
                gone.closed = True
                self._reports.pop(gone.binding_id, None)
                removed.append(gone)
            for key, (binding_id, graph) in current.items():
                w = self._watched.get(key)
                if w is None:
                    w = self._watched[key] = _Watched(binding_id, graph)
                    added.append(w)
                elif w.binding_id != binding_id:
                    self._reports.pop(w.binding_id, None)
                    w.binding_id = binding_id
                    w.text = None
                    added.append(w)
        for w in removed:
            self._unsubscribe_all(w)
            self._cancel(w.binding_id)
        for w in added:
            self._reconcile(w)
            self._schedule(w.binding_id)

    def _reconcile(self, w: _Watched) -> None:
        """Subscribe validation on every graph of the tree, unsubscribe the ones that left it."""
        levels = {id(g): g for g in tree(w.root)}
        with w.lock:
            if w.closed:
                return
            for key in [k for k in w.subs if k not in levels]:
                graph, cb = w.subs.pop(key)
                graph.unsubscribe_from_validation(cb)
            for key, graph in levels.items():
                if key not in w.subs:
                    cb = self._validation_callback(w)
                    w.subs[key] = (graph, cb)
                    graph.subscribe_to_validation(cb)

    def _validation_callback(self, w: _Watched) -> Callable[[Any], None]:
        def on_validated(result: Any) -> None:
            self._schedule(w.binding_id)

        return on_validated

    def _unsubscribe_all(self, w: _Watched) -> None:
        with w.lock:
            for graph, cb in list(w.subs.values()):
                graph.unsubscribe_from_validation(cb)
            w.subs.clear()

    # -- scheduling ----------------------------------------------------------------

    def _kick_all(self) -> None:
        """Index, queue or catalog changed: re-walk every graph. Runs under foreign locks."""
        with self._lock:
            bindings = [w.binding_id for w in self._watched.values()]
        for binding_id in bindings:
            self._schedule(binding_id)

    def _on_catalog(self, events: Any) -> None:
        self._kick_all()

    def _schedule(self, binding_id: str, delay: float | None = None) -> None:
        """Arm the debounce timer of *binding_id*. Only schedules; never walks.

        A pending timer that fires no later than the new one stays, so a steady stream of
        calls cannot postpone the walk forever.
        """
        with self._lock:
            if not self._started:
                return
            deadline = time.monotonic() + (self._debounce_s if delay is None else delay)
            pending = self._deadlines.get(binding_id)
            if pending is not None and pending <= deadline and binding_id in self._timers:
                return
            previous = self._timers.pop(binding_id, None)
            timer = threading.Timer(max(0.0, deadline - time.monotonic()), self._fire, [binding_id])
            timer.daemon = True
            self._timers[binding_id] = timer
            self._deadlines[binding_id] = deadline
            timer.start()
        if previous is not None:
            previous.cancel()

    def _cancel(self, binding_id: str) -> None:
        with self._lock:
            timer = self._timers.pop(binding_id, None)
            self._deadlines.pop(binding_id, None)
        if timer is not None:
            timer.cancel()

    def _fire(self, binding_id: str) -> None:
        with self._lock:
            timer = self._timers.get(binding_id)
            if timer is None or timer is not threading.current_thread():
                return  # superseded by a newer timer
            del self._timers[binding_id]
            self._deadlines.pop(binding_id, None)
            self._running += 1
        try:
            self._run(binding_id)
        except Exception:
            logger.exception("needs re-walk of %s failed", binding_id)
        finally:
            with self._lock:
                self._running -= 1

    # -- the re-walk -------------------------------------------------------------

    def _resolve(self, ref: ModelRef, preference: Preference) -> ResolvedModel:
        m = self._models
        return resolve(ref, preference, catalog=m.catalog, index=m.index, hf_cache=m.hf_cache)

    def _run(self, binding_id: str) -> None:
        with self._run_lock:
            with self._lock:
                w = next((x for x in self._watched.values() if x.binding_id == binding_id), None)
            if w is None:
                return
            self._reconcile(w)
            report = collect_needs(w.root, self._resolve)
            with self._lock:
                if report.missing and w in self._watched.values():
                    self._reports[binding_id] = report
                else:
                    self._reports.pop(binding_id, None)
            self._update_warnings(w, report)
            self._update_notice(w, report)

    def _update_warnings(self, w: _Watched, report: NeedsReport) -> None:
        now = {wrapper.node_id: wrapper for wrapper in report.nodes}
        for node_id, wrapper in list(w.warned.items()):
            if node_id not in now:
                self._clear_own_warning(wrapper)
        for wrapper in now.values():
            wrapper.replace_warnings(KIND, [MISSING_WARNING])
        w.warned = now

    def _update_notice(self, w: _Watched, report: NeedsReport) -> None:
        binding_id = w.binding_id
        if not report.missing:
            w.text = None
            w.batch_total = 0
            self._graphs.retract_notice(binding_id, NEEDS_NOTICE)
            return
        n = len(report.missing)
        jobs = [j for j in self._models.queue.jobs() if j.state in _ACTIVE]
        active = [j for j in jobs if any(job_matches(j, m.spec) for m in report.missing)]
        fetching = bool(active)
        if fetching:
            w.batch_total = max(w.batch_total, n)
            done = sum(j.done_bytes for j in active)
            total = sum(j.total_bytes or j.size or 0 for j in active)
            pct = min(100, int(100 * done / total)) if total else 0
            index = min(w.batch_total - n + 1, w.batch_total)
            text = f"Fetching {index} of {w.batch_total} — {pct} %"
        else:
            w.batch_total = 0
            noun = "model" if n == 1 else "models"
            size = format_size(report.total_bytes)
            if report.unknown_size:
                size += f", {report.unknown_size} of unknown size"
            text = f"Needs {n} {noun} ({size})"
        now = time.monotonic()
        if fetching and w.text is not None and text != w.text and now - w.text_at < self._throttle_s:
            self._schedule(binding_id, self._throttle_s - (now - w.text_at))
            return
        if text != w.text:
            w.text, w.text_at = text, now
        if w.action is None:
            w.action = self._action_for(w)
        self._graphs.post_notice(
            binding_id,
            GraphNotice(
                NEEDS_NOTICE,
                text,
                action_label="Show in Models",
                action=w.action,
                requires=AccessTier.VIEW,
                icon=hui.icon.models,
            ),
        )

    @staticmethod
    def _action_for(w: _Watched) -> Callable[[SessionContext], None]:
        """One stable callable per graph, so an unchanged notice re-posts as equal."""

        def show_in_models(context: SessionContext) -> None:
            context.data[ModelsViewState].graph_filter = w.binding_id
            try:
                from haybale_models.editors.models_editor import ModelsEditor
            except ImportError:
                logger.debug("ModelsEditor is not available yet")
                return
            from haywire.core.signals import Reveal

            context.session.publish(Reveal(editor=ModelsEditor))

        return show_in_models
