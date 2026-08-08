"""Step 7 — refresh the running process so it reflects what was just published.

The last step, and the only one that runs entirely after the point of no
return. Step 3 bumped every barn library's version in ``pyproject.toml`` and
re-locked, but neither of those reaches the *installed* distribution metadata
that a library declaring ``version=_pkg_version(...)`` actually reads. Without
this the studio keeps reporting the pre-bump version — right as the wizard
displays a "published vX.Y.Z" success screen.

Deliberately here rather than beside the bump it corrects. Two reasons:

* The bump is inside the rollback window. A sync there would leave the
  environment on a version the tree no longer holds if a later step failed.
* Evicting and re-importing libraries mid-flow strands the studio without them
  across the docs subprocess and the commit, for no benefit — nothing between
  the bump and the push reads the registry.

Order within the step is load-bearing: the sync must precede any reload, since
the reload re-runs ``@library(...)`` and reads back exactly the metadata the
sync rewrites. The registry reload itself lives in the flow (``haybale-share``),
which owns the live library system; this module owns the environment half.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.core.publishing.pipeline.versions import refresh_environment

if TYPE_CHECKING:
    from haywire.core.publishing.pipeline.pipeline import SharePipeline


def apply(pipeline: "SharePipeline") -> tuple[bool, str | None]:
    """``uv sync`` the workspace. Returns ``(refreshed, warning)``; never raises.

    Never blocking, for a stronger reason than :func:`refresh_lockfile`'s: by
    the time this runs the commit, tag and push have all landed, so the publish
    is already public and a failed sync cannot be a failed share. The warning
    carries the remedy — a manual ``uv sync``.
    """
    return refresh_environment(pipeline.repo_root)
