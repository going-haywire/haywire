"""Frozen result dataclasses returned by each share-pipeline step."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from haywire.core.publishing.drift.model import DepDrift


@dataclass(frozen=True)
class PreconditionFailure:
    """One reason a project cannot be published.

    ``message`` states the fault; ``remedy`` states the next action and is
    computed from repo state where that beats a constant (naming the branches
    that contain HEAD, quoting the TOML parser's line number). Presentation
    belongs to the caller: the CLI indents, the wizard renders a remedy modal.

    ``kind`` selects the wizard's remedy-modal shape: ``"inform"`` (default)
    for a failure the wizard cannot act on — message + remedy text, dismiss
    only. ``"act"`` for a failure the wizard CAN repair in place — the modal
    additionally offers a button that performs the fix, then the user
    restarts the wizard to re-check from the top. Mid-pipeline failures
    (steps 2-6, after preflight has passed) are a third, distinct modal shape
    handled outside this class entirely — see ``steps/rollback.py``.

    ``fix_id`` names a repair the pipeline can perform in place. Set only
    when ``kind == "act"``. A string rather than a callable so the report
    stays serializable and repo-mutating closures never cross the engine/UI
    seam.

    ``lib_dir`` is the subject of the fix — a barn library's directory,
    relative to ``repo_root``, for ``strip_os``; a hostname for
    ``add_host_config``. A plain string (not a Path) for the same
    serializability reason as ``fix_id``.

    ``doc_url``/``doc_label`` carry a link the caller should render as a
    LINK — the host's own auth docs for an unreachable origin, the sharing
    guide otherwise. Separate fields rather than a URL inside ``remedy``
    because a URL embedded in prose renders as dead text in the UI (the
    remedy is one pre-wrapped label) and the user would have to select and
    copy it. The CLI still just prints it.
    """

    message: str
    remedy: str = ""
    kind: Literal["inform", "act"] = "inform"
    fix_id: str | None = None
    fix_label: str = ""
    lib_dir: str | None = None
    doc_url: str = ""
    doc_label: str = ""


@dataclass(frozen=True)
class PreconditionsReport:
    """Outcome of step 1. ``ok`` is True iff nothing failed.

    ``check()`` (steps/preconditions.py) stops at the first failure it finds
    — an earlier failure can invalidate the relevance of a later probe (a
    dirty tree makes every later check moot; an unrecognized host makes the
    reachability probe against it wasted). So ``failures`` never holds more
    than one entry; ``failure`` is the primary accessor.
    """

    failures: list[PreconditionFailure]
    remote_url: str | None
    barn_libraries: list[Path]
    default_branch: str | None = None

    @property
    def ok(self) -> bool:
        return not self.failures

    @property
    def failure(self) -> PreconditionFailure | None:
        return self.failures[0] if self.failures else None


@dataclass(frozen=True)
class LibraryVersion:
    """One barn library's declared version."""

    lib_dir: Path
    name: str
    version: str | None


@dataclass(frozen=True)
class VersionPlan:
    """What step 3 could do, before the user picks.

    ``common_version`` is the shared version when every library agrees, else
    None. ``suggestions`` maps "patch"/"minor"/"major" to the resolved X.Y.Z
    and is EMPTY when the versions disagree — there is no honest arithmetic to
    offer, so the user must name a target explicitly.
    """

    current: list[LibraryVersion]
    common_version: str | None
    suggestions: dict[str, str]

    @property
    def versions_agree(self) -> bool:
        return self.common_version is not None


@dataclass(frozen=True)
class BumpResult:
    """Step 3's mutation record. ``lock_warning`` is set when uv lock failed."""

    version: str
    written: list[Path]
    lock_refreshed: bool
    lock_warning: str | None = None


@dataclass(frozen=True)
class DriftReport:
    """The Detect step's findings, aggregated across barn libraries.

    ``drifted`` holds ``DepDrift`` objects with undeclared imports — the one
    state that breaks a consumer's install. ``findings_only`` holds libraries
    with something to report but nothing broken: unused declarations, lagging
    floors, unresolved imports. Only the former forces a decision; the rest are
    offered, and leaving them alone is a valid answer.
    """

    drifted: list[DepDrift]
    findings_only: list[DepDrift]

    @property
    def needs_decision(self) -> bool:
        return bool(self.drifted)

    @property
    def libraries(self) -> list[DepDrift]:
        """Every library with anything to show, drifted first."""
        return [*self.drifted, *self.findings_only]

    @property
    def linked_registrations(self) -> dict[Path, list[str]]:
        """Per-library ``haybale.toml`` ``linked_libraries`` entries to add without asking.

        Lives here rather than in each caller because it is a *pipeline*
        decision — "which registrations are provably true and need no author
        input" — that both the share flow and the CLI must answer identically.
        It was duplicated in both, divergently, before this property existed.

        Read off every library with findings, not just the drifted ones: a
        missing registration is not drift, so a library whose only gap is this
        never appears in ``drifted`` at all.
        """
        return {
            drift.lib_dir: list(drift.linked_missing) for drift in self.libraries if drift.linked_missing
        }


@dataclass(frozen=True)
class DocsResult:
    """Step 4's outcome. ``coverage`` maps library id → coverage-gap lines."""

    coverage: dict[str, list[str]]
    written: list[Path]
    output: str = ""

    @property
    def total_gaps(self) -> int:
        return sum(len(lines) for lines in self.coverage.values())


@dataclass(frozen=True)
class CommitPlan:
    """Step 5's preview: exactly what would be staged, committed, and tagged.

    ``files`` is the pipeline's own accumulated write set. Nothing outside
    that write set can be dirty by the time this runs — step 1's clean-
    working-tree precondition guarantees it — so there is no separate
    opt-in-extras mechanism here.
    """

    files: list[Path]
    message: str
    tag: str
    diffstat: str = ""


@dataclass(frozen=True)
class CommitResult:
    """Step 5's mutation record."""

    sha: str
    tag: str
    files: list[Path]


@dataclass(frozen=True)
class PushResult:
    """Step 6's outcome."""

    remote: str
    branch: str
    tag: str
    output: str = ""


@dataclass(frozen=True)
class FrameworkOption:
    """One framework-requirement the author can publish.

    ``consequence`` states, in concrete counted terms, who this option locks
    out — following the deps-drift precedent, where the words alone cannot
    carry the semantics. Empty when there is no consequence.
    """

    specifier: str
    label: str
    consequence: str = ""
    recommended: bool = False


@dataclass(frozen=True)
class FrameworkPlan:
    """What the framework-requirement step offers, before the author picks.

    ``declared`` is the ``haywire-core`` specifier the barn libraries carry
    today (empty when undeclared); ``installed`` is the running framework
    version. One project-wide answer, matching lockstep versioning.
    """

    installed: str
    declared: str
    options: list[FrameworkOption]


@dataclass(frozen=True)
class ShareDecisions:
    """Every dependency answer the author gave, collected before anything is written.

    The whole point is that assembling this is FREE — building it touches no
    file — so a UI can let the author revise until they commit, and only then
    call :meth:`SharePipeline.apply_all`. That is what shrinks the rollback
    surface: one writing region instead of five, and a flow abandoned before
    Publish leaves the tree exactly as it found it.

    Every field defaults to "change nothing", so an untouched decision set is a
    provable no-op rather than a branch the caller has to remember to skip. The
    one exception is ``framework``: ``None`` means "leave the declared floor
    alone", which is also inert, but an empty string would not be — it would
    fail specifier parsing.

    ``registrations`` is not a decision (see
    :attr:`DriftReport.linked_registrations`); it travels here only so
    :meth:`apply_all` can write it in the same pass.
    """

    framework: str | None = None
    registrations: dict[Path, list[str]] = field(default_factory=dict)
    removals: dict[Path, list[str]] = field(default_factory=dict)
    additions: dict[Path, list[str]] = field(default_factory=dict)
    floors: dict[Path, list[str]] = field(default_factory=dict)
    undeclared_acknowledged: bool = False
