"""Advisory warning record carried on a node's wrapper state.

A warning is informational and, unlike an error, never makes a node invalid.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class NodeWarning:
    """One advisory notice attached to a node.

    Fields:
        message: Human-readable text shown in the badge tooltip / summary.
        source_version: For compatibility warnings, the library version the
            graph was saved with (None if the saved file predated the field).
        kind: Discriminator for the warning type. A "compatibility" warning
            implies the suggested remedy is the Reset Node action (re-derives
            the node from current code). A "previous_setup" warning means the
            node holds the data it had before a hot reload; the remedy is
            Apply or Dismiss on its card (see ``NodeWrapper.previous_setup``).
    """

    message: str
    source_version: Optional[str]
    kind: str = "compatibility"
