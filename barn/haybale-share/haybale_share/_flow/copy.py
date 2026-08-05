"""Static copy for the Share flow: step names, titles, and the finding vocabulary.

The finding vocabulary lives here ONCE. It used to exist twice — the wizard's
panels and the CLI's printer each carried their own list of the same five
kinds, with different headings and a duplicated explanation of why grouping by
finding beats grouping by library. Changing a finding kind meant editing both,
and nothing caught a caller that forgot.
"""

from __future__ import annotations

#: Three screens, then a terminal one.
#:
#: `preflight` auto-runs on open and renders its own failures inline — there is
#: no decision on it, so a "Check" button would ask the user to confirm an
#: intent they already expressed by opening the flow.
#:
#: `review` carries EVERY dependency decision plus the version on one screen.
#: The predecessor spread these over six, of which up to five were routinely
#: empty: a clean repo meant six clicks through six screens of good news.
#:
#: `publish` executes what `review` decided: docs, marketstall, commit, tag,
#: push. No decisions, so no intermediate screens — splitting it served the
#: pipeline's checkpoints, not the user's.
STEPS = ("preflight", "review", "publish", "done")

STEP_TITLES = {
    "preflight": "Check the project",
    "review": "Review and decide",
    "publish": "Publish",
    "done": "Published",
}

#: field name → (title, explanation, colour token).
#:
#: Only `pyproject_missing` breaks a consumer's install; the rest are facts the
#: author may legitimately leave alone. Severity is carried by COLOUR, not by
#: order, so the screen never implies that a lagging floor is a defect.
DETECT_SECTIONS: dict[str, tuple[str, str, str]] = {
    "pyproject_missing": (
        "Undeclared imports",
        "The source imports these but pyproject.toml does not declare them. "
        "Published as-is, consumers install the library and it fails on import.",
        "--hw-danger",
    ),
    "unused_declarations": (
        "Declared, not imported",
        "Declared but never imported. Harmless to consumers — removing is a "
        "tidy-up, and it cannot be undone from here.",
        "--hw-warning",
    ),
    "pyproject_version_lag": (
        "Version floors below what is installed",
        "A floor states the OLDEST version that works, not the newest available. "
        "Raising it locks out consumers who could have installed fine.",
        "--hw-warning",
    ),
    "unresolved": (
        "Unresolved imports",
        "These mapped to no installed distribution — usually a dynamic import, "
        "occasionally a typo. Nothing is written for them.",
        "--hw-text-dim",
    ),
}

#: How to declare an undeclared import. "none" is the default: declaring the
#: import is unambiguously correct, but nothing here can compute the oldest
#: version that works, so no floor is invented.
PIN_OPTIONS = {
    "none": "declare, no version floor",
    "installed": "floor at the installed version",
    "custom": "custom specifier…",
    "skip": "leave undeclared",
}

#: What to do with a floor below the installed version. "keep" writes nothing.
FLOOR_OPTIONS = {
    "keep": "keep the declared floor",
    "sync": "raise to the installed version",
    "custom": "custom specifier…",
}
