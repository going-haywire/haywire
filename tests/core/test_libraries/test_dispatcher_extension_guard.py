"""The registry — not the router — decides that only Python modules reload.

`BaseRegistry.event_dispatcher` is offered every file under the folders it
claimed, so it guards itself. Two rejections that look alike are deliberately
kept apart:

  - a file that is not a Python module at all is dropped silently, above
    `resolve_module_name`. It is not a failure; nothing was ever going to
    reload.
  - a `.py` that will not parse *is* a failure — an author's broken save — and
    still surfaces as CLASS_RELOAD_FAILED in the error ledger.

Before the guard existed, the first case took the second case's path:
`ast.parse` threw on the TOML, `event_dispatcher`'s `except Exception` caught
it, and a fake reload failure reached subscribers.
"""

import time
from pathlib import Path
from typing import Optional, Type

import pytest

from haywire.core.library.identity import LibraryIdentity
from haywire.core.registry.base import (
    BaseRegistry,
    FileChangeEvent,
    FileEventType,
    LifeCycleEvent,
)


class _Registry(BaseRegistry):
    """A concrete registry that records what the dispatcher asked it to do."""

    def __init__(self) -> None:
        super().__init__()
        self.changed: list[str] = []
        self.created: list[str] = []
        self.deleted: list[str] = []

    def _class_filter(self, cls: Type) -> bool:  # pragma: no cover - never reached here
        return False

    def _register_class(self, cls, library_identity: Optional[LibraryIdentity] = None) -> str | None:
        return None  # pragma: no cover - never reached here

    def _unregister_class(self, registry_key: str):
        return None  # pragma: no cover - never reached here

    def _on_change(self, module_name, library_identity, event=None):
        self.changed.append(module_name)

    def _on_creation(self, module_name, library_identity, event=None):
        self.created.append(module_name)

    def _on_delete(self, module_name, library_identity):
        self.deleted.append(module_name)


def _identity(folder: Path) -> LibraryIdentity:
    return LibraryIdentity(
        id="demo",
        label="Demo",
        folder_path=str(folder),
        module_name="haybale_demo",
    )


def _event(path: Path, event_type: FileEventType, folder: Path) -> FileChangeEvent:
    return FileChangeEvent(
        file_path=str(path),
        event_type=event_type,
        library_identity=_identity(folder),
        timestamp=time.time(),
    )


@pytest.fixture
def registry() -> _Registry:
    return _Registry()


@pytest.fixture
def lifecycle_events(registry: _Registry) -> list[LifeCycleEvent]:
    """Everything the registry pushes to its batch subscribers."""
    seen: list[LifeCycleEvent] = []
    registry.add_batch_event_subscriber(lambda events: seen.extend(events))
    return seen


# ── a non-Python file is dropped, quietly ────────────────────────────────────


@pytest.mark.unit
@pytest.mark.core
def test_a_toml_modification_dispatches_nothing_and_reports_nothing(
    tmp_path: Path, registry: _Registry, lifecycle_events: list[LifeCycleEvent]
) -> None:
    """The regression: this used to manufacture a CLASS_RELOAD_FAILED."""
    toml = tmp_path / "haybale.toml"
    toml.write_text('id = "demo"\nlabel = "Demo"\n')

    result = registry.event_dispatcher(_event(toml, FileEventType.MODIFIED, tmp_path))

    assert result is None
    assert registry.changed == []
    assert registry.created == []
    assert lifecycle_events == [], "a non-Python file is not a reload failure"


@pytest.mark.unit
@pytest.mark.core
def test_a_toml_deletion_does_not_reach_on_delete(tmp_path: Path, registry: _Registry) -> None:
    """DELETED skips validation entirely, so a guard below resolve_module_name
    would let 'haybale.toml' unregister the module 'haybale_demo.haybale'."""
    registry.event_dispatcher(_event(tmp_path / "haybale.toml", FileEventType.DELETED, tmp_path))

    assert registry.deleted == []


@pytest.mark.unit
@pytest.mark.core
def test_a_py_file_reloads_even_with_a_same_stemmed_toml_sibling(
    tmp_path: Path, registry: _Registry
) -> None:
    """resolve_module_name strips the suffix, so 'nodes.toml' and 'nodes.py'
    both resolve to '…nodes'. Only the .py may travel that path."""
    (tmp_path / "nodes.toml").write_text("x = 1\n")
    py = tmp_path / "nodes.py"
    py.write_text("x = 1\n")

    registry.event_dispatcher(_event(tmp_path / "nodes.toml", FileEventType.MODIFIED, tmp_path))
    assert registry.changed == []
    assert registry.created == []

    registry.event_dispatcher(_event(py, FileEventType.MODIFIED, tmp_path))
    assert registry.created == ["haybale_demo.nodes"], "the .py must still reload normally"


# ── a broken .py is still a failure ──────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.core
def test_a_syntactically_broken_py_still_reports_a_reload_failure(
    tmp_path: Path, registry: _Registry, caplog
) -> None:
    """The author saved a half-written module. That is worth telling them about
    — unlike a .toml, which was never going to reload."""
    broken = tmp_path / "broken.py"
    broken.write_text("def oops(:\n")

    with caplog.at_level("ERROR"):
        registry.event_dispatcher(_event(broken, FileEventType.MODIFIED, tmp_path))

    assert registry.changed == []
    assert registry.created == []
    assert "FAILED" in caplog.text


# ── the validator decides, it does not raise ─────────────────────────────────


@pytest.mark.unit
@pytest.mark.core
def test_validate_python_file_returns_false_instead_of_raising(tmp_path: Path, registry: _Registry) -> None:
    toml = tmp_path / "haybale.toml"
    toml.write_text('id = "demo"\n')
    broken = tmp_path / "broken.py"
    broken.write_text("def oops(:\n")
    good = tmp_path / "good.py"
    good.write_text("x = 1\n")

    assert registry._validate_python_file(toml) is False
    assert registry._validate_python_file(broken) is False
    assert registry._validate_python_file(tmp_path / "missing.py") is False
    assert registry._validate_python_file(good) is True
