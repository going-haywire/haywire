# Core Error Node

`haywire-core:node:ErrorNode` · kind: node

Placeholder for node that could not be loaded

## Notes

Stands in for a node that could not be built.

You see it when a node's library is missing, or its class fails to build,
for example after an edit that broke it. It shows the error, keeps the
node's place and connections, and does not run.

Saving the graph keeps the original node in the file, with its settings and
values. Once the library is installed or the class is fixed, the real node
comes back in its place.
