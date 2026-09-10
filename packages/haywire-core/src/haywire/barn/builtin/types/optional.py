"""OPTIONAL — a value of the wrapped IType, or absence."""

from typing import TypeVar

from haywire.core.types import FlowType, WrapperType, type
from haywire.barn.builtin import widget_keys

T = TypeVar("T")


@type(
    flow_type=FlowType.DATA,
    label="Optional",
    description="A value of the wrapped type, or absence",
    default={"value": None},
    widget_key=widget_keys.OPTIONAL_WIDGET,
)
class OPTIONAL(WrapperType[T]):
    """A value of the wrapped IType, or **absence**.

    Absence is a VALUE the user chooses — "do not pass this parameter to the
    wrapped library at all" — not an opinion about whether a tier has a view.
    The two are orthogonal: a field can be locally set *to* absence, and that
    choice survives a save/load. See the glossary's **absence** entry.

    Declared by subscripting the element type, mirroring the signature of the
    library being wrapped::

        class NmsSettings(NodeSettings):
            eta   = setting[OPTIONAL[FLOAT]](None, min=0.0, max=1.0, label="Eta")
            top_k = setting[OPTIONAL[INT]](None, min=1, max=1000, label="Top K")

    A worker then reads the bare value or ``None``, and passes only what is
    present::

        kwargs = {k: v for k, v in {"eta": self.nms.eta, "top_k": self.nms.top_k}.items()
                  if v is not None}

    The declared ``min``/``max`` stay the parameter's REAL range: absence lives
    outside the value domain, so it never has to be smuggled in as a sentinel
    (the ``-1`` convention that widening a range to admit it would require).

    **Promotable to CONFIG only.** ``setting.__set_name__`` seeds
    ``Promotable.CONFIG`` and raises if ``INLET`` or ``OUTLET`` is named. No
    adapter maps ``OPTIONAL[T]`` to ``T``, so a *pin* would refuse every edge —
    but a CONFIG port is pinless by construction, so the missing adapter cannot
    reach it. Lifting the rest of the fence is a separate design (what does a
    ``FLOAT`` edge emit for absence?), deliberately deferred.
    """
