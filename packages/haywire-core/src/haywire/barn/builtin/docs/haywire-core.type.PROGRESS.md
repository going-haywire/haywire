# Progress

`haywire-core:type:PROGRESS` · kind: type

Whether a node is busy, how far it is, and what it is doing

## Details

- **wire_type**: `haywire-core:wire:DataWire`
- **default**: `{'active': False, 'fraction': None, 'label': ''}`
- **widget_key**: `haywire-core:widget:ProgressWidget`
- **color**: `#80cbc4`

## Notes

A node's progress: idle, busy without a known end, or busy at a known fraction.

- Idle: `active` is `False`; the bar is empty.
- Busy, no known end: `active` is `True` and `fraction` is `None`; the bar sweeps.
- Busy at a fraction: `active` is `True` and `fraction` runs from 0 to 1; the bar fills.

`label` names what the node is doing, such as "inferring".

Nodes don't write this value directly: they declare a `progress_field()` on
a `ProgressSettings` subclass and report through its `track()` and `busy()`.
