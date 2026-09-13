# Add

`haywire-core:type:ADD` · kind: type

Grows a new port from whatever connects to it

## Details

- **flow_type**: `data`
- **default**: `{'value': None}`
- **color**: `#666666`

## Notes

A pin that grows a new port when something connects to it.

Connecting is the point: the node reads the connection and replaces the pin
with a real one, so `ADD` is a slot that has not been filled yet. It comes
in two forms, and the difference is what the new port's type will be.

Bare `ADD` is **undecided** — it takes the type from the other end:

```python
def init(self):
    self.add(ADD.as_inlet("in_0", on_connect="_resolve"))
```

An `INT` outlet connected to a bare `ADD` inlet gives an `INT` pin. Any
type connects, because there is nothing to convert to yet.

`ADD[T]` is **decided** — it stays `T` and lets the adapters convert:

```python
self.add(ADD[STRING].as_inlet("in_0", on_connect="_resolve"))
```

An `INT` outlet connected to an `ADD[STRING]` inlet gives a `STRING` pin
with a conversion on the edge. Only types that convert to `T` connect at
all: the edge fails to build, so the pin is never grown and nothing is
silently mistyped. The pin carries `T`'s colour with the `ADD` glyph, so it
shows what it accepts before the user drags.

Give the port an `on_connect` handler and rebuild it inside `rejig`:

```python
def _resolve(self, port, edge_wrapper):
    incoming = edge_wrapper._outlet_port.stored_type
    if incoming._is_any:
        return  # the other end is undecided too — nothing to adopt
    with self.rejig(include=[port.id]):
        self.add(incoming.as_inlet(port.id, on_connect="_resolve"))
```

The edge survives the swap and rebuilds against the new type on the next
validation pass. A handler that declines to retype leaves the pin as it is
and the edge passing values through untouched.

An edge between two bare `ADD` pins is valid and does nothing: neither end
has a type to give. Both resolve once either connects to something concrete.

Holds no value and renders no widget. Cannot be a config port — a config
never connects, so it could never resolve.
