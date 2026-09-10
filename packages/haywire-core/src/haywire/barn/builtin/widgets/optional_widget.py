"""OptionalWidget — renders an ``OPTIONAL[T]`` field: the element's own widget,
plus an absence state.

One widget serves EVERY wrapped IType. It never knows what it is wrapping: it
reads the element type off the cell, looks up that type's declared widget key,
and builds it. A library shipping its own IType gets ``OPTIONAL[TheirType]``
rendered correctly without this file changing.
"""

from typing import Any

from nicegui import ui

from haywire.core.types.fields import DataField
from haywire.core.types.interface import IType
from haywire.ui.themes.icons import ICONS
from haywire.ui.widget.base import BaseWidget
from haywire.ui.widget.decorator import widget
from haywire.ui.widget.globals import WIDGET_REGISTRY


class _ElementModel:
    """A ``WidgetModel`` view of an optional cell, seen by the INNER widget.

    Shares the outer cell verbatim (``data`` returns the same ``DataField``), so
    the inner widget's own ``on_changed`` subscription and any binding it
    registers stay live. The only thing it changes is the read: absence is
    presented to the inner widget as the restore value, because a ``NumberDrag``
    or ``ui.select`` has no way to display "nothing". The absence state is
    communicated visually by hiding that widget, never by feeding it ``None``.
    """

    def __init__(self, outer: Any, widget_config: dict, fallback: Any) -> None:
        self.id = f"{outer.id}__value"
        self.widget_config = widget_config
        self._outer = outer
        self._fallback = fallback

    @property
    def data(self) -> DataField:
        return self._outer.data

    def get_value(self) -> Any:
        value = self._outer.get_value()
        return self._fallback if value is None else value

    def set_value(self, value: Any) -> None:
        self._outer.set_value(value)


@widget(description="Optional value — the wrapped type's widget, plus an absence state")
class OptionalWidget(BaseWidget):
    """Renders an ``OPTIONAL[T]`` field in whichever of its two states it is in.

    - **Present**: the element type's own declared widget, unchanged. An
      optional int edits exactly like a plain int.
    - **Absent**: a ``none`` cell, sized and framed like a value widget so the
      row still reads as a field and the column doesn't jump, in muted italics
      so it doesn't read as a value, carrying an always-visible action icon so
      it reads as a *control*. Clicking anywhere in it enters a value and hands
      over to the element widget. The icon is deliberately not hover-revealed:
      a cell that looks inert until hovered is a control nobody finds.

    Absence must LOOK absent. A cleared cell holds ``None``, which
    ``PrimitiveUnwrappingConverter`` renders as ``0`` — a number that actively
    lies about the value — so the element widget is hidden rather than shown
    holding a stand-in.

    **Leaving absence is the widget's job; entering it is the row menu's.**
    Clicking the ``none`` cell is the only way to start entering a value, so it
    lives here. Going the other way is a Reset-shaped act and the Setting-row menu
    already owns those verbs ("Reset to default" and, where they differ, "Set to
    none"), so this widget deliberately offers no clear button of its own —
    a third control doing what a listed menu entry already does is one the user
    has to distinguish for no benefit.

    **The value that clicking the ``none`` cell produces**, in order:

    1. ``widget_config={"restore": ...}`` at the declaration site
    2. the field's own non-absent default, stamped into ``restore`` by
       ``setting._stamp_widget``
    3. the element IType's declared default (``INT`` → ``0``, ``BOOL`` → ``False``)

    Stateless by design: it answers the same way every time rather than
    remembering the last value, which would die on every panel redraw and make
    the same gesture give different answers.
    """

    def build(self) -> Any:
        element_cls = self._element_type()
        inner_cls = self._inner_widget_class(element_cls)
        self._fallback = self._restore_value(element_cls)
        self._inner: Any = None

        root = ui.element("div").classes("w-full min-w-0")
        with root:
            self._none_cell = ui.element("div").classes("hw-optional-none").on("click", self._on_restore)
            with self._none_cell:
                ui.label("none").classes("hw-optional-none__text")
                # A visible control, not just a cursor change: the row has to
                # announce that clicking it does something. The icon carries
                # that, and brightens with the frame on hover.
                ui.icon(ICONS.ADD_CIRCLE).classes("hw-optional-none__action")
            self._none_cell.tooltip("Not set — click to enter a value")

            self._value_cell = ui.element("div").classes("w-full min-w-0")
            with self._value_cell:
                if inner_cls is None:
                    # No widget registered for the element type — show the value
                    # rather than a blank cell, matching the panel's own fallback.
                    self._inner_label: Any = ui.label("").classes("text-xs truncate")
                else:
                    self._inner_label = None
                    inner_model = _ElementModel(self.port, self._config, self._fallback)
                    self._inner = inner_cls(inner_model)
                    self._inner.render()
        return root

    # ---- state -----------------------------------------------------------

    def on_model_changed(self, value: Any) -> None:
        super().on_model_changed(value)
        absent = value is None
        self._none_cell.set_visibility(absent)
        self._value_cell.set_visibility(not absent)
        if self._inner_label is not None and not absent:
            self._inner_label.set_text(str(value))

    def _on_restore(self) -> None:
        self.set_value(self._fallback)

    def _on_cleanup(self) -> None:
        if self._inner is not None:
            self._inner.cleanup()
            self._inner = None

    # ---- element resolution ---------------------------------------------

    def _element_type(self) -> "type[IType] | None":
        """The wrapped IType, read off the cell rather than declared here."""
        stored = self.port.data.get_stored_type()
        element = getattr(stored, "element_type_cls", None)
        if isinstance(element, type) and issubclass(element, IType):
            return element
        return None

    def _inner_widget_class(self, element_cls: "type[IType] | None") -> Any:
        """The element type's OWN declared widget class, or ``None``.

        Looked up by the element identity's ``widget_key`` — the same stamped
        contract every other surface reads (ADR 0017). Nothing here resolves a
        widget by inspecting the value.
        """
        if element_cls is None:
            return None
        identity = getattr(element_cls, "class_identity", None)
        key = getattr(identity, "widget_key", None)
        if not key:
            return None
        return WIDGET_REGISTRY.get(key)

    def _restore_value(self, element_cls: "type[IType] | None") -> Any:
        props = self._config.get("properties", {})
        if "restore" in props:
            return props["restore"]
        identity = getattr(element_cls, "class_identity", None)
        default = getattr(identity, "default", None)
        if isinstance(default, dict):
            return default.get("value")
        return None
