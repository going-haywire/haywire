"""The studio's security document — one CLI-owned file for every startup-read control.

See ADR 0028. The package deliberately owns *all three* axes (authentication,
network location, Farmhand) rather than one, because the invariants that matter
are the combinations: "exposed" is only safe as a statement about a document
that also has authentication on and TLS configured, and a design where those
live in different files makes the dangerous combination independently reachable.
"""
