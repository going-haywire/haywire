# packages/haywire-core/src/haywire/core/session/handlers.py
"""
Method-level signal-handler decorators for editors.

Editor authors declare which :class:`~haywire.core.signals.Signal`
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

A third decorator, ``@reveal_on(*RevealSignal_subclasses)``, is class-level
rather than instance-level: the AppShell reads it off registered editor
*classes*, so it fires even when the editor has no instance yet (and the
reveal creates the tab). See :func:`reveal_on`.

The decorators store metadata on the function object — the framework
introspects decorated methods at editor-class registration time by walking
the class MRO. Authors choose any method name; the decorator is the only
marker. There is no abstract handler method on ``BaseEditor`` to override.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Literal, Tuple

from haywire.core.signals import Signal


# The two kinds of decorated handler. Tagged on each (method, signal_type)
# binding produced by :func:`discover_handlers`. ``redraw_on`` triggers a
# ``wrapper.redraw()`` after the handler returns; ``react_on`` does not.
HandlerKind = Literal["redraw_on", "react_on"]


# Attribute names used on decorated function objects. The framework reads
# these at editor-class registration time. Names are deliberately namespaced
# to avoid collision with other decorator metadata.
_REDRAW_ON_ATTR = "_haywire_redraw_on"
_REVEAL_ON_ATTR = "_haywire_reveal_on"
_REACT_ON_ATTR = "_haywire_react_on"


def validate_signal_types(
    context: str,
    args: Tuple[Any, ...],
    *,
    allow_empty: bool = False,
) -> Tuple[type[Signal], ...]:
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


def reveal_on(*signal_types: Any) -> Callable[[Any], Any]:
    """Declare that this editor CLASS answers a :class:`RevealSignal` subclass.

    The class-level counterpart of :func:`react_on`, and the difference is the
    whole point: ``@react_on`` subscribes an *instance*, so an
    ``OpenBehavior.ON_PAYLOAD`` editor with no tab open has no subscriber and
    the signal reaches nobody. ``@reveal_on`` is read off the class by the
    AppShell, which is always alive — so it fires whether or not an instance
    exists, and the reveal's find-or-add creates the tab.

    That inverts who names whom. ``session.publish(Reveal(editor=Foo))``
    requires importing ``Foo``; publishing a bare ``RevealSignal`` subclass
    does not, so ``haywire-core`` can ask for a reveal that a barn library
    answers, with the dependency arrow still pointing the one legal way
    (``.insights/project_app_library_dependency_direction.md``).

    Decorate a **classmethod** taking ``(cls, context, event)`` and returning
    ``bool`` — the pre-reveal hook:

        @reveal_on(RevealComponentSource)
        @classmethod
        def _on_reveal(cls, context, event) -> bool:
            context.active_component = event.registry_key
            return True

    Contract:

    - Return ``True`` to proceed with the reveal, ``False`` to veto it. A
      veto means "not mine" — decide FIRST and write second, so a vetoing
      hook leaves no half-applied navigation behind.
    - Write only to ``context`` (and read the event). ``cls`` is shared by
      every session in the process, so anything stored there leaks across
      sessions. Session state written here is visible to the tab's ``draw()``,
      which runs after — that, not ``cls``, is how the revealed editor gets
      its content, exactly as it does for an ordinary context change.
    - The hook runs before the reveal, for the class, with no instance
      available — it cannot address one particular open tab. Use
      ``binding_id`` on the signal for that (the slot matches it), or an
      instance-level ``@react_on`` if a specific tab must react.

    ``binding_id`` / ``label`` come off the signal itself, so the hook never
    computes them.

    Args:
        *signal_types: :class:`RevealSignal` subclasses. Anything else — a
            plain ``Signal``, an instance, a non-type — raises ``TypeError``
            at decoration time (i.e. at import), because a signal with no
            ``binding_id``/``label`` cannot describe a reveal.

    Returns:
        A decorator returning the original object unchanged, with metadata
        attached as ``func._haywire_reveal_on = (signal_types, ...)``.
    """
    from haywire.core.signals import RevealSignal

    validated = validate_signal_types("@reveal_on(...)", signal_types)
    bad = [s.__name__ for s in validated if not issubclass(s, RevealSignal)]
    if bad:
        raise TypeError(
            f"@reveal_on(...) arguments must be RevealSignal subclasses "
            f"(a reveal needs binding_id/label); got: {', '.join(bad)}"
        )

    def decorator(func: Any) -> Any:
        # Set on the underlying function for a classmethod, so the metadata
        # survives however the two decorators are ordered.
        target = func.__func__ if isinstance(func, classmethod) else func
        existing = getattr(target, _REVEAL_ON_ATTR, ())
        setattr(target, _REVEAL_ON_ATTR, existing + validated)
        return func

    return decorator


def discover_reveal_handlers(cls: type) -> Dict[type[Signal], str]:
    """Map ``signal_type -> method name`` for every ``@reveal_on`` on ``cls``.

    Class-level and instance-free, like :func:`discover_handlers`: the shell
    calls this on registered editor *classes* at setup, which is what lets a
    zero-instance editor still answer a reveal.

    First declaration wins per signal type, walking subclass-first, so an
    override shadows the base the same way ``discover_handlers`` resolves it.
    """
    found: Dict[type[Signal], str] = {}
    for klass in cls.__mro__:
        for name, value in klass.__dict__.items():
            target = value.__func__ if isinstance(value, classmethod) else value
            if not callable(target):
                continue
            for signal_type in getattr(target, _REVEAL_ON_ATTR, ()):
                found.setdefault(signal_type, name)
    return found


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
