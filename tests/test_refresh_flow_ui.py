"""The refresh flow's state machine. UI rendering is smoke-tested only.

The property worth testing here is the one the flow exists for: the project
cache is not written until the final step, so a user who reads the fetch
result and closes the popup changes nothing.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from haywire.core.marketstall import RefreshReport
from haywire.core.marketstall import cache as marketstall_cache

pytestmark = pytest.mark.unit

_STALL_URL = "https://alice.example/marketstall.toml"
_BODY = '[[haybales]]\nname = "haybale-foo"\nversion = "0.1.0"\n'


@pytest.fixture
def anyio_backend() -> str:
    """anyio's backend parametrization. The repo runs asyncio only."""
    return "asyncio"


class _FakeState:
    """Stands in for MarketplaceState: real pipeline, test-owned paths.

    Building a real MarketplaceState would drag in DI and the workspace root;
    the flow only needs the four methods below, so this keeps the state
    machine under test rather than the state class.
    """

    def __init__(self, root: Path) -> None:
        self.global_path = root / "global.toml"
        self.global_path.write_text(
            f'[[stalls]]\nurl = "{_STALL_URL}"\nignores = []\ndoubles = []\nblocked = []\n'
        )
        self.project_path = root / "project.toml"
        self.cache_dir = root / "cache"
        self.last_report: RefreshReport | None = None

    def get_global(self):
        from haywire.core.marketstall import parse_global_marketplace

        return parse_global_marketplace(self.global_path)

    def fetch_sources(self):
        from haywire.core.marketstall import fetch_sources

        return fetch_sources(
            global_path=self.global_path,
            project_path=self.project_path,
            cache_dir=self.cache_dir,
        )

    def resolve(self, fetched):
        from haywire.core.marketstall import resolve_catalog

        return resolve_catalog(fetched)

    def apply_refresh(self, fetched, resolved):
        from haywire.core.marketstall import apply_refresh

        report = apply_refresh(fetched, resolved, project_path=self.project_path, cache_dir=self.cache_dir)
        self.last_report = report
        return report


def _flow(root: Path):
    """A RefreshFlow with no popup — the state machine under test."""
    from haybale_marketplace.editors._refresh_flow import RefreshFlow

    return RefreshFlow(state=_FakeState(root))


def _reachable():
    """Patch the fetch layer so the stall URL returns _BODY."""
    mock = patch.object(marketstall_cache, "_urlopen")
    handle = mock.start()
    handle.return_value.__enter__.return_value.read.return_value = _BODY.encode()
    return mock


@pytest.mark.anyio
async def test_fetch_advances_without_writing(tmp_path: Path) -> None:
    flow = _flow(tmp_path)
    mock = _reachable()
    try:
        await flow.advance_from_sources()
    finally:
        mock.stop()

    assert flow.step == "fetched"
    assert flow.error is None
    assert flow.fetched is not None
    assert not flow.state.project_path.exists()


@pytest.mark.anyio
async def test_resolve_advances_without_writing(tmp_path: Path) -> None:
    flow = _flow(tmp_path)
    mock = _reachable()
    try:
        await flow.advance_from_sources()
    finally:
        mock.stop()
    await flow.advance_from_fetched()

    assert flow.step == "resolved"
    assert flow.resolved is not None
    assert flow.resolved.newly_added == ["haybale-foo"]
    assert not flow.state.project_path.exists()


@pytest.mark.anyio
async def test_apply_is_the_only_step_that_writes(tmp_path: Path) -> None:
    flow = _flow(tmp_path)
    mock = _reachable()
    try:
        await flow.advance_from_sources()
    finally:
        mock.stop()
    await flow.advance_from_fetched()
    assert not flow.state.project_path.exists()

    await flow.advance_from_resolved()

    assert flow.step == "applied"
    assert flow.state.project_path.exists()
    assert flow.report is not None
    assert flow.report.haybales_resolved == 1


@pytest.mark.anyio
async def test_abandoning_after_fetch_leaves_cache_untouched(tmp_path: Path) -> None:
    """The whole point of the split: read, decide, walk away with no damage."""
    flow = _flow(tmp_path)
    flow.state.project_path.write_text('[[caches]]\nname = "haybale-old"\nversion = "0.1.0"\n')
    before = flow.state.project_path.read_text()

    mock = _reachable()
    try:
        await flow.advance_from_sources()
    finally:
        mock.stop()
    await flow.advance_from_fetched()

    assert flow.state.project_path.read_text() == before


@pytest.mark.anyio
async def test_unreachable_source_reports_without_failing(tmp_path: Path) -> None:
    """An unreachable source is information, not an error — the flow advances."""
    flow = _flow(tmp_path)
    with patch.object(marketstall_cache, "_urlopen", side_effect=OSError):
        await flow.advance_from_sources()

    assert flow.step == "fetched"
    assert flow.error is None
    assert flow.fetched is not None
    assert flow.fetched.unavailable_urls == [_STALL_URL]


@pytest.mark.anyio
async def test_malformed_global_file_stays_on_step_and_flags_repair(tmp_path: Path) -> None:
    flow = _flow(tmp_path)
    flow.state.global_path.write_text("[[stalls]\nbroken")

    await flow.advance_from_sources()

    assert flow.step == "sources"
    assert flow.error is not None
    assert flow.malformed is True


@pytest.mark.anyio
async def test_retry_clears_the_malformed_flag(tmp_path: Path) -> None:
    flow = _flow(tmp_path)
    flow.state.global_path.write_text("[[stalls]\nbroken")
    await flow.advance_from_sources()
    assert flow.malformed is True

    flow.retry()

    assert flow.error is None
    assert flow.malformed is False


@pytest.mark.anyio
async def test_newly_stale_surfaces_as_a_warning(tmp_path: Path) -> None:
    flow = _flow(tmp_path)
    flow.state.project_path.write_text('[[caches]]\nname = "haybale-gone"\nversion = "0.1.0"\n')

    mock = _reachable()
    try:
        await flow.advance_from_sources()
    finally:
        mock.stop()
    await flow.advance_from_fetched()

    assert flow.resolved is not None
    assert flow.resolved.newly_stale == ["haybale-gone"]

    await flow.advance_from_resolved()

    assert any("stale" in w for w in flow.warnings)


@pytest.mark.anyio
async def test_no_project_path_reports_instead_of_advancing(tmp_path: Path) -> None:
    """A workspace-less session gets a message, not a traceback."""
    flow = _flow(tmp_path)
    flow.state.fetch_sources = lambda: None  # type: ignore[method-assign]

    await flow.advance_from_sources()

    assert flow.step == "sources"
    assert flow.error is not None
    assert "No project open" in flow.error


def test_steps_cover_every_panel() -> None:
    """A step with no panel raises at open time, so keep the two in lockstep."""
    from haybale_marketplace.editors._refresh_flow import STEPS
    from haybale_marketplace.editors._refresh_flow.copy import STEP_TITLES

    assert set(STEPS) == set(STEP_TITLES)
    assert STEPS.index("sources") < STEPS.index("fetched") < STEPS.index("resolved")
