"""Is this catalog row the same library as that one?

The marketplace has no namespace: two authors can publish `haybale-mesh` from
unrelated repositories and nothing stops them. Dedup still has to pick one row
per name, so the question "same library from two feeds?" and "two different
libraries wearing one name?" need different answers — the first is a
preference, the second is a conflict the user must resolve.

The rule is deliberately conservative: say "same" only when it is *provable*,
because a wrong "same" silently swaps whose code gets installed. Everything
else is a conflict the user is asked about. That mirrors
``compute_library_origin``'s posture — an honest unknown beats a wrong guess
in a safety classification.

Policy lives here, in the library, not in ``haywire-core``: core defines the
comparison seam (``resolve(..., same_library=...)``) and stays ignorant of what
counts as identity, so nothing in core points at a barn library.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.core.library.haybale import Haybale

if TYPE_CHECKING:
    from haywire.core.library.info import LibraryInfo


def _canonical_origin(url: str) -> str:
    """Normalize a repo URL for comparison.

    Case, a trailing slash and a ``.git`` suffix are all cosmetic — the same
    repository written three ways must not read as three projects.
    """
    cleaned = url.strip().rstrip("/")
    if cleaned.lower().endswith(".git"):
        cleaned = cleaned[: -len(".git")]
    return cleaned.lower()


def identity_matches(a: Haybale, b: Haybale) -> bool:
    """True when *a* and *b* are provably the same library.

    - Both from PyPI: the name settles it. PyPI is a global namespace with one
      owner per name, so two rows naming one distribution mean one library —
      even if their ``origin`` fields disagree (a mirror may not carry one).
    - Both from git: the same ``origin`` repository, compared canonically.
    - Anything else — a missing ``origin``, or PyPI on one side and git on the
      other — is **not** provable and therefore a conflict.

    PyPI-vs-git is deliberately not resolved in PyPI's favour. Registering a
    name there is trivial, so auto-preferring it would hand the win to a
    squatter in exactly the case that does damage; the user is shown both and
    decides.
    """
    if a.name != b.name:
        return False

    if a.source == "pypi" and b.source == "pypi":
        return True

    if a.source == "git" and b.source == "git":
        origin_a, origin_b = _canonical_origin(a.origin), _canonical_origin(b.origin)
        return bool(origin_a) and origin_a == origin_b

    return False


def installed_identity_matches(
    installed: "LibraryInfo",
    candidate: Haybale,
    marketplace_path: str | None,
) -> bool:
    """True when *candidate* is provably the library already installed here.

    Same rule as :func:`identity_matches`, with one addition: an **editable,
    project-local** checkout is authoritative for its own identity. Its
    ``haybale.toml`` legitimately carries no ``origin`` — the share wizard
    writes that at publish time — so the plain rule would read every in-repo
    library as unprovable and raise a conflict on every refresh. Here the
    checkout wins: a feed row is the same library only when its ``origin``
    matches the one the checkout declares, and an undeclared origin means the
    feed row is something else.
    """
    from haybale_marketplace.library_origin import LibraryOrigin, compute_library_origin

    origin = compute_library_origin(installed, marketplace_path, catalog_entry=None)
    is_local_checkout = origin is LibraryOrigin.PROJECT_LOCAL and installed.install_type.is_editable()

    if is_local_checkout:
        if installed.row.name != candidate.name:
            return False
        declared = _canonical_origin(installed.row.origin)
        return bool(declared) and declared == _canonical_origin(candidate.origin)

    return identity_matches(installed.row, candidate)
