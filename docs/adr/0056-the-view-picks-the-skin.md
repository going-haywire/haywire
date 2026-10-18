---
name: the-view-picks-the-skin
description: Each node has a patch skin and a stage skin, each resolved framework < graph < node; a canvas draws with its view's skin and still tells the skin the view (`on_stage`). Skins carry tags that the skin lists filter on, and a stage canvas refuses any new edge it would not draw
status: accepted
see-also: ADR-0054
level: core
---

# The view picks the skin

**Context.**

- Slice 5a drew a node on stage with its patch skin, told which view it drew for by a required `on_stage` keyword on `render()` and `render_pin()` ([ADR 0054](0054-the-stage-view.md)). A node's stage look was fixed to its patch skin.
- Slice 5d brings widget nodes, which want a frameless face on stage and a normal card in the patch. A user may also want a different stage look per graph.

**Decision.**

- **Two skins per node.** `NodeProperties.stage_skin` mirrors `GraphProperties.default_stage_skin`, which shadows `NodeDefaultSkinSettings.studio_stage_skin`: framework < graph < node, the same chain as `skin`. Nothing crosses from the patch chain to the stage chain. The studio default is the registry's default skin (Stacked), fixed. `stage_skin` is a redraw field. Annotation and Reroute nodes bind their own skin to `stage_skin` as they do to `skin`.
- **The view picks, and still tells.** `UINode` draws with `props.stage_skin` on a stage canvas and `props.skin` on a patch canvas, and passes `on_stage=channel.stage` as ADR 0054 does. The skin contract is unchanged: `render(main_card, wrapper, *, on_stage)` and `render_pin(..., on_stage)`. A skin that suits both views draws its stage card when told `on_stage`. A skin made for the stage alone may ignore the flag.
- **The default skins on stage.** Stacked and Split, given `on_stage=True`, draw one row per port that shows a widget and only on-stage pins (ADR 0054), and ignore three node settings: collapse (never folded), layout direction (always left to right, `NodeSkin.layout_of(wrapper, on_stage=True)`) and detail.
- **Detail is the skin's, per view.** `BaseSkin.honours_detail(*, on_stage) -> bool` (default `True`) says whether the node's Detail setting thins the skin's cards in that view. `NodeSkin` returns `not on_stage`. `UINode` stamps `data-node-props-detail="full"` on a card whose skin answers no.
- **Tags.** `BaseIdentity.tags: list[str]` classifies a component for code to filter on; it is separate from a node's `search_tags`, which are words a person types. `@skin` defaults a skin's tags to `["general"]`. One function, `skin_choices(include=..., exclude=...)`, builds every skin list: a listed skin carries every tag in `include` and none in `exclude`.

  | List | Include | Exclude |
  |---|---|---|
  | Patch skin (studio, graph, node) | `general` | `special`, `stage-only` |
  | Stage skin (studio, graph, node) | `general` | `special` |

  A skin made for the stage alone is tagged `stage-only`. A skin for one kind of node is `special` plus a kind tag, and that node kind offers its own list. The lists decide what is offered; a write naming any skin is accepted.
- **Stage edge gate.** `stage_takes_edge(graph, ...)` is false when either end names an existing port off an on-stage wire. On a stage canvas, a pin-to-pin drop and the drop-to-create auto-wire refuse such an edge with the notice "This connection would not show on the stage. Make it in the patch view." Pins on an on-stage wire carry `data-pin-on-stage`, and a stage canvas starts an edge drag only from such a pin. It guards against a skin that draws off-stage pins on a stage.
- **Hot reload per card.** `SkinFactory` records the skin of each subscribed card, so a node whose patch and stage cards draw with different skins hears a reload of either.

**Considered options.**

- *Drop `on_stage` and give each patch skin a stage twin subclass* (built first in 5d-1, 2026-10-18). Rejected by the user the same day: every skin that adapts to the stage needs a subclass per view, Annotation and Reroute lost their stage behaviour until twinned, and third-party skins broke on the changed signature.
- *Keep `on_stage` and give widget nodes a skin that branches on it, with no stage skin.* Rejected: the widget nodes' patch look would be pinned to that skin, not to the user's patch skin.
- *The stage chain falls back to the patch skin when every stage tier is empty, or per tier.* Rejected: two inheritance axes need an ordering rule, and a graph's stage look would be cancelled by a node's patch choice.
- *A class flag `honours_detail`.* Rejected: one skin serves both views, and a flag cannot say "in the patch only".
- *Refuse a write of a skin a list does not offer.* Rejected: the result renders, and a validator-rejected write is dropped silently.
- *Hide node-specific skins (`hidden=True`) and list them by key on the node.* Rejected: a third-party skin for the same node kind could never be chosen. Tags let it join the right list by declaring them.

**Consequences.**

- A stage card of a Stacked or Split node no longer follows the node's layout direction or detail; collapse was already ignored.
- Every port carries an empty `tags` field through `DataTypeIdentity`; a default-equal field is not saved, so graph files are unchanged.
