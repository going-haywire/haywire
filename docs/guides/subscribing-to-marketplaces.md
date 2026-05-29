---
status: draft
doc_template: guide
scope: Subscribing to other authors' libraries — Add Source, Refresh, conflict resolution, stale handling, what to do when feeds go offline
see-also:
  - ../architecture/sharing/sharing-arch.md
  - ../architecture/library-manager/library-manager-arch.md
  - ./sharing-libraries.md
  - ../reference/glossary.md
---

# Subscribing to marketplaces — Consumer guide

This guide walks a consumer through following other authors' libraries: adding a source, refreshing the catalog, installing what you want, and handling the edge cases (conflicts, offline feeds, stale entries, malformed files). For the conceptual model — *why* the flow is shaped this way — see [sharing-arch](../architecture/sharing/sharing-arch.md). For the publisher side, see [sharing-libraries](./sharing-libraries.md).

## 1. What it solves

A **subscription** is the consumer's opt-in to follow what another author publishes. There's no central registry — there's a network of independent feeds, each one a TOML file hosted by its author, and each consumer chooses which to follow. Subscribing is explicit at every step: you add a source, you refresh, you install. Nothing pushes; nothing auto-installs.

The Library Browser in haywire-studio is the surface that drives this. It lists what you currently have installed and what's available to install, with filter toggles to scope the view. The three buttons in its toolbar — Refresh, Add Source, Edit File — are the entire consumer-facing surface.

## 2. The two-tier file layout

Your project's library state lives in two files. Knowing what each is for helps when you have to reason about what's happening.

| File | Path | What it holds |
|---|---|---|
| **Global marketplace** | `~/.haywire/db/haybale-marketplace/marketplace.toml` | Your subscriptions: `[[markets]]` for remote aggregators, `[[stalls]]` for individual marketstall feeds. Pasted-TOML inputs are saved as a local stall file and referenced via a `file://` `[[stalls]]` entry. Per-machine. |
| **Project marketplace** | `<project>/.haywire/marketplace.toml` | This project's path-based libraries (`[[heaps]]`, written by `haywire init`) and the resolved catalog cache (`[[caches]]`, written by Refresh). Per-project; travels with the source tree. |

You generally interact with the global file (subscriptions are a user concern). The project file is managed for you — `haywire init` sets up `[[heaps]]`, and Refresh maintains `[[caches]]`.

For a deep dive into the split and why it exists, see [sharing-arch §Why two tiers](../architecture/sharing/sharing-arch.md#why-two-tiers).

## 3. Add Source: subscribing to a feed

Click **Add Source** in the Library Browser toolbar. A single-field dialog opens — paste any of four forms:

| Form | What it looks like | Result |
|---|---|---|
| **Blob URL** (recommended) | `https://github.com/alice/cool-libs/blob/main/marketstall.toml` | The runtime recognizes the host, converts to the raw URL, and saves the appropriate `[[markets]]` or `[[stalls]]` subscription depending on the fetched body's shape. |
| **Raw URL** | `https://raw.githubusercontent.com/alice/cool-libs/main/marketstall.toml` | Same as blob, but skips the URL transformation. |
| **Plain TOML URL** | Any URL that serves a TOML file (GitHub Pages, GitLab Pages, your own host) | Fetched as-is; the body shape determines subscription type. |
| **TOML block** pasted directly | A `[[haybales]]` (or `[[markets]]`/`[[stalls]]`) section pasted into the field | Saved as a local file under `~/.haywire/db/haybale-marketplace/stalls/<dist-name>.toml` and referenced via a `file://` `[[stalls]]` entry. |

You don't pick a tab — the runtime inspects the fetched body and decides:

- If it contains `[[markets]]` or `[[stalls]]` references → saved as a `[[markets]]` subscription (it's an aggregator's catalog).
- If it contains only `[[haybales]]` → saved as a `[[stalls]]` subscription (it's a single marketstall).

Bare repository URLs (e.g. `https://github.com/alice/cool-libs`) are rejected — the dialog asks for the full path to a `marketstall.toml` or `marketplace.toml` so the resolver always knows what it's fetching.

Most authors share blob URLs (the canonical GitHub form). The official haywire feed lives at `https://going-haywire.github.io/haywire/marketplace.toml` — pasting that subscribes you as a `[[markets]]` entry. A `file://` URL also works, useful for testing local fixtures or air-gapped setups.

### 3.1 What happens after you click Add

1. The URL (or pasted body) is classified by host provider and parsed.
2. A new `[[markets]]` or `[[stalls]]` entry is written to your global marketplace.
3. An auto-refresh fires.
4. If the new source's haybales collide with anything you already have, a conflict-resolution prompt opens (see §4).
5. After refresh: a green toast reports the result (e.g. `"Refreshed 3 package(s) · 1 update(s) available"`).

The auto-refresh is a convenience — you don't have to remember to click Refresh after adding a source. If you ever subscribe by hand-editing the file (via Edit File), you'll need to click Refresh yourself.

## 4. Handling name conflicts

Two authors can pick the same library name — there's no central namespace stopping them. The system surfaces collisions at the moment you're about to follow a new feed that would introduce one.

When Add Source detects a conflict (a package in the new source whose name matches one your existing sources already provide), a conflict-resolution dialog opens with one row per colliding name. Each row shows the name and which sources offer it; you pick which to keep.

The choice is permanent: the losing source's `ignores` array gains the name, and from then on refresh will silently skip it from that source. You won't be asked again for the same conflict.

If you change your mind later, you can edit `~/.haywire/marketplace.toml` directly via the Edit File button — remove the entry from the `ignores` array, then click Refresh.

For the principle behind asking at intake rather than at refresh, see [sharing-arch §Resolving conflicts](../architecture/sharing/sharing-arch.md#resolving-conflicts).

## 5. Refresh: pulling the latest catalog

The **Refresh** button is the only operation that talks to the network. It does not run on a timer. You decide when to refresh.

What refresh does, in concept:

1. Reads your global marketplace.
2. Fetches every subscribed `[[markets]]` and `[[stalls]]` URL.
3. For each `[[markets]]` body, reads its `[[stalls]]` references one level deep and fetches those too. Inline `[[haybales]]` in the markets body are also collected.
4. For each haybale, applies the subscription's `blocked` array first (silently drops names you've actively rejected), then `ignores` (drops names you chose against in a previous conflict prompt). Each surviving haybale is stamped with the subscription's URL as its `via` field.
5. Assembles the combined candidate list and applies the heaps shadow (your project's path-based libraries win over any remote of the same name).
6. Deduplicates by name (first occurrence wins for any straggler).
7. Marks newly-missing entries as stale (see §7). Blocked names are filtered out of the stale-rescue step so they fully disappear rather than survive as `stale=true`.
8. Counts installed libraries whose cache `min_version` exceeds the installed version (updates available, see §9).
9. Writes the result to your project marketplace's `[[caches]]` section.

After a successful refresh, a green toast summarizes: `"Refreshed N package(s) · M source(s) unavailable · K newly stale · L update(s) available"`. The middle phrases appear only when relevant.

### 5.1 The Available section

The Library Browser's AVAILABLE filter (blue cloud-download icon) shows the resolved catalog: every haybale not currently installed. Clicking a row opens its Library Overview Editor for install.

Each row carries a **provenance label** derived from the `via` cache field — "from github.com/alice" for direct stalls, "via going-haywire.github.io" for haybales that arrived through an aggregator. The tooltip names both the aggregator and the underlying stall so you can audit which feeds contribute which haybales. If an aggregator silently adds new sources, the new haybales' provenance labels make the expansion visible.

Heaps — your project's path-based libraries — show up here too, even though they aren't on any remote feed. They're presented as `source = "local"` entries. Installing them runs `uv pip install -e <path>` so they become editable.

### 5.2 The install-safety modal

Every Install click opens a modal interposing between the click and the actual `uv pip install`. The user is installing third-party code, and the modal makes that explicit:

| Button | Effect |
|---|---|
| **Cancel** | Closes the modal, no change. |
| **Block source** | Adds the haybale's `name` to the `blocked` array on the subscription that resolved it (the one whose URL matches the cache entry's `via`). The haybale disappears from AVAILABLE immediately; the only un-block path is editing `marketplace.toml` by hand. |
| **Install** | Proceeds with `uv pip install <install_spec>` and triggers a Library System rescan. |

The modal also shows the haybale's `source_url` as a clickable "Review source" link so you can read the code at the source before installing. The modal fires on every Install click — there's no first-time-only suppression, since third-party install is a serious enough operation that the safety prompt is shown every time. Cancel dismisses it in one click if you're sure.

## 6. Sources unavailable

If a refresh can't fetch a subscribed URL — network error, server down, 404 — the refresh doesn't abort. It records the failed URL and falls back to the HTTP cache at `~/.haywire/cache/`. If the cache has a previous successful fetch, the catalog still reflects that. If no cache exists, the URL is simply absent from the candidate list.

You'll see a **yellow banner** above the library list: `"N source(s) unavailable"` with an info button. Click the info button for the specific URLs that failed.

The catalog continues to work with whatever did fetch successfully. You can keep installing, browsing, and refreshing; the next refresh will retry the failed URLs. If a URL has gone permanently offline (the author moved their hosting, say), you can remove the subscription via Edit File.

For the principle behind not aborting on partial failure, see [sharing-arch §Drift, staleness, and other soft signals](../architecture/sharing/sharing-arch.md#drift-staleness-and-other-soft-signals).

## 7. Stale entries

A **stale** entry is a package that was in your project cache from a previous refresh but didn't re-resolve in the current one. Maybe the author dropped it, maybe the feed went offline, maybe the package was renamed. The cache entry persists with `stale = true` and a `last_seen` timestamp, so you can see what was there and decide what to do.

In the Library Browser, stale entries render with a **red dot + (stale) suffix** in the row's sublabel, plus a tooltip showing when the entry was last seen fresh. Two cases:

| State | Action available |
|---|---|
| Stale **+ uninstalled** | A trash icon appears on the row. Click to remove from the cache. |
| Stale **+ installed** | The trash icon is suppressed. Uninstall the library first, then refresh again to re-evaluate. |

The asymmetry exists because removing the cache entry while the library is still installed on disk would leave the catalog inconsistent with reality.

## 8. Edit File: when you need the TOML

Sometimes the UI doesn't cover what you need to do. Examples:

- Removing a subscription (no UI yet — coming).
- Removing a name from an `ignores` array to undo a conflict-resolution choice.
- Adding or removing a name from a `blocked` array to undo an install-safety-modal Block choice.
- Inspecting what subscriptions you actually have.

The **Edit File** button in the Library Browser toolbar opens `~/.haywire/marketplace.toml` in the embedded code editor. Save your changes there, then click Refresh to apply them.

If the file becomes malformed (a typo in TOML syntax), the Library Browser shows a **red banner** at the top of the list: `"Global marketplace is malformed..."` with a hint to click Edit File again to repair. The catalog stops rendering until the file is parseable. The Library Browser refuses to mask this kind of error — a half-resolved catalog is worse than no catalog.

## 9. Installing and updating what you found

Browsing the catalog is one thing; installing is another. They're deliberately separate steps.

To install: click an AVAILABLE row in the Library Browser. The Library Overview Editor opens on the right; click **Install** — and the install-safety modal opens (see §5.2). Behind the scenes:

- The runtime parses the entry's `install_spec`.
- It runs `uv pip install <install_spec>` (which routes to PyPI, git, or a local editable path depending on the entry's `source`).
- On success, the Library System rescans to pick up the new entry point.
- The row moves from AVAILABLE to ENABLED.

If the library declares haybale dependencies that you don't have installed, the Overview Editor's gating lets you know — but it doesn't auto-install them. You install each library individually. This is by design: the dependency information is informational, not a directive (see [library-manager-arch §What the Library Manager is not](../architecture/library-manager/library-manager-arch.md#8-boundary-what-the-library-manager-is-not)).

### 9.1 Updates available

For each installed haybale, refresh compares the installed distribution version against the cache `min_version`. When the cache says you need at least `0.5.0` and you have `0.1.0` installed, an update is available:

- The Library Browser row shows a quiet **▲ "v0.5.0 available"** indicator alongside the installed version.
- The post-refresh toast appends a count: `"... · 2 update(s) available"`.
- The Library Overview Editor's actions menu adds an **Update to v0.5.0** entry. Clicking it runs the same install pipeline against the current `install_spec`, which pip resolves to a higher matching version.

The signal is informational only — nothing auto-updates. You decide when to upgrade. The Update button does NOT open the install-safety modal: you already trusted this source by installing it originally.

OS-incompatible haybales never appear as updates either. If a haybale declares `os = ["linux"]` and you're on macOS, the Library Browser row shows a disabled Install button with a "Not available on this OS" tooltip — you can still see the entry for awareness, but the install path is blocked at the gate.

## 10. Common pitfalls

**You added a subscription but nothing shows in AVAILABLE.**
Check three things:

1. Did the auto-refresh actually run? A green toast should have appeared. If not, click Refresh manually.
2. Open Edit File and confirm the URL was actually written. It should appear under `[[markets]]` or `[[stalls]]`.
3. Check for a yellow "sources unavailable" banner. If your URL is in the failed list, the feed isn't reachable.

**A library you expected to see isn't in the catalog.**
Possible causes:

1. A conflict resolution dropped it. Look in Edit File for the library's name in any subscription's `ignores` array.
2. The feed actually doesn't carry it — check the author's marketstall directly via the URL.
3. A local library with the same name is shadowing it. Locals always win.

**You can't install — `uv pip install` fails.**
The marketplace's job ends at producing the catalog; the install step is uv's. Check:

1. The `install_spec` URL is reachable.
2. For git installs, you have git credentials configured if the repo is private.
3. Your project's `pyproject.toml` doesn't conflict with the library's declared deps.

**A library is marked stale but you want to keep using it.**
Stale is a soft signal — the library is still installed and works. The flag is purely informational, telling you it's no longer in any feed you subscribe to. You can keep using it indefinitely; if the original author republishes, the next refresh will mark it fresh again.

**You uninstalled a stale library and want to re-evaluate.**
Click Refresh. Stale-uninstalled entries that aren't re-resolved by the refresh stay in the cache (so you can decide to remove them); they're not auto-pruned. Use the trash icon to remove the entry once you're done with it.

## 11. Reading on

- The **publisher side** of this flow: [sharing-libraries](./sharing-libraries.md).
- The **conceptual model** behind these mechanics: [sharing-arch](../architecture/sharing/sharing-arch.md).
- The **library manager architecture** these tools plug into: [library-manager-arch](../architecture/library-manager/library-manager-arch.md).
- The **canonical vocabulary** (Marketplace, Marketstall, Subscription, Refresh, Stale, etc.): [glossary](../reference/glossary.md).
