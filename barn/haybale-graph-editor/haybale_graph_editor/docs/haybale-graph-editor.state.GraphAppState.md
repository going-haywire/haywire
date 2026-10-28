# Graph App State

`haybale-graph-editor:state:GraphAppState` · kind: state

## Notes

Registry: ``binding_id`` → :class:`GraphContainer`.

One instance per app, shared across sessions. Source libraries
coordinate writes; GraphEditor performs reads.
