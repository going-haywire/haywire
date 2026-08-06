"""Domain exceptions for the share pipeline.

Expected failures raise; successes return dataclasses. This matches the
existing idiom in ``share.py`` (``NoBarnError``, ``InvalidOsDeclarationError``)
rather than a Result-type wrapper. Each caller translates: the CLI prints
``str(exc)`` and exits, the wizard renders inline error state, a future
Farmhand wrapper re-raises as ``FarmhandError``.
"""

from __future__ import annotations

from haywire.core.publishing.pipeline.results import PreconditionFailure


class ShareError(RuntimeError):
    """Base class for every expected share-pipeline failure."""


class PreconditionsError(ShareError):
    """The (single) step-1 precondition failure. See PreconditionFailure.kind
    for the two ways the wizard's remedy modal presents it.

    ``failures`` stays list-typed (kept as ``PreconditionsReport.failures`` is)
    for callers not yet migrated; ``check()`` never populates more than one
    entry since it stops at the first failure it finds.
    """

    def __init__(self, failures: list[PreconditionFailure]) -> None:
        self.failures = list(failures)
        lines = ["Cannot share this project:"]
        for failure in self.failures:
            lines.append(f"  - {failure.message}")
            if failure.remedy:
                for remedy_line in failure.remedy.splitlines():
                    lines.append(f"      {remedy_line}")
            # A terminal cannot render an anchor, so the URL is printed. The
            # UI renders the same field as a link instead.
            if failure.doc_url:
                lines.append(f"      {failure.doc_label or 'Docs'}: {failure.doc_url}")
        super().__init__("\n".join(lines))

    @property
    def failure(self) -> PreconditionFailure | None:
        return self.failures[0] if self.failures else None


class ManifestError(ShareError):
    """A library pyproject.toml could not be read or is invalid.

    The pipeline's translation of ``share.py``'s ``ManifestReadError``
    (and its ``InvalidOsDeclarationError`` subclass) at the module boundary —
    see the docstring on ``ManifestReadError`` for why that one is a plain
    ``RuntimeError`` instead of a ``ShareError``.
    """


class VersionError(ShareError):
    """A version string was unparsable, or a lockstep bump had no target."""


class InvalidSpecifierError(VersionError):
    """The author typed something that is not a valid PEP 440 specifier.

    A bare version ("0.0.34") lands here too: requires_haywire always carries
    the operator, so the author's intent (>=? ~=? ==?) is never guessed.
    """


class TagCollisionError(ShareError):
    """The tag for the requested version already exists locally or on the remote."""

    def __init__(self, *, tag: str, local: bool, remote: bool) -> None:
        self.tag = tag
        self.local = local
        self.remote = remote
        where = " and ".join(w for w, hit in (("locally", local), ("on origin", remote)) if hit)
        super().__init__(f"Tag {tag} already exists {where}. Pick a different version.")


class DocsGenerationError(ShareError):
    """``haywire docs --all`` exited non-zero (a crash, not a coverage gap)."""

    def __init__(self, message: str, *, output: str = "") -> None:
        self.output = output
        super().__init__(message)


class MarketstallError(ShareError):
    """The marketstall.toml rebuild could not complete."""


class CommitError(ShareError):
    """Staging, committing, or tagging failed."""

    def __init__(self, message: str, *, stderr: str = "") -> None:
        self.stderr = stderr
        super().__init__(message)


class PushError(ShareError):
    """The push failed. ``manual_command`` is the exact command to retry by hand."""

    def __init__(self, *, stderr: str, manual_command: str) -> None:
        self.stderr = stderr
        self.manual_command = manual_command
        super().__init__(f"Push failed: {stderr}\n\nRun this yourself to retry:\n  {manual_command}")


class PipelineStateError(ShareError):
    """A step was called out of order (its inputs had not been produced yet)."""
