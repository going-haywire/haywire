"""The install/update flow's state machine. UI rendering is smoke-tested only.

Key properties: nothing is installed before the final step, the resolved
removal set is carried forward rather than recomputed, and a framework
conflict blocks instead of being confirmable.
"""

from __future__ import annotations

import pytest

from haywire.core.marketstall import Haybale

pytestmark = pytest.mark.unit


@pytest.fixture
def anyio_backend() -> str:
    """anyio's backend parametrization. The repo runs asyncio only."""
    return "asyncio"


class _FakeSource:
    """Stands in for LibraryManager: records calls instead of running uv."""

    def __init__(self, *, removals: list[str] | None = None, installed: str = "") -> None:
        self._removals = removals if removals is not None else []
        self._installed = installed
        self.dry_run_calls = 0
        self.install_calls: list[dict] = []
        self.dry_run_error: Exception | None = None
        self.result: tuple[bool, str, object] = (True, "Installed", None)

    async def dry_run(self, install_spec: str) -> list[str]:
        self.dry_run_calls += 1
        if self.dry_run_error is not None:
            raise self.dry_run_error
        return list(self._removals)

    async def install(self, install_spec, on_output, source_pkg=None, known_removals=None):
        self.install_calls.append(
            {"spec": install_spec, "pkg": source_pkg, "known_removals": known_removals}
        )
        on_output(f"Installing {install_spec}…")
        return self.result

    def get_installed_version(self, dist_name: str) -> str:
        return self._installed


def _pkg(name: str = "haybale-vision", version: str = "0.3.0") -> Haybale:
    return Haybale(name=name, version=version, install_spec=f"{name}=={version}")


def _flow(source: _FakeSource, *, current_version: str = "", package: Haybale | None = None):
    from haybale_marketplace.editors._install_flow import InstallFlow

    package = package if package is not None else _pkg()
    return InstallFlow(
        source=source,
        install_spec=package.install_spec,
        name=package.name,
        package=package,
        current_version=current_version,
    )


@pytest.mark.anyio
async def test_check_resolves_without_installing() -> None:
    source = _FakeSource()
    flow = _flow(source)

    await flow.advance_from_selected()

    assert flow.step == "checked"
    assert flow.error is None
    assert source.install_calls == []


@pytest.mark.anyio
async def test_collateral_upgrades_are_reported_not_blocked() -> None:
    source = _FakeSource(removals=["haybale-old"])
    flow = _flow(source)

    await flow.advance_from_selected()

    assert flow.step == "checked"
    assert flow.removals == ["haybale-old"]
    assert flow.blocked is False


@pytest.mark.anyio
async def test_framework_conflict_blocks_on_selected() -> None:
    """A resolver refusal is not confirmable — the flow must not advance."""
    source = _FakeSource()
    source.dry_run_error = RuntimeError("Cannot install: update Haywire Studio first")
    flow = _flow(source)

    await flow.advance_from_selected()

    assert flow.step == "selected"
    assert flow.blocked is True
    assert flow.error is not None
    assert "update Haywire Studio" in flow.error


@pytest.mark.anyio
async def test_retry_clears_the_blocked_flag() -> None:
    source = _FakeSource()
    source.dry_run_error = RuntimeError("nope")
    flow = _flow(source)
    await flow.advance_from_selected()
    assert flow.blocked is True

    flow.retry()

    assert flow.blocked is False
    assert flow.error is None


@pytest.mark.anyio
async def test_install_is_the_only_step_that_installs() -> None:
    source = _FakeSource()
    flow = _flow(source)
    await flow.advance_from_selected()
    await flow.advance_from_checked()
    assert source.install_calls == []

    await flow.advance_from_installing()

    assert flow.step == "done"
    assert len(source.install_calls) == 1
    assert flow.succeeded is True


@pytest.mark.anyio
async def test_resolved_removals_are_carried_into_install() -> None:
    """What the user approved on `checked` is what install() acts on."""
    source = _FakeSource(removals=["haybale-old"])
    flow = _flow(source)
    await flow.advance_from_selected()
    await flow.advance_from_checked()

    await flow.advance_from_installing()

    assert source.install_calls[0]["known_removals"] == ["haybale-old"]
    # One resolver round for the whole flow, not two.
    assert source.dry_run_calls == 1


@pytest.mark.anyio
async def test_abandoning_after_check_installs_nothing() -> None:
    source = _FakeSource(removals=["haybale-old"])
    flow = _flow(source)

    await flow.advance_from_selected()

    assert source.install_calls == []
    assert flow.step == "checked"


@pytest.mark.anyio
async def test_failed_install_stays_on_installing() -> None:
    source = _FakeSource()
    source.result = (False, "Install failed: resolver error", None)
    flow = _flow(source)
    await flow.advance_from_selected()
    await flow.advance_from_checked()

    await flow.advance_from_installing()

    assert flow.step == "installing"
    assert flow.error == "Install failed: resolver error"
    assert flow.succeeded is False


@pytest.mark.anyio
async def test_raising_install_is_reported_not_swallowed() -> None:
    source = _FakeSource()

    async def _boom(*a, **kw):
        raise RuntimeError("uv exploded")

    source.install = _boom  # type: ignore[method-assign]
    flow = _flow(source)
    await flow.advance_from_selected()
    await flow.advance_from_checked()

    await flow.advance_from_installing()

    assert flow.step == "installing"
    assert flow.error is not None
    assert "uv exploded" in flow.error


@pytest.mark.anyio
async def test_install_output_is_captured() -> None:
    source = _FakeSource()
    flow = _flow(source)
    await flow.advance_from_selected()
    await flow.advance_from_checked()

    await flow.advance_from_installing()

    assert any("Installing" in line for line in flow.log_lines)


@pytest.mark.anyio
async def test_run_install_advances_and_installs_in_one_action() -> None:
    source = _FakeSource()
    flow = _flow(source)
    await flow.advance_from_selected()
    rendered: list[str] = []
    flow.on_render = lambda: rendered.append(flow.step)

    await flow.run_install()

    assert flow.step == "done"
    # The panel re-rendered on `installing` so the log was visible mid-flight.
    assert rendered == ["installing"]


def test_update_vs_install_is_derived_from_current_version() -> None:
    source = _FakeSource()
    assert _flow(source, current_version="0.2.0").is_update is True
    assert _flow(source).is_update is False


def test_target_version_comes_from_the_package() -> None:
    source = _FakeSource()
    assert _flow(source, package=_pkg(version="1.2.3")).target_version == "1.2.3"


def test_resolve_current_version_reports_installed() -> None:
    from haybale_marketplace.editors._install_flow._state import resolve_current_version

    assert resolve_current_version(_FakeSource(installed="0.2.0"), _pkg()) == "0.2.0"
    assert resolve_current_version(_FakeSource(installed=""), _pkg()) == ""
    assert resolve_current_version(_FakeSource(installed="0.2.0"), None) == ""


def test_steps_and_titles_stay_in_lockstep() -> None:
    from haybale_marketplace.editors._install_flow import STEPS
    from haybale_marketplace.editors._install_flow.copy import STEP_TITLES

    assert set(STEPS) == set(STEP_TITLES)
    assert STEPS.index("selected") < STEPS.index("checked") < STEPS.index("installing")


@pytest.mark.anyio
async def test_elapsed_is_zero_before_the_install_starts() -> None:
    flow = _flow(_FakeSource())

    assert flow.started_at is None
    assert flow.elapsed == 0.0


@pytest.mark.anyio
async def test_install_stamps_a_start_time() -> None:
    """The panel's liveness counter needs a start stamp independent of output."""
    source = _FakeSource()
    flow = _flow(source)
    await flow.advance_from_selected()
    await flow.advance_from_checked()

    await flow.advance_from_installing()

    assert flow.started_at is not None
    assert flow.elapsed >= 0.0


@pytest.mark.anyio
async def test_elapsed_grows_while_installing() -> None:
    import time

    flow = _flow(_FakeSource())
    flow.started_at = time.monotonic() - 5.0

    assert flow.elapsed >= 5.0
