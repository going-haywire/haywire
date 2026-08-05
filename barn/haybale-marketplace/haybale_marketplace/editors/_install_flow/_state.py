"""The Install / Update Library flow's state machine, free of NiceGUI calls.

One flow serves both operations: an update is an install with a different
``install_spec``, which is how ``install_package`` already treated it.

    selected    what is about to be installed, and from where  -> Check
    checked     the resolver's answer                          -> Install
    installing  streamed uv output                             (auto-advances)
    done        terminal

Two postures, deliberately different:

* A **framework conflict** blocks, and is caught at either of two points: the
  author's declared ``requires_haywire`` (free, checked first) or uv's
  resolver refusing to satisfy the spec without moving a framework-owned
  package. No amount of confirming makes either installable — the remedy is
  to update Haywire itself. The step stays put with the message. The declared
  check is advisory and can only ever catch a subset; the resolver is what
  actually guarantees the guard.
* **Collateral upgrades** inform. Replacing another library is a real
  consequence but a legitimate one, so it is shown and confirmed rather than
  forbidden.
"""

from __future__ import annotations

import logging
import time
from typing import Optional, Protocol

from haywire.core.marketstall import Haybale, check_require
from haywire.ui.components.popup import Popup
from haywire.ui.components.stepper import StepFlow

from .copy import STEP_TITLES, STEPS

logger = logging.getLogger(__name__)


class InstallSource(Protocol):
    """The slice of :class:`LibraryManager` this flow drives."""

    async def dry_run(self, install_spec: str) -> list[str]: ...

    async def install(
        self,
        install_spec: str,
        on_output,
        source_pkg: Optional[Haybale] = None,
        known_removals: Optional[list[str]] = None,
    ) -> tuple[bool, str, object]: ...

    def get_installed_version(self, dist_name: str) -> str: ...


class InstallFlow(StepFlow):
    """Linear, resumable state machine for the Install / Update flow."""

    STEPS = STEPS
    STEP_TITLES = STEP_TITLES

    def __init__(
        self,
        *,
        source: InstallSource,
        install_spec: str,
        name: str,
        package: Optional[Haybale] = None,
        current_version: str = "",
        popup: Optional[Popup] = None,
    ) -> None:
        super().__init__()
        self.source = source
        self.install_spec = install_spec
        self.name = name
        self.package = package
        self.current_version = current_version
        self.popup = popup

        #: Distribution names the resolver would remove to make room. Passed
        #: verbatim to install() so the eviction set acted on is the one the
        #: user approved.
        self.removals: list[str] | None = None
        #: True when dry_run refused — a framework conflict, not a choice.
        self.blocked: bool = False
        self.succeeded: bool = False
        self.message: str = ""
        self.hints: object | None = None
        #: Monotonic timestamp the install started, for the elapsed counter.
        #: The panel needs a liveness signal independent of log output, since
        #: uv can go quiet for tens of seconds mid-download.
        self.started_at: float | None = None

    @property
    def elapsed(self) -> float:
        """Seconds since the install began, or 0.0 before it does."""
        if self.started_at is None:
            return 0.0
        return max(0.0, time.monotonic() - self.started_at)

    @property
    def is_update(self) -> bool:
        """An update replaces a version already installed."""
        return bool(self.current_version)

    @property
    def target_version(self) -> str:
        return self.package.version if self.package is not None else ""

    def retry(self) -> None:
        super().retry()
        self.blocked = False

    async def advance_from_selected(self) -> None:
        """Resolve the install without performing it.

        ``uv pip install --dry-run`` is a real resolver round — seconds, and
        blocking — so it runs in a thread rather than starving NiceGUI's
        heartbeat.

        The declared framework requirement is checked FIRST, because it is
        free and the resolver round is not: when the author already told us
        this library cannot run here, spending seconds to have uv reach the
        same conclusion only delays the same answer. The check is advisory —
        it passes whenever nothing is proven (see ``check_require``)
        — so the resolver below remains the real guard.
        """
        self.retry()
        if self.package is not None:
            verdict = check_require(self.package.require)
            if not verdict.ok:
                self.blocked = True
                self.error = verdict.message
                return
        try:
            self.removals = await self.source.dry_run(self.install_spec)
        except RuntimeError as exc:
            # The resolver refused: framework conflict. Not overridable.
            self.blocked = True
            self.fail(exc)
            return
        except Exception as exc:  # noqa: BLE001 — surfaced inline, never swallowed
            self.fail(exc)
            return
        self.step = "checked"

    async def advance_from_checked(self) -> None:
        """Enter the install step. The work itself runs there."""
        self.retry()
        self.step = "installing"

    async def advance_from_installing(self) -> None:
        """Perform the install, streaming output. The only mutating step.

        Stamps ``started_at`` so the panel can show elapsed time — uv's
        output can stall for tens of seconds during a large download, and a
        silent log is indistinguishable from a hung one without it.

        ``known_removals`` carries the resolved set forward so uv is not asked
        to resolve a second time, and so the eviction set matches what the
        user saw on the previous step.
        """
        self.retry()
        self.started_at = time.monotonic()
        try:
            success, message, hints = await self.source.install(
                self.install_spec,
                self.push_log,
                self.package,
                self.removals,
            )
        except Exception as exc:  # noqa: BLE001 — surfaced inline, never swallowed
            self.fail(exc)
            return
        self.succeeded = success
        self.message = message
        self.hints = hints
        if not success:
            # Stay put so Retry re-runs the install rather than landing on a
            # "done" step that installed nothing.
            self.error = message
            return
        self.step = "done"

    async def run_install(self) -> None:
        """Enter *and* perform the install in one user action.

        The installing step has no button of its own — the user pressed
        Install on the previous step and the log panel is the feedback. Kept
        as one call so the panel renders mid-flight with the log attached.
        """
        await self.advance_from_checked()
        if self.on_render is not None:
            self.on_render()
        await self.advance_from_installing()


def resolve_current_version(source: InstallSource, package: Optional[Haybale]) -> str:
    """Installed version of *package*, or "" when it is not installed yet.

    Distinguishes an install from an update without the caller having to know
    which it is.
    """
    if package is None or not package.name:
        return ""
    try:
        return source.get_installed_version(package.name) or ""
    except Exception:  # noqa: BLE001 — a missing version is not an error here
        return ""
