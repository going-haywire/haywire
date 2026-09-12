# Any

`haywire-core:type:ANY` · kind: type

Undecided until connected; the node retypes the port from the other end

## Details

- **flow_type**: `data`
- **default**: `{'value': None}`
- **color**: `#666666`

## Notes

A placeholder pin that takes its type from the first edge drawn to it.

An `ANY` pin connects to anything, and connecting is the point: the node
reads the type from the other end and replaces the pin with a real one of
that type. Use it where the node cannot know the type in advance — a group
input that declares its interface when the user wires it, or a node that
grows a fresh slot each time one is filled.

The node does the retyping; the type only makes the connection possible.
Give the port an `on_connect` handler and rebuild the port inside `rejig`:

```python
def init(self):
    self.add(ANY.as_inlet("in_0", on_connect="_resolve"))

def _resolve(self, port, edge_wrapper):
    incoming = edge_wrapper._outlet_port.stored_type
    if incoming._is_any:
        return  # the other end is undecided too — nothing to adopt
    with self.rejig(include=[port.id]):
        self.add(incoming.as_inlet(port.id, on_connect="_resolve"))
```

The edge survives the swap and rebuilds against the new type on the next
validation pass. A handler that declines to retype leaves the pin `ANY` and
the edge passing values through untouched, which is how a node restricts
itself to the types it actually accepts.

An edge between two `ANY` pins is valid and does nothing: neither end has a
type to give. Both resolve once either is connected to something concrete.

Holds no value of its own and renders no widget. Cannot be a config port —
a config never connects, so an `ANY` config could never resolve.
