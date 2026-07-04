"""SettingWidgetModel — adapts a settings field to the ``WidgetModel`` surface.

Lets the framework's port-bound ``BaseWidget`` subclasses render a *setting*.
The adapter ALWAYS binds the field's shared ``DataField`` cell (ADR 0016): the
bag's instance cell (``bag._cell_for(descriptor)``) or, for a persistent
setting rendered from the registry, the registry-owned cell
(``registry.cell_for(key)``) — so any write into that cell (descriptor set,
registry write-through, edge drive) shows live via ``on_changed``. Writes are
NOT applied raw to the cell: the model forwards them verbatim to an injected
``on_edit`` callback, which implements whatever write policy applies
(instance: validate → setattr; registry: set_global → debounced save) — see
``render_utils._bag_on_edit`` / ``_registry_on_edit`` (Task 9). The model
itself carries no policy at all; it is a thin adapter.
"""

from __future__ import annotations

from typing import Any, Callable

from haywire.core.types.fields import DataField


class SettingWidgetModel:
    """A ``WidgetModel`` backed by a settings field.

    Satisfies the ``WidgetModel`` protocol (``id``, ``widget_config``, ``data``,
    ``get_value``, ``set_value``) so a ``BaseWidget`` binds to it exactly as it
    would to a ``DataPort``.
    """

    def __init__(
        self,
        field_id: str,
        widget_config: dict[str, Any],
        cell: DataField,
        on_edit: Callable[[Any], None],
    ) -> None:
        self.id = field_id
        self.widget_config = widget_config or {}
        # ALWAYS the shared cell (ADR 0016) — the bag's instance cell or the
        # registry-owned cell. Any write into it shows live via on_changed;
        # there is no throwaway-field fallback.
        self._cell: DataField = cell
        self._on_edit = on_edit

    @property
    def data(self) -> DataField:
        return self._cell

    def get_value(self) -> Any:
        return self._cell.get_value()

    def set_value(self, value: Any) -> None:
        # Widget → model. Forward the raw value verbatim to the injected
        # on_edit policy (descriptor setattr / registry set_global). The
        # model never writes the cell itself: the write lands in the SHARED
        # cell only if on_edit's policy accepts it (validate passes), and
        # doing it here too would flip the value while leaving the field
        # "unset", and the next registry sync would clobber the edit.
        self._on_edit(value)
