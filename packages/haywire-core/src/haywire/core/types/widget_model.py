"""WidgetModel — the structural contract a widget binds to.

A ``DataPort`` satisfies it natively; the properties panel supplies a
``SettingWidgetModel`` adapter so the same widgets render settings. Defined here
(alongside ``DataField``/``DataPort``) so both the widget base and the binding
layer can reference it without an import cycle.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from .fields import DataField


@runtime_checkable
class WidgetModel(Protocol):
    """Minimal model surface a ``BaseWidget``/``PropertyBinding`` requires."""

    id: str
    widget_config: dict[str, Any]

    @property
    def data(self) -> DataField: ...

    def get_value(self) -> Any: ...

    def set_value(self, value: Any) -> None: ...
