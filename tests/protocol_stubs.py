"""Build a stub satisfying a ``runtime_checkable`` Protocol, without listing its verbs.

``render_surface`` validates an actions host with ``isinstance`` against the
surface's ``provides`` Protocol, so tests that render a surface need an object
that satisfies it. Writing those stubs by hand means every verb added to a
Protocol breaks a test file per stub — which happened four times in one
session while ``SelectionActions`` grew the ADR-0032 card verbs, each time
costing a round trip that taught nothing.

Deriving the verb list from the Protocol removes that entirely: a stub built
here satisfies its Protocol by construction, today and after the next verb.

**What this is not for.** A test asserting that an INCOMPLETE implementation
fails ``isinstance`` must still spell out what it omits — the omission is the
subject. Use a hand-written class there.
"""

from __future__ import annotations

from typing import Any


def protocol_verbs(protocol: type) -> set[str]:
    """The callable members a Protocol declares.

    Read off the class body rather than ``__protocol_attrs__``, which is a
    CPython internal the type checker does not model.
    """
    return {name for name, attr in vars(protocol).items() if callable(attr) and not name.startswith("_")}


def stub_for(*protocols: type, **returns: Any) -> Any:
    """An object satisfying every given Protocol, recording what was called.

    ``returns`` supplies a value for a verb whose caller does something with
    the answer (``selection_is_collapsed=True``); everything else returns
    ``None``. ``isinstance`` against a ``runtime_checkable`` Protocol only
    checks that the attributes exist, so a plain callable is enough to satisfy
    it — the return values matter only to a test that goes on to call one.

    Calls land in ``.calls`` as ``(verb, args)``, so a test can assert a row
    invoked the verb it advertises.
    """
    verbs: set[str] = set()
    for protocol in protocols:
        verbs |= protocol_verbs(protocol)
    if not verbs:
        raise AssertionError(
            f"{[p.__name__ for p in protocols]} declare no verbs — a stub of them "
            f"would satisfy nothing, and any isinstance assertion using it would "
            f"be vacuous"
        )

    unknown = set(returns) - verbs
    if unknown:
        raise AssertionError(
            f"return values given for {sorted(unknown)}, which no supplied Protocol "
            f"declares — a typo here would otherwise silently do nothing"
        )

    class _Stub:
        def __init__(self) -> None:
            self.calls: list[tuple[str, tuple[Any, ...]]] = []

    def _make(verb: str):
        def _call(self, *args: Any, **_kwargs: Any) -> Any:
            self.calls.append((verb, args))
            return returns.get(verb)

        _call.__name__ = verb
        return _call

    for verb in verbs:
        setattr(_Stub, verb, _make(verb))

    return _Stub()
