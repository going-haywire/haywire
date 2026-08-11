"""The library detail page renders from one row, whatever the install state.

Guards the bug D9/D12 exist to fix: a project-local library (installed, but with
no catalogue row) rendered no links at all, and only the installed path rendered
authors. Both now read ``info.row``.

The editor is driven with stub services — the branches under test (metadata,
links, authors) never touch a registry, and every registry lookup degrades to
"no components", so no library system is needed.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
from nicegui import ui
from nicegui.testing import User
from nicegui.testing.user_simulation import user_simulation

from haywire.core.library.identity import LibraryIdentity
from haywire.core.library.info import LibraryInfo
from haywire.core.library.install_type import InstallType
from haywire.core.library.haybale import Haybale


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def user() -> AsyncGenerator[User, None]:
    async with user_simulation() as u:
        yield u


class _StubService:
    """Every ``get_*_registry()`` yields None — the editor treats that as empty."""

    def __getattr__(self, _name):
        return lambda: None


class _StubApp:
    def __init__(self, workspace_root: str) -> None:
        self.workspace_root = workspace_root
        self.library_service = _StubService()


class _StubManager:
    def get_installed_dependents(self, _lib_id):
        return []

    def get_missing_dependencies(self, _lib_id, require_enabled: bool = False):
        return []

    def get_missing_dependencies_for_package(self, _pkg, require_enabled: bool = False):
        return []


class _StubManagerState:
    manager = _StubManager()


class _StubContext:
    """The four attributes ``_rebuild``/``_render_center`` actually read."""

    def __init__(self, workspace_root: str, active_library: LibraryInfo | None) -> None:
        from haybale_marketplace.state.library_manager_state import LibraryManagerState

        self.app = _StubApp(workspace_root)
        self.app_data = {LibraryManagerState: _StubManagerState()}
        self.active_library = active_library


def _row(**kwargs) -> Haybale:
    base: dict = dict(
        name="haybale-x",
        version="1.0.0",
        label="Ex",
        description="An example",
        origin="https://github.test/o/r",
        documentation_url="https://docs.test",
        issues_url="https://issues.test",
        authors=[("Alice", "https://alice.test"), ("Bob", "")],
    )
    base.update(kwargs)
    return Haybale(**base)


def _installed(tmp_path) -> LibraryInfo:
    """An installed, project-local library — the case with no catalogue row."""
    folder = tmp_path / "barn" / "haybale-x" / "haybale_x"
    folder.mkdir(parents=True, exist_ok=True)
    return LibraryInfo(
        row=_row(source="local"),
        identity=LibraryIdentity(id="x", label="Ex", version="1.0.0", folder_path=str(folder)),
        enabled=True,
        install_type=InstallType.REGULAR,
    )


async def _render(user: User, info: LibraryInfo, workspace_root) -> None:
    from haybale_marketplace.editors.library_overview_editor import LibraryOverviewEditor

    editor = LibraryOverviewEditor(wrapper=None)  # type: ignore[arg-type]
    context = _StubContext(str(workspace_root), info)

    @ui.page("/")
    def page() -> None:
        editor.draw(context, ui.column())  # type: ignore[arg-type]

    await user.open("/")


@pytest.mark.unit
@pytest.mark.anyio
async def test_installed_project_local_library_renders_its_links(user: User, tmp_path) -> None:
    """The bug: installed + no catalogue row used to render zero links."""
    await _render(user, _installed(tmp_path), tmp_path)

    await user.should_see("Source")
    await user.should_see("Documentation")
    await user.should_see("Issues")


@pytest.mark.unit
@pytest.mark.anyio
async def test_installed_library_renders_every_author(user: User, tmp_path) -> None:
    await _render(user, _installed(tmp_path), tmp_path)

    await user.should_see("Alice")
    await user.should_see("Bob")


@pytest.mark.unit
@pytest.mark.anyio
async def test_not_installed_catalogue_row_renders_authors_and_links(user: User, tmp_path) -> None:
    """The mirror bug: a catalogue-only entry rendered no author and no homepage."""
    from haybale_marketplace.library_manager import LibraryManager

    await _render(user, LibraryManager.entry_for_haybale(_row()), tmp_path)

    await user.should_see("Alice")
    await user.should_see("Bob")
    await user.should_see("Source")
    await user.should_see("Documentation")
    await user.should_see("Issues")
