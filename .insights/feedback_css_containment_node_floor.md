# A node's size floor is CSS, and `contain: size` is not the whole answer

## The floor is not computed anywhere in Haywire

Nothing in Python decides how small a node can be. `UINode._apply_size` writes
`min-width`/`min-height` onto `.ui-node-slot`, and `canvas.vue`'s resize drag
reads `slot.offsetWidth` back. The floor is therefore whatever CSS intrinsic
sizing produces — the max-content size of the card subtree.

Two consequences that cost real debugging time:

1. **A widget's content is its node's floor.** An `<img>` is a *replaced*
   element: its max-content contribution is its natural pixel size (1280×720 for
   a 720p frame). The node can be grown but not shrunk past it.
2. **No percentage can cap it.** During intrinsic sizing, percentages resolve to
   `auto` — `width: 100%`, `max-width: 100%`, `min-width: 0` on the widget all
   evaporate in the pass that decides the floor and only apply afterwards. This
   is why the numpy viewer's careful `min-width: 0` juggling never fixed it.
   `overflow: hidden` doesn't help either: a scroll container still derives its
   intrinsic size from its content.

## Measuring the floor: do it in manual mode, or you measure `max-w-sm`

At rest the skin clamps the card (`min-w-64 max-w-sm`), so a node with 1280px of
content measures **384px** — the clamp, not the content. The card-fill CSS
releases that clamp only in manual mode (`[data-size-adapt="manual*"]`). A browser
test that measures the floor in `auto` mode measures the clamp and proves
nothing; `test_widget_size_box.py::_floor` flips to manual, clears the inline
min, reads, and restores. This is also why the bug is invisible until you drag —
and why `onResizeGripDown`'s `onUp` restores `prevMode` before measuring.

## `contain: size` kills aspect-driven growth — usually you want `inline-size`

Size containment is the right lever for the floor: the element is sized as if it
had no contents, and `contain-intrinsic-size` supplies a declared box instead.
But **both-axis containment also removes the content's height**, and for an
image that height is what made the widget grow proportionally as the node
widened. Applying `contain: size` to a frame viewer flattens it into a
fixed-height box — measured: widget height stayed at the declared 90px in a
420px-tall node.

`contain: inline-size` + `contain-intrinsic-width` is the surgical form: the
width stops coming from content (the floor drops) while the block axis still
does, so the image's aspect ratio keeps driving the height. There is **no
block-axis equivalent** — CSS defines `contain: inline-size` but nothing for
block-size alone, which is why `@widget(min_height=...)` without `min_width` is
rejected rather than half-applied.

Rule of thumb: aspect-ratio content (image, video, canvas) → `min_width` alone.
Fixed or internally-scrolling content → both axes.

Landed as `@widget(min_width=, min_height=, max_height=)`; see
`docs/components/widgets/widget-canon.md` and `haywire/ui/widget/sizing.py`.

## Height does not reach widgets, and that's accepted

Nothing between `.node-card` and the widget carries `flex: 1` + `min-height: 0`
(the port grid is `align-items: start`, the content column `align-self: center`),
so extra manual height pools below the ports rather than reaching the widget.
Width propagates fine via `w-full`/stretch. Deliberate: the viewer grows
*proportionally* through its width, so the pooling was accepted rather than
plumbed around.
