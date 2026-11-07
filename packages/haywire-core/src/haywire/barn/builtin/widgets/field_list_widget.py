"""An editor for a FIELD_LIST: one row per field, and a row that adds one."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from nicegui import ui

from haywire.barn.builtin.field_text import can_be_saved
from haywire.barn.builtin.types import FIELD_LIST, FLOAT, is_valid_key
from haywire.core.di.context import get_type_registry
from haywire.ui import elements as hui
from haywire.ui.hover_tip import TIP_ATTR, TIP_DESC_ATTR, TIP_TYPE_ATTR
from haywire.ui.widget.base import BaseWidget
from haywire.ui.widget.decorator import widget


_CORE_PREFIX = "haywire-core:"

_OPTION_WITH_TIP = f"""
<q-item v-bind="props.itemProps"
        :{TIP_ATTR}="props.opt.label"
        :{TIP_TYPE_ATTR}="props.opt.class_name"
        :{TIP_DESC_ATTR}="props.opt.tip_text">
  <q-item-section><q-item-label>{{{{ props.opt.label }}}}</q-item-label></q-item-section>
</q-item>
"""


@dataclass(frozen=True)
class TypeChoice:
    """One entry of the type picker.

    Attributes:
        label: What the picker shows, unique among the choices.
        class_name: The type's class name.
        library: The id of the library the type comes from.
        description: What the type holds, empty if it does not say.
        saved_in_files: Whether Save Image can write a field of this type to a file.
    """

    label: str
    class_name: str
    library: str
    description: str
    saved_in_files: bool

    @property
    def tip_text(self) -> str:
        """Return the hover tip's lines below the title: description, library, whether it can be saved."""
        saving = "Can be saved in image files" if self.saved_in_files else "Not saved in files"
        lines = [self.description, f"Library: {self.library}", saving]
        return "\n".join(line for line in lines if line)


def type_choices(registry: Any) -> dict[str, TypeChoice]:
    """Return the types a field can have, by registry key, sorted by label.

    A label several libraries share gets the library's name after it, except on the
    framework's own type.

    Args:
        registry: A ``TypeRegistry``.
    """
    identities = {key: registry.get_identity(key) for key in registry.list_value_type_keys()}
    counts = Counter(identity.label for identity in identities.values())
    choices = {}
    for key, identity in identities.items():
        label = identity.label
        library = key.split(":", 1)[0]
        if counts[label] > 1 and not key.startswith(_CORE_PREFIX):
            label = f"{label} ({library})"
        class_name = registry.get_type_class(key).__name__
        choices[key] = TypeChoice(
            label, class_name, library, identity.description or "", can_be_saved(identity)
        )
    return dict(sorted(choices.items(), key=lambda item: item[1].label.lower()))


def _type_label(registry_key: str | None) -> str:
    """Return what the picker calls a type, or the key itself for one not installed."""
    registry = get_type_registry()
    choice = type_choices(registry).get(registry_key or "")
    if choice is not None:
        return choice.label
    identity = registry.get_identity(registry_key) if registry_key else None
    return identity.label if identity is not None else str(registry_key)


class _TypeSelect(ui.select):
    """A select of ``TypeChoice`` entries whose options carry their hover tips for the option slot."""

    def __init__(self, choices: dict[str, TypeChoice], value: str) -> None:
        self._choices = list(choices.values())
        super().__init__(options={key: choice.label for key, choice in choices.items()}, value=value)

    def _update_options(self) -> None:
        super()._update_options()
        # NiceGUI rebuilds the options from index and label on every update.
        for option, choice in zip(self._props["options"], self._choices, strict=True):
            option["class_name"] = choice.class_name
            option["tip_text"] = choice.tip_text


@widget(description="List of fields, each a key and a type")
class FieldListWidget(BaseWidget):
    """Edits a list of fields, each a key and a type.

    Each field has a row with its key, its type and a remove button. Below them,
    type a key and pick a type to add one; hover a type to see its class, what it
    holds and its library. A key
    holds letters, digits and `_`, and appears once; the Add button stays disabled
    otherwise. To rename a field, remove it and add it again.
    """

    def build(self) -> Any:
        with ui.column().classes("w-full gap-1") as root:
            self._rows = ui.column().classes("w-full gap-0")
            with ui.row().classes("w-full items-center gap-1 flex-nowrap"):
                self._key = (
                    ui.input(
                        placeholder="key", validation=self._key_problem, on_change=lambda: self._sync_add()
                    )
                    .classes("flex-1 min-w-0 text-xs")
                    .props("dense outlined hide-bottom-space data-field-key")
                )
                self._type = (
                    _TypeSelect(type_choices(get_type_registry()), FLOAT.class_identity.registry_key)
                    .classes("flex-1 min-w-0 text-xs")
                    .props("dense outlined hide-bottom-space options-dense data-field-type")
                )
                self._type.add_slot("option", _OPTION_WITH_TIP)
                self._add = hui.icon_action(hui.icon.add, tooltip="Add field", on_click=self._on_add)
                self._add.props("data-field-add")
        self._render_rows()
        self._sync_add()
        return root

    def _list(self) -> FIELD_LIST:
        """Return the current value, always a FIELD_LIST."""
        value = self.get_value()
        return value if isinstance(value, FIELD_LIST) else FIELD_LIST()

    def _key_problem(self, key: str | None) -> str | None:
        """Return why ``key`` cannot be added, or ``None``; an empty field is not a problem yet."""
        if not key:
            return None
        if not is_valid_key(key):
            return "Letters, digits and _ only"
        return "Already listed" if any(e.key == key for e in self._list().entries) else None

    def _can_add(self) -> bool:
        key = self._key.value or ""
        return is_valid_key(key) and all(e.key != key for e in self._list().entries)

    def _sync_add(self) -> None:
        self._add.set_enabled(self._can_add())

    def _on_add(self) -> None:
        type_cls = get_type_registry().get_type_class(self._type.value)
        if type_cls is None or not self._can_add():
            return
        self.set_value(self._list().with_added(self._key.value, type_cls))
        self._key.set_value("")
        self._render_rows()

    def _on_remove(self, key: str) -> None:
        self.set_value(self._list().without(key))
        self._render_rows()
        self._sync_add()

    def _render_rows(self) -> None:
        self._rows.clear()
        with self._rows:
            for entry in self._list().entries:
                with ui.row().classes("w-full items-center gap-1 flex-nowrap"):
                    ui.label(entry.key).classes("flex-1 min-w-0 truncate text-xs")
                    ui.label(_type_label(entry.recipe.get("registry_key"))).classes(
                        "flex-1 min-w-0 truncate text-xs hw-text-dim"
                    )
                    button = hui.icon_action(
                        hui.icon.delete,
                        tooltip="Remove field",
                        on_click=lambda key=entry.key: self._on_remove(key),
                    )
                    button.props(f'data-field-remove="{entry.key}"')

    def on_model_changed(self, value: Any) -> None:
        """Redraw the rows after an external write, such as undo."""
        self._render_rows()
        self._sync_add()
