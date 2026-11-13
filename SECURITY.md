# Security policy

## Reporting a vulnerability

Please report security problems privately, never in a public issue or pull request: use
[Report a vulnerability](https://github.com/going-haywire/haywire/security/advisories/new)
on the repository's *Security* tab. The report reaches the maintainer only.

Include what you found, how to reproduce it, and the version or commit you tested. You
get an answer as soon as the maintainer has looked at it; a fix and a public advisory
follow once the problem is understood.

## Supported versions

Fixes go into the latest release only. Haywire is released in lockstep, so every package
of a release carries the same version.

## Scope

The studio has a login, can be exposed to a network, and serves an MCP endpoint
(Farmhand). Anything that lets someone reach, read or change a studio, its graphs or its
machine without the access the studio's settings grant is in scope. How exposure,
authentication and TLS are meant to work is described in
[docs/guides/security.md](docs/guides/security.md).
