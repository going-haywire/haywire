# Drain

`haybale-core:type:DRAIN` · kind: type

Every value its edge delivers, queued until the node takes them

## Details

- **default**: `{'max_len': 64}`
- **color**: `#757575`

## Notes

An inlet that keeps every value its edge delivers, in order, until the node takes them.

Use it when the values come from another flow that runs at its own pace: an
ordinary inlet holds only the latest value, so values written between two runs
of the node are lost, and a value nobody replaced is read again. A drain inlet
loses none and repeats none.

The pin is the element's pin, so `DRAIN[AUDIO]` connects to any `AUDIO`
outlet. It takes one edge. The edge is always eager, and a promoted outlet
cannot feed it.

The node takes everything queued since its last take with `self.drain(id)`,
oldest first. The queue holds `max_len` values (64 unless the port sets it);
when it is full the oldest value is dropped, and the next take reports how many
were. The queue is not saved with the graph, and it empties when its edge is
removed.

```python
def init(self):
    self.add(DRAIN[AUDIO].as_inlet("in_0", label="In 0"))
    self.add(DRAIN[AUDIO].as_inlet("in_1", label="In 1", default={"max_len": 128}))

def worker(self, context):
    batch = self.drain("in_0")
    for block in batch:
        ...
    if batch.dropped:
        logger.warning("lost %d blocks", batch.dropped)
```

`self.value(id)` shows the queued values without taking them.
