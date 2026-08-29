---
status: draft
doc_template: guide
scope: Subscribing to other authors' libraries — Add Source, Refresh, installing, and what to do when a feed misbehaves
see-also:
  - ../haybale/marketplace/haybale-marketplace-arch.md
  - ../reference/files/marketplace-toml.md
  - ./sharing-libraries.md
  - ../reference/glossary.md
---

# Subscribing to marketplaces — User guide

Following another author's libraries takes three clicks: **Add Source**,
**Refresh**, **Install**. This guide starts there. Later sections cover what to
do when something misbehaves (§3) and how the machinery works (§4) —
worth reading once, not before your first install.

For the publisher side, see [sharing-libraries](./sharing-libraries.md).

## 1. Subscribe and install

There is no central registry. Each author hosts their own feed — a TOML file at
a URL — and you choose which to follow. Nothing pushes, nothing auto-installs:
you add a source, you refresh, you install.

Everything happens in the **Library Browser**, the studio's left-hand panel. Its
toolbar has exactly three buttons: Refresh, Add Source, Edit File.

### 1.0 What you already subscribe to

A fresh install starts with two subscriptions, written into
`~/.haywire/db/haybale_marketplace/marketplace.toml` on first run:

```text
https://going-haywire.github.io/haywire/marketplace.toml            the framework's own libraries
https://going-haywire.github.io/marketplace/stable/marketplace.toml the curated catalogue
```

The first carries the libraries that ship with haywire, released in lockstep
with it. The second is the **curated catalogue** — going-haywire libraries in
their own repos, plus selected third-party ones.

#### Channels

The curated catalogue publishes the same libraries on three URLs. They differ
only in what has been *proven* about the version each one names:

| channel | you get | proven |
| --- | --- | --- |
| `stable` **(default)** | versions vetted as a set | installs **and loads together with every other library in the set** |
| `latest` | the newest as of the last catalogue release | installs and loads on its own |
| `edge` | whatever is newest on PyPI right now | only that the library is in the catalogue |

`stable` is the default because of a failure nothing in the studio can see:
libraries install into **one shared environment, one at a time**, and each
install is a separate dependency resolution. Installing B can quietly upgrade
something A needed at an older pin, and A then breaks the next time you load
it. A set proven to resolve together is the only thing that closes that.

To follow a different channel, open
`~/.haywire/db/haybale_marketplace/marketplace.toml` and change the `url` — the
other two are written in as comments, so you can uncomment one and comment the
other. **Subscribe to exactly one of the three.** Two at once offer the same
library names at different versions, which every refresh then reports as a
conflict you have to settle by hand.

Past catalogue releases stay published permanently, so an installation that
must not move can pin to one:
[archives](https://going-haywire.github.io/marketplace/archives.html).

!!! note "What being in the catalogue does and does not mean"
    A listed library exists on PyPI, its name maps to that distribution, and —
    in `stable` — that version resolves alongside the rest. **Nobody reads the
    source.** Being listed is not a security review; evaluate a library as you
    would any package you install from PyPI.

### 1.1 Add a source

Click **Add Source** and paste the URL the author gave you — typically a GitHub
link to their `marketstall.toml`.

The dialog takes one field. You do not pick a type: the runtime fetches the
body, works out whether it is one author's feed or an aggregator's catalog, and
subscribes accordingly. A refresh fires automatically, and a green toast reports
what it found.

Four kinds of input are accepted:

**A page URL** — the file as you see it in your browser on GitHub or GitLab.
This is the form most authors share, and the one to reach for by default:

```text
https://github.com/alice/cool-libs/blob/main/marketstall.toml
https://gitlab.com/alice/cool-libs/-/blob/main/marketstall.toml
```

A page URL serves HTML, not TOML, so the runtime rewrites it to its raw
equivalent before storing the subscription — you never have to do that
conversion yourself.

**A raw URL** — the same file, already in raw form. Used as-is:

```text
https://raw.githubusercontent.com/alice/cool-libs/main/marketstall.toml
```

**Any URL serving TOML** — a Pages site, your own web server, or a local file.
Fetched exactly as given:

```text
https://going-haywire.github.io/haywire/marketplace.toml
file:///Users/me/dev/cool-libs/marketstall.toml
```

**A TOML block pasted straight in** — the entries themselves, with no URL at
all. Useful when an author sends you a snippet, or for testing:

```toml
[[haybales]]
name         = "haybale-cool"
version      = "0.1.0"
install_spec = "haybale-cool @ git+https://github.com/alice/cool-libs.git@v0.1.0"
```

The block is saved to `~/.haywire/db/haybale_marketplace/stalls/<name>.toml` and
subscribed as a local file, so it refreshes like any other source.

**A bare repository URL is rejected**:

```text
https://github.com/alice/cool-libs        ✗
```

The resolver needs the full path to the file so it always knows what it is
fetching. If you only have the repo link, open its README and look for a
`marketstall:share-url` block — authors publish the exact URL there.

### 1.2 Find the library

Switch the Library Browser to **AVAILABLE** (the blue cloud-download icon) to
see everything you can install but have not. Each row carries a provenance
label — "from github.com/alice" for a feed you subscribed to directly, "via
going-haywire.github.io" for one that arrived through an aggregator — so you can
always tell where a library came from.

Your project's own local libraries appear here too, marked `local`.

### 1.3 Install it

Click the row, then **Install** in the editor that opens on the right.

Because you are installing third-party code, a confirmation modal opens every
time, with a **Review source** link to read the code first. Choose **Install**
to proceed, **Cancel** to back out, or **Block source** to hide this library
from that feed permanently.

The library installs, the Library System picks it up, and the row moves from
AVAILABLE to ENABLED. No restart.

### 1.4 Keeping up to date

Click **Refresh** whenever you want to see what has changed. It is the only
operation that touches the network, and it never runs on a timer — you decide
when.

When an author publishes a newer version of something you have installed, the
row shows a quiet **▲ v0.5.0 available** and the editor's actions menu gains
**Update to v0.5.0**. Nothing auto-updates; the signal is informational. Update
does not re-open the safety modal — you already trusted this source when you
installed it.

A library that does not run on your OS shows a disabled Install button and a
"Not available on this OS" tooltip, rather than being hidden.

## 2. When two authors use the same name

Two authors can pick the same library name — there's no central namespace stopping them. The system surfaces collisions at the moment you're about to follow a new feed that would introduce one.

When Add Source detects a conflict (a package in the new source whose name matches one your existing sources already provide), a conflict-resolution dialog opens with one row per colliding name. Each row shows the name and which sources offer it; you pick which to keep.

The choice is recorded as a preference: the winning source's `preference` array gains the name, and from then on refresh resolves it that way without asking again. Preferring a source is exclusive, so the name is cleared from every other subscription — one choice settles the collision however many sources offer it.

If you change your mind later, you don't have to edit anything: every refresh lists the collision on its resolve step with a "Use this one" next to each other source, and a single click moves the preference. (Editing `~/.haywire/marketplace.toml` via Edit File still works if you prefer.)

Why you are asked here rather than at refresh: [haybale-marketplace-arch §8](../haybale/marketplace/haybale-marketplace-arch.md#8-why-the-model-is-shaped-this-way).

## 3. When something looks wrong

### 3.1 A source is unavailable

If a refresh can't fetch a subscribed URL — network error, server down, 404 — the refresh doesn't abort. It records the failed URL and falls back to the HTTP cache at `~/.haywire/cache/`. If the cache has a previous successful fetch, the catalog still reflects that. If no cache exists, the URL is simply absent from the candidate list.

You'll see a **yellow banner** above the library list: `"N source(s) unavailable"` with an info button. Click the info button for the specific URLs that failed.

The catalog continues to work with whatever did fetch successfully. You can keep installing, browsing, and refreshing; the next refresh will retry the failed URLs. If a URL has gone permanently offline (the author moved their hosting, say), you can remove the subscription via Edit File.

Why a partial failure does not abort the refresh: [haybale-marketplace-arch §8](../haybale/marketplace/haybale-marketplace-arch.md#8-why-the-model-is-shaped-this-way).

### 3.2 An entry is marked stale

A **stale** entry is a package that was in your project cache from a previous refresh but didn't re-resolve in the current one. Maybe the author dropped it, maybe the feed went offline, maybe the package was renamed. The cache entry persists with `stale = true` and a `last_seen` timestamp, so you can see what was there and decide what to do.

In the Library Browser, stale entries render with a **red dot + (stale) suffix** in the row's sublabel, plus a tooltip showing when the entry was last seen fresh. Two cases:

| State                   | Action available                                                                              |
| ----------------------- | --------------------------------------------------------------------------------------------- |
| Stale **+ uninstalled** | A trash icon appears on the row. Click to remove from the cache.                              |
| Stale **+ installed**   | The trash icon is suppressed. Uninstall the library first, then refresh again to re-evaluate. |

The asymmetry exists because removing the cache entry while the library is still installed on disk would leave the catalog inconsistent with reality.

### 3.3 Common pitfalls

**You added a subscription but nothing shows in AVAILABLE.**
Check three things:

1. Did the auto-refresh actually run? A green toast should have appeared. If not, click Refresh manually.
2. Open Edit File and confirm the URL was actually written. It should appear under `[[markets]]` or `[[stalls]]`.
3. Check for a yellow "sources unavailable" banner. If your URL is in the failed list, the feed isn't reachable.

**A library you expected to see isn't in the catalog.**
Possible causes:

1. Another source won it. Run Refresh and look at the resolve step: a name several sources offer is listed there with the source currently supplying it.
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

### 3.4 Edit File: when you need the TOML

Sometimes the UI doesn't cover what you need to do. Examples:

- Removing a subscription (no UI yet — coming).
- Moving a `preference` by hand (the refresh flow's "Use this one" does this for you).
- Adding or removing a name from a `blocked` array to undo an install-safety-modal Block choice.
- Inspecting what subscriptions you actually have.

The **Edit File** button in the Library Browser toolbar opens `~/.haywire/marketplace.toml` in the embedded code editor. Save your changes there, then click Refresh to apply them.

If the file becomes malformed (a typo in TOML syntax), the Library Browser shows a **red banner** at the top of the list: `"Global marketplace is malformed..."` with a hint to click Edit File again to repair. The catalog stops rendering until the file is parseable. The Library Browser refuses to mask this kind of error — a half-resolved catalog is worse than no catalog.

## 4. Under the hood

None of this is something you have to do. It is what the three buttons are
doing on your behalf — useful when a result surprises you.

### 4.1 What a subscription is

A **subscription** is the consumer's opt-in to follow what another author publishes. There's no central registry — there's a network of independent feeds, each one a TOML file hosted by its author, and each consumer chooses which to follow. Subscribing is explicit at every step: you add a source, you refresh, you install. Nothing pushes; nothing auto-installs.

The Library Browser in haywire-studio is the surface that drives this. It lists what you currently have installed and what's available to install, with filter toggles to scope the view. The three buttons in its toolbar — Refresh, Add Source, Edit File — are the entire consumer-facing surface.

### 4.2 What happens when you click Add

1. The URL (or pasted body) is classified by host provider and parsed.
2. A new `[[markets]]` or `[[stalls]]` entry is written to your global marketplace.
3. An auto-refresh fires.
4. If the new source's haybales collide with anything you already have, a conflict-resolution prompt opens (see [§2](#2-when-two-authors-use-the-same-name)).
5. After refresh: a green toast reports the result (e.g. `"Refreshed 3 package(s) · 1 update(s) available"`).

The auto-refresh is a convenience — you don't have to remember to click Refresh after adding a source. If you ever subscribe by hand-editing the file (via Edit File), you'll need to click Refresh yourself.

### 4.3 How an input is classified

The four forms from [§1.1](#11-add-a-source) are `BLOB_URL`, `RAW_URL`,
`PLAIN_TOML_URL` and `PASTED_BLOCK` internally. Two things are decided
separately, and conflating them is easy:

**What gets stored.** The URL written into your marketplace file must be
directly fetchable, because refresh calls it with no re-classification. A blob
URL serves HTML, so it is normalised to its raw form *before* being stored —
that is the only input that changes on the way in. A pasted block is written to
disk first and stored as the resulting `file://` URL.

**Which section it lands in.** That comes from the fetched body, not the URL:

- Contains `[[markets]]` or `[[stalls]]` → a `[[markets]]` subscription (it is
  an aggregator's catalog).
- Contains only `[[haybales]]` → a `[[stalls]]` subscription (it is a single
  marketstall).

So a Pages URL and a GitHub blob URL can both end up as either kind — the shape
of what they serve decides, not where they point.

### 4.4 What refresh does

The **Refresh** button is the only operation that talks to the network. It does not run on a timer. You decide when to refresh.

What refresh does, in concept:

1. Reads your global marketplace.
2. Fetches every subscribed `[[markets]]` and `[[stalls]]` URL.
3. For each `[[markets]]` body, reads its `[[stalls]]` references one level deep and fetches those too. Inline `[[haybales]]` in the markets body are also collected.
4. For each haybale, applies the subscription's `blocked` array (silently drops names you've actively rejected). Each surviving haybale is stamped with the subscription's URL as its `via` field.
5. Assembles the combined candidate list and applies the heaps shadow (your project's path-based libraries win over any remote of the same name).
6. Deduplicates by name, honouring `preference` where you named a winning source and falling back to first occurrence where you have not. Every name several sources offered is reported on the resolve step so the choice is visible before it is applied.
7. Marks newly-missing entries as stale (see [§3.2](#32-an-entry-is-marked-stale)). Blocked names are filtered out of the stale-rescue step so they fully disappear rather than survive as `stale=true`.
8. Counts installed libraries whose cache `version` exceeds the installed version (updates available, see [§1.4](#14-keeping-up-to-date)).
9. Writes the result to your project marketplace's `[[caches]]` section.

After a successful refresh, a green toast summarizes: `"Refreshed N package(s) · M source(s) unavailable · K newly stale · L update(s) available"`. The middle phrases appear only when relevant.

### 4.5 What install does

Browsing the catalog and installing are deliberately separate steps. Behind the Install button:

- The runtime parses the entry's `install_spec`.
- It runs `uv pip install <install_spec>` (which routes to PyPI, git, or a local editable path depending on the entry's `source`).
- On success, the Library System rescans to pick up the new entry point.
- The row moves from AVAILABLE to ENABLED.

Installing a **local** library (one of your project's own `[[heaps]]`) runs
`uv pip install -e <path>` instead, so it stays editable and hot-reloads.

The safety modal's three buttons write different things. **Block source** adds
the library's name to the `blocked` array on the subscription that resolved it —
the one whose URL matches the cache entry's `via` — so it disappears from
AVAILABLE immediately. The only way back is editing `marketplace.toml` by hand
([§3.4](#34-edit-file-when-you-need-the-toml)). **Cancel** writes nothing. The
modal fires on every install, with no first-time-only suppression.

If the library declares haybale dependencies that you don't have installed, the Overview Editor's gating lets you know — but it doesn't auto-install them. You install each library individually. This is by design: the dependency information is informational, not a directive (see [haybale-marketplace-arch §8](../haybale/marketplace/haybale-marketplace-arch.md#what-the-library-manager-is-not)).

### 4.6 Where the state lives

Your project's library state lives in two files. Knowing what each is for helps when you have to reason about what's happening.

**Global marketplace** — per-machine, your subscriptions.

```text
~/.haywire/db/haybale_marketplace/marketplace.toml
```

`[[markets]]` for remote aggregators, `[[stalls]]` for individual marketstall feeds. 

Pasted-TOML inputs are saved as a local stall file and referenced via a
`file://` `[[stalls]]` entry.

**Project marketplace** — per-project, travels with the source tree.

```text
<project>/.haywire/marketplace.toml
```

This project's path-based libraries (`[[heaps]]`, written by `haywire init`) and
the resolved catalog cache (`[[caches]]`, written by Refresh).

You generally interact with the global file (subscriptions are a user concern). The project file is managed for you — `haywire init` sets up `[[heaps]]`, and Refresh maintains `[[caches]]`.

Field by field: [marketplace.toml](../reference/files/marketplace-toml.md). Why the split exists: [haybale-marketplace-arch §8](../haybale/marketplace/haybale-marketplace-arch.md#8-why-the-model-is-shaped-this-way).

## 5. Reading on

- The **publisher side** of this flow: [sharing-libraries](./sharing-libraries.md).
- Why the model is shaped this way: [haybale-marketplace-arch §8](../haybale/marketplace/haybale-marketplace-arch.md#8-why-the-model-is-shaped-this-way).
- The **library manager architecture** these tools plug into: [haybale-marketplace-arch](../haybale/marketplace/haybale-marketplace-arch.md).
- The **canonical vocabulary** (Marketplace, Marketstall, Subscription, Refresh, Stale, etc.): [glossary](../reference/glossary.md).
