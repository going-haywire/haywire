# Data Node

`haywire-core:node:DataNodeTemplate` · kind: node

Computes a value from its inputs each time the graph runs.

## Ports

| id | direction | type | description |
|---|---|---|---|
| x | inlet | haywire-core:type:FLOAT | Decimal numberer |
| result | outlet | haywire-core:type:FLOAT | Decimal numberer |

## Notes

A data node: one number in, one number out.

Start here for a node that turns inputs into outputs. To make it yours:

- Declare your ports in `init()`. Each `self.add(...)` adds one inlet or
  outlet; the id you give it (`"x"`, `"result"`) is how the worker names it.
- Compute in `worker()`. Every inlet arrives as a keyword argument of the
  same name. Send each result with `self.out("<outlet id>", value)`.
- Keep `node_type=NodeType.DATA` for a node that only computes. A data node
  needs at least one data outlet.

```python
def worker(self, context, x: float = 0.0) -> None:
    self.out("result", x * 2)
```
