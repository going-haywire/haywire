"""``Haybale`` — one library's metadata record, however it was read.

The same fields whether the row came from a library's own ``haybale.toml``
(:func:`~haywire.core.library.haybale_toml.read_haybale`) or a published
marketstall feed (``_parse_haybale_entry`` in
:mod:`haywire.core.marketstall.parsing`) — a renderer takes one row and never
asks which source it came from.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar


@dataclass(frozen=True)
class Deprecation:
    """An author's notice that a library is being retired.

    ``since`` is required because deprecation is a historical fact, not a
    current state: without it a user on 0.0.30 cannot be told whether their
    version predates the notice.

    Informational only — it never blocks an install, an enable, or an update.
    ``os`` remains the only field that gates installation.
    """

    since: str
    reason: str = ""
    successor: str = ""
    """A distribution name the user can install instead, when one exists."""

    def to_dict(self) -> dict:
        """TOML-serializable dict; omits the two optional fields when empty."""
        out = {"since": self.since}
        if self.reason:
            out["reason"] = self.reason
        if self.successor:
            out["successor"] = self.successor
        return out


@dataclass
class Haybale:
    """One entry from a [[haybales]] section."""

    name: str
    """The library's distribution (pip package) name, e.g. ``haybale-core``.
    Also the library's sole identifier: it prefixes every component's
    registry key (``haybale-core:node:Add``)."""
    version: str = ""
    """The version the publisher advertised. Defaulted so a row can be built
    field-by-field in tests and fixtures; an absent version in a real feed is
    still an error, raised by :func:`~haywire.core.marketstall.parsing` — which
    is the only place a row is constructed from untrusted input."""
    # The framework requirement as a full PEP 508 token, identical in shape to
    # the library's own pyproject entry: "haywire-core>=0.0.31",
    # "haywire-core~=0.0.31,<1.0.0", or the bare "haywire-core" when the author
    # deliberately declared no floor. Empty means undeclared — a state distinct
    # from the bare name, which is why this carries the package name and not
    # just the specifier. Derived from the library's pyproject at write time,
    # never authored independently. See haywire.core.marketstall.requirement.
    require: str = ""
    label: str = ""
    description: str = ""
    source: str = "pypi"
    install_spec: str = ""
    tags: list[str] = field(default_factory=list)
    os: list[str] = field(default_factory=list)
    on_reload: str = "none"
    linked_libraries: list[str] = field(default_factory=list)
    """Sibling haybales this library subscribes to, as **module** names
    (``haybale_studio``). Renamed from ``dependencies``, which collided with
    ``[project] dependencies`` — a different concept entirely."""

    origin: str = ""
    """The repository this library is published from. The base that every path
    below resolves against; renamed from ``source_url``."""

    origin_provider: str = ""
    """Which kind of forge ``origin`` is — ``"github"`` / ``"gitlab"``.

    Published because the hostname→provider mapping is otherwise machine-local
    (``~/.haywire/config.toml``), while ``origin`` travels to every consumer. A
    self-hosted forge would then resolve on the publisher's machine and nowhere
    else, so its links would silently not render — invisibly to the one person
    who could fix it. Only the publisher knows what their host runs, so that
    answer is published rather than rediscovered."""

    notes: str = ""
    """A bare filename inside the package directory — one supplementary
    human-readable page. Not the front page: label/description/tags already
    carry that. Replaces ``docs_path``, which held the *module directory* and
    to which both consumers appended something."""

    deprecated: "Deprecation | None" = None
    """The author's retirement notice, or None.

    Travels in the row so a consumer sees it *before* installing. The
    ``[project] classifiers`` projection cannot serve that: it carries neither
    ``reason`` nor ``successor``, and the studio never reads PyPI metadata —
    which would leave the notice invisible to exactly the already-installed
    users who most need it."""

    homepage_url: str = ""
    documentation_url: str = ""
    issues_url: str = ""
    """Absolute URLs, used verbatim. Unlike the paths below they name a place
    outside the repository, so there is nothing to resolve them against."""

    examples_path: str = ""
    tests_path: str = ""
    """Paths, not URLs, relative to the **project root** — the directory holding
    ``.haywire/``, which preflight requires to be the git root.

    Project-relative rather than library-relative because examples and tests
    belong to the project: an example graph wires several libraries together and
    cannot live inside any one of them. The consumer resolves them against
    ``origin`` at ``install_spec``'s ref — see
    :func:`haywire.core.marketstall.locate.resolve_row_path`. Storing a baked
    URL instead let the ref disagree with the one actually published; a trailing
    slash marks a directory."""

    # Runtime-only routing metadata (not persisted). `source_origin` is
    # unrelated to `origin` above — it records whether this row arrived from a
    # market or a stall.
    source_label: str = ""
    source_file: str = ""
    source_origin: str = ""
    owner_url: str = ""
    """The subscription URL a `preference` for this row must be written against.

    Empty when ``via`` is itself a subscription (the common case). Set only for
    a stall discovered through a `[[markets]]` body: the user never subscribed
    to that stall, so the aggregator is the only thing they can express a
    preference on. Runtime-only — never persisted."""

    # Cache-only fields (project [[caches]] only).
    via: str = ""
    last_seen: str = ""
    stale: bool = False

    authors: list[tuple[str, str]] = field(default_factory=list)
    """``(name, url)`` pairs; ``url`` is ``""`` when the author declared none.

    Serializes to a ``[[authors]]`` table array, so it is written after every bare
    key — see the ordering note on ``_TOML_FIELDS``."""

    _TOML_FIELDS: ClassVar[tuple[str, ...]] = (
        "name",
        "label",
        "version",
        "require",
        "description",
        "source",
        "install_spec",
        "tags",
        "os",
        "on_reload",
        "linked_libraries",
        "origin",
        "origin_provider",
        "notes",
        "homepage_url",
        "documentation_url",
        "issues_url",
        "examples_path",
        "tests_path",
        "via",
        "last_seen",
        "stale",
        # Both serialize to TOML tables, so they MUST stay last and in this
        # order: every bare key written after a table header is parsed into
        # that table.
        "authors",
        "deprecated",
    )

    def to_dict(self) -> dict:
        """TOML-serializable dict; omits empty/default-valued fields."""
        result: dict = {}
        for f in self._TOML_FIELDS:
            val = getattr(self, f)
            if not val:
                continue
            if f == "authors":
                result[f] = [{"name": name, **({"url": url} if url else {})} for name, url in val]
            else:
                result[f] = val.to_dict() if isinstance(val, Deprecation) else val
        return result
