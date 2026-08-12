---
name: collapse-settings-tiers
description: Settings resolution collapses from a six-case mode chain to highest-priority-set-tier-wins; SettingMode and OVERRIDE are removed
status: accepted
level: architectural
---

# Collapse the settings resolution model to highest-priority-set-wins; drop OVERRIDE / SettingMode

The settings resolver used to evaluate a six-case chain with two *strengths* per tier. Each tier value was a `SettingValue(mode, value)` where `mode ∈ {INHERIT, EXPLICIT, OVERRIDE}`: `INHERIT` meant "unset," `EXPLICIT` meant "set," and `OVERRIDE` meant "forced — beats everything below, including a per-node local value." This ADR records collapsing that model down to **highest-priority *set* tier wins**: `OVERRIDE` and the `SettingMode` enum are removed, and a tier value is now simply *set* or *unset* (`SettingValue.is_set`). This is plan **P2** of the settings↔DataField unification arc (canonical-key → **tier-collapse** → TOML→JSON → single-cell → promotion-as-direction).

## Context — the pre-P2 six-case / two-strength chain

`resolve(name, local=None)` walked six cases and returned a `source` drawn from `{'global_override', 'workspace_override', 'local', 'workspace', 'global', 'default'}`:

```text
1. global tier OVERRIDE      → forced (admin policy)
2. workspace tier OVERRIDE   → forced (workspace-wide policy)
3. local SET                 → per-node/per-instance override
4. workspace tier EXPLICIT   → workspace default (set via UI)
5. global tier EXPLICIT      → user global default (hand-edited)
6. definition default
```

The strength axis existed for exactly one capability: **an admin could *force* a value on a shared lab machine** that beat even a graph's per-node override. On disk this used an inline-table form:

```toml
[execution]
max_threads = { override = true, value = 2 }    # OVERRIDE — forced from this tier down
```

That capability was overengineered relative to its use. It introduced a second axis (strength) on top of the tier axis, doubled the resolution cases, required a special TOML syntax, and forced every consumer (`set_global(mode=…)`, the settings-status print, `SettingsTestContext.set_override`, the `LoggingConfigurator` `mode == INHERIT` branch) to reason about three states where two would do. The asymmetric "global OVERRIDE beats my local override" rule was also the least intuitive part of the model for users — a value they could not change, with no in-app explanation of why.

## Decision

Collapse the model to **highest-priority *set* tier wins**, with no forcing strength:

- `SettingValue` keeps its `value` but its three-way `mode` is replaced by a two-state `is_set` boolean, constructed via `SettingValue.unset()` / `SettingValue.of(value)` (`packages/haywire-core/src/haywire/core/settings/value.py:27,32`). Presence-with-a-value *is* the opinion; there is no strength.
- `SettingsRegistry.resolve` (`registry.py:936`) is now four cases — local-set → workspace-set → global-set → default — returning a `source` of `'local' | 'workspace' | 'global' | 'default'`. `_effective_value` (`registry.py:852`) collapses to two: workspace-set beats global-set, else unset.
- `set_global(name, value, tier=…)` loses its `mode` parameter (`registry.py:884`); a write simply marks the tier *set*. `reset_global` writes `unset()`.
- The `SettingMode` enum and its `settings/enums.py` module are deleted, and `SettingMode` is dropped from the `haywire.core.settings` exports.
- `Settings._on_field_change` adopts the **"unset tracks; set ignores"** rule (DECISIONS.md §A): when an instance holds a local override, *any* mirrored global change is suppressed — there is no OVERRIDE escape hatch that re-fires the callback. When the cell is unset the field re-resolves and the callback fires.

Below the (now-removed) force tier, the relative order of local vs workspace vs global is unchanged: old steps 3/4/5/6 become new 1/2/3/4. A graph with no OVERRIDE on disk resolves **identically** before and after this change.

## Consequences

- **Lost capability:** an admin can no longer force a value that beats per-node overrides. The workspace and global tiers are "defaults," never "forces"; the per-node local override always wins over both. This is a deliberate reversal of a documented decision, hence this ADR.
- **Forward compatibility:** a legacy `{ override = true, value = X }` TOML inline-table left over from a pre-collapse file still loads — `_parse_config_dict` reads it as a plain *set* of `X` and ignores the `override` flag (`registry.py`). `save_to_toml` now writes bare values only.
- **Simpler everywhere:** resolution drops from six cases to four; the TOML format loses its inline-table variant; every consumer reasons about set-or-unset instead of a three-way mode. `SettingsTestContext` loses `set_override` (an OVERRIDE no longer differs from a set).
- **Supersedes** the six-tier model previously documented in `architecture/settings/settings-arch.md` §1–4 (rewritten to the collapsed model).
- This is P2 of the settings↔DataField unification arc; P3 (TOML→JSON), P4 (single cell), and P5 (promotion-as-direction) build on the set-or-unset `SettingValue` and its `to_dict`/`from_dict` seam introduced here.
