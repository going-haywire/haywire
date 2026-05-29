"""Tests for MarketplaceState (Plan E Phase 3 Task 25)."""

from __future__ import annotations

import pytest


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    """Sandbox ~/.haywire/ to a tmp dir."""
    fake = tmp_path / "fake-home"
    fake.mkdir()
    monkeypatch.setenv("HOME", str(fake))
    monkeypatch.setattr("pathlib.Path.home", lambda: fake)
    return fake


@pytest.fixture
def state_with_workspace(tmp_path, fake_home, monkeypatch):
    """Construct a MarketplaceState and run on_enable with a sandboxed workspace_root."""
    from haybale_marketplace.state.marketplace_state import MarketplaceState

    workspace = tmp_path / "project"
    (workspace / ".haywire").mkdir(parents=True)

    state = MarketplaceState()
    # Patch the DI helper inside on_enable so the test doesn't need a real injector.
    monkeypatch.setattr(
        "haywire.core.di.context.get_workspace_root",
        lambda: workspace,
    )
    state.on_enable()
    return state, workspace


@pytest.mark.unit
def test_marketplace_state_is_an_app_state() -> None:
    """MarketplaceState extends AppState and carries the @state(label=...) decorator."""
    from haywire.core.state.base import AppState
    from haybale_marketplace.state.marketplace_state import MarketplaceState

    assert issubclass(MarketplaceState, AppState)
    # @state(...) attaches class_identity (set by LibraryStateRegistry at scan time;
    # we don't depend on that here — just verify the class is constructible).
    state = MarketplaceState()
    assert state is not None


@pytest.mark.unit
def test_on_enable_resolves_workspace_root(state_with_workspace) -> None:
    state, workspace = state_with_workspace
    # Internal storage — accessing via the property below would be cleaner;
    # for Task 25 just verify on_enable wired up.
    assert state._workspace_root == workspace


@pytest.mark.unit
def test_get_project_haybales_returns_empty_when_no_cache(state_with_workspace) -> None:
    """Fresh project with no refresh yet → empty haybale list."""
    state, _ = state_with_workspace
    pkgs = state.get_project_haybales()
    assert pkgs == []


@pytest.mark.unit
def test_get_project_haybales_reads_existing_cache(state_with_workspace) -> None:
    state, workspace = state_with_workspace
    # Write a project marketplace with one cache entry.
    mp = workspace / ".haywire" / "marketplace.toml"
    mp.write_text(
        "[[caches]]\n"
        'name = "haybale-from-cache"\n'
        'min_version = "0.0.1"\n'
        'source = "git"\n'
        'install_spec = "haybale-from-cache @ git+https://x.example/r.git"\n'
    )
    pkgs = state.get_project_haybales()
    assert len(pkgs) == 1
    assert pkgs[0].name == "haybale-from-cache"


@pytest.mark.unit
def test_get_global_returns_parsed(state_with_workspace, fake_home) -> None:
    """get_global parses ~/.haywire/db/haybale-marketplace/marketplace.toml via marketstall."""
    state, _ = state_with_workspace
    global_mp = fake_home / ".haywire" / "db" / "haybale-marketplace" / "marketplace.toml"
    global_mp.parent.mkdir(parents=True, exist_ok=True)
    global_mp.write_text(
        "[[markets]]\n"
        'url = "https://going-haywire.github.io/haywire/marketplace.toml"\n'
        "ignores = []\n"
        "doubles = []\n"
    )
    gm = state.get_global()
    assert gm is not None
    assert len(gm.markets) == 1


@pytest.mark.unit
def test_get_global_returns_none_on_malformed(state_with_workspace, fake_home) -> None:
    """When ~/.haywire/db/haybale-marketplace/marketplace.toml is malformed, get_global returns None
    and global_marketplace_error is set to the error message."""
    state, _ = state_with_workspace
    global_mp = fake_home / ".haywire" / "db" / "haybale-marketplace" / "marketplace.toml"
    global_mp.parent.mkdir(parents=True, exist_ok=True)
    global_mp.write_text('this is = "not valid toml')

    gm = state.get_global()
    assert gm is None
    assert state.global_marketplace_error is not None
    assert "marketplace.toml" in state.global_marketplace_error


@pytest.mark.unit
def test_refresh_invokes_runtime_refresh(state_with_workspace, fake_home, monkeypatch) -> None:
    """refresh() delegates to marketstall.refresh and caches the report."""
    state, workspace = state_with_workspace

    # Set up a stall subscription in the global marketplace.
    global_mp = fake_home / ".haywire" / "db" / "haybale-marketplace" / "marketplace.toml"
    global_mp.parent.mkdir(parents=True, exist_ok=True)
    global_mp.write_text('[[stalls]]\nurl = "https://author.example/m.toml"\n')

    # Mock urlopen for the marketstall fetch.
    class _Resp:
        def __init__(self, content: bytes) -> None:
            self._content = content

        def read(self) -> bytes:
            return self._content

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def _fake_urlopen(url, *args, **kwargs):
        if hasattr(url, "full_url"):
            url = url.full_url
        if url == "https://author.example/m.toml":
            return _Resp(b'[[haybales]]\nname = "haybale-from-author"\nmin_version = "0.0.1"\n')
        raise OSError(f"unmocked URL: {url}")

    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen)

    report = state.refresh()
    assert report.sources_fetched == 1
    assert state.last_report is report

    # Project marketplace was written with the resolved haybale.
    pkgs = state.get_project_haybales()
    names = [p.name for p in pkgs]
    assert "haybale-from-author" in names
