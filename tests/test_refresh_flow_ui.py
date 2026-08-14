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
    """A step with no panel raises at open time, so keep the two in lockstep.

    Every step needs a title and a panel, including `conflicts`, which most
    runs step over but which stays in the list so the progress bar keeps its
    length.
    """
    from haybale_marketplace.editors._refresh_flow import STEPS
    from haybale_marketplace.editors._refresh_flow.copy import STEP_TITLES

    assert set(STEPS) == set(STEP_TITLES)
    assert STEPS.index("sources") < STEPS.index("fetched") < STEPS.index("conflicts")
    assert STEPS.index("conflicts") < STEPS.index("resolved") < STEPS.index("applied")


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
        body = (
            f'[[haybales]]\nname = "haybale-foo"\nversion = "{version}"\n'
            'source = "git"\norigin = "https://github.com/alice/foo"\n'
        )
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


# ---------------------------------------------------------------------------
# Name conflicts — two different libraries wearing one name
# ---------------------------------------------------------------------------


class _ConflictingState(_CollidingState):
    """Both stalls offer haybale-foo, but the resolver calls them different
    libraries — the marketplace's identity policy said so."""

    def __init__(self, root: Path) -> None:
        super().__init__(root)
        self.blocked: list[tuple[str, str]] = []
        self.installed: dict[str, object] = {}

    def resolve(self, fetched):
        from haybale_marketplace.identity import identity_matches
        from haywire.core.marketstall import resolve_catalog

        return resolve_catalog(fetched, same_library=identity_matches)

    def installed_row(self, name: str):
        return self.installed.get(name)

    def block_source(self, name: str, *, source_url: str) -> None:
        from haywire.core.marketstall import record_block_on_source

        self.blocked.append((source_url, name))
        record_block_on_source(self.global_path, source_url=source_url, haybale_name=name)

    def unblock_source(self, name: str, *, source_url: str) -> None:
        from haywire.core.marketstall import remove_block_on_source

        self.blocked = [b for b in self.blocked if b != (source_url, name)]
        remove_block_on_source(self.global_path, source_url=source_url, haybale_name=name)


def _conflicting_flow(root: Path):
    from haybale_marketplace.editors._refresh_flow import RefreshFlow

    return RefreshFlow(state=_ConflictingState(root))


def _conflict_reachable():
    """Both stalls reachable, each serving an UNRELATED library of one name."""

    def fake_urlopen(url, *, timeout):
        from unittest.mock import MagicMock

        m = MagicMock()
        version, repo = ("2.1.0", "alice") if url == _URL_A else ("2.3.0", "bob")
        body = (
            f'[[haybales]]\nname = "haybale-foo"\nversion = "{version}"\n'
            f'source = "git"\norigin = "https://github.com/{repo}/foo"\n'
        )
        m.__enter__.return_value.read.return_value = body.encode()
        return m

    mock = patch.object(marketstall_cache, "_urlopen", side_effect=fake_urlopen)
    mock.start()
    return mock


@pytest.mark.anyio
async def test_a_name_conflict_routes_through_the_conflicts_step(tmp_path: Path) -> None:
    flow = _conflicting_flow(tmp_path)
    mock = _conflict_reachable()
    try:
        await flow.advance_from_sources()
        await flow.advance_from_fetched()
    finally:
        mock.stop()

    assert flow.step == "conflicts"
    assert "conflicts" in flow.STEPS
    assert [c.name for c in flow.conflicts] == ["haybale-foo"]
    assert not flow.state.project_path.exists()


@pytest.mark.anyio
async def test_no_conflict_steps_over_the_conflicts_step(tmp_path: Path) -> None:
    """Skipped, not removed — the bar must not change length mid-flow."""
    flow = _colliding_flow(tmp_path)  # same-library collision
    mock = _collision_reachable()
    try:
        await flow.advance_from_sources()
        await flow.advance_from_fetched()
    finally:
        mock.stop()

    assert flow.step == "resolved"
    assert "conflicts" in flow.STEPS  # listed, just not stopped at
    assert flow.conflicts == []


@pytest.mark.anyio
async def test_blocking_a_claimant_resolves_the_conflict_in_place(tmp_path: Path) -> None:
    flow = _conflicting_flow(tmp_path)
    mock = _conflict_reachable()
    try:
        await flow.advance_from_sources()
        await flow.advance_from_fetched()
        flow.block_claimant("haybale-foo", source_url=_URL_B)
    finally:
        mock.stop()

    assert flow.state.blocked == [(_URL_B, "haybale-foo")]
    # The conflict stays listed — settled, not disappeared.
    assert [c.name for c in flow.conflicts] == ["haybale-foo"]
    assert flow.conflicts_are_settled is True
    assert not flow.state.project_path.exists()  # still nothing written


@pytest.mark.anyio
async def test_an_unsettled_conflict_cannot_be_skipped(tmp_path: Path) -> None:
    """Even with nothing installed: leaving it unsettled is what lets a
    survivor win by attrition on some later refresh."""
    flow = _conflicting_flow(tmp_path)
    mock = _conflict_reachable()
    try:
        await flow.advance_from_sources()
        await flow.advance_from_fetched()
        await flow.advance_from_conflicts()
    finally:
        mock.stop()

    assert flow.step == "conflicts"
    assert flow.error is not None


@pytest.mark.anyio
async def test_a_blocked_claimant_stays_listed(tmp_path: Path) -> None:
    """Blocking must not make the claimant vanish.

    A vanished claimant turns the step into "keep blocking until the conflict
    reports itself gone", which lets the last one standing win by attrition
    rather than by being chosen.
    """
    flow = _conflicting_flow(tmp_path)
    mock = _conflict_reachable()
    try:
        await flow.advance_from_sources()
        await flow.advance_from_fetched()
        flow.block_claimant("haybale-foo", source_url=_URL_B)
    finally:
        mock.stop()

    claimants = flow.claimants_for("haybale-foo")
    assert [c.url for c in claimants] == [_URL_A, _URL_B]
    assert [c.blocked for c in claimants] == [False, True]


@pytest.mark.anyio
async def test_a_block_can_be_undone_from_the_step(tmp_path: Path) -> None:
    flow = _conflicting_flow(tmp_path)
    mock = _conflict_reachable()
    try:
        await flow.advance_from_sources()
        await flow.advance_from_fetched()
        flow.block_claimant("haybale-foo", source_url=_URL_B)
        flow.unblock_claimant("haybale-foo", source_url=_URL_B)
    finally:
        mock.stop()

    assert [c.blocked for c in flow.claimants_for("haybale-foo")] == [False, False]


@pytest.mark.anyio
async def test_a_rerun_shows_the_choice_made_last_time(tmp_path: Path) -> None:
    """The block lives in the global file, so a fresh flow reads it back."""
    from haybale_marketplace.editors._refresh_flow import RefreshFlow

    first = _conflicting_flow(tmp_path)
    mock = _conflict_reachable()
    try:
        await first.advance_from_sources()
        await first.advance_from_fetched()
        first.block_claimant("haybale-foo", source_url=_URL_B)

        second = RefreshFlow(state=first.state)
        await second.advance_from_sources()
        await second.advance_from_fetched()
    finally:
        mock.stop()

    assert second.step == "conflicts"  # still unsettled? no — one left standing
    assert [c.blocked for c in second.claimants_for("haybale-foo")] == [False, True]


@pytest.mark.anyio
async def test_continue_needs_exactly_one_unblocked_claimant(tmp_path: Path) -> None:
    """Blocking every claimant is as unresolved as blocking none."""
    flow = _conflicting_flow(tmp_path)
    mock = _conflict_reachable()
    try:
        await flow.advance_from_sources()
        await flow.advance_from_fetched()

        assert flow.conflicts_are_settled is False  # two claimants, none blocked
        await flow.advance_from_conflicts()
        assert flow.step == "conflicts"  # refused

        flow.block_claimant("haybale-foo", source_url=_URL_B)
        assert flow.conflicts_are_settled is True

        flow.block_claimant("haybale-foo", source_url=_URL_A)
        assert flow.conflicts_are_settled is False  # none left standing
        await flow.advance_from_conflicts()
        assert flow.step == "conflicts"  # refused again

        flow.unblock_claimant("haybale-foo", source_url=_URL_A)
        await flow.advance_from_conflicts()
    finally:
        mock.stop()

    assert flow.step == "resolved"


@pytest.mark.anyio
async def test_an_installed_claimant_cannot_be_blocked(tmp_path: Path) -> None:
    """Blocking the copy you are running would offer another author's code
    under the same name on the next install."""
    from haywire.core.library.haybale import Haybale

    flow = _conflicting_flow(tmp_path)
    flow.state.installed["haybale-foo"] = Haybale(
        name="haybale-foo", version="2.1.0", source="git", origin="https://github.com/alice/foo"
    )
    mock = _conflict_reachable()
    try:
        await flow.advance_from_sources()
        await flow.advance_from_fetched()
        installed = [c for c in flow.claimants_for("haybale-foo") if c.installed]
        assert [c.url for c in installed] == [_URL_A]
        assert installed[0].can_block is False

        flow.block_claimant("haybale-foo", source_url=_URL_A)
    finally:
        mock.stop()

    assert flow.state.blocked == []  # refused
    assert flow.error is not None


@pytest.mark.anyio
async def test_the_step_count_never_changes_mid_flow(tmp_path: Path) -> None:
    """The progress bar is drawn from flow.STEPS on every render.

    A step list that grows once the resolve finds a conflict would redraw the
    bar with an extra segment halfway through — the user watches the goalposts
    move. The list is fixed; a refresh with nothing to settle steps over the
    conflicts step instead of removing it.
    """
    flow = _colliding_flow(tmp_path)  # same-library: no conflict to settle
    mock = _collision_reachable()
    try:
        counts = [len(flow.STEPS)]
        await flow.advance_from_sources()
        counts.append(len(flow.STEPS))
        await flow.advance_from_fetched()
        counts.append(len(flow.STEPS))
        await flow.advance_from_resolved()
        counts.append(len(flow.STEPS))
    finally:
        mock.stop()

    assert len(set(counts)) == 1, f"step count changed mid-flow: {counts}"
    assert flow.step == "applied"


@pytest.mark.anyio
async def test_a_conflict_flow_has_the_same_step_count(tmp_path: Path) -> None:
    flow = _conflicting_flow(tmp_path)
    mock = _conflict_reachable()
    try:
        before = len(flow.STEPS)
        await flow.advance_from_sources()
        await flow.advance_from_fetched()
    finally:
        mock.stop()

    assert flow.step == "conflicts"
    assert len(flow.STEPS) == before
