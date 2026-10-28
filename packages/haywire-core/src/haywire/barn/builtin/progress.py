"""Progress bars on a node card, reported from the node's own code.

A node attaches a ``ProgressSettings`` subclass holding one ``progress_field()``
per bar, then reports from its worker with
``track()`` (loops) or ``busy()`` (everything else). Each bar's value is a
``PROGRESS``; the card renders it with ``ProgressWidget``.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Iterable, Iterator
from types import TracebackType
from typing import Any, TypeVar

from haywire.barn.builtin.types.progress import PROGRESS
from haywire.core.settings import NodeSettings, Promotable, setting, settings_fields
from haywire.core.types.enums import PortType

#: Shortest interval between two writes from ``ProgressSpan.step``, in seconds.
STEP_INTERVAL_S = 0.05

_RESERVED = ("busy", "track")

_ItemT = TypeVar("_ItemT")


def progress_field(label: str = "Progress", **kwargs: Any) -> "setting[PROGRESS]":
    """Return a progress bar field for a ``ProgressSettings`` subclass.

    The bar is a row on the node card by default; the user can hide it with
    Demote, and it never becomes a pin. Further keyword arguments go to
    ``setting()`` (``description``, ``order``, ...).

    Example::

        class progress(ProgressSettings):
            main = progress_field("Progress")
            sub = progress_field("Step", order=1)
    """
    return setting[PROGRESS](
        PROGRESS,
        label=label,
        promotable=Promotable.CONFIG,
        promote_default=PortType.CONFIG,
        **kwargs,
    )


class ProgressSettings(NodeSettings):
    """Progress bars on a node card, driven from the node's worker.

    Subclass it with one ``progress_field()`` per bar and attach the subclass to
    a node with ``bag()``, which types the attribute as the bound settings
    inside an annotated worker. Report a loop with ``track()`` and any other work with ``busy()``:
    while a block or loop runs its bar shows it, and when it ends, also by an
    exception or a ``break``, the bar returns to idle.

    Blocks on different bars nest, so an overall bar can enclose a per-step
    bar. Blocks on the same bar do not: when either ends, that bar is idle.
    Both methods work from any thread the node owns, not only from the worker.

    Raises:
        TypeError: A subclass declares a field named ``busy`` or ``track``.

    Example::

        from haywire.barn.builtin.progress import ProgressSettings, progress_field
        from haywire.core.settings import bag

        class DetectorProgress(ProgressSettings):
            main = progress_field("Progress")
            sub = progress_field("Step")

        @node(...)
        class Detector(DataNode):
            progress = bag(DetectorProgress)

            def worker(self, context: ExecutionContext, files: list) -> str | None:
                # A loop: the bar fills as the items pass.
                for f in self.progress.track("main", files, "processing"):
                    # A nested loop on the second bar.
                    for chunk in self.progress.track("sub", load(f), f"loading {f}"):
                        decode(chunk)

                # One blocking call: the bar sweeps until it returns.
                with self.progress.busy("main", "inferring"):
                    boxes = self._model(frame)

                # Progress that is not a loop, such as a download callback.
                with self.progress.busy("main", "download") as span:
                    fetch(url, on_progress=span.step)
    """

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        for name in _RESERVED:
            if isinstance(vars(cls).get(name), setting):
                raise TypeError(
                    f"{cls.__qualname__}: a field may not be named {name!r}; ProgressSettings uses it"
                )

    def busy(self, field: str, label: str = "") -> "ProgressSpan":
        """Return a block that shows bar *field* as busy with *label* until the block ends.

        The bar sweeps until ``ProgressSpan.step`` gives it a fraction.

        Raises:
            ValueError: *field* is not a progress field of these settings.
        """
        descriptor = settings_fields(self).get(field)
        if descriptor is None or descriptor._type is not PROGRESS:
            raise ValueError(f"{type(self).__qualname__} has no progress field {field!r}")
        return ProgressSpan(self, field, label)

    def track(
        self,
        field: str,
        items: Iterable[_ItemT],
        label: str = "",
        total: int | None = None,
    ) -> Iterator[_ItemT]:
        """Yield *items* unchanged while bar *field* fills with the share already passed.

        Args:
            total: Number of items, for an iterable without ``len()``. Without
                either, the bar sweeps.

        Raises:
            ValueError: *field* is not a progress field of these settings.
        """
        span = self.busy(field, label)
        if total is None and hasattr(items, "__len__"):
            total = len(items)  # type: ignore[arg-type]
        return _tracked(span, items, total)


def _tracked(span: "ProgressSpan", items: Iterable[_ItemT], total: int | None) -> Iterator[_ItemT]:
    with span:
        for index, item in enumerate(items):
            if total:
                span.step(index / total)
            yield item


class ProgressSpan:
    """One ``ProgressSettings.busy()`` block on one bar; ``step()`` reports how far it is."""

    def __init__(self, settings: ProgressSettings, field: str, label: str) -> None:
        self._settings = settings
        self._field = field
        self._label = label
        self._last_write = 0.0
        self._lock = threading.Lock()

    def __enter__(self) -> "ProgressSpan":
        self._write(None)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._settings._reset(self._field)

    def step(self, fraction: float | None, label: str | None = None) -> None:
        """Report *fraction* of the work done, from 0 to 1, and optionally a new *label*.

        ``None`` returns the bar to sweeping. Calls closer together than
        ``STEP_INTERVAL_S`` are dropped unless they change the label, so a tight
        loop may call this on every iteration.
        """
        with self._lock:
            now = time.monotonic()
            relabel = label is not None and label != self._label
            if not relabel and now - self._last_write < STEP_INTERVAL_S:
                return
            if label is not None:
                self._label = label
            self._last_write = now
        self._write(fraction)

    def _write(self, fraction: float | None) -> None:
        setattr(self._settings, self._field, PROGRESS(active=True, fraction=fraction, label=self._label))
