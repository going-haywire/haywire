"""A haybale.toml edit refreshes the identity in place — no module reload.

The refresh is an ordinary `HotReloadRegistry` (`_HaybaleTomlWatcher`) sitting on
the library's root fallback, so a metadata change travels the same dispatch path
as everything else the watcher sees. The handler stays a router: it detects
changes and informs, and knows nothing about haybale.toml.

Because it rides the normal path it is also debounced (0.5s) rather than
synchronous. The tests drive a local `_drain()` helper instead of sleeping.

Only the fields that cannot be read at the point of use are refreshed: `label`
(logged from inside the registry, which cannot do a file read per line),
`linked_libraries` (consumed during module registration, inside the import
machinery) and `on_reload` (read after eviction, when the files may be gone).
"""

from pathlib import Path
from types import SimpleNamespace

import pytest

from haywire.core.library.base import BaseLibrary
from haywire.core.library.haybale_toml import HAYBALE_TOML
from haywire.core.library.identity import LibraryIdentity
from haywire.core.registry.base import BaseRegistry


class _Lib(BaseLibrary):
    def register_components(self) -> None:  # pragma: no cover - not exercised here
        pass

    def validate(self) -> bool:  # pragma: no cover - not exercised here
        return True


class _ReloadRecordingRegistry(BaseRegistry):
    """A real BaseRegistry: it takes the genuine event_dispatcher path, so the
    rejection it performs is the shipped one, not a stand-in."""

    def __init__(self) -> None:
        super().__init__()
        self.seen: list[str] = []
        self.reloaded: list[str] = []

    def _class_filter(self, cls) -> bool:  # pragma: no cover - never reached here
        return False

    def _register_class(self, cls, library_identity=None):  # pragma: no cover
        return None

    def _unregister_class(self, registry_key):  # pragma: no cover
        return None

    def event_dispatcher(self, event):
        self.seen.append(event.file_path)
        return super().event_dispatcher(event)

    def _on_change(self, module_name, library_identity, event=None):
        self.reloaded.append(module_name)

    def _on_creation(self, module_name, library_identity, event=None):
        self.reloaded.append(module_name)

    def _on_delete(self, module_name, library_identity):
        self.reloaded.append(module_name)


def _library(tmp_path: Path, body: str) -> _Lib:
    (tmp_path / HAYBALE_TOML).write_text(body)
    _Lib.class_identity = LibraryIdentity(
        id="demo",
        label="Before",
        folder_path=str(tmp_path),
        module_name="haybale_demo",
        linked_libraries=["haybale_core"],
    )
    lib = _Lib(file_path=str(tmp_path / "__init__.py"), enforce_file_watching=True)
    # The adapter reaches the handler through the root fallback, which
    # _attach_to_registries installs. No component folders are registered, so
    # nothing competes with it — which is the arrangement every real library has.
    lib._attach_to_registries()
    return lib


def _drain(lib: _Lib) -> None:
    """Run every pending debounced event now, instead of waiting 0.5s for it.

    Cancels the timers and calls the same `_process_debounced_event` they would
    have called, so the dispatch under test is the real one — only the delay is
    skipped. Sleeping instead would cost ~4s across this file and time out
    under load.
    """
    handler = lib.file_watcher.handler
    with handler._lock:
        for timer in handler.debounce_timers.values():
            timer.cancel()
        pending = list(handler.pending_events)

    for event_key in pending:
        _file_path, registry_id = event_key
        registry = next(r for r in _fallback_registries(lib) if id(r) == registry_id)
        handler._process_debounced_event(event_key, registry)


def _fallback_registries(lib: _Lib):
    """Every registry the library put on its root fallback."""
    _identity, registries, _delay = lib.file_watcher.handler.root_fallbacks[lib.identity.folder_path]
    return registries


def _modified(path: Path) -> SimpleNamespace:
    return SimpleNamespace(is_directory=False, src_path=str(path))


def _moved(src: Path, dest: Path) -> SimpleNamespace:
    return SimpleNamespace(is_directory=False, src_path=str(src), dest_path=str(dest))


# ── the refresh ──────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_edit_refreshes_label_and_linked_libraries(tmp_path: Path) -> None:
    lib = _library(tmp_path, 'id = "demo"\nversion = "0.0.1"\nlabel = "Before"\n')

    (tmp_path / HAYBALE_TOML).write_text(
        'id = "demo"\nversion = "0.0.1"\nlabel = "After"\nlinked_libraries = ["haybale_studio"]\n'
    )
    lib.file_watcher.handler.on_modified(_modified(tmp_path / HAYBALE_TOML))
    _drain(lib)

    assert lib.identity.label == "After"
    assert lib.identity.linked_libraries == ["haybale_studio"]


@pytest.mark.unit
def test_the_identity_is_mutated_in_place(tmp_path: Path) -> None:
    """The identity object is held by the registry and the reload machinery, so
    a replacement would refresh nothing."""
    lib = _library(tmp_path, 'id = "demo"\nversion = "0.0.1"\nlabel = "Before"\n')
    held = lib.identity

    (tmp_path / HAYBALE_TOML).write_text('id = "demo"\nversion = "0.0.1"\nlabel = "After"\n')
    lib.file_watcher.handler.on_modified(_modified(tmp_path / HAYBALE_TOML))
    _drain(lib)

    assert held.label == "After"
    assert lib.identity is held


@pytest.mark.unit
def test_a_metadata_edit_does_not_trigger_a_module_reload(tmp_path: Path) -> None:
    """A description change is not a code change. The .toml reaches every
    registry on the fallback, and each one that reloads modules rejects it —
    only the adapter acts."""
    lib = _library(tmp_path, 'id = "demo"\nversion = "0.0.1"\nlabel = "Before"\n')
    # A real module-reloading registry, sharing the fallback with the adapter
    # exactly as a library's own registries do.
    reloader = _ReloadRecordingRegistry()
    identity, registries, delay = lib.file_watcher.handler.root_fallbacks[lib.identity.folder_path]
    lib.file_watcher.handler.root_fallbacks[lib.identity.folder_path] = (
        identity,
        [*registries, reloader],
        delay,
    )

    lib.file_watcher.handler.on_modified(_modified(tmp_path / HAYBALE_TOML))
    _drain(lib)

    assert lib.identity.label == "Before"
    assert reloader.seen, "the router must offer the .toml to every registry on the fallback"
    assert reloader.reloaded == [], "and the registry's own guard must reject it"


@pytest.mark.unit
def test_atomic_write_paths_are_covered(tmp_path: Path) -> None:
    """Editors save by writing a temp file and renaming it over the target, so a
    real edit can arrive as CREATE or MOVE rather than MODIFY."""
    lib = _library(tmp_path, 'id = "demo"\nversion = "0.0.1"\nlabel = "Before"\n')
    target = tmp_path / HAYBALE_TOML
    handler = lib.file_watcher.handler

    target.write_text('id = "demo"\nversion = "0.0.1"\nlabel = "Via create"\n')
    handler.on_created(_modified(target))
    _drain(lib)
    assert lib.identity.label == "Via create"

    target.write_text('id = "demo"\nversion = "0.0.1"\nlabel = "Via move"\n')
    handler.on_moved(_moved(tmp_path / "haybale.toml.tmp", target))
    _drain(lib)
    assert lib.identity.label == "Via move"


# ── failure is not fatal ─────────────────────────────────────────────────────


@pytest.mark.unit
def test_a_malformed_edit_logs_and_keeps_the_previous_values(tmp_path: Path, caplog) -> None:
    """Opposite of the import-time rule: the author is mid-keystroke, so a
    half-written file must not break a running studio."""
    lib = _library(tmp_path, 'id = "demo"\nversion = "0.0.1"\nlabel = "Before"\n')

    (tmp_path / HAYBALE_TOML).write_text("label = [unclosed\n")
    with caplog.at_level("WARNING"):
        lib.file_watcher.handler.on_modified(_modified(tmp_path / HAYBALE_TOML))
        _drain(lib)

    assert lib.identity.label == "Before"
    assert "keeping previous metadata" in caplog.text


@pytest.mark.unit
def test_a_deleted_file_keeps_the_previous_values(tmp_path: Path) -> None:
    """The adapter gets DELETED like any other event; _reload_metadata handles
    the missing file via HaybaleTomlError → warn → keep previous."""
    lib = _library(tmp_path, 'id = "demo"\nversion = "0.0.1"\nlabel = "Before"\n')

    (tmp_path / HAYBALE_TOML).unlink()
    lib.file_watcher.handler.on_deleted(_modified(tmp_path / HAYBALE_TOML))
    _drain(lib)

    assert lib.identity.label == "Before"


# ── the adapter's reach is narrow ────────────────────────────────────────────


@pytest.mark.unit
def test_a_nested_librarys_file_is_not_refreshed(tmp_path: Path) -> None:
    """The watch is recursive, so a nested library's haybale.toml is seen here
    too — but it belongs to that library, not this one."""
    lib = _library(tmp_path, 'id = "demo"\nversion = "0.0.1"\nlabel = "Before"\n')
    nested = tmp_path / "vendored"
    nested.mkdir()
    (nested / HAYBALE_TOML).write_text('id = "other"\nversion = "0.0.1"\nlabel = "Other"\n')

    lib.file_watcher.handler.on_modified(_modified(nested / HAYBALE_TOML))
    _drain(lib)

    assert lib.identity.label == "Before"


@pytest.mark.unit
def test_other_root_files_do_not_refresh_metadata(tmp_path: Path) -> None:
    """pyproject.toml sits beside haybale.toml and is not it."""
    lib = _library(tmp_path, 'id = "demo"\nversion = "0.0.1"\nlabel = "Before"\n')
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "demo"\n')
    (tmp_path / HAYBALE_TOML).write_text('id = "demo"\nversion = "0.0.1"\nlabel = "After"\n')

    lib.file_watcher.handler.on_modified(_modified(tmp_path / "pyproject.toml"))
    _drain(lib)

    assert lib.identity.label == "Before", "only haybale.toml refreshes the identity"
