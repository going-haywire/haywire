---
status: draft
doc_template: guide
scope: How to write and structure a page in this mkdocs site — front matter, templates, nav wiring, and linking to live source
see-also:
  - glossary.md
  - design-guide.md
---

# Writing a doc page

This page describes how to write a page *in this mkdocs site* (`docs/`, built by `mkdocs.yml` at the repo root). It is not about `uv run haywire docs` — that command generates per-library README/OVERVIEW/QUICKREF files from code and is a separate, deterministic pipeline (see `docs/superpowers/plans/2026-07-29-*`).

## 1. Where a page lives

Directory meaning, per the comment above `nav:` in `mkdocs.yml`:

- `components/<area>/<area>-canon.md` — extension-point authoring guides (nodes, types, ports, adapters, settings, widgets, themes, editors, panels, states, farmhands).
- `architecture/<area>/<area>-arch.md` — framework internals (execution pipeline, library system, hot-reload, settings resolution, session/state, studio).
- `haybale/` — the library/package/marketplace story (authoring, packaging, distribution).
- `guides/` — cross-component patterns and worked examples that don't belong to a single extension point.
- `reference/` — shared truth: glossary, design guide, file-format specs.
- `welcome/` — the three perspective entry points (user / advanced / core).
- `archive/` — historical record, excluded from normal maintenance.

Filename convention follows the directory: `<area>-canon.md` under `components/`, `<area>-arch.md` under `architecture/`. Reference and guide pages just use a descriptive slug (`ports.md`, `design-guide.md`).

A new page must also be added to the `nav:` tree in `mkdocs.yml` — a file that exists under `docs/` but isn't listed there won't appear in the site navigation.

## 2. Front matter

Every substantive page opens with YAML front matter:

```yaml
---
status: draft
doc_template: canonical-example
scope: One-line description of what this page covers
see-also:
  - ../../guides/ports.md
  - ../../reference/glossary.md
---
```

- **`status`** — one of `placeholder` (not written yet), `draft` (written, not reviewed), `accepted` / `stable` / `current` (settled), `superseded-in-part by ADR-NNNN` (partially replaced — cite the ADR). Placeholder pages should say so plainly in the body too (see `execution-arch.md` for the pattern) rather than presenting empty sections as finished.

- **`doc_template`** — names the shape this page follows, so a reader (or writer, or agent) can tell what's expected before reading the body. Existing values and where to copy the shape from:
  
  | Template            | Shape                                                                                     | Example                               |
  | ------------------- | ----------------------------------------------------------------------------------------- | ------------------------------------- |
  | `canonical-example` | extension-point authoring guide: what it solves → how it fits → worked example → pitfalls | `components/nodes/node-canon.md`      |
  | `system-reference`  | framework-internals deep dive: overview → lifecycle → key types → extension points        | `architecture/design/design-arch.md`  |
  | `guide`             | cross-cutting how-to, not tied to one extension point                                     | `guides/panels.md`                    |
  | `impl-spec`         | implementation-level spec (data flow, file formats, internal contracts)                   | `haybale/metadata-flow.md`            |
  | `reference`         | lookup table / field-by-field spec                                                        | `reference/files/marketstall-toml.md` |
  | `perspective-index` | landing page for one of the three welcome perspectives                                    | `welcome/advanced/index.md`           |
  | `design-guide`      | the one design-tokens page                                                                | `reference/design-guide.md`           |
  | `glossary`          | the one term-definitions page                                                             | `reference/glossary.md`               |
  
  Don't invent a new `doc_template` value casually — check whether an existing one already fits before adding one, since each value is a promise about structure that other pages of that type keep.

- **`scope`** — one sentence, third person, says what the page covers (and implicitly, what it doesn't). Used to disambiguate at a glance when several pages touch related territory.

- **`see-also`** — relative paths (not bare doc_template names) to related pages. Keep it short — the pages a reader would plausibly bounce to next, not everything tangentially related.

## 3. Linking to live source code

Two different mechanisms exist for pulling code into a doc page. Use the right one for the job — don't hand-copy a snippet that either mechanism already covers, since a hand-copy silently drifts from the code the moment it changes.

### 3a. Section-embed (`pymdownx.snippets`) — for code you want to *show verbatim and keep in sync*

`pymdownx.snippets` supports two forms of embed. Which one to use depends on where the source file lives:

- **`barn/` code (component/library examples — nodes, widgets, settings, etc.) → line-range form.** Barn example files are small and stable; a line range is quick to write and read without needing to annotate the source.
- **Everything else (`packages/`, framework internals) → tag form.** Framework files change shape more often — lines get inserted above an untagged range — so pin the region with an explicit tag instead of numbers that can silently drift out of alignment.

**Line-range form**, `path:start:end` (1-indexed !!!, inclusive):

```text
--8<-- "barn/haybale-example/haybale_example/nodes/math_op.py:12:20"
```

No markup needed in the source file — just point at the lines. Because a barn example can still be edited later, re-check the range after any edit to the source file (see §3d) — nothing fails the build if the numbers drift, it will just silently embed the wrong lines.

**Tag form**, `path:tag` — mark a region in the source file with matched start/end tags:

```python
# --8<-- [start:startup-state-wiring]
def configure(...):
    ...
# --8<-- [end:startup-state-wiring]
```

then reference it by tag name:

```python
--8<-- "packages/haywire-core/src/haywire/core/di/config.py:startup-state-wiring"
```

The tag moves with the code it wraps, and `check_paths: true` in `mkdocs.yml` fails the build if the tag is ever deleted — so drift is caught loudly instead of silently. Tag names must be unique per file; pick a name that describes the concept being shown (`startup-state-wiring`), not the file it's in.

At build time mkdocs inlines either form as a real, syntax-highlighted code block. This is the mechanism to reach for whenever a canon/arch page shows a "here's what this looks like in practice" example — see `node-canon.md`, `setting-canon.md`, `haybale-canon.md` for the existing (tag-based, pre-dating this split) pattern.

#### Library components (nodes, types, panels, …) must also print the registry key

A library component isn't just its source location — at runtime it's addressed by its **registry key**, `<library_name>:<component_type>:<registry_id>` (built by `reg_key()`; see `reference/glossary.md`). 

> **Worked example — linking to a node's source**
> 
> ```python
> --8<-- "barn/haybale-example/haybale_example/nodes/math_op.py:11:20"
> ```
>
> from: `MathOP` — registry_key: `haybale-example:node:MathOP`

which renders as:

> ```python
> @node(
>     label="Math Operation",
>     search_tags=["math", "value", "single", "basic", "operation"],
>     deprecation_warning="This node will be moved to the math library",
>     menu="examples/math/basic",
>     node_type=NodeType.DATA,
> )
> class MathOP(BaseNode):
> ```
>
> from `MathOP` — registry_key: `haybale-example:node:MathOP`


Assemble the key from source:`<library_name>:<component_type>:<class_name>`, unless the component's decorator sets an explicit `registry_id`/`id`, in which case that replaces `<class_name>`:

1. **`<library_name>`** — the library's **distribution (pip package) name**, e.g. `haybale-example` (`name` inside `haybale.toml` or more simply the folder name right below barn/).
2. **`<component_type>`** — the fixed string for the kind of component (`node`, `type`, `panel`, `widget`, `setting`, `adapter`, `editor`, `theme`, `skin`, `state`; see `NODE`/`WIDGET`/`TYPE`/… in `packages/haywire-core/src/haywire/core/library/utils.py`).
3. **`<class_name-or-registry_id>`** — check the component's own decorator (`@node(...)`, `@panel(...)`, etc.) for an explicit `registry_id=`` kwarg. If present, use it. If absent, it defaults to the class name.

Grep the package's `pyproject.toml` and the component's decorator rather than trusting memory — a library's distribution name and a component's `registry_id=` are each set in exactly one place, and neither has to match what its surrounding path or class name suggests.

### 3b. Plain markdown links — for pointing at a file/symbol without embedding it

Source files live outside `docs_dir`, so they can't be linked as markdown doc-links (mkdocs' strict mode treats any link target that isn't a file under `docs/` as unresolved). Point at source with plain text — a code-styled path, optionally a GitHub blob URL with a `#L<n>` anchor when the repo is browsed there:

```markdown
See `packages/haywire-core/src/haywire/core/execution/execution_context.py` for the full class.
```

Use this for "go look at this" pointers where reproducing the code in the doc would be redundant or would go stale (whole files, or things too large to embed a section of). Prefer 3a whenever the point is to show the reader actual code inline — it's the only one of the two that mkdocs can verify.

### 3c. Cross-doc links

Link between doc pages with relative `.md` paths (as in `see-also`, and inline: `[reference/glossary](../../reference/glossary.md)`). Don't link to a doc page's built URL — the site can be reorganized under mkdocs' instant-navigation without breaking relative links, but a hardcoded `site_url` path would need every reference updated by hand.

### 3d. Verify, don't eyeball, the relative path

Two mistakes are easy to make and easy to miss by inspection:

- Copying a `../../` depth from a page that lives *two* directories under `docs/` (e.g. `components/nodes/`) into a page that lives *one* directory under `docs/` (e.g. `reference/`) — the correct prefix depends on where **this** file sits, not on what nearby pages happen to use.
- Linking to something outside `docs_dir` (`mkdocs.yml`, anything under `packages/`, `barn/`, `tests/`) as if it were a doc-link. It never resolves, no matter the `../` count — only §3a/§3b's plain-text or snippet forms apply there.

Both are invisible from reading the Markdown — the link *looks* fine. The only reliable check is building the site:

```sh
uv run mkdocs build --strict
```

`check_paths: true` (for snippet embeds) and strict mode (for doc-links) turn a bad path into a build failure instead of a silent dead link or blank block. Run this after adding or editing any link, not just at the end of a larger change.

## 4. Style

- Second person for the reader, present tense: "you define a Python class... you decorate it..." (see `node-canon.md` §1).
- Lead each page with what it solves before how it works — a reader deciding whether to keep reading needs the "why" first.
- ASCII-art diagrams (` ```text ` fenced) are used freely for lifecycle/flow shapes where a picture beats a paragraph — see `node-canon.md` §2 for the shape.
- Keep `docs/` self-consistent with the `.insights/` traps list and ADRs it documents — if behavior changes, update the doc in the same change, not as a follow-up.
