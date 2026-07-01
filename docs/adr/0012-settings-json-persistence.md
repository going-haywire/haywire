# Persist settings as JSON; serialize each tier value through its IType at the disk edge

**Status:** Accepted.

The settings registry used to persist both tiers as TOML, writing the raw Python value per key with `toml.dump`. This ADR records swapping that persistence to **JSON** and serializing each tier value through its declared IType's `to_dict`/`from_dict` **at the disk edge**, so complex ITypes (`COLOR`, the six `VEC*` types) round-trip losslessly instead of being mangled or silently reset. This is plan **P3** of the settings↔DataField unification arc (canonical-key → tier-collapse → **TOML→JSON** → single-cell → promotion-as-direction).

## Context — TOML wrote raw values, and complex types lost their type

TOML was originally chosen for hand-editability. But `LibrarySettings` already declares typed fields — `setting[COLOR]`, `setting[VEC2I]`, `setting[VEC3F]` — and the registry persisted them by writing `sv.value` raw via `toml.dump`. Two failures followed:

- A `Vec_` value survived a save only by accident: the framework `Vec2i`/`Vec3f`/… classes subclass `list`, so `toml.dump` happened to emit them as TOML arrays — but on read the value came back as a plain `list`, having lost its `Vec2i` type entirely.
- Worse, `COLOR` and every `VEC*` IType inherited the unoverridden base `PrimitiveType.from_dict` stub (`packages/haywire-core/src/haywire/core/types/base.py:128`), which **discards the supplied data and returns the type default**. `INT`/`FLOAT`/`STRING`/`BOOL` override it; `COLOR` (`barn/builtin/types/color.py`) and the `VEC*` types (`vectors.py`) did not. Any code path routing a saved color or vector through `from_dict` got `"#ffffff"` / the zero vector back, not the user's value.

The format change is real, not cosmetic: TOML could not express the IType serialization contract the rest of the system (graph JSON) already uses.

## Decision

Persist both tiers as JSON (`~/.haywire/settings.json`, `<workspace>/.haywire/settings.json`) and serialize each tier value through its declared IType's `to_dict`/`from_dict` **at the disk edge**:

- Fix the broken overrides first: `COLOR.from_dict`/`to_dict` and a `_VecSerialize` mixin on the six `VEC*` types now round-trip their value (`color.py`, `vectors.py`), with a dedicated round-trip test (`tests/core/types/test_itype_roundtrip.py`).
- A single IType-keyed seam lives in `SettingsRegistry`: `_value_to_jsonable(name, value)` wraps the value in the setting's `_type` and stores `IType(value).to_dict()`; `_value_from_jsonable(name, raw)` rehydrates it via `IType.from_dict(raw)`. Unknown keys (auto-defined, no code definition) and untyped scalars pass through unchanged (`registry.py`).
- `save_to_json` writes the workspace tier as nested JSON, each value in its `to_dict` form; `load_from_json` parses JSON and rehydrates each `{"value": …}` entry through the seam before it lands in the tier (`save_to_json`/`load_from_json` + `_rehydrate_entry`). The flatten/auto-define machinery (`_flatten_toml`, `_process_entry`) is reused unchanged — only the parse and the value rehydration differ. `import toml` is gone from `registry.py`.
- **Hard cutover, no migration:** pre-existing `.toml` files are not read or converted.

## Deliberate scoping vs DECISIONS.md §D

`settings-datafield-unification-DECISIONS.md` §D specifies that the *tier itself* stores the `to_dict` form and that `resolve()` returns the **raw serialized dict**, with the consuming field rehydrating via `from_dict`. This ADR deliberately serializes **at the disk edge instead**: the in-memory tier keeps the live Python value (a `str`, a `Vec2i`, …) and `resolve()` is unchanged.

The reason is the "green between plans" rule. Making `resolve()` return raw dicts now would break every current reader — `setting.__get__`, the panel widgets, the `persistent_setting.__set__` echo-guard (`value == self.__get__(...)`) — until a rehydration hook lands. That hook is P4 work (the value moving into a `DataField` cell). Disk-edge serialization fixes the real fragility (the on-disk format) completely while keeping every commit green. The §D tier-value-form lands in **P4** alongside the cell and its field-rehydration step.

## Consequences

- **Lossless complex types.** `COLOR`, `VEC2I`, `VEC3F`, … now persist and rehydrate through the same `to_dict`/`from_dict` pair that graph JSON uses — one serialization contract across the system, rather than two.
- **Breaking, no migration.** Settings now persist as JSON; the old `~/.haywire/settings.toml` and `<workspace>/.haywire/settings.toml` are **not** read or migrated. Users lose hand-edited global settings unless they re-enter them. (No `CHANGELOG.md` exists in the repo, so this ADR is the ship notice.)
- **Legacy override table still loads.** A `{ "override": true, "value": X }` table left over from a pre-collapse file still parses — `_parse_config_dict` reads it as a plain *set* of `X` and ignores the `override` flag (carried over from [ADR 0011](0011-collapse-settings-tiers.md)).
- **Supersedes** the "TOML for hand-editability" choice documented in `architecture/settings/settings-arch.md` (rewritten to the JSON format + disk-edge serialization section §8.3).
- This is P3 of the settings↔DataField unification arc; P4 (single cell + tier-stored `to_dict` form per §D) and P5 (promotion-as-direction) build on the IType seam introduced here.
