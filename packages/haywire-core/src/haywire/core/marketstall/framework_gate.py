"""Pre-emptive framework-requirement check for a marketstall entry.

The gate the share pipeline's framework step always described but nobody
built: ``requires_haywire`` was authored, written to the marketstall entry,
parsed, round-tripped and preserved across refreshes — and then never
consulted. Every framework conflict surfaced only when uv's resolver refused
the install, several steps into the flow.

What this is worth, and what it is NOT: this is an **advisory** check against
author-declared metadata, so it reads a catalog value that can be stale,
absent, or simply wrong. It is therefore allowed to say "no declared problem"
and be mistaken — the constraints file in ``LibraryManager`` still refuses the
install at resolve time, and uv, which reads the real ``Requires-Dist`` off
the wheel, remains the authority. The gate only moves a knowable "no" earlier,
to the button the user just pressed. It must never be the sole guard, and a
missing ``requires_haywire`` must never block anything.

Only ``haywire-core`` is checked. It is the one package every haybale depends
on, the carrier the share wizard writes its floor to, and the version the
framework moves in lockstep with — so a core mismatch implies the rest.
"""

from __future__ import annotations

import importlib.metadata
from dataclasses import dataclass

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

_CORE = "haywire-core"


@dataclass(frozen=True)
class FrameworkVerdict:
    """The gate's answer. ``ok=False`` is the only actionable outcome.

    ``message`` is user-facing and names both sides of the mismatch — the
    requirement alone ("needs >=0.0.37") does not tell the user what they are
    running, which was the original complaint about the resolver's message.
    """

    ok: bool
    message: str = ""


def installed_core_version() -> str:
    """The running ``haywire-core`` version, or "" when it is not installed."""
    try:
        return importlib.metadata.version(_CORE)
    except importlib.metadata.PackageNotFoundError:
        return ""


def check_requires_haywire(requires_haywire: str, installed: str | None = None) -> FrameworkVerdict:
    """Whether *requires_haywire* admits the running ``haywire-core``.

    Returns ``ok=True`` for every case where no conflict is PROVEN, which
    deliberately includes all four ways the check can fail to apply:

    * no requirement declared (an older or CI-generated marketstall entry),
    * a requirement that is not a parseable PEP 440 specifier,
    * an installed version that is not parseable, and
    * ``haywire-core`` not installed at all.

    Each of those is a gap in our metadata, not evidence about the user's
    environment, and blocking on one would turn an advisory nicety into a
    wall in front of an install that may well succeed. The resolver still
    has the final say either way.
    """
    declared = (requires_haywire or "").strip()
    if not declared:
        return FrameworkVerdict(ok=True)

    running = installed_core_version() if installed is None else installed
    if not running:
        return FrameworkVerdict(ok=True)

    try:
        specifier = SpecifierSet(declared)
    except InvalidSpecifier:
        return FrameworkVerdict(ok=True)

    try:
        current = Version(running)
    except InvalidVersion:
        return FrameworkVerdict(ok=True)

    # prereleases=True: a user running 0.0.38rc1 against ">=0.0.37" is
    # satisfied. Without this, packaging excludes prereleases by default and
    # the gate would block a strictly newer framework.
    if specifier.contains(current, prereleases=True):
        return FrameworkVerdict(ok=True)

    return FrameworkVerdict(
        ok=False,
        message=(
            f"This library needs Haywire {declared}, but you are running {running}. "
            "Update Haywire first — use “Check for updates” in the top bar — then "
            "install this library again."
        ),
    )
