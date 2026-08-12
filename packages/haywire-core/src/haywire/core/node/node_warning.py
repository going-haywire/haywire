"""Advisory warning record carried on a node's wrapper state.

Distinct from errors (which make a node invalid). A warning is informational;
the first writer is the Compatibility Warning feature (kind="compatibility").
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
        kind: Discriminator for the warning type. "compatibility" today;
            a "compatibility" warning implies the suggested remedy is the
            Reset Node action (re-derives the node from current code).
    """

    message: str
    source_version: Optional[str]
    kind: str = "compatibility"
