"""The registry of model catalog JSON files."""

import json
import logging
import re
from pathlib import Path
from typing import Any, Optional, cast

from haywire.core.errors import HaywireException
from haywire.core.library.identity import LibraryIdentity
from haywire.core.registry.document import DocumentRegistry
from haywire.core.registry.identity import BaseIdentity

from .entry import CatalogEntry, ModelFile, Resource

logger = logging.getLogger(__name__)

_CATALOG_KIND = "catalog"
#: An entry's filestem becomes its registry key. Unlike a macro's, it may start
#: with a digit: OpenModelDB names lead with the scale ("4xNomos8k").
_STEM_RULE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")
_SHA256 = re.compile(r"[0-9a-fA-F]{64}")


class CatalogRegistry(DocumentRegistry[CatalogEntry]):
    """Model catalog entries, one OpenModelDB-shaped JSON file each.

    A file is refused rather than registered when it is not a JSON object,
    lists no resources, holds a resource that names neither a source nor
    files, or carries a malformed ``sha256``. Each refusal reports
    ``CLASS_RELOAD_FAILED`` against the entry's key.
    """

    SUFFIX = ".json"

    def _document_key(self, path: Path, library_identity: LibraryIdentity) -> str:
        return f"{library_identity.name}:{_CATALOG_KIND}:{path.stem}"

    def add_folder(
        self,
        folder_path: str,
        library_identity: LibraryIdentity,
        exclude_patterns: Optional[list[str]] = None,
    ):
        """Register the folder's entries, skipping files whose stem cannot be a key."""
        for path in sorted(Path(folder_path).glob(f"*{self.SUFFIX}")):
            if not _STEM_RULE.fullmatch(path.stem):
                HaywireException(
                    message=(
                        f"Library '{library_identity.label}': model entry '{path.name}' is skipped — "
                        f"a filename must start with a letter or digit and hold only letters, digits, "
                        f"'_' or '-'."
                    ),
                    operation="Model catalog scan",
                ).log(self.logger)

        super().add_folder(folder_path, library_identity, exclude_patterns)

    def register_file(
        self,
        file_path: str,
        library_identity: LibraryIdentity,
        notify: bool = True,
    ) -> str | None:
        """Register one entry, unless its filestem breaks the naming rule."""
        if not _STEM_RULE.fullmatch(Path(file_path).stem):
            return None
        return super().register_file(file_path, library_identity, notify=notify)

    def _parse(self, path: Path, text: str, library_identity: LibraryIdentity) -> CatalogEntry:
        """Return the entry ``text`` describes.

        Raises:
            ValueError: The document breaks the entry rules.
            json.JSONDecodeError: The file is not JSON.
        """
        document = json.loads(text)
        if not isinstance(document, dict):
            raise ValueError(f"'{path.name}' is not a JSON object")

        raw_resources = document.get("resources")
        if not isinstance(raw_resources, list) or not raw_resources:
            raise ValueError(f"'{path.name}' lists no resources")
        resources = tuple(_parse_resource(path, raw) for raw in raw_resources)

        name = str(document.get("name") or path.stem)
        identity = BaseIdentity(
            registry_id=path.stem,
            registry_key=self._document_key(path, library_identity),
            label=name,
            description=str(document.get("description") or ""),
            class_name=path.stem,
            module=str(path),
            tags=_str_list(document.get("tags")),
        )
        requires = document.get("requires")
        return CatalogEntry(
            name=name,
            author=_author(document.get("author")),
            license=str(document.get("license") or ""),
            architecture=str(document.get("architecture") or ""),
            scale=_opt_int(document.get("scale")),
            purpose=_str_list(document.get("purpose")),
            tags=_str_list(document.get("tags")),
            description=str(document.get("description") or ""),
            size=_opt_int(document.get("size")),
            input_channels=_opt_int(document.get("inputChannels")),
            output_channels=_opt_int(document.get("outputChannels")),
            requires=requires if isinstance(requires, dict) else {},
            resources=resources,
            document=document,
            path=path,
            content_hash=self._hash(text),
            identity=identity,
            library=library_identity,
        )

    def entry(self, registry_key: str) -> CatalogEntry | None:
        """Return the entry registered under ``registry_key``.

        ``get`` is typed ``type[T]`` for the class registries that share the
        base; a document registry stores instances.
        """
        return cast(Optional[CatalogEntry], self.get(registry_key))

    def entries(self) -> list[CatalogEntry]:
        """Every registered entry, in key order."""
        found = (self.entry(key) for key in sorted(self.list_names()))
        return [e for e in found if e is not None]


def _author(value: Any) -> str:
    """OpenModelDB allows a string or a list of names."""
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return str(value or "")


def _str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(v) for v in value]


def _opt_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _opt_str(value: Any) -> str | None:
    return str(value) if value else None


def _digest(path: Path, value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise ValueError(f"'{path.name}': sha256 {value!r} is not 64 hex characters")
    return value.lower()


def _urls(value: Any) -> tuple[str, ...]:
    return tuple(str(u) for u in value) if isinstance(value, list) else ()


def _parse_resource(path: Path, raw: Any) -> Resource:
    if not isinstance(raw, dict):
        raise ValueError(f"'{path.name}': a resource is not an object")

    sha256 = _digest(path, raw.get("sha256"))
    size = _opt_int(raw.get("size"))
    urls = _urls(raw.get("urls"))

    raw_files = raw.get("files")
    if isinstance(raw_files, list) and raw_files:
        files = tuple(_parse_file(path, f) for f in raw_files)
    elif urls or sha256:
        files = (ModelFile("", sha256, size, urls),)
    else:
        raise ValueError(f"'{path.name}': a resource names neither urls/sha256 nor files")

    return Resource(
        platform=str(raw.get("platform") or ""),
        type=str(raw.get("type") or ""),
        size=size,
        sha256=sha256,
        urls=urls,
        files=files,
        backend=_opt_str(raw.get("backend")),
        precision=_opt_str(raw.get("precision")),
    )


def _parse_file(path: Path, raw: Any) -> ModelFile:
    if not isinstance(raw, dict):
        raise ValueError(f"'{path.name}': a bundle file is not an object")
    return ModelFile(
        path=str(raw.get("path") or ""),
        sha256=_digest(path, raw.get("sha256")),
        size=_opt_int(raw.get("size")),
        urls=_urls(raw.get("urls")),
    )
