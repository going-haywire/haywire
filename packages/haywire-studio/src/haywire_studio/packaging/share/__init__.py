"""Publishing a haywire project's barn libraries — the ``haywire share`` story.

Layered bottom-up: ``git``/``barn`` (no in-package imports) → ``manifest``,
``url``, ``readme`` → ``drift``, ``marketstall`` → ``pipeline`` → ``cli``.
Modules inside this package import each other directly and never import this
``__init__``; the re-exports below exist for external consumers only, so the
one-directional import keeps cycles structurally impossible.

The public surface here is wider than the curated set the restructure plan
calls out as the eventual public API (see the plan's "Deferred / out of
scope" section — narrowing this to a real curated API is future work). Some
private (underscore-prefixed) names and the ``barn``/``git`` submodules are
re-exported because existing consumers and tests still reach for them via
``haywire_studio.packaging.share`` rather than the concrete submodule; narrowing that
surface without touching every call site is explicitly out of scope for this
task.
"""

from __future__ import annotations

from haywire_studio.packaging.share import barn
from haywire_studio.packaging.share import git
from haywire_studio.packaging.share.drift.apply import apply_drift_fix, union_pyproject_deps
from haywire_studio.packaging.share.drift.detect import detect_share_drift
from haywire_studio.packaging.share.drift.model import DepDrift
from haywire_studio.packaging.share.drift.report import _format_drift_report
from haywire_studio.packaging.share.manifest.deps import _read_library_dependencies
from haywire_studio.packaging.share.manifest.errors import InvalidOsDeclarationError, ManifestReadError
from haywire_studio.packaging.share.manifest.os_field import (
    describe_os_fix,
    invalid_os_values,
    strip_undeclarable_os_values,
)
from haywire_studio.packaging.share.manifest.reader import read_manifest, read_manifest_lenient
from haywire_studio.packaging.share.marketstall import (
    MarketstallWriteResult,
    NoBarnError,
    _build_entry_for_library,
    build_marketstall_entries,
    write_marketstall,
)
from haywire_studio.packaging.share.readme import _update_readme_markers
from haywire_studio.packaging.share.url import (
    ShareSaveResult,
    _derive_url,
    _find_git_root,
    _get_current_ref,
    _get_remote_url,
    derive_share_url_only,
)

__all__ = [
    "DepDrift",
    "InvalidOsDeclarationError",
    "ManifestReadError",
    "MarketstallWriteResult",
    "NoBarnError",
    "ShareSaveResult",
    "_build_entry_for_library",
    "_derive_url",
    "_find_git_root",
    "_format_drift_report",
    "_get_current_ref",
    "_get_remote_url",
    "_read_library_dependencies",
    "_update_readme_markers",
    "apply_drift_fix",
    "barn",
    "build_marketstall_entries",
    "derive_share_url_only",
    "describe_os_fix",
    "detect_share_drift",
    "git",
    "invalid_os_values",
    "read_manifest",
    "read_manifest_lenient",
    "strip_undeclarable_os_values",
    "union_pyproject_deps",
    "write_marketstall",
]
