"""The add-source flow's state machine. UI rendering is smoke-tested only.

The property this flow exists for: nothing is subscribed until the user has
seen what the source offers and settled its collisions. The old dialog wrote
the subscription first and asked afterwards.
"""

from __future__ import annotations

import pytest

from haywire.core.marketstall import Haybale, RefreshReport, ResolvedSource

pytestmark = pytest.mark.unit


@pytest.fixture
def anyio_backend() -> str:
    """anyio's backend parametrization. The repo runs asyncio only."""
    return "asyncio"


def _hb(name: str, *, origin: str = "") -> Haybale:
    return Haybale(name=name, version="0.1.0", source_origin=origin)


class _FakeTarget:
    """Stands in for the marketplace: records writes instead of performing them."""

    def __init__(
        self,
        *,
        offers: list[str] | None = None,
        existing: list[str] | None = None,
        kind: str = "stall",
    ) -> None:
        self._offers = offers if offers is not None else ["haybale-foo"]
        self._existing = existing or []
        self._kind = kind
        self.subscribed: list[str] = []
        self.ignores: list[tuple[str, str]] = []
        self.refreshed = 0
        self.resolve_error: Exception | None = None
        self.subscribe_error: Exception | None = None
        self.refresh_error: Exception | None = None
        self.ignore_error: Exception | None = None

    def resolve_source(self, user_input: str) -> ResolvedSource:
        if self.resolve_error is not None:
            raise self.resolve_error
        return ResolvedSource(
            kind=self._kind,  # type: ignore[arg-type]
            persist_url="https://alice.example/marketstall.toml",
            body="",
            haybales=[_hb(n) for n in self._offers],
        )

    def existing_haybales(self) -> list[Haybale]:
        return [_hb(n, origin="https://bob.example/marketstall.toml") for n in self._existing]

    def subscribe(self, resolved: ResolvedSource) -> str:
        if self.subscribe_error is not None:
            raise self.subscribe_error
        self.subscribed.append(resolved.persist_url)
        return resolved.persist_url

    def record_ignore(self, source_url: str, haybale_name: str) -> None:
        if self.ignore_error is not None:
            raise self.ignore_error
        self.ignores.append((source_url, haybale_name))

    def refresh(self) -> RefreshReport:
        if self.refresh_error is not None:
            raise self.refresh_error
        self.refreshed += 1
        return RefreshReport(haybales_resolved=len(self._offers))


def _flow(target: _FakeTarget):
    from haybale_marketplace.editors._add_source_flow import AddSourceFlow

    return AddSourceFlow(target=target)


@pytest.mark.anyio
async def test_probe_writes_nothing(tmp_path) -> None:
    target = _FakeTarget()
    flow = _flow(target)

    await flow.advance_from_input("https://alice.example/marketstall.toml")

    assert flow.step == "probed"
    assert flow.error is None
    assert target.subscribed == []


@pytest.mark.anyio
async def test_probe_reports_what_the_source_offers() -> None:
    target = _FakeTarget(offers=["haybale-foo", "haybale-bar"])
    flow = _flow(target)

    await flow.advance_from_input("https://alice.example/marketstall.toml")

    assert flow.new_names == ["haybale-foo", "haybale-bar"]
    assert flow.resolved is not None
    assert flow.resolved.kind == "stall"


@pytest.mark.anyio
async def test_empty_input_stays_put() -> None:
    flow = _flow(_FakeTarget())

    await flow.advance_from_input("   ")

    assert flow.step == "input"
    assert flow.error is not None


@pytest.mark.anyio
async def test_bare_repo_url_is_flagged_as_wrong_input() -> None:
    """Retrying verbatim cannot help, so the panel keeps the field."""
    from haywire.core.marketstall import BareRepoUrlRejectedError

    target = _FakeTarget()
    target.resolve_error = BareRepoUrlRejectedError("point at the marketstall.toml itself")
    flow = _flow(target)

    await flow.advance_from_input("https://github.com/alice/repo")

    assert flow.step == "input"
    assert flow.rejected_input is True
    assert target.subscribed == []


@pytest.mark.anyio
async def test_retry_clears_the_rejected_flag() -> None:
    from haywire.core.marketstall import BareRepoUrlRejectedError

    target = _FakeTarget()
    target.resolve_error = BareRepoUrlRejectedError("nope")
    flow = _flow(target)
    await flow.advance_from_input("https://github.com/alice/repo")

    flow.retry()

    assert flow.rejected_input is False
    assert flow.error is None


@pytest.mark.anyio
async def test_unreachable_source_is_never_subscribed() -> None:
    """The old dialog subscribed first and swallowed the fetch failure."""
    from haywire.core.marketstall import SubscribeError

    target = _FakeTarget()
    target.resolve_error = SubscribeError("Could not fetch https://gone.example/...")
    flow = _flow(target)

    await flow.advance_from_input("https://gone.example/marketstall.toml")

    assert flow.step == "input"
    assert flow.error is not None
    assert target.subscribed == []


@pytest.mark.anyio
async def test_collisions_are_detected_before_subscribing() -> None:
    target = _FakeTarget(offers=["haybale-foo"], existing=["haybale-foo"])
    flow = _flow(target)

    await flow.advance_from_input("https://alice.example/marketstall.toml")

    assert [c.name for c in flow.conflicts] == ["haybale-foo"]
    assert flow.choices == {"haybale-foo": "existing"}
    assert target.subscribed == []


@pytest.mark.anyio
async def test_no_collisions_leaves_the_conflict_step_empty() -> None:
    target = _FakeTarget(offers=["haybale-foo"], existing=["haybale-other"])
    flow = _flow(target)

    await flow.advance_from_input("https://alice.example/marketstall.toml")
    await flow.advance_from_probed()

    assert flow.step == "resolved"
    assert flow.conflicts == []


@pytest.mark.anyio
async def test_subscribe_is_the_first_step_that_writes() -> None:
    target = _FakeTarget()
    flow = _flow(target)
    await flow.advance_from_input("https://alice.example/marketstall.toml")
    await flow.advance_from_probed()
    assert target.subscribed == []

    await flow.advance_from_resolved()

    assert flow.step == "added"
    assert target.subscribed == ["https://alice.example/marketstall.toml"]


@pytest.mark.anyio
async def test_abandoning_before_subscribe_changes_nothing() -> None:
    """Cancel actually cancels — the bug this flow exists to fix."""
    target = _FakeTarget(offers=["haybale-foo"], existing=["haybale-foo"])
    flow = _flow(target)

    await flow.advance_from_input("https://alice.example/marketstall.toml")
    await flow.advance_from_probed()

    assert target.subscribed == []
    assert target.ignores == []
    assert target.refreshed == 0


@pytest.mark.anyio
async def test_keeping_existing_tells_the_new_source_to_step_aside() -> None:
    target = _FakeTarget(offers=["haybale-foo"], existing=["haybale-foo"])
    flow = _flow(target)
    await flow.advance_from_input("https://alice.example/marketstall.toml")
    await flow.advance_from_probed()

    await flow.advance_from_resolved()

    assert len(target.ignores) == 1
    source_url, name = target.ignores[0]
    assert name == "haybale-foo"
    assert source_url == "https://alice.example/marketstall.toml"


@pytest.mark.anyio
async def test_using_new_tells_the_existing_source_to_step_aside() -> None:
    target = _FakeTarget(offers=["haybale-foo"], existing=["haybale-foo"])
    flow = _flow(target)
    await flow.advance_from_input("https://alice.example/marketstall.toml")
    await flow.advance_from_probed()
    flow.choose("haybale-foo", "new")

    await flow.advance_from_resolved()

    assert len(target.ignores) == 1
    source_url, name = target.ignores[0]
    assert name == "haybale-foo"
    assert source_url == "https://bob.example/marketstall.toml"


@pytest.mark.anyio
async def test_failed_ignore_warns_but_keeps_the_subscription() -> None:
    target = _FakeTarget(offers=["haybale-foo"], existing=["haybale-foo"])
    target.ignore_error = OSError("read-only")
    flow = _flow(target)
    await flow.advance_from_input("https://alice.example/marketstall.toml")
    await flow.advance_from_probed()

    await flow.advance_from_resolved()

    assert flow.step == "added"
    assert target.subscribed != []
    assert any("haybale-foo" in w for w in flow.warnings)


@pytest.mark.anyio
async def test_failed_subscribe_stays_on_the_conflict_step() -> None:
    target = _FakeTarget()
    target.subscribe_error = OSError("read-only")
    flow = _flow(target)
    await flow.advance_from_input("https://alice.example/marketstall.toml")
    await flow.advance_from_probed()

    await flow.advance_from_resolved()

    assert flow.step == "resolved"
    assert flow.error is not None


@pytest.mark.anyio
async def test_refresh_is_a_separate_step() -> None:
    target = _FakeTarget()
    flow = _flow(target)
    await flow.advance_from_input("https://alice.example/marketstall.toml")
    await flow.advance_from_probed()
    await flow.advance_from_resolved()
    assert target.refreshed == 0

    await flow.advance_from_added()

    assert flow.step == "refreshed"
    assert target.refreshed == 1
    assert flow.report is not None


@pytest.mark.anyio
async def test_failed_refresh_keeps_the_subscription_and_stays_put() -> None:
    """The subscription is already correct; only the refresh needs retrying."""
    target = _FakeTarget()
    target.refresh_error = RuntimeError("network down")
    flow = _flow(target)
    await flow.advance_from_input("https://alice.example/marketstall.toml")
    await flow.advance_from_probed()
    await flow.advance_from_resolved()

    await flow.advance_from_added()

    assert flow.step == "added"
    assert flow.error is not None
    assert target.subscribed != []


def test_steps_and_titles_stay_in_lockstep() -> None:
    from haybale_marketplace.editors._add_source_flow import STEPS
    from haybale_marketplace.editors._add_source_flow.copy import STEP_TITLES

    assert set(STEPS) == set(STEP_TITLES)
    assert STEPS.index("input") < STEPS.index("probed") < STEPS.index("resolved")
    assert STEPS.index("resolved") < STEPS.index("added") < STEPS.index("refreshed")
