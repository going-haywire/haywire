# packages/haywire-core/src/haywire/ui/editor_framework/decorator.py
"""
@editor decorator for marking classes as Haywire editor types.

Sets class_identity on the class. Does NOT register the class —
registration happens when the library calls add_folder() in
register_components(), following the same pattern as @renderer and @widget.

For built-in framework editors, registration is bootstrapped directly
in the DI provider via register_builtin_editors().
"""

from typing import Any, Union

from haywire.core.access import AccessTier
from haywire.core.library.utils import EDITOR, derive_library_identity, reg_key

from .base import BaseEditor
from .identity import EditorIdentity, OpenBehavior, SlotName


def editor(**kwargs: Any):
    """
    Decorator to mark a class as an editor type.

    Always invoked with parentheses — `@editor(...)` or `@editor()`. The
    bare `@editor` form (no parens) is not supported.

    Sets class_identity on the class. Does NOT register the class —
    registration happens when the library calls add_folder() in
    register_components(), following the same pattern as @renderer and @widget.

    For built-in framework editors, registration is bootstrapped directly
    in the DI provider via register_builtin_editors().

    Accepted keys (splatted into ``EditorIdentity``; an unknown key raises
    ``TypeError`` at class-definition time):
        label: Human-readable display name. Defaults to class name.
        icon: Material Design icon name. Defaults to 'extension'.
        default_slot: Which slot this editor belongs in by default. A
            :class:`SlotName` or its string value — one of 'action',
            'context', 'edit', 'info'. Defaults to ``SlotName.EDIT``. An
            unknown value raises ``ValueError`` at class-definition time.
        opens: Instance-creation behavior. One of 'required', 'on_context',
            'on_payload'. Defaults to 'required'. Any value is permitted on
            any default_slot — choosing a UX-sensible pairing is up to the
            editor author.
        access: Minimum AccessTier needed to see this editor — an
            :class:`AccessTier` or its string value ('view', 'edit', 'admin').
            Defaults to 'view'. An unknown value raises ``ValueError`` at
            class-definition time.
        order: Sort priority within a slot (lower = earlier in the bar).
            Defaults to 100. Editors with equal order fall back to
            registration order.
        description: Human-readable description.
        registry_id: Unique ID for this editor, e.g. 'graph_editor'.
            Defaults to the class name if not provided.
        deprecation_warning: Optional human-readable message shown when this
            editor is listed anywhere. Empty string means not deprecated.
        hidden: When True, the editor is registered and usable but excluded
            from author-facing selection UIs. See the glossary term
            **Hidden component**.

    ``registry_key``, ``class_name`` and ``module`` are derived by the
    decorator and must not be passed. ``default_slot`` / ``opens`` accept the
    enum or its string value and are coerced here.

    Usage:
        @editor(
            label='Graph Editor',
            icon='account_tree',
            default_slot='edit',
            opens='on_payload',
            description='Visual node graph editor',
        )
        class GraphEditor(BaseEditor):
            ...
    """

    def decorator(inner_cls):
        if not issubclass(inner_cls, BaseEditor):
            raise TypeError(f"@editor can only be applied to BaseEditor subclasses, got {inner_cls}")

        identity_kwargs = dict(kwargs)

        # Coerce strings to enums; raises ValueError at class-definition time on typo.
        default_slot: Union[SlotName, str] = identity_kwargs.pop("default_slot", SlotName.EDIT)
        opens: Union[OpenBehavior, str] = identity_kwargs.pop("opens", OpenBehavior.REQUIRED)
        identity_kwargs["opens"] = OpenBehavior(opens) if isinstance(opens, str) else opens
        identity_kwargs["default_slot"] = (
            SlotName(default_slot) if not isinstance(default_slot, SlotName) else default_slot
        )

        # Coerce access to enum; raises ValueError at class-definition time on typo.
        access: Union[AccessTier, str] = identity_kwargs.pop("access", AccessTier.VIEW)
        identity_kwargs["access"] = AccessTier(access) if isinstance(access, str) else access

        _registry_id = identity_kwargs.pop("registry_id", None) or inner_cls.__name__
        _label = identity_kwargs.pop("label", None) or inner_cls.__name__

        library_identity = derive_library_identity(inner_cls)
        _registry_key = reg_key(library_identity.name, EDITOR, _registry_id)

        # Remaining keys (icon, order, description, deprecation_warning, hidden, …)
        # splat straight into the identity; an unknown key surfaces as a TypeError.
        inner_cls.class_identity = EditorIdentity(
            registry_id=_registry_id,
            registry_key=_registry_key,
            label=_label,
            class_name=inner_cls.__name__,
            module=inner_cls.__module__,
            **identity_kwargs,
        )
        inner_cls.class_library = library_identity
        return inner_cls

    return decorator
