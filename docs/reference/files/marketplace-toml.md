---
status: draft
doc_template: reference
scope: marketplace.toml — the two subscription files. [[markets]], [[stalls]], [[haybales]], [[heaps]], [[caches]], and where each lives.
see-also:
  - marketstall-toml.md
  - haybale-toml.md
  - ../../haybale/marketplace/haybale-marketplace-arch.md
  - ../../guides/subscribing-to-marketplaces.md
---

# `marketplace.toml`

Two files share this name, with deliberately separate concerns.

| | Global | Project |
| --- | --- | --- |
| Path | `~/.haywire/db/haybale_marketplace/marketplace.toml` | `<project>/.haywire/marketplace.toml` |
| Owner | The user, per machine | The project; travels with the source tree |
| Holds | What the user subscribes to | The project's own libraries + the last refresh result |
| Sections | `[[markets]]`, `[[stalls]]`, `[[haybales]]` | `[[heaps]]`, `[[caches]]` |
| Hand-editable | Yes — this is the recovery path | `[[heaps]]` yes; `[[caches]]` is derived |

Subscriptions are a user concern, not a project concern, so `[[markets]]` and
`[[stalls]]` never appear in the project file, and `[[heaps]]`/`[[caches]]`
never appear in the global one. Sections in the wrong file are silently
dropped at parse.

## The five sections

| Section | File | Written by | What it expresses |
| --- | --- | --- | --- |
| `[[markets]]` | global | Add Source | A subscription to an aggregator's catalog, which references other stalls |
| `[[stalls]]` | global | Add Source | A subscription to one author's marketstall |
| `[[haybales]]` | global | hand-written | Libraries declared inline, without a subscription |
| `[[heaps]]` | project | `haywire init` | Path-based libraries this project knows about |
| `[[caches]]` | project | refresh | The resolved catalog from the last refresh |

`[[markets]]` and `[[stalls]]` are structurally identical — the same three
fields. The difference is how the fetched body is parsed: a market body may
reference further stalls, a stall body contains only `[[haybales]]`.

## Global marketplace

```toml
# ~/.haywire/db/haybale_marketplace/marketplace.toml
# What this user subscribes to. Hand-editable — this is the recovery path when
# a source misbehaves. Created with the official feed on first run.

# ── an aggregator's catalog ─────────────────────────────────────────────────
# Its body is read one level deep: the [[stalls]] URLs it lists are fetched,
# and any [[haybales]] it inlines are taken. Any [[markets]] it lists are
# IGNORED — resolution stops after one hop, so a subscription cannot silently
# enrol the user in an unbounded graph of feeds.
[[markets]]
url = "https://going-haywire.github.io/haywire/marketplace.toml"
# Names THIS source should win when several sources offer the same library.
# Written by the conflict prompt and by the refresh flow's "Use this one";
# exclusive, so naming a winner clears the name from every other subscription.
preference = []
# Names the user actively rejected in the install-safety modal. Stronger than
# `preference`: a blocked name is filtered out of the candidate list AND out of
# the previous cache, so it disappears entirely rather than lingering as a
# stale row. Un-blockable only by editing this file.
blocked = []

# ── one author's feed ───────────────────────────────────────────────────────
# The body is [[haybales]]-only. Same three fields, same meanings.
[[stalls]]
url = "https://raw.githubusercontent.com/alice/haybales/main/marketstall.toml"
preference = []
blocked = []

# ── inline libraries ────────────────────────────────────────────────────────
# Hand-written only. Add Source does NOT write here: a pasted block is saved to
# stalls/<dist-name>.toml beside this file and subscribed as a file:// [[stalls]]
# entry, so a pasted library follows exactly the same refresh path as a remote
# one. Rows use the Haybale schema — see marketstall-toml.md.
[[haybales]]
name         = "haybale-experimental"
version      = "0.1.0"
install_spec = "haybale-experimental @ git+https://github.com/bob/exp.git@v0.1.0"
source       = "git"
```

## Project marketplace

```toml
# <project>/.haywire/marketplace.toml
# Travels with the project. [[heaps]] is authored; [[caches]] is derived and
# safe to delete — the next refresh rebuilds it.

# ── path-based libraries this project knows about ───────────────────────────
# Written by `haywire init` (the project's own scaffolded library) and by
# `haywire init --dev` (additionally, every sibling library in the dev repo).
# A heap shadows any marketplace row with the same name: local always wins.
# Surfaced in the browser's AVAILABLE section as source="local" so it is
# visible before it is installed.
[[heaps]]
name = "haybale-my-project"                                  # required
path = "/abs/path/to/my-project/barn/haybale-my-project"     # required
label = "My Project"
description = "Local library for the my-project project"

# ── the resolved catalog from the last refresh ──────────────────────────────
# Rebuilt in full on every refresh. Rows use the Haybale schema (see
# marketstall-toml.md) plus three cache-only fields. Never hand-authored; a
# malformed [[caches]] section is discarded and refetched rather than raising,
# so a bad cache cannot block the refresh that would heal it.
[[caches]]
name              = "haybale-visiongraph"
version           = "0.0.40"
label             = "Visiongraph"
description       = "Camera and vision nodes"
install_spec      = "haybale-visiongraph @ git+https://github.com/…@v0.0.40"
source            = "git"
os                = ["macos", "linux"]
origin            = "https://github.com/going-haywire/haywire"
origin_provider   = "github"
# ── cache-only, written by refresh ──────────────────────────────────────────
# The subscription URL that resolved this row. Drives the provenance label
# ("from github.com/alice" vs "via going-haywire.github.io") and tells the
# Block button which subscription's `blocked` array to write.
via               = "https://going-haywire.github.io/haywire/marketplace.toml"
# ISO timestamp, set when the row first went stale.
last_seen         = "2026-08-09T14:22:05Z"
# True when the most recent refresh did not re-resolve this name — the source
# dropped it, or the source itself is gone. Renders a red dot; the row can be
# removed with the trash icon when the library is not installed.
stale             = false
```

## Subscription fields

Shared by `[[markets]]` and `[[stalls]]`.

| Field | Type | Meaning |
| --- | --- | --- |
| `url` | string | The feed to fetch. `https://` or `file://` |
| `preference` | list[str] | Names this source should win when several offer them. Written by the conflict prompt and "Use this one" |
| `blocked` | list[str] | Names the user rejected in the install-safety modal. Fully hidden, from the candidate list and the stale-rescue pool alike |

`preference` answers "from *this* source, when several offer it"; `blocked`
answers "not at all".

When several sources offer one name, the refresh honours whichever source
claims it in `preference`, falling back to the first candidate when none do —
which is why the resolve step lists every collision, so an unsettled one is
visible before it changes a version. Preferring a source is exclusive: the name
is removed from every other subscription's array, so one edit fully settles the
choice regardless of how many sources offer it.

A refresh never writes this file. It holds your intent — subscriptions,
`preference`, `blocked` — and only an explicit action changes it.

## Heap fields

| Field | Required | Meaning |
| --- | --- | --- |
| `name` | yes | Pip distribution name |
| `path` | yes | Absolute path to the library directory |
| `label`, `description` | no | Display only |

A `[[heaps]]` entry with no `name` or no `path` raises rather than being
skipped — unlike `[[caches]]`, this section is user-authored, so a malformed
entry is a mistake worth surfacing.

Because `path` is absolute and machine-specific, committing a project
marketplace with heaps pointing at a developer's home directory breaks it for
everyone else.

## Files on disk

Everything the marketplace writes, and what is lost by deleting each.

| Path | Holds | Safe to delete? |
| --- | --- | --- |
| `~/.haywire/db/haybale_marketplace/marketplace.toml` | Subscriptions | Yes — recreated with the official feed; loses the user's own subscriptions |
| `~/.haywire/db/haybale_marketplace/stalls/<dist>.toml` | Pasted-in blocks | Yes — orphans the `file://` stall entry pointing at it |
| `~/.haywire/cache/<url-hash>.toml` | Raw fetched bodies, no TTL | Yes — forces a refetch on next refresh |
| `~/.haywire/cache/docs/<library>/` | Fetched doc bodies | Yes |
| `<project>/.haywire/marketplace.toml` | Heaps + caches | Caches yes; heaps are authored |

No installed package is ever lost by deleting any of these: installation is pip
state, not marketplace state. The recovery ladder is in
[haybale-marketplace-arch](../../haybale/marketplace/haybale-marketplace-arch.md).

## Adding a source

Add Source takes one field and accepts a blob URL, a raw URL, a plain TOML URL,
or a TOML block pasted directly. The runtime fetches the body, inspects its
shape, and writes the matching section:

| Body contains | Written as |
| --- | --- |
| `[[stalls]]` and/or inline `[[haybales]]` | `[[markets]]` |
| `[[haybales]]` only | `[[stalls]]` |
| A pasted block | `stalls/<dist>.toml` + a `file://` `[[stalls]]` entry |

A successful Add Source auto-refreshes once. Everything after that is
[the refresh pipeline](../../haybale/marketplace/haybale-marketplace-arch.md).
