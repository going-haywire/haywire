# haywire/core/graph/metadata.py
"""
GraphMetadata — framework-provided per-graph document metadata (``graph.meta``).

The editable half of a graph's metadata: who wrote it, what it is for, what
they call it. A settings bag rather than four plain attributes so the
settings framework owns editing (``render_settings`` draws the whole bag),
serialization and change propagation.

Unlike its sibling ``graph.props``, this bag declares no ``shadow()`` fields
and no node-side mirrors — it is plain per-graph document data, not a
settings tier. That is why its restore order relative to nodes is
unconstrained.

The framework-written fields (``filestem``, ``created_at``, ``modified_at``)
deliberately stay OUT of the bag: they have no setter, and a generic bag
renderer draws every field as editable.

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
