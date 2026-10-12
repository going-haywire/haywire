---
name: keyboard-commands-are-editor-addressed-command-signals
description: A keyboard shortcut publishes an EditorCommand, a CommandSignal addressed to one editor binding and gated by an access tier; an editor claims a key by subscribing to the command that declares it
status: accepted
see-also: ADR-0027, ADR-0029, ADR-0049
level: ui
---

# Keyboard commands are editor-addressed command signals

**Context.**

- The studio had no keyboard shortcuts. Copy, paste and delete in the graph editor were reachable only through the right-click menu and the selection toolbar.
- `CommandSignal` already carries imperatives on the session bus ("do X"), and editors already subscribe to signals with `@react_on` / `@redraw_on`.
- Panels own their verbs through their host's `provides` Protocol (ADR 0029): a menu panel calls `self.actions.copy_selection()`, and the editor implements it. A shortcut has to reach the editor's verbs too.
- Several editors are open at once, and several tabs of one editor class (one per graph). A key press must reach exactly one of them, and only if the session's principal may perform it (ADR 0027).

**Decision.**

- **A shortcut publishes an `EditorCommand`.** `EditorCommand` (`haywire.core.signals.signal`) is a `CommandSignal` with a `binding_id` naming the editor binding it is addressed to and an optional `position` in that editor's coordinates. The framework vocabulary declares eight: `Copy`, `Cut`, `Paste`, `Duplicate`, `Delete`, `Undo`, `Redo`, `SelectAll` (`haywire.core.signals.vocabulary`).
- **The wrapper filters.** `EditorWrapper` drops an `EditorCommand` whose `binding_id` is not its own `editor_binding_id`, or whose `access` tier the session's principal does not hold. `access` defaults to `edit`; `Copy` and `SelectAll` are `view`. An editor's handler therefore never checks either.
- **Keys live on the command class.** Each command declares a `command_id` (stable, unique app-wide), a `label`, and `default_keys` in the canonical notation of `haywire.core.signals.keys` (`Mod+Shift+Z`; `Mod` is Cmd on macOS, Ctrl elsewhere), normalised before binding. Combos are matched on `KeyboardEvent.key`, except that a letter or digit typed as a non-ASCII character under Ctrl/Cmd without Alt (a non-Latin layout), or under Option on macOS, is matched on its physical key (`KeyboardEvent.code`).
- **The keymap is derived from subscriptions.** An editor class claims a command's keys by subscribing to it. `build_keymap` (`haywire.ui.keymap`) reads every editor class's subscriptions and resolves them for the principal's tier: a command the principal cannot perform binds nothing, so its keys keep their browser behaviour. The AppShell rebuilds the keymap after a hot-reload and on `RosterChanged`, and stores it on `SessionContext.keymap`.
- **Clash rule.** When two commands of one editor declare the same combo, the command from the editor's own top-level package wins, then the lowest `command_id`. A browser-reserved combo (`Mod+W`, `Mod+T`, `Mod+N`, `Mod+Q`, `Mod+Shift+N`, `Mod+Shift+T`, `Mod+Shift+W`) is never bound. A combo that does not parse is never bound. A `command_id` declared by two classes binds neither. Each problem is logged once per process to the error ledger.
- **Target editor.** One `KeymapListener` per page tracks the editor root (`[data-hw-binding]`) under the last pointer-down, in the capture phase. A press outside any editor root leaves the target unchanged. When the target is unset, has left the page or is hidden, the first visible editor root in the EDIT slot receives the command. The target is mirrored to `SessionContext.target_binding_id`.
- **Text fields and dialogs keep their keys.** With focus inside `input, textarea, select, [contenteditable], .cm-editor, [data-hw-native-keys]`, or a key or paste event inside an open dialog (`.q-dialog`), the listener does nothing. Menus and popups do not stop it. A combo in the target's keymap has its browser default suppressed; key auto-repeat is ignored.
- **Paste is native; copy is a signal.** `Paste` declares `native_event = "paste"`: the listener lets `Mod+V` through and reports the browser's `paste` event, whose clipboard text is readable synchronously in any context, plus the pointer position from the editor's `[data-hw-pointer-local]` hook. `Copy` and `Cut` go key press → signal → Python and write the OS clipboard through `clipboard_script()`.
- **Menus show, handlers act.** A menu row or toolbar button names its command (`hui.menu_row(command=...)`, `hui.icon_action(command=...)`) only to draw the shortcut. The editor's `@react_on` handler calls the editor's own verb. In the graph editor these are the canvas verbs (`GraphCanvasManager.copy_selection`, `cut_selection`, `delete_selection`, `duplicate_selection`); copy and delete build their canvas events with the same builders the context menu and selection toolbar use (`copy_selection_event`, `remove_selection_event`), and additionally keep only the selected ids of the canvas's own graph. Cut and Duplicate have no menu row.
- **Shortcuts editor.** A CONTEXT-slot editor in haybale-studio lists every editor's keymap, one group per editor, with the target editor's group open.

**Considered options.**

- *A command component kind* (registered like nodes and panels, with its own registry). Rejected: an editor would still have to say which commands it handles, so the registry would duplicate the subscription that already says it.
- *A panel as the command.* Rejected: a panel's verb is reached through a host it is rendered on. A key press has no host until an editor is chosen, and a panel that is not drawn would have no command.
- *A separate keymap file.* Rejected for this delivery: nothing rebinds keys yet, and a second source of truth could disagree with the command classes. `command_id` is the key such a file would use.
- *Focus-based targeting* (`document.activeElement`). Rejected: canvas gestures `preventDefault` their pointer-down, so a click never focuses the canvas.
- *Hover-based targeting.* Rejected: moving the pointer across another editor on the way to a key would retarget the press.
- *Editors filtering their own commands.* Rejected: every handler of every editor would repeat the binding and tier check, and one that forgot would act on another tab's key press.

**Consequences.**

- Only `EditorWrapper`'s handler subscriptions are filtered. A panel-hosted bus subscription (`PanelRedrawCoordinator`, which wires `PropertiesEditor`'s panels) subscribes on the session directly and receives, unfiltered, any `EditorCommand` a panel lists in `redraw_on=`.
- The graph canvas's menus and gestures are not tier-gated yet: a `view` principal cannot delete with a key, but can still delete and paste through the context menu and the selection toolbar, and move and connect nodes by dragging. The [security guide](../guides/security.md) records the gap; gating them is a follow-up.
- A command has one set of keys app-wide, and one combination is displayed for it: the first `default_keys` entry. On macOS the Delete row therefore shows `Del`, though `⌫` also deletes.
- No default uses Alt/Option, and Alt combinations are not guaranteed to work across keyboard layouts: outside macOS, Ctrl+Alt is AltGr and is matched on the character it types. Multi-key sequences are unsupported.
- `command_id` is the key a future user rebinding would store.
- Keyboard Copy, Cut, Delete and Duplicate act on the part of the session's selection that belongs to the target canvas's own graph, so a selection left in another graph does nothing. The context menu and selection toolbar act on the whole, unfiltered selection through their own implementations of the `SelectionActions` protocol; unifying the keyboard and menu verbs into one is an open follow-up.
