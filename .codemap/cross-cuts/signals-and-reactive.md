# Cross-cut: Signals & Reactive Properties

> Haywire's UI and engine event plumbing: a typed signal bus in `core/signals/` plus reactive property descriptors (`shadow()` / `watch()`) used throughout settings and node properties.

## Overview

Two related mechanisms keep Haywire reactive:

1. **Signals**: a typed pub/sub bus with a vocabulary file. Components publish and subscribe through a `SignalPeer` that owns a `SignalBus` scoped to a session. Used for "something happened" notifications across engine, UI and libraries.
2. **Reactive properties**: `shadow()` and `watch()` descriptors on nodes and settings. The settings descriptor (`core/settings/descriptor.py`) is the canonical pattern. Do not introduce a competing reactive pattern.

They combine: a property change fires through the field's cell, and panels bound to that cell redraw via NiceGUI.

## Modules Involved

| Module | Role | Manifest |
|--------|------|----------|
| haywire-core-engine | Signal bus, peer, dispatcher, vocabulary, settings descriptors | [→ modules/haywire-core-engine.md](../modules/haywire-core-engine.md) |
| haywire-core-ui | Panels and editors subscribe; reactive UI helpers | [→ modules/haywire-core-ui.md](../modules/haywire-core-ui.md) |
| haybale-studio | State containers are major signal producers and consumers | [→ modules/haybale-studio.md](../modules/haybale-studio.md) |
| haybale-haystack | Defines haystack-scoped signals (`haybale_haystack/signals.py`) | [→ modules/haybale-haystack.md](../modules/haybale-haystack.md) |
| haybale-models | Defines model signals (`haybale_models/signals.py`) | [→ modules/haybale-models.md](../modules/haybale-models.md) |

## Flow

```
Producer (node / setting / state container / agent tool)
    │
    │  peer.publish(SomeSignal())      — typed, payload-free by convention
    ▼
SignalPeer (core/signals/peer.py)
    │
    ├─ cross_session=False ──▶ own SignalBus only
    │
    └─ cross_session=True  ──▶ SignalDispatcher (core/signals/dispatcher.py)
                                   │  — fans out to every registered peer
                                   ▼
                               each peer → its SignalBus
    ▼
SignalBus (core/signals/bus.py)
    │   — exact-class dispatch; vocabulary in vocabulary.py
    ▼
Subscribers (panels, editors, redraw and react decorators)
    ▼
NiceGUI re-render
```

A `Session` is one kind of `SignalPeer` (the browser-tab kind). The transport imports only `Signal`, with no NiceGUI or browser assumptions. A non-browser peer (MCP host, CLI, headless embedding) can join the same fan-out. Emitters that own no peer reach the dispatcher directly.

Reactive descriptor path (cell-authoritative model, see [ADR 0013](../../docs/adr/0013-settings-single-cell.md)):

```
Settings class defines shadow("foo") / watch("bar")
    ↓ each field's value lives in a per-field DataField cell
    ↓ persistent fields borrow the registry-owned cell (one cell, N views)
    ↓ panel/widget binds the shared cell directly
    ↓ any writer fires the cell's on_changed, the one notification channel
```

## Key Files

- `packages/haywire-core/src/haywire/core/signals/bus.py`: `SignalBus`.
- `packages/haywire-core/src/haywire/core/signals/peer.py`: `SignalPeer`, bus owner and fan-out member.
- `packages/haywire-core/src/haywire/core/signals/dispatcher.py`: `SignalDispatcher`, cross-peer fan-out.
- `packages/haywire-core/src/haywire/core/signals/vocabulary.py`: canonical signal names.
- `packages/haywire-core/src/haywire/core/signals/descriptor.py`: host and descriptor protocol.
- `packages/haywire-core/src/haywire/core/settings/descriptor.py`: `shadow()` and `watch()`.
- `packages/haywire-core/src/haywire/core/settings/registry.py`: settings registry.
- `tests/core/test_signals/test_dispatcher_and_peer.py`: transport in isolation.
- `tests/ui/test_signal_bus.py`, `tests/ui/test_signal_handler_decorators.py`, `tests/ui/test_signals_vocabulary.py`: UI signal test patterns.
- `tests/core/test_reactive.py`, `tests/libraries/test_clipboard_reactive.py`: reactive descriptor patterns.

## Gotchas

- Do not introduce a parallel reactive system. The `shadow()` and `watch()` pattern is canonical.
- NiceGUI slot stack is per asyncio task. Signal handlers that schedule UI work must not wrap `ui.notify()` in `asyncio.ensure_future`. Use the safe patterns in `.insights/feedback_nicegui_async.md`.
- The signal vocabulary is checked by `tests/ui/test_signals_vocabulary.py`. Adding a signal requires updating `vocabulary.py`.
- For settings UI, read `docs/architecture/settings/settings-arch.md` and `docs/components/settings/setting-canon.md`.
- After mutating reactive state in a test, call `force_immediate_validation()` before asserting when the result is needed synchronously.
