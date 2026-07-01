# Settings ↔ DataField Unification — Inquisition Decisions

> Running record of decisions made during the inquisition. Feeds the implementation plan.
> Companion to `settings-datafield-unification.md` (the idea).

## A. Resolution model — tiers collapsed

The 6-tier / 2-strength chain is **overengineered**. Collapse it:

- **Drop `OVERRIDE` mode entirely.** No more `{ override = true, value = ... }` inline-table
  form. `SettingMode` (INHERIT/EXPLICIT/OVERRIDE) becomes vestigial — each tier is just
  "set or not set," highest-priority-set-wins.
- **Two tiers only:** global (VST term: "user") + workspace.
- Loses the "admin forces a value on a shared lab machine" use case that motivated OVERRIDE.
  Deliberate reversal of a documented decision → **ADR-worthy**, surface at ship time.

### Resolution ladders (the `cell ?? default` model)

The chain is no longer a walk — it's **`value = cell-if-set, else default`**, where `default`
is a *computed strategy* that differs per field-kind:

| Field kind | `default` computed from | value |
|---|---|---|
| plain `setting()` | IType/descriptor literal | `cell ?? default` |
| `shadow()` | `registry.resolve(global < workspace)` | `cell ?? default` (cell = per-node override) |
| `watch()` | `registry.resolve(global < workspace)` | `default` (cell can never be set) |
| Library/Framework settings | descriptor literal | `default < global < workspace`, **no cell** |

Key insight: one mode (cell + default-strategy), not two (plain-cell vs mirror-registry).
This dissolves idea-doc cleanup **#1** (the `_registry is None` dual-mode branch) for free.

### Reactive default (shadow, when global changes)

**"Unset tracks; set ignores."**
- cell UNSET → field re-resolves to new default, fires `on_change`, re-renders widget.
- cell SET → value unchanged (override wins); **reset-to-default target moves silently** to
  the new global. Documented edge, not a bug: reset = "stop overriding, defer to current."

## B. Promotion = "field + direction" (backbone of the plan)

> **⚠️ PARTIALLY SUPERSEDED — LANDED (2026-07-01, P5 — see
> `internals/superpowers/2026-06-30-settings-promotion-as-direction.md` and `docs/adr/0014-promotion-as-direction.md`).**
> A second inquisition pass, grounded in code reads, revised two things in this section (now shipped in P5):
> - **The `config` direction is DROPPED.** Two directions only: **inlet | outlet**. Reasons (code
>   facts): an unlinked inlet *already* shows its widget (`ShowWidgetStrategy.NOT_LINKED` is the
>   inlet default, `enums.py:84`), so config's "always-on widget" is just a promoted inlet once the
>   old `show_widget=NEVER` override is removed; and the existing `as_config` factory is *pinless*
>   (`flow_type=NONE`, "Config ports are never linked", `interface.py`) — the opposite of the
>   edge-drivable widget §B imagined. An always-editable-while-linked widget would also fight the
>   §C3 spine (wiring owns the cell).
> - **Eligibility is two orthogonal flag checks, not a per-kind matrix:** `_read_only` (watch) ⇒
>   outlet-only; `direction=outlet` ⇒ `is_linked_lazy` + `on_changed→propagate`. Everything else
>   rides one mechanism (`bind_field` + the field's `on_changed`).
> - **The mirror-field cell is authoritative in the SETTING** (not bridged at the port): a tracking
>   `shadow`/`watch` keeps its own cell synced to the resolved global; the port borrows that cell.
>   "Setting oblivious" = oblivious *to ports*, not passive about value.
>
> The matrix and cell-ownership tables below are the *original* design and are kept as the historical
> record. Read the P5 plan for the landed shape.

Promotion generalizes from *setting→inlet* to **assigning a direction to a value-bearing
field**. The DataField cell is **direction-agnostic**.

### Direction-eligibility matrix

| | → inlet | → config | → outlet |
|---|---|---|---|
| plain `setting()` | ✅ | ✅ | ✅ (constant source) |
| `shadow()` | ✅ | ✅ | ✅ |
| `watch()` | ❌ | ❌ | ✅ (only direction) |

**Single governing invariant:** any field can be promoted to any direction **except a
read-only field (`watch`) can only become an outlet** (read-only ⇒ output-only).

Scope: **all three directions designed now** (not inlet-only, not design-only-build-later).

### Cell ownership per direction

- **inlet** (`show_widget=NOT_LINKED`): edge drives cell; widget hidden when linked;
  freeze-on-disconnect. ("Wiring owns the cell" is the INLET rule.)
- **config** (`show_widget=ALWAYS`): widget always on card; edge drives when linked.
- **outlet** (`show_widget=NEVER`): **source owns cell, readers observe.** No on-card widget.
  - plain→outlet: value set via properties panel; emitted as constant (re-emit on edit).
  - watch→outlet: value from registry; re-emits on registry change.

These map 1:1 onto the existing `ShowWidgetStrategy` per-direction defaults → the unification
**inherits the port system's widget-visibility rules** instead of reinventing them. This
retires idea-doc cleanup **#5** (stringly-typed widget desugaring) as a side effect.

## C. Attribute footprint verdict (answer to "which stay / re-represent")

### Retired / re-represented (field or port already carries it)
| `setting()` attr | New home |
|---|---|
| `_default` | field default-strategy (computed) |
| `_type` | `DataPort.type_cls` / the IType |
| `_min` `_max` `_choices` `_widget` | IType `widget_key`/`widget_config` + per-port override (idea #5) |
| `_stored` | **DROPPED** — `StoreStrategy` on the port covers "don't persist"; zero uses found |
| `_promoted_port_id` | **GONE** — promotion is the field *being* a port |
| `_setting_key` | one canonical key always (idea #2) |
| `_registry is None` dual-mode | **GONE** (idea #1) |
| `_validator` | **DROPPED** — zero production uses; constraints → `IType.field_class.set_value` |

### Stays — genuinely settings-specific
| attr | reason |
|---|---|
| `_mirror_key` / `_mirror_descriptor` | shadow/watch default-strategy; no port equivalent |
| `_read_only` | watch flag; also the outlet-only promotion guard |
| `_label` `_description` `_category`/`section` `_order` | display; transfer to port on promotion |
| `_on_change` | ports have `on_change` too; transfers |
| `_metadata` | **KEPT on all paths** (node + library + framework). Free-form per-field escape hatch; only place arbitrary attribution survives the setting→port identity (DataPort has none). Lives on descriptor, not port — no DataPort change. Sole current consumer: debug log-level courier (registry path). |

### Evidence gathered
- `validator=`: 0 production uses (only testbed demo + `registry.define()` pass-through + self-tests).
- `stored=False`: 0 uses anywhere.
- `metadata=`: 1 consumer — per-library log-level setting (`library/base.py:150` sets,
  `debug/configurator.py:76` reads `module_name`). Registry `define()` path only; never a node
  setting. **Kept as courier** (carries `module_name` from LibraryIdentity → configurator,
  which has only key+descriptor at apply-time). Value slot can't hold it — that's the editable log level.

## C2. Field ↔ port binding & serialization (settled)

**Setting is canonical and oblivious.** The `DataField` cell always lives on the settings
bag (per-node, created at `NodeData.__init__` — bags exist before any port). The setting
descriptor does NOT know a port exists. The **port reaches over** to share the cell.

**Promoted port = `promoted=True` flag + id.** The port id **equals the setting key**
(`setting__<accessor>__<field>`, which is the canonical key from idea #2). The `promoted`
flag + id is the *entire* binding signal — **no `_promoted_port_id` descriptor flag**
(kills cleanup #4), **no decode step** (id already is the key).

**Binding is by shared reference, not value copy.** On load the promoted port binds its
`_data` to the *same object* as the setting's cell. Consequence: **load-order is a non-issue** —
whenever the settings block restores the value, it writes the shared object the port already
points at. (This is the decisive argument for reference-sharing over copying.)

**Serialization shape (minimal):**
- A promoted port serializes as `{ kwargs: { id, port_type, promoted: true, ...display } }` —
  **NO `recipe`** (type derived from the setting at `id` on load) and **NO `field_data`**
  (the port has no value of its own; it borrows the cell).
- The **value round-trips through the settings block only** (`{accessor: {field: value}}`).
- The ports block is **value-less for promoted ports**. → `StoreStrategy.NEVER` bolt-on
  **retires naturally**: nothing to store, rather than "told not to store."

**`from_spec` gains a promoted branch:** sees `promoted: true` → skips type resolution
(derive `type_cls` from setting), skips `_data` creation (bind by ref to setting cell),
skips `field_data` restore (value came via settings block). No throwaway field created.

**Type identity:** not serialized, so no mismatch possible — the port's type IS the setting's
IType by derivation. (Chosen over assert-and-fail; nothing to assert if nothing's stored.)

**Load-order verification deferred to plan-time:** confirm where node-level `from_dict`
sequences settings-bag restore vs port restore (not found in this pass — `user_data.py:231`
is the `store` container, not the orchestrator). Reference-binding makes correctness
order-independent, but the exact call site must be located when building.

## C3. The cell-mutation spine (resolves a whole class of edge cases)

> **No structural action ever resets the cell.** Wiring, unwiring, promoting, demoting,
> changing direction — none touch the value. They change only *who can write it* and *how
> it's viewed*. The value changes only by: (a) user edit via widget/panel, (b) an edge driving
> it while linked, (c) explicit reset-to-default. That is the entire value-mutation surface.

Consequences derived from the spine:
- **Demote keeps the cell value** (the edge-driven/frozen value stays; recovery = reset-to-default).
- **Only two verbs: `promote(direction)` and `demote`.** No in-place "redirect." Redirect =
  demote + re-promote; the cell survives both. Avoids flipping edge polarity in place.
  Eligibility matrix (incl. watch→outlet-only) is re-checked at re-promote time.

## C4. watch→outlet emit — the `is_linked_lazy` port flag

> **⚠️ SCOPE REVISED — LANDED (2026-07-01, P5 — see the P5 plan + `docs/adr/0014-promotion-as-direction.md`).** Two refinements from
> a code-grounded pass:
> - **`is_linked_lazy` applies to EVERY promoted outlet (plain included), not just `watch→outlet`.**
>   The real discriminator is not "mirror field" but "setting-driven ⇒ written outside the scheduler
>   frame" — true of *all* promoted outlets (widget / registry / edge writes; never worker `out()`;
>   no "apply between frames" mechanism exists). So `direction=outlet` sets the flag unconditionally.
> - **The flag alone is INERT — it needs a trigger.** "Force lazy at link, no new propagation path"
>   (below) is insufficient: verified `pipe.py`/`port.py` — a lazy pipe pulls only after its sink is
>   marked dirty via `propagate()`, and an out-of-frame change triggers nothing. The mechanism has
>   **two parts**: (1) `is_linked_lazy` makes the deferred pull safe; (2) the port subscribes its
>   shared field's `DataField.on_changed → self._pipes.propagate()` (installed in `bind_field` for
>   outlets), which is what *fires* the pull. The setting stays oblivious to the port — it writes its
>   cell; the port reacts to its cell. The rest of this section (freshness contract, idle-liveness
>   out of scope) stands unchanged.

Problem: a `watch→outlet`'s value changes on a **registry** edit, outside any execution frame.
The settings system sets the *field*, never the port/pipe — so an **eager** edge would never
update (nothing calls `_pipes.propagate()`). Verified against `pipe.py`: a **lazy** edge's
`pull()` reads the outlet's *current* value at the consumer's execution time ("always-latest").

**Decision: new general-purpose port flag `is_linked_lazy`.** When a port has it set, the port
forces every linked edge to `is_lazy=True` at link time. A `watch→outlet` sets it. Result: the
consumer pulls the live registry value on its **next execution** — no out-of-frame propagation,
no re-entrancy, no settings→scheduler coupling.

- **Freshness contract:** downstream is "fresh as of the consumer's next execution." Idle
  liveness (rippling a global edit to an idle downstream *immediately*) is **out of scope** —
  globals don't change mid-frame.
- **Reusable:** `is_linked_lazy` is not watch-specific. Any outlet set out-of-band (not during
  `out()` in execution) can use it. `watch→outlet` is just its first customer.
- Chosen over reusing `edge_wrapper.is_lazy` at build time (explicit port-level contract,
  discoverable/serializable, covers re-link) and over option C (registry marks consumers dirty).

## C5. Hot-reload — no new requirements

Hot-reload **serialize→reload→deserialize**s the node (same path as save/load:
`serialize_recipe()` → `importlib.reload` → `NodeWrapper.build()` → `edges.rebuild()`,
hot-reload-arch §3.3/§5.1). The node instance is brand new after reload; the held cell value
survives **because and only because** it serializes via the settings block and re-applies —
already covered by C2. The promoted port re-borrows the new bag's new cell via the same
`from_spec` promoted-branch. No surviving references to manage.

**Mid-drive reload is a non-question.** Hot-reload is a *development-time* event: the graph is
marked dirty, **execution stops**, the graph recompiles, execution restarts clean. Any
in-flight driven value is re-established on the next frame from scratch. Loss is negligible by
design — no forced re-pull, no special-casing. → "hot-reload × held cell" closes as: covered
by the round-trip; execution-restart makes mid-drive loss irrelevant.

## D. Persistence — TOML → JSON cutover (settled)

- Settings tiers move **TOML → JSON**. Premise verified: `LibrarySettings` already declares
  `setting[VEC2I]`/`setting[VEC3F]`/`setting[COLOR]` (`testing.py`), and `save_to_toml`
  (registry.py:659-668) stores `sv.value` raw via `toml.dump` — fragile for multi-component
  types, especially nested inside the OVERRIDE `{override, value}` inline-table. The format
  change is **real, not cosmetic**.
- Both tiers JSON: `~/.haywire/settings.json` + `<ws>/.haywire/settings.json`.
- **Hard cutover, no migration.** Existing `.toml` dropped; surface at ship time. ADR-worthy.

### Tier value form (decision A)
- A tier stores the IType's **`to_dict` output** (JSON-able dict/scalar). `resolve()` returns
  that **raw serialized form**; the consuming **field rehydrates via `from_dict`** when
  materializing into its cell. **Same `to_dict`/`from_dict` contract as graph JSON** — "one
  serialization contract everywhere."
- Registry stays a **dumb JSON store**: no type-registry coupling, no eager materialization,
  no live IType instances pinned in tiers. (Rejected B: eager materialize — buys read speed
  settings don't need, adds registry→type-registry dependency.)
- **Code impact:** `save_to_toml`/`load_from_toml` → `save_to_json`/`load_from_json` (~6
  sites, registry.py:325/645). The OVERRIDE-wrapping branch (registry.py:663-666) and
  `SettingMode` are **deleted** (subsumed by the A-tier collapse). Write loop reduces to "for
  each set tier value, write `to_dict`-form under the nested key."

```json
// ~/.haywire/settings.json
{ "testing": { "default_offset": { "x": 1, "y": 2 } } }
```

## E. ADRs — write as the FINAL plan task, only once everything has landed

Three decisions clear the bar (hard-to-reverse + surprising + real trade-off) and each
**supersedes a documented prior decision**, so a future engineer would otherwise "fix" them
back. **Do not write them up-front** — an ADR records a decision that was *built*. They are
the **last task of the implementation plan**, authored against landed code (cite real
file/line evidence like the existing ADRs). Number by scanning `docs/adr/` at write time.

- **ADR-A — Collapse settings tiers; drop `OVERRIDE`/`SettingMode`.** Supersedes
  settings-arch §1-4 (the "five claims, one wins" motivation + admin-force-on-lab-machine).
  Trade-off: lost admin-force capability vs. collapsing the 6-case chain to `cell ?? default`.
- **ADR-B — Settings persistence TOML → JSON, hard cutover, no migration.** Supersedes the
  deliberate "TOML for hand-editability" choice. Trade-off: drops existing on-disk settings;
  relies on "JSON stays hand-editable" (VS Code precedent). Flag the data drop at ship time.
- **ADR-C — Promotion is "field + direction"; a setting and a port are one cell, two views.**
  Supersedes the Plan 3 two-cell + read-tier-bridge design. Trade-off: single shared cell +
  freeze-on-disconnect vs. the two-cell model's "preserve the typed-earlier value" safety.

## Open / not yet interrogated
- watch→outlet re-emit lifecycle (registry change → outlet fire → downstream).
- Serialization of the cell: graph JSON shape for a promoted vs unpromoted node setting.
- Demotion edge cases per direction (demote-from-outlet, demote-from-config).
- Hot-reload interaction with the held cell + reactive default.
- `_setting_key` → "one canonical key" (idea #2): exact key scheme, collision with port `id`.
- ADRs to write: (1) tier collapse / drop OVERRIDE, (2) TOML→JSON cutover, (3) promotion-as-direction.
