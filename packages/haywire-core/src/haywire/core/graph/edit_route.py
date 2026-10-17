"""The one way a user edit reaches a level's ``Editor``."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, Any

from haywire.core.access import LevelMode
from haywire.core.graph.setting_owner import SettingOwner, setting_owner

if TYPE_CHECKING:
    from haywire.core.graph.base import BaseGraph
    from haywire.core.graph.editor import Editor
    from haywire.core.settings.settings import Settings


class EditRoute:
    """Carry a session's edits at one level to that level's ``Editor``, if its level mode allows.

    Both callables are read at every call, so a route follows its level when the
    level's ``Editor`` is swapped, and refuses a write the moment the mode drops.
    Each write names the lowest level mode its surface needs (``minimum``): card
    and stage widgets pass ``OPERATE``, panels pass ``EDIT``. A write to a port or
    field that is not operable (``operable=False``) needs ``EDIT`` whatever its
    ``minimum``. A refused write returns ``False`` and changes nothing.

    Value writes (ports and settings) are recorded as undo steps only in level mode
    ``EDIT``, keyed to this route: its repeated writes to one field amend one step
    until another step, a fence, an undo or a 3 s pause ends the run.

    Example::

        route = EditRoute(lambda: level.editor, lambda: level.mode)

        route.set_port(node_id, "value_a", 2.0, minimum=LevelMode.OPERATE)  # False in view
        route.set_setting(node.props, "label", "Mixer", minimum=LevelMode.EDIT)
        route.reset_setting(node.props, "label", minimum=LevelMode.EDIT)

        if (editor := route.editor()) is not None:  # None below level mode edit
            editor.add_node(...)
    """

    def __init__(self, editor: Callable[[], Editor], mode: Callable[[], LevelMode]) -> None:
        self._editor = editor
        self._mode = mode

    @property
    def graph(self) -> BaseGraph:
        """The graph of the level's current ``Editor``."""
        return self._editor().graph

    def mode(self) -> LevelMode:
        """Return the level mode now."""
        return self._mode()

    def allows(self, minimum: LevelMode) -> bool:
        """Return whether the level mode now is at least ``minimum``."""
        return self._mode().satisfies(minimum)

    def editor(self) -> Editor | None:
        """Return the level's ``Editor`` for structure edits, or ``None`` below level mode ``EDIT``."""
        return self._editor() if self._mode() is LevelMode.EDIT else None

    def set_port(self, node_id: str, port_id: str, value: Any, *, minimum: LevelMode) -> bool:
        """Set a port's own value.

        A ``port_id`` that names no port of the node needs level mode ``EDIT``.

        Returns:
            ``False`` if the mode is below ``minimum``, or the node or port is unknown, or the
            port holds no own value (a pooled inlet or an ``ADD`` slot).
        """
        if not self.allows(minimum if self._port_operable(node_id, port_id) else LevelMode.EDIT):
            return False
        return self._editor().set_property(node_id, port_id, value, record=self._records(), merge_owner=self)

    def _port_operable(self, node_id: str, port_id: str) -> bool:
        """Return whether *port_id* names an operable port; a name that is no port is not one."""
        wrapper = self._editor().graph.get_node_wrapper(node_id)
        port = wrapper.node.ports.get(port_id) if wrapper is not None and wrapper.node is not None else None
        return port is not None and port.operable

    def _records(self) -> bool:
        return self._mode() is LevelMode.EDIT

    def set_setting(self, bag: Settings, name: str, value: Any, *, minimum: LevelMode) -> bool:
        """Set one field of a settings bag.

        A bag the graph's document does not save (a multi-selection's form) is written directly.

        Returns:
            ``False`` if the mode is below ``minimum`` or the bag has no field ``name``.
        """
        return self.set_settings([bag], name, value, minimum=minimum)

    def reset_setting(self, bag: Settings, name: str, *, minimum: LevelMode) -> bool:
        """Reset one field of a settings bag to the value it takes when not set locally.

        Returns:
            ``False`` if the mode is below ``minimum`` or the bag has no field ``name``.
        """
        return self.reset_settings([bag], name, minimum=minimum)

    def set_settings(self, bags: Sequence[Settings], name: str, value: Any, *, minimum: LevelMode) -> bool:
        """Set one field on several bags as one undo step.

        Bags the graph's document saves are written by one ``Editor.set_settings``; the
        others (a multi-selection's form) are written directly.

        Returns:
            ``False`` if the mode is below ``minimum`` or any bag has no field ``name``.
        """
        saved, direct = self._split(bags, name)
        if saved is None or not self.allows(self._minimum_for(bags, name, minimum)):
            return False
        for bag in direct:
            setattr(bag, name, value)
        if saved:
            return self._editor().set_settings(saved, name, value, record=self._records(), merge_owner=self)
        return True

    def reset_settings(self, bags: Sequence[Settings], name: str, *, minimum: LevelMode) -> bool:
        """Reset one field on several bags to the value it takes when not set locally, as one undo step.

        Returns:
            ``False`` if the mode is below ``minimum`` or any bag has no field ``name``.
        """
        saved, direct = self._split(bags, name)
        if saved is None or not self.allows(self._minimum_for(bags, name, minimum)):
            return False
        for bag in direct:
            bag._reset(name)
        if saved:
            return self._editor().reset_settings(saved, name, record=self._records(), merge_owner=self)
        return True

    @staticmethod
    def _minimum_for(bags: Sequence[Settings], name: str, minimum: LevelMode) -> LevelMode:
        """Return ``minimum``, or ``EDIT`` if field ``name`` of any bag is not operable."""
        if all(type(bag)._settings_descriptors()[name].operable for bag in bags):
            return minimum
        return LevelMode.EDIT

    def _split(
        self, bags: Sequence[Settings], name: str
    ) -> tuple[list[SettingOwner] | None, list[Settings]]:
        """Return the owners of the bags the document saves and the bags it does not.

        The owners are ``None`` if any bag lacks the field ``name``.
        """
        graph = self._editor().graph
        saved: list[SettingOwner] = []
        direct: list[Settings] = []
        for bag in bags:
            if name not in type(bag)._settings_descriptors():
                return None, []
            owner = setting_owner(graph, bag)
            if owner is None:
                direct.append(bag)
            else:
                saved.append(owner)
        return saved, direct
