# Security

`haybale-studio:panel:SecurityPanel` · kind: panel

## Details

- **surface**: `app`
- **order**: `40`

## Notes

What this studio's defences currently are — read-only (ADR 0028).

**Deliberately not editable.** Exposure, the peer allowlist, TLS and the
Farmhand switches all left the settings system precisely because a panel
that writes them writes the *workspace* settings tier, a per-project file
that travels into git and onto other machines. They are changed with
``haywire network``, ``haywire auth``, ``haywire ssl`` and
``haywire farmhand``, with the studio stopped, because every one of them is
read once at startup.

The port stays here: it is a local convenience, not a security control.
