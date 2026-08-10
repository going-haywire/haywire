"""Reading ``haybale.toml`` — a library's own metadata, from its own directory.

The file sits next to ``__init__.py``, *inside* the Python package, so it ships
in the wheel and is readable from disk at runtime. That is the whole point: a
metadata edit is a file write, visible on the next read, with no ``uv sync`` and
no registry reload. ``pyproject.toml`` cannot do this — it is not installed —
and the installed distribution's ``METADATA`` cannot either, because it is
written once at install time and never changes when the source does.

Two readers, deliberately separate:

* :func:`read_haybale_toml` — strict. Used at decoration time, where a library
  that cannot state its own identity must not load half-configured.
* :func:`read_haybale_toml_lenient` — returns ``{}`` on any failure, for
  report-only callers that would rather show a partial answer than none.

The same split ``read_manifest`` / ``read_manifest_lenient`` already draws for
``pyproject.toml``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import toml

from haywire.core.tomlio import edit_toml, read_toml

__all__ = [
    "HaybaleTomlError",
    "HAYBALE_TOML",
    "LibraryDisplay",
    "module_of",
    "read_display",
    "tag_for",
    "read_haybale_toml",
    "read_haybale_toml_lenient",
    "read_raw",
    "EDITABLE_FIELDS",
    "write_haybale_fields",
]

#: The file's name, wherever it is looked for.
HAYBALE_TOML = "haybale.toml"

#: Scalar/list fields copied straight into ``LibraryIdentity`` kwargs. Keys
#: absent from the file are omitted from the result rather than set empty, so a
#: caller can splat over defaults without clobbering them — the contract
#: ``distribution_fields()`` established for the reader this replaces.
_STR_FIELDS = ("id", "label", "on_reload", "description")
_LIST_FIELDS = ("linked_libraries", "tags", "os")

#: A Python module name: identifier characters only, no hyphens, no dots. The
#: shape ``_get_tracking_scopes`` assumes when it appends ``dep + "."``.
_MODULE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class HaybaleTomlError(Exception):
    """``haybale.toml`` is missing, malformed, or does not identify its library.

    Raised at decoration time, and deliberately fatal *for that library only* —
    ``LibraryRegistry`` already wraps each library's load in ``try/except``, so
    the studio still starts, the broken library is visibly absent, and the error
    names the file. The alternative, defaulting to empty, yields
    ``linked_libraries=[]`` and a subscriber holding a stale class reference
    after a reload: the exact failure the field exists to prevent, surfacing
    later and somewhere unrelated.
    """


def module_of(dist_name: str) -> str:
    """The module directory for a haybale distribution name.

    ``haybale-image-tools`` → ``haybale_image_tools``.

    Normalises rather than merely swapping separators: PEP 503 lowercases
    distribution names while ``[project] name`` keeps whatever case the author
    typed, so ``haybale-TEST_A`` installs as ``haybale_test_a``. A plain
    ``replace("-", "_")`` yields ``haybale_TEST_A`` — a directory that does not
    exist. Verified against every in-tree haybale.

    A *publisher* holding the filesystem should prefer
    :func:`~haywire.core.library.dep_detect.find_module_dir`, which observes the
    directory instead of deriving it. This exists for the consumer, who has only
    the name.
    """
    return re.sub(r"[-_.]+", "_", dist_name).lower()


def tag_for(version: str) -> str:
    """The git tag for a released version — ``0.0.40`` → ``v0.0.40``.

    One definition of the convention, for the three places that need it: the
    commit step, the tag step, and ``install_spec``. Each previously re-encoded
    ``f"v{...}"`` independently, which is the shape that drifts.

    The ``v`` belongs to the tag, not to the version: ``version`` is PEP 440 and
    is generated into ``[project] version``, where a leading ``v`` is invalid.
    """
    return f"v{version}"


def _validate_linked_libraries(values: list[str], source: Path) -> None:
    """Every entry must be an importable module name.

    ``_get_tracking_scopes`` builds a hot-reload scope by appending ``"."`` to
    each entry verbatim, so ``"haybale-studio"`` yields the prefix
    ``"haybale-studio."`` — which matches no module, silently disabling reload
    tracking for that dependency. A hand-editable TOML invites exactly that
    typo, so it is rejected at read time rather than accepted and ignored.
    """
    bad = [v for v in values if not _MODULE_NAME.match(v)]
    if bad:
        raise HaybaleTomlError(
            f"{source}: linked_libraries must be Python module names "
            f"(haybale_studio), not distribution names — got {bad!r}. "
            f"Hyphens and dots produce a hot-reload scope that matches nothing."
        )


def _fields_from(data: dict, source: Path) -> dict[str, Any]:
    """Project a parsed document onto ``LibraryIdentity`` kwargs."""
    fields: dict[str, Any] = {}

    for key in _STR_FIELDS:
        value = data.get(key)
        if value is None:
            continue
        if not isinstance(value, str):
            raise HaybaleTomlError(f"{source}: {key} must be a string, got {type(value).__name__}")
        fields[key] = value

    for key in _LIST_FIELDS:
        value = data.get(key)
        if value is None:
            continue
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            raise HaybaleTomlError(f"{source}: {key} must be a list of strings")
        if key == "linked_libraries":
            _validate_linked_libraries(value, source)
        fields[key] = list(value)

    # Two fields whose file spelling differs from the identity's, both
    # transitional: the identity carries one author and one URL, while the file
    # is already shaped for the marketstall row (repeatable [[authors]], and
    # url split into homepage/documentation/issues). Project the first author
    # and the homepage so nothing regresses while call sites migrate to reading
    # the file directly.
    homepage = data.get("homepage_url")
    if isinstance(homepage, str) and homepage:
        fields["url"] = homepage

    authors = data.get("authors")
    if isinstance(authors, list) and authors:
        first = authors[0]
        if not isinstance(first, dict):
            raise HaybaleTomlError(f"{source}: [[authors]] entries must be tables with a `name`")
        name = first.get("name")
        if isinstance(name, str) and name:
            fields["author"] = name
        url = first.get("url")
        if isinstance(url, str) and url:
            fields["author_url"] = url

    return fields


def read_haybale_toml(package_dir: Path) -> dict[str, Any]:
    """The ``LibraryIdentity`` fields declared in *package_dir*'s ``haybale.toml``.

    Absent keys are omitted, so the result splats over defaults cleanly::

        kwargs.update(read_haybale_toml(package_dir))

    Raises :class:`HaybaleTomlError` when the file is missing, malformed, or
    declares no ``id`` — each of which leaves the library unable to name itself
    or to be found in a registry.
    """
    source = package_dir / HAYBALE_TOML
    if not source.is_file():
        raise HaybaleTomlError(
            f"{source} not found. Every library carries one; it ships in the wheel "
            f"beside __init__.py and is the source for label, linked_libraries and "
            f"on_reload."
        )

    try:
        data = read_toml(source)
    except toml.TomlDecodeError as exc:
        raise HaybaleTomlError(f"Malformed TOML in {source}: {exc}") from exc
    except OSError as exc:
        raise HaybaleTomlError(f"Could not read {source}: {exc}") from exc

    if not isinstance(data, dict):
        raise HaybaleTomlError(f"{source}: expected a table at the top level")

    fields = _fields_from(dict(data), source)
    if not fields.get("id"):
        raise HaybaleTomlError(f"{source}: `id` is required — it prefixes every component's registry key.")
    return fields


def read_haybale_toml_lenient(package_dir: Path) -> dict[str, Any]:
    """Like :func:`read_haybale_toml`, but ``{}`` instead of raising.

    For callers that report on a library rather than load it, where a corrupt
    file should still let the report name what it could not read.
    """
    try:
        return read_haybale_toml(package_dir)
    except HaybaleTomlError:
        return {}


# ─────────────────────────────────────────────────────────────────────────────
# Reading at the point of use
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class LibraryDisplay:
    """The descriptive fields, read from disk at the moment they are rendered.

    Deliberately *not* served off ``LibraryIdentity``. The identity is built once
    at import, so a value read through it is only as fresh as the last reload —
    the same staleness the installed distribution's ``METADATA`` had, with a
    shorter cache. Reading the file at the point of use is what makes an edit
    visible immediately, which is the whole reason the metadata moved into the
    package directory.

    Every field defaults, so a library whose file is missing or unreadable
    renders blank rather than raising. That is the opposite of the import-time
    rule, and correct here: a renderer has a frame to draw, and a caller
    displaying a half-known library is better than a panel that cannot draw.
    """

    id: str = ""
    label: str = ""
    description: str = ""
    tags: tuple[str, ...] = ()
    homepage_url: str = ""
    documentation_url: str = ""
    issues_url: str = ""
    authors: tuple[tuple[str, str], ...] = ()
    """``(name, url)`` pairs; url is "" when the author declared none."""

    @property
    def author_names(self) -> str:
        """The authors as one display string — ``"Alice, Bob"``."""
        return ", ".join(name for name, _ in self.authors if name)


#: (path, mtime_ns) -> parsed display. The overview re-renders on every panel
#: redraw, so a parse per render is waste; a stat per render is not. Keyed on
#: mtime so an edit invalidates the entry without anyone having to remember to.
_display_cache: dict[Path, tuple[int, "LibraryDisplay"]] = {}


def read_display(package_dir: Path) -> LibraryDisplay:
    """The descriptive fields declared in *package_dir*'s ``haybale.toml``.

    Never raises: an unreadable or malformed file yields an empty
    :class:`LibraryDisplay`. Cached on the file's mtime, so repeated renders cost
    one ``stat``.
    """
    source = package_dir / HAYBALE_TOML
    try:
        mtime = source.stat().st_mtime_ns
    except OSError:
        _display_cache.pop(package_dir, None)
        return LibraryDisplay()

    cached = _display_cache.get(package_dir)
    if cached is not None and cached[0] == mtime:
        return cached[1]

    try:
        data = read_toml(source)
    except (toml.TomlDecodeError, OSError):
        display = LibraryDisplay()
    else:
        display = _display_from(dict(data) if isinstance(data, dict) else {})

    _display_cache[package_dir] = (mtime, display)
    return display


def _display_from(data: dict) -> LibraryDisplay:
    """Project a parsed document onto :class:`LibraryDisplay`, ignoring junk.

    Wrong-typed values are dropped rather than raised on — see the class
    docstring: rendering degrades, it does not fail.
    """

    def _str(key: str) -> str:
        value = data.get(key)
        return value if isinstance(value, str) else ""

    raw_tags = data.get("tags")
    tags = tuple(t for t in raw_tags if isinstance(t, str)) if isinstance(raw_tags, list) else ()

    authors: list[tuple[str, str]] = []
    raw_authors = data.get("authors")
    if isinstance(raw_authors, list):
        for entry in raw_authors:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name")
            if not isinstance(name, str) or not name:
                continue
            url = entry.get("url")
            authors.append((name, url if isinstance(url, str) else ""))

    return LibraryDisplay(
        id=_str("id"),
        label=_str("label"),
        description=_str("description"),
        tags=tags,
        homepage_url=_str("homepage_url"),
        documentation_url=_str("documentation_url"),
        issues_url=_str("issues_url"),
        authors=tuple(authors),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Writing
# ─────────────────────────────────────────────────────────────────────────────

#: What :func:`write_haybale_fields` will set. Everything else in the file is
#: off-limits to the editor: `name` and `id` are immutable (renaming rewrites
#: registry keys and every consumer's install_spec), `version`, `origin` and
#: `origin_provider` are written by the share wizard from facts it observes, and
#: `[deprecated]` is hand-edited because retiring a library is rare and
#: deliberate.
EDITABLE_FIELDS = (
    "label",
    "os",
    "description",
    "tags",
    "on_reload",
    "linked_libraries",
    "homepage_url",
    "documentation_url",
    "issues_url",
    "examples_path",
    "tests_path",
    "notes",
    "authors",
)


def write_haybale_fields(package_dir: Path, fields: dict[str, Any]) -> None:
    """Update *fields* in *package_dir*'s ``haybale.toml``, preserving the rest.

    Comment-preserving: the file is hand-editable and carries the author's own
    notes, so it is edited in place rather than rebuilt from a dict — a
    round-trip through plain dicts would silently delete every comment.

    Only :data:`EDITABLE_FIELDS` are writable; anything else raises rather than
    being silently dropped, so a caller passing ``version`` learns that the
    share wizard owns it instead of wondering why the write did nothing.

    An empty value removes the key rather than writing ``""``. Absent and empty
    then mean the same thing, which keeps a file edited through the UI
    indistinguishable from one an author wrote by hand.

    ``authors`` is the one non-scalar/non-string-list field: it takes
    ``(name, url)`` tuples — matching :attr:`LibraryDisplay.authors` — and is
    converted to ``[[authors]]`` tables here, dropping ``url`` when it is
    ``""`` rather than writing an empty key. A tuple with a blank ``name`` is
    the caller's problem, not this function's: nothing downstream of a bare
    ``[[authors]]`` table treats a missing ``name`` as a landmine the way a
    malformed ``linked_libraries`` entry does, so there is nothing here to
    validate against.
    """
    unknown = set(fields) - set(EDITABLE_FIELDS)
    if unknown:
        raise HaybaleTomlError(
            f"{package_dir / HAYBALE_TOML}: {', '.join(sorted(unknown))} "
            f"{'is' if len(unknown) == 1 else 'are'} not editable here. "
            f"name/id are immutable, version/origin are set by the share wizard, "
            f"and [deprecated] is hand-edited."
        )

    if "linked_libraries" in fields:
        _validate_linked_libraries(list(fields["linked_libraries"]), package_dir / HAYBALE_TOML)

    source = package_dir / HAYBALE_TOML
    if not source.is_file():
        raise HaybaleTomlError(f"{source} not found; cannot edit a library that declares nothing.")

    with edit_toml(source) as doc:
        for key, value in fields.items():
            if key == "authors" and value:
                value = [{"name": name, **({"url": url} if url else {})} for name, url in value]
            if value in ("", [], None):
                doc.pop(key, None)
            else:
                doc[key] = value


def read_raw(package_dir: Path) -> dict[str, Any]:
    """The whole file as a plain dict, or ``{}`` when unreadable.

    For the publisher, which needs keys the runtime never loads — ``notes``,
    ``examples_path``, ``tests_path``, ``[deprecated]``. The typed readers
    deliberately return only what their consumer uses; this is the escape hatch
    for the one caller that legitimately wants everything.
    """
    source = package_dir / HAYBALE_TOML
    try:
        data = read_toml(source)
    except (toml.TomlDecodeError, OSError):
        return {}
    return dict(data) if isinstance(data, dict) else {}
