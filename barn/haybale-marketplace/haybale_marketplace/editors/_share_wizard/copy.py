"""Step vocabulary and dependency copy for the Share Project wizard.

Screens are named after the FINDING, not the operation. "Unused declarations"
is a true description of that screen whether the author removes them or keeps
them; "Removals" would be true in only one branch. The names also match the
headings in the Detect report, so a finding reads identically where it is
reported and where it is resolved.
"""

from __future__ import annotations

STEPS = (
    "preconditions",
    "checked",
    "detect",
    "framework",
    "unused",
    "undeclared",
    "floors",
    "confirm",
    "version",
    "docs",
    "commit",
    "push",
    "done",
)

STEP_TITLES = {
    "preconditions": "Check the project",
    "checked": "Scan dependencies",
    "detect": "Detect",
    "framework": "Framework requirement",
    "unused": "Unused declarations",
    "undeclared": "Undeclared imports",
    "floors": "Version floors",
    "confirm": "Confirm",
    "version": "Version",
    "docs": "Documentation",
    "commit": "Review and commit",
    "push": "Publish",
    "done": "Shared",
}

# What each Detect finding means, in consumer terms, keyed by DepDrift field.
#
# The panel groups by FINDING, so each blurb is stated ONCE above every
# instance — it must read as a general statement about the category, never
# about one library. Severity is carried by the colour token, not by the
# wording: only the first BREAKS an install.
DETECT_SECTIONS = {
    "pyproject_missing": (
        "Undeclared imports",
        "The source imports these but pyproject.toml does not declare them. "
        "Consumers install the library and it fails on import.",
        "--hw-danger",
    ),
    "decorator_missing": (
        "Undeclared in @library(dependencies)",
        "Add these to the list so hot-reload scope tracking and the marketplace's "
        "enable/disable gating know about them. The library still works without "
        "it.",
        "--hw-warning",
    ),
    "unused_declarations": (
        "Declared, not imported",
        "Declared but never imported. Harmless to consumers, and a dynamic import "
        "looks exactly like this, so nothing is removed unless you say so.",
        "--hw-text-dim",
    ),
    "pyproject_version_lag": (
        "Version floors",
        "A declared floor sits below the version installed here. That is not "
        "evidence the floor is wrong: a floor states the OLDEST version that "
        "works, which nothing can compute from source alone.",
        "--hw-text-dim",
    ),
    "unresolved": (
        "Unresolved imports",
        "These imports mapped to no installed distribution, so nothing can tell "
        "whether they need declaring. Usually dynamic or conditional.",
        "--hw-warning",
    ),
}

# Per-item pin choices on the Undeclared imports screen. "no-pin" leads: it
# constrains nobody, and the correct floor is not computable from source.
PIN_OPTIONS = {
    "none": "No pin — declare it, constrain nothing",
    "installed": "Floor at the installed version",
    "custom": "Custom specifier…",
    "skip": "Skip — do not declare",
}

PIN_EXPLANATIONS = {
    "none": (
        "Declares the dependency but constrains no version. Consumers resolve "
        "whatever fits the rest of their project — the safest default, since "
        "nothing here knows the oldest version that actually works.",
        "--hw-positive",
        "check_circle",
    ),
    "installed": (
        "Declares it with a floor at the version installed on this machine. "
        "Correct when you know you rely on something recent; it does lock out "
        "consumers on older versions.",
        "--hw-text-dim",
        "vertical_align_bottom",
    ),
    "custom": (
        "Write the specifier yourself. Validated before the confirm step.",
        "--hw-text-dim",
        "edit",
    ),
    "skip": (
        "Leaves the import undeclared and publishes anyway. Consumers will fail "
        "to import until they install it by hand — choose this only when the "
        "import is optional or guarded.",
        "--hw-danger",
        "warning",
    ),
}

# Per-item choices on the Version floors screen. "keep" is pre-selected and is
# a no-op, so the no-interaction outcome is provably no change.
FLOOR_OPTIONS = {
    "keep": "Keep the declared floor",
    "sync": "Sync to the installed version",
    "custom": "Custom specifier…",
}
