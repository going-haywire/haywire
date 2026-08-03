"""Comment-preserving TOML editing for files a human wrote.

``toml.loads`` parses to plain dicts, so ``toml.dumps`` rebuilds the document
from scratch — every comment, blank line, key order and array style is lost.
For a file the framework generates and owns that is harmless. For a user's
``pyproject.toml`` it is data loss: installing a library would silently strip
the comments explaining why each dependency is pinned.

The dividing line is whether a source document exists that someone may have
edited by hand:

* **Use** :func:`edit_toml` when changing part of an existing file — a
  project's ``pyproject.toml``, a library author's ``pyproject.toml``, a
  hand-editable ``marketplace.toml``.
* **Keep ``toml.dumps``** when serializing a fresh document the framework owns
  end to end (``serialize_project_marketplace``, the generated marketstall
  feed, config scaffolding). There is no prior text, so nothing can be lost.

``toml`` also remains correct for read-only parsing.

    with edit_toml(path) as doc:
        doc["project"]["dependencies"].append("haybale-foo~=1.0")

The document is written back on clean exit only — an exception inside the
block leaves the file untouched, so a half-applied edit cannot be persisted.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

import toml
import tomlkit

logger = logging.getLogger(__name__)

__all__ = ["edit_toml", "read_toml", "write_toml"]


def read_toml(path: Path) -> Any:
    """Parse *path* into a tomlkit document, preserving its formatting.

    The result behaves like a dict for reads and writes; hand it to
    :func:`write_toml` to persist it with comments intact.

    Raises ``toml.TomlDecodeError`` on a malformed file, NOT tomlkit's own
    ``ParseError``. Callers across the codebase already catch the former —
    the share pipeline translates it into a user-facing "this file is
    malformed" message — and switching the parser underneath them must not
    silently change which exception they have to handle.
    """
    text = path.read_text(encoding="utf-8")
    try:
        return tomlkit.parse(text)
    except tomlkit.exceptions.ParseError as exc:
        raise toml.TomlDecodeError(str(exc), text, 0) from exc


def write_toml(path: Path, document: Any) -> None:
    """Serialize *document* back to *path*, preserving comments and layout.

    Only meaningful for a document that came from :func:`read_toml` — a plain
    dict has no formatting to preserve, and writing one here is equivalent to
    ``toml.dumps``.
    """
    path.write_text(tomlkit.dumps(document), encoding="utf-8")


@contextmanager
def edit_toml(path: Path) -> Iterator[Any]:
    """Read *path*, yield its document for mutation, write it back.

    The write happens on clean exit only. If the block raises, the file is
    left exactly as it was — relevant because these edits run inside
    best-effort install/uninstall paths where a partial write would be worse
    than no write at all.
    """
    document = read_toml(path)
    yield document
    write_toml(path, document)
