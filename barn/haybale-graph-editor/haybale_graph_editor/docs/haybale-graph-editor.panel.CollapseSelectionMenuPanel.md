# Collapse

`haybale-graph-editor:panel:CollapseSelectionMenuPanel` · kind: panel

## Details

- **surface**: `selection`
- **order**: `45`

## Notes

Fold or unfold every selected node — one row, both directions.

**The row rewrites itself on click rather than closing over its state.**
``hui.menu_row`` does not dismiss its popup, so this menu is still on
screen after the command runs: a handler that captured ``collapsed`` at
draw time would keep re-sending that same value, and the toggle would work
exactly once. It did, until it was found. The current state is asked for on
every click (``toggle_selection_collapsed`` decides server-side and returns
the new state), and the label and icon are updated in place from the
answer, so what the row says stays true while the menu remains open.

The icon names the action, not the state — it pairs with the label, which
also says the verb. An icon showing the *current* state beside a label
saying the *next* one reads as a contradiction.
