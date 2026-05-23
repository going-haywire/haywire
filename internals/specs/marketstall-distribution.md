---
status: ready-for-implementation
scope: The full marketstall/marketplace surface — file formats, URL distribution model, host-provider extensibility, author/consumer flows, refresh semantics, and a one-shot rename of the existing vocabulary.
---

# Marketstall distribution

A decentralized scheme for distributing Haywire libraries via git-hosted repositories. Authors publish a single TOML file at the root of their repo; consumers paste a human-readable URL into their Library Manager. No central registry; the source of truth is each author's repository.

## 1. Vocabulary

| File               | Role                                                                          | What it contains                                                                                                     |
| ------------------ | ----------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| `marketstall.toml` | Author's publish file                                                         | `[[haybales]]` only — the libraries this author distributes from this repository                                     |
| `marketplace.toml` | Consumer's catalog (global or project) — also: aggregator's published catalog | `[[markets]]`, `[[stalls]]`, optionally `[[haybales]]` inline, plus (project-side only) `[[heaps]]` and `[[caches]]` |

| Section        | Where                                                                                          | Meaning                                                                                                                                                                                                                                      |
| -------------- | ---------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `[[haybales]]` | Inside `marketstall.toml`; optionally inside `marketplace.toml` (aggregator or PyPI-only case) | One library entry. Fields: `name`, `min_version`, `label`, `description`, `author`, `source`, `install_spec`, `tags`, `dependencies`, `source_url`, `docs_url`. Same shape as the existing `MarketplaceEntry` dataclass (renamed `Haybale`). |
| `[[markets]]`  | Inside `marketplace.toml` (global)                                                             | A subscription to a remote *marketplace*. Carries `url`, `ignores`, `doubles`, `blocked`.                                                                                                                                                    |
| `[[stalls]]`   | Inside `marketplace.toml` (global)                                                             | A subscription to a remote *marketstall*. Carries `url`, `ignores`, `doubles`, `blocked`.                                                                                                                                                    |
| `[[heaps]]`    | Inside `marketplace.toml` (project)                                                            | Unpublished path-based libraries (the project's own, plus dev-repo siblings under `--dev`).                                                                                                                                                  |
| `[[caches]]`   | Inside `marketplace.toml` (project)                                                            | Refresh result. Each entry is a resolved `Haybale` plus cache-only fields `via`, `last_seen`, `stale`.                                                                                                                                       |

The structural distinction between `[[markets]]` and `[[stalls]]` is **how the runtime parses the response**, not how subscriptions are tracked — both carry identical fields. The Library Manager decides which section to write a new subscription to by inspecting the fetched body, not by asking the user to declare it.

## 2. The marketstall format

### Filename and location

A marketstall file lives in one of two places, depending on the author's pattern:

- **Single-author default**: `marketstall.toml` at the **repository root**. This is what `haywire share --save` produces by default; it lists every library the author publishes from this repo. Pasting the bare repo URL into Add Source resolves to this file (see §7).
- **Aggregator layout**: `stalls/<dist-name>.toml`, one file per published library. Used by the official Haywire feed and by any author who wants consumers to be able to subscribe to a single library at a fine-grained URL without taking the whole repo.

The two patterns coexist. A repository can have a top-level `marketstall.toml` *and* a `stalls/` directory if the author wants both — the runtime treats each file as a marketstall in its own right.

### Schema

```toml
[[haybales]]
name         = "haybale-cool-lib"
label        = "Cool Lib"
min_version  = "0.1.0"
description  = "One-line summary."
author       = "Alice Author"
source       = "git"
install_spec = "haybale-cool-lib @ git+https://github.com/alice/cool-libs.git#subdirectory=barn/haybale-cool-lib"
tags         = ["vision", "experimental"]
os           = ["macos", "linux"]
dependencies = ["haybale-core"]
source_url   = "https://github.com/alice/cool-libs"
docs_url     = "https://raw.githubusercontent.com/alice/cool-libs/main/barn/haybale-cool-lib/haybale_cool_lib/"
```

A top-level `marketstall.toml` may contain multiple `[[haybales]]` entries — an author publishing several libraries from one repository writes all of them into the single file at the root.

A per-haybale `stalls/<dist-name>.toml` file contains exactly one `[[haybales]]` entry.

A marketstall (either pattern) does NOT contain `[[markets]]`, `[[stalls]]`, `[[heaps]]`, or `[[caches]]` sections. If a server returns such sections inside what's fetched as a marketstall, the runtime silently drops them.

### Field semantics

| Field          | Required | Description                                                                                                                                                        |
| -------------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `name`         | yes      | Pip distribution name. Underscored module name is derived from this.                                                                                               |
| `min_version`  | yes      | Version floor for pip. In practice, this is the version the author is currently publishing (since `haywire share` regenerates the file at every release). See §10. |
| `label`        | no       | Human display name. Falls back to a Title-cased derivation of `name`.                                                                                              |
| `description`  | no       | One-line description.                                                                                                                                              |
| `author`       | no       | Author name(s).                                                                                                                                                    |
| `source`       | no       | One of `"pypi"`, `"git"`, `"local"`. Drives install-spec interpretation and version-fetching strategy.                                                             |
| `install_spec` | yes      | Passed verbatim to `uv pip install`.                                                                                                                               |
| `tags`         | no       | Filter tags for the Library Browser.                                                                                                                               |
| `os`           | no       | List of platforms the library supports. Declaration values: `"macos"`, `"windows"`, `"linux"`. Absent (or omitted) means "all platforms". See §2.1.                |
| `dependencies` | no       | Pip distribution names of other haybales this one depends on. NOT the underscore form used in `@library(dependencies=[...])`.                                      |
| `source_url`   | no       | URL to the repository (or source location) homepage.                                                                                                               |
| `docs_url`     | no       | URL or local path to the docs directory.                                                                                                                           |

### 2.1 The `os` field

The `os` field declares which operating systems the library supports. Source of truth: the library's `pyproject.toml` has a `[tool.haywire]` section with an `os` array.

```toml
[tool.haywire]
os = ["macos", "linux"]
```

`haywire share` reads this value from each barn library's pyproject and copies it to the `os` field of the generated `[[haybales]]` entry. Absent from pyproject → absent from the marketstall → interpreted as "all platforms".

**Declaration values**: `"macos"`, `"windows"`, `"linux"`. These are the only platforms the runtime can map definitively from `platform.system()`. An author can declare exactly the subset they have tested on.

**`"other"` is a runtime-only sentinel**, never a valid declaration value. The runtime maps unrecognized `platform.system()` results to `"other"` so the mapping function is total; libraries running on an unrecognized OS see a current-platform of `"other"`. Because `"other"` is not declarable, a haybale on an unknown OS never matches any platform list — but the absent-default (= "all platforms") still lets pure-Python libraries install on unknown OSes when no `os` is declared.

`haywire share` validates the `[tool.haywire].os` values read from each library's `pyproject.toml`. An entry containing `"other"` (or any value outside the three accepted ones) produces a clear error: *"Invalid os value 'X' in barn/`<library>`/pyproject.toml. Declarable values: macos, windows, linux."*

**Edit dialog surface**: the Library Overview Editor's Edit dialog shows an OS multi-select **only for libraries the user can author** — i.e., `[[heaps]]` libraries with a writable `pyproject.toml` in their workspace. For installed wheels (installed via pip/uv), the OS list is **displayed read-only** with no edit affordance — the wheel's `pyproject.toml` either lives inside `site-packages` (overwritten on next install) or doesn't exist at all, so editing it is meaningless. Saving on a heap library writes the chosen values back into the library's `pyproject.toml` `[tool.haywire].os`. Selecting nothing (or all three) removes the key (= "all platforms").

**Library Browser behavior**: an installable haybale whose `os` list doesn't include the current platform is shown in the AVAILABLE section *normally*, but its Install button is disabled. A tooltip on the disabled button explains: *"Not available on this OS; this library targets: macos, linux."* This is the most discoverable treatment — the user sees the library exists, learns why it's not installable on this machine, and can revisit on a different platform.

The runtime maps `platform.system()` to one of four values once at session start:

| `platform.system()` | Mapped to                                       |
| ------------------- | ----------------------------------------------- |
| `"Darwin"`          | `"macos"`                                       |
| `"Windows"`         | `"windows"`                                     |
| `"Linux"`           | `"linux"`                                       |
| anything else       | `"other"` (runtime sentinel; not declarable)    |

## 3. The marketplace format

A `marketplace.toml` plays two distinct roles depending on where it lives:

### 3.1 Consumer's marketplace (`~/.haywire/db/haybale-marketplace/marketplace.toml`)

The consumer's marketplace lives in its own per-library data folder under `~/.haywire/db/`. This folder is the global data space allocated to the (future) `haybale-marketplace` library — the Library Manager surface is being carved out as its own haybale, and giving it a dedicated subdirectory now means no migration later. Sibling libraries get sibling folders under `~/.haywire/db/<haybale-name>/` by the same convention.

```text
~/.haywire/db/haybale-marketplace/
├── marketplace.toml           # the file shown below
└── stalls/
    └── <dist-name>.toml       # one file per direct-paste subscription
```

```toml
[[markets]]
url = "https://github.com/going-haywire/haywire/blob/main/marketplace.toml"
ignores = []
doubles = []
blocked = []

[[stalls]]
url = "https://github.com/alice/cool-libs/blob/main/marketstall.toml"
ignores = ["haybale-mesh"]
doubles = []
blocked = ["haybale-untrusted"]

[[stalls]]
url = "file:///Users/me/.haywire/db/haybale-marketplace/stalls/internal-experiment.toml"
ignores = []
doubles = []
blocked = []
```

This file records: who the user is following (`[[markets]]` and `[[stalls]]`), and the per-source overrides (`ignores`, `doubles`, `blocked`). It contains no haybale definitions of its own — direct-paste entries are persisted as one-`[[haybales]]`-entry marketstalls under `~/.haywire/db/haybale-marketplace/stalls/` and referenced via `[[stalls]]` with `file://` URLs.

The three filter arrays carry distinct semantics:

- **`ignores`** — names skipped silently from this source. Populated by the conflict-resolution prompt at Add Source time (§8.3). The user did not actively reject the haybale; they preferred another source.
- **`doubles`** — names that two `[[markets]]` entries silently dedup to. Diagnostic only.
- **`blocked`** — names the user actively rejected via the install safety modal (§7.4). Per-subscription: blocking `haybale-foo` from source A does not affect source A's neighbor source B (which may legitimately offer a different haybale under the same name). Blocked haybales are **fully hidden** from the Library Browser's AVAILABLE list; the only un-block path is editing this file by hand. Persistent and deliberate by design.

### 3.2 Project's marketplace (`<project>/.haywire/marketplace.toml`)

```toml
[[heaps]]
name = "haybale-my-project"
path = "/abs/path/to/my-project/barn/haybale-my-project"
label = "My Project"
description = "Local library for the my-project project"

[[heaps]]
name = "haybale-core"
path = "/abs/path/to/haywire-repo/barn/haybale-core"
label = "Core"
description = "Core library for Haywire node system..."

[[caches]]
name        = "haybale-haystack"
label       = "Haystack"
min_version = "0.0.1"
source      = "git"
install_spec = "haybale-haystack @ git+..."
via         = "https://going-haywire.github.io/haywire/stalls/haybale-haystack.toml"
last_seen   = "2026-05-20T08:14:23Z"
stale       = false
```

This file records: path-based unpublished libraries (`[[heaps]]`, written by `haywire init`), and the cached refresh result (`[[caches]]`, written by `MarketplaceState.refresh()`). It contains no subscriptions.

### 3.3 Aggregator's marketplace (published)

A *curator* — someone who recommends other people's libraries — publishes a `marketplace.toml` whose `[[stalls]]` entries point at other authors' marketstall files. This is structurally identical to the consumer's global marketplace, just exposed via a public URL.

The official Haywire feed is exactly this shape: `marketplace.toml` at `https://going-haywire.github.io/haywire/marketplace.toml` containing `[[stalls]]` entries that reference per-haybale stall files at `https://going-haywire.github.io/haywire/stalls/<dist-name>.toml`. See §11.

A published `marketplace.toml` MAY also contain `[[haybales]]` entries inline alongside its `[[markets]]` and `[[stalls]]` references. Two cases motivate this:

- **PyPI-only / private-repo authors.** An author who publishes a library to PyPI but keeps the source repository private has nowhere to host a separate `marketstall.toml` file. They can publish a `marketplace.toml` (perhaps on a personal site) with one or more `[[haybales]]` entries declared inline, no marketstall file involved.
- **Aggregators who also publish.** A curator who recommends other people's stalls AND publishes their own libraries can declare their own haybales directly in the marketplace file instead of needing a separate marketstall.

When the runtime fetches a `[[markets]]` URL, it parses the response as a marketplace and consumes (a) the `[[stalls]]` references one level deep AND (b) any inline `[[haybales]]` entries. When it fetches a `[[stalls]]` URL, it parses the response as a marketstall (reading `[[haybales]]`, no further recursion).

## 4. URL distribution model

### 4.1 The share URL

The canonical public identifier for a marketstall or marketplace is its **blob URL** — the human-browsable URL to the file on the hosting platform:

```text
{scheme}://{host}/{owner}/{repo}/{blob-segment}/{ref}/marketstall.toml
```

(For aggregator-style repos that use per-haybale stalls, the path becomes `stalls/<dist-name>.toml` — see §11. The top-level `marketstall.toml` is the default for single-author publishers.)

- **host** — git host (`github.com`, `gitlab.com`, etc.)
- **owner/repo** — namespace and repository name on that host
- **ref** — branch name, tag, or commit SHA; the author's choice expresses the update policy
- **blob-segment** — host-specific URL fragment for "view this file as rendered" (see §5)

Authors share this URL in their README, docs, or installation instructions. Consumers paste it into the Add Source dialog.

The ref encoded in the URL is the author's update-policy decision:

- A branch name (e.g. `main`) tracks rolling updates.
- A tag name (e.g. `v0.2.0`) pins to a specific release.
- A commit SHA freezes the reference exactly.

The Library Manager respects whichever ref the URL carries — it does not second-guess the author's intent.

### 4.2 Accepted input forms

The Library Manager accepts **four** input forms in its Add Source dialog and resolves all of them to a fetchable raw URL (or, in the paste case, a locally-saved file):

1. **Blob URL** (canonical, recommended for git-hosted files):
   `https://github.com/alice/cool-libs/blob/main/marketstall.toml`
   The host provider rewrites this to a raw URL for fetching, then carries the ref through into persistence.
2. **Raw URL** (if the user copied it directly):
   `https://raw.githubusercontent.com/alice/cool-libs/main/marketstall.toml`
   Used as-is for fetching.
3. **Plain TOML URL** (any URL that doesn't match a host provider's blob/raw pattern):
   `https://going-haywire.github.io/haywire/marketplace.toml`
   Treated as an opaque URL: fetch directly with no host-provider transformation. This is the path for static hosts (GitHub Pages, GitLab Pages, plain web servers, S3, anything that just serves a TOML file at a URL).
4. **TOML block** pasted directly (not actually a URL): the dialog saves it to `~/.haywire/db/haybale-marketplace/stalls/<dist-name>.toml` and references it via `file://` as a `[[stalls]]` subscription.

The Add Source dialog has **one input field** accepting any of the four. The runtime determines what to do by inspecting the input shape. Host providers add *convenience* for git-host URLs (rewriting blob to raw) but aren't required — plain TOML URLs work without any host-provider involvement.

**Bare repo URLs are explicitly rejected.** Pasting `https://github.com/alice/cool-libs` (no path to a file) produces an immediate error: *"Paste the URL to the marketstall.toml file, not the repo. Look for a `marketstall:share-url` block in the repo's README."* Rationale: the only way to resolve a bare repo URL is to probe the network for `marketstall.toml` at the default branch (and fall back to `marketplace.toml`), which adds up to 4 sequential HTTPS requests of latency to Add Source for a convenience case that the README marker pattern (§6.6) already serves cleanly. The canonical author flow is: author runs `haywire share --save`, marker block in README updates to the full blob URL, consumer copies that URL into Add Source.

### 4.3 Resolution

1. **Parse the input.** If it looks like a URL, strip trailing slashes, `.git`, query strings, fragments. Otherwise treat as a pasted TOML block (input form 4).
2. **Classify the URL form.** Try host providers in turn; first match wins.
   - Starts with `file://` → already a fetchable URL; skip host-provider handling.
   - Some `HostProvider.parse_blob_url(url)` returns non-None → blob URL (input form 1). Use `provider.raw_url(...)` to derive the fetchable URL; the blob URL itself is what gets persisted in the marketplace file.
   - Some `HostProvider.parse_raw_url(url)` returns non-None → raw URL (input form 2). Use as-is for fetch; reconstruct the canonical blob URL via `provider.blob_url(...)` for persistence.
   - URL has no path component beyond `/owner/repo` (i.e. looks like a bare repo URL) → reject with the "paste the file URL, not the repo URL" error from §4.2. No network probing.
   - No provider matches and the URL has a path that includes a file → plain TOML URL (input form 3). Fetch the URL as-is; no host-provider rewriting; persist exactly what the user pasted.
3. **Fetch.** HTTP errors surface as install failures with the fetched URL surfaced for debugging.
4. **Parse and validate.** Reject with a clear error on malformed TOML or missing required fields.
5. **Inspect body shape to decide subscription type.**
   - Body contains `[[markets]]` or `[[stalls]]` (with or without inline `[[haybales]]`) → it's a marketplace. Add to consumer's `[[markets]]`.
   - Body contains `[[haybales]]` only → it's a marketstall. Add to consumer's `[[stalls]]`.
   - Body contains neither → reject as malformed.
6. **Run the conflict-resolution prompt** if any haybale name collides with already-subscribed sources (see §8.3).
7. **Auto-refresh** to populate the project cache.

For input form 4 (pasted TOML block): the dialog parses the block, requires a `[[haybales]]` section, derives `<dist-name>` from the first haybale's `name` field, writes the block to `~/.haywire/db/haybale-marketplace/stalls/<dist-name>.toml`, then enters the resolution flow as if the user had pasted `file:///Users/.../db/haybale-marketplace/stalls/<dist-name>.toml`.

## 5. Host-provider architecture

Host-specific URL idiosyncrasies are isolated behind a Protocol. Adding a new host is one file plus one entry in a registry.

### 5.1 The Protocol

```python
class HostProvider(Protocol):
    """One git host's URL conventions."""

    name: str  # "github", "gitlab", etc. — for error messages and config

    def matches(self, hostname: str) -> bool:
        """True if this provider handles URLs with this hostname."""

    def parse_blob_url(self, url: str) -> ParsedRef | None:
        """Parse a blob URL into (owner, repo, ref, path). None if not a match."""

    def parse_raw_url(self, url: str) -> ParsedRef | None:
        """Parse a raw URL into (owner, repo, ref, path). None if not a match."""

    def raw_url(self, owner: str, repo: str, ref: str, path: str) -> str:
        """Construct the raw URL for fetching."""

    def blob_url(self, owner: str, repo: str, ref: str, path: str) -> str:
        """Construct the share URL (canonical, browser-friendly)."""
```

`ParsedRef` is a small frozen dataclass. There is no `parse_repo_url` and no `default_branch` — bare repo URLs are rejected at input time (§4.2, §4.3), so no provider ever needs to probe for a default branch.

### 5.2 Host Table

Built-in providers shipped in the first cut:

| Host       | Blob path        | Raw path                                          |
| ---------- | ---------------- | ------------------------------------------------- |
| github.com | `/blob/{ref}/`   | `raw.githubusercontent.com/{owner}/{repo}/{ref}/` |
| gitlab.com | `/-/blob/{ref}/` | `/-/raw/{ref}/`                                   |

GitHub and GitLab cover the dominant case and exercise the Protocol with two genuinely different URL shapes (proving the abstraction generalizes). Both are verifiable against real public repos.

Self-hosted instances of these platforms use the same URL conventions; only the hostname differs (see §5.4).

**Deferred providers**: Bitbucket and Gitea/Forgejo are not in the first cut. Users on those platforms can subscribe via raw URLs (form 2) or plain TOML URLs (form 3) — they just don't get blob → raw rewriting for free. Adding a provider is one file plus one registry entry (§5.5); the Gitea branch-vs-tag complication (its blob/raw URL paths differ depending on whether `{ref}` is a branch or tag) is an unresolved spec question that lands with the Gitea provider, not before.

### 5.3 Provider registry

```python
HOST_PROVIDERS: list[HostProvider] = [
    GitHubProvider(),
    GitLabProvider(),
    # BitbucketProvider() — deferred; see §5.2
    # GiteaProvider()     — deferred; see §5.2
]

def resolve_host(hostname: str) -> HostProvider | None:
    for provider in HOST_PROVIDERS:
        if provider.matches(hostname):
            return provider
    return None
```

### 5.4 Self-hosted instances

Users with self-hosted GitHub Enterprise or GitLab declare them in `~/.haywire/config.toml`:

```toml
[[hosts]]
hostname = "git.acme.example"
provider = "gitlab"

[[hosts]]
hostname = "code.team.example"
provider = "github"
```

`resolve_host()` consults the user's config first, then falls back to built-in matchers. Each config entry maps a hostname to one of the shipped provider names (`github`, `gitlab`). Once Bitbucket and Gitea providers ship (§5.2), their names become valid here too.

### 5.5 File layout

```text
packages/haywire-core/src/haywire/core/marketstall/
├── __init__.py
├── host_providers/
│   ├── __init__.py        # exports HOST_PROVIDERS, resolve_host(), HostProvider
│   ├── base.py            # Protocol + ParsedRef
│   ├── github.py          # GitHubProvider
│   └── gitlab.py          # GitLabProvider
#   ├── bitbucket.py       # deferred (§5.2)
#   └── gitea.py           # deferred (§5.2)
```

Each provider module is self-contained, individually unit-tested.

## 6. Author tooling: `haywire share`

### 6.1 Behavior

```sh
uv run haywire share --save [--tag <tag>] [--ref <ref>]
```

1. **Walk `barn/*`.** For each directory containing a `pyproject.toml`, build a `Haybale` entry via the existing `_build_entry_for_library` helper.
2. **Write `marketstall.toml`** to the repository root, containing one `[[haybales]]` entry per library found. If the file exists, overwrite (mutation is the point of `--save`).
3. **Run the drift gate** (see §12). Default warns to stderr; `--strict` refuses to write on drift; `--fix` auto-corrects each library's manifests before writing.
4. **Attempt to derive the share URL.** Read `git remote get-url origin`:
   - **No remote:** skip URL construction. Print a warning instead (see §6.3). The file has still been written; the author can push later and re-run `haywire share` to get the URL.
   - **Remote present:** normalize the URL (convert SSH `git@host:owner/repo.git` to HTTPS `https://host/owner/repo`; strip trailing `.git` and slashes). Detect the host against `HOST_PROVIDERS` (user-configured hosts in `~/.haywire/config.toml` checked first). Unknown host → skip URL construction with a warning.
   - **Determine the ref**, in this order of precedence:
     - `--ref <ref>` if given (use verbatim)
     - `--tag <tag>` if given (use the tag name)
     - `--tag latest` resolves to the most recent tag reachable from HEAD
     - Otherwise: the current branch (`git rev-parse --abbrev-ref HEAD`)
   - **Construct the share URL** via `provider.blob_url(owner, repo, ref, "marketstall.toml")` and print it.
5. **Update READMEs in place.** When the share URL was successfully derived, scan the repo for README files with the `marketstall:share-url` marker pair and rewrite the block between markers (see §6.6). Suppressed by `--no-update-readme`.

The file write (step 2) is independent of the URL construction (step 4), which is independent of the README update (step 5). A failure to derive the URL never aborts the write — the file is local and useful on its own. README updates only run when there's a URL to write.

### 6.2 Output

Happy path:

```text
✓ Wrote marketstall.toml
✓ Share this URL:
  https://github.com/alice/cool-libs/blob/main/marketstall.toml
```

No remote:

```text
✓ Wrote marketstall.toml
⚠ No git remote found. Push this repo to a supported host first, then re-run
  `haywire share` (without `--save`) to get the share URL.
```

Unknown host:

```text
✓ Wrote marketstall.toml
⚠ Host 'gitlab.zhdk.ch' is not recognized. To enable, add this to
  ~/.haywire/config.toml:

    [[hosts]]
    hostname = "gitlab.zhdk.ch"
    provider = "gitlab"   # or one of: github, bitbucket, gitea

  Then re-run `haywire share` (without `--save`) to get the share URL.
```

The warning includes a ready-to-paste snippet so the author doesn't have to look up the config format. The author still has to choose which `provider` matches their host (the runtime doesn't auto-detect, see §5.4).

### 6.3 Failure modes

The file write itself can still fail. URL construction failures are warnings, not errors.

- **Drift in `--strict` mode:** "Refusing to share due to dependency drift. Use --fix to auto-correct, or address the drift in the listed libraries first." (Exits non-zero, file is not written.)
- **Detached HEAD with no `--ref` or `--tag`:** Warning only — share URL is not constructed because the runtime can't infer a ref. The file still writes.
- **No git remote, unknown host:** Warnings only — see §6.2.

### 6.4 URL-only re-run

`haywire share` without `--save` (and without a library path argument) re-derives the share URL for an existing `marketstall.toml` and prints it. Useful after pushing a repo for the first time, or after updating `~/.haywire/config.toml` to recognize a self-hosted instance.

### 6.5 Other share modes

- `haywire share <library_path>` — print a single-haybale snippet to stdout. Useful for chat/gist sharing. Unchanged from existing behaviour.
- `haywire share --save --strict` — refuses to write on drift. Use in CI.
- `haywire share --save --fix` — auto-corrects drift before writing.
- `haywire share --save --no-update-readme` — opts out of README auto-update (see §6.6).

### 6.6 README auto-update

`haywire share --save` updates README files in place when it finds the marker pair:

```markdown
<!-- marketstall:share-url:start -->
<!-- marketstall:share-url:end -->
```

It writes between the markers a single inline-code line containing the resolved share URL:

```markdown
<!-- marketstall:share-url:start -->
`https://github.com/alice/cool-libs/blob/main/marketstall.toml`
<!-- marketstall:share-url:end -->
```

Inline code is used because GitHub, GitLab, and most Markdown renderers attach a copy-to-clipboard affordance to inline `code` spans automatically. The author gets the copy button for free without haywire generating any platform-specific markup.

**Files scanned**, in order:

- The repository root's `README.md` (or `Readme.md` / `readme.md`, case-insensitive match — first hit wins).
- Each `<repo>/barn/*/README.md` (every library's README).

**Behavior**:

- File present + markers present → block between markers is rewritten with the current URL.
- File present + markers absent → file left untouched. The auto-update is opt-in via the markers; no surprise modifications.
- File absent → skipped silently.
- Multiple marker pairs in one file → all are updated to the same URL.

**Suppression**: `--no-update-readme` skips this step entirely. Useful when the README is auto-generated by some other tool that doesn't want haywire writing into it.

**Coupling with no-remote / unknown-host**: if the share URL couldn't be derived (no remote, unknown host), the README update is skipped — the runtime never writes a stale URL or a placeholder. The author sees the warning about the URL not being constructed (see §6.2); on the next successful share, the README updates.

**`haywire init` cooperation**: `haywire init` writes new READMEs (both root and the scaffolded library's `barn/haybale-<name>/README.md`) that already contain the marker pair. The block between starts as a placeholder:

```markdown
<!-- marketstall:share-url:start -->
*Subscribe URL not yet published — run `haywire share --save` after pushing this repo to a git remote.*
<!-- marketstall:share-url:end -->
```

So the author's first `haywire share --save` (after pushing) replaces the placeholder with the real URL. No manual marker setup required for projects scaffolded by `haywire init`.

## 7. Consumer behavior: the Library Manager

### 7.1 Add Source dialog

One input field labeled "URL or pasted TOML." The dialog accepts any of the four input forms named in §4.2 and resolves them via the algorithm in §4.3.

After successful resolution and subscription, the dialog closes and auto-refresh runs.

### 7.2 Subscription persistence

The runtime persists the **resolved blob URL** (canonical form) in the marketplace file, not whatever the user originally pasted. This way the file is always in a recognizable form for the Edit File path.

If the user pasted a bare repo URL, the resolved blob URL has the host's default branch baked in — subsequent refreshes use this exact URL.

### 7.3 Caching

`~/.haywire/cache/<url-hash>.toml` keyed by the resolved raw URL. On every successful fetch, the cache is overwritten. On fetch failure, cache provides the fallback body. **No TTL.** Cache files are valid until overwritten by a successful fetch; haywire's catalog is not time-sensitive, and a TTL would punish offline use (working on a plane, traveling) without protecting against any failure mode that matters for this data shape.

A content hash of the cached body is recorded as a side metadata file `<url-hash>.sha256` to enable "did this URL change since last refresh?" detection — informs the update-available signal in §10.

**Tri-state per-subscription refresh result.** Each subscription's refresh step produces one of three outcomes:

| Outcome | When | UI signal |
| --- | --- | --- |
| `fresh` | HTTP 200; cache overwritten | (none — happy path) |
| `cache_fallback` | HTTP failed; cache hit; body served from cache | counted in `RefreshReport.sources_from_cache`; refresh toast says "N sources served from cache" when nonzero |
| `unavailable` | HTTP failed; no cache; subscription contributes nothing this refresh | counted in `RefreshReport.sources_unavailable`; yellow banner in Library Browser |

Distinguishing `fresh` from `cache_fallback` matters: an HTTP 5xx → cache-fallback path should not look identical to a happy-path refresh in the report. The user should be able to see when their catalog is partially stale.

**Cache GC.** At the end of each refresh, the runtime deletes any `<url-hash>.toml` (and its `.sha256` sidecar) whose hash doesn't match the URL of an active subscription. This keeps `~/.haywire/cache/` bounded across subscription churn (users unsubscribing and re-subscribing accumulates orphans otherwise).

### 7.4 Install safety modal

Every Install click on a haybale opens a safety modal that interposes between the click and the actual `uv pip install`. The user is installing third-party code; the modal makes that explicit and gives them a chance to verify before committing.

**Modal contents**:

- **Title**: "Install `<haybale-name>`?"
- **Safety copy**: *"You are about to install third-party code. You are responsible for verifying this library is safe before installing. Review the source first if you don't recognize the author."*
- **Source link button** — opens the haybale's `source_url` field in a new browser tab/window. Disabled (with explanatory text) if `source_url` is empty.
- **Three action buttons**:
  - **Cancel** — close, no change.
  - **Block** — add the haybale's `name` to the `blocked = []` array on the subscription that resolved this haybale (the `[[markets]]` or `[[stalls]]` entry whose `via` URL matches). The haybale disappears from the Library Browser's AVAILABLE list immediately. Persistent; only un-blockable by editing the marketplace file by hand.
  - **Install** — proceed with `uv pip install <install_spec>` and trigger a Library System rescan.

**Scope**: the modal fires on every Install click. There is no "first time" suppression — third-party install is a serious enough operation that the safety prompt is shown every time. The user can dismiss it with one click (Cancel) if they're sure.

**Provenance display in the Library Browser**: each haybale row shows where it came from, using the `via` cache field already recorded during refresh.

- **Direct `[[stalls]]` subscription**: row shows the marketstall's host (e.g. "from github.com/alice").
- **Transitive via `[[markets]]`**: row shows the aggregator's host with a "via" qualifier (e.g. "via going-haywire.github.io"). A tooltip names both the aggregator and the underlying stall, so the user can audit which haybales arrived through which curator.

This makes aggregator catalog expansion *visible*: if Bob's curated marketplace silently adds 30 new sources, the user can see each new haybale carries a "via bob.example" provenance label and decide whether to keep, block, or unsubscribe from Bob's list.

## 8. Refresh pipeline

```text
[Global marketplace]                          [Project marketplace]
       │                                              ▲
       ├── parse                                      │
       │                                              │
       ├── for each [[markets]] subscription:         │
       │     fetch → parse → collect [[stalls]] refs  │
       │     (one level deep; the marketplace's       │
       │      own [[markets]] are ignored)            │
       │                                              │
       ├── for each [[stalls]] subscription           │
       │     (direct + discovered via markets):       │
       │     fetch → parse → collect [[haybales]]     │
       │                                              │
       ├── candidate list =                           │
       │     resolved haybales ∪                      │
       │     project [[heaps]]                        │
       │                                              │
       ├── conflict resolution:                       │
       │     apply ignores → drop matching names      │
       │     apply heaps shadow → heaps always win    │
       │     apply first-come-first-served → dedup    │
       │                                              │
       ├── stale marking:                             │
       │     diff against previous [[caches]]         │
       │     entries dropped from sources but         │
       │     present in the prior cache → stale=True  │
       │                                              │
       ├── update-available detection: (§10)          │
       │     for each installed haybale,              │
       │     compare installed version vs cache       │
       │     min_version; flag if installed lower     │
       │                                              │
       └── serialize and write ──────────────────────►│
                                                      │
                                                      ▼
                                            project [[caches]] cache
```

### 8.1 One-level-deep resolution

When a remote marketplace body's `[[markets]]` references other marketplaces, those are ignored. Only `[[stalls]]` references and (defensively, in case of malformed marketplaces) `[[haybales]]` are consumed. This bounds the resolution chain and keeps the trust model legible.

### 8.2 Conflict resolution

| Filter                  | What it does                                                                                                                                                                                                                            |
| ----------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `blocked`               | Each subscription's `blocked` array lists names the user actively rejected via the install safety modal (§7.4). Blocked haybales are dropped from the candidate list AND hidden from the Library Browser's AVAILABLE list.        |
| `ignores`               | Each subscription's `ignores` array lists names to skip from that source. Populated by the user's conflict-resolution prompt at Add Source time. Unlike `blocked`, ignored haybales may still be visible if another source offers them. |
| Heaps shadow            | Any candidate haybale whose name matches a `[[heaps]]` entry is dropped — local heaps always win.                                                                                                                                       |
| First-come-first-served | After the above, deterministically keep the first occurrence of any remaining duplicate. Safety net for hand-edits.                                                                                                                     |

Filter application order: `blocked` and `ignores` apply per-subscription (during the fetch → parse → collect step). Heaps shadow and FCFS apply across the combined candidate list. This means a haybale blocked from source A but offered freely by source B still appears (from source B); blocking is per-subscription by design (see §3.1's filter-array semantics).

### 8.3 The user-prompt path

When Add Source resolves a new subscription and detects name collisions against the existing resolved state, the user is shown one row per conflict and asked which source to keep. The losing source's `ignores` array gains the colliding name. Future refreshes honor the choice without re-asking.

## 9. The refresh report

`RefreshReport` (returned by `MarketplaceState.refresh()`):

| Field                 | Meaning                                                                                                                                                |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `sources_fetched`     | Subscriptions whose result was `fresh` (HTTP 200, cache overwritten). Distinct from `sources_from_cache`.                                              |
| `sources_from_cache`  | Subscriptions whose result was `cache_fallback` (HTTP failed, cache hit, body served from cache). Drives the toast "N sources served from cache" line. |
| `sources_unavailable` | Subscriptions whose result was `unavailable` (HTTP failed, no cache).                                                                                  |
| `unavailable_urls`    | Specific URLs in the `sources_unavailable` count. Drives the yellow banner.                                                                            |
| `haybales_resolved`   | Non-stale entries in the final cache.                                                                                                                  |
| `new_stale`           | Entries that became stale on this refresh (were fresh before).                                                                                         |
| `updates_available`   | Installed haybales whose cache `min_version` exceeds installed version. See §10.                                                                       |

The three `sources_*` counters always partition the active subscription set (`sources_fetched + sources_from_cache + sources_unavailable == total subscriptions`). The split between `sources_fetched` and `sources_from_cache` is the difference between "everything went well" and "some sources were degraded but we recovered from cache" — both produce a populated catalog, but only the latter warrants the toast line.

## 10. `min_version` and the update-available signal

### 10.1 Where `min_version` comes from

`haywire share` reads `min_version` from the library's **`pyproject.toml`** `[project] version` field. That's the single source of truth.

```toml
# In <repo>/barn/haybale-foo/pyproject.toml
[project]
name = "haybale-foo"
version = "0.2.0"
```

→ `haywire share` produces:

```toml
[[haybales]]
name        = "haybale-foo"
min_version = "0.2.0"
# ...
```

No git tags are consulted. The `@library(version=_pkg_version('haybale-foo'))` decorator (written by `haywire init`) reads the installed distribution's metadata at runtime — which itself derives from `pyproject.toml` at build time — so it's the same number, just reached through a different path. Authors who use `scripts/bump_version.py` or `/haywire-release` have those tools edit `pyproject.toml` directly. The `[project] version` field is the only place an author maintains the canonical version.

### 10.2 Operational meaning

Because `haywire share` regenerates the marketstall whenever it runs, and because `min_version` is read from `pyproject.toml` at that moment, **the stall always reflects the version the author is currently publishing**. There's no out-of-band release cadence; the stall and the version are bound by the share command.

This collapses the distinction between `min_version` (the pip-level floor) and "the latest version this author has published." For any haybale flowing through the standard pipeline, they're equal at the moment refresh sees the stall.

The field keeps its name (`min_version` is still a pip-level floor — pip may install higher), but the documented expectation is: "the version the author is currently publishing."

### 10.3 The update-available signal

After each refresh, for every installed haybale, the runtime compares the installed version (via `importlib.metadata.version`) against the `min_version` of the most-recently-resolved cache entry for that haybale. If `installed < cache.min_version`, the library has an update available.

UI surface:

- **Library Browser**: a quiet "▲" indicator + "v0.2.0 available" suffix in the row's sublabel, parallel to the stale signal.
- **Library Overview Editor**: an **Update** button alongside Disable / Uninstall. Clicking it runs `uv pip install --upgrade <name>` and triggers a Library System rescan.
- **Refresh report toast**: includes `"K updates available"` when `RefreshReport.updates_available > 0`.

Update never fires automatically. The signal is purely informational; the user decides when to upgrade.

## 11. The official feed — aggregator layout

The Haywire team's official feed uses the per-haybale-stall layout: one marketstall file per published library, all referenced from one marketplace file.

### 11.1 Deploy layout

```text
gh-pages-content/
├── marketplace.toml                    # the official aggregator
└── stalls/
    ├── haybale-core.toml               # one marketstall per library
    ├── haybale-studio.toml
    ├── haybale-haystack.toml
    ├── haybale-graph-editor.toml
    └── ...                             # one per barn/* library
```

### 11.2 Marketplace contents

```toml
[[stalls]]
url = "https://going-haywire.github.io/haywire/stalls/haybale-core.toml"
ignores = []
doubles = []
blocked = []

[[stalls]]
url = "https://going-haywire.github.io/haywire/stalls/haybale-studio.toml"
ignores = []
doubles = []
blocked = []
# ...one [[stalls]] entry per library
```

### 11.3 Per-haybale stall contents

Each `stalls/<dist-name>.toml` is a marketstall with exactly one `[[haybales]]` entry.

### 11.4 Generator

`scripts/generate_marketstall.py`:

1. Walk source `barn/*` for libraries with `pyproject.toml`.
2. For each, write an output `stalls/<dist-name>.toml` with a single `[[haybales]]` entry built via `_build_entry_for_library`.
3. Write the top-level output `marketplace.toml` with one `[[stalls]]` entry per generated file.

(The script keeps its current filename for CI compatibility. A follow-up commit can rename it to `generate_official_feed.py`.)

### 11.5 Granular subscription as a side benefit

A consumer who only wants `haybale-haystack` can subscribe to `https://going-haywire.github.io/haywire/stalls/haybale-haystack.toml` directly via `[[stalls]]`, without taking the whole feed. The old monolithic layout forced all-or-nothing.

### 11.6 Author-side aggregator pattern

An author who wants to play aggregator (publish their own libraries AND recommend others) does the same thing the Haywire team does: per-haybale stalls + one marketplace.toml at the repo root that references them. This is not the default for `haywire share --save` (which produces a single `marketstall.toml` for the simple case); aggregator-style publishing is a separate `haywire aggregate` command, out of scope for this spec.

## 12. Dep-drift gate extension

The existing drift gate (`detect_share_drift` in `haywire_studio.share`) gains a third check: **declared `min_version` floors on haybale dependencies lagging behind installed versions**.

Scenario: library declares `haybale-core~=0.0.1`; the author has since updated to `haybale-core 0.3.0` and is building against the new API. Their published library still tells consumers they need only 0.0.1 — technically a valid floor (pip will install higher), but understates the real requirement.

### 12.1 Scope: haybale-* deps only

The lag check applies **only to declared dependencies that `HaywireLibrarySource` confirms are registered haywire libraries** (i.e., the underlying distribution is known to the haywire ecosystem). Third-party deps (numpy, requests, opencv, etc.) are **not** subject to the lag check.

Rationale: the check's core assumption is "installed version = the version this library actually needs." For inter-haybale deps the assumption holds well — the haybale ecosystem is small and lockstep-released; an author building against `haybale-core 0.3.0` almost certainly needs 0.3.0 features. For third-party deps the assumption breaks — an author may have `numpy 2.0` installed system-wide while their library only exercises pure-Python numpy APIs that work on `numpy 1.x`. Flagging a uniform lag would push `--fix` to gratuitously narrow library compatibility based on the author's dev-machine state. Third-party floors remain the author's manual call.

The check uses the same `HaywireLibrarySource` infrastructure already powering `detect_deps` — in CLI flows (`haywire share`), `EntryPointLibrarySource` reads `importlib.metadata.entry_points(group="haywire.libraries")`; in studio flows, the live registry. A dep is haybale-flagged by registration, not by name pattern (`haybale-*` is a convention, not a contract).

### 12.2 The check

For each declared dependency in `[project] dependencies` whose distribution name is in `HaywireLibrarySource.list_names()`, parse the version specifier. Compare its floor against the installed version (via `importlib.metadata.version`). If `installed > declared_floor` and the operator is `~=` or `>=`, flag as drift.

Operators other than `~=` and `>=` are not flagged:

- `==`, `===` — pins; deliberate, not lag.
- `<`, `<=`, `!=` — upper bounds or exclusions; semantically different from "minimum needed."
- `>` — equivalent to `>=` for lag-detection purposes; treated identically.
- No operator — pip treats as `==`; treated as a pin.

### 12.3 Wiring

`DepDrift` gains a field:

```python
@dataclass(frozen=True)
class DepDrift:
    lib_dir: Path
    pyproject_missing: list[str]
    decorator_missing: list[str]
    pyproject_version_lag: list[tuple[str, str, str]]   # (dist, declared_floor, installed) — haybale deps only
    unresolved: list[str]
```

`apply_drift_fix` rewrites lagging floors to match the installed version when the user opts to fix. Only haybale-flagged deps appear in `pyproject_version_lag`, so `--fix` cannot accidentally narrow third-party compatibility.

`haywire share --strict` refuses to ship a library with lagging haybale floors. Default mode (warn) prints the lag alongside other drift findings.

The Detect Dependencies button's Union mode bumps lagging haybale floors. Replace mode regenerates from detected imports + current installed versions (and is already scoped to detected deps, which includes the appropriate haybale-vs-third-party split via `DetectedDeps`).

## 13. Migration

Not applicable. This is a breaking pre-release change.

Haywire has no external users yet; the only existing files in the old schema live in the dev workspace itself, and those can be reset by hand. The runtime ships with parsers that accept only the new vocabulary. No alias period; no `_migrate_marketplace_schema_if_needed` extension.

The existing `_migrate_marketplace_schema_if_needed` function in `config.py` can be deleted outright — it was added to handle the earlier `sources` → `[[marketplaces]]` transition, and that transition is being superseded by the new vocabulary in one shot.

Dev-workspace cleanup: delete the legacy `~/.haywire/marketplace.toml` (and any stale `~/.haywire/stalls/` directory) along with any project-side `.haywire/marketplace.toml` files before running the new code. The next `haywire init` (or first `haywire share` / Add Source action) regenerates the files in the new shape under `~/.haywire/db/haybale-marketplace/`.

## 14. Runtime renames

| Old                                                | New                                     |
| -------------------------------------------------- | --------------------------------------- |
| `MarketplaceEntry` (dataclass)                     | `Haybale`                               |
| `haywire.core.marketplace.MarketplaceEntry` import | `haywire.core.marketstall.Haybale`      |
| `haywire.core.marketplace_runtime`                 | `haywire.core.marketstall.runtime`      |
| `GlobalMarketplace.marketplaces`                   | `.markets`                              |
| `GlobalMarketplace.marketstalls`                   | `.stalls`                               |
| `GlobalMarketplace.packages` (direct paste)        | removed                                 |
| `GlobalMarketplace.locals_`                        | removed from global                     |
| `ProjectMarketplace.locals_`                       | `.heaps`                                |
| `ProjectMarketplace.packages`                      | `.caches`                               |
| `parse_global_marketplace`                         | unchanged name, reads new section names |
| `parse_project_marketplace`                        | unchanged name, reads new section names |
| `parse_remote_marketplace_body`                    | reads `[[stalls]]`                      |
| `parse_marketstall_body`                           | reads `[[haybales]]`                    |
| `add_marketplace_subscription_to_global`           | `add_market_subscription_to_global`     |
| `add_marketstall_subscription_to_global`           | `add_stall_subscription_to_global`      |
| `add_direct_package_to_global`                     | removed                                 |
| `add_local_to_global`                              | removed                                 |
| `add_local_to_project`                             | `add_heap_to_project`                   |
| `remove_stale_package_from_project`                | `remove_stale_haybale_from_project`     |
| `MarketplaceState.get_project_packages()`          | `.get_project_haybales()`               |
| `MarketplaceState.remove_stale_package()`          | `.remove_stale_haybale()`               |
| `RefreshReport.packages_resolved`                  | `.haybales_resolved`                    |
| `RefreshReport.updates_available`                  | new field                               |
| `apply_locals_shadow`                              | `apply_heaps_shadow`                    |
| `DuplicateLocalNameError`                          | `DuplicateHeapNameError`                |
| `_parse_local_entry`                               | `_parse_heap_entry`                     |

`Haybale` field names (`name`, `min_version`, etc.) and cache-only fields (`via`, `last_seen`, `stale`) are unchanged.

## 15. Documentation updates

All documentation that mentions the old vocabulary updates in lockstep:

- `docs/architecture/sharing/sharing-arch.md` — every mention of marketplace/marketstall as syntactic concepts updates. The philosophical model survives.
- `docs/architecture/library-manager/library-manager-arch.md` — schema tables in §2 rewrite; UI flow updates for the unified Add Source dialog.
- `docs/guides/sharing-libraries.md` — `haywire share` produces `[[haybales]]` not `[[packages]]`; the URL-distribution model section is new.
- `docs/guides/subscribing-to-marketplaces.md` — Add Source becomes one field; file-shape examples update.
- `docs/components/haybale-package/haybale-package-canon.md` — section name updates only.
- `docs/reference/glossary.md` — old vocabulary entries rewrite; new entries for `[[markets]]`, `[[stalls]]`, `[[haybales]]`, `[[heaps]]`, `[[caches]]`, blob/raw/repo URL forms, host provider.

## 16. Implementation order

Foundation lands atomically (the renames and the new dataclass/parser shapes are interlocked — half a rename is worse than none). Everything *after* foundation lands as a vertical feature slice with its own commit and revert boundary.

Tests are written **alongside each commit**, not deferred. Glossary entries update **in lockstep with renames** — the glossary lives in the same repo and can't be wrong for the duration of an implementation pass.

1. **Foundation** (one large but coherent commit). The interlocked layer:
   - Rename `MarketplaceEntry` → `Haybale`; add `os` field; the new dataclass is the data-layer ground truth.
   - New `haywire.core.marketstall/` package; new `host_providers/` subpackage with `base.py` (Protocol + `ParsedRef`), `github.py`, `gitlab.py`, and `__init__.py` exposing `HOST_PROVIDERS` and `resolve_host()` (GitHub + GitLab only per §5.2; Bitbucket and Gitea deferred).
   - Rewrite parsers for the new section names (`[[haybales]]`, `[[markets]]`, `[[stalls]]`, `[[heaps]]`, `[[caches]]`); allow `[[haybales]]` inline in marketplace bodies; update `parse_remote_marketplace_body` / `parse_marketstall_body`.
   - `MarketplaceState` and the `add_*` helpers; URL-resolution helper combining host detection + body-shape detection + auto-subscribe; current-OS detection helper.
   - `blocked: list[str]` field on subscription dataclasses (data-layer only; not yet wired through UI).
   - Tri-state per-subscription refresh result and `sources_from_cache` field on `RefreshReport` (data-layer only).
   - Cache GC at end of refresh (orphaned `<url-hash>.toml` cleanup).
   - Self-hosted-instance config reading.
   - Delete the legacy `_migrate_marketplace_schema_if_needed` in `config.py`.
   - Update glossary entries for renamed terms; add new entries for `[[markets]]` / `[[stalls]]` / `[[haybales]]` / `[[heaps]]` / `[[caches]]` / blob & raw URL forms / host provider.
   - Tests for all of the above (host providers, URL resolution, all parsers, state helpers, tri-state refresh result, cache GC).

2. **Author tooling**. `init.py` writes `[[heaps]]` + READMEs with marker pairs; `share.py` emits `[[haybales]]` (including `os` from `[tool.haywire]`, with validation rejecting non-declarable values per §2.1); URL derivation via host provider; README marker rewrite (default; `--no-update-readme` opts out); `haybale-gen-docs` skill gains a marker-pair preservation rule so the two skills compose. Tests written alongside.

3. **URL distribution UI**. Add Source dialog collapses to one field accepting the four forms from §4.2 (rejects bare repo URLs with the §4.2 error message); body-shape detection drives `[[markets]]` vs `[[stalls]]` subscription type; auto-refresh after subscribe; provenance affordance in the Library Browser (direct vs "via aggregator" row labels, using the `via` cache field). Tests for all four input forms.

4. **`os` field UI**. OS multi-select in the Library Overview Editor's Edit dialog, **gated to `[[heaps]]` libraries only** (installed wheels show read-only). Install button OS-mismatch gating with the §2.1 tooltip in the Library Browser. Tests for heap-vs-installed dialog behavior, OS-mismatch gating roundtrip.

5. **Install safety + blocked-list**. Install safety modal per §7.4 (Cancel / Block / Install + source-link button), shown on every Install click; `blocked` filter applied during the refresh conflict-resolution step (§8.2); hidden-when-blocked Library Browser behavior. Tests for modal triggering, block-and-hide roundtrip, per-source blocking semantics.

6. **Drift gate extension**. `min_version` lag detection scoped to haybale-* deps per §12.1; `DepDrift.pyproject_version_lag` field; `apply_drift_fix` floor rewrite for haybales only; `--strict` / `--fix` integration. Tests for the haybale-vs-third-party scoping (key correctness property).

7. **Update-available signal**. Installed-vs-cache `min_version` comparison per §10.3; UI surface (▲ indicator, Update button on the Library Overview Editor, refresh-toast count from `RefreshReport.updates_available`). Tests for the comparison logic and the toast surfacing.

8. **Per-haybale stall generator**. `scripts/generate_marketstall.py` produces the two-tier layout per §11; official feed restructure. Tests for the generator output shape; manual check of the resulting feed against the real consumer flow.

9. **Docs sweep**. The six files listed in §15 + glossary final pass. Update any documentation that the lockstep commits couldn't keep current (architecture docs that describe the runtime in detail, etc.). No ADRs — this spec is the durable record.

10. **Verification**. Full `ruff` / `mypy` / `pytest` sweep, plus a manual smoke through Add Source / Refresh / Edit / Detect-Dependencies / Share / Update / Install-block / Update-available against a fresh `haywire init` project.

## 17. Non-goals

- **No version-based conflict resolution.** Two sources publishing the same haybale name still resolve by user choice or first-come-first-served, not by version comparison.
- **No central registry, mirrors, or CDN.** Authors host their own repositories.
- **No signed packages or cryptographic verification.** Authors host their content; consumers read the source URL before installing if they care to verify. The install safety modal (§7.4) is the cryptographic-trust-substitute: the user reviews the source before installing third-party code.
- **No transitive dependency resolution.** A haybale's `dependencies` list is informational; consumers install dependencies individually. pip handles actual resolution.
- **No lockfiles or reproducible installs at the Haywire level.** Reproducibility is the project's responsibility through standard Python tooling.
- **No forced updates.** The update-available signal is informational; the user always decides when to upgrade.
- **No automatic discovery of repositories.** A `marketstall.toml` at the root is the only signal that a repo is a publisher.
- **No publisher index.** There is no list of "all marketstalls in the world."
- **No aggregator-style publishing via `haywire share` at first ship.** A `haywire aggregate` command is a follow-up.
- **No auto-detection of self-hosted git hosts.** Probing endpoints like `/api/v4/version` or `/api/v1/version` would be fragile and platform-specific. Self-hosted instances are declared explicitly in `~/.haywire/config.toml`; the `haywire share` warning surfaces a ready-to-paste snippet when an unknown host is encountered.
- **No bare-repo-URL Add Source form.** Pasting a repo URL like `https://github.com/alice/cool-libs` is rejected (§4.2); the canonical author surface is the README marker pair (§6.6), which renders a copy-button-friendly inline-code blob URL. Resolving bare repo URLs would require up to 4 sequential HTTPS requests per Add Source for a convenience case the marker pattern already serves.
- **No Bitbucket / Gitea / Forgejo host providers in the first cut.** GitHub and GitLab ship as built-in providers (§5.2); users on other platforms paste raw URLs (form 2) or plain TOML URLs (form 3). Adding a provider is one file plus one registry entry (§5.5).
- **No third-party-dep lag detection.** The §12 drift-gate lag check applies only to haybale-* deps; third-party floors (numpy, requests, etc.) are the author's manual call. Acting on third-party lag based on the author's dev-machine state would silently narrow library compatibility.
- **No TTL on the HTTP cache.** Cache files are valid until overwritten by a successful fetch. Catalog freshness on the order of days or weeks is acceptable; a TTL would punish offline use (§7.3).
- **No README templating beyond the marker pair.** The README auto-update writes only between the markers — nothing else in the file is touched. Authors who want richer instructions write their own prose around the markers.
- **No carve-out of `haybale-marketplace` as a separate library in this spec.** The directory path `~/.haywire/db/haybale-marketplace/` is chosen now to avoid a future migration (§3.1), but the runtime and UI code remains in `haywire.core.marketstall.*` and `haybale-studio` until the carve-out happens as its own piece of work.

## 18. Open questions

None at this revision. The Gitea branch-vs-tag URL question (§5.2) is the only known unresolved point and is deferred along with the Gitea provider itself.
