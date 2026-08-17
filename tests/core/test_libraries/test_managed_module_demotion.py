"""A component module must not be permanently demoted to a helper.

``_on_delete`` drops a module from the dependency graph and only ``_on_creation``
puts it back. Nothing else does — so a DELETE that was never a real deletion
latches the module as a "helper" for the life of the process: every later edit
takes ``_reload_unmanaged_module``, a bare ``importlib.reload`` that rebuilds the
class object but never re-registers it. The registry keeps handing out the old
class while the log reports ``Hot Reloading -> DONE``.

Spurious DELETEs are not hypothetical. An atomic write whose temp file lives in
the watched folder used to be read as a true rename (fixed in
``file_watcher.py``), and debounce keeps only the last event per path — so a
save pair ending on the delete leaves nothing to re-create the module.

These tests pin the recovery, so the latch cannot come back by another route.
"""

import time
from pathlib import Path

import pytest

from haywire.core.library.identity import LibraryIdentity
from haywire.core.registry.base import FileChangeEvent, FileEventType
from haywire.ui.editor.registry import EditorTypeRegistry

MODULE = "haybale_demo.editors.demo_editor"
# No Library class in the temp package, so @editor derives the '__system__'
# fallback identity. Which library owns the class is irrelevant here — the
# subject is whether the module keeps its *managed* status across a delete.
REGISTRY_KEY = "__system__:editor:DemoEditor"

_EDITOR_SOURCE = """
from haywire.ui.editor.base import BaseEditor
from haywire.ui.editor.decorator import editor


@editor(label="Demo", registry_id="DemoEditor")
class DemoEditor(BaseEditor):
    def draw(self, context, container) -> None:
        pass

    MARKER = "{marker}"
"""


@pytest.fixture
def library(tmp_path, monkeypatch):
    """A minimal importable library with one editor, registered from disk."""
    root = tmp_path / "haybale_demo"
    (root / "editors").mkdir(parents=True)
    (root / "__init__.py").write_text("")
    (root / "editors" / "__init__.py").write_text("")
    (root / "editors" / "demo_editor.py").write_text(_EDITOR_SOURCE.format(marker="original"))

    monkeypatch.syspath_prepend(str(tmp_path))
    for name in [m for m in list(__import__("sys").modules) if m.startswith("haybale_demo")]:
        del __import__("sys").modules[name]

    identity = LibraryIdentity(
        name="demo",
        label="Demo",
        folder_path=str(root),
        module_name="haybale_demo",
    )
    return root, identity


@pytest.fixture
def registry(library):
    root, identity = library
    reg = EditorTypeRegistry()
    reg.add_folder(str(root / "editors"), identity)
    return reg


def _event(path: Path, event_type: FileEventType, identity: LibraryIdentity) -> FileChangeEvent:
    return FileChangeEvent(
        file_path=str(path),
        event_type=event_type,
        library_identity=identity,
        timestamp=time.time(),
    )


@pytest.mark.unit
@pytest.mark.core
def test_scan_registers_the_module_as_managed(registry, library):
    root, _ = library
    assert MODULE in registry._dependency_graph._managed_modules
    assert registry.get(REGISTRY_KEY) is not None


@pytest.mark.unit
@pytest.mark.core
def test_modify_after_a_spurious_delete_re_registers_the_class(registry, library):
    """The regression: DELETE then MODIFY used to leave the class unregistered.

    The file is still on disk throughout — nothing was ever really deleted.
    """
    root, identity = library
    source = root / "editors" / "demo_editor.py"

    registry.event_dispatcher(_event(source, FileEventType.DELETED, identity))
    assert MODULE not in registry._dependency_graph._managed_modules
    assert registry.get(REGISTRY_KEY) is None

    source.write_text(_EDITOR_SOURCE.format(marker="edited"))
    registry.event_dispatcher(_event(source, FileEventType.MODIFIED, identity))

    assert MODULE in registry._dependency_graph._managed_modules, "must be managed again"
    cls = registry.get(REGISTRY_KEY)
    assert cls is not None, "the class must be registered again"
    assert cls.MARKER == "edited", "the registry must hold the *edited* class"


@pytest.mark.unit
@pytest.mark.core
def test_edits_keep_landing_after_the_recovery(registry, library):
    """Recovery must be durable, not a one-shot that re-latches on the next save."""
    root, identity = library
    source = root / "editors" / "demo_editor.py"

    registry.event_dispatcher(_event(source, FileEventType.DELETED, identity))
    source.write_text(_EDITOR_SOURCE.format(marker="first"))
    registry.event_dispatcher(_event(source, FileEventType.MODIFIED, identity))

    source.write_text(_EDITOR_SOURCE.format(marker="second"))
    registry.event_dispatcher(_event(source, FileEventType.MODIFIED, identity))

    assert registry.get(REGISTRY_KEY).MARKER == "second"


@pytest.mark.unit
@pytest.mark.core
def test_a_real_deletion_still_unregisters(registry, library):
    """The repair keys on the file existing, so a true delete must still remove."""
    root, identity = library
    source = root / "editors" / "demo_editor.py"
    source.unlink()

    registry.event_dispatcher(_event(source, FileEventType.DELETED, identity))

    assert registry.get(REGISTRY_KEY) is None
    assert MODULE not in registry._dependency_graph._managed_modules


@pytest.mark.unit
@pytest.mark.core
def test_a_genuine_helper_is_not_promoted(registry, library):
    """A module this registry never claimed keeps taking the helper path."""
    root, identity = library
    helper = root / "helpers.py"
    helper.write_text("VALUE = 1\n")

    assert registry._is_demoted_component("haybale_demo.helpers", str(helper)) is False
