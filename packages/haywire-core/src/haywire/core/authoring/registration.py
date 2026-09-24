"""Waiting for the registry to answer whether a written file registered."""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from haywire.core.registry.lifecycle_event import LifeCycleEvent, LifeCycleEventType

if TYPE_CHECKING:
    from haywire.core.errors.haywire_exception import HaywireException
    from haywire.core.errors.ledger import ErrorLedger
    from haywire.core.registry.component import ComponentRegistry

RegistrationStatus = Literal["added", "reloaded", "failed", "timeout"]

#: Seconds to wait by default: the watcher's 0.5 s debounce plus the module's import.
DEFAULT_TIMEOUT_S = 10.0


@dataclass
class RegistrationOutcome:
    """The registry's answer for one written file.

    ``registry_key`` is the key the lifecycle event carried, or ``None`` when
    nothing registered. ``errors`` holds the error-ledger entries (or the
    failed reload's error) when ``status`` is ``"failed"``.
    """

    status: RegistrationStatus
    registry_key: str | None = None
    errors: "list[HaywireException]" = field(default_factory=list)


class RegistrationWatch:
    """Subscribe before a write, then await the registry's answer for one file.

    Success is a ``CLASS_ADDED`` or ``CLASS_RELOADED`` event from
    ``module_name``, for ``registry_key`` when one is given; pass
    ``module_name=None`` to match on the key alone (a document such as a
    macro has no module). Failure is a ``CLASS_RELOAD_FAILED`` event for such
    a key, or an error-ledger entry for ``module_name``: a new file whose
    import raises emits no lifecycle event, only the ledger entry. The first
    answer wins.

    Enter the watch on the event loop; the registry and ledger callbacks may
    fire on any thread.

    Example::

        ledger = get_error_ledger()
        with RegistrationWatch(node_registry, ledger, plan.module_name, plan.registry_key) as watch:
            await asyncio.to_thread(write_node, plan, library)
            outcome = await watch.result(timeout_s=10)
        if outcome.status == "failed":
            show(outcome.errors)
    """

    def __init__(
        self,
        registry: "ComponentRegistry",
        ledger: "ErrorLedger",
        module_name: str | None,
        registry_key: str | None = None,
    ) -> None:
        if module_name is None and registry_key is None:
            raise ValueError("RegistrationWatch needs a module_name, a registry_key, or both.")
        self._registry = registry
        self._ledger = ledger
        self._module_name = module_name
        self._registry_key = registry_key
        self._lock = threading.Lock()
        self._answer: RegistrationOutcome | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._future: asyncio.Future[RegistrationOutcome] | None = None
        self._since_seq = 0

    def __enter__(self) -> "RegistrationWatch":
        self._loop = asyncio.get_running_loop()
        self._future = self._loop.create_future()
        self._since_seq = self._ledger.current_seq
        self._registry.add_batch_event_subscriber(self._on_batch)
        self._ledger.add_listener(self._on_ledger)
        return self

    def __exit__(self, *exc: object) -> None:
        self._registry.remove_batch_event_subscriber(self._on_batch)
        self._ledger.remove_listener(self._on_ledger)

    async def result(self, timeout_s: float = DEFAULT_TIMEOUT_S) -> RegistrationOutcome:
        """The first answer, or a ``"timeout"`` outcome after ``timeout_s``."""
        assert self._future is not None, "enter the watch before awaiting its result"
        try:
            return await asyncio.wait_for(asyncio.shield(self._future), timeout_s)
        except asyncio.TimeoutError:
            return RegistrationOutcome(status="timeout")

    def _matches(self, event: LifeCycleEvent) -> bool:
        if self._module_name is not None and event.module_name != self._module_name:
            return False
        return self._registry_key is None or event.registry_key == self._registry_key

    def _on_batch(self, batch: list[LifeCycleEvent]) -> None:
        for event in batch:
            if not self._matches(event):
                continue
            if event.event_type == LifeCycleEventType.CLASS_ADDED:
                self._settle(RegistrationOutcome(status="added", registry_key=event.registry_key))
            elif event.event_type == LifeCycleEventType.CLASS_RELOADED:
                self._settle(RegistrationOutcome(status="reloaded", registry_key=event.registry_key))
            elif event.event_type == LifeCycleEventType.CLASS_RELOAD_FAILED:
                errors = [event.error] if event.error is not None else []
                self._settle(RegistrationOutcome(status="failed", errors=errors))

    def _on_ledger(self) -> None:
        if self._module_name is None:
            return
        page = self._ledger.query(since_seq=self._since_seq, limit=50)
        errors = [e for e in page.entries if e.module_name == self._module_name]
        if errors:
            self._settle(RegistrationOutcome(status="failed", errors=errors))

    def _settle(self, outcome: RegistrationOutcome) -> None:
        with self._lock:
            if self._answer is not None:
                return
            self._answer = outcome
        loop, future = self._loop, self._future
        if loop is None or future is None or loop.is_closed():
            return

        def _resolve() -> None:
            if not future.done():
                future.set_result(outcome)

        loop.call_soon_threadsafe(_resolve)
