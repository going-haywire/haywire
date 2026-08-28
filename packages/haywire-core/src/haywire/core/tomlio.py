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

__all__ = ["edit_toml", "plain", "read_toml", "write_toml"]


def plain(value: Any) -> Any:
    """Strip tomlkit's wrapper types, recursively — builtins all the way down.

    :func:`read_toml` parses with tomlkit so a document can be written back
    with its comments intact. The price is that tomlkit's types *subclass* the
    builtins: ``tomlkit.items.String`` IS a ``str``, ``Array`` IS a ``list``.
    They pass every ``isinstance`` check, compare equal to their plain
    counterparts, and ``repr`` identically — so nothing looks wrong at the point
    you read them. They misbehave later, in two ways that look unrelated:

    * **Serializing.** ``toml.dumps`` does not recognise the subclass, falls
      back to treating it as a sequence, and writes ``version = ["0", ".", "0",
      ".", "3", "6"]`` where ``version = "0.0.36"`` was meant. The output is
      still valid TOML, so the corruption surfaces only when a *consumer*
      parses it and finds the field is not a string. `haywire share` shipped
      published marketstalls this way; the CI generator escaped it only because
      it hand-formats its output instead of using ``toml.dumps``.
    * **Comparing containers.** Older tomlkit compared an ``Array`` *unequal*
      to a plain list of the same content, so a diff against freshly-built data
      reported drift that was not there. Not reproducible on 0.15.1, where every
      container compares equal — but ``publishing.generate`` still normalises
      both sides of its drift comparison, which is worth keeping: it makes the
      result independent of equality semantics that have already changed once.

    Normalise at the boundary where tomlkit data stops being a document to edit
    and starts being data to use, not at each writer. Both symptoms above were
    found and patched separately, in different modules, by people who did not
    know about the other — one of the patches was even called ``_plain`` too.

    ``bool`` is checked before ``int`` because it is a subclass of it. Anything
    this does not know about (dates) passes through untouched, since ``toml``
    serializes those correctly and ``datetime`` compares fine.
    """
    if isinstance(value, dict):
        return {str(key): plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(item) for item in value]
    if isinstance(value, bool):
        return bool(value)
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        return float(value)
    if isinstance(value, str):
        return str(value)
    return value


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
