---
name: deprecated-libraries-have-no-ui-surface
description: Handoff — deprecation data path lands end-to-end but no UI renders it, for a browsing catalog visitor or an existing installer
metadata:
  type: project
  status: partial
---

# Handoff: a deprecated library says so nowhere the user can see

## Why

An author can declare `[deprecated]` in `haybale.toml`, and as of this change it
travels all the way into a marketstall row and back out of a consumer's parser.
Nothing renders it. The notice reaches the consumer's disk and stops there.

The field exists to answer one question — *should I keep using this library?* —
for two audiences: someone browsing a catalog before installing, and someone who
installed it months ago. Neither is served today.

## What landed (2026-08-09)

The data path, end to end. Verified by round-tripping a real library through
`_build_entry_for_library` → `toml.dumps` → `_parse_haybale_entry`.

- `Deprecation` dataclass — `since` (required), `reason`, `successor`
  (`core/marketstall/types.py`). Frozen; `to_dict()` omits the two optional
  fields when empty.
- `Haybale.deprecated: Deprecation | None`, and `"deprecated"` **last** in
  `_TOML_FIELDS` — it serializes to a TOML table, and any bare key written after
  a table header is parsed into that table.
- `_parse_deprecation()` (`core/marketstall/parsing.py`) — lenient: a malformed
  block yields `None` rather than costing the user the whole catalog entry, for
  a library that still installs and runs.
- `_declared_deprecation()` (`core/publishing/marketstall.py`) — strict: raises
  on a block it cannot serialize, so an authoring mistake surfaces to the one
  person who can fix it instead of publishing a notice that exists locally and
  nowhere else.
- `tests/marketstall/test_deprecation.py` — 16 tests, including both strictness
  regimes and the table-ordering constraint.

`[project] classifiers` still gets `Development Status :: 7 - Inactive`
(`core/publishing/generate.py`), unchanged. That projection cannot replace the
row: it carries neither `reason` nor `successor`, and nothing in the studio
reads PyPI metadata.

## What remains — the UI

Both surfaces read `Haybale.deprecated`, which is now populated. The designed
behaviour:

| Surface | Behaviour |
| --- | --- |
| Library browser | A badge on the row |
| Library overview | A banner carrying `reason`; an Install action for `successor` when set |
| Install / enable / update | Unaffected — warn, never refuse |
| `refresh()` | Worth surfacing once for a deprecated library the user has installed |

**It gates nothing.** A deprecated library that still works still installs,
still enables, still updates. `os` remains the only field that blocks
installation. This is the constraint most likely to be violated by accident —
the natural instinct is to disable the Install button.

Two things the implementer needs that are not obvious:

- **An installed library has no row.** A heap, a barn folder, or an editable
  install may never have come from a marketstall, so the overview must fall back
  to reading `[deprecated]` from the library's own `haybale.toml` via
  `read_raw(identity.folder_path)`. This is the same split the overview already
  makes for every other descriptive field: row when not installed, file when
  installed.
- **`since` is what makes the notice actionable.** It is the version the notice
  *landed in*, so a user below it is being told something they could not have
  known. Comparing it against the installed version is what turns a static badge
  into "you are on 0.0.30; this was retired in 0.0.41".

Treat a published block as immutable — an author who changes their mind bumps a
version and removes it, rather than rewriting what consumers already fetched.

## Related, and deliberately separate

`CompatibilityWarning` (ADR 0005) is per-*component*, append-only, and checked
against **saved graphs**. This is library-wide and checked against **installed
libraries**. Different scope, different trigger; do not merge them.

## A pre-existing bug found on the way

`_build_entry_for_library` emits `label` and `description` as **character
lists** — `label = [ "D", "e", "a", "d",]` — when the values come from
`read_raw`/`read_display`.

Cause: `read_toml` returns tomlkit types, whose `String` is a `str` *subclass*,
and `toml.dumps` serializes it as a sequence of characters. Reproduced on
`master` with the deprecation work stashed, so it predates this change.

`Deprecation` sidesteps it by calling `str(...)` on every field, but the row's
other string fields do not. Worth a sweep: normalise at the `read_raw` boundary
rather than at each call site, or the next field added here inherits the same
trap.
