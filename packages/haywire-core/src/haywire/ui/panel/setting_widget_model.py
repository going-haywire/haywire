"""SettingWidgetModel — adapts a settings field to the ``WidgetModel`` surface.

Lets the framework's port-bound ``BaseWidget`` subclasses render a *setting*. The
adapter binds to the owning ``Settings`` bag's shared ``DataField`` cell
(``bag._cell_for(descriptor)``) for **display** when one is provided — so a
registry / edge change into that cell shows live via ``on_changed`` — and falls
back to creating its own field for a standalone widget with no bag. Writes are
NOT applied raw to the cell: they are forwarded to the owning ``Settings`` via the
panel's ``make_setter`` (which routes through the descriptor ``__set__``), keeping
``_set_keys`` set-vs-unset bookkeeping correct. External setting changes are pushed
back into the field by the panel's ``apply`` (see ``_resolve_widget_instance``).
"""

from __future__ import annotations

from typing import Any, Callable

from haywire.core.types.fields import DataField
from haywire.core.types.interface import IType


class _Event:
    """Minimal change-event stand-in: setters read only ``.value``."""

    __slots__ = ("value",)

    def __init__(self, value: Any) -> None:
        self.value = value


class SettingWidgetModel:
    """A ``WidgetModel`` backed by a settings field.

    Satisfies the ``WidgetModel`` protocol (``id``, ``widget_config``, ``data``,
    ``get_value``, ``set_value``) so a ``BaseWidget`` binds to it exactly as it
    would to a ``DataPort``.
    """

    def __init__(
        self,
        field_id: str,
        itype: type[IType],
        value: Any,
        widget_config: dict[str, Any],
        make_setter: Callable[[Callable[[Any], Any]], Callable[[Any], None]],
        field: DataField | None = None,
    ) -> None:
        self.id = field_id
        self.widget_config = widget_config or {}
        # Bind to the bag's SHARED cell when provided (one cell, two views — a
        # registry/edge write into it shows live via on_changed). Otherwise create
        # a throwaway field for a standalone widget with no bag.
        self._shared = field is not None
        self._field: DataField = (
            field if field is not None else itype.create_field(default_override={"value": value})
        )
        # The panel's coerce→validate→setattr handler (identity coerce; the
        # widget already delivers a typed value). Writes route through the
        # descriptor __set__ — NOT raw cell.set_value — so _set_keys stays correct.
        self._handler = make_setter(lambda v: v)

    @property
    def data(self) -> DataField:
        return self._field

    def get_value(self) -> Any:
        return self._field.get_value()

    def set_value(self, value: Any) -> None:
        # Widget → model. Forward to the owning Settings via the panel setter,
        # which routes through the descriptor __set__ (marks _set_keys). For a
        # SHARED cell that __set__ writes the cell (→ on_changed → widget), so we
        # must NOT also write it raw here — a raw write would flip the value while
        # leaving the field "unset", and the next registry sync would clobber the
        # edit. For a standalone (own) field there is no bag to route through, so
        # update the field directly to drive sibling bindings.
        if not self._shared:
            self._field.set_value(value)
        self._handler(_Event(value))

    def apply_external(self, value: Any) -> None:
        """Push an external setting change into the field (→ widget via on_changed)."""
        if value != self._field.get_value():
            self._field.set_value(value)
