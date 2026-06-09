"""Shared scaffolding for the BaseWidget sync-path tests.

Provides a minimal DataPort, a NiceGUI-element stand-in (and a handler-recording
variant), and two BaseWidget shapes (default bind / explicit converter) driven
directly so tests/benchmarks measure the sync path with nothing else in the loop.
"""

from __future__ import annotations

# editor import first to avoid circular import (see CLAUDE.md / test conventions)
import haywire.core.graph.editor  # noqa: F401

from typing import Any

from haywire.core.types.port import DataPort
from haywire.core.types.enums import FlowType, PortType
from haywire.ui.widget.base import BaseWidget
from haywire.ui.widget.converters import Converters

from haybale_core.types import FLOAT


def make_float_port(port_id: str = "v") -> DataPort:
    """A bare FLOAT inlet port with a working data field and change event."""
    return DataPort(
        registry_id="float",
        registry_key="haybale_core:type:float",
        label="F",
        id=port_id,
        type_cls=FLOAT,
        port_type=PortType.INLET,
        flow_type=FlowType.DATA,
    )


class _StandInElement:
    """A NiceGUI-element stand-in exposing only the bound property.

    No ``client`` attribute, so the widget's ``hasattr(ui_element, "client")``
    disconnect-hook guard is skipped. ``value`` / ``text`` cover the primitive
    widget surface. ``on``/``off`` accept (and discard) handlers so a TWO_WAY
    binding can activate without a real element.
    """

    def __init__(self) -> None:
        self.value: Any = 0.0
        self.text: Any = ""

    def on(self, _event: str, _handler: Any) -> "_StandInElement":
        return self

    def off(self, _event: str, _handler: Any) -> None:
        pass


class _RecordingElement(_StandInElement):
    """Stand-in that records which (event, handler) pairs were registered,
    so a test can prove whether a view→model handler was wired."""

    def __init__(self) -> None:
        super().__init__()
        self.handlers: dict[str, Any] = {}

    def on(self, event: str, handler: Any) -> "_RecordingElement":
        self.handlers[event] = handler
        return self


# ---------------------------------------------------------------------------
# Two BaseWidget shapes for the sync-path benchmark (new bind() API)
# ---------------------------------------------------------------------------


class _BaseDefaultFloatWidget(BaseWidget):
    """Default bind() — the canonical primitive path."""

    def build(self) -> Any:
        self.el = _StandInElement()
        return self.bind(self.el)


class _BaseConverterFloatWidget(BaseWidget):
    """bind() with an explicit range converter — upper-bound converter cost."""

    def build(self) -> Any:
        self.el = _StandInElement()
        return self.bind(
            self.el,
            converter=Converters.chain(
                Converters.primitive(default_value=0),
                Converters.range(min_value=-1e9, max_value=1e9, clamp=True),
            ),
        )


def _drive(cls: type[BaseWidget]) -> tuple[Any, DataPort, _StandInElement]:
    """Render the widget against a stand-in and return (sync_fn, port, element).

    ``sync_fn()`` performs exactly one model→view sync of the single binding —
    the unit the benchmark/tests time.
    """
    port = make_float_port()
    w = cls(port)
    w.render()
    el = w.el  # type: ignore[attr-defined]
    binding = w._bindings[0]
    return binding.sync_to_view, port, el


def build_base_default() -> tuple[Any, DataPort, _StandInElement]:
    return _drive(_BaseDefaultFloatWidget)


def build_base_converter() -> tuple[Any, DataPort, _StandInElement]:
    return _drive(_BaseConverterFloatWidget)
