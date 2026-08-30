# Properties

`haybale-studio:editor:PropertiesEditor` · kind: editor

Context-sensitive property panels for the active selection.

## Details

- **default_slot**: `context`
- **opens**: `OpenBehavior.REQUIRED`
- **order**: `10`

## Notes

Surface-driven properties editor.

The left SurfaceToolbar shows one icon button per **root surface that
declares a ``presentation``** — surfaces named by some registered panel's
``surface=``, named by no panel's ``hosts=``, and carrying chrome for a
host to draw. Every other host names the surface it opens; only this one
discovers its list, so the filter lives here rather than in the registry
(ADR-0029, Presentation). Clicking a button makes that surface active and
re-renders the content area with its panels.

A surface whose ``poll()`` is false keeps its tab in place, greyed, and
its content is dropped: stable position is what makes a tab learnable,
and the editor drew that chrome so the editor greys it. The active
surface is never changed automatically after initial selection.
