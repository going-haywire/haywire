"""Helpers for node authors: resolve a MODEL_REF port and hold its loaded model per run."""

from __future__ import annotations

from collections.abc import Callable, Hashable
from typing import TYPE_CHECKING, TypeVar

from haywire.core.di.context import get_library_state_container
from haywire.core.node.node_warning import NodeWarning

from haybale_models.matcher import Preference
from haybale_models.resolver import ModelMissing, ResolvedModel, resolve
from haybale_models.state.models_state import ModelsState
from haybale_models.value.model_ref import ModelRef

if TYPE_CHECKING:
    from haywire.core.node.base import BaseNode

__all__ = [
    "KIND",
    "MISSING_WARNING",
    "ModelMissing",
    "acquire_port",
    "models_state",
    "preference_for",
    "release_node",
    "resolve_port",
]

T = TypeVar("T")

KIND = "model"
MISSING_WARNING = NodeWarning(message="Model missing — Show in Models", source_version=None, kind=KIND)


def models_state() -> ModelsState:
    """The app-wide :class:`ModelsState`.

    Raises:
        RuntimeError: If haybale-models is not enabled.
    """
    state = get_library_state_container().get(ModelsState)
    if state is None:
        raise RuntimeError("haybale-models is not enabled")
    return state


def preference_for(node: BaseNode, port_id: str) -> Preference:
    """The variant preference for *port_id*.

    The node's ``model_preference(port_id)`` if it defines one, else the port's ``prefer``
    property, else ``[{}]``.
    """
    hook = getattr(node, "model_preference", None)
    if callable(hook):
        return hook(port_id)  # type: ignore[no-any-return]
    prefer = node.ports[port_id].widget_config.get("properties", {}).get("prefer")
    return list(prefer) if prefer else [{}]


def resolve_port(node: BaseNode, port_id: str) -> ResolvedModel:
    """Resolve the model on *port_id* and set the node's ``"model"`` warnings.

    All ``MODEL_REF`` ports of one node share a single ``"model"`` warning list, so with
    several ports the last call wins. Key the list per port when a two-port consumer lands.

    Raises:
        ModelMissing: If no local file matches the reference.
    """
    state = models_state()
    value = node.ports[port_id].get_value()
    ref = value if isinstance(value, ModelRef) else ModelRef.from_dict(value or {})
    try:
        resolved = resolve(
            ref,
            preference_for(node, port_id),
            catalog=state.catalog,
            index=state.index,
            hf_cache=state.hf_cache,
        )
    except ModelMissing:
        node.wrapper.replace_warnings(KIND, [] if ref.is_empty else [MISSING_WARNING])
        raise
    node.wrapper.replace_warnings(KIND, _warnings(resolved))
    return resolved


def _warnings(resolved: ResolvedModel) -> list[NodeWarning]:
    messages: list[str] = []
    if resolved.better_unfetched is not None:
        variant = resolved.better_unfetched.variant_name()
        messages.append(f"Preferred variant {variant} is not downloaded — Show in Models")
    if resolved.ref.is_file and not resolved.ref.sha256:
        messages.append("Not pinned — use the pin on the card")
    return [NodeWarning(message=m, source_version=None, kind=KIND) for m in messages]


def acquire_port(
    node: BaseNode,
    port_id: str,
    *,
    variant_key: Hashable,
    load: Callable[[ResolvedModel], T],
    release: Callable[[T], None],
) -> T:
    """Resolve *port_id* and hold its loaded model for *node*; nodes share one load per key."""
    resolved = resolve_port(node, port_id)
    return models_state().pool.acquire(
        (resolved.key, variant_key), node, load=lambda: load(resolved), release=release
    )


def release_node(node: BaseNode) -> None:
    """Drop *node*'s holds. Call from ``on_shutdown`` and, as a backstop, ``on_teardown``."""
    models_state().pool.release(node)
