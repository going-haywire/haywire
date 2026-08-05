"""Step 1b — the dependency report. Pure: this module writes nothing.

Kept separate from ``dependencies.py`` because it has more than one consumer:
the wizard's Detect screen, ``haywire deps check``, and any future read-only
surface. Detection is a question about a directory; applying is a mutation of
one. Splitting them means a caller who only wants the answer cannot
accidentally reach a writer.

The report distinguishes what BREAKS from what merely IS. Only undeclared
imports break a consumer's install; unused declarations, lagging floors, and
unresolved imports are facts about the library that the author may want to act
on — or may legitimately leave alone. See :class:`DepDrift` for why lag in
particular is not treated as a defect.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire_studio.packaging.share.drift.detect import detect_share_drift
from haywire_studio.packaging.share.pipeline.results import DriftReport

if TYPE_CHECKING:
    from haywire_studio.packaging.share.pipeline.pipeline import SharePipeline


def check(pipeline: "SharePipeline") -> DriftReport:
    """Scan every barn library and split the findings by severity.

    ``drifted`` holds libraries with undeclared imports — the publish-breaking
    state. ``findings_only`` holds libraries with something to report but
    nothing broken, so a caller can tell "clean" from "clean but worth a look"
    without re-running detection.

    Shares ``detect_share_drift`` with ``haywire deps check``, so both commands
    report identically for the same repo state.
    """
    drifted: list[object] = []
    findings_only: list[object] = []
    for lib_dir in pipeline._barn_library_dirs():
        drift = detect_share_drift(lib_dir)
        if drift.has_drift:
            drifted.append(drift)
        elif drift.has_findings:
            findings_only.append(drift)
    return DriftReport(drifted=drifted, findings_only=findings_only)
