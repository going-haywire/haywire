# Network

`haybale-studio:setting:NetworkSettings` · kind: setting

Where the studio's web server listens.

## Notes

Where the studio's web server listens.

Holds only the port. Exposure, the peer allowlist, TLS paths and the proxy
list live in ``~/.haywire/security.json`` (ADR 0028): the settings UI writes
the workspace tier, a per-project file that travels into git and onto other
machines.

A port number is not a security control: binding 8125 instead of 8124
exposes nothing that 8124 did not.
