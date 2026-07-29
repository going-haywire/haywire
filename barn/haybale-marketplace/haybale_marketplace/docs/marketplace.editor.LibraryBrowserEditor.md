# Libraries

`marketplace:editor:LibraryBrowserEditor` · kind: editor

Searchable list of installed and available libraries.

## Details

- **default_slot**: `action`
- **opens**: `OpenBehavior.REQUIRED`
- **order**: `30`

## Notes

Shows a searchable list of installed (enabled/disabled) libraries.

On selection, updates context.active_library and notifies subscribers
via LIBRARY_STATE_CHANGED. The library_manager is retrieved from
context.app.library_manager.
