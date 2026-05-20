---
status: draft
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
| `[[markets]]`  | Inside `marketplace.toml` (global)                                                             | A subscription to a remote *marketplace*. Carries `url`, `ignores`, `doubles`.                                                                                                                                                               |
| `[[stalls]]`   | Inside `marketplace.toml` (global)                                                             | A subscription to a remote *marketstall*. Carries `url`, `ignores`, `doubles`.                                                                                                                                                               |
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
| `os`           | no       | List of platforms the library supports. Values: `"macos"`, `"windows"`, `"linux"`, `"other"`. Absent (or omitted) means "all platforms". See §2.1.                |
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

**Accepted values**: `"macos"`, `"windows"`, `"linux"`, `"other"`. The `"other"` bucket catches everything else (BSDs, illumos, Haiku, etc.).

**Edit dialog surface**: the Library Overview Editor's Edit dialog has an OS multi-select. Saving writes the chosen values back into the library's `pyproject.toml` `[tool.haywire].os`. Selecting nothing (or all four) removes the key (= "all platforms").

**Library Browser behavior**: an installable haybale whose `os` list doesn't include the current platform is shown in the AVAILABLE section *normally*, but its Install button is disabled. A tooltip on the disabled button explains: *"Not available on this OS; this library targets: macos, linux."* This is the most discoverable treatment — the user sees the library exists, learns why it's not installable on this machine, and can revisit on a different platform.

The runtime maps `platform.system()` to one of the four values once at session start:

| `platform.system()` | Mapped to  |
| ------------------- | ---------- |
| `"Darwin"`          | `"macos"`  |
| `"Windows"`         | `"windows"` |
| `"Linux"`           | `"linux"`  |
| anything else       | `"other"`  |

## 3. The marketplace format

A `marketplace.toml` plays two distinct roles depending on where it lives:

### 3.1 Consumer's marketplace (`~/.haywire/marketplace.toml`)

```toml
[[markets]]
url = "https://github.com/going-haywire/haywire/blob/main/marketplace.toml"
ignores = []
doubles = []

[[stalls]]
url = "https://github.com/alice/cool-libs/blob/main/marketstall.toml"
ignores = ["haybale-mesh"]
doubles = []

[[stalls]]
url = "file:///Users/me/.haywire/stalls/internal-experiment.toml"
ignores = []
doubles = []
```

This file records: who the user is following (`[[markets]]` and `[[stalls]]`), and the per-source overrides (`ignores`, `doubles`). It contains no haybale definitions of its own — direct-paste entries are persisted as one-`[[haybales]]`-entry marketstalls under `~/.haywire/stalls/` and referenced via `[[stalls]]` with `file://` URLs.

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

The Library Manager accepts five input forms in its Add Source dialog and resolves all of them to a fetchable raw URL (or, in the paste case, a locally-saved file):

1. **Blob URL** (canonical, recommended for git-hosted files):
   `https://github.com/alice/cool-libs/blob/main/marketstall.toml`
   The host provider rewrites this to a raw URL for fetching, then carries the ref through into persistence.
2. **Raw URL** (if the user copied it directly):
   `https://raw.githubusercontent.com/alice/cool-libs/main/marketstall.toml`
   Used as-is for fetching.
3. **Repo URL** (convenience, no ref encoded — uses the host's default branch):
   `https://github.com/alice/cool-libs`
   The host provider determines the default branch (try `main`, then `master`) and looks for `marketstall.toml` at the repo root; on 404, tries `marketplace.toml`.
4. **Plain TOML URL** (any URL that doesn't match a host provider's blob/raw/repo pattern):
   `https://going-haywire.github.io/haywire/marketplace.toml`
   Treated as an opaque URL: fetch directly with no host-provider transformation. This is the path for static hosts (GitHub Pages, GitLab Pages, plain web servers, S3, anything that just serves a TOML file at a URL).
5. **TOML block** pasted directly (not actually a URL): the dialog saves it to `~/.haywire/stalls/<dist-name>.toml` and references it via `file://` as a `[[stalls]]` subscription.

The Add Source dialog has **one input field** accepting any of the five. The runtime determines what to do by inspecting the input shape. Host providers add *convenience* for git-host URLs (rewriting blob to raw, deriving the default branch from a repo URL) but aren't required — plain TOML URLs work without any host-provider involvement.

### 4.3 Resolution

1. **Parse the input.** If it looks like a URL, strip trailing slashes, `.git`, query strings, fragments. Otherwise treat as a pasted TOML block (input form 5).
2. **Classify the URL form.** Try host providers in turn; first match wins.
   - Starts with `file://` → already a fetchable URL; skip host-provider handling.
   - Some `HostProvider.parse_blob_url(url)` returns non-None → blob URL (input form 1). Use `provider.raw_url(...)` to derive the fetchable URL; the blob URL itself is what gets persisted in the marketplace file.
   - Some `HostProvider.parse_raw_url(url)` returns non-None → raw URL (input form 2). Use as-is for fetch; reconstruct the canonical blob URL via `provider.blob_url(...)` for persistence.
   - Some `HostProvider.parse_repo_url(url)` returns non-None → repo URL (input form 3). Resolve ref via `provider.default_branch(...)`, then try fetching `marketstall.toml` at the repo root; on 404, try `marketplace.toml`; on both 404, surface a clear "no marketstall.toml or marketplace.toml at repository root" error.
   - No provider matches → plain TOML URL (input form 4). Fetch the URL as-is; no host-provider rewriting; persist exactly what the user pasted.
3. **Fetch.** HTTP errors surface as install failures with the fetched URL surfaced for debugging.
4. **Parse and validate.** Reject with a clear error on malformed TOML or missing required fields.
5. **Inspect body shape to decide subscription type.**
   - Body contains `[[markets]]` or `[[stalls]]` (with or without inline `[[haybales]]`) → it's a marketplace. Add to consumer's `[[markets]]`.
   - Body contains `[[haybales]]` only → it's a marketstall. Add to consumer's `[[stalls]]`.
   - Body contains neither → reject as malformed.
6. **Run the conflict-resolution prompt** if any haybale name collides with already-subscribed sources (see §8.3).
7. **Auto-refresh** to populate the project cache.

For input form 5 (pasted TOML block): the dialog parses the block, requires a `[[haybales]]` section, derives `<dist-name>` from the first haybale's `name` field, writes the block to `~/.haywire/stalls/<dist-name>.toml`, then enters the resolution flow as if the user had pasted `file:///Users/.../<dist-name>.toml`.

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

    def parse_repo_url(self, url: str) -> ParsedRepo | None:
        """Parse a bare repo URL into (owner, repo). None if not a match."""

    def raw_url(self, owner: str, repo: str, ref: str, path: str) -> str:
        """Construct the raw URL for fetching."""

    def blob_url(self, owner: str, repo: str, ref: str, path: str) -> str:
        """Construct the share URL (canonical, browser-friendly)."""

    def default_branch(self, owner: str, repo: str) -> str:
        """Detect the default branch. Defaults to probing 'main' then 'master'."""
```

`ParsedRef` and `ParsedRepo` are small frozen dataclasses.

### 5.2 Host Table

Built-in providers as of this spec:

| Host                                   | Blob path                                 | Raw path                                          |
| -------------------------------------- | ----------------------------------------- | ------------------------------------------------- |
| github.com                             | `/blob/{ref}/`                            | `raw.githubusercontent.com/{owner}/{repo}/{ref}/` |
| gitlab.com                             | `/-/blob/{ref}/`                          | `/-/raw/{ref}/`                                   |
| bitbucket.org                          | `/src/{ref}/`                             | `/raw/{ref}/`                                     |
| Gitea / Forgejo (codeberg.org, others) | `/src/branch/{ref}/` or `/src/tag/{ref}/` | `/raw/branch/{ref}/` or `/raw/tag/{ref}/`         |

Self-hosted instances of these platforms use the same URL conventions; only the hostname differs.

### 5.3 Provider registry

```python
HOST_PROVIDERS: list[HostProvider] = [
    GitHubProvider(),
    GitLabProvider(),
    BitbucketProvider(),
    GiteaProvider(),
]

def resolve_host(hostname: str) -> HostProvider | None:
    for provider in HOST_PROVIDERS:
        if provider.matches(hostname):
            return provider
    return None
```

### 5.4 Self-hosted instances

Users with self-hosted GitHub Enterprise, GitLab, Gitea, or Forgejo declare them in `~/.haywire/config.toml`:

```toml
[[hosts]]
hostname = "git.acme.example"
provider = "gitlab"

[[hosts]]
hostname = "code.team.example"
provider = "gitea"
```

`resolve_host()` consults the user's config first, then falls back to built-in matchers. Each config entry maps a hostname to one of the built-in provider names (`github`, `gitlab`, `bitbucket`, `gitea`).

### 5.5 File layout

```text
packages/haywire-core/src/haywire/core/marketstall/
├── __init__.py
├── host_providers/
│   ├── __init__.py        # exports HOST_PROVIDERS, resolve_host(), HostProvider
│   ├── base.py            # Protocol + ParsedRef / ParsedRepo
│   ├── github.py          # GitHubProvider
│   ├── gitlab.py          # GitLabProvider
│   ├── bitbucket.py       # BitbucketProvider
│   └── gitea.py           # GiteaProvider (also handles Forgejo)
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

`~/.haywire/cache/<url-hash>.toml` keyed by the resolved raw URL. On every successful fetch, the cache is overwritten. On fetch failure, cache provides the fallback body. No TTL.

A content hash of the cached body is recorded as a side metadata file `<url-hash>.sha256` to enable "did this URL change since last refresh?" detection — informs the update-available signal in §10.

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

| Filter                  | What it does                                                                                                                                     |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| `ignores`               | Each subscription's `ignores` array lists names to skip from that source. Populated by the user's conflict-resolution prompt at Add Source time. |
| Heaps shadow            | Any candidate haybale whose name matches a `[[heaps]]` entry is dropped — local heaps always win.                                                |
| First-come-first-served | After the above, deterministically keep the first occurrence of any remaining duplicate. Safety net for hand-edits.                              |

### 8.3 The user-prompt path

When Add Source resolves a new subscription and detects name collisions against the existing resolved state, the user is shown one row per conflict and asked which source to keep. The losing source's `ignores` array gains the colliding name. Future refreshes honor the choice without re-asking.

## 9. The refresh report

`RefreshReport` (returned by `MarketplaceState.refresh()`):

| Field                 | Meaning                                                                          |
| --------------------- | -------------------------------------------------------------------------------- |
| `sources_fetched`     | Subscriptions successfully read (cache hits count).                              |
| `sources_unavailable` | Subscriptions that failed to fetch AND had no cached fallback.                   |
| `unavailable_urls`    | Specific URLs in the previous count. Drives the yellow banner.                   |
| `haybales_resolved`   | Non-stale entries in the final cache.                                            |
| `new_stale`           | Entries that became stale on this refresh (were fresh before).                   |
| `updates_available`   | Installed haybales whose cache `min_version` exceeds installed version. See §10. |

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

[[stalls]]
url = "https://going-haywire.github.io/haywire/stalls/haybale-studio.toml"
ignores = []
doubles = []
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

The existing drift gate (`detect_share_drift` in `haywire_studio.share`) gains a third check: **declared `min_version` floors lagging behind installed versions**.

Scenario: library declares `haybale-core~=0.0.1`; the author has since updated to `haybale-core 0.3.0` and is building against the new API. Their published library still tells consumers they need only 0.0.1 — technically a valid floor (pip will install higher), but understates the real requirement.

New check:

For each declared dependency in `[project] dependencies`, parse the version specifier. Compare its floor against the installed version (via `importlib.metadata.version`). If `installed > declared_floor` and the operator is `~=` or `>=`, flag as drift.

`DepDrift` gains a field:

```python
@dataclass(frozen=True)
class DepDrift:
    lib_dir: Path
    pyproject_missing: list[str]
    decorator_missing: list[str]
    pyproject_version_lag: list[tuple[str, str, str]]   # (dist, declared_floor, installed)
    unresolved: list[str]
```

`apply_drift_fix` rewrites lagging floors to match the installed version when the user opts to fix.

`haywire share --strict` refuses to ship a library with lagging floors. Default mode (warn) prints the lag alongside other drift findings.

The Detect Dependencies button's Union mode bumps lagging floors. Replace mode regenerates from detected imports + current installed versions.

## 13. Migration

Not applicable. This is a breaking pre-release change.

Haywire has no external users yet; the only existing files in the old schema live in the dev workspace itself, and those can be reset by hand. The runtime ships with parsers that accept only the new vocabulary. No alias period; no `_migrate_marketplace_schema_if_needed` extension.

The existing `_migrate_marketplace_schema_if_needed` function in `config.py` can be deleted outright — it was added to handle the earlier `sources` → `[[marketplaces]]` transition, and that transition is being superseded by the new vocabulary in one shot.

Dev-workspace cleanup: delete `~/.haywire/marketplace.toml` and any project-side `.haywire/marketplace.toml` files before running the new code. The next `haywire init` (or first `haywire share` / Add Source action) regenerates the files in the new shape.

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

A single coherent rename pass plus the new URL distribution surface. Small handful of commits with no intermediate "broken state" branch — each commit leaves the tree green.

1. **Host providers**: new `haywire.core.marketstall.host_providers/` package with `base.py` (Protocol + dataclasses), `github.py`, `gitlab.py`, `bitbucket.py`, `gitea.py`, plus `__init__.py` exposing `HOST_PROVIDERS` and `resolve_host()`. Self-hosted-instance config reading.
2. **Runtime types and parsers**: rename `MarketplaceEntry` → `Haybale` (with new `os` field); rewrite parsers for the new section names; allow `[[haybales]]` inline in marketplace bodies; update `parse_remote_marketplace_body` / `parse_marketstall_body`.
3. **State + helpers**: `MarketplaceState`, the `add_*` helpers; URL-resolution helper combining host detection + body-shape detection + auto-subscribe; current-OS detection helper.
4. **UI**: Add Source dialog collapses to one field; Library Browser + Library Overview Editor update field references; new Update button; OS multi-select in Edit dialog; OS-mismatch Install gating with tooltip.
5. **Init + share + config**: `init.py` writes `[[heaps]]` and READMEs with marker pairs; `share.py` emits `[[haybales]]` (including `os` from `[tool.haywire]`), computes share URL via host provider when possible, prints it, updates READMEs in place (default; `--no-update-readme` opts out); delete the legacy `_migrate_marketplace_schema_if_needed` in `config.py`.
6. **Drift gate extension**: `min_version` lag detection; `DepDrift` field + apply path.
7. **Per-haybale stall generator**: `scripts/generate_marketstall.py` produces the two-tier layout.
8. **Tests**: rewrite every test file referencing old names; new tests for host providers, URL resolution, plain-TOML-URL form, OS field roundtrip, OS-mismatch gating, README marker update, update-available signal, version-lag drift.
9. **Docs**: the six files listed in §15.
10. **Verification**: full `ruff` / `mypy` / `pytest` sweep, plus a manual smoke through Add Source / Refresh / Edit / Detect-Dependencies / Share / Update against a fresh `haywire init` project.

## 17. Non-goals

- **No version-based conflict resolution.** Two sources publishing the same haybale name still resolve by user choice or first-come-first-served, not by version comparison.
- **No central registry, mirrors, or CDN.** Authors host their own repositories.
- **No signed packages or cryptographic verification.** Authors host their content; consumers read the source URL before installing if they care to verify.
- **No transitive dependency resolution.** A haybale's `dependencies` list is informational; consumers install dependencies individually. pip handles actual resolution.
- **No lockfiles or reproducible installs at the Haywire level.** Reproducibility is the project's responsibility through standard Python tooling.
- **No forced updates.** The update-available signal is informational; the user always decides when to upgrade.
- **No automatic discovery of repositories.** A `marketstall.toml` at the root is the only signal that a repo is a publisher.
- **No publisher index.** There is no list of "all marketstalls in the world."
- **No aggregator-style publishing via `haywire share` at first ship.** A `haywire aggregate` command is a follow-up.
- **No auto-detection of self-hosted git hosts.** Probing endpoints like `/api/v4/version` or `/api/v1/version` would be fragile and platform-specific. Self-hosted instances are declared explicitly in `~/.haywire/config.toml`; the `haywire share` warning surfaces a ready-to-paste snippet when an unknown host is encountered.
- **No README templating beyond the marker pair.** The README auto-update writes only between the markers — nothing else in the file is touched. Authors who want richer instructions write their own prose around the markers.

## 18. Open questions

None at draft time. Surfaced during implementation if any.
