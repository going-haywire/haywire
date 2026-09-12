# OptionalWidget

`haywire-core:widget:OptionalWidget` · kind: widget

Optional value — the wrapped type's widget, plus an absence state

## Details


## Notes

Renders an ``OPTIONAL[T]`` field in whichever of its two states it is in.

- **Present**: the element type's own declared widget, unchanged. An
  optional int edits exactly like a plain int.
- **Absent**: a ``none`` cell, sized and framed like a value widget so the
  row still reads as a field and the column doesn't jump, in muted italics
  so it doesn't read as a value, carrying an always-visible action icon so
  it reads as a *control*. Clicking anywhere in it enters a value and hands
  over to the element widget. The icon is deliberately not hover-revealed:
  a cell that looks inert until hovered is a control nobody finds.

Absence must LOOK absent. A cleared cell holds ``None``, which
``PrimitiveUnwrappingConverter`` renders as ``0`` — a number that actively
lies about the value — so the element widget is hidden rather than shown
holding a stand-in.

**Leaving absence is the widget's job; entering it is the row menu's.**
Clicking the ``none`` cell is the only way to start entering a value, so it
lives here. Going the other way is a Reset-shaped act and the Setting-row menu
already owns those verbs ("Reset to default" and, where they differ, "Set to
none"), so this widget deliberately offers no clear button of its own —
a third control doing what a listed menu entry already does is one the user
has to distinguish for no benefit.

**The value that clicking the ``none`` cell produces**, in order:

1. ``widget_config={"restore": ...}`` at the declaration site
2. the field's own non-absent default, stamped into ``restore`` by
   ``setting._stamp_widget``
3. the element IType's declared default (``INT`` → ``0``, ``BOOL`` → ``False``)

Stateless by design: it answers the same way every time rather than
remembering the last value, which would die on every panel redraw and make
the same gesture give different answers.
