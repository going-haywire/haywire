"""The metadata a library carries, independent of where it is being read from.

Two shapes extend this: :class:`~haywire.core.library.identity.LibraryIdentity`
(a library loaded in this process) and
:class:`~haywire.core.marketstall.types.Haybale` (a library offered by a feed).
They describe the same library at different moments, so the library detail view
takes a ``LibraryMetadata`` and renders either without branching.

Every field defaults. Dataclass inheritance requires it — a non-default field
cannot follow a defaulted one — and the practical effect is that a partially
populated identity no longer fails at construction. The decorator populates
these regardless.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from haywire.core.library.reload import LibraryReloadAction


@dataclass
class LibraryMetadata:
    """Fields common to a loaded library and a published feed row."""

    label: str = ""
    version: str = ""
    """For an identity this is the installed version; for a feed row, the one the
    publisher advertised. They differ only while an update is pending — which is
    the transient the library browser's update badge exists to observe."""

    description: str = ""
    authors: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    linked_libraries: list[str] = field(default_factory=list)
    """Sibling haybales whose classes this library subscribes to, as **module
    names** (``haybale_studio``). Required for hot-reload: without the
    declaration a subscriber holds a stale class reference after a reload.
    Consumers needing pip names convert at the point of use."""

    on_reload: str = LibraryReloadAction.NONE.value
    """Wire form — ``"none"``, ``"refresh"``, or ``"restart"``. Use
    :attr:`reload_action` to compare or combine."""

    os: list[str] = field(default_factory=list)
    """Platforms this library supports. Empty means all. Gates installation.

    A decorator kwarg: it has no PEP 621 equivalent and ``[tool.haywire]`` does
    not survive into a wheel, so code is the only place it can live and still be
    readable at runtime."""

    docs_path: str = ""
    """Where the library's docs live, as a path from the **git root** of the
    repository named by ``Haybale.origin`` — e.g.
    ``"barn/haybale-core/haybale_core/"``.

    A trailing slash means a directory (link with ``tree_url``; fetchers append
    ``OVERVIEW.md``/``QUICKREF.md``); no slash means a file (``blob_url``).
    Never an absolute URL: the host and ref come from ``origin`` and
    ``install_spec``, so a baked URL could contradict them. Resolve with
    :func:`haywire.core.marketstall.locate.resolve_row_path`.

    Publish-time only — an installed library's docs travel in the wheel, so this
    is empty on a runtime-constructed identity."""

    examples_path: str = ""
    """Path to the library's examples. Same trailing-slash and resolution rules
    as :attr:`docs_path`, but unlike it this is a decorator kwarg, so it is
    populated on a runtime-constructed identity too."""

    tests_path: str = ""
    """Path to the library's tests. See :attr:`examples_path`."""

    homepage_url: str = ""
    documentation_url: str = ""
    author_url: str = ""
    issues_url: str = ""

    @property
    def reload_action(self) -> LibraryReloadAction:
        """The ordered enum form of :attr:`on_reload`, for comparison and ``max()``."""
        return LibraryReloadAction(self.on_reload)
