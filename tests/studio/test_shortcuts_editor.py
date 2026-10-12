"""ShortcutsEditor: every editor's shortcuts, grouped per editor, the target editor's group open."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, ClassVar
from unittest.mock import MagicMock

import pytest
from nicegui import ui
from nicegui.testing import User
from nicegui.testing.user_simulation import user_simulation

from haywire.core.session.context import SessionContext
from haywire.core.session.handlers import _REACT_ON_ATTR, _REDRAW_ON_ATTR, react_on
from haywire.core.signals import Copy, Delete, EditorCommand, Undo
from haywire.core.signals.keys import format_combo
from haywire.ui.editor.identity import SlotName
from haywire.ui.keymap import Keymap, build_keymap

from haybale_studio.editors.shortcuts_editor import ShortcutsEditor

pytestmark = pytest.mark.unit

_GRAPH_KEY = "lib:editors:Graph"
_CODE_KEY = "lib:editors:Code"
_CLASH_KEY = "lib:editors:Clashy"


@dataclass(frozen=True, kw_only=True)
class _FirstK(EditorCommand):
    command_id: ClassVar[str] = "aaa.first_k"
    label: ClassVar[str] = "First K"
    default_keys: ClassVar[tuple[str, ...]] = ("Mod+K",)


@dataclass(frozen=True, kw_only=True)
class _SecondK(EditorCommand):
    command_id: ClassVar[str] = "zzz.second_k"
    label: ClassVar[str] = "Second K"
    default_keys: ClassVar[tuple[str, ...]] = ("Mod+K",)


def _identity(label: str) -> Any:
    return SimpleNamespace(registry_key=f"test:{label}", label=label)


class _GraphEditor:
    class_identity = _identity("Graph")

    @react_on(Copy)
    def _on_copy(self, ctx, signal): ...

    @react_on(Delete)
    def _on_delete(self, ctx, signal): ...


class _CodeEditor:
    class_identity = _identity("Code")

    @react_on(Undo)
    def _on_undo(self, ctx, signal): ...


class _ClashEditor:
    class_identity = _identity("Clashy")

    @react_on(_FirstK)
    def _on_first(self, ctx, signal): ...

    @react_on(_SecondK)
    def _on_second(self, ctx, signal): ...


def _keymap() -> Keymap:
    return build_keymap(
        {_GRAPH_KEY: _GraphEditor, _CODE_KEY: _CodeEditor, _CLASH_KEY: _ClashEditor},
        lambda _tier: True,
    )


def _empty_keymap() -> Keymap:
    return Keymap(
        editors={}, editor_labels={}, commands={}, clashes=(), reserved=(), invalid=(), duplicate_ids=()
    )


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def user() -> AsyncGenerator[User, None]:
    async with user_simulation() as u:
        yield u


class _Harness:
    """Draws a ShortcutsEditor into a container and redraws it the way its wrapper does."""

    def __init__(self, keymap: Keymap | None, target: str | None) -> None:
        self.ctx = SimpleNamespace(keymap=keymap, target_binding_id=target)
        self.wrapper = MagicMock()
        self.wrapper.redraw.side_effect = self.redraw
        self.editor = ShortcutsEditor(self.wrapper)
        self.container: ui.element | None = None

    def mount(self) -> None:
        self.container = ui.column()
        self.redraw()

    def redraw(self) -> None:
        assert self.container is not None
        self.container.clear()
        self.editor.draw(self.ctx, self.container)  # type: ignore[arg-type]

    def retarget(self, binding_id: str | None) -> None:
        """Change the target editor and dispatch the change the way the session bus does."""
        self.ctx.target_binding_id = binding_id
        self.editor._on_target(self.ctx, None)  # type: ignore[arg-type]

    def descendants(self) -> list[ui.element]:
        assert self.container is not None
        return list(self.container.descendants())

    def groups(self) -> dict[str, ui.expansion]:
        return {el.text: el for el in self.descendants() if isinstance(el, ui.expansion)}

    def open_groups(self) -> list[str]:
        return [label for label, exp in self.groups().items() if exp.value]


def _texts(root: ui.element, cls: str) -> list[str]:
    return [el.text for el in [root, *root.descendants()] if cls in el._classes and hasattr(el, "text")]


async def _open(user: User, harness: _Harness) -> None:
    @ui.page("/")
    def page() -> None:
        harness.mount()

    await user.open("/")


def test_editor_identity_is_a_context_slot_editor() -> None:
    identity = ShortcutsEditor.class_identity
    assert identity.label == "Shortcuts"
    assert identity.default_slot is SlotName.CONTEXT


def test_editor_redraws_on_keymap_changes_and_reacts_to_target_changes() -> None:
    assert getattr(ShortcutsEditor._on_keymap, _REDRAW_ON_ATTR, ()) == (SessionContext.keymap,)
    assert getattr(ShortcutsEditor._on_target, _REACT_ON_ATTR, ()) == (SessionContext.target_binding_id,)


@pytest.mark.anyio
async def test_one_group_per_editor_ordered_by_label(user: User) -> None:
    harness = _Harness(_keymap(), None)
    await _open(user, harness)

    assert list(harness.groups()) == ["Clashy", "Code", "Graph"]


@pytest.mark.anyio
async def test_the_target_editors_group_is_open_and_the_others_closed(user: User) -> None:
    harness = _Harness(_keymap(), f"{_GRAPH_KEY}::graph-1")
    await _open(user, harness)

    assert harness.open_groups() == ["Graph"]
    graph = harness.groups()["Graph"]
    assert "active" in [getattr(el, "text", None) for el in graph.descendants()]
    code = harness.groups()["Code"]
    assert "active" not in [getattr(el, "text", None) for el in code.descendants()]


@pytest.mark.anyio
async def test_a_new_target_reexpands_its_group(user: User) -> None:
    harness = _Harness(_keymap(), f"{_GRAPH_KEY}::graph-1")
    await _open(user, harness)

    harness.retarget(_CODE_KEY)

    assert harness.open_groups() == ["Code"]


@pytest.mark.anyio
async def test_a_target_without_shortcuts_keeps_the_groups_without_a_redraw(user: User) -> None:
    harness = _Harness(_keymap(), f"{_GRAPH_KEY}::graph-1")
    await _open(user, harness)
    groups_before = harness.groups()

    harness.retarget("studio:editors:Shortcuts")

    harness.wrapper.redraw.assert_not_called()
    assert harness.groups() == groups_before
    assert harness.open_groups() == ["Graph"]


@pytest.mark.anyio
async def test_a_retarget_to_the_followed_editor_does_not_redraw(user: User) -> None:
    harness = _Harness(_keymap(), f"{_GRAPH_KEY}::graph-1")
    await _open(user, harness)

    harness.retarget(f"{_GRAPH_KEY}::graph-2")

    harness.wrapper.redraw.assert_not_called()


@pytest.mark.anyio
async def test_a_hand_toggled_group_keeps_its_state_across_redraws(user: User) -> None:
    harness = _Harness(_keymap(), f"{_GRAPH_KEY}::graph-1")
    await _open(user, harness)

    user.find(kind=ui.expansion, content="Code").trigger("update:modelValue", True)
    user.find(kind=ui.expansion, content="Graph").trigger("update:modelValue", False)
    harness.redraw()

    assert harness.open_groups() == ["Code"]


@pytest.mark.anyio
async def test_following_resumes_after_a_target_without_shortcuts(user: User) -> None:
    harness = _Harness(_keymap(), f"{_GRAPH_KEY}::graph-1")
    await _open(user, harness)

    harness.retarget("studio:editors:Shortcuts")
    user.find(kind=ui.expansion, content="Code").trigger("update:modelValue", True)
    user.find(kind=ui.expansion, content="Graph").trigger("update:modelValue", False)
    harness.retarget(f"{_GRAPH_KEY}::graph-1")

    assert harness.open_groups() == ["Graph"]
    graph = harness.groups()["Graph"]
    assert "active" in [getattr(el, "text", None) for el in graph.descendants()]


@pytest.mark.anyio
async def test_every_combo_of_a_command_is_listed(user: User) -> None:
    harness = _Harness(_keymap(), None)
    await _open(user, harness)

    graph = harness.groups()["Graph"]
    other = _texts(graph, "hw-keys-other")
    mac = _texts(graph, "hw-keys-mac")
    for combo in ("Delete", "Backspace"):
        assert format_combo(combo, mac=False) in other
        assert format_combo(combo, mac=True) in mac
    assert format_combo("Mod+C", mac=False) in other


@pytest.mark.anyio
async def test_a_shadowed_command_is_marked_with_its_winner(user: User) -> None:
    harness = _Harness(_keymap(), None)
    await _open(user, harness)

    clashy = harness.groups()["Clashy"]
    warnings = _texts(clashy, "hw-text-warning")
    assert warnings == ["Shadowed by First K"]


@pytest.mark.anyio
@pytest.mark.parametrize("keymap", [None, _empty_keymap()])
async def test_no_shortcuts_shows_the_empty_state(user: User, keymap: Keymap | None) -> None:
    harness = _Harness(keymap, None)
    await _open(user, harness)

    texts = [getattr(el, "text", None) for el in harness.descendants()]
    assert "No editor declares keyboard shortcuts." in texts
    assert harness.groups() == {}
