"""The registry of ``.hwm`` macro documents."""

import json
import logging
import re
from pathlib import Path
from typing import Optional, cast

from haywire.core.errors import HaywireException
from haywire.core.library.identity import LibraryIdentity
from haywire.core.node.identity import NodeIdentity
from haywire.core.registry.document import DocumentRegistry

from .template import MacroTemplate

logger = logging.getLogger(__name__)

#: A macro's filestem becomes its registry key and its menu entry.
_STEM_RULE = re.compile(r"[A-Za-z][A-Za-z0-9_-]*")

_MACRO_KIND = "macro"


class MacroRegistry(DocumentRegistry[MacroTemplate]):
    """Macro documents, registered as a node-like component kind.

    A file is refused rather than registered when it does not hold exactly one
    Subgraph Input and one Subgraph Output, when it contains an EVENT or
    OUTPUT node, or when placing it would close a cycle. Each refusal reports
    ``CLASS_RELOAD_FAILED`` against the document's key, so the error ledger
    points at the file.
    """

    SUFFIX = ".hwm"

    def _document_key(self, path: Path, library_identity: LibraryIdentity) -> str:
        return f"{library_identity.name}:{_MACRO_KIND}:{path.stem}"

    def add_folder(
        self,
        folder_path: str,
        library_identity: LibraryIdentity,
        exclude_patterns: Optional[list[str]] = None,
    ):
        """Register the folder's macros, skipping files whose stem cannot be a key."""
        for path in sorted(Path(folder_path).glob(f"*{self.SUFFIX}")):
            if not _STEM_RULE.fullmatch(path.stem):
                HaywireException(
                    message=(
                        f"Library '{library_identity.label}': macro '{path.name}' is skipped — a "
                        f"macro filename must start with a letter and hold only letters, digits, "
                        f"'_' or '-'."
                    ),
                    operation="Macro registry scan",
                ).log(self.logger)

        super().add_folder(folder_path, library_identity, exclude_patterns)

    def register_file(
        self,
        file_path: str,
        library_identity: LibraryIdentity,
        notify: bool = True,
    ) -> str | None:
        """Register one macro, unless its filestem breaks the naming rule."""
        if not _STEM_RULE.fullmatch(Path(file_path).stem):
            return None
        return super().register_file(file_path, library_identity, notify=notify)

    def _parse(self, path: Path, text: str, library_identity: LibraryIdentity) -> MacroTemplate:
        """Return the template ``text`` describes.

        Raises:
            ValueError: The document fails containment or would close a cycle.
            json.JSONDecodeError: The file is not a graph document.
        """
        document = json.loads(text)
        if not isinstance(document, dict):
            raise ValueError(f"'{path.name}' is not a graph document")

        registry_key = self._document_key(path, library_identity)

        ok, reason = self._validate_containment(document)
        if not ok:
            raise ValueError(reason)

        cycle = self._closes_a_cycle(registry_key, document)
        if cycle is not None:
            raise ValueError(
                f"'{path.stem}' cannot place itself: {cycle}. A macro's interior may not "
                f"reach back to the macro it belongs to."
            )

        meta = document.get("meta") or {}
        identity = NodeIdentity(
            registry_id=path.stem,
            registry_key=registry_key,
            label=path.stem,
            description=str(meta.get("description") or ""),
            class_name=path.stem,
            module=str(path),
            menu=f"{library_identity.name}/macros",
        )
        return MacroTemplate(
            document=document,
            path=path,
            content_hash=self._hash(text),
            identity=identity,
            library=library_identity,
        )

    def _validate_containment(self, document: dict) -> tuple[bool, str | None]:
        """Exactly one Subgraph Input and Output; no EVENT or OUTPUT node.

        Reads each node's ``registry_key`` against ``NodeRegistry`` rather than
        instantiating: a registry scan must not construct nodes, which would
        acquire whatever hardware their ``init`` opens. A node class that is
        not registered is skipped — an absent library is the placement's
        problem, not a malformed document.
        """
        from haywire.core.di.config import get_library_system
        from haywire.core.node.behavior import NodeType

        try:
            registry = get_library_system().get_node_registry()
        except Exception:
            # Without a node registry there is nothing to validate against;
            # the document is accepted and the placement reports what is missing.
            return (True, None)

        inputs: list[str] = []
        outputs: list[str] = []
        offenders: list[str] = []

        for node_id, entry in (document.get("nodes") or {}).items():
            cls = registry.get(str(entry.get("registry_key", "")))
            if cls is None:
                continue
            identity = cls.class_identity
            node_type = cls.class_behavior.node_type
            if NodeType.BOUNDARY in node_type:
                if identity._is_subgraph_input:
                    inputs.append(node_id)
                if identity._is_subgraph_output:
                    outputs.append(node_id)
                continue
            if NodeType.EVENT in node_type or NodeType.OUTPUT in node_type:
                offenders.append(f"{node_id} ({identity.label})")

        if offenders:
            return (
                False,
                f"A Subgraph cannot contain an EVENT or OUTPUT node. Found: {', '.join(offenders)}",
            )

        if len(inputs) != 1 or len(outputs) != 1:
            return (
                False,
                (
                    f"A Subgraph must contain exactly one Subgraph Input and one Subgraph Output "
                    f"(found {len(inputs)} input(s), {len(outputs)} output(s))"
                ),
            )

        return (True, None)

    def _closes_a_cycle(self, registry_key: str, document: dict) -> str | None:
        """Return the cycle ``document`` would close, or ``None``.

        The backstop for a file edited outside the studio; a placement made in
        the studio is refused at bind time instead.
        """
        for placed in self._macro_keys_in(document):
            if placed == registry_key:
                return f"'{registry_key}' places itself"
            if registry_key in self._macro_keys_reachable_from(placed):
                return f"'{registry_key}' → '{placed}' → '{registry_key}'"
        return None

    def _macro_keys_in(self, document: dict) -> set[str]:
        """Macro keys placed directly by this document's nodes."""
        keys = set()
        for entry in (document.get("nodes") or {}).values():
            key = str(entry.get("registry_key", ""))
            if key.split(":")[1:2] == [_MACRO_KIND]:
                keys.add(key)
        return keys

    def template(self, registry_key: str) -> MacroTemplate | None:
        """Return the template registered under ``registry_key``.

        ``get`` is typed ``type[T]`` for the class registries that share the
        base; a document registry stores instances, and this undoes that one
        cast for callers that read the template's own fields.
        """
        return cast(Optional[MacroTemplate], self.get(registry_key))

    def _macro_keys_reachable_from(self, registry_key: str) -> set[str]:
        """Every macro key reachable by following placements from ``registry_key``."""
        seen: set[str] = set()
        frontier = [registry_key]
        while frontier:
            current = frontier.pop()
            if current in seen:
                continue
            seen.add(current)
            template = self.template(current)
            if template is None:
                continue
            frontier.extend(self._macro_keys_in(template.document))
        return seen
