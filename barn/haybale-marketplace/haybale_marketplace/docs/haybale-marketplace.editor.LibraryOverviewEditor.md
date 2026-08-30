# Library Detail

`haybale-marketplace:editor:LibraryOverviewEditor` · kind: editor

Detailed information for the selected library.

## Details

- **default_slot**: `edit`
- **opens**: `OpenBehavior.ON_CONTEXT`
- **order**: `100`

## Notes

Full center-panel port of LibraryManagerPage.

Displays:
- Fixed header: name, version, dist name, badges, action buttons, metadata
- Scrollable content: tabs (Overview, Nodes, Widgets, Types, Adapters,
  Renderers) for installed libraries, or async overview for marketplace-only.

Rebuilds on LIBRARY_STATE_CHANGED.
