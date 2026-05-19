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
| **Global marketplace** | `~/.haywire/marketplace.toml` | Your subscriptions (`[[marketplaces]]`, `[[marketstalls]]`), any packages you've pasted in directly (`[[packages]]`), and any cross-project local libraries (`[[locals]]`). Per-machine. |
| **Project marketplace** | `<project>/.haywire/marketplace.toml` | This project's path-based libraries (`[[locals]]`, written by `haywire init`) and the resolved catalog cache (`[[packages]]`, written by Refresh). Per-project; travels with the source tree. |

You generally interact with the global file (subscriptions are a user concern). The project file is managed for you — `haywire init` sets up `[[locals]]`, and Refresh maintains the cache.

For a deep dive into the split and why it exists, see [sharing-arch §Why two tiers](../architecture/sharing/sharing-arch.md#why-two-tiers).

## 3. Add Source: subscribing to a feed

Click **Add Source** in the Library Browser toolbar. A modal opens with three tabs.

| Tab | What you paste | Adds to the global marketplace as |
|---|---|---|
| **Marketplace** | URL of a remote marketplace file (aggregates multiple authors' packages and/or marketstall references) | `[[marketplaces]]` |
| **Marketstall** | URL of a single-author marketstall file (one author's library list) | `[[marketstalls]]` |
| **Direct package** | A full `[[packages]]` TOML block, pasted verbatim | `[[packages]]` |

Most authors will give you a URL like `https://maybites.github.io/haywire/marketplace.toml` — that's a marketplace (note the filename can be either; the *content* determines which tab to use). When in doubt: if the file you're pointed at contains `[[marketstalls]]` or `[[marketplaces]]` sections, it's a marketplace. If it only has `[[packages]]`, it's a marketstall.

A `file://` URL works too — useful for testing local fixtures or air-gapped setups.

### 3.1 What happens after you click Add

1. The URL is appended to the appropriate section in your global marketplace.
2. The runtime fetches the URL immediately to check for conflicts (see §4).
3. If no conflicts: an auto-refresh fires.
4. After refresh: a green toast reports the result (`"Refreshed 3 package(s)"`).

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
2. Fetches every subscribed marketplace and marketstall URL.
3. For each remote marketplace, reads its `[[marketstalls]]` references one level deep and fetches those too.
4. Assembles a candidate list from: global `[[packages]]`, global `[[locals]]`, project `[[locals]]`, and everything fetched.
5. Applies your `ignores` (per-subscription skip lists).
6. Applies the locals-win rule (your path-based libraries shadow any remote of the same name).
7. Deduplicates by name (first occurrence wins for any straggler).
8. Marks newly-missing entries as stale (see §7).
9. Writes the result to your project marketplace's `[[packages]]` cache.

After a successful refresh, a green toast summarizes: `"Refreshed N package(s) · M source(s) unavailable · K newly stale"`. The middle and right phrases appear only when relevant.

### 5.1 The Available section

The Library Browser's AVAILABLE filter (blue cloud-download icon) shows the resolved catalog: every package not currently installed. Clicking a row opens its Library Overview Editor for install.

Locals — your project's path-based libraries — show up here too, even though they aren't on any remote feed. They're presented as `source = "local"` entries. Installing them runs `uv pip install -e <path>` so they become editable.

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
- Adding a `[[locals]]` entry to the global file for cross-project use.
- Inspecting what subscriptions you actually have.

The **Edit File** button in the Library Browser toolbar opens `~/.haywire/marketplace.toml` in the embedded code editor. Save your changes there, then click Refresh to apply them.

If the file becomes malformed (a typo in TOML syntax), the Library Browser shows a **red banner** at the top of the list: `"Global marketplace is malformed..."` with a hint to click Edit File again to repair. The catalog stops rendering until the file is parseable. The Library Browser refuses to mask this kind of error — a half-resolved catalog is worse than no catalog.

## 9. Installing what you found

Browsing the catalog is one thing; installing is another. They're deliberately separate steps.

To install: click an AVAILABLE row in the Library Browser. The Library Overview Editor opens on the right; click **Install**. Behind the scenes:

- The runtime parses the entry's `install_spec`.
- It runs `uv pip install <install_spec>` (which routes to PyPI, git, or a local editable path depending on the entry's `source`).
- On success, the Library System rescans to pick up the new entry point.
- The row moves from AVAILABLE to ENABLED.

If the library declares haybale dependencies that you don't have installed, the Overview Editor's gating lets you know — but it doesn't auto-install them. You install each library individually. This is by design: the dependency information is informational, not a directive (see [library-manager-arch §What the Library Manager is not](../architecture/library-manager/library-manager-arch.md#8-boundary-what-the-library-manager-is-not)).

## 10. Common pitfalls

**You added a subscription but nothing shows in AVAILABLE.**
Check three things:

1. Did the auto-refresh actually run? A green toast should have appeared. If not, click Refresh manually.
2. Open Edit File and confirm the URL was actually written. It should appear under `[[marketplaces]]` or `[[marketstalls]]`.
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
