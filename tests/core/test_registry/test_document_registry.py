"""``DocumentRegistry`` maps file events onto the component lifecycle."""

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


def _identity(folder_path="/lib"):
    from haywire.core.library.identity import LibraryIdentity

    return LibraryIdentity(label="testlib", name="testlib", folder_path=folder_path, module_name="testlib")


class _Doc:
    """A parsed document satisfying RegisteredClass."""

    def __init__(self, registry_key, text):
        from haywire.core.registry.identity import BaseIdentity

        self._identity = BaseIdentity(
            registry_id=registry_key.split(":")[-1],
            registry_key=registry_key,
            label=registry_key.split(":")[-1],
        )
        self._library = _identity()
        self.text = text

    @property
    def class_identity(self):
        return self._identity

    @property
    def class_library(self):
        return self._library


def _registry(fail_on: str = ""):
    """A DocumentRegistry over '.txt' that parses into _Doc."""
    from haywire.core.registry.document import DocumentRegistry

    class _Fake(DocumentRegistry):
        SUFFIX = ".txt"

        def _parse(self, path: Path, text: str, library_identity):
            if fail_on and fail_on in text:
                raise ValueError("bad document")
            return _Doc(self._document_key(path, library_identity), text)

        def _document_key(self, path: Path, library_identity):
            return f"{library_identity.name}:doc:{path.stem}"

    return _Fake()


def _event(path, kind, identity=None):
    from haywire.core.registry.events import FileChangeEvent

    return FileChangeEvent(
        file_path=str(path),
        event_type=kind,
        library_identity=identity or _identity(),
        timestamp=0.0,
    )


def test_a_created_file_registers_and_emits_added(tmp_path):
    from haywire.core.registry.events import FileEventType
    from haywire.core.registry.lifecycle_event import LifeCycleEventType

    doc = tmp_path / "alpha.txt"
    doc.write_text("hello")
    reg = _registry()
    batches = []
    reg.add_batch_event_subscriber(lambda b: batches.append(list(b)))

    reg.event_dispatcher(_event(doc, FileEventType.CREATED, _identity(str(tmp_path))))

    assert reg.has("testlib:doc:alpha")
    assert [e.event_type for e in batches[-1]] == [LifeCycleEventType.CLASS_ADDED]


def test_a_file_of_another_suffix_is_ignored(tmp_path):
    from haywire.core.registry.events import FileEventType

    other = tmp_path / "notes.md"
    other.write_text("hello")
    reg = _registry()

    reg.event_dispatcher(_event(other, FileEventType.CREATED, _identity(str(tmp_path))))

    assert reg.list_names() == []


def test_unchanged_content_on_modify_emits_nothing(tmp_path):
    from haywire.core.registry.events import FileEventType

    doc = tmp_path / "alpha.txt"
    doc.write_text("hello")
    identity = _identity(str(tmp_path))
    reg = _registry()
    reg.event_dispatcher(_event(doc, FileEventType.CREATED, identity))

    batches = []
    reg.add_batch_event_subscriber(lambda b: batches.append(list(b)))
    reg.event_dispatcher(_event(doc, FileEventType.MODIFIED, identity))

    assert batches == [] or batches[-1] == []


def test_changed_content_on_modify_emits_reloaded(tmp_path):
    from haywire.core.registry.events import FileEventType
    from haywire.core.registry.lifecycle_event import LifeCycleEventType

    doc = tmp_path / "alpha.txt"
    doc.write_text("hello")
    identity = _identity(str(tmp_path))
    reg = _registry()
    reg.event_dispatcher(_event(doc, FileEventType.CREATED, identity))

    doc.write_text("goodbye")
    batches = []
    reg.add_batch_event_subscriber(lambda b: batches.append(list(b)))
    reg.event_dispatcher(_event(doc, FileEventType.MODIFIED, identity))

    assert [e.event_type for e in batches[-1]] == [LifeCycleEventType.CLASS_RELOADED]


def test_a_deleted_file_unregisters_and_emits_removed(tmp_path):
    from haywire.core.registry.events import FileEventType
    from haywire.core.registry.lifecycle_event import LifeCycleEventType

    doc = tmp_path / "alpha.txt"
    doc.write_text("hello")
    identity = _identity(str(tmp_path))
    reg = _registry()
    reg.event_dispatcher(_event(doc, FileEventType.CREATED, identity))

    doc.unlink()
    batches = []
    reg.add_batch_event_subscriber(lambda b: batches.append(list(b)))
    reg.event_dispatcher(_event(doc, FileEventType.DELETED, identity))

    assert not reg.has("testlib:doc:alpha")
    assert [e.event_type for e in batches[-1]] == [LifeCycleEventType.CLASS_REMOVED]


def test_a_parse_failure_keeps_the_key_and_emits_reload_failed(tmp_path):
    """A broken save must not silently drop the component."""
    from haywire.core.registry.events import FileEventType
    from haywire.core.registry.lifecycle_event import LifeCycleEventType

    doc = tmp_path / "alpha.txt"
    doc.write_text("good")
    identity = _identity(str(tmp_path))
    reg = _registry(fail_on="BROKEN")
    reg.event_dispatcher(_event(doc, FileEventType.CREATED, identity))

    doc.write_text("BROKEN")
    batches = []
    reg.add_batch_event_subscriber(lambda b: batches.append(list(b)))
    reg.event_dispatcher(_event(doc, FileEventType.MODIFIED, identity))

    assert reg.has("testlib:doc:alpha"), "the previous good document stays registered"
    assert [e.event_type for e in batches[-1]] == [LifeCycleEventType.CLASS_RELOAD_FAILED]
    assert batches[-1][0].error is not None


def test_add_folder_registers_every_matching_file(tmp_path):
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "b.txt").write_text("b")
    (tmp_path / "c.md").write_text("c")
    reg = _registry()

    reg.add_folder(str(tmp_path), _identity(str(tmp_path)))

    assert set(reg.list_names()) == {"testlib:doc:a", "testlib:doc:b"}


def test_remove_folder_unregisters_them_again(tmp_path):
    (tmp_path / "a.txt").write_text("a")
    identity = _identity(str(tmp_path))
    reg = _registry()
    reg.add_folder(str(tmp_path), identity)

    reg.remove_folder(str(tmp_path), identity)

    assert reg.list_names() == []
