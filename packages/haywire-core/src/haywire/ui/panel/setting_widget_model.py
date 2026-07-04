"""SettingWidgetModel — adapts a settings field to the ``WidgetModel`` surface.

Lets the framework's port-bound ``BaseWidget`` subclasses render a *setting*.
The adapter ALWAYS binds the field's shared ``DataField`` cell (ADR 0016): the
bag's instance cell (``bag._cell_for(descriptor)``) or, for a persistent
setting rendered from the registry, the registry-owned cell
(``registry.cell_for(key)``) — so any write into that cell (descriptor set,
registry write-through, edge drive) shows live via ``on_changed``. Writes are
NOT applied raw to the cell: they are forwarded via the panel's ``make_setter``
(descriptor ``__set__`` or registry setter), keeping set-vs-unset bookkeeping
correct.
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
        field: DataField,
    ) -> None:
        self.id = field_id
        self.widget_config = widget_config or {}
        # ALWAYS the shared cell (ADR 0016) — the bag's instance cell or the
        # registry-owned cell. Any write into it shows live via on_changed;
        # there is no throwaway-field fallback anymore.
        self._field: DataField = field
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
        # which routes through the descriptor __set__ (marks _set_keys) or the
        # registry setter (persistent fields). The write lands in the SHARED
        # cell (→ on_changed → widget), so we must NOT also write it raw here —
        # that would flip the value while leaving the field "unset", and the
        # next registry sync would clobber the edit.
        self._handler(_Event(value))

    def apply_external(self, value: Any) -> None:
        """Push an external setting change into the field (→ widget via on_changed)."""
        if value != self._field.get_value():
            self._field.set_value(value)
