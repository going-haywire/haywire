---
status: draft
doc_template: reference
scope: pyproject.toml in a haybale — which fields haywire reads, which it generates, and the build config that carries haybale.toml into the wheel
see-also:
  - haybale-toml.md
  - marketstall-toml.md
  - ../../haybale/metadata-flow.md
  - ../../haybale/haybale-canon.md
---

# `pyproject.toml`

**Location:** the library directory root — `barn/haybale-core/pyproject.toml`.

**Owner:** split. `dependencies`, the entry point and the build machinery are
authored; the descriptive `[project]` fields are generated from
[`haybale.toml`](haybale-toml.md) at publish.

Haywire reads exactly two things from this file: `[project] dependencies` (for
the framework requirement it projects into a marketstall row) and
`[project] version` (owned by the release machinery). Everything else in
`[project]` exists so the wheel is a well-formed PEP 621 package — PyPI, `uv`
and `pip` read those fields, and Haywire does not.

## The file

```toml
[project]
# ── generated from haybale.toml at publish; do not hand-edit ────────────────
# Preflight reports a hand-edit as drift before the point of no return, and
# publishing regenerates the block regardless.
name = "haybale-core"                                    # from haybale.name
description = "Fundamental components for haywire graphs" # from haybale.description
keywords = ["haywire", "node-editor", "core"]            # from haybale.tags
# Names only — PEP 621 authors carry {name, email} and have no URL slot, so an
# author's url stays in haybale.toml and reaches the marketstall row instead.
authors = [{ name = "maybites" }, { name = "cansik" }]
# Emitted only when haybale.toml has a [deprecated] block. PEP 621 has no
# deprecation field and unknown [project] keys are a spec violation, so this
# trove classifier is the ecosystem's only signal.
classifiers = ["Development Status :: 7 - Inactive"]

# ── owned by the release machinery ──────────────────────────────────────────
# The one field that flows the other way: the share wizard bumps it here and
# writes the same value into haybale.toml, and the marketstall row reads it
# from this file. PEP 440 — no "v".
version = "0.0.40"

# ── authored here ───────────────────────────────────────────────────────────
requires-python = ">=3.12"
readme = "README.md"
license = { text = "MIT" }

# CANON. The only descriptive-adjacent field this file owns outright.
# Pip requirements — NOT haybale load order, which is `linked_libraries` in
# haybale.toml. The haywire-core floor here is projected into the marketstall
# row's `require`.
dependencies = [
    "haywire-core>=0.0.39",
    "haybale-core>=0.0.39",
    "nicegui>=3.12.1",
]

[project.optional-dependencies]
dev = ["pytest>=7.0.0", "ruff>=0.1.0"]

# ── generated from haybale.toml at publish ──────────────────────────────────
[project.urls]
Homepage      = "https://github.com/going-haywire/haywire"   # from homepage_url
Documentation = "https://going-haywire.github.io/haywire/"   # from documentation_url
Issues        = "https://github.com/going-haywire/haywire/issues"  # from issues_url
Source        = "https://github.com/going-haywire/haywire"   # from origin

# ── the line that makes the library discoverable ────────────────────────────
# The key is the entry-point name: it only has to be unique within the group,
# and need not match the library `id`. The value is <module>:<class>.
[project.entry-points."haywire.libraries"]
core = "haybale_core:Library"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

# Declares the package DIRECTORY, so everything inside it that is not
# VCS-ignored reaches the wheel — haybale.toml, NOTES.md, OVERVIEW.md,
# QUICKREF.md and the whole docs/ tree. No `force-include` is needed, and an
# explicit include/exclude here risks dropping haybale.toml, without which the
# library cannot load.
[tool.hatch.build.targets.wheel]
packages = ["haybale_core"]

[tool.hatch.build.targets.sdist]
include = ["haybale_core/", "README.md"]
```

## What haywire reads

| Field | Read by | For |
| --- | --- | --- |
| `dependencies` | `haywire_core_requirement()` | The marketstall row's `require` — the framework floor, projected |
| `version` | The marketstall writer | The row's `version`, and the git tag `v<version>` |
| `[project.entry-points."haywire.libraries"]` | `LibraryDiscovery` | Finding the `Library` class at startup |

Nothing else in `[project]` is read back by the studio.

## What haywire generates

Regenerated from [`haybale.toml`](haybale-toml.md) during publish, after that
file is final:

| `[project]` key | From `haybale.toml` |
| --- | --- |
| `name` | `name` |
| `description` | `description` |
| `keywords` | `tags` |
| `authors` | `[[authors]]` — names only |
| `classifiers` | presence of `[deprecated]` |
| `urls.Homepage` | `homepage_url` |
| `urls.Documentation` | `documentation_url` |
| `urls.Issues` | `issues_url` |
| `urls.Source` | `origin` |

Generation is comment-preserving and removes a key rather than writing an empty
value, so absent keeps meaning "unset" and a generated file stays
indistinguishable from a hand-written one.

There is no per-field source choice: `haybale.toml` wins. Preflight's
`sync_pyproject` check renders which fields differ and what they will become,
then regenerates. The value is learning that a pyproject hand-edit is about to
be discarded *before* the push rather than after.

Implemented in `haywire.core.publishing.generate` — `pyproject_drift()` reports,
`sync_pyproject_from_haybale()` writes.

## `dependencies` vs `linked_libraries`

The two most-confused fields in a haybale.

| | `[project] dependencies` | `linked_libraries` |
| --- | --- | --- |
| Lives in | `pyproject.toml` | [`haybale.toml`](haybale-toml.md) |
| Names | Pip **distribution** names — `haybale-core` | Python **module** names — `haybale_core` |
| Means | Install this package first | Track this library's classes for hot-reload; gate enable/uninstall |
| Consumed by | `uv` / `pip` | The hot-reload scope tracker and the library browser |

A library normally declares both, spelled differently. The share wizard's drift
detector maintains each against a static scan of the source.

## The entry point

```toml
[project.entry-points."haywire.libraries"]
core = "haybale_core:Library"
```

The framework calls `importlib.metadata.entry_points(group='haywire.libraries')`
at startup; every installed haybale appears there. The value is
`<python_module>:<class_name>` — a dotted module path, a colon, then the
attribute to import. It points at the **class**, not an instance; the framework
instantiates it.

Multiple libraries in one distribution are supported by listing multiple
entries:

```toml
[project.entry-points."haywire.libraries"]
lib_a = "my_package.lib_a:Library"
lib_b = "my_package.lib_b:Library"
```

## Build config

`packages = ["haybale_core"]` declares the package directory. Hatchling's
default selection inside a declared package is everything not VCS-ignored, so
`haybale.toml` — and `NOTES.md`, `OVERVIEW.md`, `QUICKREF.md`, the `docs/` tree
— reach the wheel with no further configuration.

A build that omits `haybale.toml` produces a library that cannot load: it is
read from disk at runtime, and its absence raises at decoration time. Setting an
explicit `include`/`exclude` under `[tool.hatch.build.targets.wheel]` is the one
way to cause that, and is why nothing in-tree does.

Note the asymmetry with `README.md`: it sits at the *library* root, outside the
package directory, so it does **not** ship in the wheel. That is deliberate —
see the [README/OVERVIEW split](../../haybale/haybale-canon.md).
