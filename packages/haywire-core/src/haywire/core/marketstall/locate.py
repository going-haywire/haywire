"""Turn a marketstall row's coordinates into a URL.

A row says which repo (``origin``), which commit (``install_spec``), and which
file (``notes``/``examples_path``/``tests_path``); it stores no URLs, so the
caller picks raw-versus-rendered at read time.

Resolution happens on the reader's machine, so a self-hosted host registered in
the reader's config resolves even when the publisher had never heard of it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal
from urllib.parse import urlparse

from haywire.core.marketstall.host_providers import resolve_host

if TYPE_CHECKING:
    from haywire.core.library.haybale import Haybale


def _ref_from_install_spec(install_spec: str) -> str | None:
    """The tag glued into a git+URL, or None."""
    spec = install_spec.strip()
    if " @ " in spec:
        spec = spec.split(" @ ", 1)[1].strip()
    if not spec.startswith("git+"):
        # A PyPI requirement ("haybale-core>=1.0") names no commit.
        return None
    spec = spec.removeprefix("git+")
    spec = spec.split("#", 1)[0].strip()
    # Everything up to "://" is the scheme; a tag is an "@" after that.
    _, _, rest = spec.partition("://")
    if "@" not in rest:
        return None
    return rest.rpartition("@")[2].strip() or None


def resolve_row_path(
    row: "Haybale",
    path: str,
    *,
    form: Literal["raw", "blob", "tree"],
) -> str | None:
    """Resolve *path* against *row*'s origin and ref.

    ``form`` picks the shape: ``"raw"`` to fetch bytes, ``"blob"`` to link a file
    in a browser, ``"tree"`` to link a directory.

    Returns None — never a guessed ref — when the host is unrecognised, the row
    lacks ``origin`` or a ref, or *path* is empty.
    """
    if not path or not row.origin or not row.install_spec:
        return None

    hostname = urlparse(row.origin).hostname
    if not hostname:
        return None
    provider = resolve_host(hostname)
    if provider is None:
        return None

    parsed = provider.parse_origin(row.origin)
    if parsed is None:
        return None
    owner, repo = parsed

    ref = _ref_from_install_spec(row.install_spec)
    if not ref:
        return None

    builder = {
        "raw": provider.raw_url,
        "blob": provider.blob_url,
        "tree": provider.tree_url,
    }[form]
    return builder(owner, repo, ref, path.lstrip("/"))


def link_form(path: str) -> Literal["blob", "tree"]:
    """Which browser form *path* wants: a trailing slash means a directory."""
    return "tree" if path.endswith("/") else "blob"


def module_dir_path(row: "Haybale") -> str:
    """The row's module directory, relative to the git root — ``barn/x/haybale_x/``.

    Built from ``install_spec``'s ``#subdirectory=`` and the module name derived
    from ``row.name``. Empty when ``install_spec`` names no subdirectory.
    """
    from haywire.core.library.haybale_toml import module_of

    spec = row.install_spec
    if "#subdirectory=" not in spec:
        return ""
    subdirectory = spec.split("#subdirectory=", 1)[1].strip()
    if not subdirectory:
        return ""
    return f"{subdirectory.rstrip('/')}/{module_of(row.name)}/"
