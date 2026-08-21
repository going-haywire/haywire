"""FarmhandContext — the facade every Farmhand.run() receives.

Turns the codebase's conventions into methods: ambient-DI resolution,
caller-owned cross-session signal emission (inventory gap 5), thread
offload for blocking work (handlers share the NiceGUI loop in-process),
MCP progress bridging, and the one-call-one-undo-fence rule (ticket 06).
Future enforcement point for guardrails — add locks/policies here, not
in tools.

Cancellation (spec §3): no explicit API is needed in v1 — handlers are
async and run as tasks the SDK cancels when the client cancels a request,
so every ``await`` point (including ``offload``) is a cancellation point.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional, TYPE_CHECKING, TypeVar, cast

from haywire.core.access import AccessTier, resolve_tier
from haywire.core.di.context import (
    get_library_state_container,
    get_signal_dispatcher,
    get_workspace_root,
)

if TYPE_CHECKING:
    from haywire.core.state.base import AppState

T = TypeVar("T")
S = TypeVar("S", bound="AppState")


class FarmhandContext:
    def __init__(
        self,
        progress_reporter: Optional[Callable[[str], Awaitable[None]]] = None,
        principal: Optional[str] = None,
    ):
        self._progress_reporter = progress_reporter
        #: Who is calling. Set by the Farmhand host from the ASGI scope the auth
        #: gate stamped; ``None`` when authentication is off, which resolves to
        #: ADMIN exactly as it does for a browser session.
        self.principal = principal

    # -- access (ADR 0027) ----------------------------------------------

    def can_access(self, required: AccessTier) -> bool:
        """Whether the calling principal currently holds at least ``required``.

        The host already refused this call if the tool's own ``access=`` tier
        was too high, so this is for finer checks *inside* a tool — a branch
        that writes when the caller may write, and reports instead when it may
        not. Reads live authority per call, like ``SessionContext.can_access``,
        so a demotion lands without a reconnect.
        """
        return resolve_tier(self.principal).satisfies(required)

    def can_view(self) -> bool:
        """True whenever the caller holds any tier at all."""
        return self.can_access(AccessTier.VIEW)

    def can_edit(self) -> bool:
        """True for ``edit`` and ``admin``."""
        return self.can_access(AccessTier.EDIT)

    def can_admin(self) -> bool:
        """True for ``admin`` only."""
        return self.can_access(AccessTier.ADMIN)

    def state(self, state_cls: type[S]) -> S:
        """Resolve an AppState instance (e.g. HaystackState) from the DI container."""
        result = get_library_state_container().get(state_cls)
        assert result is not None, f"No state registered for {state_cls.__name__}"
        return result

    def registry(self, registry_cls: type[T]) -> T:
        """Resolve a framework singleton (registries, factories) from the global injector."""
        from haywire.core.di import config as di_config

        injector = getattr(di_config, "_global_injector", None)
        if injector is None:
            raise RuntimeError("Global injector not set — is the library system initialized?")
        return cast(T, injector.get(registry_cls))

    def broadcast(self, signal: Any) -> None:
        """Emit a cross-peer signal so open browser UIs update (caller-owned, gap 5)."""
        get_signal_dispatcher().broadcast(signal)

    async def offload(self, fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Run blocking work off the shared NiceGUI loop."""
        return await asyncio.to_thread(fn, *args, **kwargs)

    async def progress(self, message: str) -> None:
        """Stream a progress line to the MCP client (no-op outside a request)."""
        if self._progress_reporter is not None:
            await self._progress_reporter(message)

    def fence(self, editor: Any) -> None:
        """Open the undo fence for this tool call: one call = one undo gesture."""
        editor.add_fence()

    def workspace_root(self) -> Path:
        return Path(get_workspace_root())
