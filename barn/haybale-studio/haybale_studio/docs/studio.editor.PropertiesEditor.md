# Properties

`studio:editor:PropertiesEditor` · kind: editor

Context-sensitive property panels for the active selection.

## Details

- **default_slot**: `context`
- **opens**: `OpenBehavior.REQUIRED`
- **order**: `10`

## Notes

Focus-driven properties editor.

The left toolbar shows one icon button per Focus class contributed by
registered panels. Clicking a button makes that Focus active and
re-renders the content area with the panels belonging to that Focus.

Focus availability is determined by ``Focus.available(ctx)``. Unavailable
focuses are shown dimmed and are not clickable. The active focus is
never changed automatically after initial selection.
