# tests/ui/surface/test_surface.py
"""Surface base class: id ClassVar, order/presentation/provides defaults,
concrete poll() default, runtime_checkable enforcement, and the
id -> class registry (surface_by_id / all_surfaces)."""

from __future__ import annotations

import importlib
import sys

from typing import Protocol, runtime_checkable

import pytest

from haywire.ui.surface.presentation import Presentation
from haywire.ui.surface.surface import Surface
from haywire.ui.surface.tree import all_surfaces, surface_by_id


def test_surface_subclass_with_id_is_discoverable():
    class _MySurface(Surface):
        id = "my_test_surface_unique_id"

        @classmethod
        def poll(cls, ctx):
            return True

    assert surface_by_id("my_test_surface_unique_id") is _MySurface
    assert _MySurface in all_surfaces()


def test_surface_id_collision_raises():
    """Two Surface subclasses with the same id (different origin) raise at
    class definition."""

    class _A(Surface):
        id = "duplicate_id_for_surface_collision_test"

    with pytest.raises(ValueError, match="collision"):

        class _B(Surface):
            id = "duplicate_id_for_surface_collision_test"


def test_surface_class_attributes_have_sensible_defaults():
    class _Demo(Surface):
        id = "demo_surface_id"
        order = 50

    assert _Demo.id == "demo_surface_id"
    assert _Demo.order == 50
    assert _Demo.presentation is None
    assert _Demo.provides is None


def test_surface_presentation_can_be_set():
    class _WithChrome(Surface):
        id = "surface_with_chrome"
        presentation = Presentation(label="Tab Label", icon="tune")

    assert _WithChrome.presentation == Presentation(label="Tab Label", icon="tune")


def test_poll_default_is_true_with_no_override():
    """A Surface subclass declaring no poll() override returns True when
    called. This is the fix vs Focus.available, which was an abstractmethod
    that read as None/false when merely called on the class."""

    class _NoPollOverride(Surface):
        id = "surface_no_poll_override"

    assert _NoPollOverride.poll(None) is True


def test_poll_can_be_overridden():
    class _PollsFalse(Surface):
        id = "surface_polls_false"

        @classmethod
        def poll(cls, ctx):
            return False

    assert _PollsFalse.poll(None) is False


def test_provides_must_be_runtime_checkable():
    """A Surface subclass setting provides to a plain (non-runtime_checkable)
    Protocol raises TypeError at class-definition time."""

    class _PlainProtocol(Protocol):
        def do_thing(self) -> None: ...

    with pytest.raises(TypeError, match="runtime_checkable"):

        class _BadSurface(Surface):
            id = "surface_bad_provides"
            provides = _PlainProtocol


def test_provides_accepts_runtime_checkable_protocol():
    @runtime_checkable
    class _GoodProtocol(Protocol):
        def do_thing(self) -> None: ...

    class _GoodSurface(Surface):
        id = "surface_good_provides"
        provides = _GoodProtocol

    assert _GoodSurface.provides is _GoodProtocol


def test_intermediate_subclass_without_id_is_not_registered():
    """A Surface subclass that doesn't declare id (an intermediate ABC) is
    skipped by registration, mirroring Focus's handling of intermediate
    classes."""

    class _IntermediateBase(Surface):
        order = 5

    assert surface_by_id("_IntermediateBase") is None
    assert _IntermediateBase not in all_surfaces()


@pytest.fixture(autouse=True)
def _isolate_hot_reload_target():
    """Pop the test-target module from sys.modules so each test starts fresh."""
    yield
    sys.modules.pop("tests.ui.surface._hot_reload_target", None)


def test_hot_reload_supersedes_same_module_qualname():
    """Redefining a Surface subclass with the same module+qualname (as
    happens on hot-reload) supersedes the old registration under the same
    id, per ADR-0009."""
    target = importlib.import_module("tests.ui.surface._hot_reload_target")

    OldSurface = target.MySurface
    assert surface_by_id("hot_reload_target_surface") is OldSurface

    importlib.reload(target)
    NewSurface = target.MySurface

    assert OldSurface is not NewSurface
    assert surface_by_id("hot_reload_target_surface") is NewSurface
    assert surface_by_id("hot_reload_target_surface") is not OldSurface
