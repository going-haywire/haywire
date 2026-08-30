# More Actions

`haybale-graph-editor:panel:GraphMorePanel` · kind: panel

## Details

- **surface**: `graph-toolbar`
- **hosts**: `['graph-more']`
- **order**: `999`

## Notes

The "…" — a panel that is itself a host.

The provider travels one hop further by the pipe default, so a panel
landing on ``GraphMoreActions`` reaches it through three hops without any
of them being an inherited tree edge.

An empty flyout greys this row retroactively: ``GraphMoreActions`` is an
extension point, and its resting state is having nothing on it.
