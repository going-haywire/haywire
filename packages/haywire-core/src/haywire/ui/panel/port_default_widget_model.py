"""PortDefaultWidgetModel — adapts a port's *default* to the ``WidgetModel`` surface.

Lets the framework's port-bound ``BaseWidget`` subclasses edit the value a port
starts at, rather than the value it currently holds. The two are different
cells: ``DataPort.default`` is part of the port's spec and serializes with it,
while the live value moves independently once anything writes it.

The adapter binds a **throwaway** ``DataField`` seeded from the default, so
typing in the widget never touches the port. Each edit is forwarded verbatim to
an injected ``on_edit`` callback, which is what decides where the value goes —
a dialog stages it and commits every field it collected through one
``Editor.set_port_metadata`` call, so an Apply is one undo step.

Sibling of :class:`~haywire.ui.panel.setting_widget_model.SettingWidgetModel`,
which does the same for a settings field. Like it, this model carries no write
policy of its own.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from haywire.core.types import DataPort
    from haywire.core.types.fields import DataField


class PortDefaultWidgetModel:
    """A ``WidgetModel`` backed by a scratch copy of a port's default.

    Satisfies the ``WidgetModel`` protocol (``id``, ``widget_config``, ``data``,
    ``get_value``, ``set_value``) so a ``BaseWidget`` binds to it exactly as it
    would to a ``DataPort`` — and therefore renders whatever widget the port
    declares, with the port's own bounds.

    Example::

        model = PortDefaultWidgetModel(port, on_edit=staged.__setitem__)
        widget_factory.render_widget(port.widget_key, model, node_id="dialog")
    """

    def __init__(self, port: "DataPort", on_edit: Callable[[Any], None]) -> None:
        """
        Args:
            port: The port whose default is being edited. Read for its id, its
                widget config and its type; never written.
            on_edit: Called with each raw value the widget produces. The model
                applies no policy of its own — where the value lands is the
                caller's decision.
        """
        assert port.type_cls is not None  # DataPort.__post_init__ enforces this
        self.id = port.id
        self.widget_config = dict(port.widget_config or {})
        # A field of the port's own type, seeded from the default: the widget
        # reads and writes here, so an abandoned dialog leaves the port alone.
        self._cell: "DataField" = port.type_cls.create_field(default_override=port.default)
        self._on_edit = on_edit

    @property
    def data(self) -> "DataField":
        return self._cell

    def get_value(self) -> Any:
        return self._cell.get_value()

    def set_value(self, value: Any) -> None:
        """Write the scratch cell so the widget reflects the edit, then report it.

        Unlike ``SettingWidgetModel``, this model does write its own cell: the
        cell is a scratch copy nothing else observes, and the widget needs it
        to stay in step with what the user typed.
        """
        self._cell.set_value(value)
        self._on_edit(value)

    def as_default(self) -> dict[str, Any]:
        """The staged value in the shape ``DataPort.default`` takes."""
        return self._cell.to_dict()
