# Cross-cut: Signals & Reactive Properties

> Haywire's UI/engine event plumbing: a typed signal bus in `core/session/signals/` plus reactive property descriptors (`shadow()` / `watch()`) used throughout settings and node properties.

## Overview

Two related-but-distinct mechanisms keep Haywire reactive:

1. **Signals** — a typed pub/sub bus with a vocabulary file. Components emit and listen on a `SignalBus` scoped to a session. Used for "something happened" notifications across engine, UI, and libraries.
2. **Reactive properties** — `shadow()` and `watch()` descriptors on nodes/settings that materialise observable values which the UI binds to. The settings descriptor system (`core/settings/descriptor.py`) is the canonical pattern; do not introduce competing reactive patterns.

The two combine: a property change typically fires a signal on the bus, panels subscribe, and the UI redraws via NiceGUI bindings.

## Modules Involved

| Module | Role | Manifest |
|--------|------|----------|
| haywire-core-engine | Signal bus, signal vocabulary, settings descriptors | [→ modules/haywire-core-engine.md](../modules/haywire-core-engine.md) |
| haywire-core-ui | Panels/editors subscribe; reactive UI helpers | [→ modules/haywire-core-ui.md](../modules/haywire-core-ui.md) |
| haybale-studio | State container is a major signal producer/consumer | [→ modules/haybale-studio.md](../modules/haybale-studio.md) |
| haybale-haystack | Defines haystack-scoped signals (`haybale_haystack/signals.py`) | [→ modules/haybale-haystack.md](../modules/haybale-haystack.md) |

## Flow

```
Producer (node / setting / state container)
    │
    │  emit("vocabulary.key", payload)
    ▼
SignalBus (core/session/signals/bus.py)
    │   — typed dispatch, vocabulary in vocabulary.py
    ▼
Subscribers (panels, editors, signal_handler_decorators)
    │   — invoke ui callbacks; rebind reactive props
    ▼
NiceGUI re-render
```

Reactive descriptor path:

```
Settings class defines shadow("foo") / watch("bar")
    ↓ registered in SettingsRegistry (core/settings/registry.py)
    ↓ resolved per node/library scope
    ↓ panel binds to the descriptor's reactive value
    ↓ change triggers re-evaluation + signal emission
```

## Key Files

- `packages/haywire-core/src/haywire/core/session/signals/bus.py` — the SignalBus.
- `packages/haywire-core/src/haywire/core/session/signals/vocabulary.py` — canonical signal names.
- `packages/haywire-core/src/haywire/core/session/signals/descriptor.py` — host/descriptor protocol.
- `packages/haywire-core/src/haywire/core/settings/descriptor.py` — `shadow()` / `watch()`.
- `packages/haywire-core/src/haywire/core/settings/registry.py` — SettingsRegistry.
- `tests/ui/test_signal_bus.py`, `tests/ui/test_signal_handler_decorators.py`, `tests/ui/test_signals_vocabulary.py` — test patterns to follow.
- `tests/core/test_reactive.py`, `tests/libraries/test_clipboard_reactive.py` — reactive descriptor patterns.

## Gotchas

- Don't introduce a parallel reactive system. The `shadow()`/`watch()` descriptor pattern is canonical.
- NiceGUI slot stack is per-asyncio-task: signal handlers that schedule UI work via `asyncio.ensure_future` will crash `ui.notify`. Use the three safe patterns in `.insights/feedback_nicegui_async.md`.
- Signal vocabulary is checked by `tests/ui/test_signals_vocabulary.py` — adding a new signal requires updating `vocabulary.py`.
- For settings UI panels, refer to `docs/architecture/<settings>/<settings>-arch.md` and `docs/components/<settings>/<settings>-canon.md`.
- After mutating reactive state in a test, run `force_immediate_validation()` before asserting.
