"""ArrayWidget — edits an ``ArrayType[T]`` value one row per item.

Each row is the item type's own declared widget, so a library shipping its own
IType gets ``ArrayType[TheirType]`` rows without this file changing. A row
talks to the list through ``_ItemModel``, which reads and writes one index.
"""

from typing import Any
from uuid import uuid4

from nicegui import ui

# Importing the class registers "nicegui-sortable" as an ESM module. A page's
# importmap is written when the page is served, and `make_sortable` imports the
# class only at render time, too late for a page already in the browser.
from nicegui.elements.sortable.sortable import Sortable as _Sortable  # noqa: F401

from haywire.core.types.event import Event
from haywire.core.types.interface import IType
from haywire.ui import elements as hui
from haywire.ui.widget.base import BaseWidget
from haywire.ui.widget.decorator import widget
from haywire.ui.widget.globals import WIDGET_REGISTRY

_GRIP_CLASS = "hw-array-grip"
"""Marks the grip SortableJS accepts a drag from (its ``handle`` selector)."""


class _ItemField:
    """The list cell as one row's widget sees it: a field of the item type.

    Holds only what an item widget reads off ``data``. ``on_changed`` is the
    row's own event, fired by the ``ArrayWidget``, so a row rebuild never
    changes the list cell's handler list while it dispatches.
    """

    def __init__(self, outer: Any, item_cls: "type[IType]") -> None:
        self.type_cls = item_cls
        self.on_changed: Event[Any] = Event[Any]()
        self._outer = outer

    def get_stored_type(self) -> "type[IType]":
        return self.type_cls

    def has_linked_value(self) -> bool:
        return self._outer.has_linked_value()

    def accepts_own_value(self) -> bool:
        return self._outer.accepts_own_value()


class _ItemModel:
    """A ``WidgetModel`` for item *index* of the list behind *outer*.

    A write replaces that item in a new list and hands it to *outer*, so it
    takes the list widget's edit route; a refusal returns ``False``.
    """

    def __init__(
        self, outer: Any, index: int, item_cls: "type[IType]", widget_config: dict, default: Any
    ) -> None:
        self.id = f"{outer.id}__{index}"
        self.widget_config = widget_config
        self.data = _ItemField(outer.data, item_cls)
        self._outer = outer
        self._index = index
        self._item_cls = item_cls
        self._default = default

    def get_value(self) -> Any:
        items = self._outer.get_value() or []
        return items[self._index] if self._index < len(items) else self._default

    def set_value(self, value: Any) -> bool | None:
        items = list(self._outer.get_value() or [])
        if self._index >= len(items):
            return False
        try:
            # An item field coerces as the item type does: an INT row stores an int.
            field = self._item_cls.create_field()
            field.set_value(value)
            items[self._index] = field.get_value()
        except (TypeError, ValueError):
            return False
        return self._outer.set_value(items)


@widget(description="List editor — one row per item, each drawn by the item type's widget")
class ArrayWidget(BaseWidget):
    """Edits a list: one row per item, plus controls to add, remove and reorder items.

    Each row is the item type's own widget: a text field for `ArrayType[STRING]`,
    a number field for `ArrayType[INT]` and `ArrayType[FLOAT]`. Add appends the
    item type's default (`""`, `0`, `0.0`). Drag a row by its grip to move it;
    the cross on its right removes it.

    `ArrayType` does not use this widget by default. Name it on the setting or
    port that should show a list editor:

    ```python
    class Settings(NodeSettings):
        options = setting[ArrayType[STRING]](
            ["One", "Two", "Three"], label="Options", widget=ArrayWidget.config()
        )

    def init(self):
        self.add(
            ArrayType[FLOAT].as_inlet("weights", default={"value": [1.0]}, widget=ArrayWidget.config())
        )
    ```

    Config options (via `ArrayWidget.config(properties={...})`):

    - `item` (dict): widget properties for every row, on top of the item
      type's own. For example, commit-mode text rows that write only on Enter
      or blur:

    ```python
    ArrayWidget.config(properties={"item": {"commit": True}})
    ```

    An item type without a widget shows a read-only item count instead of rows.
    """

    def build(self) -> Any:
        self._item_cls = self._item_type()
        self._inner_cls = self._inner_widget_class(self._item_cls)
        self._rows: list[Any] = []
        self._grips: list[Any] = []
        self._summary: Any = None
        self._add_button: Any = None

        root = ui.column().classes("w-full gap-1").props("data-array")
        with root:
            if self._inner_cls is None:
                self._summary = ui.label("").classes("text-xs")
            else:
                self._rows_box = ui.column().classes("w-full gap-1")
                # A group of its own, so a row can never be dropped into another list.
                self._rows_box.make_sortable(
                    group=f"hw-array:{uuid4().hex}",
                    handle=f".{_GRIP_CLASS}",
                    on_end=lambda e: self._reorder(e.old_index, e.new_index),
                )
                self._add_button = (
                    ui.button(icon=hui.icon.add, on_click=self._add)
                    .props("flat dense size=xs data-array-add")
                    .classes("self-start")
                    .tooltip("Add item")
                )
        self._render_rows()
        return root

    # ---- model -----------------------------------------------------------

    def _items(self) -> list[Any]:
        value = self.get_value()
        return list(value) if isinstance(value, list) else []

    def _item_default(self) -> Any:
        default = getattr(getattr(self._item_cls, "class_identity", None), "default", None)
        return default.get("value") if isinstance(default, dict) else None

    def on_model_changed(self, value: Any) -> None:
        items = value if isinstance(value, list) else []
        if self._summary is not None:
            self._summary.set_text(f"{len(items)} items")
        elif len(items) != len(self._rows):
            self._render_rows()
        else:
            # Same rows, new contents (an edit or a reorder): each row re-reads its index.
            for row in self._rows:
                row.port.data.on_changed(value)

    # ---- edits -----------------------------------------------------------

    def _add(self) -> None:
        self.set_value([*self._items(), self._item_default()])

    def _remove(self, index: int) -> None:
        items = self._items()
        if 0 <= index < len(items):
            items.pop(index)
            self.set_value(items)

    def _reorder(self, old_index: int, new_index: int) -> None:
        """Move the item at *old_index* to *new_index*, as a finished drag dropped it."""
        items = self._items()
        if old_index == new_index or not (0 <= old_index < len(items) and 0 <= new_index < len(items)):
            return
        items.insert(new_index, items.pop(old_index))
        self.set_value(items)
        # The drop already moved the row in the DOM and each row reads a fixed
        # index, so redraw from the model, accepted or refused.
        self._render_rows()

    # ---- rendering -------------------------------------------------------

    def _render_rows(self) -> None:
        """Rebuild the rows for the current items. Called only when the item count changes."""
        item_cls = self._item_cls
        if self._summary is not None or item_cls is None:
            self._summary.set_text(f"{len(self._items())} items")
            return
        for row in self._rows:
            row.cleanup()
        self._rows = []
        self._grips = []
        self._rows_box.clear()

        count = len(self._items())
        identity = getattr(item_cls, "class_identity", None)
        type_props = (getattr(identity, "widget_config", None) or {}).get("properties", {})
        item_props = self._config.get("properties", {}).get("item", {})
        row_config = {"properties": {**type_props, **item_props}}
        default = self._item_default()

        with self._rows_box:
            for index in range(count):
                with (
                    ui.row().classes("w-full items-center gap-1 no-wrap").props(f'data-array-row="{index}"')
                ):
                    # data-interactive keeps the canvas from dragging the node.
                    grip = (
                        ui.icon(hui.icon.drag_handle)
                        .classes(f"{_GRIP_CLASS} text-sm hw-text-dim shrink-0 cursor-grab")
                        .props(f'data-interactive="true" data-array-grip="{index}"')
                    )
                    with ui.element("div").classes("flex-1 min-w-0"):
                        model = _ItemModel(self.port, index, item_cls, row_config, default)
                        row = self._inner_cls(model)
                        row.render()
                    (
                        ui.button(icon=hui.icon.close, on_click=lambda _, i=index: self._remove(i))
                        .props(f'flat dense size=xs data-array-remove="{index}"')
                        .classes("shrink-0")
                        .tooltip("Remove")
                    )
                self._rows.append(row)
                self._grips.append(grip)

    def _on_cleanup(self) -> None:
        for row in self._rows:
            row.cleanup()
        self._rows = []

    # ---- item type -------------------------------------------------------

    def _item_type(self) -> "type[IType] | None":
        """Return the item type of this list field (``STRING`` for ``ArrayType[STRING]``), or ``None``."""
        element = getattr(self.port.data.type_cls, "element_type_cls", None)
        if isinstance(element, type) and issubclass(element, IType):
            return element
        return None

    @staticmethod
    def _inner_widget_class(item_cls: "type[IType] | None") -> Any:
        """Return the item type's declared widget class, or ``None``."""
        key = getattr(getattr(item_cls, "class_identity", None), "widget_key", None)
        return WIDGET_REGISTRY.get(key) if key else None
