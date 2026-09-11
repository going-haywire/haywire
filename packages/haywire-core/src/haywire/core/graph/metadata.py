# haywire/core/graph/metadata.py
"""GraphMetadata — framework-provided per-graph document metadata (``graph.meta``).

A settings bag holding the editable half of a graph's metadata, so the settings
framework owns its editing, serialization and change propagation. It declares no
``shadow()`` fields and no node-side mirrors, so it is document data, not a
settings tier.

The framework-written fields (``filestem``, ``created_at``, ``modified_at``) are
not in the bag; a bag renderer draws every field it holds as editable.

Serialized under the ``'meta'`` key in graph JSON.
"""

from haywire.barn.builtin.types import STRING
from haywire.core.settings.descriptor import setting
from haywire.core.settings.settings_graph import GraphSettings


class GraphMetadata(GraphSettings):
    """Editable document metadata available on every graph as ``graph.meta``."""

    label = setting[STRING](
        "",
        label="Label",
        description=(
            "Free-text title for this graph. Has no navigation role — tabs and "
            "haystack rows stay filename-derived."
        ),
        category="metadata",
        order=10,
    )

    description = setting[STRING](
        "",
        label="Description",
        description="What this graph is for.",
        category="metadata",
        order=20,
    )

    author = setting[STRING](
        "",
        label="Author",
        description="Who wrote this graph. Blank until typed — never auto-populated.",
        category="metadata",
        order=30,
    )

    version = setting[STRING](
        "1.0.0",
        label="Version",
        description="Author-managed version of this graph's design. NOT the file format version.",
        category="metadata",
        order=40,
    )
