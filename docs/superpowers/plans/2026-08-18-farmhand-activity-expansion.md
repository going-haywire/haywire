# Farmhand activity tracking + UX expansion

Settled via inquisition, 2026-08-18. Unbuilt as of this writing.

## Problem (Q1)

Today's `ActivityRecord` (`packages/haywire-studio/src/haywire_studio/farmhand/activity.py`)
proves *who* called *which tool*, *when*, and *whether it succeeded* — but not
*with what* or *to what effect*. This expansion serves three goals at once:

- **Debug/reconstruction** — see actual arguments/result when an agent does
  something surprising.
- **Audit/accountability** — a durable, session-independent record of what an
  agent did.
- **Live collaboration awareness** — richer in-the-moment context for a human
  watching an agent work right now.

## Decisions

### Tracking / storage

1. **Two tiers, not one** (Q2): the existing in-memory `ActivityTracker`
   (bounded, session-scoped, serves debug + live-awareness) stays as today's
   shape; a **separate, opt-in persisted log** is layered on top for audit.
   Matches the Error ledger's existing in-memory/bounded pattern rather than
   silently turning it into an unconditional audit trail.

2. **Log-write trigger** (Q3): while persistence is on, **every** finished
   tool call is appended, unconditionally — no mutating/read-only filter.
   Filtering by call kind would need a reliable per-tool classification that
   doesn't currently exist cleanly; filtering can be done at *read* time later,
   never un-done at *write* time.

3. **Payload capture scope** (Q4): capture **both full arguments and full
   result**, not a lossy summary. Matches the existing "no per-tool opt-in to
   forget" design principle in the module docstring.

4. **Capture format** (Q16a): store **already-serialized JSON text**, not a
   live Python dict — reuse the exact `json.dumps(result, default=str)` the
   host already computes at
   [host.py:324](../../../packages/haywire-studio/src/haywire_studio/farmhand/host.py#L324)
   for `result`; do the same for `arguments`. Truncation becomes a plain
   string slice at every layer (in-memory record, persisted line, rendered
   popup).

5. **Size control** (Q5): **hard char-length truncation** on the serialized
   text, uniform across both fields and both tiers, with a
   `"...[truncated]"` marker. Confirmed via codegraph that **no
   framework-level cap exists today** on this path — `truncation_note`/
   `_DOC_CHAR_CAP`/per-tool `limit`/`offset` are all ad-hoc, tool-author-opt-in
   conventions, not a guarantee. The tracker becomes the first real backstop.

6. **No redaction** (Q6): capture verbatim, no key-name denylist. VIEW-tier
   access already exposes equivalent information by other means (Q7), so a
   redaction layer would be a per-field maintenance burden without closing a
   real new exposure.

7. **Access tier unchanged** (Q7): stays `AccessTier.VIEW` for the live editor
   and for anything gating the persisted log's (future) viewer. No new
   disclosure boundary introduced by richer payload content.

8. **Farmhand-tool read access: out of scope** (Q14): no `studio_get_activity`
   tool this round. Cross-principal visibility at farmhand-tool level raises
   its own tier questions and isn't needed for any of the three Q1 goals,
   which are all human-facing.

### Persisted audit log

9. **Format + location** (Q11): **JSONL, append-only, per-project**, under
   `<workspace>/.haywire/` — matches `studio.json`'s existing per-project
   placement rather than the global Security document (activity is
   project-scoped; auth is cross-project by design).

10. **Record shape**: each line is the full `ActivityRecord` as JSON —
    `principal`, `tool`, `started_at`, `finished_at`, `ok`, `error`, plus the
    new `arguments`/`result` text fields (§4 above).

11. **Write ordering**: one line appended per call, at `finish()` time (§2
    above) — so the file is ordered by **finish time**, not start time. Two
    concurrent calls can appear out of invocation order if the one started
    later finishes first; this mirrors the existing in-memory `_history`
    deque's behavior exactly (`activity.py:92`), not a new ordering scheme.

12. **Toggle + destination unified into one field** (Q26): a single
    `log_path: setting[STRING]` — **empty string = logging off**; any
    non-empty value is treated as a **relative path from the workspace
    root**, and its presence alone turns logging on. No separate boolean.

13. **Settings placement** (Q12, Q29): a new `FrameworkSettings` schema (not
    `LibrarySettings` — confirmed via codegraph that `FrameworkSettings` is
    explicitly scoped to haywire-core/haywire-studio internals, which is
    where `activity.py` lives) at
    `packages/haywire-studio/src/haywire_studio/farmhand/settings.py`,
    namespaced `"farmhand.activity"`:

    ```python
    class ActivitySettings(FrameworkSettings, namespace="farmhand.activity"):
        history_size = setting[INT](50, label="Activity History Size", ...)
        log_path = setting[STRING]("", label="Activity Log Path", ...)
    ```

    Per-project (travels with the project, not the global Security document),
    following the same file-per-feature convention as `ExecutionSettings`,
    `MinimapSettings`, etc.

14. **History size setting** (Q28): `history_size` replaces the `HISTORY_LIMIT`
    module constant, bounding the **in-memory `_history` deque only**. Does
    **not** cap or rotate the persisted JSONL file — that file's unbounded
    growth is an accepted, explicitly out-of-scope gap (see Scope below).

### UX — running/recent list (`ActivityEditor`)

15. **Expand-in-place, not a new dialog/editor** (Q9): clicking a row toggles
    an inline expansion, extending the existing pattern where `record.error`
    already gets its own line only when present
    ([activity_editor.py:146-147](../../../barn/haybale-studio/haybale_studio/editors/activity_editor.py#L146)).

16. **Per-row expand state lives on the editor instance** (Q10): e.g. a
    `set[int]` of expanded record tokens. This amends the module docstring's
    current "holds no state of its own" claim — that was true only because
    nothing was worth remembering yet. Full collapse-on-every-signal (the
    alternative) was rejected: `FarmhandActivity` fires on both call start
    *and* finish, so an expanded row would snap shut almost immediately
    during any active agent session.

17. **Detail trigger: an icon-only button, always present** (Q18, Q23):
    every row (running or finished) carries the button regardless of whether
    there's a result yet. Sized to match the existing status icons
    (`play_arrow`/`check`/`close`, `text-xs` — [activity_editor.py:137](../../../barn/haybale-studio/haybale_studio/editors/activity_editor.py#L137)),
    never larger than those.

18. **Detail surface: `haywire.ui.components.popup.Popup`** (user-specified),
    not a new dialog. Precedent: `EdgeInfoPopup` in
    `barn/haybale-graph-editor/.../connection_info_popup.py`.

    - **Centered on screen**, not positioned at the click (Q21) — unlike
      `EdgeInfoPopup`'s canvas-contextual placement, a list row has no
      spatial meaning worth preserving, and avoids off-screen risk for rows
      near the bottom of a scrolled list.
    - **Fixed size**, not `"auto"` (Q22) — two JSON viewers need a stable
      height to manage their own internal scroll (confirmed:
      `svelte-jsoneditor` scrolls internally when its container height is
      bounded); the truncation cap (§5) already bounds the worst case.
      Originally ~800×500px for a side-by-side layout; changed to
      ~560×640px (narrower, taller) when the layout below flipped to
      stacked.
    - **Bare chrome** — just the two viewers, no repeated header info (Q20);
      the triggering row is still visible in the list.

19. **Two `ui.json_editor` instances**, labeled "Arguments" / "Result".
    Originally **side-by-side** (Q19, user override of the initial
    single-combined-object recommendation); changed to **stacked
    (Arguments over Result)** in a later session at the user's request —
    same two-instance, two-label decision, layout axis flipped.

    - **Read-only mode** (`{'mode': 'view'}` or equivalent) (Q17) — matches
      the editor's own stated purpose ("supplementary output you glance at,
      not a surface you edit in" —
      [activity_editor.py:5](../../../barn/haybale-studio/haybale_studio/editors/activity_editor.py#L5)).
      Requires `json.loads()` on the stored text at popup-open time only —
      storage stays text everywhere else (§4).

20. **Clear button, mirroring `LogEditor`** (Q27): clears the in-memory
    `_history` deque only. Explicitly does **not**:
    - touch `_running` (clearing an in-flight call would strand it with no
      way to ever see it finish);
    - truncate the persisted JSONL file — an audit trail a UI button can
      casually erase isn't an audit trail, defeating the whole point of §9-13.

### Explicitly deferred / out of scope this round (Q15, Q24, Q30)

- Any query/filter/search over the live list or the persisted log.
- A viewer for the persisted log — this round ships recording only; reading
  back is manual (`jq`/`cat`) until a future round builds one.
- Any tier above VIEW, anywhere in this feature.
- Farmhand-tool read access to activity data (own future feature, own
  questions about cross-principal disclosure).
- Type-aware payload elision — plain char-length truncation only.
- Global (cross-project) persistence toggle or log location.
- **Retention/rotation for the persisted JSONL file.** It grows forever as
  specified. Explicitly accepted as a known gap, not an oversight — worth
  revisiting if it becomes an operational problem.
- Changing the entry point (the "Agent activity" account-menu panel) or the
  newest-first, 30-row-capped list shape.

## Facts confirmed via codegraph during this session (not decisions)

- No framework-level size cap exists on farmhand tool call arguments/results
  today; only ad-hoc per-tool pagination conventions
  (`truncation_note`, `limit`/`offset`, underscore-key filtering).
- `haywire.ui.components.popup.Popup` is an established, heavily-used
  component (43 call sites) with a working detail-popup precedent
  (`EdgeInfoPopup`).
- No `FarmhandSettings` schema exists; the `require_auth`-style toggle
  referenced in prior memory actually lives in the Security document, a
  different mechanism entirely.
- `FrameworkSettings` is explicitly documented as scoped to
  haywire-core/haywire-studio internals (not barn libraries) — the correct
  base class for this feature, since `activity.py` lives in `haywire-studio`
  proper.
- `LogEditor._clear()` is in-memory-only (no disk persistence to worry about
  in that precedent) — informed but did not fully determine Q27, since this
  feature's persisted tier has no analog in `LogEditor`.

## Open follow-up (not blocking, flagged during the session)

- **Glossary**: "Agent Activity" / `ActivityRecord` / the persisted audit log
  aren't yet defined in `docs/reference/glossary.md`. Worth a short entry once
  this lands, so the in-memory/persisted split has canonical names. No
  conflict found with existing terms — just a gap, not raised as a
  contradiction requiring immediate resolution.
