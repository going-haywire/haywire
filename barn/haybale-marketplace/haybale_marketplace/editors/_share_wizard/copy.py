"""Step vocabulary and dependency-drift copy for the Share Project wizard."""

from __future__ import annotations

STEPS = ("preconditions", "checked", "drift", "framework", "version", "docs", "commit", "push", "done")

STEP_TITLES = {
    "preconditions": "Check the project",
    "checked": "Scan dependencies",
    "drift": "Dependencies",
    "framework": "Framework requirement",
    "version": "Version",
    "docs": "Documentation",
    "commit": "Review and commit",
    "push": "Publish",
    "done": "Shared",
}

# Union leads: it is the only choice that is both corrective and safe.
_DRIFT_OPTIONS = {
    "union": "Union — add what's missing",
    "replace": "Replace — overwrite declarations",
    "skip": "Skip — publish as-is",
}

# (explanation, colour token, icon). The words alone can't carry these
# semantics: the two that sound safest are the destructive one and the one
# that ships a knowingly-broken artifact.
_DRIFT_EXPLANATIONS = {
    "union": (
        "Adds the dependencies listed above to each library's pyproject.toml and "
        "@library decorator, and raises any lagging version floors. Nothing is "
        "removed — declarations you already have are kept as they are.",
        "--hw-positive",
        "add_circle",
    ),
    "replace": (
        "Overwrites each library's declarations with exactly what its source "
        "imports. Anything declared but no longer imported is REMOVED — including "
        "deps you added deliberately, such as optional or runtime-only ones. "
        "The wizard cannot undo this.",
        "--hw-danger",
        "warning",
    ),
    "skip": (
        "Changes nothing and publishes with the drift unresolved. The libraries "
        "above will install for consumers without these dependencies, so they "
        "fail on import until each one is installed by hand.",
        "--hw-warning",
        "info",
    ),
}
