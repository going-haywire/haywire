"""Domain exceptions for the share pipeline.

Expected failures raise; successes return dataclasses. This matches the
existing idiom in ``share.py`` (``DriftError``, ``NoBarnError``) rather than a
Result-type wrapper. Each caller translates: the CLI prints ``str(exc)`` and
exits, the wizard renders inline error state, a future Farmhand wrapper
re-raises as ``FarmhandError``.
"""

from __future__ import annotations


class ShareError(RuntimeError):
    """Base class for every expected share-pipeline failure."""


class PreconditionsError(ShareError):
    """One or more step-1 preconditions failed.

    Carries EVERY failure rather than the first: a user missing both a remote
    and a barn library should see both in one pass, not discover the second
    after fixing the first.
    """

    def __init__(self, failures: list[str]) -> None:
        self.failures = list(failures)
        super().__init__("Cannot share this project:\n  - " + "\n  - ".join(self.failures))


class VersionError(ShareError):
    """A version string was unparsable, or a lockstep bump had no target."""


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
