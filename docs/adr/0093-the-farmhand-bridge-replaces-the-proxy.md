---
name: the-farmhand-bridge-replaces-the-proxy
description: an agent session reaches its project's studio through haywire farmhand bridge, a stdio MCP server in haywire-studio started from the project's own environment, which reads the Farmhand principal's token itself
status: accepted
see-also: ADR-0028, ADR-0092
level: architectural
---

# The Farmhand bridge replaces the proxy

**Context.**

- An agent session has to reach a studio that starts after the session: a plain HTTP MCP entry fails at session start and is not retried.
- The npm `@going-haywire/farmhand-proxy` did this from outside the project. It needed Node, shipped its own version, and its studio discovery had not worked since ADR 0028 removed the token file it looked for.

**Decision.**

- **`haywire farmhand bridge`** is a stdio MCP server in haywire-studio, started by the place's adapter from its own environment. It is up before any studio, finds its project's studio through `.haywire/studio.json`, forwards the studio's tools and resources with `list_changed`, and drops them when the studio stops.
- **The bridge serves the instructions:** its server instructions index the docs pages marked `serve: product` (and the repository's `serve: developer` pages); its resources serve the baked docs and the declared developer docs.
- **A studio that requires a token gets the Farmhand principal's** (`farmhand`, or `$FARMHAND_PRINCIPAL`), read from the roster by the bridge. The token never passes through the agent: no command prints a token unasked (`haywire user token <name>` prints one on request).

**Considered.**

- *Repair the proxy's discovery.* Node, a separately versioned package, and discovery from outside the project would have stayed.
- *A proxy-fetched token through a subprocess or the agent.* The token would land in transcripts and logs.

**Consequences.**

- The npm package is deprecated and its repository archived.
- The tier of the Farmhand principal, chosen by the user, is what agents may do in a studio with authentication on.
