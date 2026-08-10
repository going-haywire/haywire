"""LibraryOrigin — the second, orthogonal axis alongside InstallType.

InstallType (haywire.core.library.install_type) answers "how did this
library reach the Python environment" (REGULAR / EDITABLE / FOLDER) — a
pure filesystem fact, workspace-agnostic, computed in haywire-core.

LibraryOrigin answers "where did the code come from / who owns it"
(FRAMEWORK / PROJECT_LOCAL / PYPI / GIT / UNKNOWN) — this requires
workspace context (the project's barn/ root), which haywire-core
deliberately does not have. Origin computation therefore lives here, at
the marketplace layer, not in core.

``LibraryOrigin.is_protected`` is the single predicate every "can this be
disabled/uninstalled" check should read, replacing the OR-of-scattered-
checks pattern the original narrow is_required() fix used but didn't
generalize. See internals/handoff/library-origin-and-required-classification.md.
"""

from __future__ import annotations

import enum
from pathlib import Path
from typing import TYPE_CHECKING

from haywire.core.library.info import LibraryInfo
from haywire.core.library.install_type import InstallType

if TYPE_CHECKING:
    from haywire.core.marketstall.types import Haybale


class LibraryOrigin(enum.Enum):
    """Where a library's code came from / who owns it."""

    FRAMEWORK = "framework"  # This library IS the framework (e.g. builtin).
    PROJECT_LOCAL = "project_local"  # Lives under this workspace's own barn/.
    PYPI = "pypi"  # Came from a marketplace install, catalog source=pypi.
    GIT = "git"  # Came from a marketplace install, catalog source=git.
    UNKNOWN = "unknown"  # No catalog entry — origin honestly unresolvable.

    @property
    def is_protected(self) -> bool:
        """True when Disable/Uninstall should never be offered for this origin.

        FRAMEWORK and PROJECT_LOCAL only. UNKNOWN is deliberately NOT
        protected — an editable install with no catalog entry (e.g. a bare
        ``pip install -e ../some-other-repo`` outside the marketplace flow)
        stays exactly as disable/uninstallable as it always was; origin's
        job is to correctly protect the two cases it CAN prove, not to
        become a general trust gate for everything it can't classify.
        """
        return self in (LibraryOrigin.FRAMEWORK, LibraryOrigin.PROJECT_LOCAL)


def is_project_library(lib: LibraryInfo, marketplace_path: str | None) -> bool:
    """Return True if lib is the local project library (lives under workspace/barn/).

    Low-level path-check primitive — one input to compute_library_origin(),
    but also used independently by callers that only need this narrower
    question (e.g. the Edit dialog's heap-vs-installed-wheel branching).
    """
    if not marketplace_path or not lib.identity.folder_path:
        return False
    workspace_root = Path(marketplace_path).parent.parent
    return Path(lib.identity.folder_path).is_relative_to(workspace_root / "barn")


def compute_library_origin(
    lib: LibraryInfo,
    marketplace_path: str | None,
    catalog_entry: "Haybale | None",
) -> LibraryOrigin:
    """Compute lib's LibraryOrigin.

    Rules, in order:
      1. FOLDER mechanism implies FRAMEWORK directly — no path analysis.
         There is exactly one FOLDER-mechanism library today (builtin),
         discovered through its own dedicated folder-scan path, structurally
         distinct from the pip entry-point path. Revisit only if a second
         FOLDER-mechanism library ever ships.
      2. Path under this workspace's barn/ (is_project_library) -> PROJECT_LOCAL.
         Takes priority over any catalog entry — a project's own barn/
         library that also happens to have a stale catalog row is still
         project-local first.
      3. A matching catalog Haybale row exists -> its source field
         ("pypi" / "git") maps directly.
      4. No catalog row -> UNKNOWN. Never guessed from mechanism — a wrong
         guess is worse than an honest unknown for a safety classification.

    ``catalog_entry`` is the caller-resolved Haybale row matching lib's
    distribution_name (or None). Callers already have this lookup
    (LibraryOverviewEditor._catalog_row_for, or a scan over
    MarketplaceState.get_project_haybales() / parse_project_marketplace(...).caches)
    — resolving it here would couple this module to SessionContext/
    MarketplaceState, which it deliberately stays free of.
    """
    if lib.install_type is InstallType.FOLDER:
        return LibraryOrigin.FRAMEWORK
    if is_project_library(lib, marketplace_path):
        return LibraryOrigin.PROJECT_LOCAL
    if catalog_entry is not None:
        if catalog_entry.source == "pypi":
            return LibraryOrigin.PYPI
        if catalog_entry.source == "git":
            return LibraryOrigin.GIT
    return LibraryOrigin.UNKNOWN
