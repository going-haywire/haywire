"""Share pipeline — one publishing engine, driven by the CLI and the wizard.

``SharePipeline`` itself is added in a later task; the vocabulary is
re-exported here so callers have a single import site.
"""

from haywire_studio.gitcmd import (
    GitResult,
    git,
    git_remote,
    git_remote_streaming,
    run,
    run_streaming,
)
from haywire_studio.share_pipeline.errors import (
    CommitError,
    DocsGenerationError,
    ManifestError,
    MarketstallError,
    PipelineStateError,
    PreconditionsError,
    PushError,
    ShareError,
    TagCollisionError,
    VersionError,
)
from haywire_studio.share_pipeline.pipeline import GIT_INSTALL_HINT, SharePipeline
from haywire_studio.share_pipeline.results import (
    BarnDirtyFile,
    BumpResult,
    CommitPlan,
    CommitResult,
    DocsResult,
    DriftReport,
    LibraryVersion,
    PreconditionFailure,
    PreconditionsReport,
    PushResult,
    VersionPlan,
)

__all__ = [
    "BarnDirtyFile",
    "BumpResult",
    "CommitError",
    "CommitPlan",
    "CommitResult",
    "DocsGenerationError",
    "DocsResult",
    "DriftReport",
    "GIT_INSTALL_HINT",
    "GitResult",
    "LibraryVersion",
    "ManifestError",
    "MarketstallError",
    "PipelineStateError",
    "PreconditionFailure",
    "PreconditionsError",
    "PreconditionsReport",
    "PushError",
    "PushResult",
    "ShareError",
    "SharePipeline",
    "TagCollisionError",
    "VersionError",
    "VersionPlan",
    "git",
    "git_remote",
    "git_remote_streaming",
    "run",
    "run_streaming",
]
