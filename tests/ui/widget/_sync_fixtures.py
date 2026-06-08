"""Shared scaffolding for the BaseWidget-vs-SimpleWidget sync-path study.

Resolves review finding #3 (see
``docs/plans/widget-unification-perf-verification.md``): is BaseWidget's
``_sync_to_view`` path cheap enough to make BaseWidget the single canonical
widget base, and does ``create_default_binding()`` close the gap to
SimpleWidget's bare ``setattr``?

Both the parity test (Test 3) and the microbenchmark (Test 1) build the same
three widget shapes against the same minimal DataPort, so they measure / assert
the *exact* code under question with nothing else in the loop.

Construction notes
------------------
* ``DataPort`` is built directly (not via ``from_spec``) because the sync path
  only needs ``get_value()`` / ``set_value()`` / ``_data.on_changed`` — the full
  spec/registry/wrapper machinery would add noise and isn't on the path. The
  minimal identity kwargs below are the ones ``DataTypeIdentity`` requires; the
  type does the rest in ``__post_init__`` (creates ``_data`` via
  ``FLOAT.create_field``).
* The widgets bind against a ``_StandInElement`` rather than a real NiceGUI
  element. This isolates the binding + converter cost from Vue/Quasar setattr
  reactivity, which is identical for both paths and would only add variance. We
  drive ``_sync_to_view`` / binding activation directly and never call
  ``render()`` (which would reach for ``ui_element.client`` for the disconnect
  hook — irrelevant to what we measure).
"""

from __future__ import annotations

# editor import first to avoid circular import (see CLAUDE.md / test conventions)
import haywire.core.graph.editor  # noqa: F401

from typing import Any

from haywire.core.types.port import DataPort
from haywire.core.types.enums import FlowType, PortType
from haywire.ui.widget.base import BaseWidget
from haywire.ui.widget.binding import PropertyBinding
from haywire.ui.widget.converters import Converters
from haywire.ui.widget.simple import SimpleWidget

from haybale_core.types import FLOAT


# ---------------------------------------------------------------------------
# Minimal port + stand-in element
# ---------------------------------------------------------------------------


def make_float_port(port_id: str = "v") -> DataPort:
    """A bare FLOAT inlet port with a working data field and change event.

    Enough for ``get_value`` / ``set_value`` / ``_data.on_changed``; nothing more
    is on the sync path.
    """
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

    No ``client`` attribute, so the widgets' ``hasattr(ui_element, "client")``
    disconnect-hook guard is simply skipped. ``value`` / ``text`` cover the
    primitive widget surface.
    """

    def __init__(self) -> None:
        self.value: Any = 0.0
        self.text: Any = ""

    # PropertyBinding's view->model immediate handler reads ``e.sender`` and
    # calls ``.on(event, handler)`` during activate(); provide no-op hooks so a
    # TWO_WAY binding can activate without a real element.
    def on(self, _event: str, _handler: Any) -> "_StandInElement":
        return self

    def off(self, _event: str, _handler: Any) -> None:
        pass


# ---------------------------------------------------------------------------
# Three widget shapes under study
# ---------------------------------------------------------------------------
#
# These are NOT decorated with @widget — they're driven directly in-process, so
# they don't need registry identity. We attach a stand-in element and invoke the
# sync logic by hand. (Decorating would require a library identity and pull in
# registration; unnecessary for measuring the sync path.)


class SimpleFloatWidget(SimpleWidget):
    """Baseline: SimpleWidget's direct get_value -> setattr path."""

    def create_element(self) -> Any:  # pragma: no cover - not used in study
        return _StandInElement()

    def get_default_value(self) -> float:
        return 0.0


class BaseDefaultFloatWidget(BaseWidget):
    """The SimpleWidget-equivalent BaseWidget: one create_default_binding().

    This is the shape that decides GREEN vs YELLOW — if its _sync_to_view is
    within budget, BaseWidget can absorb SimpleWidget's role for free.
    """

    def create_element(self) -> Any:  # pragma: no cover - not used in study
        return _StandInElement()

    def configure_bindings(self) -> None:
        self.add_binding(self.create_default_binding())


class BaseConverterFloatWidget(BaseWidget):
    """Upper-bound context: BaseWidget with an explicit range converter.

    Not the canonical-path candidate; included so the study can report how much a
    *real* converter costs relative to the default path.
    """

    def create_element(self) -> Any:  # pragma: no cover - not used in study
        return _StandInElement()

    def configure_bindings(self) -> None:
        self.add_binding(
            self.create_default_binding(
                converter=Converters.chain(
                    Converters.primitive(default_value=0),
                    Converters.range(min_value=-1e9, max_value=1e9, clamp=True),
                )
            )
        )


# ---------------------------------------------------------------------------
# Drivers — return a (sync_callable, port, element) triple
# ---------------------------------------------------------------------------
#
# Each builder wires the widget to a stand-in element and returns a zero-arg
# ``sync()`` that performs exactly one model->view synchronization, plus the
# port (to push new model values) and element (to read the synced result).


def build_simple() -> tuple[Any, DataPort, _StandInElement]:
    port = make_float_port()
    w = SimpleFloatWidget(port)
    el = _StandInElement()
    w.ui_element = el
    # SimpleWidget syncs via its private method; that's the measured unit.
    return w._sync_to_view, port, el


def build_base_default() -> tuple[Any, DataPort, _StandInElement]:
    return _build_base(BaseDefaultFloatWidget)


def build_base_converter() -> tuple[Any, DataPort, _StandInElement]:
    return _build_base(BaseConverterFloatWidget)


def _build_base(cls: type[BaseWidget]) -> tuple[Any, DataPort, _StandInElement]:
    port = make_float_port()
    w = cls(port)
    el = _StandInElement()
    w.ui_element = el
    w.configure_bindings()

    # Activate the main binding against the stand-in (mirrors what render() ->
    # _activate_all_bindings does, minus the NiceGUI element). The model->view
    # sync we want to time is one binding's _sync_to_view.
    binding = _main_binding(w)
    binding.activate(port, el)
    return binding._sync_to_view, port, el


def _main_binding(w: BaseWidget) -> PropertyBinding:
    """The single ``__main__`` binding configured by these study widgets."""
    bindings = w._bindings.get("__main__", [])
    assert len(bindings) == 1, f"study widget must have exactly one main binding, got {len(bindings)}"
    return bindings[0]
