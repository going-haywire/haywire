# Optional

`haywire-core:type:OPTIONAL` · kind: type

A value of the wrapped type, or absence

## Details

- **flow_type**: `data`
- **default**: `{'value': None}`
- **widget_key**: `haywire-core:widget:OptionalWidget`
- **color**: `#757575`

## Notes

A value of the wrapped IType, or **absence**.

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

**Promotion is ordinary.** ``promotable`` defaults to ``ALL`` and
eligibility never depends on the field's current value — promotion is a
structural fact. The generated port carries the ELEMENT type, so an
``OPTIONAL[INT]`` field becomes an ``INT`` pin and connects to whatever
``INT`` connects to. That is what removes the need for an
``OPTIONAL[T] -> T`` adapter: nothing asks for one.

**What crosses an edge** is decided by the SINK, via
``DataField.accepts_absence()`` — resolved once when the pipe is built:

- ``OPTIONAL -> OPTIONAL``: absence arrives as ``None``. The sink can
  represent "nothing", so discarding that would lose real information.
- ``OPTIONAL -> INT`` (directly or through an adapter): absence is skipped
  and the sink keeps its last value. ``INTField`` coerces with
  ``int(value)``, so forwarding ``None`` would raise from inside
  propagation — and "nothing to say this frame" is the honest downstream
  reading of *don't pass this parameter*.
