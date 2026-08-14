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
        self.global_path.write_text(f'[[stalls]]\nurl = "{_STALL_URL}"\npreference = []\nblocked = []\n')
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

    def prefer_source(self, name: str, *, source_url: str) -> None:
        from haywire.core.marketstall import record_preference

        record_preference(self.global_path, source_url=source_url, haybale_name=name)


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


# ---------------------------------------------------------------------------
# Standing collisions — surfaced on the resolved step, resolvable in place
# ---------------------------------------------------------------------------

_URL_A = "https://a.example/marketstall.toml"
_URL_B = "https://b.example/marketstall.toml"


class _CollidingState(_FakeState):
    """Two stalls, both offering haybale-foo at different versions."""

    def __init__(self, root: Path) -> None:
        super().__init__(root)
        self.global_path.write_text(
            f'[[stalls]]\nurl = "{_URL_A}"\npreference = []\nblocked = []\n'
            "\n"
            f'[[stalls]]\nurl = "{_URL_B}"\npreference = []\nblocked = []\n'
        )


def _colliding_flow(root: Path):
    from haybale_marketplace.editors._refresh_flow import RefreshFlow

    return RefreshFlow(state=_CollidingState(root))


def _collision_reachable():
    """Both stalls reachable; A serves 2.1.0, B serves 2.3.0."""

    def fake_urlopen(url, *, timeout):
        from unittest.mock import MagicMock

        m = MagicMock()
        version = "2.1.0" if url == _URL_A else "2.3.0"
        body = f'[[haybales]]\nname = "haybale-foo"\nversion = "{version}"\n'
        m.__enter__.return_value.read.return_value = body.encode()
        return m

    mock = patch.object(marketstall_cache, "_urlopen", side_effect=fake_urlopen)
    mock.start()
    return mock


@pytest.mark.anyio
async def test_collision_is_visible_before_the_write(tmp_path: Path) -> None:
    """The whole point: the user sees the version choice before Apply, not after."""
    flow = _colliding_flow(tmp_path)
    mock = _collision_reachable()
    try:
        await flow.advance_from_sources()
        await flow.advance_from_fetched()
    finally:
        mock.stop()

    assert flow.step == "resolved"
    assert flow.resolved is not None
    assert len(flow.resolved.collisions) == 1
    collision = flow.resolved.collisions[0]
    assert collision.name == "haybale-foo"
    assert collision.winner_url == _URL_A
    assert collision.losers == [(_URL_B, "2.3.0")]
    assert not flow.state.project_path.exists()  # still nothing written


@pytest.mark.anyio
async def test_preferring_the_other_source_flips_the_winner_in_place(tmp_path: Path) -> None:
    """ "Use this one" re-resolves and stays on the step — no write, new winner."""
    flow = _colliding_flow(tmp_path)
    mock = _collision_reachable()
    try:
        await flow.advance_from_sources()
        await flow.advance_from_fetched()
        assert flow.resolved is not None
        assert flow.resolved.haybales[0].version == "2.1.0"

        flow.prefer_source("haybale-foo", source_url=_URL_B)
    finally:
        mock.stop()

    assert flow.step == "resolved"  # still pre-write
    assert flow.error is None
    assert flow.resolved is not None
    assert flow.resolved.haybales[0].version == "2.3.0"  # B now wins
    # The collision is settled, not hidden: A is still listed as an option.
    assert flow.resolved.collisions[0].winner_url == _URL_B
    assert flow.resolved.collisions[0].losers == [(_URL_A, "2.1.0")]
    assert not flow.state.project_path.exists()


@pytest.mark.anyio
async def test_applying_never_writes_the_global_file(tmp_path: Path) -> None:
    """Refresh reads user intent and writes only the project cache."""
    flow = _colliding_flow(tmp_path)
    before = flow.state.global_path.read_text()
    mock = _collision_reachable()
    try:
        await flow.advance_from_sources()
        await flow.advance_from_fetched()
        await flow.advance_from_resolved()
    finally:
        mock.stop()

    assert flow.step == "applied"
    assert flow.state.global_path.read_text() == before


@pytest.mark.anyio
async def test_no_collision_leaves_the_list_empty(tmp_path: Path) -> None:
    flow = _flow(tmp_path)
    mock = _reachable()
    try:
        await flow.advance_from_sources()
        await flow.advance_from_fetched()
    finally:
        mock.stop()

    assert flow.resolved is not None
    assert flow.resolved.collisions == []
