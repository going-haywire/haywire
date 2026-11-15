# ASIDE slot and the Questionnaire: design and slices

Settled in an inquisition on 2026-11-15 (questions Q0–Q25 below). Each slice's last task
marks its row in *Status* done, with commit, date and deviations.

## Problem

When a feature needs a live check in the studio, the agent has no structured way to tell
the user what to test or to get the results back; today both travel as free text in the
terminal. A **Questionnaire** gives the two a structured exchange channel: the agent posts
it through Farmhand, the user works through it in the studio beside the canvas, and the
agent reads back the **Findings** to fix what failed.

It needs a place to live next to the canvas without taking the EDIT slot, so the studio
gets a fifth slot, **ASIDE**: a role slot any editor may use, the Questionnaire editor
being its first user.

## Decisions

### Part 1: the ASIDE slot (`haywire-core`)

| # | Area | Decision |
|---|---|---|
| 0A | Docs drift | `studio-arch.md` §2.1 still names the slots Left/Right/Main/Bottom; it moves to the `SlotName` vocabulary in the same edit that adds the ASIDE row. |
| 1B | What the slot is | A general-purpose role slot, like the other four; any editor may declare it as `default_slot`. |
| 3B | Name | `SlotName.ASIDE`, value `"aside"`, label "Aside". |
| 4A | Placement | Full height: its own column between the EDIT/INFO column (`main_col`) and CONTEXT, with its own divider. INFO stays under EDIT only. |
| 5A | Toggle | Only ASIDE gets a top-bar toggle (right side, before the presence row; right-panel icon; lit while open). Closed, ASIDE disappears entirely: no rail. The other slots keep their fold gestures. |
| — | Slot class | A `TabSlot` with its tab bar on top; supports every `OpenBehavior`. |
| 6A | Reveal | A `Reveal` into a closed ASIDE opens it, like every other slot. Whether something publishes a `Reveal` is that feature's policy. |
| 7B | No ASIDE editor | The toggle is always shown; an empty ASIDE opens to the "No editor" placeholder. |
| 8A | Persistence | The uniform slot snapshot under `workspace_state.json["aside"]`, saved by the existing *Save workspace layout* button. Closed by default; default width about 360px. |
| — | Active slot / keymap | ASIDE takes part like EDIT and INFO: its tab bar is its slot bar, lit when active; `HW_SLOT_ASIDE` joins the keymap JS. |
| 15A | Badges while closed | While ASIDE is closed, the top bar draws each ASIDE binding's existing `draw_tab(orientation="vertical")` next to the toggle; a click reveals that binding. ASIDE's `_refresh_bar` repaints this group too, so an editor's `wrapper.refresh_tab_bar()` keeps working unchanged. No new API. |

### Part 2: the Questionnaire (`haybale-studio`)

| # | Area | Decision |
|---|---|---|
| 1B/2B | First user | The Questionnaire editor, default slot ASIDE. Both parts are one plan, ASIDE first. |
| 9B | Channel | Farmhand tools; the studio stores questionnaires and findings as JSON under `library_storage_dir(__name__)` / `questionnaires/`. No repository paths. |
| 10A | Home | `haybale-studio` for now: the editor in `editors/`, the tools in `farmhands/`. |
| 11–12 | Format | SurveyJS JSON, a subset, drawn by **our own NiceGUI renderer** (no SurveyJS runtime). Types: `boolean`, `radiogroup`, `checkbox`, `dropdown`, `text` (by `inputType`), `comment`, `rating`, `ranking`, `html`, `panel`, `pages`. Conditions: `visibleIf` / `enableIf` / `requiredIf` with a small grammar: `{name}` references, `= != < > <= >=`, `and / or / not`, `empty / notempty`, `contains / anyof`. No functions, calculated values, piping or triggers. See ADR 0083. |
| 12 | Validation | `post_questionnaire` validates against the subset and rejects anything unsupported, with an error naming the element and property and linking the format page. |
| 13B | `check` type | Our own element: `{"type": "check", "name", "title", "do", "expect"}`. The renderer draws do/expect, the verdict (pass / fail / blocked / skip) and a note field shown on fail. Its answer is `{"verdict": …, "note": …}`. |
| — | Renderer | A dispatch table from `type` to builder, using `hui` wrappers wherever they exist (mapping below). `html` through `ui.html(..., sanitize=True)`. `ranking` drag-sorts with `make_sortable` (see `.insights/feedback_nicegui_sortable_import.md`). |
| 14/16A | Tabs | One editor tab (`opens='required'`). A new post replaces the current questionnaire; earlier ones stay on disk for the agent only. Questionnaire management is a non-goal. |
| — | Badge | The editor's `draw_tab` shows the count of unanswered items (`hui.count_badge`), like the errors editor. |
| 15A | Noticing a new one | The badge, visible next to the toggle while ASIDE is closed (Part 1, 15A). The post does not publish a `Reveal`. |
| 17C | Completion | Answers are stored as they are given. *Submit* (required fields enforced) and *Submit anyway* (`incomplete: true`) set the status to `submitted`; the form then becomes read-only. |
| 18C | Protocol | The post's tool result tells the agent: tell the user a questionnaire waits in ASIDE, then call `get_findings` when they say they are done; `status` says whether it is submitted. No push, no long-poll. |
| 19A | Tiers | `post_questionnaire`: `EDIT`. Answering in the studio: `EDIT`. `get_findings`: `VIEW`. |
| 20A | Sessions | One shared set of answers per studio, synced live across sessions (detail below). Last write to a field wins. |
| 21C | Findings content | `{id, status, incomplete, answers}` plus studio version, posted/submitted timestamps, submitting principal, browser user agent, the error-ledger sequence range recorded while the questionnaire was open (`ledger_seq` from post to submit, so the agent can query the error tools with `since_seq`), and the active graph's path. |
| 22A | Names | **Questionnaire** (what the agent posts), **Check** (one do/expect/verdict item), **Findings** (what comes back). "Live check" stays the name of the activity. Tools: `post_questionnaire`, `get_findings`. |
| 23B | Teaching the format | A canon page (baked into the Farmhand docs), a short tool description holding the essentials and the page's URI, and validator errors linking it. |

### Live sync (20A)

- Store: an `AppState` in `haybale-studio` holding the current questionnaire, its answers
  and status, persisting to the storage dir on every change. The tools and the editor both
  go through it.
- Signal: `QuestionnaireChanged`, `cross_session = True`, payload-free (the existing
  observable-store pattern).
- A broadcast also reaches the session it came from, so answer changes never redraw. The
  editor keeps a `name → element` map; on the signal it re-reads the store and calls
  `set_value` only where the value differs, behind an echo guard so the update does not
  write back. Text fields commit on blur / change, not per keystroke.
- A full redraw only when the questionnaire is replaced or submitted.
- Mind `.insights/feedback_nicegui_outbox_updatevalue_stomp.md` and
  `project_nicegui_input_update_value_event.md` (`ui.input` emits `update:value`).

### Renderer mapping (NiceGUI 3.18)

| SurveyJS | NiceGUI / `hui` |
|---|---|
| `pages` | `ui.stepper` or a page header with Back / Next; `showProgressBar` maps onto it |
| `panel` | `hui.box`; `hui.expansion_section` for `state: "collapsed"`; `title` → `hui.section_label`, `description` → `hui.hint` |
| `boolean` | `ui.switch` (or `ui.toggle` with `labelTrue` / `labelFalse`) |
| `radiogroup` | `ui.radio`; `colCount` → inline / grid; `showOtherItem` → an extra `ui.input` |
| `checkbox` | a column of `ui.checkbox` (no group element) |
| `dropdown` | `hui.select_field` |
| `text` | `hui.input_field` / `hui.number_field` by `inputType`; `date` → `ui.date`, `color` → `ui.color_input`, `range` → `ui.slider` |
| `comment` | `ui.textarea` |
| `rating` | `ui.toggle` over `rateMin..rateMax`; `ui.rating` for `rateType: "stars"`; rate descriptions → `hui.hint` |
| `ranking` | rows in a `make_sortable` container |
| `html` | `ui.html(content, sanitize=True)` |
| `check` | `ui.markdown` for do/expect, `ui.toggle` for the verdict, `ui.textarea` shown on fail |
| `isRequired` | `hui.error_label`, checked on Next / Submit |
| `visibleIf` / `enableIf` / `requiredIf` | `set_visibility` / `enable` / required flag, re-evaluated on each value change |

## Non-goals

1. No questionnaire management: no list, history, archive or search in the studio.
2. Not all of SurveyJS: no functions, calculated values, piping, triggers, matrices, dynamic panels, file upload, `expression` questions.
3. No SurveyJS runtime, iframe, `postMessage` bridge or agent-written JavaScript.
4. No push to the agent: no long-poll, no notification.
5. No answers per principal.
6. No tab per questionnaire (cheap to add later: `on_payload`).
7. No top-bar toggles for the other slots.
8. No library of its own for now.

## Evidence

A Haiku subagent, given only the feature description and "use standard SurveyJS", wrote a
22-check, 9-page live check for ASIDE itself that stayed entirely inside the subset:
types `radiogroup`, `comment`, `panel`, `html`, `text`, `rating`; 24 `visibleIf`
expressions using only `=`, `<`, `and`, `notempty`. Its check pattern (panel + html +
radiogroup + comment) cost about 1.2 KB per check, 31 KB in all — the reason for the
`check` type. Its one error (a follow-up on a two-sided rating scale asked only for
`< 4`) was the agent's, not the format's.

## Slices

### Slice 1: the ASIDE slot

1. `SlotName.ASIDE` in `haywire/ui/editor/identity.py`; check every `SlotName` switch for
   an exhaustive match (`grep -rn "SlotName\." packages barn`), including `@editor`'s
   IconSlot / `opens` validation.
2. `AppShell.render()`: the ASIDE column and its divider between `main_col` and CONTEXT,
   always built (7B); resize JS emits `{slot: "aside", size}`; `HW_SLOT_ASIDE` in the
   keymap and active-slot JS and CSS.
3. Closed by default when the snapshot has no `aside` key; default width; `to_snapshot`
   / `populate_from_snapshot` unchanged (uniform dict).
4. Top-bar toggle: lit while open; opens and closes ASIDE; while closed, the group of
   vertical `draw_tab` interiors with click-to-reveal, repainted from ASIDE's
   `_refresh_bar`.
5. Tests: snapshot round-trip with `aside`; reveal opens a closed ASIDE; toggle state;
   keymap target in ASIDE; a badge repaint reaching the closed-state group.
6. Docs: `studio-arch.md` §2.1 (0A plus the ASIDE row and toggle); glossary rows Slot,
   SlotName, default_slot, AppShell, Bar, Slot bar; editor canon on `default_slot`.
7. Mark slice 1 done below.

### Slice 2: the Questionnaire

1. Store: the `AppState`, persistence under the storage dir, the `QuestionnaireChanged`
   signal.
2. Validator: the subset, `check`, the expression grammar (parsed, never `eval`), errors
   naming element and property.
3. Expression evaluator for `visibleIf` / `enableIf` / `requiredIf`.
4. Renderer: the dispatch table and builders, including `check` and `ranking`.
5. The editor: `default_slot=ASIDE`, `opens='required'`, unanswered-count badge, Submit /
   Submit anyway, read-only after submit, in-place live sync.
6. Farmhand tools: `post_questionnaire` (`EDIT`; validates, replaces, returns the
   protocol text) and `get_findings` (`VIEW`; answers plus the context block of 21C).
7. Tests: validator accept/reject (the Haiku questionnaire as a fixture, rewritten with
   `check`), expression grammar, findings shape, two-session sync, replace while open,
   tier refusals.
8. Docs: the canon page for format and protocol; glossary terms Questionnaire, Check,
   Findings; editor listed where the studio's editors are.
9. A live check of slice 2 run as a Questionnaire.
10. Mark slice 2 done below.

## Status

| Slice | State | Commit | Date | Deviations |
|---|---|---|---|---|
| 1 ASIDE slot | done, live-checked | 311394673 | 2026-11-15 | `AsideSlot(TabSlot)` in `ui/app/aside_slot.py` owns the column, the toggle and the closed-state tab group (`render_toggle`, like `IconSlot.set_footer`); the toggle icon is `hui.icon.aside` (`view_sidebar`). Glossary gains **Aside toggle**. |
| 2 Questionnaire | done, live-checked | cda456aa4, d2d4811ed, 6a37378ef | 2026-11-15 | Findings omit the active graph's path: haybale-studio does not depend on haybale-graph-editor and core has no accessor for it; the ledger range and timestamps cover the window. Findings add `title`, `unanswered`, `failed_checks` and `ledger_seq.now`. A Check's note opens on fail and on blocked. `completedHtml` is supported (shown after submit). A choice question's "Other" text is stored under `<name>-Comment`, as SurveyJS does. Agents see the tools as `haybale-studio_post_questionnaire` / `haybale-studio_get_findings`. The format page is `docs/reference/questionnaire.md` (a format spec, so `reference/`). Two posts in one second get distinct ids. Live check (2026-11-15) found a crash drawing a submitted ranking read-only (fixed d2d4811ed). Added from it: submit drops the answers of hidden questions, as SurveyJS does; a Questionnaire closes (`closed: read`) when an agent reads its submitted Findings, and *Discard* closes it (`closed: discarded`); its Findings stay readable until the next post. |
