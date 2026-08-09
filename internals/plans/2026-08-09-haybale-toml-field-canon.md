# `haybale.toml` — field canon and data lifecycle

Design note, 2026-08-09. Supersedes the direction in
[ADR 0024](../../docs/adr/0024-library-metadata-single-source.md) and
[the consolidation plan](../superpowers/2026-08-08-library-metadata-consolidation.md).

**Built, 2026-08-09** — see the [implementation plan](2026-08-09-haybale-toml-implementation.md)
and [ADR 0025](../../docs/adr/0025-haybale-toml-is-canon.md). This note defines
**where each field's canon lives, how it is aggregated, and when it is
generated** — not the implementation order.

> **Where the cited code lives.** Master was rolled back to `ed00decd`, so
> several things this note references are **not on master**: `LibraryMetadata`,
> `distmeta.py`, `_hot_swap_bumped_libraries()`, `_PRECONDITION_FIXES` /
> `strip_os` / `add_origin`, the AST `read_decorator`, and the declared-path
> preconditions. They are all on **`feat/library-metadata-consolidation`**
> (tip `53108922`, pushed). Read them there — the reasoning below rests on real
> working implementations, not sketches. Nothing from that branch is
> cherry-picked back; what survives is findings, plus three shapes worth
> reimplementing (the two-phase publish, the precondition/fix machinery, and the
> post-publish registry eviction).

## The problem this replaces

ADR 0024 made `pyproject.toml` the single source for descriptive metadata and had
the `@library(...)` decorator read it back through `importlib.metadata`. That
removed the drift, but inherited a defect it could not fix: **dist metadata is
written once, at install time.** `site-packages/<dist>.dist-info/METADATA` does
not change when `pyproject.toml` changes — not even for an editable install
(verified 2026-08-08 by editing a pyproject in place and re-reading in a fresh
interpreter; version and description both reported pre-edit values until
`pip install -e` was re-run).

So every metadata edit required `uv sync` + registry reload to become visible.
That forced editing out of a modal and into the Share wizard, which is why the
overview's Edit dialog was deleted. The cost was paid to work around the read
path, not to solve the duplication.

`haybale.toml` removes the indirection instead. It sits next to `__init__.py`,
inside the package directory, so it ships in the wheel — the constraint that
disqualified `[tool.haywire]`, which never reaches an installed distribution.
The runtime reads it from disk. An edit is a file write: no sync, no reload, no
reinstall.

## Canon, in one sentence

`haybale.toml` is canon for everything descriptive about a library.
`pyproject.toml` keeps **`dependencies`** as its sole canonical field, plus the
packaging machinery no other file can own (`build-system`, `entry-points`,
`[tool.hatch]`). Everything else in `[project]` is *generated into* it during
the share process.

### The rule that follows: nothing writes the decorator

A decorator edit is a source edit, and a source edit needs a library reload to
take effect. That is the cost this whole design exists to remove, so no flow —
edit modal, share wizard, drift auto-apply — writes `@library(...)` ever again.
Every field a tool needs to *write* lives in `haybale.toml`; the decorator keeps
only what must be known before any file is read.

This is why `on_reload` and `linked_libraries` are in the TOML rather than the
decorator: the drift detector auto-applies `linked_libraries`, and an
auto-applied decorator edit would mean an automatic reload.

A consequence worth having: `decorator_io`'s regex writers
(`_set_decorator_str_field`, `_set_decorator_list_field`,
`merge_decorator_list_field`) lose their callers. The bug class they carried —
the double-quote no-op fixed in `bc59f254` — cannot recur, because writing a
TOML value is not a text substitution.

## pyproject.toml

```toml
[project]
# generated from haybale.name
name = "haybale-core"
# generated from haybale.version
version = "0.0.40"
# generated from haybale.description
description = "Fundamental components for haywire graphs"
# generated from haybale.tags
keywords = ["haywire", "node-editor", "core"]
# generated from haybale.authors — names only; author URLs are dropped
authors = [{ name = "maybites" }, { name = "cansik" }]
# emitted only when [deprecated] is present — PEP 621 has no deprecation field,
# and this classifier is the ecosystem's only signal
classifiers = ["Development Status :: 7 - Inactive"]

# CANON — authored here, read by everything else
dependencies = ["haywire-core>=0.0.31"]

[project.urls]
# generated from haybale.homepage_url
Homepage      = "https://github.com/going-haywire/haywire"
# generated from haybale.documentation_url
Documentation = "https://going-haywire.github.io/haywire/"
# generated from haybale.issues_url
Issues        = "https://github.com/going-haywire/haywire/issues"
# generated from origin
Source        = "https://github.com/going-haywire/haywire"
```

The generated `[project]` fields exist so the wheel is a well-formed PEP 621
package — PyPI, `uv`, and `pip` read them, and Haywire does not. Nothing in the
studio reads `[project]` back except `dependencies`.

**Author URLs do not survive into pyproject.** PEP 621 `authors` entries carry
`{name, email}` and have no URL slot. The URL is kept in `haybale.toml`, travels
in the wheel, reaches the marketstall row, and renders in the library overview —
it simply has nowhere to go in the generated package metadata, and Haywire never
reads it back from there. `[project.urls] Author` is *not* resurrected for it:
that key can hold one URL, and `authors` is a list.

## Field canon and inheritance table

`haybale` — how the field gets into `haybale.toml`.
`marketstall` — how the row field is produced at publish time.

| field               | haybale                                     | marketstall                                                                       | example                                                                 |
| ------------------- | ------------------------------------------- | --------------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| `name`              | immutable (mutable only via  rename-wizard) | copy                                                                              | `"haybale-core"`                                                        |
| `id`                | immutable (mutable only via  rename-wizard) | copy                                                                              | `"core"`                                                                |
| `version`           | set via share-wizard                        | copy                                                                              | `"0.0.40"`                                                              |
| `linked_libraries`  | seeded by scaffold; share-wizard maintains  | copy                                                                              | module names:`["haybale_studio"]`                                       |
| `label`             | user input                                  | copy                                                                              | `"Core"`                                                                |
| `description`       | user input                                  | copy                                                                              | `"Fundamental components for haywire graphs"`                           |
| `authors`           | user input (repeatable; name, optional url) | copy                                                                              | `[{name="maybites",url="https://maybites.ch"},{name="cansik"}]`         |
| `tags`              | user input                                  | copy                                                                              | `["haywire", "node-editor", "core"]`                                    |
| `os`                | user input (multi-select)                   | copy                                                                              | `["macos", "linux"]`                                                    |
| `on_reload`         | user input (choice)                         | copy                                                                              | `"restart"`                                                             |
| `origin`            | regenerated by share-wizard from the git remote | copy                                                                          | `"https://github.com/going-haywire/haywire"`                            |
| `origin_provider`   | autofilled by preflight's host check         | copy                                                                              | `"github"` / `"gitlab"`                                                 |
| `homepage_url`      | user input                                  | copy                                                                              | `"https://github.com/going-haywire/haywire"`                            |
| `documentation_url` | user input                                  | copy                                                                              | `"https://going-haywire.github.io/haywire/"`                            |
| `issues_url`        | user input                                  | copy                                                                              | `"https://github.com/going-haywire/haywire/issues"`                     |
| `examples_path`     | user input; wizard repairs a broken one     | copy — verbatim, project-relative; verified at preflight                          | `"examples/"` (from the project root)                                   |
| `tests_path`        | user input; wizard repairs a broken one     | copy — verbatim, project-relative; verified at preflight                          | `"tests/"` (from the project root)                                      |
| `notes`             | user input; preflight offers the package root's `*.md` | copy — a bare filename inside the package dir              | `"NOTES.md"` (replaces `docs_path`)                                     |
| `deprecated`        | hand-edited in the file; no modal field     | copy — `since` / `reason` / `successor`                                           | `{since="0.0.41", reason="…", successor="haybale-vision"}`              |
| `require`           | —                                           | generated — on the haywire-core from `[project] dependencies`                     | `"haywire-core>=0.0.31"`                                                |
| `install_spec`      | —                                           | generated — `{name} @ git+{origin}.git@{tag}#subdirectory={lib_rel}`              | `"haybale-core @ git+https://…@v0.0.40#subdirectory=barn/haybale-core"` |
| `source`            | —                                           | generated — `"git"` (wizard) / `"pypi"` (CI script)                               | `"git"`                                                                 |
| `source_label`      | —                                           | runtime routing, not persisted                                                    | —                                                                       |
| `source_file`       | —                                           | runtime routing, not persisted                                                    | —                                                                       |
| `source_origin`     | —                                           | runtime routing, not persisted                                                    | —                                                                       |
| `via`               | —                                           | refresh-owned, project `[[caches]]` only                                          | —                                                                       |
| `last_seen`         | —                                           | refresh-owned, project `[[caches]]` only                                          | —                                                                       |
| `stale`             | —                                           | refresh-owned, project `[[caches]]` only                                          | —                                                                       |

Three groups, and the shape of the table is the point:

- **copy** — 17 fields pass through untouched. A marketstall row is mostly a
  verbatim `haybale.toml`.
- **generated** — 3 fields the library cannot state itself: `install_spec`
  (name + origin + tag + subdirectory), `source`, and `require` (the framework
  floor projected out of `[project] dependencies`).
- **not persisted / refresh-owned** — 6 fields belonging to the consumer's
  cache, never written by a publisher.

Three fields are **written by the share wizard and read-only in the edit
modal**: `version` (the wizard *is* the bump machinery), `origin` (the git
remote at publish time), and `origin_provider` (what preflight's host check
already resolved). All three are stored in `haybale.toml` — that is what lets an
installed library resolve its own paths without a marketstall row and without
local host config — but the author never types any of them.

**`rename-wizard` does not exist yet** — until it does, `name` and `id` are
immutable after scaffold. Building it is deferred until this change lands, so it
can edit `haybale.toml` instead of rewriting the decorator (see Settled).

`require` is the one marketstall field sourced from `pyproject.toml` rather than
`haybale.toml`, because `dependencies` is canon there. It is a *projection*, not
a copy: `haywire_core_requirement()` distinguishes three states (undeclared,
declared with no floor, declared with a floor) that a bare specifier collapses.
See `haywire.core.marketstall.requirement`.

## `haybale.toml` — target author surface

`barn/haybale-core/haybale_core/haybale.toml`:

```toml
# name and id are immutable — changing either needs the rename-wizard
name = "haybale-core"
id = "core"

# all three written by the share wizard, never by the edit modal.
# version is PEP 440 — no "v". The git tag is derived: tag_for(version).
version = "0.0.40"
origin = "https://github.com/going-haywire/haywire"
# which kind of host `origin` is. Autofilled by preflight; travels to consumers
# so they need no local config for a self-hosted forge.
origin_provider = "github"

label = "Core"
description = "Fundamental components for haywire graphs"
tags = ["haywire", "node-editor", "core"]

os = ["macos", "linux"]
on_reload = "restart"

# user input; the wizard auto-adds entries the drift detector proves are missing
linked_libraries = ["haybale_studio"]

# relative to the PROJECT root (the directory holding .haywire/) — verbatim,
# the publisher does not prefix them
examples_path = "examples/"
tests_path = "tests/"

# a bare filename in THIS directory — one supplementary human-readable page
notes = "NOTES.md"

homepage_url = "https://github.com/going-haywire/haywire"
documentation_url = "https://going-haywire.github.io/haywire/"
issues_url = "https://github.com/going-haywire/haywire/issues"

# repeatable; `url` is optional and does not survive into pyproject
[[authors]]
name = "maybites"
url = "https://maybites.ch"

[[authors]]
name = "cansik"

# omitted unless the library is being retired. Hand-edited — the modal has no
# field for it. Informational only: never blocks install, enable, or update.
[deprecated]
since = "0.0.41"
reason = "Superseded by haybale-vision, which handles both OAK-D revisions."
successor = "haybale-vision"
```

TOML ordering matters in that example: every bare key must precede the first
table header, or it is parsed into that table. `[[authors]]` and `[deprecated]`
therefore come last.

### `notes` replaces `docs_path`

**`docs_path` is deleted, not renamed.** It never held what its name claimed: it
was the *module directory* relative to the git root
(`barn/haybale-core/haybale_core/`), and both consumers appended something to it
— `docs/<registry_key>.md` for the farmhand, `OVERVIEW.md`/`QUICKREF.md` for the
overview fetch. Nothing treated it as "the docs".

It is also **derivable**, so storing it was redundant. `install_spec` already
carries the library dir relative to the git root as `#subdirectory=`, and the
module name follows from the distribution name, so the farmhand's coordinate is
`subdirectory(install_spec) + module_of(name) + "/docs/"` — the CI generator
literally writes `f"{subdirectory}/{module_name}/"` from two components it holds
separately. Deriving it removes a field that can disagree with `install_spec`.

**The derivation must normalise, not just swap separators:**

```python
def module_of(dist_name: str) -> str:
    """The module directory for a haybale distribution name."""
    return re.sub(r"[-_.]+", "_", dist_name).lower()
```

`name.replace("-", "_")` is **not** sufficient — verified against every in-tree
haybale, and `haybale-TEST_A` breaks it: the module is `haybale_test_a`, because
PEP 503 lowercases distribution names while the declared `name` keeps its case.
The normalising form above matches all ten in-tree haybales with no mismatches.

Two related things in the tree, worth knowing about when implementing:
`_read_self_module_name()` (`dep_detect.py:139`) uses the naive replace for a
different purpose and carries the same latent bug; `find_module_dir()`
(`dep_detect.py:118`) sidesteps the question entirely by scanning for
`__init__.py` across flat and `src/` layouts, which is why the publisher — who
has the filesystem — should keep using it rather than deriving.

*Out of scope:* `haywire-core`'s module is `haywire`, which no transformation
produces. It is a framework package, never published as a haybale, so it never
travels this path.

**The farmhand does not need either field for an installed library.** It reads
`identity.folder_path / "docs"` directly (`catalog_tools.py:198`); the wheel
carries the whole `docs/` tree (48 files confirmed in the packaging spike). The
remote branch is the only one that needs a coordinate.

In its place, `notes` names **one human-readable Markdown file inside the
package directory** — a bare filename, no slashes, no `../`:

```toml
notes = "NOTES.md"
```

This is not the library's front page. The overview panel already renders label,
description, authors, tags and version from the row; `notes` is the
supplementary page an author writes for anything that does not fit those fields.
`fetch_overview()` already supports exactly this shape — `if
base.endswith(".md"): candidates = [base]` — so naming the file makes explicit
the branch that currently only gets reached by guessing, and drops two
speculative HTTP fetches per library. A library whose page is `NOTES.md` or
`INTRO.md` becomes reachable at all, which the hardcoded
`OVERVIEW.md`/`QUICKREF.md` pair never allowed.

A bare filename is deliberate: the file sits in the same directory as
`haybale.toml` itself, so there is no "relative to what?" question — the one
this design has had to answer three separate ways for other fields.

#### Preflight check: `set_notes`

A declared `notes` file that does not exist fails preflight, `kind="act"`,
`fix_id="set_notes"`, `lib_dir` kwarg — the shape `strip_os` established.

The fix modal **scans the package root for `*.md` and offers what it finds**,
plus `<empty>` to opt out. That makes it better than the `clear_examples_path` /
`clear_tests_path` handlers, whose only remedy is deletion: here the valid
answers are enumerable, so the modal proposes real ones. This closes the missing
`set_*` gap noted against the landed declared-paths work.

Scan the **package root on disk**, not the wheel — at preflight no wheel exists
yet, and everything in the package dir provably reaches the wheel anyway (see
Settled), so the checkout gives the same answer with no build.

### `deprecated`: inform, never block

PEP 621 has **no `deprecated` field**, and one cannot be invented — unknown keys
in `[project]` are a spec violation (unlike `[tool.*]`). The packaging world's
only signal is a trove classifier, `"Development Status :: 7 - Inactive"`, which
PyPI renders and which carries no reason and no successor.

So `haybale.toml` owns it and the publisher *projects* it into that classifier,
the same way `tags` becomes `keywords`:

```toml
[deprecated]
since = "0.0.41"
reason = "Superseded by haybale-vision, which handles both OAK-D revisions."
successor = "haybale-vision"   # optional
```

`since` is required because deprecation is a **historical fact, not a current
state** — the same reasoning `CompatibilityWarning`'s docstring gives for its own
`version` field ("ALWAYS explicit — never derived from the library's current
version"). Without it, a user on 0.0.30 cannot be told whether their version
predates the notice.

**Inform only — it gates nothing.** A deprecated library that still works still
installs, still enables, still updates. `os` remains the only field that blocks
installation. Where it surfaces:

| surface | behaviour |
| --- | --- |
| library browser | badge on the row |
| overview | banner carrying `reason`; an Install action for `successor` when set |
| install / enable | unaffected — warn, never refuse |
| `refresh()` | worth surfacing once for a deprecated library the user has installed |

**No edit-modal field.** Deprecating is rare and deliberate, so the author edits
`haybale.toml` directly — this is the one block the modal does not round-trip,
and the authoring docs must say so explicitly, since the modal otherwise implies
it shows everything editable.

Treat a published `[deprecated]` block as immutable, like
`CompatibilityWarning`'s append-only history: an author who changes their mind
bumps a version and removes the block rather than rewriting what consumers
already fetched.

**Distinct from `CompatibilityWarning`** (ADR 0005), and not to be merged with
it: that is per-*component*, append-only, and checked against **saved graphs**;
this is library-wide and checked against **installed libraries**. Different
scope, different trigger.

### The project root must be the git root

`examples_path` and `tests_path` are project-relative and reach the row
verbatim, but a consumer resolves them against `origin` at a tag — i.e.
**git-root-relative**. Those are only the same directory if the project *is* the
repository.

**A scaffolded project already satisfies this.** `haywire init` runs `git init`
at the project directory (`init.py:657`) and refuses to scaffold at all when git
is missing (`init.py:567`), so every project it creates is a repository rooted
exactly at the project root.

The check therefore guards a case the scaffold cannot produce, but a user can:
moving a scaffolded project inside another repository, deleting `.git`, or
hand-assembling a project layout. If a project ended up at
`repo/projects/foo/`, a declared `examples/` would resolve to `<repo>/examples/`
— silently wrong, and wrong **only for consumers**, since the publisher's local
path still works. That asymmetry is what makes it worth a check rather than a
convention.

**Preflight requires them to coincide.** Walking up from the library directory
must find the git root at exactly the project root (the directory holding
`.haywire/`). Otherwise publishing fails with a message pointing at the CLI —
not an inline `kind="act"` fix, because the remedy is restructuring a
repository, not editing a field.

Rejected alternatives: *prefixing at publish* with the project's git-relative
path would work, but reintroduces exactly the `_declared_path()` step this
design deleted, and re-opens the "relative to what?" question. *Making the
fields git-root-relative* is honest but contradicts their stated base and forces
authors to write `projects/foo/examples/`.

Nested projects in a monorepo are a feature with their own design, not something
to accommodate implicitly here.

### Two path scopes, and why they differ

`notes` is **library-relative** — strictly, package-directory-relative: it
travels inside the wheel, so it means the same thing wherever the library lands.

`examples_path` and `tests_path` are **project-relative** — from the project
root, the directory holding `.haywire/`. Examples and tests belong to the
*project*, not the library: an example graph wires several libraries together
and cannot live inside any one of them. This corrects a misconception carried
since the first draft, which treated them as library-relative and had the
publisher prefix them with the library's own path (`_declared_path()` in
`publishing/marketstall.py`). That prefixing is deleted — the declared value
reaches the row verbatim.

They stay in `haybale.toml` despite being project-scoped, because a library
pointing a user at the project's examples is worth having and there is nowhere
else to say it. The consequence is accepted rather than hidden: in a wheel
installed by a consumer, these two point into the *publisher's* project and mean
nothing locally. They are publisher-side coordinates, resolved through
`HostProvider` against `origin` at `install_spec`'s ref — never read as local
paths.

No absolute URL is ever stored — the host and ref come from `origin` and
`install_spec`, so a baked URL could contradict them.

### `origin` and the ref: a library can locate itself

**`origin` lives here**, regenerated from the git remote in Phase A of every
publish. An earlier draft kept it out on the grounds that a fork would carry a
stale upstream URL. That was wrong: forking and cloning gives `origin` = *the
fork* (upstream is only present if added explicitly, conventionally as
`upstream`), so the wizard reads the right value the moment Alice publishes her
fork. The only stale window is between forking and her first publish — during
which nothing has been published to be wrong about, and pointing at upstream is
arguably the correct local answer anyway.

Keeping it here is what lets an **installed** library resolve its own `notes`
and `examples_path` without a marketstall row — the case a heap, folder, or
editable install would otherwise fail (see stage 4).

**The ref is derived, not stored.** `resolve_row_path()` needs a git ref;
today it recovers one from `install_spec` via `_ref_from_install_spec()`, which
an installed library has no reason to carry. Since a haybale's tag is always
`v` + its version, the ref is a function of data already present:

```python
def tag_for(version: str) -> str:
    """The git tag for a released version. One definition, three callers."""
    return f"v{version}"
```

Sibling to `haywire_core_requirement()`, and for the same reason its module
docstring gives: *one* definition of what the token means rather than several
that drift. Today `f"v{pipeline.version}"` is re-encoded independently in
`steps/commit.py:35`, `:60`, and inside `install_spec`'s construction.

**`version` stays PEP 440 — no `v` prefix.** Storing the tag form instead was
considered and rejected: it is illegal in `[project] version` (which is
generated from it), it would sit beside `require = "haywire-core>=0.0.31"` where
a `v` can never appear, and `packaging.Version` *tolerates* the prefix by
normalising it away — so mixed forms compare correctly until something does a
string equality, and then they do not. The `v` belongs to the tag, and
`tag_for()` is where it lives.

If tags ever stop being `v`-prefixed, or a library needs to publish at a tag
unrelated to its version, storing the tag becomes right — but that is a
different feature, and today `tag == "v" + version` is invariant across the
whole pipeline.

### `origin_provider`: the host mapping must travel with the library

`origin` alone is not enough to build a URL. `resolve_row_path()` needs a
`HostProvider`, and `resolve_host(hostname)` finds one by matching built-ins
(`github.com`, `gitlab.com`) or consulting `~/.haywire/config.toml`. That config
is **machine-local**, while `origin` is **published data** — an asymmetry that
breaks every self-hosted library:

| | publisher | consumer |
| --- | --- | --- |
| `gitlab.zhdk.ch` declared in `~/.haywire/config.toml` | yes | almost never |
| `resolve_host()` succeeds | yes | **no** |
| Docs / Examples links render | yes | **no** |
| install works | yes | yes — `install_spec` is a plain clone URL |

The library installs correctly and silently shows no links, and the publisher
never sees it because theirs is the one configured machine. Only the publisher
knows what kind of forge their host runs, so **that answer has to be published**,
not rediscovered.

**Preflight already computes it.** `steps/preconditions.py:237` calls
`resolve_host(hostname)` and throws the provider away, keeping only the
null-check. Phase A records what it found:

```python
provider = resolve_host(hostname)          # already called at preflight
origin_provider = provider.name if provider else ""
```

No new probe, no new user input, and it cannot disagree with the gate that let
the publish through.

Resolution order for a consumer:

1. `origin_provider` when present — the publisher's own answer, always right
2. `resolve_host(hostname)` — built-ins, then local config
3. `None` — no link. Never a guess.

The vocabulary is closed (`"github"`, `"gitlab"`); an unknown value degrades to
no-link rather than to a wrong URL.

**Prerequisite: providers must be host-parameterised.** Today `GitLabProvider`
hardcodes `gitlab.com` in five places — `matches()`, both parse patterns, and
all three URL builders — so declaring `gitlab.zhdk.ch` in local config resolves
to a provider that then emits `https://gitlab.com/...`, pointing at the wrong
server. `load_self_hosted_hosts()` is therefore wired to something that
structurally cannot honour it.

```python
class GitLabProvider:
    def __init__(self, hostname: str = "gitlab.com"):
        self._hostname = hostname

    def matches(self, hostname: str) -> bool:
        return hostname == self._hostname

    def blob_url(self, owner, repo, ref, path) -> str:
        return f"https://{self._hostname}/{owner}/{repo}/-/blob/{ref}/{path}"
```

`resolve_host()` then constructs a per-host instance instead of returning the
`gitlab.com` singleton, and the parse patterns interpolate
`re.escape(self._hostname)`. Same shape for `GitHubProvider` — GitHub Enterprise
has the identical problem.

This is a pre-existing bug that this design neither causes nor worsens, but it
does raise the stakes: with `origin` in every wheel, more paths depend on host
resolution working. Fix it as a prerequisite, not a follow-up.

### What stays in the decorator

```python
@library(id="core", file_watcher=False)
class Library(BaseLibrary): ...
```

`id` is duplicated deliberately: the registry needs it before any file read, and
a mismatch between decorator and TOML is a preflight failure rather than a
silent pick. `file_watcher` is a development-only runtime flag with no
publishing meaning.

Both remaining kwargs are **author-written only**. Nothing in the studio writes
this call, which is the rule the whole design rests on — see "nothing writes the
decorator" above. `linked_libraries` and `on_reload` moved to the TOML precisely
because tools need to write them.

The trade: the library loader now depends on a parseable `haybale.toml` for
`linked_libraries` (hot-reload scope) and `on_reload` (post-install prompt) — see
"Reading it at import" below.

### Reading it at import

The decorator reads `haybale.toml` from the directory it already computes for
`folder_path`, and splats the result over `kwargs` exactly where
`distribution_fields(dist)` sits today:

```python
class_file = inspect.getfile(inner_cls)
kwargs["folder_path"] = str(Path(class_file).parent)
kwargs.update(haybale_fields(Path(class_file).parent))   # replaces distribution_fields
```

Nearly all the machinery exists. `read_toml()` (`core/tomlio.py`) is the
sanctioned read-only surface and `toml` is already a hard dependency of
haywire-core; `core.library` importing `core.tomlio` introduces no cycle.
`_parse_haybale()` (`core/marketstall/parsing.py`) is the template for
field-by-field parsing, and `read_manifest()` /`read_manifest_lenient()`
(`publishing/manifest/reader.py`) are the template for the strict/lenient split.
`distribution_fields()` already establishes the omit-absent-keys-so-callers-can-
splat contract the new reader should copy.

What is new: the reader itself (`core/library/haybale_toml.py`, sibling to
`distmeta.py` — placing it there avoids a new `core.library` → `core.marketstall`
edge), and module-name validation for `linked_libraries`.

**A malformed, missing, or contradictory file raises `LibraryLoadError`** at
decoration time — the same place `@library` already rejects a missing `label`/
`id`. Three fatal cases: file missing (nothing to build an identity from),
malformed TOML (wrap `TOMLDecodeError` with the path), and an `id` that is absent
or disagrees with the decorator's.

Raising is safe because `LibraryRegistry` **already wraps every library load in
`try/except`** (`library/registry.py:626`, `:660`): the studio still starts, that
one library fails visibly, and the error names the file. The alternative —
defaulting to empty — yields `linked_libraries=[]`, and a subscriber then holds a
stale class reference after a reload. That is the precise failure the field
exists to prevent, surfacing later and somewhere unrelated.

The `id`-mismatch check belongs here *as well as* at preflight: the decorator
runs on every import, so the author sees it immediately rather than weeks later
at publish.

**Validate module-name shape.** `_get_tracking_scopes` appends `dep + "."`
verbatim, so a hyphenated `"haybale-studio"` produces a prefix matching no Python
module — the scope is silently dead. A hand-editable TOML invites exactly that
typo, so entries must be validated (or normalised through `norm_dep()`) at read
time rather than accepted and ignored.

### `linked_libraries`: two roles, two read paths

The field is load-bearing twice over, and the two roles read it at different
moments — which is what decides where each reads it *from*.

**Role 1 — hot-reload scope (import-time).** `_get_tracking_scopes()`
(`core/registry/base.py:861`) turns each entry into a module prefix and hands it
to `add_managed_module(module, scopes)`, which **snapshots** the list into
`_module_scope_prefixes[module_name]` (`registry/dependency_graph.py:226`) and
builds the reverse-dependency graph from it, once. This runs inside module
registration, so it cannot do a file read — it must come off the identity.

**Role 2 — marketplace gating (UI-time).** Three functions in
`haybale_marketplace/library_manager.py` drive four gates:

| function | gates |
| --- | --- |
| `get_installed_dependents` (`:758`) | uninstall/disable — "3 libraries depend on this" |
| `get_missing_dependencies` (`:790`) | **enable** — refuses when a dep is absent |
| `get_missing_dependencies_for_package` (`:770`) | **install** — refuses when a dep is absent |

Called from `library_browser_editor.py:528` and
`library_overview_editor.py:404,407,545`. None of these run at import time, so
**they read `haybale.toml` live**, like every other rendered field. Install
gating necessarily reads the *marketstall row* instead — the library is not on
disk yet, which is exactly why the row carries a verbatim copy.

The split is the point: gating is correct immediately after an edit, while
hot-reload keeps its honest reload requirement.

*Why the identity copy goes stale.* The identity object is held by reference —
non-frozen dataclass, stored in the watcher's `folder_mappings` — so mutating it
at runtime is possible, but it only affects modules registered *afterwards*.
Everything already in the graph keeps the old scopes. A mid-session edit would
appear to work and silently not.

*Normalisation differs between the two roles, and must not.*
`get_missing_dependencies_for_package` normalises with
`self._norm(d.split(".")[0])`, tolerating a hyphen; `_get_tracking_scopes`
appends `dep + "."` verbatim, so `"haybale-studio"` yields a prefix matching no
module and the scope is silently dead. One field, two regimes — validate at read
time (see "Reading it at import").

So the value is consumed at *module-registration* time, not at file-change time.
The identity object itself is held by reference — non-frozen dataclass, stored in
the watcher's `folder_mappings` — so mutating it at runtime is possible, but it
only affects modules registered *afterwards*. Everything already in the graph
keeps the old scopes. A mid-session edit would therefore appear to work and
silently not.

#### The watcher refreshes it in development

Each library owns its **own** `FileWatcher`, constructed in `BaseLibrary.__init__`
(`core/library/base.py:53`) and rooted at `self.identity.folder_path` — the only
construction site in the codebase. Each carries its own `watchdog.Observer` and
its own `LibraryFileHandler`, started when
`enforce_file_watching or identity.file_watcher`.

`haybale.toml` sits inside that watch root, and `_attach_to_registries` already
registers a root fallback over `identity.folder_path`
(`base.py:239-244`). So a library running with `file_watcher=True` is **already
receiving events for this file** — they are dropped only by the
`endswith(".py")` filter in `on_modified`/`on_created`
(`file_watcher.py:120-137`).

Therefore: when a `haybale.toml` write lands inside a watched library, re-read
it and refresh that library's identity, then re-register its modules so
`_get_tracking_scopes` runs again against the new value. Scoped to the one
library, debounced by the existing per-file timer, and reusing the routing that
already resolves a path to `(library_identity, registry)`.

This closes the stale-scope hole for exactly the population that suffers from
it: libraries under active development, which are also the only ones that never
reach the wizard's evict-and-rescan. A `haybale.toml` edit is a metadata change,
not a code change — so this refreshes the identity and re-derives scopes; it
does not need the full module-reload path a `.py` edit takes.

Three details the implementation must respect:

- **The identity is shared by reference.** The handler holds the same
  `LibraryIdentity` object stored in `folder_mappings` and `root_fallbacks`
  (`file_watcher.py:58`, `:85`), so mutating its fields in place is what makes
  the refresh visible — but it also means the refresh runs on the watchdog
  thread, mutating an object other threads read. Mutate under the handler's
  existing `_lock`, or rebuild and re-register.
- **Editors write atomically.** `on_created` already downgrades a CREATE for a
  known file to MODIFIED, and `on_moved` treats `foo.tmp → foo` as MODIFIED —
  a TOML write must be admitted through the same paths, not just `on_modified`.
- **A malformed edit must not kill the library.** Unlike the import-time read,
  this one is mid-session: log and keep the previous values rather than raising,
  since the author is mid-keystroke and will save again.

Production libraries (`file_watcher=False`) are unaffected — they read
`haybale.toml` once at import, which is all they need.

#### Who writes it

Scaffold seeds it; the share wizard maintains it; **the edit modal does not**.
The write rule follows from role 1 alone — roles 2 and 3 pick up a file edit on
the next read and would be fine either way. In development the watcher above
narrows even that gap.

*Why the wizard suffices.* `_hot_swap_bumped_libraries()`
(`haybale_share/_flow/_state.py:270`, now on the archive branch) already evicts
and rescans as the flow's last act — `registry.remove_library(lib_id)`, then
`scan_for_libraries()` and `enable_all_libraries()`. A rescan re-runs
`@library(...)`, producing a fresh identity, and re-registration re-enters
`_on_creation` → `_get_tracking_scopes` → `add_managed_module`. The scope graph
is rebuilt rather than left stale — and the wizard performs it already. It is
the refresh path for *published* libraries; the watcher above covers development
ones.

*Why the scaffold must seed it.* The eviction path only covers libraries being
bumped, so a library developed but never shared keeps whatever it was scaffolded
with. Left empty that breaks **both** roles: hot-reload scope is wrong for
exactly the population that uses hot-reload, and — worse because it is
user-visible — the marketplace reports no dependents on uninstall and no missing
deps on enable, silently permitting an uninstall that breaks other libraries.
`haywire init` knows which libraries it is wiring together, so it writes the
initial list; the wizard's drift detector corrects it from then on.

Two properties of the existing eviction to preserve: it is **best-effort** (a
library not currently enabled is skipped, not an error), and it iterates
`plan.current` — only *bumped* libraries. Lockstep publishing means every barn
library bumps together today, so writing `linked_libraries` for a library the
wizard is not bumping would leave its scopes stale. A constraint to keep, not a
bug to fix.

*Rejected:* having the modal itself trigger an evict-and-rescan for the edited
library. With the watcher in place there is nothing left for it to do — a modal
write to `haybale.toml` is a file write like any other, and a development
library picks it up through the path above. Making the modal drive a reload
directly would duplicate that, and would put an "applies after reload"
affordance on one field of an otherwise reload-free dialog.

The residue is honest and small: on a library with `file_watcher=False`, a
`linked_libraries` edit updates gating immediately and hot-reload scope at the
next import. That population does not hot-reload, so the lag has no observable
effect.

### Rendering reads the file, never the identity

**The library detail editor does not touch `LibraryIdentity`.** Two sources, one
field set:

| library state | rendered from |
| --- | --- |
| not installed | the `Haybale` row in the project's `[[caches]]` |
| installed | `haybale.toml`, parsed off `identity.folder_path` |

Going through the identity would buy nothing and cost the design's whole
premise: the identity is only as fresh as the last import, so a modal edit would
write the file and the renderer would keep showing the pre-edit value until
something re-imported. That is the same staleness `METADATA` had, with a shorter
cache. Reading the file at the point of use is what makes "write it, see it"
true.

It is always reachable: `folder_path` is set by the decorator from
`inspect.getfile()`, so anything the registry knows about — installed, heap,
enabled or disabled — has a directory to read from.

Because the row is a verbatim copy of `haybale.toml` plus generated coordinates,
both branches carry identical keys with identical meanings, and the overview's
`if installed_lib: … else: …` field-by-field branching
(`library_overview_editor.py:312-324`) collapses into one path. The
consolidation attempted this with a shared base class and only got the *names*
to line up; sharing the file format achieves it properly.

*Implementation note:* the overview re-renders on every panel redraw, so the
reader wants a small read-through cache keyed on `(path, mtime)` — a `stat` per
render is fine, a parse per render is waste.

### `LibraryIdentity` after this

Seven fields. Four from the decorator, three from `haybale.toml`:

```python
@dataclass
class LibraryIdentity:
    id: str = ""                 # decorator — needed before any file read
    folder_path: str = ""        # decorator — where haybale.toml lives
    module_name: str = ""        # decorator
    file_watcher: bool = False   # decorator

    label: str = ""                            # haybale.toml
    linked_libraries: list[str] = field(...)   # haybale.toml
    on_reload: str = "none"                    # haybale.toml
```

`linked_libraries` is there for the import-time hot-reload role only (above).
`label` is there because ~20 framework call sites *mention* a library in passing
— log lines, error detail rows, DI dumps, the skin factory, `docs/extract.py` —
and a logger inside the registry cannot do a file read per line.

`on_reload` is there because the post-change prompt must survive eviction (see
below).

Every other field is ignored by the identity: `description`, `authors`, `tags`,
`os`, the four `*_url`s, `version`, `notes`, `[deprecated]`, and both path
fields are read from `haybale.toml` at the point of use.

`LibraryMetadata` is dropped — with nothing renderable left on the identity, the
shared base has nothing to share.

`on_reload` **must** stay on the identity — verified 2026-08-09 against every
reader. Two consume it: the share flow's hot-swap (`_state.py:316`) and
`_hints_for_library()` (`library_manager.py:312`), which drives the
post-install/update/uninstall prompt. The second settles it, per its own
docstring: it runs *"after it's been evicted"*, when the library's files may
already be gone — so a `haybale.toml` read would fail exactly when the hint is
needed most. The marketstall row cannot substitute either, since an uninstall
targets an installed library that may have no row at all (heap, folder,
editable).

## Lifecycle — where the data is at each moment

### 1. Scaffold (`haywire init` / studio scaffold)

Writes `haybale.toml` with `name`, `id`, `label` filled from the author's
answers. **`linked_libraries` is seeded here** — the scaffold knows which
libraries it is wiring together, and this is the only chance to get hot-reload
scope right before the first publish (see the `linked_libraries` section above).
Everything else starts empty.

Writes `pyproject.toml` with `dependencies` and the packaging machinery; the
generated `[project]` fields are written once here so the package is installable
before its first publish.

### 2. Edit (studio, any time)

The resurrected edit modal writes `haybale.toml` and nothing else. No `uv sync`,
no registry reload, no reinstall — the next read is the new value.

`version` is displayed read-only: **the share wizard is the bump machinery**, so
a version the modal could edit would be a version no tag corresponds to.
`name` and `id` are read-only for the same class of reason — a rename breaks
saved graphs and every consumer's `install_spec` — and stay so until the
rename-wizard lands (see Settled).

`examples_path` / `tests_path` accept anything. A path that does not exist on
disk is not an error here, because it is not yet a problem for anyone: it
becomes one only at publish, when the row would point at nothing. All folder
checking happens in one place, at preflight (stage 5).

### 3. Read (runtime, installed or heap)

Two distinct readers, and conflating them is the mistake this design exists to
avoid.

*The loader*, at import, takes only what the identity needs — `label` and
`linked_libraries` — from `haybale.toml` in the package directory. Identical path
for a heap (editable, in `barn/`) and an installed wheel: both have the file next
to `__init__.py`. `importlib.metadata` is no longer consulted at all.

*Everything else*, at the point of use, reads `haybale.toml` directly off
`identity.folder_path` — the marketplace overview, the gating functions, any
future consumer of a descriptive field. Never through the identity, which would
reintroduce import-time staleness (see "Rendering reads the file").

### 4. Read (marketplace, not installed)

There is no library on disk, so the overview renders the marketstall row from
the project's `[[caches]]`. Note this is a *local* read: `refresh()` fetches
subscribed feeds periodically and writes the rows into
`<project>/.haywire/marketplace.toml`; opening a detail view does no network
call. The exception is the `notes` page, fetched on demand through
`HostProvider` and separately cached.

Because the row is a verbatim copy of `haybale.toml` plus generated coordinates,
this branch and stage 3's carry the same keys with the same meanings — one
renderer, no per-field branching.

#### Rendering the Docs / Examples links

`collect_overview_links()` builds `(label, href)` pairs by resolving each
declared path against a host provider — `tree_url` for a trailing slash,
`blob_url` otherwise. `tests_path` is deliberately not surfaced
(framework-maintainer metadata). The links are **web URLs into the publishing
repo at the published tag**, not local paths.

The link row changes with `docs_path`'s removal:

| label | from | destination |
| --- | --- | --- |
| Source | `origin` | repository home |
| Documentation | `documentation_url` | **rendered HTML docs site** |
| Notes | `notes` | one Markdown page, `blob_url` |
| Examples | `examples_path` | the project's examples |

Two fixes here. **`documentation_url` gets surfaced** — it is already in the
table, already generated into `[project.urls] Documentation`, and today renders
nowhere, so a library's actual HTML documentation site was unreachable from the
overview. And the old **"Docs" link pointed at a source tree**: `docs_path`
ended in `/`, so `link_form` chose `tree_url` and the link opened a directory
listing of `nodes/`, `widgets/`, `__init__.py`. `notes` is a file, so it links
as a `blob`.

With `origin` and `version` in `haybale.toml`, resolution needs three inputs the
library always has — `origin`, `tag_for(version)`, and the declared path — so it
works from a row *or* from the file:

| library | resolved from |
| --- | --- |
| has a marketstall row | the row (`origin` + ref from `install_spec`) |
| installed, no row (heap, folder, editable) | its own `haybale.toml` |

The second case is why `origin` stays in the file. Previously
`collect_overview_links(marketplace_pkg)` took only the row, so a library
installed as a heap or barn folder rendered **no Examples link at all** even
though it declared `examples_path` — `_lookup_marketplace_pkg()` searches
`[[caches]]` by distribution name and returns `None` for anything never
published through a marketstall.

Returning `None` rather than guessing stays the rule: a missing `origin` or an
unresolvable host yields no link. A wrong URL is worse than none — the
implementation this replaced guessed `main`/`master` and 404'd silently.

Host resolution consults `origin_provider` first, so a self-hosted forge renders
links on a consumer's machine with no local config (see `origin_provider`
above).

**A local library opens the directory, not a URL.** For a heap or barn library
the project root is on disk, so the declared project-relative path names a real
directory — and examples are meant to be *run*, not read about. Prefer the local
form whenever the path resolves locally; fall back to the web link otherwise.
`fetch_overview()` already sets this precedent, checking `local.is_dir()` /
`local.is_file()` before reaching for a URL.

### 5. Share — preflight

The only place folder checks and cross-file agreement are verified. Four
checks, each emitting a `PreconditionFailure` with `kind="act"` and a `fix_id`,
in the shape `strip_os` and `add_origin` already established.

**`sync_pyproject`** — `pyproject.toml`'s generated fields disagree with
`haybale.toml`. There is **no per-field source choice**: `haybale.toml` wins,
always. Offering a direction would imply `pyproject.toml` might legitimately be
canon, which is the thing this design denies. The existing gate already draws
exactly this line — `DepDrift` auto-applies `decorator_missing` because "there
is nothing to decide", and offers `unused_declarations` because removing one is
a judgement. Derived data belongs in the first category; nobody is asked whether
to overwrite a build artifact.

The fix is therefore a *notification with an apply button*, not a negotiation:
it must render which fields differ and what they will become, then regenerate
`[project]` from `haybale.toml`. The value is telling the author their pyproject
hand-edit is about to be discarded **before** the point of no return rather than
after the push. Publish would regenerate regardless; the check makes it not a
surprise.

> If the blunt form proves annoying in practice, the fallback is per-field
> *direction* — take haybale's value (default), or lift pyproject's value **into**
> `haybale.toml` and then regenerate. That still leaves one canon and never
> admits "pyproject stays different". Build the simple version first.

**`clear_examples_path` / `set_examples_path`** (and the `tests_path` pair) — a
declared path that does not exist on disk. The fix writes the correction back to
`haybale.toml`, so the repair persists rather than being re-prompted next
publish. This is why the edit modal does not validate paths: one checker, at the
only moment the answer matters.

**`id` mismatch** — the decorator's `id` and the TOML's disagree. No auto-fix:
the decorator is never written (see the rule above), so the remedy is an author
edit and a reload.

**Project root ≠ git root** — blocks the publish, no inline fix, message points
at the CLI. See "The project root must be the git root": the remedy is
restructuring a repository, not editing a field.

Note this makes preflight-with-fixes a *writing* stage. That is already the
established shape — `_PRECONDITION_FIXES` handlers write and run on user action
between preflight passes — and it matters for stage 6's invariant: the fixes are
part of finalizing `haybale.toml`, not part of generation.

### 6. Share — publish

In order:

Two phases, and the boundary between them is the load-bearing invariant:
**nothing generates until `haybale.toml` is final.**

*Phase A — finalize `haybale.toml`.* Every write to it happens here, and only
here:

1. Write `version` — the wizard's bump. PEP 440, no `v`.
2. Write `origin` — read fresh from the git remote (`ssh_to_https`, `.git`
   stripped). Regenerated every publish, so a fork corrects itself on its first.
   Write `origin_provider` alongside it, from the `resolve_host()` call
   preflight already made — the two are one decision and must not disagree.
3. Write `linked_libraries` — the drift detector's provably-missing entries,
   auto-applied (reported, never offered; see `DepDrift`).
4. Any preflight fixes from stage 5 already landed, before this ran.

*Phase B — generate from it.* Everything downstream reads the finalized file and
writes nothing back to it:

1. Regenerate `[project]` and `[project.urls]` from `haybale.toml`,
   comment-preserving, canonical ordering, remove-the-key rather than
   write-empty so absent keeps meaning "unset".
2. Build the marketstall row: copy the 14 (`origin` among them now — Phase A
   already wrote it), generate the 6, read `require` from
   `[project] dependencies`.
3. Commit, tag `tag_for(version)`, push. `install_spec` is tag-pinned here and
   only here — a standalone `write_marketstall()` call floats to the current
   branch (see `.insights/project_git_url_publishing_traps.md`).

The phase split is what makes the data flow one-directional. `haybale.toml` is
the only input to generation, with `[project] dependencies` the single documented
exception (`require`).

### 7. Consume — install from a marketstall

The consumer reads `os` from the row to gate installation *before* installing,
resolves `notes`/`examples_path`/`tests_path` through
`resolve_row_path()` → `HostProvider`, and installs via `install_spec`. After
install, the library's own `haybale.toml` arrives in the wheel and becomes the
runtime source — same values the row advertised, now local.

## Consequences

- **No reinstall for a metadata edit.** The reason for the whole change.
- **The edit modal returns.** Metadata editing leaves the Share wizard; the
  wizard's `edit` screen is removed and `STEPS` returns to four.
- **The decorator becomes read-only to tooling.** `decorator_io`'s three regex
  writers lose every caller, and with them the quote-sensitivity bug class.
  `read_decorator` (AST) survives — it still reads `id` for the mismatch check.
- **`LibraryIdentity` shrinks to seven fields** — `id`, `folder_path`,
  `module_name`, `file_watcher` from the decorator; `label`,
  `linked_libraries` and `on_reload` from `haybale.toml`. It carries nothing renderable, so
  `LibraryMetadata` is dropped: with nothing left to share, the base class has
  no purpose.
- **The library detail editor stops reading `LibraryIdentity` entirely** — a row
  when not installed, `haybale.toml` off `folder_path` when installed. The
  overview's per-field `if installed_lib: … else: …` branching collapses, which
  the consolidation's shared base class never actually achieved.
- **Marketplace dependency gating becomes live.** `get_installed_dependents`,
  `get_missing_dependencies` and `get_missing_dependencies_for_package` read
  `haybale.toml` (or the row, pre-install) rather than a snapshot, so an edit is
  reflected without a reload.
- **A library can locate itself.** `origin` + `origin_provider` +
  `tag_for(version)` + a declared path is enough to build a URL, so Docs and
  Examples links render for heap, folder and editable installs that have no
  marketstall row — where they previously rendered nothing at all.
- **Self-hosted forges work for consumers.** The hostname→provider mapping
  travels with the library instead of living only in the publisher's
  `~/.haywire/config.toml`, fixing a class of library whose links were broken
  for everyone except the one person who could not see it. Requires
  host-parameterised providers as a prerequisite.
- **`docs_path` is deleted and `notes` takes its slot.** The farmhand derives
  its remote coordinate from `install_spec` + module name; an installed library
  reads `folder_path / "docs"` and never needed the field. `notes` names one
  human-readable Markdown file in the package dir, so `fetch_overview()` stops
  guessing `OVERVIEW.md`/`QUICKREF.md` and a page named anything else becomes
  reachable.
- **`documentation_url` finally renders**, and the "Docs" link stops opening a
  source-tree listing.
- **A library can announce its own retirement.** `[deprecated]` carries `since`,
  `reason` and an optional `successor`, surfaces as a badge and a banner, and
  gates nothing. It also projects into the `Development Status :: 7 - Inactive`
  classifier, the only deprecation signal the packaging ecosystem has.
- **`tag_for(version)` becomes the single definition of the tag convention**,
  replacing `f"v{...}"` re-encoded in `steps/commit.py:35`, `:60`, and inside
  `install_spec`. `version` itself stays PEP 440.
- **The per-library watcher gains one file type.** `LibraryFileHandler`'s
  `.py`-only filter widens to admit `haybale.toml`, refreshing that library's
  identity and re-deriving its hot-reload scopes. Scoped, debounced, and routed
  by machinery that already exists — no new watcher, no new thread. Development
  libraries only; production ones read the file once at import.
- **`distmeta.py` leaves the runtime path entirely.** With no migration window
  (clean slate), nothing reads distribution metadata for descriptive fields —
  there is no old-wheel fallback to keep it alive. Keep the module only if a
  publish-time cross-check wants it; its header-parsing (the
  `Author`/`Author-email` split, comma-joined `Keywords`, `Project-URL` shape)
  was verified against a real wheel and is expensive to re-derive, so delete the
  call sites before deleting the file.
- **No rename path until the follow-up wizard lands.** `name` and `id` are
  read-only everywhere; renaming a library is unsupported in the interim.
- **`pyproject.toml` becomes partly generated.** Enforced by preflight rather
  than by convention.
- **Author URLs exist only in Haywire's own metadata.** They ship in the wheel
  and reach the marketstall, but never appear in PEP 621 fields.

## Settled by investigation, 2026-08-09

**The wheel carries `haybale.toml`. Verified, not assumed.** Built
`haybale-testing` with a `haybale.toml` in its package dir and unzipped the
result: the file is present at `haybale_testing/haybale.toml`, with no
`include`, no `force-include`, no config change. `packages = ["haybale_testing"]`
declares the *directory*, and hatchling's default selection inside a declared
package is everything not VCS-ignored.

The v0.0.26 `force-include` worry does not apply: that mechanism **relocates** a
tree (`src/haywire/_baked_docs` → `haywire/docs`), which has a source path, a
destination path, and two chances to be wrong. `haybale.toml` keeps its own name
and location inside an already-declared package, so that bug class is
unreachable.

Stronger evidence still: every barn library **already** ships `OVERVIEW.md`,
`QUICKREF.md` and a whole `docs/` tree from inside its package directory — 49
non-`.py` files in `haybale-testing` alone, all present in the wheel. This also
disposes of the gitignore trap: if an unanchored ignore pattern were swallowing
files in package dirs, `OVERVIEW.md` would already be missing for consumers.

*Residual caveat:* this works because hatchling's default is
include-everything-in-the-package. A third-party library setting an explicit
`include`/`exclude` under `[tool.hatch.build.targets.wheel]` could still exclude
it. None of the ten in-tree libraries do — and it is another reason the loader
raises on a missing file rather than degrading quietly.

**Import-time reading is safe and mostly built.** See "Reading it at import"
above: `read_toml()` exists, `toml` is already a hard dependency, there is no
import cycle, and a raise is contained by the registry's existing per-library
`try/except`. Resolved in favour of raising.

**`linked_libraries` needs no new refresh machinery, only a widened filter.**
Two existing paths cover it: the share wizard's evict-and-rescan for published
libraries, and each library's own `FileWatcher` — already rooted at
`identity.folder_path`, already receiving events for `haybale.toml`, dropping
them only at the `.py` filter — for development ones. The scaffold seeds the
initial value. Resolved in favour of scaffold-seeded, wizard-maintained,
watcher-refreshed, modal-excluded.

**`name` in two files.** `[project] name` is regenerated from `haybale.name` on
every publish, so they cannot disagree at publish time, and `sync_pyproject`
reports it beforehand if they have drifted.

**The rename-wizard is a follow-up, not a prerequisite.** `name` and `id` are
read-only in the edit modal — changing `id` orphans every saved graph
referencing `<id>.NodeName`, and changing `name` breaks the `install_spec` every
existing consumer holds. Renaming is therefore *deferred until this change has
landed*: the wizard is built afterwards, against `haybale.toml` as its edit
surface rather than against the decorator it would otherwise have had to rewrite.
Shipping without it means no supported rename path in the interim, accepted
knowingly.

**No migration path for already-published libraries.** Breaking changes are
still acceptable at this stage — clean slate. The loader does **not** fall back
to `distmeta` for old wheels, and no dual-read window is built. This removes the
last reason to keep `distmeta.py` on the runtime path (see Consequences).

## No open questions

Every question this note opened is settled, including the three that were still
marked as of 2026-08-09:

- **Project root vs git root** — preflight requires them to coincide; failure
  points at the CLI. `haywire init` already guarantees it (`git init` at the
  project dir, git a hard prerequisite), so the check guards only
  hand-assembled or relocated projects. See "The project root must be the git
  root".
- **Local examples** — open the directory, not a URL, whenever the path resolves
  locally.
- **`on_reload` on the identity** — verified: it stays. `_hints_for_library()`
  runs after eviction, so a file read would fail exactly when the hint matters.

The remaining dependency is external: an implementation plan, and its ordering
against the rollback already done.

## Traps

- `.insights/project_git_url_publishing_traps.md` — `install_spec` and doc paths
  are tag-pinned *only* through `SharePipeline`; a standalone
  `write_marketstall()` call floats to the current branch. The gitignore half of
  this trap is settled above: package-dir files provably reach consumers.
- `.insights/project_library_dependencies_use_package_names.md` — `linked_libraries`
  takes Python **module** names, not pip names. Still live, and more exposed
  under a hand-editable TOML: `_get_tracking_scopes` appends the value verbatim,
  so a hyphen yields a silently dead scope.
- `.insights/project_stale_version_diagnosis.md` — site-packages vs pyproject vs
  `uv.lock` disagreeing is the class of bug this change exists to remove from
  the descriptive fields; it still applies to `version`.
- `.insights/feedback_barn_module_reload_test_trap.md` — this touches every barn
  `__init__.py`; tests importing barn classes at module top level go stale after
  `importlib.reload`.

`.insights/project_farmhand_docs_bake.md` is **no longer relevant** — it
describes `force-include`, a mechanism this design does not use. Keeping it
listed would misdirect whoever implements the packaging step.

## Task: correct the examples/tests path-scope misconception

**Done, 2026-08-09** — landed with stage 8. `docs_path` was deleted outright
rather than corrected (see "`notes` replaces `docs_path`"), and the remaining
library-relative wording lives only in the superseded ADR 0024, where it is
correct as a historical record.

Originally deferred deliberately. These edits were **not** applied on 2026-08-09 because the
25-commit consolidation is scheduled to be rolled back, and edits landing on
soon-to-be-reset code would be lost or produce merge noise. Line numbers below
are as of commit `53108922`; re-locate by symbol name if they have moved.

The misconception: `examples_path` and `tests_path` were documented and
implemented as **library-relative**, with the publisher prefixing them with the
library's own repo-relative path. They are **project-relative** — from the
directory holding `.haywire/`. `docs_path` is **deleted** rather than corrected
(see "`notes` replaces `docs_path`") — so where this sweep touches it, remove
rather than rewrite.

### Code

- `packages/haywire-core/src/haywire/core/publishing/marketstall.py:126-131` —
  **delete `_declared_path()`** and pass `decorator.examples_path` /
  `decorator.tests_path` through verbatim (`:148-149`). Its docstring
  ("Prefix an author-declared, library-relative path…") is the misconception
  stated outright.
- `packages/haywire-core/src/haywire/core/library/metadata.py:67-73` — the
  `examples_path` / `tests_path` docstrings say "Same trailing-slash and
  resolution rules as `docs_path`". Trailing-slash yes, **scope no**.
- `packages/haywire-core/src/haywire/core/library/decorator.py` — the `@library`
  docstring's `examples_path` line ("relative to the library directory").
- `packages/haywire-core/src/haywire/core/publishing/pipeline/fixes.py:170-180`
  and `steps/preconditions.py` — the declared-path existence check resolves
  against `lib_dir`; it must resolve against the project root.
- `scripts/generate_marketstall.py` — mirrors the same prefixing.

### Published docs

- `docs/haybale/library-canon.md:93-94` — the decorator parameter table. Replace
  "relative to the library directory" with the project-root wording, and note
  the two scopes differ.
- `docs/adr/0024-library-metadata-single-source.md:309-315` — the
  "Declared paths are checked at publish time" section. This ADR is superseded
  by this note; mark it so rather than editing it in place.

### Plans (historical — mark, do not rewrite)

`docs/superpowers/plans/2026-08-08-library-metadata-*.md`,
`2026-08-09-library-metadata-{author-migration,declared-paths}.md`, and
`internals/superpowers/2026-08-08-library-metadata-consolidation.md` all encode
the old scope. They are records of what was built, not instructions — add a
one-line superseded-by pointer at the top of each instead of correcting them.

### Tests

`tests/studio/test_share_examples.py`, `tests/share_pipeline/test_declared_paths.py`,
`tests/scripts/test_generate_marketstall.py`, `tests/marketstall/test_locate.py`
assert the prefixed form.
`test_docs_path_is_the_module_dir_relative_to_the_git_root` goes with the field
it pins; its replacement asserts the farmhand derives that coordinate from
`install_spec` instead.
