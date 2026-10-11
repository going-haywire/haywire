# Keyboard Commands Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** App-wide keyboard shortcuts, delivered first for the graph editor (copy, cut, paste, duplicate, delete, undo, redo, select-all), with the shortcut shown on menu rows and listed in a Shortcuts editor.

**Architecture:** A shortcut triggers an `EditorCommand` — a `CommandSignal` addressed to one editor binding. One browser listener per page turns a key press into `{command_id, binding_id, position, text}`; the AppShell publishes the matching `EditorCommand` on the session bus; `EditorWrapper` delivers it only to the wrapper whose binding matches and whose principal holds the command's tier. Each editor class's keymap is derived from the `EditorCommand`s it subscribes to; the keys live on the command class.

**Tech Stack:** Python 3.12, NiceGUI 3.x (custom Vue elements), Quasar, pytest, Playwright (browser tier).

**Spec:** the inquisition of 2026-10-11, summarised in memory `project_keyboard_commands.md` and restated as **Settled decisions** below. Decision numbers (Q1…Q30) refer to that session.

## Settled decisions (the spec)

| # | Decision |
|---|---|
| Q1 | First delivery: graph editor only, on the app-wide mechanism. |
| Q2 | Registry also feeds menu-row suffixes and a read-only shortcut list. No user rebinding. |
| Q3/Q9 | A command **is** an `EditorCommand` subclass. Menu panels keep calling host verbs; the editor's `@react_on` handler calls the same verb. A menu row names its command only to show the suffix. |
| Q4 | Default keys are declared on the command class. An editor class claims a key by subscribing to the command. |
| Q5/Q25 | **Target editor** = editor root under the last pointer-down. A press outside any editor root (popups, TopBar) leaves it unchanged. If unset or no longer in the DOM: the EDIT slot's visible binding. |
| Q6/Q24 | `EditorWrapper` drops an `EditorCommand` whose `binding_id` is not its own, or whose `access` the session's principal doesn't hold. |
| Q7 | Base class name: `EditorCommand`. |
| Q8 | No applicability check: a command that doesn't apply is a silent no-op. The listener still `preventDefault`s every claimed combination. |
| Q10 | Paste through the native `paste` event (text read synchronously). Copy/Cut go keydown → signal → Python path, writing the OS clipboard via `clipboard_script()`. |
| Q11 | Keys are native when focus is inside `input, textarea, select, [contenteditable], .cm-editor, [data-hw-native-keys]`. |
| Q12 | Notation `Mod+Shift+Z`; `Mod` = Meta on macOS, Ctrl elsewhere; matched on `e.key`. First entry of `default_keys` is the displayed one. Alt combinations unsupported. |
| Q13 | A combination claimed twice within one editor class: report to the error ledger; winner = command from the editor's own library, then lowest `command_id`. Same report for browser-reserved combinations. |
| Q14 | Breaking rename `ExternalToolsSettings.editor_command` → `external_editor_command`, no migration. |
| Q15/Q18 | Commands and default keys: Copy `Mod+C`; Cut `Mod+X`; Paste `Mod+V`; Duplicate `Mod+D`; Delete `Delete`,`Backspace`; Undo `Mod+Z`; Redo `Mod+Shift+Z`,`Mod+Y`; SelectAll `Mod+A`. |
| Q16 | Paste lands at the pointer when over the canvas, else at the viewport centre. Duplicate places the copy at +40,+40 canvas units. Pasted/duplicated elements become the whole selection. |
| Q17 | SelectAll is a stateless toggle over **nodes only**: if every node is selected → clear the selection, else select all nodes (no edges). No Select None command; Escape keeps its existing meaning (cancel an edge drag). |
| Q19 | The eight commands live in `haywire.core.signals.vocabulary`. Names drop "Selection". |
| Q20 | `Paste.position` comes from a JS hook `hwPointerLocal()` on a `[data-hw-pointer-local]` element in the target editor; `None` without a hook. |
| Q21 | Each command declares an explicit, app-unique `command_id`. |
| Q22/Q23 | A **Shortcuts editor** in haybale-studio, CONTEXT slot: every editor class that claims keys, one group each; the target editor's group expanded and following. |
| Q26 | `KeyboardEvent.repeat` is ignored. |
| Q28 | Docs: new insight on canvas focus; correct the clipboard insight; known-gap note in `docs/guides/security.md`. |
| Q29 | Graph copy reuses `clipboard_script()`. Unifying the debug overlay copy is a follow-up. |
| Q30 | One ADR (0050), written with the code. |

## Global Constraints

- `access` default on `EditorCommand`: `AccessTier.EDIT`. `Copy.access` and `SelectAll.access`: `AccessTier.VIEW`.
- Duplicate offset: `DUPLICATE_OFFSET = 40.0` canvas units, both axes.
- Browser-reserved combinations (warned, never claimed): `Mod+W`, `Mod+T`, `Mod+N`, `Mod+Q`, `Mod+Shift+N`, `Mod+Shift+T`, `Mod+Shift+W`.
- Native-key selector, verbatim: `input, textarea, select, [contenteditable], .cm-editor, [data-hw-native-keys]`.
- Canonical combo order: `Mod`, `Ctrl` (macOS only, the physical Control key), `Alt`, `Shift`, then the key. A single-character key is upper-cased; named keys keep `KeyboardEvent.key` spelling (`Delete`, `Backspace`, `Escape`).
- DOM attributes: editor root `data-hw-binding="<editor_binding_id>"` and `data-hw-editor="<editor_key>"`; pointer hook element `data-hw-pointer-local`.
- Browser → Python event names: `hw-command` (`{command_id, binding_id, position, text}`) and `hw-target` (`{binding_id}`).
- Glossary and ADR edits land in Task 13, not earlier (user rule: docs describe what landed).
- Lint line length 109. Run `ruff check` **and** `ruff format --check`.
- Before Task 2: baseline `uv run ruff check` + `uv run mypy` on `packages/haywire-core/src/haywire/core/signals/ packages/haywire-core/src/haywire/ui/editor/ packages/haywire-core/src/haywire/ui/app/ barn/haybale-graph-editor/haybale_graph_editor/`. The codebase is clean; anything new after an edit is yours.
- Test tiers: iterate with single files; each slice ends with `uv run pytest -m "not browser and not perf" -n 4` and `uv run pytest -m browser -n 4`, both green.

## Review Focus

1. **A text field inside an editor root** (a node's NumberDrag or name input on the canvas): Mod+A, Delete, Backspace and Mod+Z must act on the text, not the graph. Test in Task 6 (`test_keys_native_inside_text_field`).
2. **Two graph documents open** (two EDIT-slot tabs): a command reaches only the target binding, never both. Test in Task 3 (`test_command_reaches_only_matching_binding`).
3. **The target editor's tab is closed** while it is the target: the next key goes to the EDIT slot's visible binding, not into the void. Test in Task 6 (`test_falls_back_to_edit_slot_when_target_gone`).
4. **Mod+V must still fire the native `paste` event**: the keydown for a combination mapped to a native-event command must not be `preventDefault`ed. Test in Task 9 (`test_mod_v_reaches_paste_event`).
5. **Locked nodes and SelectAll**: canvas.vue keeps locked nodes out of multi-selections, so "all" means all **unlocked** nodes; otherwise the toggle never reads "all selected" and Mod+A can never clear. Test in Task 8 (`test_select_all_skips_locked_nodes`).

---

## Slice 1 — rename

### Task 1: Rename `editor_command` → `external_editor_command`

**Files:**
- Modify: `packages/haywire-core/src/haywire/core/tooling/settings.py:9-26`
- Modify: `packages/haywire-core/src/haywire/ui/utils.py:88,115` (`_build_editor_command` → `_build_external_editor_command`)
- Modify: `tests/core/test_tooling_settings.py`, `tests/ui/errors/test_open_file_in_editor.py`
- Grep for stragglers: `rg -n "editor_command" --type py --type md -g '!docs/superpowers/**' .`

**Interfaces:** Produces `ExternalToolsSettings.external_editor_command` (same default, label, description). The persisted key changes from `tools.editor_command` to `tools.external_editor_command`; no alias.

- [ ] **Step 1:** Rename the test: `test_external_editor_command_default` asserting `ExternalToolsSettings().external_editor_command == "code --goto {file}:{line}"`; rename the helper imports in `test_open_file_in_editor.py`.
- [ ] **Step 2:** `uv run pytest tests/core/test_tooling_settings.py tests/ui/errors/test_open_file_in_editor.py` → FAIL (attribute/import missing).
- [ ] **Step 3:** Rename the field and helper. Fix the class docstring: it currently explains the field name from the tool's point of view — drop that sentence.
- [ ] **Step 4:** Same pytest → PASS. Run the grep; it returns only `docs/superpowers/` hits.
- [ ] **Step 5:** Commit `refactor(tooling)!: rename editor_command setting to external_editor_command`.

---

## Slice 2 — the mechanism, end to end

### Task 2: `EditorCommand`, key combos, and the core command vocabulary

**Files:**
- Create: `packages/haywire-core/src/haywire/core/signals/keys.py`
- Modify: `packages/haywire-core/src/haywire/core/signals/signal.py` (add `EditorCommand`)
- Modify: `packages/haywire-core/src/haywire/core/signals/vocabulary.py` (eight commands, new `# Editor commands` section, `__all__`)
- Modify: `packages/haywire-core/src/haywire/core/signals/__init__.py` (export)
- Test: `tests/core/signals/test_editor_command.py`, `tests/core/signals/test_keys.py`

**Interfaces — Produces:**

```python
# signal.py
@dataclass(frozen=True, kw_only=True)
class EditorCommand(CommandSignal):
    command_id: ClassVar[str]
    label: ClassVar[str]
    default_keys: ClassVar[tuple[str, ...]] = ()
    access: ClassVar[AccessTier] = AccessTier.EDIT
    native_event: ClassVar[Optional[str]] = None   # "paste" for Paste
    binding_id: str
    position: Optional[tuple[float, float]] = None

# keys.py
RESERVED_COMBOS: frozenset[str]
def normalize_combo(combo: str) -> str           # "mod+shift+z" -> "Mod+Shift+Z"; raises ValueError on empty/unknown modifier/Alt-less garbage like "Mod+"
def format_combo(combo: str, *, mac: bool) -> str  # "Mod+Shift+Z" -> "⌘⇧Z" (mac) / "Ctrl+Shift+Z"

# vocabulary.py — command_id, label, default_keys, access
Copy(EditorCommand)       "copy"       "Copy"        ("Mod+C",)                 VIEW
Cut(EditorCommand)        "cut"        "Cut"         ("Mod+X",)
Paste(EditorCommand)      "paste"      "Paste"       ("Mod+V",)   native_event="paste"; extra field text: str = ""
Duplicate(EditorCommand)  "duplicate"  "Duplicate"   ("Mod+D",)
Delete(EditorCommand)     "delete"     "Delete"      ("Delete", "Backspace")
Undo(EditorCommand)       "undo"       "Undo"        ("Mod+Z",)
Redo(EditorCommand)       "redo"       "Redo"        ("Mod+Shift+Z", "Mod+Y")
SelectAll(EditorCommand)  "select_all" "Select All"  ("Mod+A",)                 VIEW
```

`signal.py` must import `AccessTier` from `haywire.core.access.tier` (dependency-free module — check it imports nothing from `signals`). `format_combo` mac glyphs: `Mod`→`⌘`, `Ctrl`→`⌃`, `Alt`→`⌥`, `Shift`→`⇧`, joined with no separator; other platforms: `Mod`→`Ctrl`, joined with `+`. `Delete`→`Del`, `Backspace`→`⌫` (mac) / `Backspace`.

- [ ] **Step 1: Failing tests.**
  - `test_keys.py`: `normalize_combo("mod+shift+z") == "Mod+Shift+Z"`; `normalize_combo("Shift+Mod+a") == "Mod+Shift+A"` (canonical order); `normalize_combo("Delete") == "Delete"`; `normalize_combo("Mod+")` raises `ValueError`; `format_combo("Mod+Shift+Z", mac=True) == "⌘⇧Z"`; `format_combo("Mod+Shift+Z", mac=False) == "Ctrl+Shift+Z"`; `"Mod+W" in RESERVED_COMBOS`.
  - `test_editor_command.py`: every command in `[Copy, Cut, Paste, Duplicate, Delete, Undo, Redo, SelectAll]` has a unique `command_id`; each `default_keys` entry equals `normalize_combo(entry)`; `Copy.access is AccessTier.VIEW`, `Delete.access is AccessTier.EDIT`; `Paste(binding_id="b", text="x").text == "x"`; `Paste.native_event == "paste"`; `issubclass(Copy, CommandSignal)`; constructing `Copy()` without `binding_id` raises `TypeError`.
- [ ] **Step 2:** Run both files → FAIL (import errors).
- [ ] **Step 3:** Implement. Docstring of `EditorCommand` explains the routing contract (delivered only to the matching binding, dropped below `access`) and gives an example of declaring a library command and subscribing with `@react_on`.
- [ ] **Step 4:** Run → PASS. Also `uv run pytest tests/ui/test_signals_vocabulary.py` (it may assert `__all__` contents — update it if so).
- [ ] **Step 5:** Commit `feat(signals): EditorCommand and the core editor-command vocabulary`.

### Task 3: Wrapper delivers a command only to its binding and tier

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/editor/wrapper.py` (`_make_handler_closure._dispatch`, ~line 431)
- Test: `tests/ui/test_editor_command_delivery.py` (reuse `_make_session` / `_make_wrapper` style from `tests/ui/test_editor_handler_dispatch.py`)

**Interfaces:** Consumes `EditorCommand` (Task 2), `SessionContext.can_access(tier)`. Produces no new API — a dispatch rule.

- [ ] **Step 1: Failing tests.**
  - `test_command_reaches_only_matching_binding`: two wrappers of the same editor class, binding ids `"ed::a"` and `"ed::b"`, both `@react_on(Copy)` recording calls; `session.publish(Copy(binding_id="ed::a"))` → only wrapper a's handler ran.
  - `test_command_below_tier_is_dropped`: patch `session.context.can_access` to return `False` for `EDIT`, `True` for `VIEW`; publish `Delete(binding_id=…)` → handler not called; publish `Copy(binding_id=…)` → called.
  - `test_plain_signals_unaffected`: a non-command `Signal` still reaches both wrappers.
- [ ] **Step 2:** Run → FAIL (both wrappers receive).
- [ ] **Step 3:** In `_dispatch`, before resolving the method: if `isinstance(event, EditorCommand)` and (`event.binding_id != self.editor_binding_id` or not `self._session.context.can_access(type(event).access)`) → `return`. Comment: one line pointing at ADR 0050.
- [ ] **Step 4:** Run the new file and `tests/ui/test_editor_handler_dispatch.py` → PASS.
- [ ] **Step 5:** Commit `feat(editor): deliver EditorCommands only to their binding and tier`.

### Task 4: Keymap — derived from subscriptions, clashes reported

**Files:**
- Create: `packages/haywire-core/src/haywire/ui/keymap/__init__.py`, `packages/haywire-core/src/haywire/ui/keymap/keymap.py`
- Test: `tests/ui/keymap/test_keymap.py`

**Interfaces — Produces:**

```python
@dataclass(frozen=True)
class KeymapEntry:
    combo: str
    command: type[EditorCommand]

@dataclass(frozen=True)
class KeymapClash:
    editor_key: str
    combo: str
    winner: type[EditorCommand]
    losers: tuple[type[EditorCommand], ...]

@dataclass(frozen=True)
class Keymap:
    editors: Mapping[str, Mapping[str, KeymapEntry]]      # editor_key -> combo -> entry
    editor_labels: Mapping[str, str]                       # editor_key -> class_identity.label, for keys in `editors`
    commands: Mapping[str, type[EditorCommand]]            # command_id -> class
    clashes: tuple[KeymapClash, ...]
    reserved: tuple[tuple[str, type[EditorCommand]], ...]  # (combo, command) declared but reserved
    duplicate_ids: tuple[tuple[str, tuple[type[EditorCommand], ...]], ...]
    def to_client(self) -> dict              # {"editors": {editor_key: {combo: command_id}}, "native": {command_id: event_name}}
    def editor_commands(self, editor_key: str) -> list[type[EditorCommand]]  # sorted by label

def build_keymap(
    editor_classes: Mapping[str, type],                    # editor_key -> editor class
    can_access: Callable[[AccessTier], bool],
) -> Keymap
def report_keymap_problems(keymap: Keymap) -> None        # each clash / reserved / duplicate id -> HaywireException.create(..., severity=WARNING, category="Keyboard Shortcuts").log()
```

Rules in `build_keymap`: subscriptions come from `discover_handlers(cls)` keys filtered to `EditorCommand` subclasses; commands failing `can_access(cmd.access)` are skipped (their keys stay native); a reserved combo is recorded and not claimed; on a clash the winner is the command whose top-level package (`cls.__module__.split(".")[0]`) equals the editor class's, then the lowest `command_id`. A `command_id` declared by two different classes → recorded in `duplicate_ids`, both kept out of `commands`/`editors`.

- [ ] **Step 1: Failing tests** (fake editor classes with `@react_on`, fake commands declared in the test module):
  - `test_editor_claims_keys_of_subscribed_commands`: editor subscribing `Copy`, `Redo` → `editors[key]` has `"Mod+C"`, `"Mod+Shift+Z"`, `"Mod+Y"`.
  - `test_unsubscribed_editor_claims_nothing`: editor with no commands is absent from `editors`.
  - `test_below_tier_command_not_claimed`: `can_access` false for EDIT → `Mod+Z` absent, `Mod+C` present.
  - `test_clash_prefers_own_library_then_command_id`: two commands on `Mod+K` — one from the editor's package wins; with neither own, lower `command_id` wins; `clashes` holds one entry naming both.
  - `test_reserved_combo_recorded_not_claimed`: a command on `Mod+W` → absent from `editors`, present in `reserved`.
  - `test_duplicate_command_id_excluded`.
  - `test_to_client_shape`: `{"editors": {"ed": {"Mod+C": "copy", …}}, "native": {"paste": "paste"}}`.
  - `test_report_logs_each_problem`: patch `get_error_ledger`; one record per clash/reserved/duplicate.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement `keymap.py`. Pure: no NiceGUI import.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(keymap): derive per-editor keymaps from EditorCommand subscriptions`.

### Task 5: Editor roots carry their binding; session knows the target editor

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/app/slot.py:441-447` (`_create_panel`)
- Modify: `packages/haywire-core/src/haywire/core/session/context.py` (signal field)
- Test: extend `tests/ui/test_slot.py`; `tests/core/test_session_context_target.py`

**Interfaces — Produces:** every slot tab panel has `data-hw-binding` and `data-hw-editor` props; on `SessionContext`:
- `target_binding_id: Optional[str] = signal_field(None)` — "the editor binding that receives key commands; set from the browser on pointer-down".
- `keymap: Optional["Keymap"] = signal_field(None)` — "this session's keymap, filtered by the principal's tier; set by the AppShell". Per session, not app-wide, because the tier filter is per principal. (Type import under `TYPE_CHECKING` from `haywire.ui.keymap` — core must not import ui at runtime.)

- [ ] **Step 1: Failing tests:** after a slot adds a wrapper, `slot._panels[bid].props["data-hw-binding"] == bid` and `props["data-hw-editor"] == wrapper.editor_key`; writing `ctx.target_binding_id = "x"` fires a `@react_on(SessionContext.target_binding_id)` subscriber; same for `ctx.keymap`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Add the two props in `_create_panel` (`.props(f'data-hw-binding="{bid}" data-hw-editor="{wrapper.editor_key}"')`; binding ids may contain `/` and `:` — set via `panel._props[...]` to avoid prop-string parsing of quotes). Add the field with a comment block like `developer_mode`'s.
- [ ] **Step 4:** Run → PASS; also `uv run pytest tests/ui/test_slot.py tests/ui/test_slot_on_focus.py`.
- [ ] **Step 5:** Commit `feat(shell): mark editor roots with their binding; SessionContext.target_binding_id`.

### Task 6: `KeymapListener` — the browser side

**Files:**
- Create: `packages/haywire-core/src/haywire/ui/components/keymap/__init__.py`, `keymap_listener.py`, `keymap_listener.vue`
- Modify: `tests/ui/harness/routes.py` (page `/keymap`)
- Test: `tests/ui/harness/test_keymap_listener.py` (browser tier — the harness dir is auto-marked)

**Interfaces — Produces:**

```python
class KeymapListener(ui.element, component="keymap_listener.vue"):
    def __init__(self, *, on_command: Callable[[dict], None], on_target: Callable[[dict], None],
                 fallback_slot: str = SlotName.EDIT.value, platform: str = "auto") -> None
    def set_keymap(self, client_keymap: dict) -> None    # Keymap.to_client() shape
```

Vue behaviour (all listeners on `document`, capture phase, installed in `mounted`, removed in `unmounted`):
- `pointerdown`: `root = e.target.closest('[data-hw-binding]')`; if found and its binding differs from the current target → set target, `$emit('target', {binding_id})`. Not found → unchanged.
- `keydown`: return if `e.repeat`, or `document.activeElement?.closest(NATIVE_SELECTOR)`; build combo (`comboFromEvent(e, isMac)`, Global Constraints order; `isMac` from `platform` prop, `"auto"` → `navigator.platform` starts with `Mac`); resolve target root (current target if `document.querySelector` finds it, else first `#hw-slot-<fallback_slot> [data-hw-binding]` with `offsetParent !== null`); look up `editors[root.dataset.hwEditor][combo]`; none → return; command in `native` → return without `preventDefault`; else `preventDefault()` and `$emit('command', {command_id, binding_id, position: null, text: ''})`.
- `paste`: same native-selector guard on the event target; resolve target root; the command id mapped to event `"paste"` must be a value in that editor's map; then `preventDefault()`, read `e.clipboardData.getData('text/plain')`, position from the first visible `[data-hw-pointer-local]` in the root (`el.hwPointerLocal?.()` → `[x, y]` or `null`), emit `command`.

Harness page `/keymap`: a `KeymapListener` with `platform="other"` and keymap `{"editors": {"ed": {"Mod+A": "select_all", "Delete": "delete", "Mod+V": "paste"}}, "native": {"paste": "paste"}}`; `#hw-slot-edit` containing two roots `data-hw-binding="ed::one"` / `"ed::two"` (both `data-hw-editor="ed"`), an `<input>` inside `ed::one`; a `[data-hw-pointer-local]` div in `ed::one` whose `hwPointerLocal` returns `[12, 34]`; labels `#last-command` / `#last-target` written by the callbacks; `_stamp_synced()` last.

- [ ] **Step 1: Failing browser tests** (`goto_ready(page, "/keymap")`):
  - `test_pointerdown_sets_target`: click `ed::two` → `#last-target` text `ed::two`.
  - `test_command_goes_to_target`: click `ed::two`, press `Control+a` → `#last-command` shows `select_all@ed::two`.
  - `test_keys_native_inside_text_field`: focus the input, type `abc`, press `Control+a` → `#last-command` unchanged, and `input.selectionStart == 0 and selectionEnd == 3`.
  - `test_repeat_ignored`: dispatch a `keydown` with `repeat: true` via `page.evaluate` → no command.
  - `test_unclaimed_key_not_prevented`: press `Control+s` → no command (and `defaultPrevented` false, checked with an evaluate-installed probe listener).
  - `test_falls_back_to_edit_slot_when_target_gone`: click `ed::two`, remove that element via evaluate, press `Delete` → command `delete@ed::one`.
  - `test_pointerdown_outside_roots_keeps_target`: click `ed::two`, click the page body outside `#hw-slot-edit` → target still `ed::two`.
- [ ] **Step 2:** `uv run pytest tests/ui/harness/test_keymap_listener.py` → FAIL.
- [ ] **Step 3:** Implement the element and page. Labels format `"{command_id}@{binding_id}"`.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(keymap): KeymapListener resolves the target editor and key commands in the browser`.

### Task 7: AppShell mounts the listener and publishes commands

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/app/shell.py` (build ~line 870; lifecycle unsubs; new `_rebuild_keymap`, `_on_key_command`, `_on_key_target`)
- Test: `tests/ui/test_shell_keymap.py`

**Interfaces:** Consumes `build_keymap`, `report_keymap_problems`, `Keymap` (Task 4), `KeymapListener` (Task 6), `SessionContext.target_binding_id` / `SessionContext.keymap` (Task 5). Produces `ctx.keymap` kept current (read by Task 12).

Behaviour: build once in the page build (`build_keymap({k: registry.get(k) for k in registry.list_names()}, ctx.can_access)`), `report_keymap_problems` once per process per keymap content (dedupe on `frozenset` of problems so N sessions don't log N times), assign `ctx.keymap`, push `to_client()`; rebuild + push on `self._editor_registry.add_batch_event_subscriber(...)` and on `RosterChanged` (tier may change); remove the batch subscriber in the shell's teardown alongside `_lifecycle_unsubs`. `_on_key_command(payload)`: look up `keymap.commands[payload["command_id"]]` (unknown id → log debug, return); construct with `binding_id`, `position` (tuple or `None`), and `text` only if the class has a `text` field; `self.session.publish(cmd)`. `_on_key_target(payload)`: `ctx.target_binding_id = payload["binding_id"]`.

- [ ] **Step 1: Failing tests** (no browser; call the handlers directly on a shell built the way `tests/ui/test_app_shell.py` builds one):
  - `test_key_command_publishes_editor_command`: `_on_key_command({"command_id": "copy", "binding_id": "ed::a", "position": None, "text": ""})` → a bus subscriber receives `Copy(binding_id="ed::a")`.
  - `test_paste_carries_text_and_position`: `{"command_id": "paste", "position": [1, 2], "text": "t", …}` → `Paste(position=(1.0, 2.0), text="t")`.
  - `test_unknown_command_id_ignored`.
  - `test_key_target_sets_context`.
  - `test_keymap_rebuilt_on_editor_reload`: fire the registry batch callback → `KeymapListener.set_keymap` called again.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run → PASS; `uv run pytest tests/ui/test_app_shell.py tests/ui/test_shell_account_chrome.py`.
- [ ] **Step 5:** Commit `feat(shell): mount KeymapListener and publish EditorCommands`.

### Task 8: Graph editor handles Copy, Delete, Undo, Redo, SelectAll

**Files:**
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_editor.py` (handlers; `_canvas_manager` exists at line ~157)
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/graph_canvas_manager.py` (public verbs)
- Modify: `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/selection.py` (`select_all_toggle`; copy via `clipboard_script`)
- Modify: `docs/guides/security.md` (known-gap note in §9 "Managing principals"), create `.insights/project_canvas_focus_not_browser_focus.md` + CLAUDE.md trap line
- Test: `tests/ui/test_canvas_handlers/test_selection_handlers.py`, new `tests/graph_editor/test_graph_editor_commands.py`

**Interfaces — Produces:**

```python
# GraphCanvasManager
def copy_selection(self) -> None
def delete_selection(self) -> None
def select_all_toggle(self) -> None

# SelectionHandlers
def select_all_toggle(self, is_locked: Callable[[str], bool]) -> None
```

`GraphEditor` handlers (`@react_on`, one per command): `Copy` → `self._canvas_manager.copy_selection()`; `Delete` → `delete_selection()`; `Undo` → `self._do_undo(context)`; `Redo` → `self._do_redo(context)`; `SelectAll` → `select_all_toggle()`. Each no-ops when `_canvas_manager` is `None`. The manager's `copy_selection`/`delete_selection` build the same `UserCopySelectedEvent`/`UserRemoveEvent` from `EditState` that `SelectionToolbarProvider` does and route them through `_handle_canvas_event`; then make `SelectionToolbarProvider.copy_selection/delete_selection` call the manager's — no third copy of that code (check `SelectionToolbarProvider` can reach it; if not, extract a module-level helper both call).

`select_all_toggle`: `candidates = {id for id in graph.node_wrappers if not is_locked(id)}`; if `candidates and self.selected_nodes == candidates` → clear both sets; else nodes = candidates, edges = ∅. Write `EditState` (`active_node`/`active_edge` = `None`, `ctx.active_component = None`), publish `SelectionMoved()`, `visual_layer.sync_selections(nodes, edges)`. The manager passes `self.visual_layer._is_locked` (make it public: `is_locked`).

Copy: replace the `navigator.clipboard.writeText` line in `process_copy_selection` with `ui.run_javascript(clipboard_script(json.dumps(payload)))`.

Docs in this task: security.md gets a "Known gap" admonition: in the graph canvas a `view` principal can still delete, paste and move through the menus and gestures; keyboard commands are tier-gated (ADR 0050) but the menus are not yet. The insight file states the trap: canvas mousedown gestures `preventDefault`, so focus never reaches the canvas and `document.activeElement` cannot identify the editor in use; the target editor is tracked by pointer-down instead (`KeymapListener`). Add the CLAUDE.md "Traps and gotchas" one-liner.

- [ ] **Step 1: Failing tests.**
  - `test_select_all_selects_every_unlocked_node`: graph with nodes a, b, c; nothing selected → `selected_nodes == {"a","b","c"}`, `selected_edges == set()`, `sync_selections` called with those.
  - `test_select_all_twice_clears`: second call → both sets empty.
  - `test_select_all_from_partial_selects_all`: selection `{"a"}` → all three.
  - `test_select_all_skips_locked_nodes`: `is_locked("c")` true → `{"a","b"}`; a second call clears.
  - `test_copy_uses_clipboard_script`: patch `ui.run_javascript`; the JS contains `execCommand('copy')`.
  - `test_graph_editor_routes_commands` (graph_editor tests): a `GraphEditor` with a mock `_canvas_manager`; calling the handlers for `Copy`, `Delete`, `SelectAll` calls the manager verbs; `Undo` with `can_undo()` true calls `editor.undo()` and publishes `GraphDataMutated`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement code + the three docs edits.
- [ ] **Step 4:** Run the two test files plus `tests/ui/test_canvas_handlers/` → PASS.
- [ ] **Step 5:** Slice gate: `uv run pytest -m "not browser and not perf" -n 4 > /tmp/t.log 2>&1; echo "exit=$?"` and `uv run pytest -m browser -n 4`; ruff check + format --check; mypy on the baseline paths. All green. Manual check with the `run` skill: open a graph, click the canvas, Mod+A / Mod+A / Mod+C / Delete / Mod+Z.
- [ ] **Step 6:** Commit `feat(graph-editor): keyboard copy, delete, undo, redo and select-all`.

---

## Slice 3 — clipboard commands

### Task 9: Paste through the native event, at the pointer

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/components/graph/canvas.vue` (root gets `data-hw-pointer-local`; `mounted` sets `this.$refs.container.hwPointerLocal`; `handleMouseMove` records last client position)
- Modify: `graph_canvas_manager.py` (`paste(position, text)`), `graph_editor.py` (`@react_on(Paste)`)
- Modify: `.insights/feedback_clipboard_secure_context.md` (scope the "FIXED" claim: it covers `hui` copy buttons; graph copy now uses `clipboard_script`, graph keyboard paste uses the native event; the menu's Paste still uses `readText()` and needs the session mirror on a LAN)
- Test: `tests/ui/harness/test_keymap_listener.py` (extend), harness `/graph-keymap` page, `tests/graph_editor/test_graph_editor_commands.py`

**Interfaces:** Consumes `Paste` (Task 2), the listener's `paste` path (Task 6). Produces `GraphCanvasManager.paste(position: tuple[float, float], text: str) -> None` (builds `UserPasteClipboardEvent(canvasX, canvasY, clipboardText=text)` and dispatches it, reusing the existing timestamp arbitration and select-the-pasted behaviour).

`hwPointerLocal()` returns `[x, y]` from `_transformScreenToSVG(lastClientX, lastClientY)` when the last pointer position lies inside the zoom-pan container's rect, else the transform of that rect's centre. `GraphEditor._on_paste`: `position is None` → `ui.notify("Nothing to paste here", type="warning")` and return.

- [ ] **Step 1: Failing tests.**
  - `test_mod_v_reaches_paste_event` (listener page): focus `ed::one`, `page.evaluate` dispatches a `ClipboardEvent('paste')` with a `DataTransfer` holding `"hello"` after a `Control+v` keydown → `#last-command` shows `paste@ed::one`, and a probe confirms the keydown was not `defaultPrevented`.
  - `test_paste_carries_pointer_position`: the command payload's position is `[12, 34]`.
  - `test_paste_in_text_field_is_native`: paste with the input focused → no command.
  - `test_graph_editor_paste_uses_position`: handler calls `manager.paste((5.0, 6.0), "t")`; `position=None` → no call.
  - Browser `/graph-keymap` page (a real `GraphCanvasManager`, see `/graph-reconnect` for the pattern, plus a `KeymapListener` with the graph editor's keymap): copy a node with Control+c, move the mouse, dispatch paste with the copied JSON → node count +1 and the new node is the only selected one.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement; update the insight.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(graph-editor): keyboard paste at the pointer via the native paste event`.

### Task 10: Cut and Duplicate

**Files:**
- Modify: `selection.py` (`duplicate_selection`), `graph_canvas_manager.py` (`cut_selection`, `duplicate_selection`), `graph_editor.py` (`@react_on(Cut)`, `@react_on(Duplicate)`)
- Test: `tests/ui/test_canvas_handlers/test_selection_handlers.py`, `tests/graph_editor/test_graph_editor_commands.py`

**Interfaces — Produces:**

```python
DUPLICATE_OFFSET = 40.0  # selection.py, module level
# SelectionHandlers
def duplicate_selection(self) -> None
# GraphCanvasManager
def cut_selection(self) -> None        # copy_selection() then delete_selection()
def duplicate_selection(self) -> None
```

`duplicate_selection`: no selected nodes → return. `payload = build_clipboard_payload(graph, nodes, edges, session_id)`; paste via `self.editor.paste_clipboard(payload, bbox.min_x + DUPLICATE_OFFSET, bbox.min_y + DUPLICATE_OFFSET)` (`bbox = payload["bounding_box"]`); does **not** touch `EditState.clipboard` or the OS clipboard; then the same select-the-new-elements tail as `process_paste_clipboard` — extract that tail into `_select_pasted(new_node_ids, new_edge_ids)` and call it from both.

- [ ] **Step 1: Failing tests.**
  - `test_duplicate_offsets_and_selects_copy`: patch `editor.paste_clipboard` to return `(["n2"], [])`; called with `min_x + 40, min_y + 40`; `selected_nodes == {"n2"}`.
  - `test_duplicate_leaves_clipboard_untouched`: `EditState.clipboard` unchanged; `ui.run_javascript` not called.
  - `test_duplicate_nothing_selected_noop`.
  - `test_cut_copies_then_deletes`: manager's `cut_selection` emits `UserCopySelectedEvent` then `UserRemoveEvent` with the same ids, in that order.
  - `test_cut_is_one_undo_step`: on a real `Editor` with two nodes, cut one → `history_manager` gained exactly one action; `undo()` restores it.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run → PASS. Slice gate as in Task 8 Step 5.
- [ ] **Step 5:** Commit `feat(graph-editor): keyboard cut and duplicate`.

---

## Slice 4 — making shortcuts visible

### Task 11: Shortcut hints on menu rows and toolbar buttons

**Files:**
- Modify: `packages/haywire-core/src/haywire/ui/elements/elements.py` (`menu_row(..., command=None)`, new `key_hint(command)`, `icon_action(..., command=None)` appends the hint to the tooltip)
- Modify: `packages/haywire-core/src/haywire/ui/app/shell.py` (CSS for `.hw-keys-mac` / `.hw-keys-other`)
- Modify: `keymap_listener.vue` (on mount: `document.documentElement.dataset.hwPlatform = isMac ? 'mac' : 'other'`)
- Modify call sites: `CopySelectionMenuPanel`, `DeleteSelectionMenuPanel` (`panels/graph/menu/selection/selection.py`), `PastePanel` (`panels/graph/menu/graph/context.py`), the selection toolbar's copy/delete icons, undo/redo buttons in `graph_editor.py`
- Test: `tests/ui/test_menu_row.py`, `tests/ui/test_key_hint.py`

**Interfaces — Produces:** `hui.key_hint(command: type[EditorCommand]) -> ui.element` — renders nothing when `command.default_keys` is empty; otherwise two spans, `<span class="hw-keys-mac">{format_combo(k, mac=True)}</span><span class="hw-keys-other">{format_combo(k, mac=False)}</span>` for `k = default_keys[0]`, with classes `text-xs hw-text-dim ml-auto font-mono` (design guide §8, "Keyboard shortcut suffix"). CSS: `html[data-hw-platform="mac"] .hw-keys-other, html:not([data-hw-platform="mac"]) .hw-keys-mac { display: none; }`. Tooltips can't hold spans: `icon_action(command=…)` builds its tooltip as `f"{tooltip} ({format_combo(k, mac=False)})"` — accepted limitation, noted in the docstring.

The hint shows the class default, not the per-editor keymap winner: only clashes differ, and those are reported (Q13).

- [ ] **Step 1: Failing tests:** `menu_row("Copy", command=Copy)` contains a `.hw-keys-mac` with text `⌘C` and `.hw-keys-other` with `Ctrl+C`; `menu_row("X")` has neither; `key_hint` of a command with no keys renders nothing; `icon_action(hui.icon.copy, tooltip="Copy", command=Copy)` tooltip text `Copy (Ctrl+C)`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement and update the call sites.
- [ ] **Step 4:** Run → PASS; `uv run pytest tests/ui/test_canvas_handlers/test_selection_panels_unified.py tests/ui/graph_canvas/`.
- [ ] **Step 5:** Commit `feat(ui): show keyboard shortcuts on menu rows and toolbar tooltips`.

### Task 12: Shortcuts editor

**Files:**
- Create: `barn/haybale-studio/haybale_studio/editors/shortcuts_editor.py`
- Modify: `barn/haybale-studio/haybale_studio/editors/__init__.py`, `packages/haywire-core/src/haywire/ui/elements/icons.py` (add `keyboard: Final[str] = "keyboard"`)
- Test: `tests/studio/test_shortcuts_editor.py`

**Interfaces:** Consumes `SessionContext.keymap` and `SessionContext.target_binding_id` (Task 5, kept current by Task 7), `EditorWrapper.split_id`, `Keymap.editor_labels`, `key_hint` (Task 11).

```python
@editor(label="Shortcuts", icon=hui.icon.keyboard, default_slot=SlotName.CONTEXT,
        description="Keyboard shortcuts of every editor, grouped by editor.", order=60)
class ShortcutsEditor(BaseEditor):
    @redraw_on(SessionContext.target_binding_id, SessionContext.keymap)
    def _on_keymap_or_target(self, ctx, signal) -> None: ...
```

Draw: one `ui.expansion` per editor key in `keymap.editors`, titled with the editor's `class_identity.label`, ordered by label; `value=True` for the target editor's key (`split_id(ctx.target_binding_id)[0]`), with an "active" chip. Rows: command label, then `key_hint`-style spans for **every** combo in that editor's map pointing at the command. A clash for that editor marks the losing command's row with `hui.warning_label("Shadowed by <winner label>")`. Empty keymap → `hui` empty-state text "No editor declares keyboard shortcuts."

- [ ] **Step 1: Failing tests** (NiceGUI `user` fixture; see `.insights/feedback_nicegui_user_simulation_find.md`): groups render per editor; the target editor's group is open and the others closed; changing `target_binding_id` re-expands; a clash row shows the warning; both `Delete` and `Backspace` appear for Delete.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(studio): Shortcuts editor`.

### Task 13: ADR, glossary, guides

**Files:**
- Create: `docs/adr/0050-keyboard-commands-are-editor-addressed-command-signals.md` (follow `docs/reference/doc-authoring.md` and the ADR front matter used by 0049)
- Modify: `docs/reference/glossary.md`, `docs/guides/signals.md` (vocabulary table: an "Editor commands" table with the eight commands; a short "Adding a keyboard command" section), `docs/components/editors/editor-canon.md` (subscribing to `EditorCommand`s claims keys), mkdocs nav if the ADR index needs it
- Run: `uv run mkdocs build --strict` (or the docs test the repo uses for snippet refs)

ADR content, per Q30: context (no shortcuts; `CommandSignal` already exists; panels own verbs via host Protocols), decision (`EditorCommand` + binding/tier filter in the wrapper; keys on the command class; keymap derived from subscriptions; clash rule; target editor = last pointer-down with EDIT-slot fallback; explicit `command_id`; native paste vs signal copy), considered options (command component kind; panel-as-command; separate keymap file; focus-based and hover-based targeting; editor self-filtering), consequences (menus not yet tier-gated; one combination per command app-wide; Alt unsupported; `command_id` is the future rebinding key).

Glossary entries (Term | Definition | Aliases to avoid):
- **EditorCommand** — a `CommandSignal` delivered only to the editor whose binding matches its `binding_id`, and only when the principal holds its `access` tier. Distinct from the **external editor command** setting (`tools.external_editor_command`). | key command, shortcut signal
- **command_id** — a command's stable app-wide id; keys the keymap and any future rebinding. | command name
- **Keymap** — per editor class, combination → command, derived from the `EditorCommand`s the editor subscribes to. | shortcut table, bindings
- **Target editor** — the editor binding that receives key commands: the editor root under the last pointer-down, else the EDIT slot's visible editor. | focused editor, active editor
- **Shortcuts editor** — the CONTEXT-slot editor listing every editor's keymap. | cheat sheet, help panel
- Update **Selection axis** (command target) to mention keyboard commands.

- [ ] **Step 1:** Write the ADR, glossary and guide edits.
- [ ] **Step 2:** Docs build/snippet check → PASS.
- [ ] **Step 3:** Full gate: `uv run pytest -m "not browser and not perf" -n 4`, `uv run pytest -m browser -n 4`, `uv run ruff check .`, `uv run ruff format --check .`, the CLAUDE.md mypy command. All green.
- [ ] **Step 4:** Commit `docs: ADR 0050 keyboard commands, glossary and guides`.

---

## Non-goals

App-level commands (save, close tab, `?`, command palette); user rebinding; applicability greying; Alt/Option combinations and multi-step sequences; auto-repeat; navigation commands (frame all/selection, nudge, Tab into Group); new menu rows for Cut/Duplicate/Select All; exposing `EditorCommand`s as Farmhand tools; shortcuts for editors other than the graph editor.

## Follow-ups (not in this plan)

1. **Access gap in graph menus and gestures:** `CopySelectionMenuPanel`, `DeleteSelectionMenuPanel`, `PastePanel` declare no `access=`, and canvas gestures (move, connect) have no tier check, so a `view` principal can mutate a graph — contradicting ADR 0027 ("every affordance that reaches one is hidden"). Fix the code, then remove the security.md known-gap note.
2. **Clipboard helper unification:** `debug_overlay.vue` `_copyToClipboard()` duplicates `clipboard_script()` ("keep them in step"); move both onto one JS module.
3. **The menu's Paste** still uses `navigator.clipboard.readText()` (permission prompt; absent on a LAN over http). Consider routing it through the same session-mirror-first path or a native paste prompt.
