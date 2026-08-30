# FillWidget

`haybale-example:widget:FillWidget` · kind: widget

Background fill editor (solid / linear / radial)

## Details


## Notes

Editor for a :class:`FILL` — a solid colour or a gradient.

Layout is kind-driven: the angle row belongs to ``linear`` alone, and the
stop list is meaningless for ``solid`` (which reads only the first stop),
so both are shown and hidden rather than redrawn — rebuilding the rows on
every kind change would drop focus from whichever control triggered it.
