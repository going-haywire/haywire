"""LibraryRegistry post-enable callbacks.

Tests for ``add_library_enabled_callback`` + ``_fire_library_enabled`` —
the mechanism that lets ``LibraryStateContainer`` learn "library X
finished registering its components" so it can catch up on X's state
classes per-library instead of reacting to per-folder batch events
mid-enable.

These tests bypass ``BaseLibrary``'s abstract methods by mocking the
library instance; the registry's callback logic doesn't read anything
beyond ``library.enable()`` and ``library.identity.label``.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from haywire.core.library.registry import LibraryRegistry


def make_library_mock(library_id: str = "midi") -> MagicMock:
    """Build a stand-in BaseLibrary: only enable() and identity are read."""
    lib = MagicMock()
    lib.identity.id = library_id
    lib.identity.label = library_id.capitalize()
    return lib


class TestAddLibraryEnabledCallback:
    def test_callback_added_to_internal_list(self):
        reg = LibraryRegistry()

        def cb(library):
            pass

        reg.add_library_enabled_callback(cb)
        assert cb in reg._library_enabled_callbacks

    def test_multiple_callbacks_preserved_in_registration_order(self):
        reg = LibraryRegistry()
        order: list[str] = []

        def cb1(_lib):
            order.append("cb1")

        def cb2(_lib):
            order.append("cb2")

        def cb3(_lib):
            order.append("cb3")

        reg.add_library_enabled_callback(cb1)
        reg.add_library_enabled_callback(cb2)
        reg.add_library_enabled_callback(cb3)

        # Use _fire_library_enabled directly — that's what tests target.
        reg._fire_library_enabled(make_library_mock())

        assert order == ["cb1", "cb2", "cb3"]


class TestFireLibraryEnabled:
    def test_callback_receives_library_instance(self):
        reg = LibraryRegistry()
        captured: list = []

        def cb(library):
            captured.append(library)

        reg.add_library_enabled_callback(cb)
        lib = make_library_mock("audio")
        reg._fire_library_enabled(lib)

        assert captured == [lib]

    def test_callback_exception_is_logged_and_does_not_stop_other_callbacks(self, caplog):
        reg = LibraryRegistry()
        order: list[str] = []

        def bad_cb(_lib):
            order.append("bad")
            raise RuntimeError("intentional test failure")

        def good_cb(_lib):
            order.append("good")

        reg.add_library_enabled_callback(bad_cb)
        reg.add_library_enabled_callback(good_cb)

        # Should not raise.
        with caplog.at_level("ERROR"):
            reg._fire_library_enabled(make_library_mock())

        assert order == ["bad", "good"]
        assert any("post-enable callback" in rec.message for rec in caplog.records)

    def test_no_callbacks_is_a_noop(self):
        reg = LibraryRegistry()
        # Should not raise.
        reg._fire_library_enabled(make_library_mock())


class TestEnableAllLibrariesFiresCallbacks:
    def test_callback_fires_after_each_library_enable(self):
        reg = LibraryRegistry()
        order: list[str] = []

        lib_a = make_library_mock("a")
        lib_b = make_library_mock("b")

        # Library.enable() records its own invocation order so we can prove
        # the callback fires AFTER it (not before).
        def enable_a():
            order.append("a-enable")

        def enable_b():
            order.append("b-enable")

        lib_a.enable.side_effect = enable_a
        lib_b.enable.side_effect = enable_b

        reg._libraries["a"] = lib_a
        reg._libraries["b"] = lib_b

        def cb(library):
            order.append(f"{library.identity.id}-callback")

        reg.add_library_enabled_callback(cb)
        reg.enable_all_libraries()

        # Each library's enable() runs BEFORE its callback fires.
        assert order == [
            "a-enable",
            "a-callback",
            "b-enable",
            "b-callback",
        ]

    def test_callback_fires_per_library_not_at_the_end(self):
        """Each library's enable() must be followed immediately by its
        callback, NOT batched until after all libraries have enabled.
        This is what makes M1 work for hot-installed libraries at runtime
        — the callback fires per-library, so the state container can
        catch up incrementally.

        The previous test asserts ordering with two libraries; this test
        makes the same point in a way that explicitly forbids the
        'fire all callbacks at the end' shape."""
        reg = LibraryRegistry()
        callback_times: dict[str, int] = {}
        enable_times: dict[str, int] = {}
        counter = [0]

        def make_lib(library_id):
            lib = make_library_mock(library_id)

            def enable_fn():
                enable_times[library_id] = counter[0]
                counter[0] += 1

            lib.enable.side_effect = enable_fn
            return lib

        lib_first = make_lib("first")
        lib_second = make_lib("second")
        reg._libraries["first"] = lib_first
        reg._libraries["second"] = lib_second

        def cb(library):
            callback_times[library.identity.id] = counter[0]
            counter[0] += 1

        reg.add_library_enabled_callback(cb)
        reg.enable_all_libraries()

        # first's callback runs BEFORE second's enable runs.
        assert callback_times["first"] < enable_times["second"]


class TestEnableLibraryFiresCallback:
    def test_callback_fires_for_targeted_library(self):
        reg = LibraryRegistry()
        captured: list[str] = []

        lib = make_library_mock("midi")
        reg._libraries["midi"] = lib

        def cb(library):
            captured.append(library.identity.id)

        reg.add_library_enabled_callback(cb)
        ok = reg.enable_library("midi")

        assert ok is True
        assert captured == ["midi"]

    def test_unknown_library_does_not_fire_callbacks(self):
        reg = LibraryRegistry()
        captured: list[str] = []

        def cb(library):
            captured.append(library.identity.id)

        reg.add_library_enabled_callback(cb)
        ok = reg.enable_library("does-not-exist")

        assert ok is False
        assert captured == []


class TestDisableLibraryFiresCallback:
    """Mirror of TestEnableLibraryFiresCallback: disable_library must fire
    every registered disable callback after library.disable() returns, so
    LibraryStateContainer can drop the library from its filter set."""

    def test_callback_fires_for_targeted_library_after_disable(self):
        reg = LibraryRegistry()
        order: list[str] = []

        lib = make_library_mock("midi")
        # Library.disable() records its invocation so we can prove the
        # callback fires AFTER, not before.
        lib.disable.side_effect = lambda: order.append("disable")
        reg._libraries["midi"] = lib

        def cb(library):
            order.append(f"{library.identity.id}-callback")

        reg.add_library_disabled_callback(cb)
        ok = reg.disable_library("midi")

        assert ok is True
        assert order == ["disable", "midi-callback"]

    def test_unknown_library_does_not_fire_callbacks(self):
        reg = LibraryRegistry()
        captured: list[str] = []

        def cb(library):
            captured.append(library.identity.id)

        reg.add_library_disabled_callback(cb)
        ok = reg.disable_library("does-not-exist")

        assert ok is False
        assert captured == []

    def test_disable_callback_exception_is_logged_and_does_not_stop_other_callbacks(self, caplog):
        reg = LibraryRegistry()
        order: list[str] = []

        def bad_cb(_lib):
            order.append("bad")
            raise RuntimeError("intentional test failure")

        def good_cb(_lib):
            order.append("good")

        reg.add_library_disabled_callback(bad_cb)
        reg.add_library_disabled_callback(good_cb)

        # Should not raise.
        with caplog.at_level("ERROR"):
            reg._fire_library_disabled(make_library_mock())

        assert order == ["bad", "good"]
        assert any("post-disable callback" in rec.message for rec in caplog.records)
