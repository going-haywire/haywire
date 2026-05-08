---
status: draft
doc_template: guide
scope: Worked examples of each node role — CONTROL (multi-pin dispatch), DATA (pure compute), EVENT (with matching emitter), LOOPBACK (round-trip with break)
see-also:
  - ../components/nodes/node-canon.md
  - ./ports.md
  - ../architecture/execution/callbacks/callbacks-arch.md
  - ../reference/glossary.md
---

# Node roles — worked examples

The node authoring API — the `@node` decorator, lifecycle hooks, the worker contract, port access, `rejig()`, groups — is documented in [components/nodes/node-canon](../components/nodes/node-canon.md). This guide shows what's distinctive about each **role**: CONTROL, DATA, EVENT, and LOOPBACK. Each example is minimal — only the role-specific bits are explained inline; everything else is in the canon.

## CONTROL — multi-pin dispatch

A CONTROL node has at least one EXEC inlet *and* outlet. When it has **multiple** EXEC inlets, the worker uses `context.control_pin` to discover which one fired and dispatch accordingly.

```python
from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import node, BaseNode, NodeType


@node(
    label='Counter',
    description='Increments on one pin, resets on another',
    menu='control/counter',
    node_type=NodeType.CONTROL,
)
class CounterNode(BaseNode):
    def init(self):
        from haybale_core.types.specs import EXEC, INT

        self.add(EXEC.as_inlet('increment', label='Increment'))
        self.add(EXEC.as_inlet('reset', label='Reset'))
        self.add(EXEC.as_outlet('done', label='Done'))
        self.add(INT.as_outlet('count', label='Count'))

    def post_init(self):
        self._count = 0

    def worker(self, context: ExecutionContext) -> str | None:
        if context.control_pin == 'increment':
            self._count += 1
        elif context.control_pin == 'reset':
            self._count = 0
        self.out('count', self._count)
        return 'done'
```

**Role-specific:** `context.control_pin` carries the ID of the EXEC inlet that triggered this run. Single-inlet CONTROL nodes don't need it; multi-inlet ones do.

## DATA — pure compute

A DATA node has **no EXEC ports**. It runs only when a downstream CONTROL node demands one of its outputs. Its worker returns `None` and writes results via `self.out(...)`.

```python
from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import node, BaseNode, NodeType


@node(
    label='Add',
    description='Adds two floats',
    menu='math/basic',
    node_type=NodeType.DATA,
)
class AddNode(BaseNode):
    def init(self):
        from haybale_core.types.specs import FLOAT
        from haybale_core.widgets.basic_widgets import NumberWidget

        self.add(FLOAT.as_inlet('a', label='A', default=0.0, widget=NumberWidget.config()))
        self.add(FLOAT.as_inlet('b', label='B', default=0.0, widget=NumberWidget.config()))
        self.add(FLOAT.as_outlet('result', label='Result'))

    def worker(self, context: ExecutionContext, a: float, b: float) -> None:
        self.out('result', a + b)
        return None
```

**Role-specific:** no EXEC ports, returns `None`, runs lazily on demand.

## EVENT — `event_subscription`

An EVENT node has no EXEC inlet either, but unlike DATA it is an **entry point** of a control flow: it runs when an event source fires. The role-defining hook is `self.event_subscription`, set in `post_init()`.

The simplest case is a system event — fired by the framework at well-known moments (start of play, shutdown, …):

```python
from haywire.core.execution.event_source import SystemEvent, SystemEventType
from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import node, BaseNode, NodeType


@node(
    label='Begin Play',
    description='Triggered once when execution starts',
    menu='event/runtime',
    node_type=NodeType.EVENT,
)
class BeginPlayNode(BaseNode):
    def init(self):
        from haybale_core.types.specs import EXEC, FLOAT

        self.add(EXEC.as_outlet('exec', label='Execute'))
        self.add(FLOAT.as_outlet('timestamp', label='Start Time'))

    def post_init(self):
        self.event_subscription = SystemEvent(SystemEventType.BEGIN_PLAY)

    def worker(self, context: ExecutionContext) -> str | None:
        import time
        self.out('timestamp', time.time())
        return 'exec'
```

**Role-specific:** `event_subscription` is set in `post_init()`. There is no EXEC inlet — the framework dispatches the event source instead. `SystemEvent` covers framework-level moments; for user-driven events, use `CallbackEvent` (next section).

### Variant: callback events (listener + emitter pair)

`event_subscription` also accepts `CallbackEvent(event_name=...)`, which lets one node trigger another by name. A callback listener is meaningless on its own — it needs a matching emitter — so we show the pair together. The emitter is technically a CONTROL node (it has an EXEC inlet); it lives here because the listener can't be exercised without it.

```python
# --- Listener: an EVENT node ---
from haywire.core.execution.event_source import CallbackEvent
from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import node, BaseNode, NodeType


@node(
    label='On Ping',
    description='Runs when a matching Ping is emitted',
    menu='event/runtime',
    node_type=NodeType.EVENT,
)
class OnPingNode(BaseNode):
    def init(self):
        from haybale_core.types.specs import EXEC, CALLBACK, STRING

        # Outlet broadcasts this listener's ID; many emitters can wire to it.
        self.add(CALLBACK.as_outlet(
            'listen', label='Listen',
            default=self.node_id,
            allow_multiple_links=True,
        ))
        self.add(EXEC.as_outlet('exec', label='Execute'))
        self.add(STRING.as_outlet('message', label='Message'))

    def post_init(self):
        # Subscribe under this node's id, which is what the CALLBACK outlet broadcasts.
        self.event_subscription = CallbackEvent(event_name=self.node_id)

    def worker(self, context: ExecutionContext) -> str | None:
        payload = context.trigger.payload or {}
        self.out('message', payload.get('message', ''))
        return 'exec'
```

```python
# --- Emitter: a CONTROL node ---
from haywire.core.node import node, BaseNode, NodeType


@node(
    label='Emit Ping',
    description='Triggers all connected On Ping listeners',
    menu='emit/runtime',
    node_type=NodeType.CONTROL,
)
class EmitPingNode(BaseNode):
    def init(self):
        from haybale_core.types.specs import EXEC, CALLBACK, STRING
        from haybale_core.types.pooled_type import PooledType

        self.add(EXEC.as_inlet('exec', label='Execute'))
        self.add(STRING.as_inlet('message', default='hello', label='Message'))
        # Pooled inlet — collects listener IDs from any number of connected listeners.
        self.add(PooledType[CALLBACK].as_inlet('listeners', label='Listeners'))
        self.add(EXEC.as_outlet('done', label='Done'))

    def worker(self, context):
        message = self.value('message')
        for listener_id in self.value('listeners').values():
            context.emit_callback(event_name=listener_id, payload={'message': message})
        return 'done'
```

**What the pair shows:**

- **`allow_multiple_links=True`** on the listener's CALLBACK outlet lets many emitters target the same listener (port detail in [guides/ports](./ports.md)).
- **`PooledType[CALLBACK].as_inlet(...)`** on the emitter collects all connected listener IDs into a dict (port detail in [guides/ports](./ports.md)).
- **`context.emit_callback(event_name=..., payload=...)`** dispatches to subscribers.
- **`context.trigger.payload`** delivers the emitter's payload to the listener's worker.

For the framework's dispatch model — assembly-time wiring, FlowType.CALLBACK, CallbackManager — see [architecture/execution/callbacks](../architecture/execution/callbacks/callbacks-arch.md).

## LOOPBACK — round-trip with break

A LOOPBACK node fires an EXEC outlet, control flows through downstream nodes, and **returns to the same node** to run its worker again. The role-defining marker is `needs_loopback=True` on the body outlet. A second EXEC inlet provides early exit.

```python
from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import node, BaseNode, NodeType


@node(
    label='Repeat',
    description='Runs the body N times, with break',
    menu='control/loops',
    node_type=NodeType.LOOPBACK,
)
class RepeatNode(BaseNode):
    def init(self):
        from haybale_core.types.specs import EXEC, INT
        from haybale_core.widgets.basic_widgets import NumberWidget

        self.add(EXEC.as_inlet('execute', label='Execute'))
        self.add(EXEC.as_inlet('break_loop', label='Break'))

        self.add(INT.as_inlet('count', label='Count', default=10,
                              widget=NumberWidget.config()))

        # The loop body. needs_loopback=True tells the VM that control is
        # expected to return here after the body runs.
        self.add(EXEC.as_outlet('loop_body', label='Loop Body', needs_loopback=True))
        self.add(INT.as_outlet('index', label='Index', default=0))
        self.add(EXEC.as_outlet('completed', label='Completed'))

    def post_init(self):
        self._index = 0
        self._end = 0

    def worker(self, context: ExecutionContext, count: int = 0) -> str | None:
        pin = context.control_pin
        if pin == 'execute':
            # Fresh entry — initialise.
            self._index = 0
            self._end = count
        elif pin == 'break_loop':
            return 'completed'
        else:
            # Re-entry from the body — advance.
            self._index += 1

        if self._index >= self._end:
            return 'completed'

        self.out('index', self._index)
        return 'loop_body'
```

**Role-specific:**

- **`needs_loopback=True`** on `loop_body` declares the round-trip: the VM remembers this node and returns control to it after the body completes.
- **`context.control_pin` dispatch** distinguishes three cases: `'execute'` (first entry), `'break_loop'` (early exit), and anything else (re-entry from the body). This is the same `control_pin` mechanism shown in the CONTROL example, used here for a different purpose.
