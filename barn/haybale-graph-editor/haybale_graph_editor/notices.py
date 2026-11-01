"""Graph notices — short messages a library attaches to an open graph.

Producers post a :class:`GraphNotice` through ``GraphAppState.post_notice``;
the haystack row lists them. A notice is identified by its ``key`` within one
graph, so re-posting under the same key replaces it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from haywire.core.access import AccessTier
from haywire.core.signals import Signal

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext


@dataclass(frozen=True)
class GraphNotice:
    """One message about an open graph, with an optional action.

    ``key`` is namespaced by the producer (``haybale-models:needs``). The
    action button is shown only to sessions that satisfy ``requires``.

    Example::

        GraphNotice("haybale-models:needs", "2 models missing", action_label="Show in Models", action=show)
    """

    key: str
    text: str
    action_label: str | None = None
    action: Callable[[SessionContext], None] | None = None
    requires: AccessTier = AccessTier.VIEW
    dismissable: bool = False


@dataclass(frozen=True)
class GraphNoticesChanged(Signal):
    """The notices of some open graph changed. Cross-session, payload-free.

    Subscribers re-read ``GraphAppState.notices``.
    """

    cross_session: ClassVar[bool] = True
