"""Pre-emptive framework-requirement check for a marketstall entry.

The check is advisory: it reads author-declared catalog metadata, which can be
absent or wrong, so it may report no problem and be mistaken. uv, which reads
the real ``Requires-Dist`` off the wheel, remains the authority and still
refuses the install at resolve time. Never use this gate as the sole guard,
and never block on a missing ``require``.

Only ``haywire-core`` is checked — the one package every haybale depends on,
and the version the framework moves in lockstep with. A ``require`` token
naming any other package is passed through.
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

    ``message`` is user-facing and empty unless ``ok`` is False; it names both
    the requirement and the running version.
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

    Returns ``ok=True`` unless a conflict is proven, so all six ways the check
    can fail to apply pass:

    * no requirement declared (an entry that omits the field),
    * a token naming some package other than ``haywire-core``,
    * a token with no specifier (declared, no floor),
    * a specifier that is not parseable PEP 440,
    * an installed version that is not parseable, and
    * ``haywire-core`` not installed at all.

    Prereleases satisfy a specifier: 0.0.38rc1 admits ``">=0.0.37"``.

    Args:
        require: A PEP 508 token in the shape of the library's own pyproject
            entry, such as ``"haywire-core>=0.0.38"``. May be empty.
        installed: The ``haywire-core`` version to check against; read from the
            environment via :func:`installed_core_version` when ``None``.
    """
    token = (require or "").strip()
    if not token:
        return FrameworkVerdict(ok=True)

    # A foreign package name is a gap in the metadata, not a conflict.
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

    # prereleases=True: packaging excludes them by default, which would block a
    # strictly newer framework such as 0.0.38rc1 against ">=0.0.37".
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
