"""The @reveal_on seam: editor CLASSES claim a bare RevealSignal.

The property that justifies the whole mechanism is the zero-instance case.
``@react_on`` subscribes an *instance*, so an ``OpenBehavior.ON_PAYLOAD``
editor with no tab open has no subscriber at all and the signal reaches
nobody — which is exactly the state you are in when you ask to open a file
for the first time. ``@reveal_on`` is read off the class by the always-alive
AppShell, so it fires with no instance and the reveal creates the tab.

It also inverts who names whom: the publisher names no editor class, so
haywire-core can ask for a reveal that a barn library answers without
importing it (.insights/project_app_library_dependency_direction.md).
"""

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, cast

import pytest

from haywire.core.session.handlers import discover_reveal_handlers, reveal_on
from haywire.core.signals import RevealSignal
from haywire.ui.app.shell import AppShell
from haywire.ui.editor.identity import OpenBehavior

pytestmark = pytest.mark.unit


@dataclass(frozen=True, kw_only=True)
class _DemoReveal(RevealSignal):
    note: str = ""


class _FakeSession:
    def __init__(self) -> None:
        self.context = SimpleNamespace(touched=[])
        self.workspace_manager = SimpleNamespace(
            active=SimpleNamespace(
                left=SimpleNamespace(active_tab_key=None, visible=True, size=300),
                right=SimpleNamespace(active_tab_key=None, visible=True, size=300),
                main=SimpleNamespace(tabs=[], active_tab_key=None),
                bottom=SimpleNamespace(tabs=[], active_tab_key=None, visible=False, size=200),
            )
        )
        self.subscriptions: dict = {}

    def subscribe(self, event_type, handler):
        self.subscriptions.setdefault(event_type, []).append(handler)
        return lambda: None


class _FakeSlot:
    def __init__(self) -> None:
        self.revealed: list = []

    def reveal(self, command, editor_cls=None) -> bool:
        self.revealed.append(((editor_cls or command.editor), command.binding_id))
        return True


class _FakeEditorRegistry:
    def __init__(self, classes: dict) -> None:
        self._classes = classes

    def list_names(self) -> list:
        return list(self._classes)

    def get(self, registry_key: str):
        return self._classes.get(registry_key)

    def get_by_key(self, registry_key: str):
        return self._classes.get(registry_key)

    def get_by_default_slot(self, _slot):
        return {}


def _editor_cls(name: str, decide, *, opens=OpenBehavior.ON_PAYLOAD) -> Any:
    """An editor-shaped class whose ``@reveal_on`` hook delegates to *decide*.

    ``decide(context, event) -> bool`` keeps each test's interesting line to
    one expression while the decorator/classmethod wiring stays identical to
    what a real editor writes.
    """

    @reveal_on(_DemoReveal)  # type: ignore[misc]  # classmethod built outside a class body
    @classmethod
    def _on_reveal(cls, context, event) -> bool:
        return decide(context, event)

    return type(
        name,
        (),
        {
            "class_identity": SimpleNamespace(
                registry_key=f"lib:editor:{name}",
                default_slot="edit",
                opens=opens,
                label=name,
                icon="icon",
            ),
            "_on_reveal": _on_reveal,
        },
    )


def _build_shell(classes: dict) -> tuple:
    session = _FakeSession()
    shell = AppShell(
        session=cast(Any, session),
        editor_registry=cast(Any, _FakeEditorRegistry(classes)),
    )
    slot = _FakeSlot()
    shell._managed_slots = cast(Any, {"edit": slot})
    shell._subscribe_reveal_on_editors()
    return shell, session, slot


def _fire(session: _FakeSession, command) -> None:
    for handler in session.subscriptions.get(type(command), []):
        handler(command)


# ---------------------------------------------------------------------------
# Declaration
# ---------------------------------------------------------------------------


def test_reveal_on_is_discovered_from_the_class_with_no_instance():
    cls = _editor_cls("Demo", lambda context, event: True)

    # No instance is ever constructed — this is the property @react_on lacks.
    assert discover_reveal_handlers(cls) == {_DemoReveal: "_on_reveal"}


def test_reveal_on_rejects_a_non_reveal_signal():
    from haywire.core.signals import SelectionMoved

    with pytest.raises(TypeError, match="RevealSignal"):

        @reveal_on(SelectionMoved)  # type: ignore[misc]
        @classmethod
        def hook(cls, context, event) -> bool:  # pragma: no cover
            return True


# ---------------------------------------------------------------------------
# Shell dispatch
# ---------------------------------------------------------------------------


def test_a_zero_instance_editor_is_revealed():
    """The case that motivates the decorator: no tab open, so no instance, so
    an instance-level @react_on would have nobody subscribed."""

    cls = _editor_cls("Demo", lambda context, event: True)
    _shell, session, slot = _build_shell({cls.class_identity.registry_key: cls})

    _fire(session, _DemoReveal(binding_id="/tmp/x.py"))

    assert slot.revealed == [(cls, "/tmp/x.py")]


def test_the_hook_runs_before_the_reveal():
    """Session state written by the hook must be in place before the editor
    draws, or the revealed tab renders the previous subject."""
    order: list = []

    def _decide(context, event) -> bool:
        order.append("hook")
        return True

    cls = _editor_cls("Demo", _decide)
    _shell, session, slot = _build_shell({cls.class_identity.registry_key: cls})

    class _RecordingSlot(_FakeSlot):
        def reveal(self, command, editor_cls=None) -> bool:
            order.append("reveal")
            return True

    _shell._managed_slots = cast(Any, {"edit": _RecordingSlot()})
    _fire(session, _DemoReveal(binding_id="/tmp/x.py"))

    assert order == ["hook", "reveal"]


def test_a_vetoing_hook_is_not_revealed():
    cls = _editor_cls("Demo", lambda context, event: False)
    _shell, session, slot = _build_shell({cls.class_identity.registry_key: cls})

    _fire(session, _DemoReveal(binding_id="/tmp/x.py"))

    assert slot.revealed == []


def test_only_the_claiming_class_among_several_is_revealed():
    """Two editors declare the same signal; each decides for itself, so a
    signal can be routed by content rather than by a discriminator field."""

    py_cls = _editor_cls("Py", lambda context, event: event.binding_id.endswith(".py"))
    md_cls = _editor_cls("Md", lambda context, event: event.binding_id.endswith(".md"))
    _shell, session, slot = _build_shell(
        {
            py_cls.class_identity.registry_key: py_cls,
            md_cls.class_identity.registry_key: md_cls,
        }
    )

    _fire(session, _DemoReveal(binding_id="/tmp/x.py"))

    assert slot.revealed == [(py_cls, "/tmp/x.py")]


def test_a_raising_hook_does_not_stop_the_other_candidates():
    def _boom(context, event) -> bool:
        raise RuntimeError("hook is broken")

    bad = _editor_cls("Bad", _boom)
    good = _editor_cls("Good", lambda context, event: True)
    _shell, session, slot = _build_shell(
        {
            bad.class_identity.registry_key: bad,
            good.class_identity.registry_key: good,
        }
    )

    _fire(session, _DemoReveal(binding_id="/tmp/x.py"))

    assert slot.revealed == [(good, "/tmp/x.py")]
