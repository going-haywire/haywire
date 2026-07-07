---
status: accepted
see-also: ADR-0014, ADR-0020
---

# watch() is a shadow() preset; read_only and same-bag mirroring are deleted

**Context.** `setting()` carried a `read_only: bool` parameter, set by the `watch()` factory (`shadow()` left it `False`). It forked behavior through five independent call sites: the write guard (`__set__` raised `AttributeError`), promotion eligibility (`eligible_promotion_directions()` forced outlet-only regardless of `promotable=`), panel rendering (`render_utils.py` branched to a plain-label row instead of a real widget), dirty-chrome suppression (`_has_local_opinion()` hard-excluded read-only fields), and serialization (`to_dict()`/`from_dict()` skipped them outright). Auditing actual usage found `watch()` had exactly one call site in the entire codebase — 8 demo fields in `haybale-testing`'s `SettingsNode`, built to exercise the UI test harness. No production library used it.

Separately, `_in_bag_mirror_adapters` (same-bag sibling mirroring — a field mirroring another field on the SAME `Settings` subclass, as opposed to a registered `LibrarySettings`/`FrameworkSettings` global on a different class) was found to have been introduced as a `fix:` commit closing a gap in the generic `mirrors=` type signature, not for any real driving use case. Also zero production usage.

**Decision.**

- **`read_only` is deleted** as an independent descriptor concept. `watch(src, **kwargs)` is now pure sugar: `setting(mirrors=src, ui_state=UiState.DISABLED, promotable=Promotable.OUTLET, **kwargs)`. `shadow(src, **kwargs)` is unchanged in effect (`setting(mirrors=src, **kwargs)`).
- **The write guard is gone.** A `watch()` field is now writable via plain `setattr` — the `AttributeError` protected against a mistake no production code ever made; keeping it required a dedicated boolean flag threaded through five call sites for a guarantee nothing depended on. "Don't write to a mirror you're meant to only read" is now a naming/usage convention, same as any other field a caller shouldn't mutate directly.
- **Promotion eligibility is `promotable=` alone.** `eligible_promotion_directions()` no longer has a separate structural override for read-only-ness — `watch()` seeds `Promotable.OUTLET` itself, so the declared flag IS the eligibility. One fewer place two independent flags could disagree.
- **Panel rendering is uniform.** `watch()` fields render through the same `UiState.DISABLED` path as any other disabled field (a real, greyed-out widget) instead of a bespoke plain-label branch. This is an intentional visible UI change from the previous "label-only, no widget" rendering (introduced 2026-07-07, commit `12c1bdbd`) — DISABLED is pure structure-agnostic chrome (ADR 0020) and a mirrored value showing in a disabled widget is normal, well-understood UI, not misleading.
- **Dirty/reset chrome applies uniformly.** Since writes are legal, a `watch()` field that gets locally written now shows the same `•` dirty prefix and Reset menu item as any other mirror field. Reset is offered for every field regardless of promotability or mirror-ness (no more `read_only` gate on `offers_reset`).
- **Serialization applies uniformly.** A locally-set `watch()` field now serializes like any other mirror field; the previous unconditional exclusion is gone.
- **Same-bag mirroring is deleted.** `mirrors=` (used by both `shadow()` and `watch()`) must reference a field on a DIFFERENT class — a same-bag sibling raises `ValueError` at `__set_name__` time instead of being silently made to work via `_in_bag_mirror_adapters`. `_in_bag_mirror_adapters`, `_subscribe_in_bag_mirror`, and `_in_bag_mirror_of` are deleted along with their branches in `_cell_for`, `_subscribe_setting`, `reset`, and `cleanup`.

**Considered and rejected.**

- *Keep `read_only` as an enforced write guard, drop only the panel-rendering special case.* Rejected — the write guard was the least-motivated piece (a self-afflicted restriction easily remedied with `ui_state=DISABLED`), and keeping it while deleting the rendering special-case would leave `_read_only` alive for no consumer except `__set__` — not a meaningful simplification.
- *Derive DISABLED-implies-label-rendering as a new special case, decoupled from `read_only`.* Considered and rejected — it re-introduces a two-flags-must-agree problem (`ui_state is DISABLED` meaning "grey widget" for normal fields but "label only" for mirrors), which is exactly the class of bug this ADR removes.
- *Keep same-bag mirroring as out-of-scope / a separate follow-up.* Rejected once its motivation was audited — it is the identical "unused generality accepted by a permissive type signature" pattern as `read_only`, discovered in the same session, with zero production usage and no documented driving scenario. Bundling both deletions in one ADR was judged cleaner than two overlapping partial changes to the same file.

**Consequences.** `setting(read_only=...)` and any same-bag `mirrors=` are hard breaking changes — no deprecation shim (matches ADR 0019's precedent: "hard breaking change — no migration"). `haybale-testing/settings_node.py`'s `read_only_value` demo field (a non-mirror local field that used `read_only=True` for no structural reason — there was never a "read-only local field" concept, only "read-only mirror") is deleted outright, since nothing else in the codebase used a bare `read_only=True` local field and there is no replacement primitive for it (a locally-owned field that can't be written makes little sense — the mirror-specific rationale doesn't apply).
