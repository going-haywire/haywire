"""Pre-emptive framework-requirement check for a marketstall entry.

The gate the share pipeline's framework step always described but nobody
built: the framework requirement was authored, written to the marketstall
entry, parsed, round-tripped and preserved across refreshes — and then never
consulted. Every framework conflict surfaced only when uv's resolver refused
the install, several steps into the flow.

What this is worth, and what it is NOT: this is an **advisory** check against
author-declared metadata, so it reads a catalog value that can be absent or
simply wrong. It is therefore allowed to say "no declared problem" and be
mistaken — the constraints file in ``LibraryManager`` still refuses the
install at resolve time, and uv, which reads the real ``Requires-Dist`` off
the wheel, remains the authority. The gate only moves a knowable "no" earlier,
to the button the user just pressed. It must never be the sole guard, and a
missing ``require`` must never block anything.

Staleness is no longer one of the failure modes for entries this repo
publishes: ``require`` is derived from the library's own pyproject floor at
write time rather than authored beside it, so the two cannot disagree. A
hand-edited catalog still can, hence "advisory".

Only ``haywire-core`` is checked. It is the one package every haybale depends
on, the carrier the share wizard writes its floor to, and the version the
framework moves in lockstep with — so a core mismatch implies the rest. The
``require`` token names the package anyway, matching the pyproject entry it
projects; a token naming anything else is metadata this gate cannot act on and
is passed through rather than blocked on.
"""

from __future__ import annotations

import importlib.metadata
from dataclasses import dataclass

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

from haywire.core.marketstall.requirement import CORE as _CORE
from haywire.core.marketstall.requirement import dependency_name, requirement_specifier


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


def check_require(require: str, installed: str | None = None) -> FrameworkVerdict:
    """Whether the *require* token admits the running ``haywire-core``.

    *require* is a full PEP 508 token — ``"haywire-core>=0.0.38"`` — matching
    the shape of the library's own pyproject entry. A bare ``"haywire-core"``
    means the author declared the dependency with no floor, which constrains
    nothing and therefore passes.

    Returns ``ok=True`` for every case where no conflict is PROVEN, which
    deliberately includes all six ways the check can fail to apply:

    * no requirement declared (an entry that omits the field),
    * a token naming some package other than ``haywire-core``,
    * a token with no specifier (declared, no floor),
    * a specifier that is not parseable PEP 440,
    * an installed version that is not parseable, and
    * ``haywire-core`` not installed at all.

    Each of those is a gap in our metadata, not evidence about the user's
    environment, and blocking on one would turn an advisory nicety into a
    wall in front of an install that may well succeed. The resolver still
    has the final say either way.
    """
    token = (require or "").strip()
    if not token:
        return FrameworkVerdict(ok=True)

    # A token for anything else is metadata we cannot act on — only
    # haywire-core is checked (see the module docstring for why that is
    # sufficient), so a foreign name is a gap, not a conflict.
    if dependency_name(token).lower() != _CORE:
        return FrameworkVerdict(ok=True)

    declared = requirement_specifier(token)
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
