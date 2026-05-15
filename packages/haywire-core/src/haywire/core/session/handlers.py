# packages/haywire-core/src/haywire/core/session/handlers.py
"""
Method-level signal-handler decorators for editors.

Editor authors declare which :class:`~haywire.core.session.signals.Signal`
subclasses a handler method should fire on by decorating the method:

    from haywire.core.session import Signal, SelectionMoved, GraphDataMutated
    from haywire.core.session.handlers import redraw_on, react_on
    from haywire.ui.editor import editor, BaseEditor

    @editor(label="Properties", ...)
    class PropertiesEditor(BaseEditor):

        @redraw_on(SelectionMoved, GraphDataMutated)
        def _refresh(self, ctx, signal):
            ...   # framework triggers wrapper.redraw() after this returns

        @react_on(EntityRemoved)
        def _on_remove(self, ctx, signal):
            ...   # pure side-effect; no auto-redraw

Two flavors, semantically distinct:

- ``@redraw_on(*signal_types)`` — the framework calls ``wrapper.redraw()``
  after the handler returns. Multiple ``@redraw_on`` handlers matching the
  same signal still trigger exactly one redraw per dispatch pass.
- ``@react_on(*signal_types)`` — pure side-effect channel. Framework does
  not auto-redraw. The author is responsible for any explicit
  ``wrapper.redraw()`` / ``wrapper.force_close()`` /
  ``session.publish(Reveal/Close/...)`` calls inside the handler body.

Both kinds fire regardless of whether the editor's wrapper is the active
tab. Backgrounded editors (kept alive by Quasar ``ui.tab_panels`` keep-alive)
stay current; on focus they are already drawn correctly.

The decorators store metadata on the function object — the framework
introspects decorated methods at editor-class registration time by walking
the class MRO. Authors choose any method name; the decorator is the only
marker. There is no abstract handler method on ``BaseEditor`` to override.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Literal, Tuple

from .signals import Signal


# The two kinds of decorated handler. Tagged on each (method, signal_type)
# binding produced by :func:`discover_handlers`. ``redraw_on`` triggers a
# ``wrapper.redraw()`` after the handler returns; ``react_on`` does not.
HandlerKind = Literal["redraw_on", "react_on"]


# Attribute names used on decorated function objects. The framework reads
# these at editor-class registration time. Names are deliberately namespaced
# to avoid collision with other decorator metadata.
_REDRAW_ON_ATTR = "_haywire_redraw_on"
_REACT_ON_ATTR = "_haywire_react_on"


def validate_signal_types(
    context: str,
    args: Tuple[Any, ...],
    *,
    allow_empty: bool = False,
) -> Tuple[type, ...]:
    """Validate ``args`` are Signal subclasses; return them as a tuple.

    Catches the two most common authoring mistakes at decoration time
    (which fires at module-import, so errors surface during app startup
    rather than when the signal happens to fire):

    - Passing a signal *instance* instead of the class:
        ``@redraw_on(SelectionMoved())``  →  TypeError
    - Passing a non-signal type:
        ``@redraw_on(str)``  →  TypeError

    Args:
        context: Human-readable label for the error message, e.g.
            ``"@redraw_on(...)"`` or ``"@panel(..., redraw_on=...)"``.
        args:    Positional argument tuple to validate.
        allow_empty: When ``False`` (default), an empty ``args`` raises
            ``TypeError``. Set ``True`` for kwargs that legitimately
            default to an empty tuple (e.g. ``@panel(redraw_on=())``).
    """
    if not args and not allow_empty:
        raise TypeError(f"{context} requires at least one Signal subclass; got none.")
    bad: list[str] = []
    for a in args:
        if not isinstance(a, type):
            bad.append(f"{a!r} (not a type)")
        elif not issubclass(a, Signal):
            bad.append(f"{a.__name__} (not a Signal subclass)")
    if bad:
        raise TypeError(f"{context} arguments must be Signal subclasses; got: {', '.join(bad)}")
    return args


def redraw_on(*signal_types: Any) -> Callable[[Callable[..., None]], Callable[..., None]]:
    """Decorate an editor method to fire on the listed signal types, with auto-redraw.

    The framework subscribes the decorated method to each ``signal_type`` on the
    owning editor's per-session bus at editor instantiation. When any of those
    signals publish, the framework calls the handler, then triggers
    ``self.wrapper.redraw()`` once per dispatch pass (even if multiple
    ``@redraw_on`` handlers on this editor match the same signal).

    Both kinds fire regardless of active state — backgrounded editors stay
    current via the same dispatch path.

    Args:
        *signal_types: Signal subclasses OR synthetic signal_field
            classes (e.g. ``SessionContext.active_file``). Validated at
            decoration time as ``Signal``; passing an instance or non-signal
            type raises ``TypeError``. Runtime dispatch matches the exact
            class.

    Returns:
        A decorator that returns the original function unchanged with metadata
        attached as ``func._haywire_redraw_on = (signal_types, ...)``.
    """
    validated = validate_signal_types("@redraw_on(...)", signal_types)

    def decorator(func: Callable[..., None]) -> Callable[..., None]:
        # Allow stacking with @react_on: store as tuple, append if already present.
        existing = getattr(func, _REDRAW_ON_ATTR, ())
        setattr(func, _REDRAW_ON_ATTR, existing + validated)
        return func

    return decorator


def react_on(*signal_types: Any) -> Callable[[Callable[..., None]], Callable[..., None]]:
    """Decorate an editor method to fire on the listed signal types, side-effect only.

    The framework subscribes the decorated method to each ``signal_type`` on the
    owning editor's per-session bus at editor instantiation. When any of those
    signals publish, the framework calls the handler — and does *nothing else*.
    The author is responsible for any explicit ``self.wrapper.redraw()`` /
    ``self.wrapper.force_close()`` / ``session.publish(Reveal/Close/...)`` calls inside
    the handler body.

    Both kinds fire regardless of active state.

    Args:
        *signal_types: Signal subclasses OR synthetic signal_field
            classes (e.g. ``SessionContext.active_file``). Validated at
            decoration time as ``Signal``; passing an instance or non-signal
            type raises ``TypeError``. Runtime dispatch matches the exact
            class.

    Returns:
        A decorator that returns the original function unchanged with metadata
        attached as ``func._haywire_react_on = (signal_types, ...)``.
    """
    validated = validate_signal_types("@react_on(...)", signal_types)

    def decorator(func: Callable[..., None]) -> Callable[..., None]:
        existing = getattr(func, _REACT_ON_ATTR, ())
        setattr(func, _REACT_ON_ATTR, existing + validated)
        return func

    return decorator


def get_redraw_on_types(func: Callable[..., Any]) -> Tuple[type[Signal], ...]:
    """Return the tuple of signal types a method was decorated with via :func:`redraw_on`.

    Returns an empty tuple if the method was not decorated. The framework uses
    this to discover handlers at editor-class registration time.
    """
    return getattr(func, _REDRAW_ON_ATTR, ())


def get_react_on_types(func: Callable[..., Any]) -> Tuple[type[Signal], ...]:
    """Return the tuple of signal types a method was decorated with via :func:`react_on`.

    Returns an empty tuple if the method was not decorated. The framework uses
    this to discover handlers at editor-class registration time.
    """
    return getattr(func, _REACT_ON_ATTR, ())


# ----------------------------------------------------------------------
# Class-level handler discovery
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class HandlerBinding:
    """A single (method, kind) pair for one signal type on one class.

    Produced by :func:`discover_handlers`. The framework wraps each binding
    in a per-instance closure at editor instantiation: the closure looks up
    ``method_name`` on the instance (so subclass overrides resolve via MRO),
    calls it with ``(ctx, signal)``, and — if ``kind == "redraw_on"`` —
    calls ``wrapper.redraw()`` after.

    Stored by name rather than by function object: subclasses can override
    an inherited decorated method without re-decorating, and the framework
    still calls the subclass's version. (The override silently removes the
    subscription if it isn't re-decorated; matches normal Python override
    semantics.)
    """

    method_name: str
    kind: HandlerKind


# Cache attribute name. Stored on the class via setattr so a hot-reload
# (which produces a fresh class object) drops the cache automatically.
_HANDLER_INDEX_ATTR = "_haywire_handler_index"


def discover_handlers(cls: type) -> Dict[type[Signal], List[HandlerBinding]]:
    """Walk ``cls.__mro__`` and index every ``@redraw_on`` / ``@react_on``-decorated method.

    Returns a mapping ``signal_type → [HandlerBinding, ...]`` covering every
    method decorated anywhere in the inheritance chain. Method-name collisions
    across the MRO (the natural Python override case) resolve to the leaf
    method — only the first occurrence walking from subclass to base is kept.
    A subclass that redefines an inherited decorated method *without* re-
    decorating effectively removes its subscriptions.

    The result is cached on the class as ``cls._haywire_handler_index``. A
    hot-reload that replaces ``cls`` with a fresh class object naturally
    rebuilds the cache on next access — there is no separate invalidation
    hook to wire.

    Args:
        cls: A class (typically an editor class derived from ``BaseEditor``).

    Returns:
        Mapping of signal-type → list of bindings, ordered by MRO walk
        (subclass-first). Empty mapping if no decorated methods are found.
    """
    cached = cls.__dict__.get(_HANDLER_INDEX_ATTR)
    if cached is not None:
        return cached  # type: ignore[no-any-return]

    seen_names: set[str] = set()
    index: Dict[type[Signal], List[HandlerBinding]] = {}

    for klass in cls.__mro__:
        # Iterate the raw __dict__ rather than ``dir(klass)`` so we see
        # functions as functions (not bound methods) and avoid picking up
        # MRO entries that descriptor-protocol-rebind in odd ways.
        for name, value in klass.__dict__.items():
            if not callable(value):
                continue
            if name in seen_names:
                continue
            # Mark *every* callable name as seen during the MRO walk so that
            # a subclass override (decorated or not) shadows the inherited
            # base method's bindings. An undecorated override therefore
            # silently strips the subscription.
            seen_names.add(name)
            redraw_types = get_redraw_on_types(value)
            react_types = get_react_on_types(value)
            if not redraw_types and not react_types:
                continue
            for et in redraw_types:
                index.setdefault(et, []).append(HandlerBinding(name, "redraw_on"))
            for et in react_types:
                index.setdefault(et, []).append(HandlerBinding(name, "react_on"))

    # Cache on the leaf class only — base classes keep their own cache if
    # they're ever discovered directly. Use setattr so the cache survives
    # ``__slots__``-using classes (none today, but cheap insurance).
    try:
        setattr(cls, _HANDLER_INDEX_ATTR, index)
    except (AttributeError, TypeError):
        # Class doesn't allow attribute setting (e.g. an exotic builtin
        # passed in by a test). Skip caching; correctness is unaffected.
        pass
    return index
