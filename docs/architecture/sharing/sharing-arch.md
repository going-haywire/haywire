---
status: draft
doc_template: philosophy
scope: The philosophy behind haywire's sharing model — how libraries move between authors and consumers, the trust assumptions, the lifecycle, the non-goals
see-also:
  - ../library-manager/library-manager-arch.md
  - ../library-system/library-system-arch.md
  - ../../components/haybale-package/haybale-package-canon.md
  - ../../reference/glossary.md
  - ../../reference/publish_releases.md
---

# Sharing — Philosophy

*An essay on how haywire libraries move between authors and consumers, and the reasoning behind the shape of that flow. No code, no UI, no schemas. The vocabulary used here is defined in [reference/glossary.md](../../reference/glossary.md).*

---

## What we are trying to make true

Haywire is a system in which independent authors write visual-programming libraries, and independent consumers compose those libraries into their own projects. The sharing model has to make three things true at once:

The first is **agency for authors**: anyone can publish a library at any time, without permission from a central authority. A library author should be able to take work they have running on their own machine and make it findable by anyone else — using infrastructure they already control (a git repository, perhaps a static page), not infrastructure they have to apply for.

The second is **agency for consumers**: anyone subscribing to other people's libraries should retain full control over what enters their project. Subscription should be opt-in at every step. A consumer should be able to follow a feed without losing the right to refuse any specific package from that feed. And a consumer's project should always reflect the consumer's choices, not the union of every author's choices.

The third is **stability under partial failure**: this is a network of independent feeds, hosted by independent people, on independent infrastructure. Feeds will go offline. URLs will rot. Authors will rename packages. A working project should keep working through all of that, with a clear story for how to react when something it depends on changes.

The rest of the document is about what those three commitments force us to do, and what they cost.

---

## Two sides, one cycle

There are two roles in haywire's sharing model, and most users will be both at different moments.

The **author** is the person whose source code defines a library. They write it inside a project of their own, run it, refine it, and at some point decide it is worth sharing. The act of sharing is not the act of publishing to a registry — it is the act of producing a small, self-contained description of what they have made and where to get it, and then placing that description somewhere others can read it.

The **consumer** is the person who wants to use someone else's library inside their own project. They start by deciding which authors they trust enough to follow. Subscribing to an author is a one-time, explicit act. Once subscribed, the consumer can periodically ask haywire to refresh: "tell me what's available from everyone I follow." From that list, they pick the specific libraries they want to install.

The two roles connect through a published artifact — a document the author produces and the consumer reads. Neither side talks to the other through a server we control. The artifact lives wherever the author chooses to put it, and the consumer reaches it directly. This is deliberate: a central coordinator would be a central point of failure and a central point of policy, and the model is designed to need neither.

The cycle, then, is short. An author finishes work. The author publishes. A consumer who follows that author refreshes. The consumer sees the new offering. The consumer chooses to install. That is the whole loop. Everything else in this document is about what happens when one of those steps doesn't go cleanly.

---

## The aggregator, not the publisher

Within this model, haywire itself plays a deliberately small role.

It does not host libraries. It does not run a server. It does not vet, sign, or rank what authors publish. The official haywire project does publish *its own* libraries through the same mechanism every other author uses — there is no privileged path. A user who installs haywire is, in effect, subscribing to the haywire team's feed by default, but that subscription is no different in kind from one to any other author.

What haywire does is aggregate. The consumer points haywire at the authors they want to follow, and haywire combines those feeds into a single browsable catalog. The catalog is a *view*, computed from the subscription list at the moment of refresh. It is not a database. There is no canonical "list of all haywire libraries" anywhere — there is only what each individual consumer has chosen to subscribe to.

This is why the system has so few moving parts at the center. The hard problem isn't building a registry; the hard problem is making a network of independently-hosted feeds *feel* like a coherent catalog without giving up the property that anyone can join it.

---

## Why two tiers

A consumer's project state lives in two distinct places, and the split is load-bearing.

One belongs to the **user** — the person sitting at the keyboard. It records who they have decided to follow, what direct packages they have manually pasted in, and which path-based libraries they want available across every project they open. This is per-machine, not per-project. It survives switching between projects. It is the user's library bookcase.

The other belongs to the **project** — a specific piece of work being built. It records what the project itself depends on (its own internal libraries, plus any sibling libraries needed for development), and a cached snapshot of what was available from the user's subscriptions the last time the project refreshed. This is per-project. It travels with the source repository if shared.

The reason for the split is that these two questions have different answers. "What feeds do I follow?" is an answer about the person. "What does this project need?" is an answer about the project. Mixing them — putting subscriptions into the project, or putting per-project dependencies into the user bookcase — causes real bugs: subscriptions leaking into projects you didn't intend, project deps polluting unrelated work, dev-mode libraries from one experiment becoming visible in another.

The two-tier model isolates these concerns. It also makes the trust model legible: anything in the user tier is something the user explicitly opted into; anything in the project tier is something this specific project needs. A reader inspecting either file can tell, at a glance, who put it there and why.

---

## The refresh cycle

The link between subscription and installation is **refresh**. It is the moment when the consumer asks haywire to reach out to every feed they follow and report back what's available.

Refresh is explicit, not automatic. The consumer triggers it. The system does not poll feeds on a timer, because that would mean making network calls the user didn't ask for, and that would mean network failures the user can't time. Refresh runs when the user opts to run it, and not otherwise.

What refresh does is conceptually simple but worth naming clearly. It fetches each subscribed feed. It reads what's in each feed. It assembles a candidate list of packages drawn from every feed plus any direct entries the user has pasted in plus any local libraries the project knows about. It applies conflict resolution to that list (more on which in a moment). And it writes the result — the resolved, conflict-free catalog — to the project's cache.

The cache matters because refresh is the only network step. Once the cache is written, every other operation — browsing the catalog, installing from it, inspecting it — works offline. A consumer can refresh once at the start of a session and then work entirely from local state until they choose to refresh again. This is part of the stability-under-partial-failure commitment: a project that has refreshed successfully once is fully functional even if every feed it follows is offline.

---

## Bounded resolution

A subtle but important rule: when haywire fetches a remote feed, it reads what the feed says about *its own* packages and about other feeds *it* depends on, but it does not chase that second level. If a feed you follow lists another feed as a source, haywire will fetch the packages that feed declares but will not then follow *that* feed's onward references.

The reason is bounded blast radius. Without the limit, a single subscription could pull in arbitrarily many feeds transitively, each maintained by someone you have never heard of, each with the power to add packages to your catalog. The recursion would also be unbounded — there's no protocol-level mechanism preventing two feeds from referencing each other.

By stopping at one level of resolution, haywire keeps the trust model legible. You trust the people you follow directly. You do not, by extension, trust whoever they trust. If a feed you follow wants to introduce you to another feed, that's a recommendation the feed's documentation can make — and you, the consumer, can act on it by adding the other feed to your own subscription list. The act of trusting remains yours.

---

## Resolving conflicts

There is no central namespace, so two authors can legitimately publish a package under the same name. When the consumer's catalog draws from multiple feeds, these collisions surface — and they have to be resolved before installation, because two libraries claiming the same name cannot coexist in a project.

The principle is simple: **the user is asked, and asked at the moment of agency**.

That moment is when the user adds a subscription. The act of adding a feed is explicit and deliberate; the user is already deciding what to trust. Before the new subscription takes effect, haywire compares what the feed provides against what the consumer is already getting from the rest of their subscriptions. If any name collides, the user is shown the conflict — *this new source provides a package by this name, your existing source also provides one* — and asked which to keep. The user picks. The decision is recorded so future refreshes honor it without re-asking, and the chosen feed becomes the authoritative source for that name going forward.

Asking at intake matters for two reasons. The user is already paying attention — adding a feed is a deliberate act, and a question fits the moment. Refresh, by contrast, is a maintenance step the user runs to *avoid* surprises, not to encounter them. Prompting at refresh would punish the user for keeping their catalog fresh.

A second kind of overlap is not really a conflict at all: two feeds the consumer follows happen to share an upstream, so they end up offering the same package. Both deliver the same thing, so there is nothing to choose. The catalog presents the package once. No prompt, no decision needed — the duplication is a topology coincidence, not a competing offer.

Local libraries sit outside this whole picture. A path-based library a project has wired in for development always wins over any remote package of the same name. This is structural, not user-chosen: locals exist precisely to let an author's in-progress copy shadow whatever happens to be published under the same name. Without this rule, a remote of the same name would silently override the work the author is in the middle of doing.

One thing the system explicitly does not do is choose by version. When two feeds advertise the same package, haywire does not compare their versions and pick the higher one. Version selection belongs to the install layer (pip, uv), which haywire defers to for actually putting code on disk. The catalog's job is to describe *what is available*; picking between competing offers of the same thing is the user's decision, not the catalog's.

---

## Drift, staleness, and other soft signals

A network of independent feeds is going to be partly broken at any given moment. Servers go down; URLs change; authors lose interest in libraries they once published. The model's stance on all of this is consistent: surface the discrepancy, keep working with what's known, let the consumer decide what to do about it. The system reports; it does not panic.

A feed can be **unavailable** — temporarily unreachable, permanently 404'd, behind a server having a bad day. Refresh records which feeds failed to fetch. It does not abort, and it does not remove cached entries from previously-successful fetches of those feeds. The consumer sees an indicator that some sources were unavailable; the catalog continues to reflect the last known state. Work continues.

A package can be **stale** — present in the project's cache from a previous refresh, but not re-resolved by the current one. Maybe the feed it came from went away; maybe the author renamed the package; maybe the feed dropped it. The cache entry persists, marked as stale, so the consumer can see what was there and decide whether to remove it. If the stale package is still *installed*, the cache entry is locked from removal: pulling the catalog entry while the library is still running on disk would be incoherent. If the package is uninstalled, the consumer can drop the stale entry at their leisure.

A library's *declared* dependencies can **drift** from what it actually imports. An author can add an import to their library's source without remembering to update either of the two manifests that describe what the library needs. The runtime manifest controls who's required-for-enable in haywire's own dependency graph; the packaging manifest controls what pip resolves at install time. When they diverge, the published library ships with declarations that lie about its real requirements.

Drift is detected, not enforced. Haywire offers tooling that compares a library's actual imports against its declared dependencies and reports the difference. Authors choose when to apply the corrections. The publish step can be configured to refuse drift outright, to warn about it, or to silently fix it. The model's stance is that drift is the author's responsibility, but the system should make drift visible rather than letting it ship.

The common thread across these three signals — unavailable, stale, drift — is that the system records the discrepancy and surfaces it, then lets the human decide what to do. A registry that automatically pruned stale entries would lose information; a publish flow that hard-failed on drift would lock authors out at the wrong moments. Information is cheaper to provide than to take back.

---

## The lifecycle of a published library

Putting the pieces together: what does the full arc look like, from an author opening a project to a consumer installing the result?

The author starts inside a project. They write code, importing whatever they need — framework pieces, other haywire libraries, third-party packages. As they work, the manifests that describe their library's dependencies fall out of sync with the imports their source has accumulated. This is normal: authors add imports as they think; manifests reflect a snapshot in time.

When the author decides to publish, the system does a comparison pass. The actual imports become the source of truth; the manifests get reconciled against them. The author chooses how aggressive the reconciliation is — additive only, or full replacement. This reconciliation is the difference between a library that says "I depend on X, Y, Z" and one that actually does.

The output is a small description of the library: its name, its version, its declared metadata, and an instruction for how to install it (typically a git URL pointing at the source). The author writes this description into a publish file alongside any other libraries they author, and places the file somewhere consumers can fetch it — usually a static web host attached to the same repository.

A consumer learns about the author through some out-of-band channel — a link in a blog post, a recommendation from a colleague, a mention in documentation. The consumer adds the author's publish URL to their own subscription list. The next refresh fetches the file, reads the listed packages, and adds them to the consumer's catalog. The consumer browses the catalog, picks the package they want, and installs it.

Once installed, the library is no longer a marketplace concept. It is a piece of code running in the consumer's project, subject to the same enable/disable lifecycle as any other library. It can be uninstalled later. Its source can be inspected. It participates fully in haywire's normal operation. The marketplace was a discovery mechanism; once discovery is done, the marketplace step is over.

---

## What this model does not try to do

The model is shaped by what it explicitly declines to solve. Each non-goal exists because attempting it would compromise one of the three commitments at the top.

It does not provide a **trusted central namespace**. Two authors can pick the same package name; the system surfaces this as a conflict and asks the consumer. There is no global "haywire-foo" registration that one author owns and another can't. This is the price of letting anyone publish without permission.

It does not provide **signed packages**, **package verification**, or any cryptographic trust chain. Authors host their own publish files; if a consumer wants to verify what they're installing, they can read the source at the install URL before installing. Adding signing later would not change the architecture, but the current model has zero crypto and is deliberately shaped that way to keep the publish path as low-friction as possible.

It does not perform **transitive dependency resolution** across haywire libraries. If library A imports library B, A's manifest declares B, and pip installs B alongside A through its normal mechanism. Haywire does not track or resolve those chains; that's pip's job. The model's responsibility ends at the point where the consumer chooses to install — from there, ordinary Python packaging takes over.

It does not provide **lockfiles** or **reproducible installs** at the haywire level. Reproducibility is the project's responsibility, expressed through standard Python tooling (uv lockfiles, version pins in the project's own manifest). Haywire's catalog is a discovery layer, not a build system.

It does not **curate**. No source is more authoritative than any other in the data; the haywire team's official feed is one feed among many. A consumer who subscribes only to the official feed sees only haywire-team libraries; a consumer who subscribes to no feeds at all sees no libraries beyond their own project's locals. The catalog is exactly what the consumer asked for, no more.

It does not provide **forced updates**. Subscriptions don't push; consumers pull. A consumer can run the same project for a year without refreshing once, and the catalog they see is the one they cached. This is part of how the model copes with feeds going offline: nothing pulls until the consumer asks.

It does not provide **mirrors**, **CDNs**, or any **redundancy** for publish files. If an author's feed goes down, it's down for everyone who follows them until it comes back. Consumers who care about availability can subscribe to mirrors of feeds they value, but creating those mirrors is an author-side concern outside the model.

The list of non-goals is long on purpose. Each item is a feature that, if added, would make the model more powerful and more brittle simultaneously — adding policy, central control, or hidden complexity. The model's value comes from refusing those temptations.

---

## Reading on

Concrete mechanisms — file formats, UI flows, command-line surfaces, code-level architecture — live in the documents linked from the frontmatter `see-also`. This essay is the orientation; those are the maps.
