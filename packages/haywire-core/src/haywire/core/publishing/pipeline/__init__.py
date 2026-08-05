"""Share pipeline — one publishing engine, driven by the CLI and the wizard.

``SharePipeline`` itself is added in a later task; the vocabulary is
re-exported here so callers have a single import site.
"""

from haywire.core.publishing.git import (
    GitResult,
    git,
    git_remote,
    git_remote_streaming,
    run,
    run_streaming,
)
from haywire.core.publishing.drift.model import DepDrift
from haywire.core.publishing.pipeline.errors import (
    CommitError,
    DocsGenerationError,
    InvalidSpecifierError,
    ManifestError,
    MarketstallError,
    PipelineStateError,
    PreconditionsError,
    PushError,
    ShareError,
    TagCollisionError,
    VersionError,
)
from haywire.core.publishing.pipeline.pipeline import GIT_INSTALL_HINT, SharePipeline
from haywire.core.publishing.pipeline.results import (
    BumpResult,
    CommitPlan,
    CommitResult,
    DocsResult,
    DriftReport,
    FrameworkOption,
    FrameworkPlan,
    LibraryVersion,
    PreconditionFailure,
    PreconditionsReport,
    ShareDecisions,
    PushResult,
    VersionPlan,
)

__all__ = [
    "BumpResult",
    "CommitError",
    "CommitPlan",
    "CommitResult",
    "DepDrift",
    "DocsGenerationError",
    "DocsResult",
    "DriftReport",
    "FrameworkOption",
    "FrameworkPlan",
    "GIT_INSTALL_HINT",
    "GitResult",
    "InvalidSpecifierError",
    "LibraryVersion",
    "ManifestError",
    "MarketstallError",
    "PipelineStateError",
    "PreconditionFailure",
    "PreconditionsError",
    "PreconditionsReport",
    "ShareDecisions",
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
