"""E2E: FileViewer is opens='on_payload'; one tab per file; re-clicking dedupes."""

import pytest

from haybale_studio.editors.file_viewer import FileViewerEditor
from haywire.ui.editor.identity import OpenBehavior


@pytest.mark.unit
def test_file_viewer_declares_on_payload():
    assert FileViewerEditor.class_identity.opens is OpenBehavior.ON_PAYLOAD


@pytest.mark.unit
def test_file_viewer_reads_payload_from_binding(tmp_path):
    """FileViewerEditor.draw must render the file indicated by binding.payload,
    not context.active_file."""
    path = tmp_path / "hello.txt"
    path.write_text("hello world")

    viewer = FileViewerEditor()

    # Simulate wrapper attachment the way EditorWrapper._instantiate does.
    class _FakeWrapper:
        editor_key = FileViewerEditor.class_identity.registry_key
        payload = str(path)

    viewer.wrapper = _FakeWrapper()

    # Assert the helper that resolves the path from the binding:
    assert viewer._resolve_path() == path


@pytest.mark.unit
def test_file_browser_reveal_includes_payload(tmp_path):
    """FileBrowser._open_in_file_viewer must supply reveal_payload=<path>."""
    from haybale_studio.editors.file_browser import FileBrowserEditor

    browser = FileBrowserEditor()
    path = tmp_path / "a.txt"
    path.write_text("x")

    captured = []

    class _FakeSession:
        def notify_context_changed(self, event):
            captured.append(event)

    class _FakeContext:
        session = _FakeSession()
        active_file = None

    browser._open_in_file_viewer(path, _FakeContext())

    assert len(captured) == 1
    event = captured[0]
    assert event.reveal_editor == FileViewerEditor.class_identity.registry_key
    assert event.reveal_payload == str(path)
    assert event.reveal_label == path.name
