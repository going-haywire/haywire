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
and location when this session may, to read them otherwise. A volume a user
added can be deleted; a volume a library added cannot, and is reset to the
location its library suggests instead. The project volume is always the open
project's folder and cannot be changed. The header's add button adds a volume.
A location that does not exist on this machine (unplugged drive, folder not
created yet) is marked *missing*; it is still a valid location.
