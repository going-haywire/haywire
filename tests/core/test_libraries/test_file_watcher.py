"""
Tests for LibraryFileHandler — the component that translates OS filesystem
events (via watchdog) into debounced FileChangeEvents dispatched to registries.

Covers:
  - Basic file operations: creation, modification, deletion
  - Atomic writes (tmp → .py rename): should emit MODIFIED, not CREATED
  - Spurious DELETE suppression after atomic writes
  - True renames (foo.py → bar.py): should emit DELETED + CREATED
  - Debounce coalescing: rapid events collapse into the latest one
  - Non-.py files are ignored
  - Directory events are ignored
  - Multiple registry routing
  - Race condition: CREATE arriving before MOVE during atomic write
  - Known-files tracking: pre-existing files seeded on folder registration
"""

import threading
import time

import pytest
from watchdog.events import (
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileMovedEvent,
    DirCreatedEvent,
)

from haywire.core.library.file_watcher import LibraryFileHandler
from haywire.core.library.identity import LibraryIdentity
from haywire.core.registry.base import FileChangeEvent, FileEventType, HotReloadRegistry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_identity(label: str = "TestLib", folder: str = "/tmp/fake") -> LibraryIdentity:
    return LibraryIdentity(
        label=label,
        version="0.1",
        description="test",
        url="",
        help_url="",
        author="",
        author_url="",
        folder_path=folder,
    )


class RecordingRegistry(HotReloadRegistry):
    """A minimal registry that just records dispatched events."""

    def __init__(self):
        self.events: list[FileChangeEvent] = []
        self._event = threading.Event()

    def event_dispatcher(self, event: FileChangeEvent):
        self.events.append(event)
        self._event.set()

    def wait_for_event(self, timeout: float = 2.0) -> bool:
        """Wait until at least one event arrives. Returns True if event received."""
        return self._event.wait(timeout)

    def wait_for_n_events(self, n: int, timeout: float = 2.0) -> bool:
        """Wait until n events have arrived."""
        deadline = time.monotonic() + timeout
        while len(self.events) < n:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            time.sleep(0.01)
        return True

    def clear(self):
        self.events.clear()
        self._event.clear()


@pytest.fixture
def tmp_lib(tmp_path):
    """Create a temp directory with a pre-existing .py file to simulate a library folder."""
    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()
    (lib_dir / "existing.py").write_text("# existing module\n")
    return lib_dir


@pytest.fixture
def handler():
    h = LibraryFileHandler()
    yield h
    h.cleanup()


@pytest.fixture
def identity(tmp_lib):
    return _make_identity(folder=str(tmp_lib))


@pytest.fixture
def registry():
    return RecordingRegistry()


@pytest.fixture
def wired_handler(handler, identity, registry):
    """Handler with a single folder mapping, using a very short debounce."""
    handler.add_folder_mapping(identity.folder_path, identity, registry, debounce_delay=0.05)
    return handler


# ---------------------------------------------------------------------------
# Basic operations
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.core
class TestBasicFileOperations:
    """Test that standard filesystem events produce the correct FileEventType."""

    def test_file_created(self, wired_handler, identity, registry):
        """A new .py file should dispatch CREATED."""
        path = f"{identity.folder_path}/new_module.py"
        wired_handler.on_created(FileCreatedEvent(path))
        assert registry.wait_for_event()
        assert len(registry.events) == 1
        assert registry.events[0].event_type == FileEventType.CREATED
        assert registry.events[0].file_path == path

    def test_file_modified(self, wired_handler, identity, registry):
        """A modified .py file should dispatch MODIFIED."""
        path = f"{identity.folder_path}/existing.py"
        wired_handler.on_modified(FileModifiedEvent(path))
        assert registry.wait_for_event()
        assert len(registry.events) == 1
        assert registry.events[0].event_type == FileEventType.MODIFIED

    def test_file_deleted(self, wired_handler, identity, registry):
        """A deleted .py file should dispatch DELETED."""
        path = f"{identity.folder_path}/old_module.py"
        wired_handler.on_deleted(FileDeletedEvent(path))
        assert registry.wait_for_event()
        assert len(registry.events) == 1
        assert registry.events[0].event_type == FileEventType.DELETED


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.core
class TestFiltering:
    """Verify that non-.py files and directories are ignored."""

    def test_non_python_file_ignored(self, wired_handler, identity, registry):
        """Events for non-.py files should be silently dropped."""
        base = identity.folder_path
        wired_handler.on_created(FileCreatedEvent(f"{base}/readme.md"))
        wired_handler.on_modified(FileModifiedEvent(f"{base}/data.json"))
        wired_handler.on_deleted(FileDeletedEvent(f"{base}/style.css"))
        # Give debounce time to fire (if anything were pending)
        time.sleep(0.1)
        assert len(registry.events) == 0

    def test_directory_events_ignored(self, wired_handler, identity, registry):
        """Directory events should be silently dropped."""
        wired_handler.on_created(DirCreatedEvent(f"{identity.folder_path}/subdir"))
        time.sleep(0.1)
        assert len(registry.events) == 0

    def test_file_outside_watched_folder_ignored(self, handler, registry, identity):
        """Events for files outside all watched folders should be dropped."""
        handler.add_folder_mapping(identity.folder_path, identity, registry, debounce_delay=0.05)
        handler.on_created(FileCreatedEvent("/completely/other/path/module.py"))
        time.sleep(0.1)
        assert len(registry.events) == 0


# ---------------------------------------------------------------------------
# Atomic writes (tmp → .py)
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.core
class TestAtomicWrites:
    """
    Editors and tools often write atomically: write to a temp file, then
    rename it over the target.  The watcher should treat this as MODIFIED.
    """

    def test_atomic_write_emits_modified(self, wired_handler, identity, registry):
        """A move from a .tmp file to a .py file should dispatch MODIFIED."""
        base = identity.folder_path
        wired_handler.on_moved(FileMovedEvent(f"{base}/module.py.tmp.12345", f"{base}/module.py"))
        assert registry.wait_for_event()
        assert len(registry.events) == 1
        assert registry.events[0].event_type == FileEventType.MODIFIED
        assert registry.events[0].file_path == f"{base}/module.py"

    def test_atomic_write_suppresses_spurious_delete(self, wired_handler, identity, registry):
        """
        After an atomic write (MOVE), the OS may deliver a spurious DELETE
        for the destination file.  The watcher should suppress it.
        """
        base = identity.folder_path
        wired_handler.on_moved(FileMovedEvent(f"{base}/module.py.tmp.12345", f"{base}/module.py"))
        assert registry.wait_for_event()
        registry.clear()

        # Spurious DELETE arrives shortly after
        wired_handler.on_deleted(FileDeletedEvent(f"{base}/module.py"))
        time.sleep(0.1)
        assert len(registry.events) == 0, "DELETE after atomic write should be suppressed"

    def test_delete_suppression_expires(self, wired_handler, identity, registry):
        """
        The DELETE suppression window should expire, so a real DELETE
        much later is not suppressed.
        """
        path = f"{identity.folder_path}/module.py"
        # Manually set a very short suppression window for testing
        with wired_handler._lock:
            wired_handler._atomic_write_suppress[path] = time.time() - 1.0  # already expired

        wired_handler.on_deleted(FileDeletedEvent(path))
        assert registry.wait_for_event()
        assert registry.events[0].event_type == FileEventType.DELETED


# ---------------------------------------------------------------------------
# True renames
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.core
class TestTrueRenames:
    """A rename of one .py file to another .py file should emit DELETED + CREATED."""

    def test_rename_emits_deleted_and_created(self, wired_handler, identity, registry):
        """foo.py → bar.py should produce DELETED(foo) then CREATED(bar)."""
        base = identity.folder_path
        wired_handler.on_moved(FileMovedEvent(f"{base}/foo.py", f"{base}/bar.py"))
        assert registry.wait_for_n_events(2)
        types = [(e.file_path, e.event_type) for e in registry.events]
        assert (f"{base}/foo.py", FileEventType.DELETED) in types
        assert (f"{base}/bar.py", FileEventType.CREATED) in types


# ---------------------------------------------------------------------------
# Debounce coalescing
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.core
class TestDebounceCoalescing:
    """Rapid events for the same file should be coalesced by the debounce timer."""

    def test_rapid_modifications_coalesce(self, wired_handler, identity, registry):
        """Multiple rapid MODIFIEDs should produce only one dispatched event."""
        path = f"{identity.folder_path}/module.py"
        for _ in range(5):
            wired_handler.on_modified(FileModifiedEvent(path))
        assert registry.wait_for_event()
        # Wait a bit more to confirm no extra events
        time.sleep(0.15)
        assert len(registry.events) == 1
        assert registry.events[0].event_type == FileEventType.MODIFIED

    def test_create_then_modify_coalesces_to_latest(self, wired_handler, identity, registry):
        """A CREATE followed quickly by MODIFIED should coalesce to MODIFIED."""
        path = f"{identity.folder_path}/module.py"
        wired_handler.on_created(FileCreatedEvent(path))
        wired_handler.on_modified(FileModifiedEvent(path))
        assert registry.wait_for_event()
        time.sleep(0.15)
        assert len(registry.events) == 1
        assert registry.events[0].event_type == FileEventType.MODIFIED

    def test_modify_then_delete_coalesces_to_deleted(self, wired_handler, identity, registry):
        """A MODIFIED followed quickly by DELETED should coalesce to DELETED."""
        path = f"{identity.folder_path}/module.py"
        wired_handler.on_modified(FileModifiedEvent(path))
        wired_handler.on_deleted(FileDeletedEvent(path))
        assert registry.wait_for_event()
        time.sleep(0.15)
        assert len(registry.events) == 1
        assert registry.events[0].event_type == FileEventType.DELETED


# ---------------------------------------------------------------------------
# Multiple registries
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.core
class TestMultipleRegistries:
    """Events should be routed to all registries whose folder matches."""

    def test_event_routed_to_multiple_registries(self, handler, tmp_lib):
        """Two registries watching the same folder should both receive the event."""
        sub_dir = tmp_lib / "sub"
        sub_dir.mkdir()
        (sub_dir / "module.py").write_text("# sub module\n")

        identity = _make_identity(folder=str(tmp_lib))
        reg_a = RecordingRegistry()
        reg_b = RecordingRegistry()
        handler.add_folder_mapping(str(tmp_lib), identity, reg_a, debounce_delay=0.05)
        handler.add_folder_mapping(str(sub_dir), identity, reg_b, debounce_delay=0.05)

        handler.on_modified(FileModifiedEvent(f"{sub_dir}/module.py"))
        assert reg_a.wait_for_event()
        assert reg_b.wait_for_event()
        assert len(reg_a.events) == 1
        assert len(reg_b.events) == 1

    def test_event_only_routed_to_matching_registry(self, handler, tmp_path):
        """An event should only reach registries whose folder prefix matches."""
        lib_a = tmp_path / "lib_a"
        lib_b = tmp_path / "lib_b"
        lib_a.mkdir()
        lib_b.mkdir()
        (lib_a / "module.py").write_text("# a\n")
        (lib_b / "module.py").write_text("# b\n")

        id_a = _make_identity("LibA", str(lib_a))
        id_b = _make_identity("LibB", str(lib_b))
        reg_a = RecordingRegistry()
        reg_b = RecordingRegistry()
        handler.add_folder_mapping(str(lib_a), id_a, reg_a, debounce_delay=0.05)
        handler.add_folder_mapping(str(lib_b), id_b, reg_b, debounce_delay=0.05)

        handler.on_modified(FileModifiedEvent(f"{lib_a}/module.py"))
        assert reg_a.wait_for_event()
        time.sleep(0.1)
        assert len(reg_a.events) == 1
        assert len(reg_b.events) == 0


# ---------------------------------------------------------------------------
# Known-files tracking
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.core
class TestKnownFilesTracking:
    """Verify that _known_files is seeded and maintained correctly."""

    def test_existing_files_seeded_on_registration(self, handler, tmp_lib):
        """Pre-existing .py files should be in _known_files after add_folder_mapping."""
        identity = _make_identity(folder=str(tmp_lib))
        registry = RecordingRegistry()
        handler.add_folder_mapping(str(tmp_lib), identity, registry, debounce_delay=0.05)

        expected = str(tmp_lib / "existing.py")
        assert expected in handler._known_files

    def test_created_file_added_to_known(self, wired_handler, identity):
        """A CREATE event should add the file to _known_files."""
        path = f"{identity.folder_path}/brand_new.py"
        assert path not in wired_handler._known_files
        wired_handler.on_created(FileCreatedEvent(path))
        assert path in wired_handler._known_files

    def test_deleted_file_removed_from_known(self, wired_handler, identity):
        """A DELETE event should remove the file from _known_files."""
        path = f"{identity.folder_path}/existing.py"
        assert path in wired_handler._known_files
        wired_handler.on_deleted(FileDeletedEvent(path))
        assert path not in wired_handler._known_files

    def test_create_for_known_file_downgraded_to_modified(self, wired_handler, identity, registry):
        """A CREATE for a file already in _known_files should dispatch MODIFIED."""
        path = f"{identity.folder_path}/existing.py"
        assert path in wired_handler._known_files

        wired_handler.on_created(FileCreatedEvent(path))
        assert registry.wait_for_event()
        assert len(registry.events) == 1
        assert registry.events[0].event_type == FileEventType.MODIFIED

    def test_create_for_unknown_file_dispatches_created(self, wired_handler, identity, registry):
        """A CREATE for a genuinely new file should dispatch CREATED."""
        path = f"{identity.folder_path}/brand_new.py"
        assert path not in wired_handler._known_files

        wired_handler.on_created(FileCreatedEvent(path))
        assert registry.wait_for_event()
        assert len(registry.events) == 1
        assert registry.events[0].event_type == FileEventType.CREATED

    def test_delete_then_create_is_genuine_creation(self, wired_handler, identity, registry):
        """After a real DELETE, a subsequent CREATE for the same path is genuine."""
        path = f"{identity.folder_path}/existing.py"

        # Delete removes from known
        wired_handler.on_deleted(FileDeletedEvent(path))
        assert registry.wait_for_event()
        registry.clear()

        # Re-create — should be CREATED since the file was deleted
        wired_handler.on_created(FileCreatedEvent(path))
        assert registry.wait_for_event()
        assert registry.events[0].event_type == FileEventType.CREATED


# ---------------------------------------------------------------------------
# Atomic write race condition: CREATE before MOVE
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.core
class TestAtomicWriteRaceCondition:
    """
    Reproduce the race condition where the OS delivers events for an atomic
    write in the wrong order: CREATE for the destination arrives and is
    dispatched BEFORE the MOVE (tmp → .py) event arrives.

    In this scenario, the registry receives a CREATED event for a file that
    was merely overwritten — causing a duplicate registration error.

    The correct behaviour is: the registry should NEVER see a CREATED event
    for a file that is being atomically overwritten.  It should see MODIFIED.
    """

    def test_create_before_move_should_emit_modified(self, handler, identity):
        """
        Simulate the race: OS delivers CREATE for dest.py, then later the
        MOVE (tmp → dest.py).  The debounce should coalesce them so only
        MODIFIED reaches the registry.

        This test uses a longer debounce to ensure the MOVE arrives before
        the CREATE timer fires.
        """
        registry = RecordingRegistry()
        handler.add_folder_mapping(identity.folder_path, identity, registry, debounce_delay=0.2)
        base = identity.folder_path

        # Step 1: OS fires CREATE for the destination (the spurious event)
        handler.on_created(FileCreatedEvent(f"{base}/existing.py"))

        # Step 2: Shortly after, OS fires MOVE (tmp → .py) — the real event
        handler.on_moved(FileMovedEvent(f"{base}/existing.py.tmp.99999", f"{base}/existing.py"))

        assert registry.wait_for_event()
        time.sleep(0.3)
        assert len(registry.events) == 1, (
            f"Expected exactly 1 event, got {len(registry.events)}: "
            f"{[(e.event_type, e.file_path) for e in registry.events]}"
        )
        assert registry.events[0].event_type == FileEventType.MODIFIED, (
            f"Expected MODIFIED but got {registry.events[0].event_type} — "
            "the atomic write was misidentified as a new file creation"
        )

    def test_create_dispatched_before_move_arrives(
        self, handler: LibraryFileHandler, identity: LibraryIdentity
    ):
        """
        Simulate the worst-case race: the CREATE event's debounce timer
        fires and dispatches to the registry BEFORE the MOVE event arrives.
        This is the exact scenario that caused the duplicate registration
        error in production.

        With _known_files tracking, the CREATE for the pre-existing file
        is downgraded to MODIFIED, so the registry never sees CREATED.
        """
        registry = RecordingRegistry()
        handler.add_folder_mapping(identity.folder_path, identity, registry, debounce_delay=0.02)
        base = identity.folder_path

        # Step 1: OS fires CREATE for the destination (existing file)
        handler.on_created(FileCreatedEvent(f"{base}/existing.py"))

        # Step 2: Wait long enough for the CREATE debounce to fire
        time.sleep(0.08)

        # Step 3: MOVE arrives late
        handler.on_moved(FileMovedEvent(f"{base}/existing.py.tmp.99999", f"{base}/existing.py"))

        assert registry.wait_for_n_events(1)
        time.sleep(0.1)

        event_types = [e.event_type for e in registry.events]

        assert FileEventType.CREATED not in event_types, (
            f"Registry received CREATED event during atomic write — "
            f"_known_files should have downgraded it. Events: {event_types}"
        )
