# Control Payload TestNode

`haybale-testing:node:ControlPayloadTestNode` · kind: node

Test-only control node for exercising EXEC-edge payloads. Records the payload that arrived on its exec inlet, then advances — optionally writing its own payload, optionally forwarding the entered one implicitly (transparent conduit).

## Ports

| id | direction | type | description |
|---|---|---|---|
| exec_in | inlet | haybale-core:type:EXEC | Signal for controlling execution flow between nodes |
| exec_out | outlet | haybale-core:type:EXEC | Signal for controlling execution flow between nodes |

## Notes

Control node that participates in EXEC-payload flows.

Behaviour is driven by two plain attributes the test sets after the node
is created (kept off the port surface to keep the testbed node trivial):

- ``emit_payload``: if not ``None``, the worker calls ``out("exec_out", …)``
  with this value, exercising the *explicit* payload path.
- otherwise the worker writes nothing to ``exec_out`` and returns it anyway,
  exercising the *transparent-conduit* path where the VM forwards the
  payload that arrived on ``exec_in`` without the developer doing so.

Either way the worker stashes the payload seen on ``exec_in`` into
``received`` so the test can assert what propagated down the chain.
