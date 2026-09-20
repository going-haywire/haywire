"""``MacroNode`` — the card standing for a macro placed in a graph.

A Graph-node whose interior comes from a file rather than from the host graph.
Each placement instantiates the template into its own ``SubgraphDefinition``,
keyed by the card's node id, so two cards standing for one macro never share
nodes. That interior is runtime state: the host serializes the card and its
port values, and rebuilds the interior from the template on load.

Saving the macro file reloads the template, which every placement absorbs in
place — the values and label the user set survive, because the node is never
rebuilt. See ADR 0038.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from haywire.core.node import node, NodeType
from haywire.core.graph.scheduler import SyncScheduler

from .graph_node import GraphNode

if TYPE_CHECKING:
    from haywire.core.macro.template import MacroTemplate
    from haywire.core.node.identity import NodeIdentity
    from haywire.core.registry.lifecycle_event import LifeCycleEvent

logger = logging.getLogger(__name__)

#: Prefix of a placement's derived Subgraph key.
_KEY_PREFIX = "macro_"


@node(
    label="Macro",
    description="A card standing for a macro: a Subgraph that lives in its own file.",
    node_type=NodeType.CONTROL,
    hidden=True,
    is_mutable=True,
    _is_macro_node=True,
    # Cleared explicitly: identity flags are inherited from the base class, and
    # leaving this set would make a placement the registry's Graph-node — so
    # collapsing a selection into a Group would build a macro card instead.
    _is_graph_node=False,
)
class MacroNode(GraphNode):
    """One placement of a macro template.

    Differs from a Group's card in what owns the interior: a Group's Subgraph
    lives in the host file and is the card's alone, while a macro's lives in
    its own file and is shared by every placement as a template. The card still
    owns its port values.
    """

    @property
    def identity(self) -> "NodeIdentity":
        """The template's identity, not this class's.

        Every placement of every macro is an instance of this one class, so the
        class identity says only "Macro". The name, description and menu path a
        user sees belong to the template the card stands for; falling back to
        the class identity covers a placement whose template is absent.
        """
        template = self._template()
        if template is None:
            return super().identity
        return template.class_identity

    @property
    def subgraph_key(self) -> str | None:
        """The key of this placement's interior, derived from the card's node id.

        Never read from the store: a derived key cannot be copied onto a second
        card, so pasting a placement yields a second interior rather than two
        cards sharing one.
        """
        wrapper = self.wrapper
        if wrapper is None:
            return None
        return f"{_KEY_PREFIX}{wrapper.node_id}"

    def bind_subgraph(self, key: str) -> None:
        """Not available: a placement's interior is keyed by its own node id."""
        raise RuntimeError(
            f"'{self.identity.label}' derives its Subgraph key from its node id and "
            f"cannot be bound to '{key}'."
        )

    def post_init(self) -> None:
        self._instantiate_from_template()
        super().post_init()

    def _template(self) -> "MacroTemplate | None":
        """The registered template this card stands for, or ``None`` if absent."""
        wrapper = self.wrapper
        if wrapper is None:
            return None
        try:
            from haywire.core.di.config import get_library_system

            registry = get_library_system().get_macro_registry()
        except Exception:
            return None
        return registry.template(wrapper.registry_key)

    def _instantiate_from_template(self) -> None:
        """Build this placement's interior from the template.

        Replaces any interior already standing under the derived key, so a
        reload swaps the contents without the card noticing a new definition.
        """
        from haywire.core.graph.subgraph import SubgraphDefinition

        wrapper = self.wrapper
        key = self.subgraph_key
        if wrapper is None or wrapper.graph is None or key is None:
            return

        template = self._template()
        if template is None:
            # An uninstalled library: the card keeps the pins restored from the
            # host file, and validation reports the missing interior.
            return

        host = wrapper.graph
        if host.get_subgraph(key) is not None:
            host.remove_subgraph(key)

        definition = SubgraphDefinition(
            key=key,
            label=template.class_identity.label,
            validation_scheduler=SyncScheduler(),
        )
        definition.template_key = wrapper.registry_key
        host.add_subgraph(definition)
        definition.instantiate(template.nodes, template.edges, template.subgraphs)

    def _on_label_changed(self, _value: object, _old: object) -> None:
        """A no-op: the interior's name belongs to the template, not to a card.

        A Group's card renames its Subgraph because it is the only card that
        stands for it. Doing that here would rename one placement's interior
        out of step with every other placement of the same macro.
        """

    def on_class_reloaded(self, event: "LifeCycleEvent") -> bool:
        """Swap the interior for the reloaded template, keeping values and label.

        The generic rebuild would run ``init()`` and discard both. Reconciling
        is the path an edit inside a Group's Subgraph already takes, so a pin
        that survives keeps its edges and a pin that is gone drops them to the
        ghost pin.
        """
        self._instantiate_from_template()
        self.reconcile_interface()
        return True
