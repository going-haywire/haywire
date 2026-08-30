# Reset Detail & Collapse

`haybale-graph-editor:panel:ClearDetailOverridesMenuPanel` · kind: panel

## Details

- **surface**: `selection`
- **order**: `47`

## Notes

Drop each selected node's own answer on BOTH card axes, so it tracks its
graph again.

Without this a node that has ever been folded or re-ranked by hand is
pinned for good, and a graph-wide collapse silently skips it — "unset
tracks, set ignores", per hop. That makes this the counterpart to the
graph-tier toggle, not a tidy-up: without a way back, the tier stops being
able to reassert over anything the user has touched.
