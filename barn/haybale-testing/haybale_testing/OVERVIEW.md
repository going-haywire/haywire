# haybale-testing

The internal test library for the Haywire monorepo. It ships deliberately
adversarial components — nodes with every setting kind, panels that import
state modules eagerly, a state block registered last — so the framework's
scan-order, hot-reload, and settings machinery are exercised by the test
suite rather than only by real plugin libraries.

It is not intended for end users. Its `farmhands/` folder contributes the
`testing_echo`, `testing_fail`, `testing_affinity`, and `testing_block`
tools that the Farmhand MCP integration tests drive over a real server.
