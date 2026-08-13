"""@farmhand — stamps FarmhandIdentity. Follows the @node decorator shape
(node/decorator.py:70): freeform **kwargs splatted into the identity dataclass,
class-name defaults via setdefault, kind constant from library/utils."""

from __future__ import annotations

import inspect
from typing import Any, Callable, Type, TypeVar

from haywire.core.farmhand.base import Farmhand
from haywire.core.farmhand.identity import FarmhandIdentity, ToolAnnotations
from haywire.core.library.utils import FARMHAND, derive_library_identity, reg_key

T = TypeVar("T")


def farmhand(**kwargs: Any) -> Callable[[Type[T]], Type[T]]:
    """
    Decorator to register a class as a Farmhand (a haywire MCP tool).

    Always invoked with parentheses — `@farmhand(...)` or `@farmhand()`.
    Accepts FarmhandIdentity fields as keyword arguments; unknown keys raise
    in the dataclass constructor.

    Identity Fields (metadata):
        label (str): Human-readable display name. Default: registry_id
        description (str): SHORT human-facing blurb — shown in generated docs
            (OVERVIEW.md/QUICKREF.md) and the studio_list_components catalog,
            same role it plays for every other component kind. NOT sent to
            MCP clients — see instructions below. Default: ""
        instructions (str): REQUIRED. The text sent verbatim as the MCP
            Tool.description — the only thing an agent reads to decide
            whether/how to call this tool, since derived input schemas carry
            no per-parameter descriptions. Write it for an LLM, not a human:
            cover what the tool does, when to use it (and when not to),
            parameter semantics/gotchas, and worked examples where the
            argument shape isn't obvious. Omitting it raises TypeError from
            the FarmhandIdentity constructor — a farmhand tool with no
            instructions is unusable to the agents it exists for.
        registry_id (str): Unique identifier within library. Default: class name.
            The MCP-visible tool name is {lib_id}_{registry_id}, so pass a
            snake_case registry_id (e.g. registry_id="save_graph").
        annotations (ToolAnnotations): MCP consent hints
            (read_only_hint/destructive_hint/...). Default: ToolAnnotations()
        hidden (bool): Exclude from author-facing selection UIs. Default: False
        deprecation_warning (str): Advisory message. Default: ""

    The library identity derives from the defining module; the studio_*
    baseline is simply barn/haybale-studio's farmhands/ folder — its library
    id IS 'studio', so no special registration path exists.

    Example:

    .. code-block:: python

        @farmhand(
            label="Save graph",
            description="Save an open graph.",
            instructions=(
                "Save an open graph; save_as writes to a new path instead of "
                "overwriting. Call haystack_list_graphs first if binding_id is "
                "unknown — it is not the same as the graph's display name."
            ),
            registry_id="save_graph",
            annotations=ToolAnnotations(),
        )
        class SaveGraphTool(Farmhand):
            async def run(self, ctx, binding_id: str, save_as: str | None = None) -> dict:
                ...
    """

    def decorator(inner_cls: Type[T]) -> Type[T]:
        if not (inspect.isclass(inner_cls) and issubclass(inner_cls, Farmhand)):
            raise TypeError(f"@farmhand can only be applied to Farmhand subclasses, got {inner_cls}")
        if not inspect.iscoroutinefunction(inner_cls.run):
            raise TypeError(
                f"{inner_cls.__name__}.run must be async — the MCP SDK thread-offloads "
                f"sync functions, breaking loop affinity."
            )

        identity_kwargs: dict[str, Any] = dict(kwargs)

        # Set defaults from class name if not provided (the @node idiom)
        identity_kwargs.setdefault("registry_id", inner_cls.__name__)
        identity_kwargs.setdefault("label", identity_kwargs["registry_id"])
        identity_kwargs.setdefault("annotations", ToolAnnotations())

        # Get library identity (survives hot-reload)
        library_identity = derive_library_identity(inner_cls)

        # Auto-derive registry_key
        identity_kwargs["registry_key"] = reg_key(
            library_identity.name, FARMHAND, identity_kwargs["registry_id"]
        )

        # Set source info from the class itself
        identity_kwargs["class_name"] = inner_cls.__name__
        identity_kwargs["module"] = inner_cls.__module__

        inner_cls.class_identity = FarmhandIdentity(**identity_kwargs)
        inner_cls.class_library = library_identity
        return inner_cls

    return decorator
