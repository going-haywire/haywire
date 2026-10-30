# Volumes

`haybale-studio:editor:VolumesEditor` · kind: editor

Where each volume lives on this machine

## Details

- **default_slot**: `action`
- **opens**: `OpenBehavior.REQUIRED`
- **order**: `100`

## Notes

One row per volume: its label, and below it where it lives on this machine.

A row's button opens the volume's details: to change its label, description
and location, or delete it, when this session may; to read them otherwise.
The project volume is always the open project's folder and cannot be changed.
The header's add button adds a volume. A location that does not exist on this
machine (unplugged drive, folder not created yet) is marked *missing*; it is
still a valid location. Deleting a volume a library added resets it: the
library adds it back with its suggested location the next time it starts.
