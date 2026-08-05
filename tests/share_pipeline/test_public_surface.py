"""The public import surface of the share package.

A characterization test: it encodes what external consumers (the share
wizard, _overview_edit_dialog, deps_cli, app.py) import today, so the
restructure cannot silently drop a name. It is not a design statement —
narrowing this surface is a deliberate follow-up, not something to do by
accident.
"""

import importlib

# Every name the wizard imports from the pipeline package today.
_WIZARD_IMPORTS = (
    "CommitPlan",
    "CommitResult",
    "DocsResult",
    "DriftReport",
    "FrameworkOption",
    "FrameworkPlan",
    "PreconditionFailure",
    "PreconditionsError",
    "PreconditionsReport",
    "PushResult",
    "ShareError",
    "SharePipeline",
    "VersionPlan",
)

# Names other in-repo consumers reach for. `union_pyproject_deps` used to sit
# here for _overview_edit_dialog; both are gone — dependency authoring moved
# into the share wizard, which took the last barn→app import with it.
_OTHER_CONSUMER_IMPORTS = (
    "derive_share_url_only",  # _share_wizard._panel_done
    "detect_share_drift",  # deps_cli
)


def test_pipeline_vocabulary_is_importable() -> None:
    module = importlib.import_module("haywire.core.publishing.pipeline")
    missing = [name for name in _WIZARD_IMPORTS if not hasattr(module, name)]
    assert missing == [], f"share_pipeline no longer exports: {missing}"


def test_share_domain_functions_are_importable() -> None:
    module = importlib.import_module("haywire.core.publishing")
    missing = [name for name in _OTHER_CONSUMER_IMPORTS if not hasattr(module, name)]
    assert missing == [], f"share no longer exports: {missing}"


def test_share_error_hierarchy_is_intact() -> None:
    """Every step exception stays a ShareError, so the wizard's single
    `except ShareError` per step keeps catching all of them."""
    module = importlib.import_module("haywire.core.publishing.pipeline")
    for name in (
        "PreconditionsError",
        "ManifestError",
        "VersionError",
        "TagCollisionError",
        "DocsGenerationError",
        "MarketstallError",
        "CommitError",
        "PushError",
        "PipelineStateError",
        "InvalidSpecifierError",
    ):
        assert issubclass(getattr(module, name), module.ShareError), name
