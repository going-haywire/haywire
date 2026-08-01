"""The Share Project entry point lives on the repo-scoped burger menu."""

import inspect
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


def test_share_menu_item_is_on_the_library_browser() -> None:
    """Not on LibraryOverviewEditor: the unit of sharing is the PROJECT, and the
    other repo-scoped actions (Refresh, Add Source, Edit File) live here (ADR 0023)."""
    from haybale_marketplace.editors.library_browser_editor import LibraryBrowserEditor

    source = inspect.getsource(LibraryBrowserEditor._build_ui)
    assert "Share Project" in source
    assert "_on_share_project_click" in source


def test_overview_editor_has_no_share_button() -> None:
    """A per-library Share button would misrepresent a project-scoped, lockstep action."""
    overview = Path(
        "barn/haybale-marketplace/haybale_marketplace/editors/library_overview_editor.py"
    ).read_text()
    assert "show_share_wizard" not in overview
    assert "Share Project" not in overview


def test_handler_exists_and_takes_context() -> None:
    from haybale_marketplace.editors.library_browser_editor import LibraryBrowserEditor

    sig = inspect.signature(LibraryBrowserEditor._on_share_project_click)
    assert list(sig.parameters) == ["self", "context"]


def test_handler_notifies_when_no_workspace_root(monkeypatch) -> None:
    """A studio started outside a project has nothing to share; say so instead
    of opening a wizard that fails at step 1 for a confusing reason."""
    from haybale_marketplace.editors import _share_wizard
    from haybale_marketplace.editors import library_browser_editor as mod

    notifications: list[tuple[str, str]] = []
    monkeypatch.setattr(mod.ui, "notify", lambda msg, **kw: notifications.append((msg, kw.get("type", ""))))
    opened: list[Path] = []
    monkeypatch.setattr(_share_wizard, "show_share_wizard", lambda root, **kw: opened.append(root))

    editor = mod.LibraryBrowserEditor.__new__(mod.LibraryBrowserEditor)
    context = type("Ctx", (), {"app": type("App", (), {"workspace_root": None})()})()
    editor._on_share_project_click(context)

    assert opened == []
    assert notifications
    assert "project" in notifications[0][0].lower()


def test_handler_opens_the_wizard_at_the_workspace_root(monkeypatch, tmp_path: Path) -> None:
    from haybale_marketplace.editors import _share_wizard
    from haybale_marketplace.editors import library_browser_editor as mod

    opened: list[Path] = []
    monkeypatch.setattr(_share_wizard, "show_share_wizard", lambda root, **kw: opened.append(Path(root)))
    monkeypatch.setattr(mod.ui, "notify", lambda *a, **kw: None)

    editor = mod.LibraryBrowserEditor.__new__(mod.LibraryBrowserEditor)
    context = type("Ctx", (), {"app": type("App", (), {"workspace_root": str(tmp_path)})()})()
    editor._on_share_project_click(context)

    assert opened == [tmp_path]
