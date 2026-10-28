# undo

`haywire-core:setting:undo` · kind: setting

## Notes

What a user may tune about undo history.

Deliberately thin. :class:`~haywire.core.undo.config.UndoConfig` carries
~20 fields, but nearly all of them (merge windows, compression thresholds,
performance metrics) are internal tuning that would be noise in a settings
panel. This class exposes only the one a user has a real opinion about;
``UndoConfig`` stays the internal knob-set and reads this at construction.

Applies when a graph editor is *created*: ``HistoryManager`` reads
``max_actions`` from the config it was built with and has no resize path,
so editors already open keep the limit they started with.
