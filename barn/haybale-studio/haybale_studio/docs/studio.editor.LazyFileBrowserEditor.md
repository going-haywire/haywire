# Files

`studio:editor:LazyFileBrowserEditor` · kind: editor

Project file tree, eager-then-lazy: three levels are loaded up front, then 'Click to load children' sentinels appear at deeper folders so the user can pull in three more levels on demand.

## Details

- **default_slot**: `action`
- **opens**: `OpenBehavior.REQUIRED`
- **order**: `10`

## Notes

File tree that loads three levels at a time on demand.
